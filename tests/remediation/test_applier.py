# ABOUTME: Tests locator-based patch application — single-match validation, ambiguity rejection.
# ABOUTME: Applier refuses to edit when locator_phrase matches 0 or >1 times in the target section.

import pytest

from aec_bench.contracts.remediation import Patch
from aec_bench.remediation.applier import (
    AmbiguousLocator,
    AnnotatedPatch,
    SectionNotFound,
    apply_annotated_patch,
    apply_patch,
    apply_patches,
    split_sections,
)


def _sample_output() -> str:
    return """# 3. Contractor Obligations

## 3.2 Site Access

The Contractor shall not permit any person to access the Site without approval.

## 3.3 Security

All personnel require project clearance.

# 4. Scope

Sample scope items follow.
"""


def test_split_sections_by_h1():
    sections = split_sections(_sample_output())
    # Allow either normalised id ("contractor_obligations") or similar
    keys = list(sections)
    assert any("contractor" in k for k in keys)
    assert any("scope" in k for k in keys)


def test_apply_patch_replaces_locator_phrase():
    patch = Patch(
        section_id="contractor_obligations",
        locator_phrase="shall not permit any person to access the Site without approval",
        replacement="shall not permit unauthorised personnel to enter the Site",
        occurrence=1,
    )
    result = apply_patch(_sample_output(), patch)
    assert "shall not permit unauthorised personnel" in result
    assert "shall not permit any person to access" not in result


def test_apply_patch_rejects_ambiguous_locator():
    text = """# 3. Contractor Obligations

The Contractor shall comply.
The Contractor shall comply.
"""
    patch = Patch(
        section_id="contractor_obligations",
        locator_phrase="The Contractor shall comply",
        replacement="x",
        occurrence=1,
    )
    with pytest.raises(AmbiguousLocator):
        apply_patch(text, patch)


def test_apply_patch_rejects_missing_locator():
    patch = Patch(
        section_id="contractor_obligations",
        locator_phrase="nonexistent phrase",
        replacement="x",
        occurrence=1,
    )
    with pytest.raises(AmbiguousLocator):
        apply_patch(_sample_output(), patch)


def test_apply_patch_rejects_missing_section():
    patch = Patch(
        section_id="no_such_section",
        locator_phrase="anything",
        replacement="x",
        occurrence=1,
    )
    with pytest.raises(SectionNotFound):
        apply_patch(_sample_output(), patch)


def test_apply_patches_applies_successes_records_failures():
    good = Patch(
        section_id="contractor_obligations",
        locator_phrase="shall not permit any person",
        replacement="shall not permit unauthorised personnel",
        occurrence=1,
    )
    bad = Patch(
        section_id="contractor_obligations",
        locator_phrase="missing phrase",
        replacement="x",
        occurrence=1,
    )
    result = apply_patches(_sample_output(), [good, bad])
    assert "unauthorised personnel" in result.patched_text
    assert result.applied_count == 1
    assert len(result.rejected) == 1
    assert result.rejected[0].patch is bad


def test_apply_patches_preserves_order():
    """Applying patches must not reorder sections or lose content."""
    original = _sample_output()
    patch = Patch(
        section_id="scope",
        locator_phrase="Sample scope items follow",
        replacement="Scope details listed below",
        occurrence=1,
    )
    result = apply_patches(original, [patch])
    assert "# 3. Contractor Obligations" in result.patched_text
    assert "# 4. Scope" in result.patched_text
    assert "Scope details listed below" in result.patched_text
    assert "All personnel require project clearance." in result.patched_text


def test_apply_patch_rejects_substring_collision():
    """'scope' must NOT match 'telescope_specs' — word-boundary partial match only."""
    text = """# Telescope Specs

Body text.
"""
    patch = Patch(
        section_id="scope",
        locator_phrase="Body text",
        replacement="x",
        occurrence=1,
    )
    with pytest.raises(SectionNotFound):
        apply_patch(text, patch)


def test_apply_patch_accepts_word_boundary_prefix_match():
    """'scope' DOES match 'scope_of_works' because it's a word-prefix."""
    text = """# 2. Scope of Works

Sample scope items follow.
"""
    patch = Patch(
        section_id="scope",
        locator_phrase="Sample scope items follow",
        replacement="Scope details listed below",
        occurrence=1,
    )
    result = apply_patch(text, patch)
    assert "Scope details listed below" in result


def test_apply_annotated_patch_replaces_span():
    text = """# 3. Contractor Obligations

The Contractor shall allow for investigation works as part of the lump sum.
"""
    patch = AnnotatedPatch(
        section_id="contractor_obligations",
        span_to_replace="allow for investigation works",
        replacement="allow up to 40 hours of investigation works",
    )
    result = apply_annotated_patch(text, patch)
    assert "allow up to 40 hours of investigation works" in result
    assert "allow for investigation works" not in result


def test_apply_annotated_patch_rejects_ambiguous_span():
    """Even annotated patches reject ambiguous spans — guards against stale patches."""
    text = """# 3. Contractor Obligations

allow for x and allow for y
"""
    patch = AnnotatedPatch(
        section_id="contractor_obligations",
        span_to_replace="allow for",
        replacement="specified",
    )
    with pytest.raises(AmbiguousLocator):
        apply_annotated_patch(text, patch)


def test_apply_annotated_patch_rejects_missing_span():
    """The span must be present in the section — if document changed since span selection, reject."""
    text = """# 3. Contractor Obligations

Nothing here matches.
"""
    patch = AnnotatedPatch(
        section_id="contractor_obligations",
        span_to_replace="allow for investigation works",
        replacement="x",
    )
    with pytest.raises(AmbiguousLocator):
        apply_annotated_patch(text, patch)
