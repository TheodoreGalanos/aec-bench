# ABOUTME: Tests for the TrialRecord provenance contract in the aec-bench contracts package.
# ABOUTME: These tests define completeness rules and nested provenance requirements.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    AgentReference,
    Completeness,
    CostRecord,
    DerivationStepRecord,
    EnvironmentSnapshot,
    FileReference,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)


def build_trial_record(**overrides: object) -> TrialRecord:
    payload = {
        "trial_id": "trial-001",
        "experiment_id": "experiment-001",
        "timestamp": "2026-03-13T10:00:00Z",
        "task": TaskReference(
            task_id="electrical/voltage-drop/au-office-fitout",
            task_revision="git-sha-task",
        ),
        "agent": AgentReference(
            adapter="tool_loop",
            model="anthropic:claude-sonnet-4-20250514",
            adapter_revision="git-sha-adapter",
            configuration={"max_turns": 20},
        ),
        "environment": EnvironmentSnapshot(
            runtime_image="ghcr.io/example/task-image:latest",
            compute_backend="modal",
            tool_versions={"codes_search": "abc123"},
        ),
        "inputs": InputRecord(
            instruction="Review the task and write output.",
            system_prompt="Use tools carefully.",
            input_files=[
                FileReference(
                    path="/workspace/input/drawing.json",
                    hash="hash-123",
                    source="r2://bucket/drawing.json",
                )
            ],
        ),
        "outputs": OutputRecord(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path="/workspace/output.jsonl",
                output_format="jsonl",
            ),
            raw_output_path="/workspace/output.jsonl",
            conversation_path="/workspace/conversation.jsonl",
            agent_result={"completion_status": "completed"},
        ),
        "evaluation": EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        "timing": TimingRecord(total_seconds=12.0, agent_seconds=8.0),
        "completeness": Completeness.COMPLETE,
    }
    payload.update(overrides)
    return TrialRecord.model_validate(payload)


# --- Valid construction ---


def test_trial_record_accepts_complete_payload_with_required_provenance() -> None:
    record = build_trial_record()

    assert record.completeness is Completeness.COMPLETE
    assert record.agent.adapter_revision == "git-sha-adapter"


def test_trial_record_allows_partial_payload_without_full_replay_provenance() -> None:
    record = build_trial_record(
        agent={
            "adapter": "tool_loop",
            "model": "anthropic:claude-sonnet-4-20250514",
            "configuration": {"max_turns": 20},
        },
        environment={
            "runtime_image": "ghcr.io/example/task-image:latest",
            "compute_backend": "modal",
        },
        inputs={
            "instruction": "Review the task and write output.",
        },
        completeness=Completeness.PARTIAL,
    )

    assert record.completeness is Completeness.PARTIAL


def test_trial_record_accepts_with_cost_record() -> None:
    record = build_trial_record(
        cost=CostRecord(
            tokens_in=1500,
            tokens_out=800,
            estimated_cost_usd=0.012,
        )
    )

    assert record.cost is not None
    assert record.cost.tokens_in == 1500


def test_trial_record_accepts_none_cost() -> None:
    record = build_trial_record(cost=None)

    assert record.cost is None


def test_trial_record_defaults_dataset_id_to_none() -> None:
    record = build_trial_record()

    assert record.dataset_id is None


def test_trial_record_accepts_dataset_id() -> None:
    record = build_trial_record(dataset_id="my-suite@1.0.0")

    assert record.dataset_id == "my-suite@1.0.0"


# --- Completeness validation ---


def test_trial_record_rejects_complete_payload_missing_optional_provenance() -> None:
    with pytest.raises(ValidationError):
        build_trial_record(
            agent={
                "adapter": "tool_loop",
                "model": "anthropic:claude-sonnet-4-20250514",
                "configuration": {"max_turns": 20},
            }
        )


def test_trial_record_rejects_complete_missing_tool_versions() -> None:
    with pytest.raises(ValidationError, match="tool_versions"):
        build_trial_record(
            environment=EnvironmentSnapshot(
                runtime_image="ghcr.io/example/task-image:latest",
                compute_backend="modal",
            )
        )


def test_trial_record_rejects_complete_missing_input_files() -> None:
    with pytest.raises(ValidationError, match="input_files"):
        build_trial_record(
            inputs=InputRecord(instruction="Review the task."),
        )


# --- Adaptation provenance ---


