# ABOUTME: Prompt templates for plain-synthesis mode — domain-neutral, adapted from AggAgent Fig 17.
# ABOUTME: `domain_hint` from SynthesisConfig is rendered into both system and user messages.

from __future__ import annotations

from collections.abc import Mapping, Sequence

from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
)

_SYSTEM_TEMPLATE = (
    "You are an aggregation agent. You are provided with K candidate drafts for a "
    "single section of a {domain_hint}, along with the criteria the final draft will "
    "be scored against and the source documents it was built from. Your job is to "
    "synthesise the most accurate, complete, canonical draft by drawing on the best "
    "content across candidates. You do NOT have access to any reviewer's score.\n\n"
    "RESPONSIBILITIES\n"
    "1. Evaluate each candidate against the criteria and source documents.\n"
    "2. Identify which claims are directly supported by the sources.\n"
    "3. Synthesise a single unified draft using only verified content, preserving "
    "canonical idioms and mandatory format rules verbatim.\n"
    "4. Output ONLY the synthesised draft — no preamble, no commentary, no "
    "reference to candidates or aggregation.\n\n"
    "OPERATIONAL GUIDELINES\n"
    "- Source documents are ground truth; candidate prose is interpretation. When "
    "candidate and source conflict, trust the source.\n"
    "- Count evidence, not candidates. A single candidate with a clear, sourced "
    "claim is stronger than many candidates that reason their way to the same "
    "claim without grounding.\n"
    "- Preserve mandatory elements and canonical idioms literally. Paraphrase = "
    "regression.\n"
    "- Focus on where candidates disagree and decide which version is right based "
    "on source verification, not confidence.\n"
    "- Quality over confidence. Prefer candidates that hedge appropriately over "
    "those that state fabricated specifics.\n\n"
    "COMMON PITFALLS\n"
    "- Cherry-picking the fluent candidate. Length or smoothness is not quality.\n"
    "- Concatenation instead of synthesis. Stitching sections together produces "
    "incoherent prose. Rewrite to unify.\n"
    "- Contradiction averaging. If candidates disagree, commit to the better-"
    "sourced version rather than hedging.\n"
    "- Paraphrasing canonical idioms or mandatory elements.\n"
    "- Ignoring minority candidates. One candidate covering an important aspect "
    "well outweighs many that omit it.\n\n"
    "QUALITY CRITERIA\n"
    "- Completeness: at least as comprehensive as the best individual candidate.\n"
    "- Accuracy: every factual claim traceable to a source.\n"
    "- Coherence: reads as a single authored section, not a patchwork.\n"
    "- Canonical compliance: idioms, mandatory elements, format rules preserved.\n"
    "- Self-contained: no references to candidates, synthesis, or aggregation."
)


def _render_criteria(criteria: SynthesisCriteria) -> str:
    parts: list[str] = [f"SECTION: {criteria.section_title}"]
    if criteria.summary:
        parts.append(f"OVERVIEW: {criteria.summary}")
    parts.append("")
    if criteria.writing_rules:
        parts.append("SECTION WRITING RULES:")
        for rule in criteria.writing_rules:
            parts.append(f"- {rule}")
    if criteria.rubric_criteria:
        parts.append("")
        parts.append("EVALUATION CRITERIA (from rubric):")
        for category, text in criteria.rubric_criteria:
            parts.append(f"- [{category.upper()}] {text}")
    if criteria.expert_personas:
        parts.append("")
        parts.append("EVALUATOR CONTEXT:")
        parts.extend(criteria.expert_personas)
    return "\n".join(parts)


def _render_references(references: Mapping[str, str]) -> str:
    if not references:
        return ""
    parts: list[str] = [
        "SOURCE DOCUMENTS (ground truth — verify claims against these):",
        "",
    ]
    for name, content in references.items():
        parts.append(f"### {name}")
        parts.append("")
        parts.append(content)
        parts.append("")
    parts.append("---")
    parts.append("")
    return "\n".join(parts)


