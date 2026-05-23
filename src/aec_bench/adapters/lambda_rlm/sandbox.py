# ABOUTME: DocumentSandbox + four anchor extractors for sandbox-grounded extraction.
# ABOUTME: Anchors address slices via #slug, @id, :p<N>, or bare label (whole doc).

from __future__ import annotations

import csv
import io
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Literal

_ANCHOR_RE = re.compile(r"^(?P<label>[\w./-]+)(?P<anchor>([#@]|:p|:bytes:).+)?$")


@dataclass(frozen=True)
class Anchor:
    """Deterministic address into a source document."""

    canonical: str
    """The anchor sigil + identifier, e.g., '#scope', '@msg3', ':p7'."""

    scheme: Literal["heading", "instance", "paragraph", "byte_range", "whole"]
    """Which extractor produced this anchor."""

    position_index: int
    """0-based occurrence order within the document, used as a debug alias."""


@dataclass(frozen=True)
class Slice:
    """A bounded view into a source document."""

    label: str
    anchor: str
    text: str
    start: int
    end: int


def parse_anchor_ref(ref: str) -> tuple[str, str | None]:
    """Parse a TOML anchored reference into (label, anchor_or_None)."""
    match = _ANCHOR_RE.match(ref)
    if match is None:
        msg = f"invalid anchor reference: {ref!r}"
        raise ValueError(msg)
    return match["label"], match["anchor"]


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _slugify(text: str) -> str:
    """Lowercase, non-alphanumeric → hyphen, runs collapsed, trim hyphens."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def extract_markdown_headings(text: str) -> tuple[Anchor, ...]:
    """Yield one Anchor per heading; collisions get -2, -3, ... suffixes."""
    seen: dict[str, int] = {}
    anchors: list[Anchor] = []
    for idx, match in enumerate(_HEADING_RE.finditer(text)):
        slug = _slugify(match.group(2))
        seen[slug] = seen.get(slug, 0) + 1
        canonical = f"#{slug}" if seen[slug] == 1 else f"#{slug}-{seen[slug]}"
        anchors.append(Anchor(canonical=canonical, scheme="heading", position_index=idx))
    return tuple(anchors)


_MESSAGE_RE = re.compile(r"^##\s+Message\s+(\d+)\b", re.MULTILINE)


def extract_email_thread(text: str) -> tuple[Anchor, ...]:
    """One anchor per `## Message N` heading; canonical IDs are @msg<N>."""
    anchors: list[Anchor] = []
    for idx, match in enumerate(_MESSAGE_RE.finditer(text)):
        canonical = f"@msg{match.group(1)}"
        anchors.append(Anchor(canonical=canonical, scheme="instance", position_index=idx))
    return tuple(anchors)


def extract_paragraph_index(text: str) -> tuple[Anchor, ...]:
    """One anchor per non-empty paragraph (blank-line separated)."""
    paragraphs = [p for p in text.split("\n\n") if p.strip()]
    return tuple(Anchor(canonical=f":p{i + 1}", scheme="paragraph", position_index=i) for i in range(len(paragraphs)))


def extract_table_rows(text: str, *, key_column: str | None) -> tuple[Anchor, ...]:
    """One anchor per data row. If key_column given, anchor is @<key>=<value>."""
    reader = csv.DictReader(io.StringIO(text))
    anchors: list[Anchor] = []
    for idx, row in enumerate(reader):
        if key_column and key_column in row:
            canonical = f"@{key_column}={row[key_column]}"
        else:
            canonical = f"@row{idx + 1}"
        anchors.append(Anchor(canonical=canonical, scheme="instance", position_index=idx))
    return tuple(anchors)


# ---------------------------------------------------------------------------
# Extractor registry
# ---------------------------------------------------------------------------

_EXTRACTOR_BY_EXTENSION: dict[str, str] = {
    ".md": "markdown_headings",
    ".eml": "email_thread",
    ".txt": "paragraph_index",
    ".csv": "table_rows",
    ".tsv": "table_rows",
}

_PRIMARY_EXTRACTORS: dict[str, object] = {
    "markdown_headings": lambda text: extract_markdown_headings(text),
    "email_thread": lambda text: extract_email_thread(text),
    "paragraph_index": lambda text: extract_paragraph_index(text),
    # table_rows: key_column=None yields @row<N> anchors; precise per-row slicing
    # is v1 only — table rows return the whole doc text for now (see _offsets_for).
    "table_rows": lambda text: extract_table_rows(text, key_column=None),
}


def _select_extractor(label: str) -> str:
    """Return extractor name for a filename based on its extension."""
    suffix = PurePosixPath(label).suffix.lower()
    return _EXTRACTOR_BY_EXTENSION.get(suffix, "paragraph_index")


# ---------------------------------------------------------------------------
# Internal document holder
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _DocumentEntry:
    text: str
    anchors_by_canonical: Mapping[str, tuple[Anchor, int, int]]
    """Map canonical → (anchor, start_offset, end_offset)."""


# ---------------------------------------------------------------------------
# DocumentSandbox
# ---------------------------------------------------------------------------


class DocumentSandbox:
    """Typed holder of source documents addressable by anchors."""

    def __init__(self, entries: Mapping[str, _DocumentEntry]) -> None:
        self._entries: dict[str, _DocumentEntry] = dict(entries)

    @classmethod
    def from_documents(
        cls,
        documents: Mapping[str, str],
        *,
        extractor_overrides: Mapping[str, str],
    ) -> DocumentSandbox:
        """Build a sandbox from a label→text mapping."""
        entries: dict[str, _DocumentEntry] = {}
        for label, text in documents.items():
            extractor_name = extractor_overrides.get(label) or _select_extractor(label)
            primary_fn = _PRIMARY_EXTRACTORS[extractor_name]
            primary: tuple[Anchor, ...] = primary_fn(text)  # type: ignore[operator]
            secondary = extract_paragraph_index(text)
            offsets = _compute_offsets(text, primary, secondary)
            entries[label] = _DocumentEntry(text=text, anchors_by_canonical=offsets)
        return cls(entries)

    def labels(self) -> tuple[str, ...]:
        """Return all registered document labels in insertion order."""
        return tuple(self._entries.keys())

    def anchors(self, label: str) -> tuple[Anchor, ...]:
        """Return all anchors for a document (primary + universal secondary)."""
        entry = self._entries[label]
        return tuple(a for a, _, _ in entry.anchors_by_canonical.values())

    def slice(self, label: str, anchor: str | None) -> Slice:
        """Return a Slice for the given anchor, or the whole doc if anchor is None."""
        entry = self._entries[label]
        if anchor is None:
            return Slice(
                label=label,
                anchor="",
                text=entry.text,
                start=0,
                end=len(entry.text),
            )
        if anchor not in entry.anchors_by_canonical:
            msg = f"anchor {anchor!r} not found in {label!r}"
            raise KeyError(msg)
        _, start, end = entry.anchors_by_canonical[anchor]
        return Slice(
            label=label,
            anchor=anchor,
            text=entry.text[start:end],
            start=start,
            end=end,
        )


# ---------------------------------------------------------------------------
# Offset computation helpers
# ---------------------------------------------------------------------------


def _compute_offsets(
    text: str,
    primary: tuple[Anchor, ...],
    secondary: tuple[Anchor, ...],
) -> Mapping[str, tuple[Anchor, int, int]]:
    """Compute (start, end) byte offsets for each anchor.

    Primary anchors are indexed first; secondary (paragraph_index) anchors fill
    in any canonical slots not already claimed by the primary extractor.
    """
    result: dict[str, tuple[Anchor, int, int]] = {}
    for anchor in primary:
        start, end = _offsets_for(text, anchor)
        result[anchor.canonical] = (anchor, start, end)
    for anchor in secondary:
        if anchor.canonical not in result:
            start, end = _offsets_for(text, anchor)
            result[anchor.canonical] = (anchor, start, end)
    return result


def _offsets_for(text: str, anchor: Anchor) -> tuple[int, int]:
    """Locate (start, end) byte offsets for a single anchor within text.

    Heading and instance (email) anchors use their respective regex positions.
    Paragraph anchors use blank-line splitting with manual cursor tracking.
    Table-row anchors (also scheme="instance" but no _MESSAGE_RE match) fall
    back to (0, len(text)) — v1 behaviour; precise row slicing can be added later.
    """
    if anchor.scheme == "heading":
        positions = [m.start() for m in _HEADING_RE.finditer(text)]
        if anchor.position_index >= len(positions):
            return (0, len(text))
        start = positions[anchor.position_index]
        end = positions[anchor.position_index + 1] if anchor.position_index + 1 < len(positions) else len(text)
        return (start, end)

    if anchor.scheme == "instance":
        positions = [m.start() for m in _MESSAGE_RE.finditer(text)]
        if not positions or anchor.position_index >= len(positions):
            # Table rows and other instance anchors without _MESSAGE_RE matches:
            # return whole-doc offsets (v1 — precise slicing deferred).
            return (0, len(text))
        start = positions[anchor.position_index]
        end = positions[anchor.position_index + 1] if anchor.position_index + 1 < len(positions) else len(text)
        return (start, end)

    if anchor.scheme == "paragraph":
        cursor = 0
        seen = 0
        for chunk in text.split("\n\n"):
            if chunk.strip():
                if seen == anchor.position_index:
                    return (cursor, cursor + len(chunk))
                seen += 1
            cursor += len(chunk) + 2  # +2 accounts for the "\n\n" separator
        return (0, len(text))

    return (0, len(text))