def test_trial_record_accepts_adaptation_provenance() -> None:
    record = build_trial_record(
        adaptation=AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            variation_key="city=perth__building_type=mixed-use",
            variation={"city": "perth", "building_type": "mixed-use"},
            derivation_lineage=[
                DerivationStepRecord(
                    axis="city",
                    parent_value="sydney",
                    value="perth",
                ),
                DerivationStepRecord(
                    axis="building_type",
                    parent_value="office",
                    value="mixed-use",
                ),
            ],
        )
    )

    assert record.adaptation is not None
    assert record.adaptation.family_id == "heat-load-audit"
    assert record.adaptation.derivation_lineage[0].axis == "city"


def test_trial_record_rejects_inconsistent_adaptation_lineage() -> None:
    with pytest.raises(ValidationError):
        build_trial_record(
            adaptation={
                "family_id": "heat-load-audit",
                "seed_task_id": "mechanical/heat-load/audit-office-building/sydney-8rm",
                "variation_key": "city=perth",
                "variation": {"city": "perth"},
                "derivation_lineage": [
                    {
                        "axis": "building_type",
                        "parent_value": "office",
                        "value": "mixed-use",
                    }
                ],
            }
        )


def test_derivation_step_rejects_same_value_as_parent() -> None:
    with pytest.raises(ValidationError, match="must change"):
        DerivationStepRecord(axis="jurisdiction", parent_value="au", value="au")


def test_adaptation_provenance_rejects_duplicate_lineage_axes() -> None:
    with pytest.raises(ValidationError, match="unique"):
        AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            variation_key="city=perth",
            variation={"city": "perth"},
            derivation_lineage=[
                DerivationStepRecord(axis="city", parent_value="sydney", value="perth"),
                DerivationStepRecord(axis="city", parent_value="brisbane", value="perth"),
            ],
        )


def test_adaptation_provenance_rejects_empty_variation() -> None:
    with pytest.raises(ValidationError, match="must not be empty"):
        AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="task-001",
            variation_key="none",
            variation={},
        )


# --- Nested model isolation ---


def test_task_reference_rejects_blank_task_id() -> None:
    with pytest.raises(ValidationError):
        TaskReference(task_id="  ", task_revision="sha-abc")


def test_agent_reference_rejects_blank_adapter() -> None:
    with pytest.raises(ValidationError):
        AgentReference(adapter="", model="claude")


def test_environment_snapshot_rejects_blank_compute_backend() -> None:
    with pytest.raises(ValidationError):
        EnvironmentSnapshot(runtime_image="image:latest", compute_backend="  ")


def test_file_reference_rejects_blank_hash() -> None:
    with pytest.raises(ValidationError):
        FileReference(path="/workspace/file.json", hash="  ")


def test_input_record_rejects_blank_instruction() -> None:
    with pytest.raises(ValidationError):
        InputRecord(instruction="   ")


def test_output_record_accepts_all_none_fields() -> None:
    output = OutputRecord()

    assert output.agent_output is None
    assert output.raw_output_path is None


def test_timing_record_rejects_negative_total_seconds() -> None:
    with pytest.raises(ValidationError):
        TimingRecord(total_seconds=-1.0)


def test_cost_record_rejects_negative_tokens() -> None:
    with pytest.raises(ValidationError):
        CostRecord(tokens_in=-100)


# --- Round-trip serialization ---


def test_trial_record_roundtrip_serialization() -> None:
    original = build_trial_record()

    serialized = original.model_dump(mode="json")
    restored = TrialRecord.model_validate(serialized)

    assert restored == original
    assert restored.completeness is Completeness.COMPLETE
    assert restored.task.task_id == "electrical/voltage-drop/au-office-fitout"
    assert restored.agent.adapter_revision == "git-sha-adapter"


def test_trial_record_roundtrip_with_adaptation() -> None:
    original = build_trial_record(
        adaptation=AdaptationProvenance(
            family_id="heat-load-audit",
            seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
            variation_key="city=perth",
            variation={"city": "perth"},
            derivation_lineage=[DerivationStepRecord(axis="city", parent_value="sydney", value="perth")],
        ),
        cost=CostRecord(tokens_in=1000, tokens_out=500, estimated_cost_usd=0.01),
    )

    serialized = original.model_dump(mode="json")
    restored = TrialRecord.model_validate(serialized)

    assert restored == original
    assert restored.adaptation is not None
    assert restored.adaptation.derivation_lineage[0].value == "perth"
    assert restored.cost is not None
    assert restored.cost.tokens_in == 1000
