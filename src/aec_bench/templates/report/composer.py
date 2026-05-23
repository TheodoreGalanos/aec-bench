# ABOUTME: Renders a compose-mode section by walking its block list.
# ABOUTME: Pure orchestrator — fragment lookup, slot substitution, delegation, assembly.

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from aec_bench.contracts.report_template import (
    Block,
    BlockGenerator,
    BlockTrace,
    BoilerplateFragment,
    CompositionTrace,
    FillBlock,
    GeneratedBlock,
    SlotResolver,
    VerbatimBlock,
)

_SLOT_RE = re.compile(r"\{\{(\w+)\}\}")
_BLOCK_SEPARATOR = "\n\n"


class FragmentNotFoundError(LookupError):
    """A block referenced a fragment that does not exist or is not a string."""


class UnresolvedSlotError(ValueError):
    """The SlotResolver did not return a value for a slot present in the fragment."""


def lookup_fragment(fragments: Mapping[str, Any], ref: str) -> str:
    """Resolve a dotted ref to a string fragment.

    A leaf string returns directly. A sub-table (Mapping) returns all string
    descendants joined by paragraph breaks in declaration order, which lets
    authors group several related fragments under one ref and prepend a
    ``heading`` key to control the assembled markdown.
    """
    parts = ref.split(".")
    node: Any = fragments
    for part in parts:
        if not isinstance(node, Mapping) or part not in node:
            msg = f"fragment not found at path {ref!r}"
            raise FragmentNotFoundError(msg)
        node = node[part]

    if isinstance(node, str):
        return node

    if isinstance(node, Mapping):
        joined = _BLOCK_SEPARATOR.join(_collect_strings(node))
        if not joined:
            msg = f"sub-table at path {ref!r} contains no string fragments to render"
            raise FragmentNotFoundError(msg)
        return joined

    msg = f"fragment at path {ref!r} is neither a string nor a sub-table (got {type(node).__name__})"
    raise FragmentNotFoundError(msg)


def _collect_strings(node: Mapping[str, Any]) -> list[str]:
    """Walk a sub-table in declaration order, gathering every string descendant."""
    out: list[str] = []
    for value in node.values():
        if isinstance(value, str):
            out.append(value)
        elif isinstance(value, Mapping):
            out.extend(_collect_strings(value))
        # Non-string, non-Mapping values (ints, lists, bools) are skipped silently
        # so that future TOML schema additions don't crash the renderer.
    return out


def detect_slots(text: str) -> tuple[str, ...]:
    """Return slot names found in *text* in first-occurrence order, deduplicated."""
    seen: dict[str, None] = {}
    for match in _SLOT_RE.finditer(text):
        seen.setdefault(match.group(1), None)
    return tuple(seen.keys())


def _render_verbatim(block: VerbatimBlock, fragments: Mapping[str, Any]) -> str:
    return lookup_fragment(fragments, block.ref)


def _render_fill(
    block: FillBlock,
    fragments: Mapping[str, Any],
    slot_resolver: SlotResolver,
) -> tuple[str, dict[str, str]]:
    text = lookup_fragment(fragments, block.ref)
    slots = detect_slots(text)

    if not slots:
        return text, {}

    fragment = BoilerplateFragment(text=text, slots=slots)
    values = slot_resolver.resolve(fragment, block.sources, block.task)

    missing = [slot for slot in slots if slot not in values]
    if missing:
        msg = f"resolver did not return values for slots: {', '.join(missing)}"
        raise UnresolvedSlotError(msg)

    resolved = {slot: values[slot] for slot in slots}
    rendered = _SLOT_RE.sub(lambda m: resolved[m.group(1)], text)
    return rendered, resolved


def _render_generated(block: GeneratedBlock, block_generator: BlockGenerator) -> str:
    return block_generator.generate(block.prompt, block.sources, block.task)


def render_section(
    blocks: Sequence[Block],
    fragments: Mapping[str, Any],
    slot_resolver: SlotResolver,
    block_generator: BlockGenerator,
) -> tuple[str, CompositionTrace]:
    """Render a compose-mode section by walking *blocks* in order.

    Returns ``(text, trace)`` where *trace* is a tuple of :class:`BlockTrace`
    entries — one per block — with character offsets pointing back into *text*.
    The invariant ``text[entry.start_offset:entry.end_offset] == entry.text``
    holds for every entry so downstream consumers (report-gen, reviewer UIs)
    can highlight exact spans without re-parsing.
    """
    rendered: list[str] = []
    traces: list[BlockTrace] = []
    sep_len = len(_BLOCK_SEPARATOR)

    # Track the running offset into the eventual joined text. Each block's
    # start offset is the cumulative length of previously rendered blocks plus
    # separators between them.
    cursor = 0
    for index, block in enumerate(blocks):
        try:
            if isinstance(block, VerbatimBlock):
                block_text = _render_verbatim(block, fragments)
                trace = BlockTrace(
                    block_index=index,
                    block_type="verbatim",
                    text=block_text,
                    start_offset=cursor,
                    end_offset=cursor + len(block_text),
                    ref=block.ref,
                )
            elif isinstance(block, FillBlock):
                block_text, resolved = _render_fill(block, fragments, slot_resolver)
                declared = tuple(block.sources)
                slot_prov = getattr(slot_resolver, "last_slot_provenance", {})
                trace = BlockTrace(
                    block_index=index,
                    block_type="fill",
                    text=block_text,
                    start_offset=cursor,
                    end_offset=cursor + len(block_text),
                    ref=block.ref,
                    sources=declared,
                    resolved_slots=resolved,
                    provenance=declared,
                    declared_provenance=declared,
                    slot_provenance=dict(slot_prov),  # snapshot; don't alias resolver's live dict
                    task=block.task,
                )
            elif isinstance(block, GeneratedBlock):
                block_text = _render_generated(block, block_generator)
                declared = tuple(block.sources)
                fetched = tuple(getattr(block_generator, "last_fetched_provenance", ()))
                full_prov = tuple(getattr(block_generator, "last_provenance", declared))
                trace = BlockTrace(
                    block_index=index,
                    block_type="generated",
                    text=block_text,
                    start_offset=cursor,
                    end_offset=cursor + len(block_text),
                    prompt=block.prompt,
                    sources=declared,
                    provenance=full_prov,
                    declared_provenance=declared,
                    fetched_provenance=fetched,
                    task=block.task,
                )
            else:
                msg = f"block {index}: unsupported block type {type(block).__name__}"
                raise TypeError(msg)
        except FragmentNotFoundError as exc:
            msg = f"block {index}: {exc}"
            raise FragmentNotFoundError(msg) from exc

        rendered.append(block_text)
        traces.append(trace)
        cursor += len(block_text) + sep_len  # next block starts after this block + separator

    return _BLOCK_SEPARATOR.join(rendered), tuple(traces)


__all__ = [
    "FragmentNotFoundError",
    "UnresolvedSlotError",
    "detect_slots",
    "lookup_fragment",
    "render_section",
]
