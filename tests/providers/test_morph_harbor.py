# ABOUTME: Tests for the Morph-backed Harbor environment adapter.
# ABOUTME: Verifies Harbor BaseEnvironment methods delegate to Morph provider operations.

from __future__ import annotations

import asyncio
import io
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from harbor.models.task.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.contracts.execution_environment import RUNTIME_PYTHON_PACKAGES
from aec_bench.providers.morph_cloud import MorphCloudOperations, MorphCommandResult
from aec_bench.providers.morph_harbor import MORPH_HARBOR_ENVIRONMENT_BINDING, MorphHarborEnvironment


def test_morph_harbor_implements_the_neutral_environment_binding() -> None:
    assert MORPH_HARBOR_ENVIRONMENT_BINDING.backend == "morph"
    assert MORPH_HARBOR_ENVIRONMENT_BINDING.import_path == ("aec_bench.providers.morph_harbor:MorphHarborEnvironment")
    assert MORPH_HARBOR_ENVIRONMENT_BINDING.kwargs == {"compute_backend": "morph"}


def test_morph_runtime_packages_are_exactly_pinned_to_the_kernel_environment() -> None:
    assert RUNTIME_PYTHON_PACKAGES == (
        "pydantic==2.11.10",
        "pydantic-ai[anthropic,bedrock,openai]==1.60.0",
        "boto3==1.42.73",
        "botocore==1.42.73",
        "httpx==0.28.1",
        "PyYAML==6.0.3",
        "polars==1.39.0",
    )


def test_morph_harbor_environment_starts_runtime_snapshot(tmp_path: Path) -> None:
    environment_dir = _write_environment(tmp_path)
    operations = FakeMorphHarborOperations()
    env = MorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
        project_src_dir=tmp_path / "src" / "aec_bench",
    )

    _run(env.start(force_build=False))

    assert operations.builds[0]["dockerfile_path"] == environment_dir / "Dockerfile"
    assert operations.builds[0]["context_dir"] == environment_dir
    assert operations.builds[0]["runtime_packages"] == RUNTIME_PYTHON_PACKAGES
    assert operations.started_snapshots == [operations.snapshot]
    assert operations.started_containers == [
        {
            "instance": operations.instance,
            "workspace_dir": "/workspace",
            "logs_dir": "/logs",
            "tests_dir": "/tests",
        }
    ]


def test_morph_harbor_environment_accepts_disabled_internet(tmp_path: Path) -> None:
    environment = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="pump-station",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(allow_internet=False),
        operations=FakeMorphHarborOperations(),
    )

    assert environment.can_disable_internet is True


@pytest.mark.parametrize(
    ("requested_storage_mb", "expected_disk_size_mb"),
    ((5120, 8192), (10240, 10240)),
)
def test_morph_harbor_environment_satisfies_provider_disk_minimum(
    tmp_path: Path,
    requested_storage_mb: int,
    expected_disk_size_mb: int,
) -> None:
    environment = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(storage_mb=requested_storage_mb),
    )

    assert isinstance(environment._operations, MorphCloudOperations)
    assert environment._operations.disk_size_mb == expected_disk_size_mb


def test_morph_harbor_environment_exec_returns_harbor_exec_result(tmp_path: Path) -> None:
    environment_dir = _write_environment(tmp_path)
    operations = FakeMorphHarborOperations()
    env = MorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    _run(env.start(force_build=False))

    result = _run(env.exec("python3 --version", cwd="/workspace", env={"ABC": "123"}, timeout_sec=30))

    assert result.return_code == 7
    assert result.stdout == "hello\n"
    assert result.stderr == "warn\n"
    assert operations.commands[-1] == {
        "instance": operations.instance,
        "command": ("bash", "-lc", "python3 --version"),
        "workdir": "/workspace",
        "env": {"ABC": "123"},
        "timeout_seconds": 30,
    }


