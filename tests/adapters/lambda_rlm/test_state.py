# ABOUTME: Tests for lambda-rlm execution plan and state dataclasses.
# ABOUTME: Validates plan construction, state snapshots, and cost estimation.

import json

from aec_bench.adapters.lambda_rlm.state import (
    CompositionOp,
    ExecutionPlan,
    LeafOp,
    PlanState,
    ReduceOp,
    ReviewResult,
    SectionPlan,
)


def test_section_plan_single_source():
    plan = SectionPlan(
        section_id="background",
        generation_mode="transform",
        sources=["brief:Description/Background"],
        leaf_ops=[LeafOp(source="brief:Description/Background", chunk_index=0, total_chunks=1)],
        reduce_ops=[],
        composition_op=CompositionOp.MERGE_EXTRACTIONS,
        estimated_leaf_calls=1,
        estimated_reduce_calls=0,
    )
    assert plan.estimated_total_calls == 1


def test_section_plan_chunked_source():
    leaf_ops = [LeafOp(source="feasibility:full", chunk_index=i, total_chunks=4) for i in range(4)]
    plan = SectionPlan(
        section_id="methodology",
        generation_mode="guided",
        sources=["feasibility:full"],
        leaf_ops=leaf_ops,
        reduce_ops=[ReduceOp(source="feasibility:full", inputs_count=4)],
        composition_op=CompositionOp.MERGE_EXTRACTIONS,
        estimated_leaf_calls=4,
        estimated_reduce_calls=1,
    )
    assert plan.estimated_total_calls == 5


def test_execution_plan_total_cost():
    plans = [
        SectionPlan(
            section_id="background",
            generation_mode="transform",
            sources=["brief:bg"],
            leaf_ops=[LeafOp(source="brief:bg", chunk_index=0, total_chunks=1)],
            reduce_ops=[],
            composition_op=CompositionOp.MERGE_EXTRACTIONS,
            estimated_leaf_calls=1,
            estimated_reduce_calls=0,
        ),
        SectionPlan(
            section_id="design",
            generation_mode="transform",
            sources=["brief:scope", "feasibility:options"],
            leaf_ops=[
                LeafOp(source="brief:scope", chunk_index=0, total_chunks=1),
                LeafOp(source="feasibility:options", chunk_index=0, total_chunks=1),
            ],
            reduce_ops=[],
            composition_op=CompositionOp.MERGE_EXTRACTIONS,
            estimated_leaf_calls=2,
            estimated_reduce_calls=0,
        ),
    ]
    exec_plan = ExecutionPlan(
        section_order=["background", "design"],
        section_plans={"background": plans[0], "design": plans[1]},
        skipped_sections=["fee_summary"],
    )
    assert exec_plan.total_estimated_leaf_calls == 3
    assert exec_plan.total_estimated_reduce_calls == 0
    assert exec_plan.total_estimated_calls == 3 + 0 + 2 + 2


def test_plan_state_snapshot():
    state = PlanState()
    state.extractions["background"] = {"brief:bg": {"location": "Princes Highway"}}
    state.sections["background"] = "The project is located on Princes Highway."
    state.phase = "generate"
    state.current_section = "design"
    state.llm_calls = 5
    state.tokens_used = 12000

    snapshot = state.snapshot()
    assert snapshot["phase"] == "generate"
    assert snapshot["current_section"] == "design"
    assert snapshot["llm_calls"] == 5
    assert snapshot["tokens_used"] == 12000
    assert "background" in snapshot["extractions"]
    assert "background" in snapshot["sections"]
    json.dumps(snapshot)


def test_review_result_pass():
    result = ReviewResult(
        status="pass",
        gaps=[],
        risks=[],
        reextract_sources=[],
        supplement_guidance=None,
    )
    assert result.needs_action is False


def test_review_result_needs_reextract():
    result = ReviewResult(
        status="needs_reextract",
        gaps=["Missing milestone dates"],
        risks=[],
        reextract_sources=["brief:milestones"],
        supplement_guidance=None,
    )
    assert result.needs_action is True


# ── Phase 1: New PlanState fields and snapshot extensions ──


