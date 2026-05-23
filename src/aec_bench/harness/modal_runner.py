# ABOUTME: Concrete Modal sandbox runner for harness execution in aec-bench Python.
# ABOUTME: Stages a task workspace into Modal volumes, launches a sandbox,
# ABOUTME: and collects artifacts back to local storage.

# DEPRECATED: Direct Modal SDK integration. Evolution uses this for tighter control,
# but production runs should go through Harbor. Will be migrated to Harbor dispatch
# in a future pass. See memory: project_local_sandbox_environments.md

import asyncio
import inspect
from collections.abc import Coroutine
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, TypeVar, cast
from uuid import uuid4

import modal

from aec_bench.adapters.base import SerializedClientSpec
from aec_bench.adapters.direct_providers import required_env_values_for_client_spec
from aec_bench.harness.backend import (
    BackendExecutionRequest,
    BackendExecutionResult,
    CollectedArtifacts,
    TrialHandle,
)
from aec_bench.harness.execution_payload import (
    read_execution_result,
    write_execution_bundle,
)

REMOTE_WORKSPACE_DIR = "/workspace"
REMOTE_LOGS_DIR = "/logs/verifier"
REMOTE_AEC_BENCH_DIR = "/workspace/.aec-bench"
REMOTE_EXECUTION_BUNDLE_PATH = f"{REMOTE_AEC_BENCH_DIR}/execution-bundle.json"
REMOTE_EXECUTION_RESULT_PATH = f"{REMOTE_AEC_BENCH_DIR}/adapter-result.json"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_PYTHON_PACKAGES = (
    "httpx>=0.28,<0.29",
    "polars>=1.30,<2",
    "pydantic>=2.11,<2.12",
    "PyYAML>=6.0,<7",
)


