# ABOUTME: Tests bounded-edit-distance near-match detection and audit-logged substitution.
# ABOUTME: Conservative defaults: distance <= 1 always, distance 2 only if both strings >=6 chars.

from aec_bench.contracts.canonical_refs import CanonicalRef, CanonicalRefSet
from aec_bench.evaluation.normalisation import (
    edit_distance,
    find_near_matches,
    normalise_output,
)


def test_edit_distance_identical_is_zero():
    assert edit_distance("EST11221", "EST11221") == 0


def test_edit_distance_single_insert_is_one():
    assert edit_distance("EST11221", "EST112211") == 1


def test_edit_distance_substitution_is_one():
    assert edit_distance("ABC", "ABD") == 1


def test_edit_distance_two_changes():
    assert edit_distance("hello", "hxllx") == 2


def test_edit_distance_completely_different_high():
    assert edit_distance("hello", "world") == 4


def test_find_near_matches_detects_extra_digit():
    """The motivating case: EST112211 is one insertion from EST11221."""
    text = "Per cost estimate EST112211 Revision D, the scope is..."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    matches = find_near_matches(text, refs)
    assert len(matches) == 1
    assert matches[0].matched_text == "EST112211"
    assert matches[0].canonical_value == "EST11221"
    assert matches[0].distance == 1


def test_find_near_matches_skips_exact_matches():
    text = "Project EST11221 is referenced here."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    matches = find_near_matches(text, refs)
    assert matches == []


def test_find_near_matches_ignores_distance_greater_than_two():
    text = "Project EST99999 is fabricated."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    matches = find_near_matches(text, refs)
    assert matches == []


def test_find_near_matches_short_strings_only_distance_1():
    """Distance 2 is only allowed when both strings are >=6 chars."""
    text = "Reference: ABCD"
    refs = CanonicalRefSet(refs=(CanonicalRef(name="code", value="WXYZ"),))
    matches = find_near_matches(text, refs)
    # ABCD vs WXYZ has distance 4 -- no match regardless of length rule
    assert matches == []


def test_find_near_matches_distance_2_allowed_for_long_strings():
    """Two-char difference between two >=6-char strings should match."""
    text = "See document RAAFEastSXle (transposed)"
    refs = CanonicalRefSet(refs=(CanonicalRef(name="base", value="RAAFEastSale"),))
    matches = find_near_matches(text, refs)
    # RAAFEastSXle vs RAAFEastSale: 1 substitution = distance 1
    assert len(matches) == 1
    assert matches[0].canonical_value == "RAAFEastSale"


def test_normalise_output_replaces_all_instances():
    text = "Per EST112211 (revision D) and again per EST112211, scope is set."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = normalise_output(text, refs)
    assert result.normalised.count("EST112211") == 0
    assert result.normalised.count("EST11221") == 2
    assert result.substitutions_count == 2


def test_normalise_output_audit_log_records_each_substitution():
    text = "Per EST112211 and once for EST11221x"
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = normalise_output(text, refs)
    audits = result.audit_log
    assert len(audits) >= 1
    # Each audit entry has matched_text, canonical_value, distance, count
    for entry in audits:
        assert entry.matched_text != entry.canonical_value
        assert entry.distance > 0


def test_normalise_output_preserves_text_when_no_matches():
    text = "Project EST11221 -- no near-misses anywhere in this body of text."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = normalise_output(text, refs)
    assert result.normalised == text
    assert result.substitutions_count == 0
    assert result.audit_log == ()


def test_normalise_output_with_empty_ref_set_is_passthrough():
    text = "Anything goes here, no canonical refs declared."
    result = normalise_output(text, CanonicalRefSet())
    assert result.normalised == text
    assert result.substitutions_count == 0


def test_normalise_output_does_not_match_substring_in_longer_word():
    """EST11221 must not match EST11221X if X-suffix is part of a longer ID."""
    text = "Drawing EST11221XYZ-001 references different doc."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = normalise_output(text, refs)
    # EST11221XYZ is too far from EST11221 to be a near-match (distance 3)
    # and we don't want to replace inside a longer identifier
    assert "EST11221XYZ-001" in result.normalised


def test_find_near_matches_distance_2_rejected_regardless_of_length():
    """Distance 2 is always rejected — tighter default after EST11127 false positive."""
    # Two 6-char strings at distance 2; previously allowed under length guard.
    text = "Reference AXCDEY here."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="code", value="ABCDEF"),))
    matches = find_near_matches(text, refs)
    assert matches == []


def test_find_near_matches_sibling_id_not_matched():
    """Real-world case: EST11127 (sibling project) must NOT be normalised to EST11221."""
    text = "See related project EST11127 for context; this project is EST11221."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    matches = find_near_matches(text, refs)
    # EST11127 vs EST11221 has distance 2 — now rejected
    assert matches == []


def test_normalise_output_audit_count_bumps_for_repeated_token():
    """Same token string twice produces one audit entry with count=2."""
    text = "Per EST112211 (rev D) and again per EST112211."
    refs = CanonicalRefSet(refs=(CanonicalRef(name="project_id", value="EST11221"),))
    result = normalise_output(text, refs)
    assert len(result.audit_log) == 1
    assert result.audit_log[0].count == 2
