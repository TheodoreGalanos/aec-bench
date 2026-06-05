# ABOUTME: Tests for Morph Cloud provider operations in aec-bench Python.
# ABOUTME: Covers SDK command/upload adapters and build-snapshot cleanup behavior.

import io
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from aec_bench.providers.morph_cloud import (
    MorphCloudOperations,
    MorphCommandResult,
    extract_archive,
)


def test_morph_cloud_operations_runs_host_commands_through_instance_exec() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations(command_timeout_seconds=31)

    result = operations._run_host_command(instance, "echo ok")

    assert result == MorphCommandResult(exit_code=0, stdout="ok\n", stderr="")
    assert instance.commands == [("echo ok", 31)]


def test_morph_cloud_operations_uploads_files_through_instance_upload() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations()

    operations.write_instance_file(
        instance=instance,
        remote_path="/tmp/aec-bench-smoke/payload.txt",
        content=b"hello morph\n",
    )

    assert instance.commands == [("mkdir -p /tmp/aec-bench-smoke", 900)]
    assert len(instance.uploads) == 1
    local_path, remote_path, recursive, content = instance.uploads[0]
    assert remote_path == "/tmp/aec-bench-smoke/payload.txt"
    assert recursive is False
    assert Path(local_path).name
    assert content == b"hello morph\n"


