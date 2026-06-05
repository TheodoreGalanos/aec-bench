# ABOUTME: Tests for the Morph-backed Harbor environment adapter.
# ABOUTME: Verifies Harbor BaseEnvironment methods delegate to Morph provider operations.

from __future__ import annotations

import io
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from harbor.models.task.config import EnvironmentConfig  # type: ignore[import-untyped]
from harbor.models.trial.paths import TrialPaths  # type: ignore[import-untyped]

from aec_bench.providers.morph_cloud import MorphCommandResult
from aec_bench.providers.morph_harbor import MorphHarborEnvironment


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
    assert operations.builds[0]["context_dir"] == environment_dir.parent
    assert operations.started_snapshots == [operations.snapshot]
    assert operations.started_containers == [
        {"instance": operations.instance, "workspace_dir": "/workspace", "logs_dir": "/logs"}
    ]


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

    assert operations.stopped_instances == [operations.instance]


def _write_environment(tmp_path: Path) -> Path:
    task_dir = tmp_path / "task"
    environment_dir = task_dir / "environment"
    environment_dir.mkdir(parents=True)
    (environment_dir / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    return environment_dir


def _environment_config() -> EnvironmentConfig:
    return EnvironmentConfig.model_construct(
        build_timeout_sec=600.0,
        docker_image=None,
        cpus=1,
        memory_mb=2048,
        storage_mb=10240,
        gpus=0,
        gpu_types=None,
        allow_internet=True,
        mcp_servers=[],
        memory=None,
        storage=None,
    )


def _run(coro: Any) -> Any:
    import asyncio

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
    stopped_instances: list[object] = field(default_factory=list)

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
        return self.snapshot

    def start_instance(self, *, snapshot: object) -> object:
        self.started_snapshots.append(snapshot)
        return self.instance

    def start_trial_container(self, *, instance: object, workspace_dir: str, logs_dir: str) -> None:
        self.started_containers.append({"instance": instance, "workspace_dir": workspace_dir, "logs_dir": logs_dir})

    def run_container_command_result(
        self,
        *,
        instance: object,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> MorphCommandResult:
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
        self.stopped_instances.append(instance)
