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
    _runtime_dockerfile,
    _write_directory_archive,
    extract_archive,
)


def test_morph_cloud_operations_runs_host_commands_through_instance_exec() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations(command_timeout_seconds=31)

    result = operations._run_host_command(instance, "echo ok")

    assert result == MorphCommandResult(exit_code=0, stdout="ok\n", stderr="")
    assert instance.commands == [("echo ok", 31)]


def test_morph_cloud_operations_returns_nonzero_container_result_to_harbor() -> None:
    class NonzeroMorphInstance(FakeMorphInstance):
        def exec(self, command: str, timeout: int | None = None) -> FakeMorphExecResponse:
            self.commands.append((command, timeout))
            return FakeMorphExecResponse(exit_code=2, stdout="", stderr="verification failed\n")

    instance = NonzeroMorphInstance()
    operations = MorphCloudOperations(command_timeout_seconds=31)

    result = operations.run_container_command_result(
        instance=instance,
        command=("bash", "-lc", "/tests/test.sh"),
    )

    assert result == MorphCommandResult(exit_code=2, stdout="", stderr="verification failed\n")


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


def test_morph_cloud_operations_mounts_harbor_verifier_tests() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations()

    operations.start_trial_container(
        instance=instance,
        workspace_dir="/workspace",
        logs_dir="/logs",
        tests_dir="/tests",
    )

    commands = [command for command, _timeout in instance.commands]
    assert commands[0] == "mkdir -p /workspace && mkdir -p /logs && mkdir -p /tests"
    assert "docker run --rm --volume /workspace:/aec-bench-host-workspace" in commands[2]
    assert "cp -a /workspace/. /aec-bench-host-workspace/" in commands[2]
    assert "--volume /tests:/tests" in commands[3]


def test_morph_runtime_dockerfile_installs_packages_in_virtual_environment() -> None:
    dockerfile = _runtime_dockerfile(runtime_packages=("pydantic==2.11.10",))

    assert "python3 -m venv /opt/aec-bench-venv" in dockerfile
    assert "/opt/aec-bench-venv/bin/python -m pip install --no-cache-dir pydantic==2.11.10" in dockerfile
    assert 'ENV PATH="/opt/aec-bench-venv/bin:$PATH"' in dockerfile
    assert "--break-system-packages" not in dockerfile


def test_morph_cloud_operations_keeps_container_secrets_out_of_remote_commands() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations(command_timeout_seconds=31)
    secret = "bedrock-secret-marker"

    result = operations.run_container_command_result(
        instance=instance,
        command=("python", "-V"),
        workdir="/workspace",
        env={"AWS_BEARER_TOKEN_BEDROCK": secret, "AWS_REGION": "ap-southeast-2"},
        timeout_seconds=29,
    )

    assert result == MorphCommandResult(exit_code=0, stdout="ok\n", stderr="")
    assert len(instance.uploads) == 1
    _local_path, remote_path, recursive, content = instance.uploads[0]
    assert remote_path.startswith("/tmp/aec-bench-container-env-")
    assert remote_path.endswith(".env")
    assert recursive is False
    assert content == (b"AWS_BEARER_TOKEN_BEDROCK=bedrock-secret-marker\nAWS_REGION=ap-southeast-2\n")
    commands = [command for command, _timeout in instance.commands]
    assert all(secret not in command for command in commands)
    assert commands == [
        "mkdir -p /tmp",
        f"chmod 600 {remote_path}",
        f"docker exec --workdir /workspace --env-file {remote_path} aec-bench-trial python -V",
        f"rm -f {remote_path}",
    ]
    assert [timeout for _command, timeout in instance.commands] == [31, 31, 29, 31]


def test_morph_cloud_operations_removes_secret_env_file_when_container_command_fails() -> None:
    secret = "bedrock-secret-marker"
    instance = FakeMorphInstance(fail_command_containing="docker exec")
    operations = MorphCloudOperations()

    with pytest.raises(RuntimeError, match="simulated Morph command failure"):
        operations.run_container_command_result(
            instance=instance,
            command=("python", "-V"),
            workdir=None,
            env={"AWS_BEARER_TOKEN_BEDROCK": secret},
        )

    remote_path = instance.uploads[0][1]
    commands = [command for command, _timeout in instance.commands]
    assert all(secret not in command for command in commands)
    assert commands[-1] == f"rm -f {remote_path}"


