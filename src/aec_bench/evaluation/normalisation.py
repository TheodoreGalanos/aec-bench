# ABOUTME: Bounded-edit-distance normalisation pass -- fixes near-miss references in agent output.
# ABOUTME: Catches LLM fabrications and source-document typos via canonical refs from task config.

from __future__ import annotations

import re
from dataclasses import dataclass

from aec_bench.contracts.canonical_refs import CanonicalRefSet


def edit_distance(a: str, b: str) -> int:
    """Levenshtein edit distance between two strings.

    Inline implementation (no external deps). O(len(a) * len(b)) time
    and O(min(len(a), len(b))) space.
    """
    if len(a) < len(b):
        return edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[-1] + 1, prev[j] + 1, prev[j - 1] + cost))
        prev = curr
    return prev[-1]


@dataclass(frozen=True)
class NearMatch:
    """A near-miss found in agent output that maps to a canonical value."""

    matched_text: str
    canonical_value: str
    distance: int
    count: int = 1


@dataclass(frozen=True)
class NormalisationResult:
    """Result of running normalisation over an output string."""

    normalised: str
    substitutions_count: int
    audit_log: tuple[NearMatch, ...] = ()


# Conservative threshold: only exact single-edit typos (insert/delete/substitute)
# are auto-corrected. Distance 2 was proven to produce false positives on sibling
# project IDs (e.g. EST11127 vs EST11221 on the same base). Tasks that need
# wider matching can add the near-miss value as its own canonical ref.
_MAX_DISTANCE = 1
_TOKEN_PATTERN = re.compile(r"\b[A-Za-z0-9][A-Za-z0-9_\-]*\b")


def find_near_matches(text: str, refs: CanonicalRefSet) -> list[NearMatch]:
    """Find tokens in text that are near-misses to canonical reference values.

    A token is a maximal run of alphanumeric / underscore / hyphen chars.
    A token is a near-match if:
      - It is not equal to the canonical value
      - Edit distance to the canonical value is exactly 1
    """
    if not refs.refs:
        return []
    matches: dict[tuple[str, str], NearMatch] = {}
    for token in _TOKEN_PATTERN.findall(text):
        for ref in refs.refs:
            if token == ref.value:
                continue
            d = edit_distance(token, ref.value)
            if d == 0 or d > _MAX_DISTANCE:
                continue
            key = (token, ref.value)
            if key in matches:
                matches[key] = NearMatch(
                    matched_text=token,
                    canonical_value=ref.value,
                    distance=d,
                    count=matches[key].count + 1,
                )
            else:
                matches[key] = NearMatch(
                    matched_text=token,
                    canonical_value=ref.value,
                    distance=d,
                )
    return list(matches.values())


def normalise_output(text: str, refs: CanonicalRefSet) -> NormalisationResult:
    """Normalise the text by replacing near-matches with canonical values.

    Performs whole-token replacements only -- does not touch substrings
    inside longer identifiers (e.g. EST11221XYZ-001 stays unchanged
    because it's a different token).
    """
    matches = find_near_matches(text, refs)
    if not matches:
        return NormalisationResult(normalised=text, substitutions_count=0)

    normalised = text
    total_subs = 0
    for match in matches:
        # Whole-token replacement: use \b boundaries
        pattern = re.compile(rf"\b{re.escape(match.matched_text)}\b")
        normalised, n = pattern.subn(match.canonical_value, normalised)
        total_subs += n

    return NormalisationResult(
        normalised=normalised,
        substitutions_count=total_subs,
        audit_log=tuple(matches),
    )
