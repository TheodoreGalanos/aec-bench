# ABOUTME: Extract section references from verifier evidence; match them to real section keys.
# ABOUTME: Unblocks remediation on tasks where unsatisfied criteria are keyed by rubric dimension.

from __future__ import annotations

import re

# Match patterns in priority order:
#   1. "Section N.N.N" or "section N.N" (explicit Section keyword)
#   2. "N.N Name" (numbered + named heading)
#   3. "N.N" (bare number)
#   4. "SSNN" (substation code)
_SECTION_PATTERNS = [
    re.compile(r"\bSection\s+(\d+(?:\.\d+){0,2})\b", re.IGNORECASE),
    re.compile(r"\b(\d+\.\d+(?:\.\d+)?\s+[A-Z][A-Za-z ]+?)(?=\.|,|;|$|\s{2,})"),
    re.compile(r"\b(\d+\.\d+(?:\.\d+)?)\b"),
    re.compile(r"\b(SS\d{2,3})\b"),
]


def extract_section_refs(evidence: str) -> list[str]:
    """Return section references found in evidence, deduplicated in appearance order."""
    seen: dict[str, None] = {}
    for pattern in _SECTION_PATTERNS:
        for match in pattern.findall(evidence):
            ref = match.strip()
            if ref and ref not in seen:
                seen[ref] = None
    return list(seen.keys())


def _normalise_ref(ref: str) -> str:
    """Normalise a section ref to a lookup key (lowercase, non-alphanum -> _)."""
    return re.sub(r"[^a-z0-9]+", "_", ref.lower()).strip("_")


def match_refs_to_sections(
    refs: list[str],
    available_sections: list[str],
) -> list[str]:
    """Match normalised refs to available section keys, preserving ref-order.

    Each ref is normalised to lowercase underscored form. A ref matches a
    section key when either is a word-boundary prefix/suffix/substring of the
    other (same logic as applier._resolve_section). Results are returned in
    the order refs were supplied; duplicate matches are suppressed.
    """
    matched: dict[str, None] = {}
    for ref in refs:
        norm = _normalise_ref(ref)
        if not norm:
            continue
        for sec_key in available_sections:
            if sec_key in matched:
                continue
            if (
                sec_key == norm
                or sec_key.startswith(norm + "_")
                or sec_key.endswith("_" + norm)
                or ("_" + norm + "_") in sec_key
                or norm in sec_key.split("_")
            ):
                matched[sec_key] = None
    return list(matched.keys())
