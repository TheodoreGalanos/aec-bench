# ABOUTME: Boundary contracts for compose-mode report templates.
# ABOUTME: Sections are ordered blocks (verbatim/fill/generated); resolvers fill slots and run LLMs.

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Protocol, runtime_checkable


class BlockTask(str, Enum):
    """Cognitive operation a fill/generated block performs.

    The semantic discriminator that complements the rendering discriminator
    (``type``). Each task routes to a dedicated handler with its own prompt
    template, output schema, and recommended cost class. See
    docs/lambda-rlm/idea-c-block-task-routing.md.
    """

    EXTRACT_FACT = "extract_fact"
    CLASSIFY_APPLICABILITY = "classify_applicability"
    SUMMARISE_CONTEXT = "summarise_context"
    RESTATE_CLAUSE = "restate_clause"
    SYNTHESISE_NARRATIVE = "synthesise_narrative"


@dataclass(frozen=True)
class BoilerplateFragment:
    """A reusable text fragment with optional named slots.

    Slots are referenced inside *text* using ``{{slot_name}}`` placeholders.
    A renderer fills them via a SlotResolver; fragments without slots are
    rendered verbatim.
    """

    text: str
    slots: tuple[str, ...] = ()


@dataclass(frozen=True)
class VerbatimBlock:
    """Render a boilerplate fragment as-is, no LLM involvement."""

    ref: str
    type: Literal["verbatim"] = "verbatim"


@dataclass(frozen=True)
class FillBlock:
    """Render a boilerplate fragment with slot values resolved from sources."""

    ref: str
    sources: tuple[str, ...] = ()
    type: Literal["fill"] = "fill"
    task: BlockTask = BlockTask.EXTRACT_FACT


@dataclass(frozen=True)
class GeneratedBlock:
    """Free-form LLM generation guided by a prompt and source references."""

    prompt: str
    sources: tuple[str, ...] = ()
    type: Literal["generated"] = "generated"
    task: BlockTask = BlockTask.SYNTHESISE_NARRATIVE


Block = VerbatimBlock | FillBlock | GeneratedBlock


def _parse_task(raw: Any, default: BlockTask) -> BlockTask:
    if raw is None:
        return default
    try:
        return BlockTask(raw)
    except ValueError as exc:
        allowed = ", ".join(sorted(t.value for t in BlockTask))
        msg = f"unknown task {raw!r}; allowed: {allowed}"
        raise ValueError(msg) from exc


def parse_block(data: Mapping[str, Any]) -> Block:
    """Construct the appropriate Block subtype from a TOML/dict payload."""
    if "type" not in data:
        msg = "block missing 'type' discriminator field"
        raise ValueError(msg)

    block_type = data["type"]
    if block_type == "verbatim":
        return VerbatimBlock(ref=data["ref"])
    if block_type == "fill":
        return FillBlock(
            ref=data["ref"],
            sources=tuple(data.get("sources", ())),
            task=_parse_task(data.get("task"), BlockTask.EXTRACT_FACT),
        )
    if block_type == "generated":
        return GeneratedBlock(
            prompt=data["prompt"],
            sources=tuple(data.get("sources", ())),
            task=_parse_task(data.get("task"), BlockTask.SYNTHESISE_NARRATIVE),
        )

    msg = f"unknown block type: {block_type!r}"
    raise ValueError(msg)


@runtime_checkable
class SlotResolver(Protocol):
    """Adapter-supplied callback that fills fragment slots from source documents.

    Implementations route through the adapter's existing trajectory-aware LLM
    call infrastructure so resolved-slot calls appear in the trial record.
    The *task* parameter names the cognitive operation (default
    ``BlockTask.EXTRACT_FACT``) so adapters can dispatch to a task-specific
    prompt + parser via their handler registry.
    """

    def resolve(
        self,
        fragment: BoilerplateFragment,
        sources: Sequence[str],
        task: BlockTask = BlockTask.EXTRACT_FACT,
    ) -> Mapping[str, str]: ...


@runtime_checkable
class BlockGenerator(Protocol):
    """Adapter-supplied callback for free-form generation blocks.

    The *task* parameter names the cognitive operation (default
    ``BlockTask.SYNTHESISE_NARRATIVE``) so adapters can dispatch to a
    task-specific prompt + parser via their handler registry.
    """

    def generate(
        self,
        prompt: str,
        sources: Sequence[str],
        task: BlockTask = BlockTask.SYNTHESISE_NARRATIVE,
    ) -> str: ...


@dataclass(frozen=True)
class BlockTrace:
    """Per-block provenance record produced by the compose renderer.

    Offsets refer to the assembled section text — the invariant
    ``section_text[start_offset:end_offset] == text`` must hold, which lets
    downstream tools (report-gen, reviewer UIs) highlight exact spans without
    re-parsing the output. ``ref`` is populated for verbatim/fill blocks,
    ``prompt`` for generated blocks; ``resolved_slots`` is the slot-name →
    filled-value map for fill blocks (empty for verbatim and generated).
    """

    block_index: int
    block_type: Literal["verbatim", "fill", "generated"]
    text: str
    start_offset: int
    end_offset: int
    ref: str | None = None
    prompt: str | None = None
    sources: tuple[str, ...] = ()
    resolved_slots: Mapping[str, str] = field(default_factory=dict)
    provenance: tuple[str, ...] = ()
    slot_provenance: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    declared_provenance: tuple[str, ...] = ()
    fetched_provenance: tuple[str, ...] = ()
    task: BlockTask | None = None


CompositionTrace = tuple[BlockTrace, ...]


__all__ = [
    "Block",
    "BlockGenerator",
    "BlockTask",
    "BlockTrace",
    "BoilerplateFragment",
    "CompositionTrace",
    "FillBlock",
    "GeneratedBlock",
    "SlotResolver",
    "VerbatimBlock",
    "parse_block",
]