def test_morph_harbor_environment_uploads_and_downloads_files(tmp_path: Path) -> None:
    environment_dir = _write_environment(tmp_path)
    operations = FakeMorphHarborOperations(files={"/workspace/output.md": b"answer\n"})
    env = MorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    local_file = tmp_path / "payload.txt"
    local_file.write_text("payload\n", encoding="utf-8")
    target_file = tmp_path / "downloaded.md"
    _run(env.start(force_build=False))

    _run(env.upload_file(local_file, "/workspace/payload.txt"))
    _run(env.upload_dir(environment_dir.parent, "/workspace"))
    _run(env.download_file("/workspace/output.md", target_file))

    assert operations.writes[0] == {
        "instance": operations.instance,
        "remote_path": "/workspace/payload.txt",
        "content": b"payload\n",
    }
    assert operations.uploads[0] == {
        "instance": operations.instance,
        "local_path": environment_dir.parent,
        "remote_path": "/workspace",
    }
    assert target_file.read_bytes() == b"answer\n"


def test_morph_harbor_environment_downloads_directories(tmp_path: Path) -> None:
    environment_dir = _write_environment(tmp_path)
    operations = FakeMorphHarborOperations(directories={"/logs/agent": _archive_bytes({"output.md": b"answer\n"})})
    env = MorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    target_dir = tmp_path / "agent"
    _run(env.start(force_build=False))

    _run(env.download_dir("/logs/agent", target_dir))

    assert (target_dir / "output.md").read_bytes() == b"answer\n"


def test_morph_harbor_environment_stop_tears_down_instance(tmp_path: Path) -> None:
    environment_dir = _write_environment(tmp_path)
    operations = FakeMorphHarborOperations()
    env = MorphHarborEnvironment(
        environment_dir=environment_dir,
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    _run(env.start(force_build=False))

    _run(env.stop(delete=True))

    assert operations.scrubbed_instances == [operations.instance]
    assert operations.stopped_instances == [operations.instance]
    assert operations.deleted_snapshots == [operations.snapshot]


def test_morph_harbor_environment_stop_without_delete_retains_runtime_snapshot(tmp_path: Path) -> None:
    operations = FakeMorphHarborOperations()
    env = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    _run(env.start(force_build=False))

    _run(env.stop(delete=False))

    assert operations.teardown_events == ["stop"]
    assert operations.deleted_snapshots == []


@pytest.mark.parametrize("failing_step", ("scrub", "stop", "delete"))
def test_morph_harbor_environment_attempts_all_teardown_steps_after_failure(
    tmp_path: Path,
    failing_step: str,
) -> None:
    operations = FakeMorphHarborOperations(fail_teardown_step=failing_step)
    env = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    _run(env.start(force_build=False))

    with pytest.raises(ExceptionGroup, match="Morph Harbor teardown failed"):
        _run(env.stop(delete=True))

    assert operations.teardown_events == ["scrub", "stop", "delete"]


def test_morph_harbor_environment_deletes_snapshot_when_instance_start_fails(tmp_path: Path) -> None:
    operations = FakeMorphHarborOperations(fail_start_instance=True)
    env = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )

    with pytest.raises(RuntimeError, match="simulated instance start failure"):
        _run(env.start(force_build=False))

    assert operations.deleted_snapshots == [operations.snapshot]


def test_morph_harbor_environment_disposes_instance_when_container_start_fails(tmp_path: Path) -> None:
    operations = FakeMorphHarborOperations(fail_start_container=True)
    env = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )

    with pytest.raises(RuntimeError, match="simulated container start failure"):
        _run(env.start(force_build=False))

    assert operations.teardown_events == ["scrub", "stop", "delete"]