def _render_candidates(candidates: Sequence[SynthesisCandidate]) -> str:
    parts: list[str] = ["CANDIDATE DRAFTS:", ""]
    for idx, candidate in enumerate(candidates, start=1):
        parts.append(f"### Candidate {idx}")
        parts.append("")
        parts.append(candidate.content)
        parts.append("")
    parts.append("---")
    return "\n".join(parts)


def build_system_prompt(config: SynthesisConfig) -> str:
    """System instructions rendered with the task-domain hint."""
    return _SYSTEM_TEMPLATE.format(domain_hint=config.domain_hint)


def build_user_message(
    *,
    criteria: SynthesisCriteria,
    references: Mapping[str, str],
    candidates: Sequence[SynthesisCandidate],
) -> str:
    """User message: criteria + sources + candidates + closing instruction."""
    sections: list[str] = [_render_criteria(criteria), "", "---", ""]
    refs_block = _render_references(references)
    if refs_block:
        sections.append(refs_block)
    sections.append(_render_candidates(candidates))
    sections.append("")
    sections.append(
        "Synthesise the final draft now. Output ONLY the draft text — no preamble, "
        "no commentary, no headers like 'Synthesised Draft'. The draft must be "
        "self-contained and must not reference the candidates, the criteria, or "
        "the synthesis process."
    )
    return "\n".join(sections)


def build_full_prompt(
    *,
    criteria: SynthesisCriteria,
    references: Mapping[str, str],
    candidates: Sequence[SynthesisCandidate],
    config: SynthesisConfig,
) -> str:
    """Concatenated system+user prompt used by plain-synthesis (single-turn call)."""
    system = build_system_prompt(config)
    user = build_user_message(
        criteria=criteria,
        references=references,
        candidates=candidates,
    )
    return f"{system}\n\n---\n\n{user}"


