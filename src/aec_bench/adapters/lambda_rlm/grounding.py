# ABOUTME: Grounding-check fact detectors + category-specific matchers.
# ABOUTME: Five built-in categories; template-extensible via custom_patterns mapping.

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox, parse_anchor_ref
from aec_bench.contracts.grounding_report import (
    FactCategory,
    FlaggedFact,
    SectionGroundingResult,
)


@dataclass(frozen=True)
class CandidateFact:
    """A fact extracted from output text, ready to be matched against slices."""

    fact: str
    category: FactCategory


# ─── Built-in detector regexes ────────────────────────────────────────────────


_URL_RE = re.compile(r"https?://[^\s)\]]+")

_DOC_REF_RE = re.compile(r"\b(?:NZS|AS/NZS|AS|ISO|IEC|EST|WWL|HCP)\s*\d+(?:[:\-/]\d+)*\b")

_NUMBER_UNIT_RE = re.compile(
    r"\d+(?:\.\d+)?\s?"
    r"(?:kW|MW|GW|kV|MVA|m³(?:/h)?|m²|km|mm|kg|°C|%|m|t)\b"
)

_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")

_LONG_DATE_RE = re.compile(
    r"\b\d{1,2}\s+(?:January|February|March|April|May|June|July|"
    r"August|September|October|November|December)\s+\d{4}\b"
)

_PROPER_NOUN_RE = re.compile(
    # Title-case tokens only (`[A-Z][a-z]+`) so all-caps section headings like
    # 'ADDRESS FOR NOTICES' don't match. Separator is a literal space rather
    # than `\s+` so the phrase can't span newlines or eat heading-then-name
    # patterns like 'ADDRESS\n\nExample Dairy'. Surfaced by a live report run
    # with multiple false-positive proper-noun flags.
    r"\b(?:[A-Z][a-z]+)(?:[ ]+[A-Z][a-z]+){1,3}\b"
)

_PROPER_NOUN_STOPWORDS_FIRST = frozenset(
    {
        # Determiners + section structure
        "The",
        "A",
        "An",
        "This",
        "Project",
        "Phase",
        "Section",
        "ExampleCo",
        # Signature-block / document-header table labels — these get rendered
        # adjacent to title-case names ('Name Mark Abbott', 'Position Project
        # Manager') and produce false-positive proper-noun matches. Surfaced
        # by a live report run. Add new labels here as they
        # appear in real grounding reports rather than preemptively.
        "Name",
        "Position",
    }
)


# ─── Public API ───────────────────────────────────────────────────────────────


def extract_facts(
    text: str,
    *,
    custom_patterns: Mapping[str, re.Pattern[str]] | None = None,
) -> tuple[CandidateFact, ...]:
    """Extract candidate facts from output text across five categories."""
    facts: list[CandidateFact] = []

    for m in _URL_RE.finditer(text):
        facts.append(CandidateFact(m.group(0), "url"))

    for m in _DOC_REF_RE.finditer(text):
        facts.append(CandidateFact(m.group(0), "document_ref"))

    for m in _NUMBER_UNIT_RE.finditer(text):
        facts.append(CandidateFact(m.group(0), "number_with_unit"))

    for m in _ISO_DATE_RE.finditer(text):
        facts.append(CandidateFact(m.group(0), "date"))
    for m in _LONG_DATE_RE.finditer(text):
        facts.append(CandidateFact(m.group(0), "date"))

    for m in _PROPER_NOUN_RE.finditer(text):
        first_token = m.group(0).split()[0]
        if first_token not in _PROPER_NOUN_STOPWORDS_FIRST:
            facts.append(CandidateFact(m.group(0), "proper_noun_phrase"))

    if custom_patterns:
        for _name, pattern in custom_patterns.items():
            for m in pattern.finditer(text):
                # Custom patterns are bucketed as document_ref in v1
                # (their nature is template-specific identifiers).
                facts.append(CandidateFact(m.group(0), "document_ref"))

    return tuple(facts)


def match_fact_in_text(
    fact: str,
    category: FactCategory,
    text: str,
) -> bool:
    """Apply category-specific matching rules from spec Q10."""
    if category == "url":
        return _normalise_url(fact) in _normalise_url(text)
    if category == "document_ref":
        return _normalise_doc_ref(fact) in _normalise_doc_ref(text)
    if category == "number_with_unit":
        return _strip_unit(fact) in _strip_unit(text)
    if category == "date":
        return _date_to_iso(fact) in _all_dates_iso(text)
    if category == "proper_noun_phrase":
        return _all_tokens_within_window(fact, text, window=50)
    return False


