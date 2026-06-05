# ABOUTME: Harbor BaseEnvironment adapter backed by Morph Cloud instances.
# ABOUTME: Translates Harbor async environment calls into Morph provider operations.

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from harbor.environments.base import BaseEnvironment, ExecResult  # type: ignore[import-untyped]
from harbor.models.environment_type import EnvironmentType  # type: ignore[import-untyped]
from harbor.models.task.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.providers.morph_cloud import (
    MorphCloudOperations,
    MorphCommandResult,
    extract_archive,
)

REMOTE_WORKSPACE_DIR = "/workspace"
REMOTE_LOGS_DIR = "/logs"
PROJECT_SRC_DIR = Path(__file__).resolve().parents[1]
RUNTIME_PYTHON_PACKAGES = (
    "pydantic>=2.11",
    "pydantic-ai[anthropic,openai]",
    "httpx>=0.28",
    "PyYAML>=6.0",
    "polars>=1.30,<2",
)


class MorphHarborOperations(Protocol):
    def build_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        project_src_dir: Path,
        runtime_packages: tuple[str, ...],
    ) -> object: ...

    def start_instance(self, *, snapshot: object) -> object: ...

    def start_trial_container(self, *, instance: object, workspace_dir: str, logs_dir: str) -> None: ...

    def run_container_command_result(
        self,
        *,
        instance: object,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> MorphCommandResult: ...

    def write_instance_file(self, *, instance: object, remote_path: str, content: bytes) -> None: ...

    def upload_directory(self, *, instance: object, local_path: Path, remote_path: str) -> None: ...

    def read_container_file(self, *, instance: object, remote_path: str) -> bytes | None: ...

    def read_container_directory_archive(self, *, instance: object, remote_path: str) -> bytes | None: ...

    def stop_instance(self, *, instance: object) -> None: ...


@dataclass
class MorphHarborState:
    snapshot: object
    instance: object


class MorphHarborEnvironment(BaseEnvironment):  # type: ignore[misc]
    def __init__(
        self,
        environment_dir: Path,
        environment_name: str,
        session_id: str,
        trial_paths: TrialPaths,
        task_env_config: EnvironmentConfig,
        *,
        compute_backend: str = "morph",
        operations: MorphHarborOperations | None = None,
        project_src_dir: Path = PROJECT_SRC_DIR,
        runtime_packages: tuple[str, ...] = RUNTIME_PYTHON_PACKAGES,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            environment_dir=environment_dir,
            environment_name=environment_name,
            session_id=session_id,
            trial_paths=trial_paths,
            task_env_config=task_env_config,
            **kwargs,
        )
        self.compute_backend = compute_backend
        self._operations = operations or MorphCloudOperations(
            vcpus=task_env_config.cpus,
            memory_mb=task_env_config.memory_mb,
            disk_size_mb=task_env_config.storage_mb,
        )
        self._project_src_dir = project_src_dir
        self._runtime_packages = runtime_packages
        self._state: MorphHarborState | None = None

    @staticmethod
    def type() -> EnvironmentType:
        return EnvironmentType.DOCKER

    @property
    def is_mounted(self) -> bool:
        return False

    @property
    def supports_gpus(self) -> bool:
        return False

    @property
    def can_disable_internet(self) -> bool:
        return False

    @property
    def _environment_definition_path(self) -> Path:
        return Path(self.environment_dir) / "Dockerfile"

    def _validate_definition(self) -> None:
        if not self._environment_definition_path.exists():
            msg = f"{self._environment_definition_path} not found. Please ensure the file exists."
            raise FileNotFoundError(msg)

    async def start(self, force_build: bool) -> None:
        del force_build
        snapshot = await asyncio.to_thread(
            self._operations.build_runtime_snapshot,
            dockerfile_path=self._environment_definition_path,
            context_dir=self.environment_dir.parent,
            project_src_dir=self._project_src_dir,
            runtime_packages=self._runtime_packages,
        )
        instance = await asyncio.to_thread(self._operations.start_instance, snapshot=snapshot)
        await asyncio.to_thread(
            self._operations.start_trial_container,
            instance=instance,
            workspace_dir=REMOTE_WORKSPACE_DIR,
            logs_dir=REMOTE_LOGS_DIR,
        )
        self._state = MorphHarborState(snapshot=snapshot, instance=instance)
        await self.exec("mkdir -p /logs/agent /logs/verifier /logs/artifacts /workspace")

    async def stop(self, delete: bool) -> None:
        del delete
        if self._state is None:
            return
        await asyncio.to_thread(self._operations.stop_instance, instance=self._state.instance)
        self._state = None

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        source = Path(source_path)
        await asyncio.to_thread(
            self._operations.write_instance_file,
            instance=self._require_instance(),
            remote_path=target_path,
            content=source.read_bytes(),
        )

    async def upload_dir(self, source_dir: Path | str, target_dir: str) -> None:
        await asyncio.to_thread(
            self._operations.upload_directory,
            instance=self._require_instance(),
            local_path=Path(source_dir),
            remote_path=target_dir,
        )

    async def download_file(self, source_path: str, target_path: Path | str) -> None:
        content = await asyncio.to_thread(
            self._operations.read_container_file,
            instance=self._require_instance(),
            remote_path=source_path,
        )
        if content is None:
            msg = f"file not found in Morph environment: {source_path}"
            raise FileNotFoundError(msg)
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    async def download_dir(self, source_dir: str, target_dir: Path | str) -> None:
        archive = await asyncio.to_thread(
            self._operations.read_container_directory_archive,
            instance=self._require_instance(),
            remote_path=source_dir,
        )
        if archive is None:
            msg = f"directory not found in Morph environment: {source_dir}"
            raise FileNotFoundError(msg)
        extract_archive(archive_bytes=archive, target_dir=Path(target_dir))

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> ExecResult:
        result = await asyncio.to_thread(
            self._operations.run_container_command_result,
            instance=self._require_instance(),
            command=("bash", "-lc", command),
            workdir=cwd,
            env=env,
            timeout_seconds=timeout_sec,
        )
        return ExecResult(
            stdout=result.stdout,
            stderr=result.stderr,
            return_code=result.exit_code,
        )

    def _require_instance(self) -> object:
        if self._state is None:
            msg = "Morph Harbor environment has not been started"
            raise RuntimeError(msg)
        return self._state.instance