@pytest.mark.parametrize(
    ("blocked_step", "expected_teardown_events"),
    (
        ("build", ["delete"]),
        ("instance", ["scrub", "stop", "delete"]),
        ("container", ["scrub", "stop", "delete"]),
        ("initialize", ["scrub", "stop", "delete"]),
    ),
)
def test_morph_harbor_environment_reclaims_resources_created_after_start_cancellation(
    tmp_path: Path,
    blocked_step: str,
    expected_teardown_events: list[str],
) -> None:
    operations = FakeMorphHarborOperations(block_start_step=blocked_step)
    env = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )

    async def cancel_blocked_start() -> None:
        start_task = asyncio.create_task(env.start(force_build=False))
        assert await asyncio.to_thread(operations.start_step_blocked.wait, 5.0)
        start_task.cancel()
        operations.release_start_step.set()
        with pytest.raises(asyncio.CancelledError):
            await start_task

    _run(cancel_blocked_start())

    assert operations.teardown_events == expected_teardown_events
    assert operations.deleted_snapshots == [operations.snapshot]
    assert env._state is None


@pytest.mark.parametrize("blocked_step", ("scrub", "stop"))
def test_morph_harbor_environment_finishes_teardown_before_propagating_cancellation(
    tmp_path: Path,
    blocked_step: str,
) -> None:
    operations = FakeMorphHarborOperations(block_teardown_step=blocked_step)
    env = MorphHarborEnvironment(
        environment_dir=_write_environment(tmp_path),
        environment_name="heat-load-alpha",
        session_id="trial-001",
        trial_paths=TrialPaths(tmp_path / "trial"),
        task_env_config=_environment_config(),
        operations=operations,
    )
    _run(env.start(force_build=False))

    async def cancel_blocked_stop() -> None:
        stop_task = asyncio.create_task(env.stop(delete=True))
        assert await asyncio.to_thread(operations.teardown_step_blocked.wait, 5.0)
        stop_task.cancel()
        operations.release_teardown_step.set()
        with pytest.raises(asyncio.CancelledError):
            await stop_task

    _run(cancel_blocked_stop())

    assert operations.teardown_events == ["scrub", "stop", "delete"]
    assert operations.deleted_snapshots == [operations.snapshot]
    assert env._state is None