def run_grounding_check(
    *,
    section_id: str,
    section_text: str,
    block_traces: Sequence[Mapping[str, Any]],
    sandbox: DocumentSandbox,
    custom_patterns: Mapping[str, re.Pattern[str]] | None = None,
    back_brief: Mapping[str, str] | None = None,
) -> SectionGroundingResult:
    """Audit a section's text against the slices each block declared as provenance.

    Returns a SectionGroundingResult with one FlaggedFact per fact that did not
    appear in any of its owning block's accessed slices.

    *back_brief*, when provided, supplies content for ``references/*:<topic>``
    provenance refs — these point into the planning-phase back-brief digest
    rather than the document sandbox. Matches the resolution order used by
    ``compose_bridge._format_sandbox_sources`` so the auditor sees the same
    sources the generator did.
    """
    facts = extract_facts(section_text, custom_patterns=custom_patterns)
    flagged: list[FlaggedFact] = []
    facts_checked = 0
    facts_grounded = 0

    for cf in facts:
        offset = section_text.find(cf.fact)
        if offset < 0:
            continue
        owner = _find_owning_block(block_traces, offset)
        if owner is None:
            continue

        provenance = tuple(owner.get("provenance", []) or [])
        # Skip blocks with no declared provenance — there's nothing to audit
        # against. This is the case for verbatim blocks, and for fill blocks
        # whose slot values came entirely from the planning-phase scratchpad
        # (which v1 doesn't surface as block-level provenance). Counting them
        # as 'flagged' produces noise; counting them as 'grounded' would be
        # dishonest. Skipping them silently is the truthful v1 behaviour.
        # Surfaced by a live report run.
        if not provenance:
            continue

        facts_checked += 1
        accessed_texts = _slice_texts(sandbox, provenance, back_brief=back_brief)

        is_grounded = any(match_fact_in_text(cf.fact, cf.category, t) for t in accessed_texts)
        if is_grounded:
            facts_grounded += 1
        else:
            flagged.append(
                FlaggedFact(
                    fact=cf.fact,
                    category=cf.category,
                    block_index=int(owner.get("block_index", -1)),
                    block_provenance=provenance,
                    matched_anchors=(),
                )
            )

    return SectionGroundingResult(
        section_id=section_id,
        facts_checked=facts_checked,
        facts_grounded=facts_grounded,
        flagged=tuple(flagged),
    )


# ─── Normalisers ──────────────────────────────────────────────────────────────


def _normalise_url(s: str) -> str:
    """Lowercase, strip trailing slash, strip query string."""
    s = s.lower()
    # Strip query string
    if "?" in s:
        s = s.split("?", 1)[0]
    # Strip trailing slash
    s = s.rstrip("/")
    return s


def _normalise_doc_ref(s: str) -> str:
    """Uppercase, strip all whitespace."""
    return re.sub(r"\s+", "", s).upper()


def _strip_unit(s: str) -> str:
    """Lowercase, strip whitespace — for number+unit comparison."""
    return re.sub(r"\s+", "", s).lower()


_MONTHS = {
    name: idx
    for idx, name in enumerate(
        [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ],
        start=1,
    )
}


def _date_to_iso(s: str) -> str:
    """Parse a date string (ISO or '30 June 2026' form) into ISO 8601."""
    if _ISO_DATE_RE.fullmatch(s):
        return s
    parts = s.split()
    if len(parts) == 3 and parts[1] in _MONTHS:
        day = int(parts[0])
        month = _MONTHS[parts[1]]
        year = parts[2]
        return f"{year}-{month:02d}-{day:02d}"
    return s


def _all_dates_iso(text: str) -> set[str]:
    """Collect every date in text, normalised to ISO."""
    out = {m.group(0) for m in _ISO_DATE_RE.finditer(text)}
    for m in _LONG_DATE_RE.finditer(text):
        out.add(_date_to_iso(m.group(0)))
    return out


def _all_tokens_within_window(fact: str, text: str, *, window: int) -> bool:
    """All tokens of *fact* must appear within a *window*-char span in *text*."""
    tokens = fact.lower().split()
    text_l = text.lower()
    if not tokens:
        return False
    if len(text_l) <= window:
        return all(tok in text_l for tok in tokens)
    for start in range(len(text_l) - window + 1):
        chunk = text_l[start : start + window]
        if all(tok in chunk for tok in tokens):
            return True
    return False


def _find_owning_block(
    block_traces: Sequence[Mapping[str, Any]],
    offset: int,
) -> Mapping[str, Any] | None:
    """Return the first block whose [start_offset, end_offset) contains offset."""
    for trace in block_traces:
        start = int(trace.get("start_offset", 0))
        end = int(trace.get("end_offset", 0))
        if start <= offset < end:
            return trace
    return None


def _slice_texts(
    sandbox: DocumentSandbox,
    provenance: tuple[str, ...],
    *,
    back_brief: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Fetch each anchor's slice text; silently skip stale or unparseable anchors.

    Resolution order per ref mirrors ``compose_bridge._format_sandbox_sources``:
      1. ``references/*:<topic>`` + non-empty ``back_brief[<topic>]`` → the
         topic digest text.
      2. Otherwise parse via ``parse_anchor_ref`` and fetch from the sandbox.

    Refs that fail at every step are silently dropped.
    """
    out: list[str] = []
    for ref in provenance:
        if back_brief is not None and ref.startswith("references/*:"):
            topic = ref.split(":", 1)[1]
            content = back_brief.get(topic, "")
            if content:
                out.append(content)
            continue
        try:
            label, anchor = parse_anchor_ref(ref)
        except ValueError:
            continue
        try:
            sl = sandbox.slice(label, anchor)
        except KeyError:
            continue
        out.append(sl.text)
    return tuple(out)


__all__ = [
    "CandidateFact",
    "extract_facts",
    "match_fact_in_text",
    "run_grounding_check",
]
