# ABOUTME: Tests for the concrete Modal runner in aec-bench Python.
# ABOUTME: Covers workspace staging, sandbox launch, and artifact collection via Modal operations.

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aec_bench.adapters.base import AdapterResult, SerializedAdapterExecution
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.backend import BackendExecutionRequest, TrialHandle
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    read_execution_bundle,
    write_execution_result,
)
from aec_bench.harness.modal_runner import ModalSandboxRunner


@dataclass
class FakeSandbox:
    object_id: str


@dataclass
class FakeModalOperations:
    images: list[tuple[Path, Path]] = field(default_factory=list)
    uploads: list[tuple[object, Path, str]] = field(default_factory=list)
    sandboxes: list[tuple[object, object, object, str]] = field(default_factory=list)
    sandbox_commands: list[tuple[str, tuple[str, ...], str | None, dict[str, str] | None]] = field(default_factory=list)
    terminated: list[str] = field(default_factory=list)
    file_contents: dict[tuple[object, str], bytes] = field(default_factory=dict)
    sandbox_file_contents: dict[tuple[str, str], bytes] = field(default_factory=dict)

    def create_image(self, *, dockerfile_path: Path, context_dir: Path) -> object:
        self.images.append((dockerfile_path, context_dir))
        return {"dockerfile_path": dockerfile_path, "context_dir": context_dir}

    def create_ephemeral_volume(self) -> object:
        return object()

    def upload_directory(self, *, volume: object, local_path: Path, remote_path: str) -> None:
        self.uploads.append((volume, local_path, remote_path))

    def write_sandbox_file(self, *, sandbox: Any, remote_path: str, content: bytes) -> None:
        self.sandbox_file_contents[(sandbox.object_id, remote_path)] = content

    def create_sandbox(
        self,
        *,
        image: object,
        workspace_volume: object,
        logs_volume: object,
        workspace_dir: str,
    ) -> Any:
        self.sandboxes.append((image, workspace_volume, logs_volume, workspace_dir))
        return FakeSandbox(object_id="sb-123")

    def read_sandbox_file(self, *, sandbox: Any, remote_path: str) -> bytes | None:
        return self.sandbox_file_contents.get((sandbox.object_id, remote_path))

    def run_sandbox_command(
        self,
        *,
        sandbox: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.sandbox_commands.append((sandbox.object_id, command, workdir, env))
        if command[:3] == ("python", "-m", "aec_bench.harness.execution_entrypoint"):
            bundle_path = command[4]
            result_path = command[6]
            bundle_file = Path("/tmp/fake-modal-bundle.json")
            bundle_file.parent.mkdir(parents=True, exist_ok=True)
            bundle_bytes = self.sandbox_file_contents[(sandbox.object_id, bundle_path)]
            bundle_file.write_bytes(bundle_bytes)
            bundle = read_execution_bundle(bundle_file)
            result = _result_from_bundle(bundle)
            result_file = Path("/tmp/fake-modal-result.json")
            write_execution_result(path=result_file, result=result)
            self.sandbox_file_contents[(sandbox.object_id, result_path)] = result_file.read_bytes()
            self.sandbox_file_contents[(sandbox.object_id, bundle.request.output_path)] = (
                result.raw_output_text or ""
            ).encode("utf-8")

    def terminate_sandbox(self, *, sandbox: Any) -> None:
        self.terminated.append(sandbox.object_id)


@dataclass
class FakeAdapter:
    def serialize_execution(self) -> SerializedAdapterExecution:
        return SerializedAdapterExecution(
            adapter_kind="test-fixture",
            adapter_name="tool_loop",
            resolved_model="gpt-5.4-mini",
            payload={
                "configuration_record": {"model": "gpt-5.4-mini"},
                "assistant_content": '{"findings": []}',
                "raw_output_text": '{"findings": []}\n',
            },
        )

    def adapter_name(self) -> str:
        return "tool_loop"

    def resolved_model(self) -> str:
        return "gpt-5.4-mini"


def test_modal_runner_builds_image_and_stages_workspace(tmp_path: Path) -> None:
    task_dir = tmp_path / "task-instance"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")
    operations = FakeModalOperations()
    runner = ModalSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    assert image_ref.startswith("modal-image:")
    assert operations.images == [(task_dir / "environment" / "Dockerfile", task_dir)]
    assert len(operations.uploads) == 1
    assert operations.uploads[0][1] == task_dir
    assert operations.uploads[0][2] == "/"
    assert isinstance(handle, TrialHandle)
    assert handle.handle_id == "sb-123"
    assert handle.backend_name == "modal"


def test_modal_runner_collects_workspace_and_verifier_artifacts(tmp_path: Path) -> None:
    task_dir = tmp_path / "task-instance"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")
    operations = FakeModalOperations()
    runner = ModalSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    sandbox = runner._sessions[handle.handle_id].sandbox
    operations.sandbox_file_contents[(sandbox.object_id, "/output.jsonl")] = b'{"findings": []}\n'
    operations.sandbox_file_contents[(sandbox.object_id, "/reward.json")] = b'{"reward": 1.0}\n'
    operations.sandbox_file_contents[(sandbox.object_id, "/details.json")] = b'{"matched": 2}\n'

    artifacts = runner.collect_outputs(handle=handle)
    runner.teardown(handle=handle)

    assert artifacts.output_path is not None
    assert artifacts.verifier_reward_path is not None
    assert artifacts.verifier_details_path is not None
    assert artifacts.output_path.read_text(encoding="utf-8") == '{"findings": []}\n'
    assert artifacts.verifier_reward_path.read_text(encoding="utf-8") == '{"reward": 1.0}\n'
    assert operations.terminated == ["sb-123"]


def test_modal_runner_executes_adapter_and_runs_verifier(tmp_path: Path) -> None:
    task_dir = tmp_path / "task-instance"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    operations = FakeModalOperations()
    runner = ModalSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")
    adapter = FakeAdapter()

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    sandbox = runner._sessions[handle.handle_id].sandbox
    operations.sandbox_file_contents[(sandbox.object_id, "/logs/verifier/reward.json")] = b'{"reward": 0.5}\n'
    operations.sandbox_file_contents[(sandbox.object_id, "/logs/verifier/details.json")] = b'{"matched": 1}\n'

    execution = runner.execute_trial(
        handle=handle,
        request=BackendExecutionRequest(
            execution_bundle=ExecutionBundle(
                execution=adapter.serialize_execution(),
                request=AdapterRequestPayload(
                    instruction="Review the task.",
                    system_prompt=None,
                    tools=[],
                    configuration={},
                    output_path="/workspace/output.jsonl",
                    output_format="jsonl",
                ),
            ),
            verifier_script=task_dir / "tests" / "test.sh",
        ),
    )

    assert operations.sandbox_file_contents[(sandbox.object_id, "/workspace/output.jsonl")] == b'{"findings": []}\n'
    assert execution.collected_artifacts.verifier_reward_path is not None
    assert operations.sandbox_commands == [
        (
            "sb-123",
            (
                "python",
                "-m",
                "aec_bench.harness.execution_entrypoint",
                "--bundle",
                "/workspace/.aec-bench/execution-bundle.json",
                "--result",
                "/workspace/.aec-bench/adapter-result.json",
            ),
            "/workspace",
            None,
        ),
        ("sb-123", ("bash", "/workspace/tests/test.sh"), "/workspace", None),
    ]


def test_modal_runner_passes_provider_env_to_entrypoint(tmp_path: Path, monkeypatch: Any) -> None:
    task_dir = tmp_path / "task-instance"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM ubuntu:24.04\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")
    operations = FakeModalOperations()
    runner = ModalSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    sandbox = runner._sessions[handle.handle_id].sandbox
    operations.sandbox_file_contents[(sandbox.object_id, "/logs/verifier/reward.json")] = b'{"reward": 1.0}\n'

    execution = runner.execute_trial(
        handle=handle,
        request=BackendExecutionRequest(
            execution_bundle=ExecutionBundle(
                execution=SerializedAdapterExecution(
                    adapter_kind="direct",
                    adapter_name="direct-anthropic",
                    resolved_model="claude-sonnet-4-20250514",
                    payload={
                        "client": {
                            "client_kind": "anthropic_api",
                            "payload": {
                                "api_key_env": "ANTHROPIC_API_KEY",
                                "max_tokens": 1024,
                            },
                        },
                        "configuration_record": {"model": "claude-sonnet-4-20250514"},
                        "assistant_content": "ok",
                        "raw_output_text": "ok",
                    },
                ),
                request=AdapterRequestPayload(
                    instruction="Review the task.",
                    system_prompt=None,
                    tools=[],
                    configuration={},
                    output_path="/workspace/output.md",
                    output_format="markdown",
                ),
            ),
            verifier_script=task_dir / "tests" / "test.sh",
        ),
    )

    assert execution.collected_artifacts.verifier_reward_path is not None
    assert operations.sandbox_commands[0][3] == {"ANTHROPIC_API_KEY": "secret-key"}


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
    )
