# ABOUTME: Post-mutation workspace sanitiser enforcing limits on skills and prompts.
# ABOUTME: Uses LLM-based compaction with a soft budget — trusts the model to keep critical content.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from aec_bench.evolution.workspace import Workspace

logger = logging.getLogger(__name__)

# Soft target for skill compaction — the LLM aims for this but is trusted
# if it can't compress further without losing critical content.
COMPACTION_TARGET_CHARS = 4000
MIN_SKILL_BODY_CHARS = 20
MAX_PROMPT_CHARS = 4000
JACCARD_DEDUP_THRESHOLD = 0.6

# Threshold for switching between preserve and summarise compaction modes.
# Below this ratio (skill_size / budget), we preserve all content verbatim.
# Above it, we allow the LLM to make editorial choices.
COMPACTION_RATIO_THRESHOLD = 1.5


class CompactionMode(Enum):
    """Determines how oversized skill bodies are reduced."""

    PRESERVE = "preserve"
    SUMMARISE = "summarise"


class CompactionLLM(Protocol):
    """Protocol for LLM clients used in skill compaction."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str: ...


@dataclass(frozen=True)
class SanitiseResult:
    """Summary of changes made by the sanitiser pass."""

    skills_removed: list[str] = field(default_factory=list)
    skills_truncated: list[str] = field(default_factory=list)
    skills_compacted: list[str] = field(default_factory=list)
    prompt_truncated: bool = False


def _jaccard_similarity(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two word sets."""
    if not a and not b:
        return 1.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _determine_compaction_mode(body_len: int, budget: int) -> CompactionMode:
    """Choose compaction mode based on compression ratio needed."""
    ratio = body_len / budget
    if ratio <= COMPACTION_RATIO_THRESHOLD:
        return CompactionMode.PRESERVE
    return CompactionMode.SUMMARISE


def _build_preserve_prompt(body: str, budget: int) -> str:
    """Build the LLM prompt for preserve mode (mild overage)."""
    return (
        f"Compact the following skill text to fit within {budget} characters. "
        "Preserve ALL tables, formulas, numerical values, and worked examples verbatim. "
        "Only compress explanatory prose — remove filler words, combine sentences, "
        "use abbreviations where meaning is clear. Do NOT drop any data rows or formulas.\n\n"
        "Return ONLY the compacted skill text, nothing else.\n\n"
        f"--- SKILL TEXT ---\n{body}\n--- END ---"
    )


def _build_summarise_prompt(body: str, budget: int) -> str:
    """Build the LLM prompt for summarise mode (heavy overage)."""
    return (
        f"Summarise the following skill text to fit within {budget} characters. "
        "Prioritise content in this order:\n"
        "1. Lookup tables with exact numerical values\n"
        "2. Formulas and equations\n"
        "3. Worked examples with numbers\n"
        "4. Procedural steps\n"
        "5. Explanatory text (lowest priority — cut first)\n\n"
        "Preserve table formatting. Keep all numerical values exact. "
        "Return ONLY the compacted skill text, nothing else.\n\n"
        f"--- SKILL TEXT ---\n{body}\n--- END ---"
    )


def compact_skill(body: str, *, budget: int, llm: CompactionLLM) -> str:
    """Compact an oversized skill body using an LLM.

    Chooses preserve mode (mild overage ≤1.5x) or summarise mode (heavy overage >1.5x)
    based on the compression ratio needed. The budget is a soft target — if the LLM
    cannot compress further without losing critical content, the result is trusted as-is.
    """
    mode = _determine_compaction_mode(len(body), budget)

    if mode == CompactionMode.PRESERVE:
        prompt = _build_preserve_prompt(body, budget)
    else:
        prompt = _build_summarise_prompt(body, budget)

    compacted = llm.complete(prompt, temperature=0.0, max_tokens=budget)

    if len(compacted) > budget:
        logger.info(
            "Compaction LLM output over target (%d > %d) — trusting content is necessary",
            len(compacted),
            budget,
        )

    return compacted