class TestPlanStateNewFields:
    """Tests for 3a/3b/3c fields on PlanState."""

    def test_new_fields_default_to_empty(self) -> None:
        state = PlanState()
        assert state.extraction_confidence == {}
        assert state.extraction_confidence_chunks == {}
        assert state.extraction_confidence_missing == {}
        assert state.extraction_consistency == {}
        assert state.extraction_candidates is None
        assert state.leaf_output_tokens == {}
        assert state.uncertainty_scores == {}

    def test_confidence_fields_are_mutable(self) -> None:
        state = PlanState()
        state.extraction_confidence["sec-1"] = {"spec": 0.85}
        state.extraction_confidence_chunks["sec-1"] = {"spec": [0.85]}
        assert state.extraction_confidence["sec-1"]["spec"] == 0.85
        assert state.extraction_confidence_chunks["sec-1"]["spec"] == [0.85]

    def test_consistency_fields_are_mutable(self) -> None:
        state = PlanState()
        state.extraction_consistency["sec-1"] = {"spec": 0.9}
        assert state.extraction_consistency["sec-1"]["spec"] == 0.9

    def test_leaf_output_tokens_are_mutable(self) -> None:
        state = PlanState()
        state.leaf_output_tokens["sec-1"] = {"spec": [412, 380]}
        assert state.leaf_output_tokens["sec-1"]["spec"] == [412, 380]

    def test_uncertainty_scores_are_mutable(self) -> None:
        state = PlanState()
        state.uncertainty_scores["sec-1"] = {"spec": 0.83}
        assert state.uncertainty_scores["sec-1"]["spec"] == 0.83


class TestSnapshotConfidence:
    """Tests for the 'confidence' key in snapshot()."""

    def test_snapshot_confidence_empty(self) -> None:
        state = PlanState()
        snap = state.snapshot()
        assert "confidence" in snap
        assert snap["confidence"]["by_source"] == {}
        assert snap["confidence"]["by_section"] == {}
        assert snap["confidence"]["chunks"] == {}
        assert snap["confidence"]["missing"] == {}

    def test_snapshot_confidence_by_source(self) -> None:
        state = PlanState()
        state.extraction_confidence["sec-1"] = {"spec": 0.82, "drawings": 0.93}
        snap = state.snapshot()
        assert snap["confidence"]["by_source"]["sec-1"]["spec"] == 0.82
        assert snap["confidence"]["by_source"]["sec-1"]["drawings"] == 0.93

    def test_snapshot_confidence_by_section_derived(self) -> None:
        import pytest

        state = PlanState()
        state.extraction_confidence["sec-1"] = {"spec": 0.80, "drawings": 0.90}
        snap = state.snapshot()
        # by_section is mean of valid source confidences.
        assert snap["confidence"]["by_section"]["sec-1"] == pytest.approx(0.85)

    def test_snapshot_confidence_chunks(self) -> None:
        state = PlanState()
        state.extraction_confidence_chunks["sec-1"] = {"spec": [0.82, 0.75]}
        snap = state.snapshot()
        assert snap["confidence"]["chunks"]["sec-1"]["spec"] == [0.82, 0.75]

    def test_snapshot_confidence_missing(self) -> None:
        state = PlanState()
        state.extraction_confidence_missing["sec-1"] = {"spec": "missing_key"}
        snap = state.snapshot()
        assert snap["confidence"]["missing"]["sec-1"]["spec"] == "missing_key"


class TestSnapshotUncertainty:
    """Tests for the 'uncertainty' key in snapshot()."""

    def test_snapshot_uncertainty_empty(self) -> None:
        state = PlanState()
        snap = state.snapshot()
        assert "uncertainty" in snap
        assert snap["uncertainty"]["scoring_active"] is False
        assert snap["uncertainty"]["leaf_output_tokens"] == {}
        assert snap["uncertainty"]["scores"] == {}
        assert snap["uncertainty"]["population_stats"] == {
            "mean": 0.0,
            "stdev": 0.0,
            "n": 0,
        }

    def test_snapshot_uncertainty_with_tokens(self) -> None:
        state = PlanState()
        state.leaf_output_tokens["sec-1"] = {"spec": [412, 380]}
        snap = state.snapshot()
        assert snap["uncertainty"]["leaf_output_tokens"]["sec-1"]["spec"] == [412, 380]

    def test_snapshot_uncertainty_with_scores(self) -> None:
        state = PlanState()
        state._uncertainty_scoring_active = True
        state.uncertainty_scores["sec-1"] = {"spec": 0.83}
        state._uncertainty_population_stats = {"mean": 396.0, "stdev": 168.0, "n": 38}
        snap = state.snapshot()
        assert snap["uncertainty"]["scores"]["sec-1"]["spec"] == 0.83
        assert snap["uncertainty"]["scoring_active"] is True
        assert snap["uncertainty"]["population_stats"] == {
            "mean": 396.0,
            "stdev": 168.0,
            "n": 38,
        }