def test_morph_cloud_operations_preserves_execution_and_secret_cleanup_failures() -> None:
    class DualFailureMorphInstance(FakeMorphInstance):
        def exec(self, command: str, timeout: int | None = None) -> FakeMorphExecResponse:
            self.commands.append((command, timeout))
            if "docker exec" in command:
                raise RuntimeError("simulated container execution failure")
            if command.startswith("rm -f /tmp/aec-bench-container-env-"):
                return FakeMorphExecResponse(exit_code=9, stderr="simulated secret cleanup failure")
            return FakeMorphExecResponse()

    instance = DualFailureMorphInstance()
    operations = MorphCloudOperations()

    with pytest.raises(ExceptionGroup, match="execution and environment cleanup failed") as captured:
        operations.run_container_command_result(
            instance=instance,
            command=("python", "-V"),
            env={"AWS_BEARER_TOKEN_BEDROCK": "bedrock-secret-marker"},
        )

    messages = tuple(str(error) for error in captured.value.exceptions)
    assert any("container execution failure" in message for message in messages)
    assert any("secret cleanup failure" in message for message in messages)


def test_morph_cloud_operations_rejects_multiline_container_environment_values() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations()

    with pytest.raises(ValueError, match="single-line"):
        operations.run_container_command_result(
            instance=instance,
            command=("python", "-V"),
            workdir=None,
            env={"AWS_BEARER_TOKEN_BEDROCK": "secret\nINJECTED=value"},
        )

    assert instance.commands == []
    assert instance.uploads == []


