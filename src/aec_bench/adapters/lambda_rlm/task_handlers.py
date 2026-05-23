# ABOUTME: Lambda-rlm block-task handler registry — semantic dispatch for compose-mode blocks.
# ABOUTME: Each handler owns its prompt builder + parser; resolver/generator delegate to handlers.

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from aec_bench.contracts.report_template import BlockTask, BoilerplateFragment

CostClass = Literal["cheap", "medium", "strong"]


@dataclass(frozen=True)
class SlotPromptContext:
    """Inputs supplied to a slot-task prompt builder.

    `remaining_slots` is the subset of `fragment.slots` that still need
    LLM resolution (scratchpad hits have been removed upstream).
    `sources_block` is the already-formatted "### Source: ..." text block
    so handlers don't need to know about sandbox vs source-resolver paths.
    """

    fragment: BoilerplateFragment
    remaining_slots: Sequence[str]
    sources_block: str


@dataclass(frozen=True)
class ProsePromptContext:
    """Inputs supplied to a prose-task prompt builder.

    `user_prompt` is the per-block prompt declared on `GeneratedBlock.prompt`.
    `known_facts` and `scope_evolution` come from the planning-phase scratchpad
    (None when no planning phase ran or the scratchpad is empty).
    """

    user_prompt: str
    sources_block: str
    known_facts: str | None
    scope_evolution: str | None


@dataclass(frozen=True)
class SlotTaskHandler:
    """Registered handler for a fill-block (slot-resolution) task."""

    task: BlockTask
    cost_class: CostClass
    build_prompt: Callable[[SlotPromptContext], str]
    parse: Callable[[str], Mapping[str, str]]
    max_tokens: int | None = None
    temperature: float | None = None


def _identity(text: str) -> str:
    return text


@dataclass(frozen=True)
class ProseTaskHandler:
    """Registered handler for a generated-block (prose) task."""

    task: BlockTask
    cost_class: CostClass
    build_prompt: Callable[[ProsePromptContext], str]
    parse: Callable[[str], str] = field(default=_identity)
    max_tokens: int | None = None
    temperature: float | None = None


# ─── extract_fact (today's slot resolution) ────────────────────────────────

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json_object(text: str) -> dict[str, str]:
    """Parse a JSON object from *text*, tolerating leading/trailing prose."""
    text = text.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = _JSON_OBJECT_RE.search(text)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def _build_extract_fact_prompt(ctx: SlotPromptContext) -> str:
    slot_list = ", ".join(ctx.remaining_slots)
    return (
        f"Boilerplate fragment:\n{ctx.fragment.text}\n\n"
        f"Slots to fill: {slot_list}\n\n"
        f"Source documents:\n{ctx.sources_block}\n\n"
        f"Return ONLY a JSON object mapping each slot to its value."
    )


# ─── synthesise_narrative (today's free-form generation) ───────────────────

_SCOPE_EVOLUTION_PREAMBLE = (
    "Scope summary (from planning phase — descriptive record "
    "of how the client's ask evolved; use as orientation when "
    "the raw source contains a negotiation). The primary "
    "source remains authoritative: check the source documents "
    "for specific scope items, personnel, dates, and phrasing "
    "before relying on this summary:\n"
)


def _build_synthesise_narrative_prompt(ctx: ProsePromptContext) -> str:
    parts = [ctx.user_prompt]
    if ctx.scope_evolution:
        parts.append(_SCOPE_EVOLUTION_PREAMBLE + ctx.scope_evolution)
    if ctx.known_facts:
        parts.append(f"Known facts (from planning phase):\n{ctx.known_facts}")
    parts.append(f"Source documents:\n{ctx.sources_block}")
    parts.append("Write the requested text directly, no preamble.")
    return "\n\n".join(parts)


# ─── summarise_context (faithful enumeration over sources) ─────────────────

_SUMMARISE_PREAMBLE = (
    "Your task is to summarise — extract a faithful enumeration of items "
    "from the source material below. Do not add facts that are not "
    "explicitly evidenced in the sources. The instruction that follows "
    "specifies what to extract and how to format it."
)

_SUMMARISE_CLOSING = (
    "Write a faithful summary. Adhere to any format constraints in the "
    "instruction above. Every item must be explicitly evidenced in the "
    "source documents — do not infer, do not pad, do not invent."
)


def _build_summarise_context_prompt(ctx: ProsePromptContext) -> str:
    parts = [_SUMMARISE_PREAMBLE, ctx.user_prompt]
    if ctx.scope_evolution:
        parts.append(_SCOPE_EVOLUTION_PREAMBLE + ctx.scope_evolution)
    if ctx.known_facts:
        parts.append(f"Known facts (from planning phase):\n{ctx.known_facts}")
    parts.append(f"Source documents:\n{ctx.sources_block}")
    parts.append(_SUMMARISE_CLOSING)
    return "\n\n".join(parts)


# ─── Registries ────────────────────────────────────────────────────────────


SLOT_TASK_HANDLERS: dict[BlockTask, SlotTaskHandler] = {
    BlockTask.EXTRACT_FACT: SlotTaskHandler(
        task=BlockTask.EXTRACT_FACT,
        cost_class="cheap",
        build_prompt=_build_extract_fact_prompt,
        parse=_extract_json_object,
    ),
}


PROSE_TASK_HANDLERS: dict[BlockTask, ProseTaskHandler] = {
    BlockTask.SYNTHESISE_NARRATIVE: ProseTaskHandler(
        task=BlockTask.SYNTHESISE_NARRATIVE,
        cost_class="strong",
        build_prompt=_build_synthesise_narrative_prompt,
    ),
    BlockTask.SUMMARISE_CONTEXT: ProseTaskHandler(
        task=BlockTask.SUMMARISE_CONTEXT,
        cost_class="medium",
        build_prompt=_build_summarise_context_prompt,
    ),
}


def get_slot_handler(task: BlockTask) -> SlotTaskHandler:
    try:
        return SLOT_TASK_HANDLERS[task]
    except KeyError as exc:
        registered = ", ".join(sorted(t.value for t in SLOT_TASK_HANDLERS))
        msg = f"no slot handler registered for task={task.value!r}; have: {registered}"
        raise KeyError(msg) from exc


def get_prose_handler(task: BlockTask) -> ProseTaskHandler:
    try:
        return PROSE_TASK_HANDLERS[task]
    except KeyError as exc:
        registered = ", ".join(sorted(t.value for t in PROSE_TASK_HANDLERS))
        msg = f"no prose handler registered for task={task.value!r}; have: {registered}"
        raise KeyError(msg) from exc


__all__ = [
    "PROSE_TASK_HANDLERS",
    "SLOT_TASK_HANDLERS",
    "CostClass",
    "ProsePromptContext",
    "ProseTaskHandler",
    "SlotPromptContext",
    "SlotTaskHandler",
    "get_prose_handler",
    "get_slot_handler",
]
