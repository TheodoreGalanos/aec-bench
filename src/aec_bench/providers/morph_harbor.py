# ABOUTME: Harbor BaseEnvironment adapter backed by Morph Cloud instances.
# ABOUTME: Translates Harbor async environment calls into Morph provider operations.

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Protocol, TypeVar

from harbor.environments.base import BaseEnvironment, ExecResult  # type: ignore[import-untyped]
from harbor.models.environment_type import EnvironmentType  # type: ignore[import-untyped]
from harbor.models.task.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.harness.runtime_dependencies import RUNTIME_PYTHON_PACKAGES
from aec_bench.providers.morph_cloud import (
    MorphCloudOperations,
    MorphCommandResult,
    extract_archive,
)

REMOTE_WORKSPACE_DIR = "/workspace"
REMOTE_LOGS_DIR = "/logs"
REMOTE_TESTS_DIR = "/tests"
MORPH_MIN_DISK_SIZE_MB = 8192
PROJECT_SRC_DIR = Path(__file__).resolve().parents[1]
ProvisionedT = TypeVar("ProvisionedT")


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

    def start_trial_container(
        self,
        *,
        instance: object,
        workspace_dir: str,
        logs_dir: str,
        tests_dir: str,
    ) -> None: ...

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

    def scrub_trial_instance(self, *, instance: object) -> None: ...

    def delete_snapshot(self, *, snapshot: object) -> None: ...


@dataclass
class MorphHarborState:
    snapshot: object
    instance: object


async def _run_provisioning_call(
    operation: Callable[[], ProvisionedT],
    *,
    label: str,
    cancel_cleanup: Callable[[ProvisionedT | None], Awaitable[list[Exception]]],
) -> ProvisionedT:
    """Resolve a provider thread and reclaim any late resource before propagating cancellation."""

    worker = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancellation:
        result: ProvisionedT | None = None
        failures: list[Exception] = []
        try:
            result = await worker
        except Exception as error:
            failures.append(error)
        try:
            failures.extend(await cancel_cleanup(result))
        except Exception as error:
            failures.append(error)
        if failures:
            raise BaseExceptionGroup(
                f"Morph Harbor {label} was cancelled and cleanup failed",
                [cancellation, *failures],
            ) from cancellation
        raise


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
            disk_size_mb=max(task_env_config.storage_mb, MORPH_MIN_DISK_SIZE_MB),
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
        return True

    @property
    def _environment_definition_path(self) -> Path:
        return Path(self.environment_dir) / "Dockerfile"

    def _validate_definition(self) -> None:
        if not self._environment_definition_path.exists():
            msg = f"{self._environment_definition_path} not found. Please ensure the file exists."
            raise FileNotFoundError(msg)

    async def start(self, force_build: bool) -> None:
        del force_build

        async def cleanup_cancelled_snapshot(snapshot: object | None) -> list[Exception]:
            if snapshot is None:
                return []
            return await self._delete_snapshot_errors(snapshot)

        snapshot = await _run_provisioning_call(
            partial(
                self._operations.build_runtime_snapshot,
                dockerfile_path=self._environment_definition_path,
                context_dir=self.environment_dir,
                project_src_dir=self._project_src_dir,
                runtime_packages=self._runtime_packages,
            ),
            label="runtime snapshot build",
            cancel_cleanup=cleanup_cancelled_snapshot,
        )
        instance: object | None = None
        try:

            async def cleanup_cancelled_instance(instance: object | None) -> list[Exception]:
                if instance is None:
                    return await self._delete_snapshot_errors(snapshot)
                return await self._teardown_errors(
                    MorphHarborState(snapshot=snapshot, instance=instance),
                    delete=True,
                )

            instance = await _run_provisioning_call(
                partial(self._operations.start_instance, snapshot=snapshot),
                label="instance start",
                cancel_cleanup=cleanup_cancelled_instance,
            )
            state = MorphHarborState(snapshot=snapshot, instance=instance)

            async def cleanup_cancelled_container(_: None) -> list[Exception]:
                return await self._teardown_errors(state, delete=True)

            await _run_provisioning_call(
                partial(
                    self._operations.start_trial_container,
                    instance=instance,
                    workspace_dir=REMOTE_WORKSPACE_DIR,
                    logs_dir=REMOTE_LOGS_DIR,
                    tests_dir=REMOTE_TESTS_DIR,
                ),
                label="trial-container start",
                cancel_cleanup=cleanup_cancelled_container,
            )
            self._state = state

            async def cleanup_cancelled_initialization(_: MorphCommandResult | None) -> list[Exception]:
                self._state = None
                return await self._teardown_errors(state, delete=True)

            await _run_provisioning_call(
                partial(
                    self._operations.run_container_command_result,
                    instance=instance,
                    command=("bash", "-lc", "mkdir -p /logs/agent /logs/verifier /logs/artifacts /workspace"),
                ),
                label="trial-container initialization",
                cancel_cleanup=cleanup_cancelled_initialization,
            )
        except Exception as error:
            self._state = None
            if instance is None:
                cleanup_errors = await self._delete_snapshot_errors(snapshot)
            else:
                cleanup_errors = await self._teardown_errors(
                    MorphHarborState(snapshot=snapshot, instance=instance),
                    delete=True,
                )
            if cleanup_errors:
                raise ExceptionGroup("Morph Harbor start and rollback failed", [error, *cleanup_errors]) from error
            raise

    async def stop(self, delete: bool) -> None:
        if self._state is None:
            return
        state = self._state
        self._state = None
        teardown = asyncio.create_task(self._teardown_errors(state, delete=delete))
        try:
            errors = await asyncio.shield(teardown)
        except asyncio.CancelledError as cancellation:
            failures: list[Exception] = []
            try:
                failures.extend(await teardown)
            except Exception as error:
                failures.append(error)
            if failures:
                raise BaseExceptionGroup(
                    "Morph Harbor teardown was cancelled and cleanup failed",
                    [cancellation, *failures],
                ) from cancellation
            raise
        if errors:
            raise ExceptionGroup("Morph Harbor teardown failed", errors)

    async def _teardown_errors(
        self,
        state: MorphHarborState,
        *,
        delete: bool,
    ) -> list[Exception]:
        errors: list[Exception] = []
        if delete:
            try:
                await asyncio.to_thread(self._operations.scrub_trial_instance, instance=state.instance)
            except Exception as error:
                errors.append(error)
        try:
            await asyncio.to_thread(self._operations.stop_instance, instance=state.instance)
        except Exception as error:
            errors.append(error)
        if delete:
            errors.extend(await self._delete_snapshot_errors(state.snapshot))
        return errors

    async def _delete_snapshot_errors(self, snapshot: object) -> list[Exception]:
        try:
            await asyncio.to_thread(self._operations.delete_snapshot, snapshot=snapshot)
        except Exception as error:
            return [error]
        return []

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
