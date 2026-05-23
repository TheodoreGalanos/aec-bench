# ABOUTME: Locator-based patch applier — finds the target section, validates unique-match, rewrites in place.
# ABOUTME: Any ambiguous or missing locator raises rather than guess; caller escalates to HITL.

from __future__ import annotations

import re
from dataclasses import dataclass

from aec_bench.contracts.remediation import Patch


class SectionNotFound(Exception):
    """The patch's section_id could not be located in the document."""


class AmbiguousLocator(Exception):
    """The locator phrase matched 0 times or >1 times in the target section."""


_HEADING_RE = re.compile(r"^#\s+(?:\d+(?:\.\d+)*\.?\s*)?(.+?)\s*$", re.MULTILINE)


def _normalise_section_id(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.lower()).strip("_")


def split_sections(text: str) -> dict[str, tuple[int, int]]:
    """Split output.md into top-level sections, return section_id -> (start, end) byte offsets."""
    headings = [(m.start(), m.group(1)) for m in _HEADING_RE.finditer(text)]
    if not headings:
        return {"": (0, len(text))}
    result: dict[str, tuple[int, int]] = {}
    for i, (pos, title) in enumerate(headings):
        end = headings[i + 1][0] if i + 1 < len(headings) else len(text)
        sid = _normalise_section_id(title)
        result[sid] = (pos, end)
    return result


def heading_derived_id(text: str) -> str | None:
    """Return the same id `split_sections` would assign to the first heading in `text`.

    Returns None if no top-level (`# `) heading is found. Used to translate
    canonical section IDs (from sections.json) into their heading-derived
    equivalents — the id space the loop and applier operate in.
    """
    m = _HEADING_RE.search(text)
    if not m:
        return None
    return _normalise_section_id(m.group(1))


def _resolve_section(sections: dict[str, tuple[int, int]], target: str) -> str:
    """Resolve a section_id against the discovered section keys.

    Accepts exact match or word-boundary partial match — target must be a whole
    token within the key. Prevents "scope" from matching "telescope_specs" while
    still allowing "scope" → "scope_of_works" and "works" → "scope_of_works".
    Raises SectionNotFound when there is no unique match.
    """
    if target in sections:
        return target
    candidates = [
        k
        for k in sections
        if k == target or k.startswith(target + "_") or k.endswith("_" + target) or ("_" + target + "_") in k
    ]
    if len(candidates) == 0:
        raise SectionNotFound(f"section_id {target!r} has no candidate match in {list(sections)}")
    if len(candidates) > 1:
        raise SectionNotFound(f"section_id {target!r} is ambiguous — matched {candidates}")
    return candidates[0]


def apply_patch(text: str, patch: Patch) -> str:
    """Apply a single patch. Raises SectionNotFound or AmbiguousLocator on failure."""
    sections = split_sections(text)
    target = _resolve_section(sections, patch.section_id)
    start, end = sections[target]
    body = text[start:end]
    occurrences = body.count(patch.locator_phrase)
    if occurrences != patch.occurrence:
        raise AmbiguousLocator(
            f"locator {patch.locator_phrase!r} found {occurrences} time(s) "
            f"in section {target!r}, expected {patch.occurrence}"
        )
    patched_body = body.replace(patch.locator_phrase, patch.replacement, patch.occurrence)
    return text[:start] + patched_body + text[end:]


@dataclass(frozen=True)
class AnnotatedPatch:
    """A patch where span_to_replace was selected by the extractor, not invented by the LLM.

    Unlike Patch, the span here is guaranteed to have been present in the section
    at selection time (extracted from verifier evidence and validated as unique).
    The LLM only supplied the replacement text.
    """

    section_id: str
    span_to_replace: str
    replacement: str


def apply_annotated_patch(text: str, patch: AnnotatedPatch) -> str:
    """Apply an annotated patch. Same validation as apply_patch but uses span_to_replace.

    Raises SectionNotFound or AmbiguousLocator on failure — caller escalates to HITL.
    """
    sections = split_sections(text)
    target = _resolve_section(sections, patch.section_id)
    start, end = sections[target]
    body = text[start:end]
    occurrences = body.count(patch.span_to_replace)
    if occurrences != 1:
        raise AmbiguousLocator(
            f"span {patch.span_to_replace!r} found {occurrences} time(s) in section {target!r}, expected 1"
        )
    patched_body = body.replace(patch.span_to_replace, patch.replacement, 1)
    return text[:start] + patched_body + text[end:]


@dataclass(frozen=True)
class RejectedPatch:
    patch: Patch
    reason: str


@dataclass(frozen=True)
class ApplyResult:
    patched_text: str
    applied_count: int
    rejected: tuple[RejectedPatch, ...]


def apply_patches(text: str, patches: list[Patch]) -> ApplyResult:
    """Apply patches in order; successes mutate the text, failures are reported."""
    current = text
    applied = 0
    rejected: list[RejectedPatch] = []
    for patch in patches:
        try:
            current = apply_patch(current, patch)
            applied += 1
        except (SectionNotFound, AmbiguousLocator) as exc:
            rejected.append(RejectedPatch(patch=patch, reason=str(exc)))
    return ApplyResult(
        patched_text=current,
        applied_count=applied,
        rejected=tuple(rejected),
    )
