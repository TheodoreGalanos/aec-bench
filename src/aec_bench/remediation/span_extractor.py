# ABOUTME: Pull quoted spans from verifier evidence and locate them in section text.
# ABOUTME: Used by the remediation loop to pre-highlight the defective span for the proposer.

from __future__ import annotations

import re

# Match quoted substrings with ASCII single, ASCII double, and smart quotes.
# Non-greedy to support multiple quoted spans per evidence string.
_QUOTE_PATTERNS = [
    re.compile(r"'([^']+?)'"),
    re.compile(r'"([^"]+?)"'),
    re.compile(r"\u2018([^\u2019]+?)\u2019"),
    re.compile(r"\u201c([^\u201d]+?)\u201d"),
]


def extract_quoted_spans(evidence: str) -> list[str]:
    """Return all quoted substrings found in the evidence string.

    Supports single, double, and smart quotes. Trims whitespace and drops
    empties. Preserves order of first appearance; duplicates kept once.
    """
    seen: dict[str, None] = {}
    for pattern in _QUOTE_PATTERNS:
        for match in pattern.findall(evidence):
            stripped = match.strip()
            if stripped and stripped not in seen:
                seen[stripped] = None
    return list(seen.keys())


def locate_span_in_section(
    section_text: str,
    candidate_spans: list[str],
) -> str | None:
    """Return the first candidate that appears exactly once in section_text.

    Returns None when no candidate has a unique match. Callers should
    fall back to the v1 locator-based path in this case.
    """
    for candidate in candidate_spans:
        if section_text.count(candidate) == 1:
            return candidate
    return None
