# ABOUTME: Tests for the lambda-rlm execution planner.
# ABOUTME: Validates plan construction from template + source documents with cost-optimal splitting.

from aec_bench.adapters.lambda_rlm.config import PlannerConfig
from aec_bench.adapters.lambda_rlm.planner import build_execution_plan
from aec_bench.adapters.lambda_rlm.state import CompositionOp


def _make_sections() -> list[dict]:
    """Minimal report-style section definitions."""
    return [
        {
            "id": "background",
            "title": "Background",
            "depends_on": [],
            "generation_mode": "transform",
            "writing_guidance": ["Carry language verbatim"],
            "input_mapping": ["brief:Description"],
        },
        {
            "id": "design",
            "title": "Design",
            "depends_on": ["background"],
            "generation_mode": "transform",
            "writing_guidance": ["Commit to preferred option"],
            "input_mapping": ["brief:Scope", "feasibility:options"],
        },
        {
            "id": "fee_summary",
            "title": "Fee Summary",
            "depends_on": ["design"],
            "generation_mode": "external",
            "writing_guidance": ["Placeholder tables only"],
            "input_mapping": [],
        },
    ]


def _make_source_docs() -> dict[str, str]:
    """Source document contents keyed by label."""
    return {
        "brief:Description": "A" * 5_000,
        "brief:Scope": "B" * 8_000,
        "feasibility:options": "C" * 12_000,
    }


def test_plan_skips_external_sections():
    plan = build_execution_plan(
        sections=_make_sections(),
        source_docs=_make_source_docs(),
        config=PlannerConfig(),
    )
    assert "fee_summary" in plan.skipped_sections
    assert "fee_summary" not in plan.section_plans


def test_plan_respects_dependency_order():
    plan = build_execution_plan(
        sections=_make_sections(),
        source_docs=_make_source_docs(),
        config=PlannerConfig(),
    )
    bg_idx = plan.section_order.index("background")
    design_idx = plan.section_order.index("design")
    assert bg_idx < design_idx


def test_plan_single_leaf_for_small_source():
    plan = build_execution_plan(
        sections=_make_sections(),
        source_docs=_make_source_docs(),
        config=PlannerConfig(context_window_chars=100_000),
    )
    bg_plan = plan.section_plans["background"]
    assert bg_plan.estimated_leaf_calls == 1
    assert bg_plan.estimated_reduce_calls == 0
    assert len(bg_plan.leaf_ops) == 1
    assert bg_plan.leaf_ops[0].total_chunks == 1


def test_plan_chunks_large_source():
    large_docs = {
        "brief:Description": "A" * 5_000,
        "brief:Scope": "B" * 8_000,
        "feasibility:options": "C" * 200_000,
    }
    plan = build_execution_plan(
        sections=_make_sections(),
        source_docs=large_docs,
        config=PlannerConfig(context_window_chars=100_000),
    )
    design_plan = plan.section_plans["design"]
    feasibility_leaves = [op for op in design_plan.leaf_ops if op.source == "feasibility:options"]
    assert len(feasibility_leaves) >= 2
    assert design_plan.estimated_reduce_calls >= 1


def test_plan_composition_ops_match_generation_mode():
    plan = build_execution_plan(
        sections=_make_sections(),
        source_docs=_make_source_docs(),
        config=PlannerConfig(),
    )
    assert plan.section_plans["background"].composition_op == CompositionOp.MERGE_EXTRACTIONS
    assert plan.section_plans["design"].composition_op == CompositionOp.MERGE_EXTRACTIONS


def test_plan_missing_source_treated_as_empty():
    """If input_mapping references a source not in source_docs, treat as empty."""
    sections = [
        {
            "id": "risks",
            "title": "Risks",
            "depends_on": [],
            "generation_mode": "guided",
            "writing_guidance": ["7-9 risks"],
            "input_mapping": ["brief:Risks", "feasibility:constraints"],
        },
    ]
    docs = {"brief:Risks": "Some risk content."}
    plan = build_execution_plan(sections=sections, source_docs=docs, config=PlannerConfig())
    risks_plan = plan.section_plans["risks"]
    assert risks_plan.estimated_leaf_calls == 1
    sources_in_ops = {op.source for op in risks_plan.leaf_ops}
    assert "brief:Risks" in sources_in_ops
    assert "feasibility:constraints" not in sources_in_ops
