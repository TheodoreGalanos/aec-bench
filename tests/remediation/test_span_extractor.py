# ABOUTME: Tests span extraction from verifier evidence — regex for quoted substrings, exact-match lookup.
# ABOUTME: Powers the v2 remediation path where spans are pre-highlighted for the LLM.

from aec_bench.remediation.span_extractor import (
    extract_quoted_spans,
    locate_span_in_section,
)


def test_extract_single_quoted_span():
    evidence = "Several items use open-ended 'allow for' language in SS04."
    spans = extract_quoted_spans(evidence)
    assert "allow for" in spans


def test_extract_double_quoted_span():
    evidence = 'The phrase "allow for investigation works" is vague.'
    spans = extract_quoted_spans(evidence)
    assert "allow for investigation works" in spans


def test_extract_smart_quoted_span():
    evidence = "The phrase \u2018allow for\u2019 is vague, and also \u201copen-ended\u201d."
    spans = extract_quoted_spans(evidence)
    assert "allow for" in spans
    assert "open-ended" in spans


def test_extract_multiple_quoted_spans():
    evidence = "Items 'alpha', 'beta', and 'gamma' are vague."
    spans = extract_quoted_spans(evidence)
    assert "alpha" in spans
    assert "beta" in spans
    assert "gamma" in spans


def test_extract_returns_empty_list_when_no_quotes():
    evidence = "Several items are unspecific without any quoted examples."
    assert extract_quoted_spans(evidence) == []


def test_extract_strips_whitespace():
    evidence = "See the phrase '  spaced out  ' somewhere."
    spans = extract_quoted_spans(evidence)
    assert "spaced out" in spans


def test_locate_returns_span_when_unique_match():
    section = "The Contractor shall allow for investigation works as part of the lump sum."
    candidates = ["allow for investigation works", "lump sum payment"]
    assert locate_span_in_section(section, candidates) == "allow for investigation works"


def test_locate_returns_none_when_no_match():
    section = "This section contains neither candidate phrase."
    candidates = ["alpha", "beta"]
    assert locate_span_in_section(section, candidates) is None


def test_locate_returns_none_when_ambiguous_match():
    """Candidate that appears >1 times must not be selected (caller should fallback)."""
    section = "allow for x and allow for y"
    candidates = ["allow for"]
    assert locate_span_in_section(section, candidates) is None


def test_locate_prefers_first_unique_candidate():
    """If multiple candidates have unique matches, the first listed wins."""
    section = "alpha bravo charlie delta"
    candidates = ["alpha", "charlie"]
    assert locate_span_in_section(section, candidates) == "alpha"