class TestSnapshotConsistency:
    """Tests for the 'consistency' key in snapshot()."""

    def test_snapshot_consistency_empty(self) -> None:
        state = PlanState()
        snap = state.snapshot()
        assert "consistency" in snap
        assert snap["consistency"] == {}

    def test_snapshot_consistency_populated(self) -> None:
        state = PlanState()
        state.extraction_consistency["sec-1"] = {"spec": 0.9, "drawings": 0.67}
        snap = state.snapshot()
        assert snap["consistency"]["sec-1"]["spec"] == 0.9
        assert snap["consistency"]["sec-1"]["drawings"] == 0.67


class TestSnapshotJsonSerializable:
    """Snapshot must remain fully JSON-serializable after new fields."""

    def test_full_snapshot_serializes(self) -> None:
        state = PlanState()
        state.extractions["sec-1"] = {"spec": {"tank_count": 4}}
        state.sections["sec-1"] = "Some content."
        state.extraction_confidence["sec-1"] = {"spec": 0.82}
        state.extraction_confidence_chunks["sec-1"] = {"spec": [0.82]}
        state.extraction_confidence_missing["sec-2"] = {"spec": "missing_key"}
        state.extraction_consistency["sec-1"] = {"spec": 0.9}
        state.leaf_output_tokens["sec-1"] = {"spec": [412]}
        state.uncertainty_scores["sec-1"] = {"spec": 0.83}
        state.phase = "extract"
        state.llm_calls = 3
        state.tokens_used = 5000

        snap = state.snapshot()
        serialized = json.dumps(snap)
        assert isinstance(serialized, str)


def test_composition_op_from_generation_mode():
    assert CompositionOp.from_generation_mode("transform") == CompositionOp.MERGE_EXTRACTIONS
    assert CompositionOp.from_generation_mode("creative") == CompositionOp.COMBINE_ANALYSIS
    assert CompositionOp.from_generation_mode("guided") == CompositionOp.MERGE_EXTRACTIONS
    assert CompositionOp.from_generation_mode("boilerplate") == CompositionOp.CONCATENATE
    assert CompositionOp.from_generation_mode("external") == CompositionOp.SKIP


def test_plan_state_compose_scratchpad_defaults_empty():
    from aec_bench.adapters.lambda_rlm.state import PlanState

    state = PlanState()
    assert state.compose_scratchpad == {}


def test_plan_state_compose_scratchpad_accepts_writes():
    from aec_bench.adapters.lambda_rlm.state import PlanState

    state = PlanState()
    state.compose_scratchpad["project_name"] = "North Plant Casein Air Heater"
    state.compose_scratchpad["site"] = "North Plant"
    assert state.compose_scratchpad == {
        "project_name": "North Plant Casein Air Heater",
        "site": "North Plant",
    }


def test_plan_state_snapshot_includes_compose_scratchpad():
    from aec_bench.adapters.lambda_rlm.state import PlanState

    state = PlanState()
    state.compose_scratchpad["project_code"] = "D37806"
    snapshot = state.snapshot()
    assert "compose_scratchpad" in snapshot
    assert snapshot["compose_scratchpad"] == {"project_code": "D37806"}


def test_plan_state_compose_scratchpad_accepts_back_brief_dict_value():
    state = PlanState()
    state.compose_scratchpad["client"] = "Example Dairy"
    state.compose_scratchpad["_back_brief"] = {
        "services": "Pattern A; Pattern B",
        "exclusions": "Carve-out X; Carve-out Y",
    }
    snap = state.snapshot()
    assert snap["compose_scratchpad"]["client"] == "Example Dairy"
    assert snap["compose_scratchpad"]["_back_brief"] == {
        "services": "Pattern A; Pattern B",
        "exclusions": "Carve-out X; Carve-out Y",
    }


def test_plan_state_structure_retries_default_empty() -> None:
    state = PlanState()
    assert state.structure_retries == {}
    assert state.structure_unresolved == {}


def test_plan_state_snapshot_includes_structure_retries() -> None:
    state = PlanState()
    state.structure_retries["drawing_register"] = 1
    snap = state.snapshot()
    assert snap["structure_retries"] == {"drawing_register": 1}
    assert snap["structure_unresolved_count"] == 0


def test_plan_state_snapshot_counts_unresolved() -> None:
    from aec_bench.adapters.lambda_rlm.structure_validator import (
        FieldGap,
        StructureValidationResult,
    )

    state = PlanState()
    state.structure_unresolved["drawing_register"] = StructureValidationResult(
        section_id="drawing_register",
        passed=False,
        missing=(
            FieldGap(
                field_name="revision",
                dtype="str",
                kind="missing",
                locator="",
            ),
        ),
        malformed=(),
        validator_input_tokens=0,
        validator_output_tokens=0,
    )
    snap = state.snapshot()
    assert snap["structure_unresolved_count"] == 1
