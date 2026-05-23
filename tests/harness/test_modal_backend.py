# ABOUTME: Tests that ModalSandboxRunner satisfies the ComputeBackend contract directly.
# ABOUTME: Covers delegation to injected ModalOperations while preserving the backend-neutral interface.

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.adapters.base import AdapterResult
from aec_bench.adapters.transcript import TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.harness.backend import (
    CollectedArtifacts,
    TrialHandle,
)
from aec_bench.harness.execution_payload import ExecutionBundle
from aec_bench.harness.modal_runner import ModalSandboxRunner


@dataclass
class FakeModalOperations:
    """Minimal stub for ModalOperations protocol."""

    built_images: dict[str, object] | None = None
    uploaded: list[tuple[object, Path, str]] | None = None
    written_files: list[tuple[Any, str, bytes]] | None = None
    sandbox_commands: list[tuple[Any, tuple[str, ...], str | None, dict[str, str] | None]] | None = None

    def __post_init__(self) -> None:
        self.built_images = {}
        self.uploaded = []
        self.written_files = []
        self.sandbox_commands = []

    def create_image(self, *, dockerfile_path: Path, context_dir: Path) -> object:
        image = f"image:{dockerfile_path.name}"
        return image

    def create_ephemeral_volume(self) -> object:
        return "ephemeral-vol"

    def upload_directory(self, *, volume: object, local_path: Path, remote_path: str) -> None:
        assert self.uploaded is not None
        self.uploaded.append((volume, local_path, remote_path))

    def write_sandbox_file(self, *, sandbox: Any, remote_path: str, content: bytes) -> None:
        assert self.written_files is not None
        self.written_files.append((sandbox, remote_path, content))

    def create_sandbox(
        self,
        *,
        image: object,
        workspace_volume: object,
        logs_volume: object,
        workspace_dir: str,
    ) -> Any:
        return _FakeSandbox()

    def run_sandbox_command(
        self,
        *,
        sandbox: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        assert self.sandbox_commands is not None
        self.sandbox_commands.append((sandbox, command, workdir, env))

    def read_sandbox_file(self, *, sandbox: Any, remote_path: str) -> bytes | None:
        # Return fake adapter result for the execution result path
        if "adapter-result" in remote_path:
            import json

            return json.dumps(
                {
                    "adapter_name": "tool_loop",
                    "resolved_model": "gpt-5.4-mini",
                    "configuration_record": {},
                    "agent_output": {
                        "status": "completed",
                        "output_path": "/workspace/output.jsonl",
                        "output_format": "jsonl",
                    },
                    "transcript": [],
                    "raw_output_text": '{"findings": []}',
                }
            ).encode()
        return None

    def terminate_sandbox(self, *, sandbox: Any) -> None:
        pass


class _FakeSandbox:
    object_id = "fake-sandbox-id"


def test_modal_sandbox_runner_satisfies_backend_contract(tmp_path: Path) -> None:
    operations = FakeModalOperations()
    runner = ModalSandboxRunner(operations=operations, artifacts_dir=tmp_path)
    task_dir = tmp_path / "task-instance"
    task_dir.mkdir()
    (task_dir / "environment").mkdir()
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "test.sh").write_text("#!/bin/bash\necho ok")

    image_ref = runner.build_environment(task_dir=task_dir)
    handle = runner.launch_trial(image_ref=image_ref, workspace_dir=task_dir)

    assert isinstance(handle, TrialHandle)
    assert handle.backend_name == "modal"
    assert handle.handle_id == "fake-sandbox-id"

    artifacts = runner.collect_outputs(handle=handle)
    assert isinstance(artifacts, CollectedArtifacts)

    runner.teardown(handle=handle)


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
