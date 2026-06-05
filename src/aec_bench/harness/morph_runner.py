# ABOUTME: Morph Cloud compute-backend orchestration for aec-bench trials.
# ABOUTME: Keeps task execution flow backend-neutral while provider code owns Morph transport details.

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

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
from aec_bench.providers.morph_cloud import morph_object_id

REMOTE_WORKSPACE_DIR = "/workspace"
REMOTE_LOGS_DIR = "/logs/verifier"
REMOTE_AEC_BENCH_DIR = "/workspace/.aec-bench"
REMOTE_EXECUTION_BUNDLE_PATH = f"{REMOTE_AEC_BENCH_DIR}/execution-bundle.json"
REMOTE_EXECUTION_RESULT_PATH = f"{REMOTE_AEC_BENCH_DIR}/adapter-result.json"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROJECT_SRC_DIR = PROJECT_ROOT / "src" / "aec_bench"
RUNTIME_PYTHON_PACKAGES = (
    "httpx>=0.28,<0.29",
    "polars>=1.30,<2",
    "pydantic>=2.11,<2.12",
    "PyYAML>=6.0,<7",
)


class MorphOperations(Protocol):
    def build_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        project_src_dir: Path,
        runtime_packages: tuple[str, ...],
    ) -> object: ...

    def start_instance(self, *, snapshot: object) -> Any: ...

    def upload_directory(self, *, instance: Any, local_path: Path, remote_path: str) -> None: ...

    def start_trial_container(self, *, instance: Any, workspace_dir: str, logs_dir: str) -> None: ...

    def write_instance_file(self, *, instance: Any, remote_path: str, content: bytes) -> None: ...

    def run_container_command(
        self,
        *,
        instance: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None: ...

    def read_container_file(self, *, instance: Any, remote_path: str) -> bytes | None: ...

    def stop_instance(self, *, instance: Any) -> None: ...


@dataclass
class MorphSession:
    snapshot: object
    instance: Any
    workspace_dir: Path
    execution_request: BackendExecutionRequest | None = None


@dataclass
class MorphSandboxRunner:
    operations: MorphOperations
    artifacts_dir: Path

    def __post_init__(self) -> None:
        self._snapshots: dict[str, object] = {}
        self._sessions: dict[str, MorphSession] = {}

    def build_environment(self, *, task_dir: Path) -> str:
        dockerfile_path = task_dir / "environment" / "Dockerfile"
        snapshot = self.operations.build_runtime_snapshot(
            dockerfile_path=dockerfile_path,
            context_dir=task_dir,
            project_src_dir=PROJECT_SRC_DIR,
            runtime_packages=RUNTIME_PYTHON_PACKAGES,
        )
        image_ref = f"morph-snapshot:{morph_object_id(snapshot)}"
        self._snapshots[image_ref] = snapshot
        return image_ref

    def launch_trial(self, *, image_ref: str, workspace_dir: Path) -> TrialHandle:
        snapshot = self._snapshots[image_ref]
        instance = self.operations.start_instance(snapshot=snapshot)
        self.operations.upload_directory(
            instance=instance,
            local_path=workspace_dir,
            remote_path=REMOTE_WORKSPACE_DIR,
        )
        self.operations.start_trial_container(
            instance=instance,
            workspace_dir=REMOTE_WORKSPACE_DIR,
            logs_dir=REMOTE_LOGS_DIR,
        )

        handle_id = morph_object_id(instance)
        self._sessions[handle_id] = MorphSession(
            snapshot=snapshot,
            instance=instance,
            workspace_dir=workspace_dir,
        )
        return TrialHandle(backend_name="morph", handle_id=handle_id)

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
        self.operations.write_instance_file(
            instance=session.instance,
            remote_path=REMOTE_EXECUTION_BUNDLE_PATH,
            content=bundle_path.read_bytes(),
        )

        self.operations.run_container_command(
            instance=session.instance,
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
            instance=session.instance,
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
        self.operations.run_container_command(
            instance=session.instance,
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
            instance=session.instance,
            remote_candidates=output_candidates,
            local_artifact_dir=local_artifact_dir,
        )
        reward_path = self._read_artifact(
            instance=session.instance,
            remote_candidates=reward_candidates,
            local_artifact_dir=local_artifact_dir,
        )
        details_path = self._read_artifact(
            instance=session.instance,
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
        self.operations.stop_instance(instance=session.instance)

    def _read_artifact(
        self,
        *,
        instance: Any,
        remote_candidates: list[str],
        local_artifact_dir: Path,
    ) -> Path | None:
        for remote_path in remote_candidates:
            content = self.operations.read_container_file(
                instance=instance,
                remote_path=remote_path,
            )
            if content is None:
                continue
            local_path = local_artifact_dir / Path(remote_path).name
            local_path.write_bytes(content)
            return local_path
        return None


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
