# ABOUTME: Tests for the Morph sandbox runner in aec-bench Python.
# ABOUTME: Covers runtime snapshot selection, workspace staging, execution, artifacts, and teardown.

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
from aec_bench.harness.morph_runner import (
    REMOTE_EXECUTION_BUNDLE_PATH,
    REMOTE_EXECUTION_RESULT_PATH,
    REMOTE_LOGS_DIR,
    REMOTE_WORKSPACE_DIR,
    MorphSandboxRunner,
)


@dataclass
class FakeMorphInstance:
    id: str


@dataclass
class FakeMorphOperations:
    snapshots: list[dict[str, Any]] = field(default_factory=list)
    uploads: list[tuple[str, Path, str]] = field(default_factory=list)
    containers: list[tuple[str, str, str]] = field(default_factory=list)
    commands: list[tuple[str, tuple[str, ...], str | None, dict[str, str] | None]] = field(default_factory=list)
    stopped: list[str] = field(default_factory=list)
    files: dict[tuple[str, str], bytes] = field(default_factory=dict)

    def build_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        project_src_dir: Path,
        runtime_packages: tuple[str, ...],
    ) -> object:
        snapshot = {
            "id": "snapshot-123",
            "dockerfile_path": dockerfile_path,
            "context_dir": context_dir,
            "project_src_dir": project_src_dir,
            "runtime_packages": runtime_packages,
        }
        self.snapshots.append(snapshot)
        return snapshot

    def start_instance(self, *, snapshot: object) -> Any:
        del snapshot
        return FakeMorphInstance(id="inst-123")

    def upload_directory(self, *, instance: Any, local_path: Path, remote_path: str) -> None:
        self.uploads.append((instance.id, local_path, remote_path))

    def start_trial_container(self, *, instance: Any, workspace_dir: str, logs_dir: str) -> None:
        self.containers.append((instance.id, workspace_dir, logs_dir))

    def write_instance_file(self, *, instance: Any, remote_path: str, content: bytes) -> None:
        self.files[(instance.id, remote_path)] = content

    def run_container_command(
        self,
        *,
        instance: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.commands.append((instance.id, command, workdir, env))
        if command[:3] == ("python", "-m", "aec_bench.harness.execution_entrypoint"):
            bundle_file = Path("/tmp/fake-morph-bundle.json")
            bundle_file.write_bytes(self.files[(instance.id, command[4])])
            bundle = read_execution_bundle(bundle_file)
            result_file = Path("/tmp/fake-morph-result.json")
            write_execution_result(path=result_file, result=_result_from_bundle(bundle))
            self.files[(instance.id, command[6])] = result_file.read_bytes()
            raw_output_text = bundle.execution.payload["raw_output_text"]
            self.files[(instance.id, bundle.request.output_path)] = raw_output_text.encode()

    def read_container_file(self, *, instance: Any, remote_path: str) -> bytes | None:
        return self.files.get((instance.id, remote_path))

    def stop_instance(self, *, instance: Any) -> None:
        self.stopped.append(instance.id)


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


def test_morph_runner_builds_snapshot_from_task_dockerfile(tmp_path: Path) -> None:
    task_dir = _task_dir(tmp_path)
    operations = FakeMorphOperations()
    runner = MorphSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")

    image_ref = runner.build_environment(task_dir=task_dir)

    assert image_ref == "morph-snapshot:snapshot-123"
    assert operations.snapshots[0]["dockerfile_path"] == task_dir / "environment" / "Dockerfile"
    assert operations.snapshots[0]["context_dir"] == task_dir
    assert operations.snapshots[0]["project_src_dir"].name == "aec_bench"
    assert "pydantic>=2.11,<2.12" in operations.snapshots[0]["runtime_packages"]


def test_morph_runner_launches_trial_and_stages_workspace(tmp_path: Path) -> None:
    task_dir = _task_dir(tmp_path)
    operations = FakeMorphOperations()
    runner = MorphSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    assert isinstance(handle, TrialHandle)
    assert handle.backend_name == "morph"
    assert handle.handle_id == "inst-123"
    assert operations.uploads == [("inst-123", task_dir, REMOTE_WORKSPACE_DIR)]
    assert operations.containers == [("inst-123", REMOTE_WORKSPACE_DIR, REMOTE_LOGS_DIR)]


def test_morph_runner_executes_adapter_verifier_and_collects_artifacts(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")
    task_dir = _task_dir(tmp_path)
    operations = FakeMorphOperations()
    runner = MorphSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")
    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    instance = runner._sessions[handle.handle_id].instance
    operations.files[(instance.id, "/logs/verifier/reward.json")] = b'{"reward": 1.0}\n'
    operations.files[(instance.id, "/logs/verifier/details.json")] = b'{"matched": 2}\n'

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
                        "assistant_content": '{"findings": []}',
                        "raw_output_text": '{"findings": []}\n',
                    },
                ),
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

    assert operations.files[(instance.id, REMOTE_EXECUTION_BUNDLE_PATH)]
    assert execution.adapter_result.raw_output_text == '{"findings": []}\n'
    assert execution.collected_artifacts.output_path is not None
    assert execution.collected_artifacts.verifier_reward_path is not None
    assert execution.collected_artifacts.verifier_details_path is not None
    assert operations.commands == [
        (
            "inst-123",
            (
                "python",
                "-m",
                "aec_bench.harness.execution_entrypoint",
                "--bundle",
                REMOTE_EXECUTION_BUNDLE_PATH,
                "--result",
                REMOTE_EXECUTION_RESULT_PATH,
            ),
            REMOTE_WORKSPACE_DIR,
            {"ANTHROPIC_API_KEY": "secret-key"},
        ),
        ("inst-123", ("bash", "/workspace/tests/test.sh"), REMOTE_WORKSPACE_DIR, None),
    ]


def test_morph_runner_tears_down_instance(tmp_path: Path) -> None:
    task_dir = _task_dir(tmp_path)
    operations = FakeMorphOperations()
    runner = MorphSandboxRunner(operations=operations, artifacts_dir=tmp_path / "artifacts")

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)
    runner.teardown(handle=handle)

    assert operations.stopped == ["inst-123"]


def _task_dir(tmp_path: Path) -> Path:
    task_dir = tmp_path / "task-instance"
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    return task_dir


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
