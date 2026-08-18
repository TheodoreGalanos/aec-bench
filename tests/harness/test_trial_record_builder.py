# ABOUTME: Tests for harness-side TrialRecord construction in aec-bench Python.
# ABOUTME: Covers mapping adapter results into append-only provenance records.

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    OutputCompletionAssistance,
)
from aec_bench.contracts.adapter_execution import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    DerivationStepRecord,
)
from aec_bench.harness.trial_record_builder import build_trial_record
from tests.support.output_completion import make_output_commit_attestation
from tests.support.task_factories import make_task_definition


def test_build_trial_record_uses_adapter_configuration_record() -> None:
    task = make_task_definition()
    request = AdapterRequest(
        instruction=task.instruction,
        system_prompt="Use tools carefully.",
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
    )
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={
            "model": "gpt-5.4-mini",
            "max_turns": 4,
            "manifest_path": "/host/deepseek-evidence.json",
            "evidence_manifest_sha256": "a" * 64,
            "sdk_version": "0.1.0",
        },
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
        completion_reason=AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED,
        completion_assistance=OutputCompletionAssistance(
            contract_satisfied=True,
            reminder_sent=True,
            reminder_turn=3,
            explicit_final_turn=4,
        ),
        raw_output_text='{"findings": []}',
        usage_model_calls=4,
        usage_input_tokens=120,
        usage_output_tokens=40,
    )
    evaluation = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    record = build_trial_record(
        trial_id="trial-001",
        experiment_id="experiment-001",
        task=task,
        task_revision="git-sha-task",
        request=request,
        result=result,
        evaluation=evaluation,
        total_seconds=12.5,
        runtime_image="ghcr.io/example/task-image:latest",
        compute_backend="modal",
        adapter_revision="git-sha-adapter",
        tool_versions={"codes_search": "abc123"},
    )

    assert record.agent.configuration == {"model": "gpt-5.4-mini", "max_turns": 4}
    assert record.task.visibility == task.visibility
    assert record.outputs.agent_result == {
        "completion_reason": "output_contract_satisfied",
        "completion_assistance": {
            "contract_satisfied": True,
            "reminder_sent": True,
            "reminder_turn": 3,
            "explicit_final_turn": 4,
        },
        "completion_commit": None,
        "failure_kind": None,
        "provider_error": None,
    }
    assert record.outputs.terminated is True
    assert record.outputs.truncated is False
    assert record.outputs.final_reason == "output_contract_satisfied"
    assert record.cost is not None
    assert record.cost.model_calls == 4
    assert record.cost.tokens_in == 120
    assert record.cost.tokens_out == 40


def test_build_trial_record_preserves_output_commit_attestation() -> None:
    task = make_task_definition()
    attestation = make_output_commit_attestation()
    request = AdapterRequest(
        instruction=task.instruction,
        output_path=attestation.output_path,
        output_format="markdown",
    )
    result = AdapterResult(
        adapter_name="rlm",
        resolved_model="test-model",
        configuration_record={"output_completion_commit": True},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path=attestation.output_path,
            output_format="markdown",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
        completion_reason=AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED,
        completion_commit=attestation,
        turns_used=attestation.commit_turn,
        max_turns=32,
    )
    evaluation = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    record = build_trial_record(
        trial_id="trial-output-commit",
        experiment_id="experiment-output-commit",
        task=task,
        task_revision="git-sha-task",
        request=request,
        result=result,
        evaluation=evaluation,
        total_seconds=12.5,
        runtime_image="ghcr.io/example/task-image:latest",
        compute_backend="morph",
    )

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["completion_reason"] == "output_contract_committed"
    assert record.outputs.agent_result["completion_commit"] == attestation.model_dump(mode="json")


def test_build_trial_record_preserves_failure_kind() -> None:
    task = make_task_definition()
    request = AdapterRequest(
        instruction=task.instruction,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
    )
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={"model": "gpt-5.4-mini"},
        agent_output=AgentOutput(
            status=AgentOutputStatus.FAILED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
            error_message="provider timeout",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
        provider_error="provider timeout",
        failure_kind=AdapterFailureKind.TIMEOUT,
    )
    evaluation = EvaluationResult(
        reward=0.0,
        validity=ValidityCheck(
            output_parseable=False,
            schema_valid=False,
            verifier_completed=False,
            errors=["timeout"],
        ),
    )

    record = build_trial_record(
        trial_id="trial-002",
        experiment_id="experiment-001",
        task=task,
        task_revision="git-sha-task",
        request=request,
        result=result,
        evaluation=evaluation,
        total_seconds=3.0,
        runtime_image="ghcr.io/example/task-image:latest",
        compute_backend="modal",
    )

    assert record.outputs.agent_result is not None
    assert record.outputs.agent_result["failure_kind"] == "timeout"


def test_build_trial_record_preserves_adaptation_provenance() -> None:
    task = make_task_definition()
    request = AdapterRequest(
        instruction=task.instruction,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
    )
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={"model": "gpt-5.4-mini"},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
    )
    evaluation = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    record = build_trial_record(
        trial_id="trial-003",
        experiment_id="experiment-001",
        task=task,
        task_revision="git-sha-task",
        request=request,
        result=result,
        evaluation=evaluation,
        total_seconds=5.0,
        runtime_image="ghcr.io/example/task-image:latest",
        compute_backend="modal",
        extensions={
            "adaptation": AdaptationProvenance(
                family_id="heat-load-audit",
                seed_task_id="mechanical/heat-load/audit-office-building/sydney-8rm",
                variation_key="city=perth",
                variation={"city": "perth"},
                derivation_lineage=[
                    DerivationStepRecord(
                        axis="city",
                        parent_value="sydney",
                        value="perth",
                    )
                ],
            )
        },
    )

    assert record.adaptation is not None
    assert record.adaptation.variation == {"city": "perth"}


def test_build_trial_record_passes_trajectory_path_to_output_record() -> None:
    task = make_task_definition()
    request = AdapterRequest(
        instruction=task.instruction,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
    )
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={"model": "gpt-5.4-mini"},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
    )
    evaluation = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    record = build_trial_record(
        trial_id="trial-004",
        experiment_id="experiment-001",
        task=task,
        task_revision="git-sha-task",
        request=request,
        result=result,
        evaluation=evaluation,
        total_seconds=7.0,
        runtime_image="ghcr.io/example/task-image:latest",
        compute_backend="modal",
        trajectory_path="/artifacts/trial-004-trajectory.jsonl",
    )

    assert record.outputs.trajectory_path == "/artifacts/trial-004-trajectory.jsonl"


def test_build_trial_record_trajectory_path_defaults_to_none() -> None:
    task = make_task_definition()
    request = AdapterRequest(
        instruction=task.instruction,
        output_path="/workspace/output.jsonl",
        output_format="jsonl",
    )
    result = AdapterResult(
        adapter_name="tool_loop",
        resolved_model="gpt-5.4-mini",
        configuration_record={"model": "gpt-5.4-mini"},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
    )
    evaluation = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    record = build_trial_record(
        trial_id="trial-005",
        experiment_id="experiment-001",
        task=task,
        task_revision="git-sha-task",
        request=request,
        result=result,
        evaluation=evaluation,
        total_seconds=2.0,
        runtime_image="ghcr.io/example/task-image:latest",
        compute_backend="modal",
    )

    assert record.outputs.trajectory_path is None
