# ABOUTME: Tests for the TrialRunner orchestration slice in aec-bench Python.
# ABOUTME: Covers one trial path from backend provisioning through transcript collection.

from dataclasses import dataclass
from pathlib import Path

from aec_bench.adapters.base import AdapterResult, SerializedAdapterExecution
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.trial_record import AdaptationProvenance, DerivationStepRecord
from aec_bench.harness.backend import (
    BackendExecutionRequest,
    BackendExecutionResult,
    CollectedArtifacts,
    TrialHandle,
)
from aec_bench.harness.execution_payload import ExecutionBundle
from aec_bench.harness.trial_runner import TrialRunner
from aec_bench.tasks.instance import resolve_instance_paths
from tests.support.task_factories import make_task_definition


@dataclass
class FakeBackend:
    launched: bool = False
    cleaned_up: bool = False
    last_execution_request: BackendExecutionRequest | None = None

    def build_environment(self, *, task_dir: Path) -> str:
        return f"image:{task_dir.name}"

    def launch_trial(self, *, image_ref: str, workspace_dir: Path) -> TrialHandle:
        self.launched = True
        return TrialHandle(backend_name="modal", handle_id=f"handle:{workspace_dir.name}")

    def collect_outputs(self, *, handle: TrialHandle) -> CollectedArtifacts:
        return CollectedArtifacts(
            output_path=Path("/workspace/output.jsonl"),
            verifier_reward_path=Path("/tmp/verifier/reward.json"),
            verifier_details_path=Path("/tmp/verifier/details.json"),
        )

    def execute_trial(
        self,
        *,
        handle: TrialHandle,
        request: BackendExecutionRequest,
    ) -> BackendExecutionResult:
        self.last_execution_request = request
        return BackendExecutionResult(
            adapter_result=_result_from_bundle(request.execution_bundle),
            collected_artifacts=self.collect_outputs(handle=handle),
        )

    def teardown(self, *, handle: TrialHandle) -> None:
        self.cleaned_up = True


@dataclass
class FakeAdapter:
    def serialize_execution(self) -> SerializedAdapterExecution:
        return SerializedAdapterExecution(
            adapter_kind="test-fixture",
            adapter_name="tool_loop",
            resolved_model="gpt-5.4-mini",
            payload={
                "configuration_record": {"model": "gpt-5.4-mini", "max_turns": 4},
                "assistant_content": '{"findings": []}',
                "raw_output_text": '{"findings": []}',
                "usage_input_tokens": 120,
                "usage_output_tokens": 40,
            },
        )

    def adapter_name(self) -> str:
        return "tool_loop"

    def resolved_model(self) -> str:
        return "gpt-5.4-mini"


def test_trial_runner_runs_one_trial_and_builds_record(tmp_path: Path) -> None:
    instance_dir = tmp_path / "task-instance"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "environment" / "Dockerfile").write_text(
        "FROM ubuntu:24.04\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    verifier_dir = Path("/tmp/verifier")
    verifier_dir.mkdir(parents=True, exist_ok=True)
    (verifier_dir / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (verifier_dir / "details.json").write_text('{"matched": 2}\n', encoding="utf-8")

    task = make_task_definition(
        instruction="Review the task and write findings to /workspace/output.jsonl.",
    )
    resolved = resolve_instance_paths(task, instance_dir)
    backend = FakeBackend()
    adapter = FakeAdapter()
    runner = TrialRunner(artifacts_dir=tmp_path / "artifacts")

    record = runner.run(
        trial_id="trial-001",
        experiment_id="experiment-001",
        task=resolved,
        task_revision="git-sha-task",
        backend=backend,
        adapter=adapter,
        runtime_image="ghcr.io/example/task-image:latest",
        adapter_revision="git-sha-adapter",
        tool_versions={"codes_search": "abc123"},
    )

    assert backend.launched is True
    assert backend.cleaned_up is True
    assert backend.last_execution_request is not None
    assert backend.last_execution_request.execution_bundle.request.output_path == "/workspace/output.jsonl"
    assert backend.last_execution_request.verifier_script == instance_dir / "tests" / "test.sh"
    assert record.evaluation.reward == 1.0
    assert record.outputs.conversation_path is not None
    conversation_path = Path(record.outputs.conversation_path)
    assert conversation_path.exists()
    assert '"role": "assistant"' in conversation_path.read_text(encoding="utf-8")


def test_trial_runner_preserves_adaptation_provenance(tmp_path: Path) -> None:
    instance_dir = tmp_path / "task-instance"
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "environment" / "Dockerfile").write_text(
        "FROM ubuntu:24.04\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")

    verifier_dir = Path("/tmp/verifier")
    verifier_dir.mkdir(parents=True, exist_ok=True)
    (verifier_dir / "reward.json").write_text('{"reward": 1.0}\n', encoding="utf-8")
    (verifier_dir / "details.json").write_text('{"matched": 2}\n', encoding="utf-8")

    task = make_task_definition(
        instruction="Review the task and write findings to /workspace/output.jsonl.",
    )
    resolved = resolve_instance_paths(task, instance_dir)
    backend = FakeBackend()
    adapter = FakeAdapter()
    runner = TrialRunner(artifacts_dir=tmp_path / "artifacts")

    record = runner.run(
        trial_id="trial-002",
        experiment_id="experiment-001",
        task=resolved,
        task_revision="git-sha-task",
        backend=backend,
        adapter=adapter,
        runtime_image="ghcr.io/example/task-image:latest",
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
    )

    assert record.adaptation is not None
    assert record.adaptation.variation_key == "city=perth"


def _result_from_bundle(bundle: ExecutionBundle) -> AdapterResult:
    payload = bundle.execution.payload
    return AdapterResult(
        adapter_name=bundle.execution.adapter_name,
        resolved_model=bundle.execution.resolved_model,
        configuration_record=payload["configuration_record"],
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path=bundle.request.output_path,
            output_format=bundle.request.output_format,
        ),
        transcript=[
            TranscriptEntry(role=TranscriptRole.USER, content=bundle.request.instruction),
            TranscriptEntry(role=TranscriptRole.ASSISTANT, content=payload["assistant_content"]),
        ],
        raw_output_text=payload["raw_output_text"],
        usage_input_tokens=payload["usage_input_tokens"],
        usage_output_tokens=payload["usage_output_tokens"],
    )
