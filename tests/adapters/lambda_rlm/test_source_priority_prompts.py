# ABOUTME: Tests priority-aware prompt content for extraction, generation, and review.
# ABOUTME: Lower priority number = higher authority. Prompts emit ordered tier lists.

from aec_bench.adapters.lambda_rlm.prompts import (
    build_extraction_prompt,
    build_generation_prompt,
    build_review_prompt,
)


def test_extraction_prompt_mentions_priority_when_provided():
    prompt = build_extraction_prompt(
        section_title="Scope",
        generation_mode="prose",
        writing_guidance=["crisp"],
        source_label="design_report:d",
        chunk_text="alpha",
        dependency_context={},
        source_priority=1,
    )
    assert "priority 1" in prompt.lower() or "tier 1" in prompt.lower()


def test_extraction_prompt_without_priority_omits_the_line():
    """Omitting source_priority produces a prompt without the priority annotation."""
    prompt = build_extraction_prompt(
        section_title="Scope",
        generation_mode="prose",
        writing_guidance=["crisp"],
        source_label="design_report:d",
        chunk_text="alpha",
        dependency_context={},
    )
    assert "priority" not in prompt.lower()
    assert "tier" not in prompt.lower()


def test_generation_prompt_emits_ordered_precedence_block_when_priorities_present():
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"a": 1},
        dependency_sections={},
        source_priority={
            "design_report:d": 1,
            "project_brief:p": 4,
            "cost_estimate:c": 3,
            "spec_summaries:s": 2,
        },
    )
    # Precedence list is emitted in ascending priority order
    dr_pos = prompt.find("design_report:d")
    sp_pos = prompt.find("spec_summaries:s")
    ce_pos = prompt.find("cost_estimate:c")
    pb_pos = prompt.find("project_brief:p")
    assert dr_pos != -1 and sp_pos != -1 and ce_pos != -1 and pb_pos != -1
    assert dr_pos < sp_pos < ce_pos < pb_pos
    assert "prefer" in prompt.lower() or "higher" in prompt.lower() or "authority" in prompt.lower()


def test_generation_prompt_without_priority_is_unchanged():
    """source_priority={} or absent: no precedence block emitted."""
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"a": 1},
        dependency_sections={},
    )
    assert "Source precedence" not in prompt
    assert "Tier 1" not in prompt


def test_generation_prompt_with_uniform_priority_omits_precedence_block():
    """If all sources share the same priority, no precedence hint is meaningful."""
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"a": 1},
        dependency_sections={},
        source_priority={"design_report:d": 1, "cost_estimate:c": 1},
    )
    assert "Source precedence" not in prompt


def test_generation_prompt_with_two_tiers_emits_block():
    prompt = build_generation_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        extracted_data={"a": 1},
        dependency_sections={},
        source_priority={"design_report:d": 1, "project_brief:p": 2},
    )
    assert "design_report:d" in prompt
    assert "project_brief:p" in prompt
    assert "prefer" in prompt.lower() or "higher" in prompt.lower()


def test_review_prompt_suppresses_lower_priority_gap_flags():
    """Review prompt hints that lower-priority sources aren't expected to be exhaustive."""
    prompt = build_review_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        input_sources=["design_report:d", "project_brief:p"],
        extracted_data={"a": 1},
        dependency_summaries={},
        source_priority={"design_report:d": 1, "project_brief:p": 4},
    )
    assert "lower" in prompt.lower() or "priority" in prompt.lower() or "authority" in prompt.lower()


def test_review_prompt_without_priority_is_unchanged():
    prompt = build_review_prompt(
        section_title="Scope",
        writing_guidance=["crisp"],
        input_sources=["design_report:d"],
        extracted_data={"a": 1},
        dependency_summaries={},
    )
    assert "priority" not in prompt.lower()
    assert "authority" not in prompt.lower()