def test_morph_upload_archive_excludes_transient_python_cache_files(tmp_path: Path) -> None:
    source_dir = tmp_path / "aec_bench"
    cache_dir = source_dir / "__pycache__"
    nested_dir = source_dir / "nested"
    nested_cache_dir = nested_dir / "__pycache__"
    cache_dir.mkdir(parents=True)
    nested_cache_dir.mkdir(parents=True)
    (source_dir / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
    (nested_dir / "helper.py").write_text("VALUE = 2\n", encoding="utf-8")
    (source_dir / "module.pyc").write_bytes(b"top-level-pyc")
    (source_dir / "module.pyo").write_bytes(b"top-level-pyo")
    (cache_dir / "module.cpython-313.pyc").write_bytes(b"cached-pyc")
    (nested_cache_dir / "helper.cpython-313.pyc").write_bytes(b"nested-cached-pyc")
    archive_path = tmp_path / "payload.tar.gz"

    _write_directory_archive(local_path=source_dir, archive_path=archive_path)

    with tarfile.open(archive_path, "r:gz") as archive:
        member_names = {member.name for member in archive.getmembers()}
    assert "module.py" in member_names
    assert "nested/helper.py" in member_names
    assert all("__pycache__" not in Path(name).parts for name in member_names)
    assert all(Path(name).suffix not in {".pyc", ".pyo"} for name in member_names)


def test_morph_cloud_operations_scrubs_trial_payload_before_instance_stop() -> None:
    instance = FakeMorphInstance()
    operations = MorphCloudOperations()

    operations.scrub_trial_instance(instance=instance)

    commands = [command for command, _timeout in instance.commands]
    assert commands == [
        "docker rm -f aec-bench-trial >/dev/null 2>&1 || true",
        "docker image rm -f aec-bench-task-runtime aec-bench-task-base >/dev/null 2>&1 || true",
        "rm -rf -- /workspace /logs /tests /tmp/aec-bench-runtime-build",
        "find /tmp -maxdepth 1 -type f -name 'aec-bench-container-env-*.env' -delete",
        "find /tmp -maxdepth 1 -type f -name 'aec-bench-upload-*.tar.gz' -delete",
    ]


def test_morph_cloud_operations_attempts_every_scrub_step_after_failure() -> None:
    instance = FakeMorphInstance(fail_command_containing="rm -rf")
    operations = MorphCloudOperations()

    with pytest.raises(ExceptionGroup, match="Morph trial scrub failed"):
        operations.scrub_trial_instance(instance=instance)

    commands = [command for command, _timeout in instance.commands]
    assert commands[-2:] == [
        "find /tmp -maxdepth 1 -type f -name 'aec-bench-container-env-*.env' -delete",
        "find /tmp -maxdepth 1 -type f -name 'aec-bench-upload-*.tar.gz' -delete",
    ]


def test_morph_cloud_operations_deletes_owned_runtime_snapshot() -> None:
    snapshot = FakeMorphSnapshot(id="snapshot-runtime")
    operations = MorphCloudOperations()

    operations.delete_snapshot(snapshot=snapshot)

    assert snapshot.deleted is True


def test_morph_cloud_operations_deletes_build_snapshot_after_runtime_snapshot(tmp_path: Path) -> None:
    environment_dir = tmp_path / "environment"
    project_src_dir = tmp_path / "src" / "aec_bench"
    environment_dir.mkdir(parents=True)
    project_src_dir.mkdir(parents=True)
    (environment_dir / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (project_src_dir / "__init__.py").write_text("", encoding="utf-8")

    build_snapshot = FakeMorphSnapshot(id="snapshot-build")
    runtime_snapshot = FakeMorphSnapshot(id="snapshot-runtime")
    builder = FakeMorphInstance(id="morphvm-builder", runtime_snapshot=runtime_snapshot)
    client = FakeMorphClient(build_snapshot=build_snapshot, builder=builder)
    operations = RecordingMorphCloudOperations(client_factory=lambda: client)

    snapshot = operations.build_runtime_snapshot(
        dockerfile_path=environment_dir / "Dockerfile",
        context_dir=environment_dir,
        project_src_dir=project_src_dir,
        runtime_packages=("pydantic>=2.11,<2.12",),
    )

    assert snapshot is runtime_snapshot
    assert builder.stopped is True
    assert build_snapshot.deleted is True
    assert client.started_snapshot_ids == ["snapshot-build"]
    assert builder.snapshot_metadata == {"aec-bench-role": "runtime"}
    assert operations.events[0] == "prepare:morphvm-builder"
    assert (
        "command:morphvm-builder:docker build -t aec-bench-task-base "
        "-f /tmp/aec-bench-runtime-build/task/Dockerfile /tmp/aec-bench-runtime-build/task"
    ) in operations.events


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


def test_morph_cloud_operations_deletes_all_snapshots_when_builder_stop_fails(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    project_src_dir = tmp_path / "src" / "aec_bench"
    (task_dir / "environment").mkdir(parents=True)
    project_src_dir.mkdir(parents=True)
    (task_dir / "environment" / "Dockerfile").write_text("FROM python:3.13-slim\n", encoding="utf-8")
    (project_src_dir / "__init__.py").write_text("", encoding="utf-8")
    build_snapshot = FakeMorphSnapshot(id="snapshot-build")
    runtime_snapshot = FakeMorphSnapshot(id="snapshot-runtime")
    builder = FakeMorphInstance(
        id="morphvm-builder",
        runtime_snapshot=runtime_snapshot,
        fail_stop=True,
    )
    client = FakeMorphClient(build_snapshot=build_snapshot, builder=builder)
    operations = RecordingMorphCloudOperations(client_factory=lambda: client)

    with pytest.raises(RuntimeError, match="simulated Morph stop failure"):
        operations.build_runtime_snapshot(
            dockerfile_path=task_dir / "environment" / "Dockerfile",
            context_dir=task_dir,
            project_src_dir=project_src_dir,
            runtime_packages=("pydantic>=2.11,<2.12",),
        )

    assert build_snapshot.deleted is True
    assert runtime_snapshot.deleted is True


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
    fail_command_containing: str | None = None
    fail_stop: bool = False

    def wait_until_ready(self) -> None:
        return None

    def exec(self, command: str, timeout: int | None = None) -> FakeMorphExecResponse:
        self.commands.append((command, timeout))
        if self.fail_command_containing is not None and self.fail_command_containing in command:
            raise RuntimeError("simulated Morph command failure")
        return FakeMorphExecResponse()

    def upload(self, local_path: str, remote_path: str, recursive: bool = False) -> None:
        self.uploads.append((local_path, remote_path, recursive, Path(local_path).read_bytes()))

    def stop(self) -> None:
        self.stopped = True
        if self.fail_stop:
            raise RuntimeError("simulated Morph stop failure")

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