class ModalOperations(Protocol):
    def create_image(self, *, dockerfile_path: Path, context_dir: Path) -> object: ...

    def create_ephemeral_volume(self) -> object: ...

    def upload_directory(self, *, volume: object, local_path: Path, remote_path: str) -> None: ...

    def write_sandbox_file(self, *, sandbox: Any, remote_path: str, content: bytes) -> None: ...

    def create_sandbox(
        self,
        *,
        image: object,
        workspace_volume: object,
        logs_volume: object,
        workspace_dir: str,
    ) -> Any: ...

    def run_sandbox_command(
        self,
        *,
        sandbox: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None: ...

    def read_sandbox_file(self, *, sandbox: Any, remote_path: str) -> bytes | None: ...

    def terminate_sandbox(self, *, sandbox: Any) -> None: ...


@dataclass
class ModalSession:
    image: object
    sandbox: Any
    workspace_volume: object
    logs_volume: object
    workspace_dir: Path
    execution_request: BackendExecutionRequest | None = None


@dataclass
class ModalSandboxRunner:
    operations: ModalOperations
    artifacts_dir: Path

    def __post_init__(self) -> None:
        self._images: dict[str, object] = {}
        self._sessions: dict[str, ModalSession] = {}

    def build_environment(self, *, task_dir: Path) -> str:
        dockerfile_path = task_dir / "environment" / "Dockerfile"
        image = self.operations.create_image(
            dockerfile_path=dockerfile_path,
            context_dir=task_dir,
        )
        image_ref = f"modal-image:{uuid4()}"
        self._images[image_ref] = image
        return image_ref

    def launch_trial(self, *, image_ref: str, workspace_dir: Path) -> TrialHandle:
        image = self._images[image_ref]
        workspace_volume = self.operations.create_ephemeral_volume()
        logs_volume = self.operations.create_ephemeral_volume()
        self.operations.upload_directory(
            volume=workspace_volume,
            local_path=workspace_dir,
            remote_path="/",
        )
        sandbox = self.operations.create_sandbox(
            image=image,
            workspace_volume=workspace_volume,
            logs_volume=logs_volume,
            workspace_dir=REMOTE_WORKSPACE_DIR,
        )
        handle_id = str(sandbox.object_id)
        self._sessions[handle_id] = ModalSession(
            image=image,
            sandbox=sandbox,
            workspace_volume=workspace_volume,
            logs_volume=logs_volume,
            workspace_dir=workspace_dir,
        )
        return TrialHandle(backend_name="modal", handle_id=handle_id)

    def execute_trial(
        self,
        *,
        handle: TrialHandle,
        request: BackendExecutionRequest,
    ) -> BackendExecutionResult:
        handle_id = handle.handle_id
        session = self._sessions[handle_id]
        session.execution_request = request
        local_artifact_dir = self.artifacts_dir / handle_id
        local_artifact_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = write_execution_bundle(
            path=local_artifact_dir / "execution-bundle.json",
            bundle=request.execution_bundle,
        )
        self.operations.write_sandbox_file(
            sandbox=session.sandbox,
            remote_path=REMOTE_EXECUTION_BUNDLE_PATH,
            content=bundle_path.read_bytes(),
        )

        self.operations.run_sandbox_command(
            sandbox=session.sandbox,
            command=(
                "python",
                "-m",
                "aec_bench.harness.execution_entrypoint",
                "--bundle",
                REMOTE_EXECUTION_BUNDLE_PATH,
                "--result",
                REMOTE_EXECUTION_RESULT_PATH,
            ),
            workdir=REMOTE_WORKSPACE_DIR,
            env=_execution_environment(request.execution_bundle),
        )

        result_path = self._read_artifact(
            sandbox=session.sandbox,
            remote_candidates=[REMOTE_EXECUTION_RESULT_PATH],
            local_artifact_dir=local_artifact_dir,
        )
        if result_path is None:
            msg = "missing adapter execution result artifact"
            raise FileNotFoundError(msg)
        adapter_result = read_execution_result(result_path)

        verifier_command = (
            "bash",
            _remote_workspace_path(
                workspace_dir=session.workspace_dir,
                local_path=request.verifier_script,
            ),
        )
        self.operations.run_sandbox_command(
            sandbox=session.sandbox,
            command=verifier_command,
            workdir=REMOTE_WORKSPACE_DIR,
            env=None,
        )

        return BackendExecutionResult(
            adapter_result=adapter_result,
            collected_artifacts=self.collect_outputs(handle=handle),
        )

    def collect_outputs(self, *, handle: TrialHandle) -> CollectedArtifacts:
        handle_id = handle.handle_id
        session = self._sessions[handle_id]
        local_artifact_dir = self.artifacts_dir / handle_id
        local_artifact_dir.mkdir(parents=True, exist_ok=True)

        output_candidates = ["/output.jsonl", "/output.md"]
        reward_candidates = ["/reward.json"]
        details_candidates = ["/details.json"]
        if session.execution_request is not None:
            output_candidates = [session.execution_request.execution_bundle.request.output_path]
            reward_candidates = [session.execution_request.verifier_reward_path]
            if session.execution_request.verifier_details_path is not None:
                details_candidates = [session.execution_request.verifier_details_path]
            else:
                details_candidates = []

        output_path = self._read_artifact(
            sandbox=session.sandbox,
            remote_candidates=output_candidates,
            local_artifact_dir=local_artifact_dir,
        )
        reward_path = self._read_artifact(
            sandbox=session.sandbox,
            remote_candidates=reward_candidates,
            local_artifact_dir=local_artifact_dir,
        )
        details_path = self._read_artifact(
            sandbox=session.sandbox,
            remote_candidates=details_candidates,
            local_artifact_dir=local_artifact_dir,
        )

        return CollectedArtifacts(
            output_path=output_path,
            verifier_reward_path=reward_path,
            verifier_details_path=details_path,
        )

    def teardown(self, *, handle: TrialHandle) -> None:
        session = self._sessions.pop(handle.handle_id)
        self.operations.terminate_sandbox(sandbox=session.sandbox)

    def _read_artifact(
        self,
        *,
        sandbox: Any,
        remote_candidates: list[str],
        local_artifact_dir: Path,
    ) -> Path | None:
        for remote_path in remote_candidates:
            content = self.operations.read_sandbox_file(
                sandbox=sandbox,
                remote_path=remote_path,
            )
            if content is None:
                continue
            local_path = local_artifact_dir / Path(remote_path).name
            local_path.write_bytes(content)
            return local_path
        return None


@dataclass(frozen=True)
class ModalSdkOperations:
    app_name: str = "aec-bench-modal-runner"
    sandbox_timeout_seconds: int = 900
    sandbox_idle_timeout_seconds: int = 300

    def create_image(self, *, dockerfile_path: Path, context_dir: Path) -> object:
        return (
            modal.Image.from_dockerfile(
                dockerfile_path,
                context_dir=context_dir,
                add_python="3.13",
            )
            .pip_install(*RUNTIME_PYTHON_PACKAGES)
            .add_local_dir(
                PROJECT_ROOT / "src" / "aec_bench",
                "/opt/aec_bench/aec_bench",
                copy=True,
            )
            .env({"PYTHONPATH": "/opt/aec_bench"})
        )

    def create_ephemeral_volume(self) -> object:
        return _run_async(_create_ephemeral_volume())

    def upload_directory(self, *, volume: object, local_path: Path, remote_path: str) -> None:
        _run_async(_upload_directory(volume=volume, local_path=local_path, remote_path=remote_path))

    def write_sandbox_file(self, *, sandbox: Any, remote_path: str, content: bytes) -> None:
        _write_sandbox_file(sandbox=sandbox, remote_path=remote_path, content=content)

    def create_sandbox(
        self,
        *,
        image: object,
        workspace_volume: object,
        logs_volume: object,
        workspace_dir: str,
    ) -> Any:
        modal_app = modal.App.lookup(self.app_name, create_if_missing=True)
        modal_image = cast(modal.Image, image)
        workspace_modal_volume = cast(modal.Volume, workspace_volume)
        logs_modal_volume = cast(modal.Volume, logs_volume)
        return modal.Sandbox.create(
            "sleep",
            "infinity",
            app=modal_app,
            image=modal_image,
            volumes={
                REMOTE_WORKSPACE_DIR: workspace_modal_volume,
                REMOTE_LOGS_DIR: logs_modal_volume,
            },
            workdir=workspace_dir,
            timeout=self.sandbox_timeout_seconds,
            idle_timeout=self.sandbox_idle_timeout_seconds,
        )

    def read_sandbox_file(self, *, sandbox: Any, remote_path: str) -> bytes | None:
        return _read_sandbox_file(sandbox=sandbox, remote_path=remote_path)

    def run_sandbox_command(
        self,
        *,
        sandbox: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        process = sandbox.exec(*command, workdir=workdir, env=env)
        _wait_for_sandbox_process(process)

    def terminate_sandbox(self, *, sandbox: Any) -> None:
        sandbox.terminate()


async def _create_ephemeral_volume() -> object:
    context_manager = modal.Volume.ephemeral()
    return await context_manager.__aenter__()


async def _upload_directory(*, volume: Any, local_path: Path, remote_path: str) -> None:
    context_manager = volume.batch_upload()
    uploader = await context_manager.__aenter__()
    try:
        uploader.put_directory(local_path, remote_path)
    finally:
        await context_manager.__aexit__(None, None, None)


def _write_sandbox_file(*, sandbox: Any, remote_path: str, content: bytes) -> None:
    parent_dir = str(Path(remote_path).parent)
    if parent_dir not in {"", ".", "/"}:
        process = sandbox.exec("mkdir", "-p", parent_dir)
        _wait_for_sandbox_process(process)
    with sandbox.open(remote_path, "wb") as file_handle:
        file_handle.write(content)


def _read_sandbox_file(*, sandbox: Any, remote_path: str) -> bytes | None:
    try:
        with sandbox.open(remote_path, "rb") as file_handle:
            return cast(bytes, file_handle.read())
    except (FileNotFoundError, OSError):
        return None


def _wait_for_sandbox_process(process: Any) -> None:
    wait_result = process.wait()
    if inspect.isawaitable(wait_result):
        _run_async(cast(Coroutine[Any, Any, Any], wait_result))
    return_code = cast(int | None, getattr(process, "returncode", None))
    if return_code not in {None, 0}:
        stdout = _read_process_stream(getattr(process, "stdout", None))
        stderr = _read_process_stream(getattr(process, "stderr", None))
        message = f"sandbox command failed with exit code {return_code}"
        if stderr:
            message = f"{message}\nstderr:\n{stderr}"
        if stdout:
            message = f"{message}\nstdout:\n{stdout}"
        raise RuntimeError(message)


def _read_process_stream(stream: Any) -> str:
    if stream is None:
        return ""
    read_result = stream.read()
    if inspect.isawaitable(read_result):
        read_result = _run_async(cast(Coroutine[Any, Any, Any], read_result))
    if isinstance(read_result, bytes):
        return read_result.decode("utf-8", errors="replace")
    return cast(str, read_result or "")


ResultType = TypeVar("ResultType")


def _run_async(coroutine: Coroutine[Any, Any, ResultType]) -> ResultType:
    return asyncio.run(coroutine)


def _remote_workspace_path(*, workspace_dir: Path, local_path: Path) -> str:
    relative_path = local_path.relative_to(workspace_dir)
    return f"{REMOTE_WORKSPACE_DIR}/{relative_path.as_posix()}"


def _execution_environment(bundle: object) -> dict[str, str] | None:
    from aec_bench.harness.execution_payload import ExecutionBundle

    execution_bundle = cast(ExecutionBundle, bundle)
    client_payload = cast(dict[str, Any], execution_bundle.execution.payload.get("client", {}))
    if not client_payload:
        return None
    spec = SerializedClientSpec(
        client_kind=cast(str, client_payload["client_kind"]),
        payload=cast(dict[str, Any], client_payload.get("payload", {})),
    )
    env = required_env_values_for_client_spec(spec)
    return env or None