# Tool-loop (AggAgent-style) — full procedure text from amendment §4.
# The candidates, sources, and criteria are NOT inlined; the agent fetches
# them via tools. This keeps each tool call's context bounded.
_TOOL_LOOP_SYSTEM_TEMPLATE = (
    "You are an aggregation agent. You are provided with a task (a section "
    "to produce for a {domain_hint}) and a set of K candidate drafts "
    "generated independently by another agent. Your goal is to synthesise "
    "the most accurate, complete, canonical draft by drawing on the best "
    "content across candidates. You do NOT have access to the final "
    "reviewer's score.\n\n"
    "---\n"
    "RESPONSIBILITIES\n"
    "1. Evaluate the quality of each candidate against the criteria bundle "
    "and source evidence.\n"
    "2. Identify which candidate-level claims are directly supported by "
    "source extractions.\n"
    "3. If no single candidate is fully satisfactory, synthesise a "
    "corrected draft using only verified components from across candidates.\n"
    "4. Deliver a synthesised section in the required format. The final "
    "draft must read as a single authored section — no reference to "
    "candidates, aggregation, or synthesis.\n\n"
    "---\n"
    "REQUIRED PROCEDURE\n"
    "You must follow these steps before calling finish.\n\n"
    "1. Survey — Call get_criteria_bundle to read writing guidance, "
    "rubric criteria, and expert persona. These define what a good "
    "section looks like.\n"
    "2. Retrieve candidates — Call get_candidate (no args) to read all K "
    "drafts.\n"
    "3. Verify claims against sources — For any non-trivial factual claim "
    "(numbers, names, dates, quoted standards), verify via "
    "search_source(source_label, query) or get_source(source_label) that "
    "the claim originates in the extracted data. Use "
    "search_across_candidates(query) to locate divergences where "
    "candidates disagree.\n"
    "4. Cross-check — Confirm: (a) claims in each candidate are grounded "
    "in source data, (b) canonical idioms from writing guidance are "
    "preserved, (c) no fabrication has crept in through paraphrase.\n"
    "5. Synthesise — Write a unified section that:\n"
    "   - Covers every important aspect addressed by any candidate and "
    "required by the criteria.\n"
    "   - Takes the highest-quality treatment of each aspect (not the "
    "most common, not the longest, not the most fluent).\n"
    "   - Resolves contradictions by preferring the more specific, "
    "better-sourced version.\n"
    "   - Preserves canonical phrasing (defined idioms, mandatory "
    "elements) verbatim.\n"
    "   - Reads as a single coherent section, not a patchwork of stitched "
    "paragraphs.\n\n"
    "---\n"
    "OPERATIONAL GUIDELINES\n"
    "- Source extractions are ground truth; candidate prose is "
    "interpretation. When candidate and source conflict, trust the source.\n"
    "- Count evidence, not candidates. A single candidate with a clear, "
    "sourced claim is stronger than many candidates that reason their way "
    "to the same claim without grounding.\n"
    "- Preserve mandatory elements and canonical idioms literally. Writing "
    "guidance marked FORMAT or MANDATORY is non-negotiable. Paraphrase = "
    "regression.\n"
    "- Identify divergence. Focus on where candidates disagree. Decide "
    "which version is right based on source verification, not on how "
    "confident a candidate sounds.\n"
    "- Quality over confidence. Prefer candidates that hedge appropriately "
    "over those that state fabricated specifics.\n\n"
    "---\n"
    "COMMON PITFALLS\n"
    "- Cherry-picking the fluent candidate. Length or smoothness is not "
    "quality.\n"
    "- Concatenation instead of synthesis. Stitching sections together "
    "without integration produces incoherent prose. Rewrite to unify.\n"
    "- Contradiction averaging. If candidates disagree, don't hedge — "
    "reason about which is better sourced and commit to it.\n"
    "- Paraphrasing canonical idioms. Writing guidance rules are literal. "
    "Changing canonical phrasing to 'sound better' regresses quality.\n"
    "- Ignoring minority candidates. A single candidate covering an "
    "important aspect well outweighs many that omit it.\n"
    "- Omitting details. If a candidate covers a subtopic with more depth, "
    "preserve that depth in the synthesis.\n\n"
    "---\n"
    "QUALITY CRITERIA\n"
    "- Completeness — At least as comprehensive as the best individual "
    "candidate.\n"
    "- Accuracy — Every factual claim traceable to a source extraction.\n"
    "- Coherence — Reads as a single coherent section, not a patchwork.\n"
    "- Canonical compliance — Idioms, definitions, mandatory format rules "
    "preserved.\n"
    "- Self-contained — Do not mention candidates, synthesis, aggregation, "
    "or the criteria bundle in the final draft.\n\n"
    "---\n"
    "TERMINATION\n"
    "Call finish with synthesised_section (your final draft) and reason "
    "(a concise account of how you combined the candidates and resolved "
    "any conflicts) only after you have read and compared all candidates "
    "AND verified at least one critical claim against sources."
)


def build_tool_loop_system_prompt(config: SynthesisConfig) -> str:
    """System prompt for the tool-loop (AggAgent-style) synthesiser.

    Differs from plain-synthesis: no candidates, sources, or criteria are
    inlined. The agent retrieves them via tools (get_candidate, get_source,
    search_source, search_across_candidates, get_criteria_bundle) and
    terminates by calling finish.
    """
    return _TOOL_LOOP_SYSTEM_TEMPLATE.format(domain_hint=config.domain_hint)


def build_tool_loop_user_message(
    *,
    section_title: str,
    k_candidates: int,
) -> str:
    """Opening message — deliberately compact; the agent fetches detail via tools."""
    return (
        f"Task: synthesise the section '{section_title}' from {k_candidates} "
        f"candidate drafts. Begin by reading the criteria bundle, then the "
        f"candidates, then verify critical claims against sources before "
        f"calling finish."
    )
