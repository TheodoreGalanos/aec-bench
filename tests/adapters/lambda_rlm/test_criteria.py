# ABOUTME: Tests for criteria bundle assembly used by the best-of-k tournament.
# ABOUTME: Verifies writing rules + multi-dimension rubric criteria are merged correctly.

from __future__ import annotations

from aec_bench.adapters.lambda_rlm.criteria import (
    build_all_criteria_bundles,
    build_criteria_bundle,
    filter_references,
)
from aec_bench.contracts.repl import DependencyTreeSchema, TreeSection
from aec_bench.contracts.rubric import Rubric, RubricCriterion, RubricDimension


def _make_section(section_id: str, title: str, rules: list[str]) -> TreeSection:
    return TreeSection(
        id=section_id,
        title=title,
        fields={},
        depends_on=(),
        generation_mode="guided",
        per_discipline=False,
        writing_guidance=tuple(rules),
        input_mapping=(),
    )


def _make_rubric() -> Rubric:
    return Rubric(
        dimensions=[
            RubricDimension(
                id="methodology_quality",
                name="Methodology Quality",
                description="",
                weight=3.0,
                max_score=10.0,
                eval_method="llm_judge",
                criteria=[
                    RubricCriterion(text="Addresses both projects", category="essential"),
                    RubricCriterion(text="References NZ CCTV manual", category="essential"),
                ],
                eval_sections=("methodology",),
                eval_references=("scope_of_works", "activity-brief"),
                expert_persona="A wastewater consulting engineer",
            ),
            RubricDimension(
                id="innovation_quality",
                name="Innovation",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="llm_judge",
                criteria=[
                    RubricCriterion(text="Innovations are project-specific", category="essential"),
                ],
                eval_sections=("innovation",),
                eval_references=(),
                expert_persona="A sustainability advisor",
            ),
            RubricDimension(
                id="cross_section_quality",
                name="Cross",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="llm_judge",
                criteria=[
                    RubricCriterion(text="Coherent across sections", category="important"),
                ],
                eval_sections=("methodology", "innovation"),
                eval_references=("references",),
                expert_persona="",
            ),
        ],
        rollup_strategy="weighted_mean",
    )


def test_build_bundle_one_to_one_dimension():
    section = _make_section("methodology", "Proposed Methodology", ["MANDATORY: cover both projects"])
    rubric = _make_rubric()
    bundle = build_criteria_bundle(section=section, rubric=rubric)

    assert bundle.section_id == "methodology"
    assert bundle.section_title == "Proposed Methodology"
    assert bundle.writing_rules == ("MANDATORY: cover both projects",)
    # methodology is targeted by methodology_quality AND cross_section_quality
    assert "methodology_quality" in bundle.rubric_dimensions
    assert "cross_section_quality" in bundle.rubric_dimensions
    # All criteria from both targeting dimensions are bundled
    assert len(bundle.rubric_criteria) == 3


def test_build_bundle_unions_eval_references():
    section = _make_section("methodology", "Methodology", [])
    rubric = _make_rubric()
    bundle = build_criteria_bundle(section=section, rubric=rubric)
    assert "scope_of_works" in bundle.eval_references
    assert "activity-brief" in bundle.eval_references
    assert "references" in bundle.eval_references  # from cross_section dim


def test_build_bundle_collects_personas():
    section = _make_section("methodology", "Methodology", [])
    rubric = _make_rubric()
    bundle = build_criteria_bundle(section=section, rubric=rubric)
    # methodology_quality has a persona; cross_section_quality has empty (deduped out)
    assert any("wastewater consulting" in p for p in bundle.expert_personas)
    assert "" not in bundle.expert_personas


def test_build_bundle_with_no_rubric():
    section = _make_section("intro", "Introduction", ["Be concise"])
    bundle = build_criteria_bundle(section=section, rubric=None)
    assert bundle.writing_rules == ("Be concise",)
    assert bundle.rubric_dimensions == ()
    assert bundle.rubric_criteria == ()
    assert bundle.eval_references == ()


def test_format_for_judge_includes_all_blocks():
    section = _make_section("methodology", "Methodology", ["MANDATORY: rule one"])
    bundle = build_criteria_bundle(section=section, rubric=_make_rubric())
    rendered = bundle.format_for_judge()
    assert "SECTION: Methodology" in rendered
    assert "SECTION WRITING RULES:" in rendered
    assert "MANDATORY: rule one" in rendered
    assert "EVALUATION CRITERIA" in rendered
    assert "ESSENTIAL" in rendered
    assert "EVALUATOR CONTEXT:" in rendered


def test_build_all_bundles_covers_every_section():
    schema = DependencyTreeSchema(
        sections=[
            _make_section("methodology", "Methodology", ["a"]),
            _make_section("innovation", "Innovation", ["b"]),
            _make_section("orphan", "Orphan", ["c"]),  # not in any rubric dim
        ]
    )
    bundles = build_all_criteria_bundles(schema=schema, rubric=_make_rubric())
    assert set(bundles.keys()) == {"methodology", "innovation", "orphan"}
    assert bundles["orphan"].rubric_dimensions == ()


def test_filter_references_substring_match():
    refs = {
        "scope_of_works": "scope content",
        "activity-brief-omapere": "omapere content",
        "team_profiles": "team content",
    }
    filtered = filter_references(refs, ["scope_of_works", "activity-brief"])
    assert "scope_of_works" in filtered
    assert "activity-brief-omapere" in filtered
    assert "team_profiles" not in filtered


def test_filter_references_empty_returns_all():
    refs = {"a": "1", "b": "2"}
    assert filter_references(refs, ()) == refs


def test_filter_references_no_match_returns_all_fallback():
    refs = {"a": "1", "b": "2"}
    assert filter_references(refs, ["missing"]) == refs
