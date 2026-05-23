# ABOUTME: Tests for the harness compute-backend contract in aec-bench Python.
# ABOUTME: Covers a backend-neutral interface for launch, collection, and teardown.

from dataclasses import dataclass
from pathlib import Path

from aec_bench.adapters.base import AdapterResult, SerializedAdapterExecution
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.backend import (
    BackendExecutionRequest,
    BackendExecutionResult,
    CollectedArtifacts,
    ComputeBackend,
    TrialHandle,
)
from aec_bench.harness.execution_payload import AdapterRequestPayload, ExecutionBundle


@dataclass
class FakeBackend:
    launched: bool = False
    cleaned_up: bool = False

    def build_environment(self, *, task_dir: Path) -> str:
        return f"image-for:{task_dir.name}"

    def launch_trial(self, *, image_ref: str, workspace_dir: Path) -> TrialHandle:
        self.launched = True
        return TrialHandle(backend_name="fake", handle_id=f"trial:{image_ref}")

    def collect_outputs(self, *, handle: TrialHandle) -> CollectedArtifacts:
        return CollectedArtifacts(
            output_path=Path("/workspace/output.jsonl"),
            conversation_path=Path("/workspace/conversation.jsonl"),
        )

    def execute_trial(
        self,
        *,
        handle: TrialHandle,
        request: BackendExecutionRequest,
    ) -> BackendExecutionResult:
        return BackendExecutionResult(
            adapter_result=_result_from_bundle(request.execution_bundle),
            collected_artifacts=self.collect_outputs(handle=handle),
        )

    def teardown(self, *, handle: TrialHandle) -> None:
        self.cleaned_up = True


def test_fake_backend_satisfies_compute_backend_protocol(tmp_path: Path) -> None:
    backend: ComputeBackend = FakeBackend()

    image_ref = backend.build_environment(task_dir=tmp_path)
    handle = backend.launch_trial(image_ref=image_ref, workspace_dir=tmp_path)
    execution = backend.execute_trial(
        handle=handle,
        request=BackendExecutionRequest(
            execution_bundle=ExecutionBundle(
                execution=SerializedAdapterExecution(
                    adapter_kind="test-fixture",
                    adapter_name="fake",
                    resolved_model="gpt-5.4",
                    payload={"raw_output_text": '{"ok": true}'},
                ),
                request=AdapterRequestPayload(
                    instruction="Solve the task.",
                    system_prompt=None,
                    tools=[],
                    configuration={},
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
            ),
            verifier_script=tmp_path / "tests" / "test.sh",
        ),
    )
    artifacts = backend.collect_outputs(handle=handle)
    backend.teardown(handle=handle)

    assert image_ref == f"image-for:{tmp_path.name}"
    assert handle.backend_name == "fake"
    assert execution.adapter_result.raw_output_text == '{"ok": true}'
    assert artifacts.output_path == Path("/workspace/output.jsonl")


def _result_from_bundle(bundle: ExecutionBundle) -> AdapterResult:
    return AdapterResult(
        adapter_name=bundle.execution.adapter_name,
        resolved_model=bundle.execution.resolved_model,
        configuration_record={},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path=bundle.request.output_path,
            output_format=bundle.request.output_format,
        ),
        transcript=[TranscriptEntry(role=TranscriptRole.USER, content=bundle.request.instruction)],
        raw_output_text=bundle.execution.payload["raw_output_text"],
    )
