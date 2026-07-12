# ABOUTME: Tests for harness-side TrialRecord construction in aec-bench Python.
# ABOUTME: Covers mapping adapter results into append-only provenance records.

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest, AdapterResult
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    Completeness,
    DerivationStepRecord,
)
from aec_bench.harness.trial_record_builder import build_trial_record
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
        configuration_record={"model": "gpt-5.4-mini", "max_turns": 4},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=task.instruction)],
        raw_output_text='{"findings": []}',
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
        completeness=Completeness.PARTIAL,
    )

    assert record.agent.configuration == {"model": "gpt-5.4-mini", "max_turns": 4}
    assert record.task.visibility == task.visibility
    assert record.outputs.agent_result == {
        "failure_kind": None,
        "provider_error": None,
        "usage_input_tokens": 120,
        "usage_output_tokens": 40,
    }


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
        completeness=Completeness.PARTIAL,
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
        adaptation=AdaptationProvenance(
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
        ),
        completeness=Completeness.PARTIAL,
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
        completeness=Completeness.PARTIAL,
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
        completeness=Completeness.PARTIAL,
    )

    assert record.outputs.trajectory_path is None