def test_morph_cloud_operations_deletes_build_snapshot_after_runtime_snapshot(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    project_src_dir = tmp_path / "src" / "aec_bench"
    (task_dir / "environment").mkdir(parents=True)
    project_src_dir.mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (project_src_dir / "__init__.py").write_text("", encoding="utf-8")

    build_snapshot = FakeMorphSnapshot(id="snapshot-build")
    runtime_snapshot = FakeMorphSnapshot(id="snapshot-runtime")
    builder = FakeMorphInstance(id="morphvm-builder", runtime_snapshot=runtime_snapshot)
    client = FakeMorphClient(build_snapshot=build_snapshot, builder=builder)
    operations = RecordingMorphCloudOperations(client_factory=lambda: client)

    snapshot = operations.build_runtime_snapshot(
        dockerfile_path=task_dir / "environment" / "Dockerfile",
        context_dir=task_dir,
        project_src_dir=project_src_dir,
        runtime_packages=("pydantic>=2.11,<2.12",),
    )

    assert snapshot is runtime_snapshot
    assert builder.stopped is True
    assert build_snapshot.deleted is True
    assert client.started_snapshot_ids == ["snapshot-build"]
    assert builder.snapshot_metadata == {"aec-bench-role": "runtime"}
    assert operations.events[0] == "prepare:morphvm-builder"


def test_morph_cloud_operations_deletes_build_snapshot_when_builder_start_fails(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    project_src_dir = tmp_path / "src" / "aec_bench"
    (task_dir / "environment").mkdir(parents=True)
    project_src_dir.mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (project_src_dir / "__init__.py").write_text("", encoding="utf-8")

    build_snapshot = FakeMorphSnapshot(id="snapshot-build")
    client = FakeMorphClient(build_snapshot=build_snapshot, builder=FakeMorphInstance(), fail_start=True)
    operations = RecordingMorphCloudOperations(client_factory=lambda: client)

    with pytest.raises(RuntimeError, match="start failed"):
        operations.build_runtime_snapshot(
            dockerfile_path=task_dir / "environment" / "Dockerfile",
            context_dir=task_dir,
            project_src_dir=project_src_dir,
            runtime_packages=("pydantic>=2.11,<2.12",),
        )

    assert build_snapshot.deleted is True


def test_extract_archive_rejects_path_traversal(tmp_path: Path) -> None:
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode="w:gz") as archive:
        content = b"escape\n"
        member = tarfile.TarInfo("../escape.txt")
        member.size = len(content)
        archive.addfile(member, io.BytesIO(content))

    with pytest.raises(RuntimeError, match="unsafe archive member"):
        extract_archive(archive_bytes=payload.getvalue(), target_dir=tmp_path / "target")

    assert not (tmp_path / "escape.txt").exists()


@dataclass
class FakeMorphExecResponse:
    exit_code: int = 0
    stdout: str = "ok\n"
    stderr: str = ""


@dataclass
class FakeMorphSnapshot:
    id: str
    deleted: bool = False

    def delete(self) -> None:
        self.deleted = True


@dataclass
class FakeMorphInstance:
    id: str = "morphvm-test"
    runtime_snapshot: FakeMorphSnapshot | None = None
    commands: list[tuple[str, int | None]] = field(default_factory=list)
    uploads: list[tuple[str, str, bool, bytes]] = field(default_factory=list)
    stopped: bool = False
    snapshot_metadata: dict[str, str] | None = None

    def wait_until_ready(self) -> None:
        return None

    def exec(self, command: str, timeout: int | None = None) -> FakeMorphExecResponse:
        self.commands.append((command, timeout))
        return FakeMorphExecResponse()

    def upload(self, local_path: str, remote_path: str, recursive: bool = False) -> None:
        self.uploads.append((local_path, remote_path, recursive, Path(local_path).read_bytes()))

    def stop(self) -> None:
        self.stopped = True

    def snapshot(
        self,
        *,
        digest: str | None = None,
        metadata: dict[str, str] | None = None,
        ttl_seconds: int | None = None,
    ) -> FakeMorphSnapshot:
        del digest, ttl_seconds
        self.snapshot_metadata = metadata
        if self.runtime_snapshot is None:
            return FakeMorphSnapshot(id="snapshot-runtime")
        return self.runtime_snapshot


@dataclass
class FakeSnapshotApi:
    build_snapshot: FakeMorphSnapshot

    def create(self, **kwargs: object) -> FakeMorphSnapshot:
        del kwargs
        return self.build_snapshot


@dataclass
class FakeInstanceApi:
    builder: FakeMorphInstance
    started_snapshot_ids: list[str]
    fail_start: bool = False

    def start(self, *, snapshot_id: str, **kwargs: object) -> FakeMorphInstance:
        del kwargs
        self.started_snapshot_ids.append(snapshot_id)
        if self.fail_start:
            msg = "start failed"
            raise RuntimeError(msg)
        return self.builder


@dataclass
class FakeMorphClient:
    build_snapshot: FakeMorphSnapshot
    builder: FakeMorphInstance
    fail_start: bool = False
    started_snapshot_ids: list[str] = field(default_factory=list)

    @property
    def snapshots(self) -> FakeSnapshotApi:
        return FakeSnapshotApi(build_snapshot=self.build_snapshot)

    @property
    def instances(self) -> FakeInstanceApi:
        return FakeInstanceApi(
            builder=self.builder,
            started_snapshot_ids=self.started_snapshot_ids,
            fail_start=self.fail_start,
        )


@dataclass(frozen=True)
class RecordingMorphCloudOperations(MorphCloudOperations):
    events: list[str] = field(default_factory=list)

    def _prepare_docker_host(self, instance: Any) -> None:
        self.events.append(f"prepare:{instance.id}")

    def upload_directory(self, *, instance: Any, local_path: Path, remote_path: str) -> None:
        self.events.append(f"upload:{instance.id}:{local_path.name}:{remote_path}")

    def write_instance_file(self, *, instance: Any, remote_path: str, content: bytes) -> None:
        del content
        self.events.append(f"write:{instance.id}:{remote_path}")

    def _run_host_command(
        self,
        instance: Any,
        command: str,
        *,
        check: bool = True,
        command_timeout_seconds: int | None = None,
    ) -> MorphCommandResult:
        del check, command_timeout_seconds
        self.events.append(f"command:{instance.id}:{command}")
        return MorphCommandResult(exit_code=0, stdout="", stderr="")