def sanitise_workspace(
    ws: Workspace,
    compaction_llm: CompactionLLM | None = None,
) -> SanitiseResult:
    """Enforce limits on skills and prompts after evolver mutations.

    Applied in order:
    1. Remove skills with body < MIN_SKILL_BODY_CHARS (empty/trivial)
    2. Compact oversized skill bodies (LLM) or truncate (fallback without LLM)
    3. Deduplicate skills by Jaccard word overlap > JACCARD_DEDUP_THRESHOLD
    4. Enforce skill_budget — remove excess (later alphabetically first)
    5. Truncate system prompt if > MAX_PROMPT_CHARS
    """
    removed: list[str] = []
    truncated: list[str] = []
    compacted: list[str] = []
    prompt_truncated = False

    # Step 1: Remove trivially short skills
    for skill in ws.list_skills():
        if len(skill.body) < MIN_SKILL_BODY_CHARS:
            logger.info(
                "Sanitiser: removing trivial skill '%s' (%d chars)",
                skill.name,
                len(skill.body),
            )
            ws.delete_skill(skill.name)
            removed.append(skill.name)

    # Step 2: Compact or truncate oversized skill bodies
    for skill in ws.list_skills():
        if len(skill.body) > COMPACTION_TARGET_CHARS:
            if compaction_llm is not None:
                mode = _determine_compaction_mode(len(skill.body), COMPACTION_TARGET_CHARS)
                logger.info(
                    "Sanitiser: compacting skill '%s' from %d chars (target=%d, mode=%s)",
                    skill.name,
                    len(skill.body),
                    COMPACTION_TARGET_CHARS,
                    mode.value,
                )
                new_body = compact_skill(skill.body, budget=COMPACTION_TARGET_CHARS, llm=compaction_llm)
                compacted_skill = skill.model_copy(update={"body": new_body})
                ws.write_skill(compacted_skill)
                compacted.append(skill.name)
            else:
                logger.info(
                    "Sanitiser: truncating skill '%s' from %d to %d chars",
                    skill.name,
                    len(skill.body),
                    COMPACTION_TARGET_CHARS,
                )
                truncated_skill = skill.model_copy(update={"body": skill.body[:COMPACTION_TARGET_CHARS]})
                ws.write_skill(truncated_skill)
                truncated.append(skill.name)

    # Step 3: Deduplicate by Jaccard word overlap
    skills = ws.list_skills()
    seen_word_sets: list[tuple[str, set[str]]] = []
    for skill in skills:
        words = set(skill.body.lower().split())
        is_duplicate = False
        for kept_name, kept_words in seen_word_sets:
            if _jaccard_similarity(words, kept_words) > JACCARD_DEDUP_THRESHOLD:
                logger.info(
                    "Sanitiser: removing duplicate skill '%s' (similar to '%s')",
                    skill.name,
                    kept_name,
                )
                ws.delete_skill(skill.name)
                removed.append(skill.name)
                is_duplicate = True
                break
        if not is_duplicate:
            seen_word_sets.append((skill.name, words))

    # Step 4: Enforce skill budget — remove excess (later alphabetically removed first)
    budget = ws.manifest.skill_budget
    skills = ws.list_skills()
    if len(skills) > budget:
        sorted_skills = sorted(skills, key=lambda s: s.name)
        excess = sorted_skills[budget:]
        for skill in excess:
            logger.info(
                "Sanitiser: removing skill '%s' (over budget %d/%d)",
                skill.name,
                len(skills),
                budget,
            )
            ws.delete_skill(skill.name)
            removed.append(skill.name)

    # Step 5: Truncate system prompt if oversized
    prompt = ws.read_prompt()
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.info(
            "Sanitiser: truncating system prompt from %d to %d chars",
            len(prompt),
            MAX_PROMPT_CHARS,
        )
        ws.write_prompt(prompt[:MAX_PROMPT_CHARS])
        prompt_truncated = True

    return SanitiseResult(
        skills_removed=removed,
        skills_truncated=truncated,
        skills_compacted=compacted,
        prompt_truncated=prompt_truncated,
    )
