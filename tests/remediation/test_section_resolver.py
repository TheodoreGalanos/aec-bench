# ABOUTME: Tests regex section-reference extraction from verifier evidence.
# ABOUTME: Supports numbered sections, substation codes, and named-with-number forms.

from aec_bench.remediation.section_resolver import (
    extract_section_refs,
    match_refs_to_sections,
)


def test_extract_numbered_section():
    evidence = "Issues found in 2.4 Electrical and 3.2 Site Access."
    refs = extract_section_refs(evidence)
    assert "2.4 Electrical" in refs or "2.4" in refs
    assert "3.2 Site Access" in refs or "3.2" in refs


def test_extract_section_keyword_form():
    evidence = "See Section 2.1 for the relevant scope."
    refs = extract_section_refs(evidence)
    assert any("2.1" in r for r in refs)


def test_extract_substation_codes():
    evidence = "SS04, SS05, SS07 have vague pricing language."
    refs = extract_section_refs(evidence)
    assert "SS04" in refs
    assert "SS05" in refs
    assert "SS07" in refs


def test_extract_deduplicates():
    evidence = "Issue with SS04 and again with SS04 later."
    refs = extract_section_refs(evidence)
    assert refs.count("SS04") == 1


def test_extract_returns_empty_when_no_refs():
    evidence = "Section text is generally vague without specifics."
    assert extract_section_refs(evidence) == []


def test_match_refs_to_sections_exact_normalised():
    refs = ["2.4 Electrical"]
    sections = ["introduction", "2_4_electrical", "scope_of_works"]
    assert match_refs_to_sections(refs, sections) == ["2_4_electrical"]


def test_match_refs_to_sections_word_boundary():
    refs = ["electrical"]
    sections = ["scope_of_works", "2_4_electrical", "supporting_material"]
    assert match_refs_to_sections(refs, sections) == ["2_4_electrical"]


def test_match_refs_to_sections_returns_empty_when_no_match():
    refs = ["3.9 Nonexistent"]
    sections = ["introduction", "scope_of_works"]
    assert match_refs_to_sections(refs, sections) == []


def test_match_refs_to_sections_preserves_order():
    refs = ["scope", "the_site"]
    sections = ["introduction", "the_site", "scope_of_works"]
    assert match_refs_to_sections(refs, sections) == ["scope_of_works", "the_site"]


def test_match_refs_handles_substation_codes():
    """SS04-style refs should match sections that have the code as a token."""
    refs = ["SS04"]
    sections = ["scope_of_works", "ss04_decommissioning", "general_requirements"]
    result = match_refs_to_sections(refs, sections)
    assert "ss04_decommissioning" in result