def _write_environment(tmp_path: Path) -> Path:
    task_dir = tmp_path / "task"
    environment_dir = task_dir / "environment"
    environment_dir.mkdir(parents=True)
    (environment_dir / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    return environment_dir


def _environment_config(
    *,
    storage_mb: int = 10240,
    allow_internet: bool = True,
) -> EnvironmentConfig:
    return EnvironmentConfig.model_construct(
        build_timeout_sec=600.0,
        docker_image=None,
        cpus=1,
        memory_mb=2048,
        storage_mb=storage_mb,
        gpus=0,
        gpu_types=None,
        allow_internet=allow_internet,
        mcp_servers=[],
        memory=None,
        storage=None,
    )


def _run(coro: Any) -> Any:
    return asyncio.run(coro)


def _archive_bytes(files: dict[str, bytes]) -> bytes:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        for name, content in sorted(files.items()):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return payload.getvalue()


@dataclass(frozen=True)
class FakeMorphObject:
    id: str


@dataclass
class FakeMorphHarborOperations:
    files: dict[str, bytes] = field(default_factory=dict)
    directories: dict[str, bytes] = field(default_factory=dict)
    snapshot: FakeMorphObject = field(default_factory=lambda: FakeMorphObject(id="snapshot-001"))
    instance: FakeMorphObject = field(default_factory=lambda: FakeMorphObject(id="instance-001"))
    builds: list[dict[str, Any]] = field(default_factory=list)
    started_snapshots: list[object] = field(default_factory=list)
    started_containers: list[dict[str, Any]] = field(default_factory=list)
    commands: list[dict[str, Any]] = field(default_factory=list)
    writes: list[dict[str, Any]] = field(default_factory=list)
    uploads: list[dict[str, Any]] = field(default_factory=list)
    scrubbed_instances: list[object] = field(default_factory=list)
    stopped_instances: list[object] = field(default_factory=list)
    deleted_snapshots: list[object] = field(default_factory=list)
    teardown_events: list[str] = field(default_factory=list)
    fail_teardown_step: str | None = None
    fail_start_instance: bool = False
    fail_start_container: bool = False
    block_start_step: str | None = None
    start_step_blocked: Event = field(default_factory=Event)
    release_start_step: Event = field(default_factory=Event)
    block_teardown_step: str | None = None
    teardown_step_blocked: Event = field(default_factory=Event)
    release_teardown_step: Event = field(default_factory=Event)

    def _block_start(self, step: str) -> None:
        if self.block_start_step != step:
            return
        self.start_step_blocked.set()
        if not self.release_start_step.wait(5.0):
            raise RuntimeError(f"timed out waiting to release simulated {step} start")

    def _block_teardown(self, step: str) -> None:
        if self.block_teardown_step != step:
            return
        self.teardown_step_blocked.set()
        if not self.release_teardown_step.wait(5.0):
            raise RuntimeError(f"timed out waiting to release simulated {step} teardown")

    def build_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        project_src_dir: Path,
        runtime_packages: tuple[str, ...],
    ) -> object:
        self.builds.append(
            {
                "dockerfile_path": dockerfile_path,
                "context_dir": context_dir,
                "project_src_dir": project_src_dir,
                "runtime_packages": runtime_packages,
            }
        )
        self._block_start("build")
        return self.snapshot

    def start_instance(self, *, snapshot: object) -> object:
        self.started_snapshots.append(snapshot)
        self._block_start("instance")
        if self.fail_start_instance:
            raise RuntimeError("simulated instance start failure")
        return self.instance

    def start_trial_container(
        self,
        *,
        instance: object,
        workspace_dir: str,
        logs_dir: str,
        tests_dir: str,
    ) -> None:
        self._block_start("container")
        if self.fail_start_container:
            raise RuntimeError("simulated container start failure")
        self.started_containers.append(
            {
                "instance": instance,
                "workspace_dir": workspace_dir,
                "logs_dir": logs_dir,
                "tests_dir": tests_dir,
            }
        )

    def run_container_command_result(
        self,
        *,
        instance: object,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> MorphCommandResult:
        self._block_start("initialize")
        self.commands.append(
            {
                "instance": instance,
                "command": command,
                "workdir": workdir,
                "env": env,
                "timeout_seconds": timeout_seconds,
            }
        )
        return MorphCommandResult(exit_code=7, stdout="hello\n", stderr="warn\n")

    def write_instance_file(self, *, instance: object, remote_path: str, content: bytes) -> None:
        self.writes.append({"instance": instance, "remote_path": remote_path, "content": content})

    def upload_directory(self, *, instance: object, local_path: Path, remote_path: str) -> None:
        self.uploads.append({"instance": instance, "local_path": local_path, "remote_path": remote_path})

    def read_container_file(self, *, instance: object, remote_path: str) -> bytes | None:
        del instance
        return self.files.get(remote_path)

    def read_container_directory_archive(self, *, instance: object, remote_path: str) -> bytes | None:
        del instance
        return self.directories.get(remote_path)

    def stop_instance(self, *, instance: object) -> None:
        self.teardown_events.append("stop")
        self.stopped_instances.append(instance)
        self._block_teardown("stop")
        if self.fail_teardown_step == "stop":
            raise RuntimeError("simulated stop failure")

    def scrub_trial_instance(self, *, instance: object) -> None:
        self.teardown_events.append("scrub")
        self.scrubbed_instances.append(instance)
        self._block_teardown("scrub")
        if self.fail_teardown_step == "scrub":
            raise RuntimeError("simulated scrub failure")

    def delete_snapshot(self, *, snapshot: object) -> None:
        self.teardown_events.append("delete")
        self.deleted_snapshots.append(snapshot)
        if self.fail_teardown_step == "delete":
            raise RuntimeError("simulated snapshot delete failure")
