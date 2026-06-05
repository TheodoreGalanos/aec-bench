# ABOUTME: Morph Cloud provider operations for remote sandbox instances.
# ABOUTME: Keeps Morph SDK calls, file transfer, and Docker host commands outside harness orchestration.

import base64
import hashlib
import inspect
import io
import logging
import shlex
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, cast
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MorphCloudOperations:
    base_image_id: str = "morphvm-sandbox"
    vcpus: int = 2
    memory_mb: int = 4096
    disk_size_mb: int = 20_480
    snapshot_ttl_seconds: int = 604_800
    instance_ttl_seconds: int = 900
    command_timeout_seconds: int = 900
    build_timeout_seconds: int = 1_800
    build_root: str = "/tmp/aec-bench-runtime-build"
    runtime_image_name: str = "aec-bench-task-runtime"
    base_task_image_name: str = "aec-bench-task-base"
    trial_container_name: str = "aec-bench-trial"
    client_factory: Callable[[], Any] = field(default_factory=lambda: _morph_client)

    def build_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        project_src_dir: Path,
        runtime_packages: tuple[str, ...],
    ) -> object:
        del dockerfile_path
        client = self.client_factory()
        base_snapshot = _call_with_supported_kwargs(
            client.snapshots.create,
            image_id=self.base_image_id,
            vcpus=self.vcpus,
            memory=self.memory_mb,
            disk_size=self.disk_size_mb,
            metadata={"aec-bench-role": "runtime-build"},
            ttl_seconds=self.snapshot_ttl_seconds,
        )
        builder: Any | None = None
        try:
            builder = self.start_instance(snapshot=base_snapshot)
            if hasattr(builder, "wait_until_ready"):
                builder.wait_until_ready()
            self._prepare_docker_host(builder)
            self._run_host_command(builder, f"rm -rf {shlex.quote(self.build_root)}")
            self._run_host_command(builder, f"mkdir -p {shlex.quote(self.build_root)}")
            self.upload_directory(
                instance=builder,
                local_path=context_dir,
                remote_path=f"{self.build_root}/task",
            )
            self.upload_directory(
                instance=builder,
                local_path=project_src_dir,
                remote_path=f"{self.build_root}/src/aec_bench",
            )
            self.write_instance_file(
                instance=builder,
                remote_path=f"{self.build_root}/Dockerfile",
                content=_runtime_dockerfile(runtime_packages=runtime_packages).encode(),
            )
            self._run_host_command(
                builder,
                shlex.join(
                    (
                        "docker",
                        "build",
                        "-t",
                        self.base_task_image_name,
                        "-f",
                        f"{self.build_root}/task/environment/Dockerfile",
                        f"{self.build_root}/task",
                    )
                ),
                command_timeout_seconds=self.build_timeout_seconds,
            )
            self._run_host_command(
                builder,
                shlex.join(
                    (
                        "docker",
                        "build",
                        "-t",
                        self.runtime_image_name,
                        "-f",
                        f"{self.build_root}/Dockerfile",
                        self.build_root,
                    )
                ),
                command_timeout_seconds=self.build_timeout_seconds,
            )
            return _call_with_supported_kwargs(
                builder.snapshot,
                digest=_runtime_digest(
                    context_dir=context_dir,
                    project_src_dir=project_src_dir,
                    runtime_packages=runtime_packages,
                ),
                metadata={"aec-bench-role": "runtime"},
                ttl_seconds=self.snapshot_ttl_seconds,
            )
        finally:
            if builder is not None:
                self.stop_instance(instance=builder)
            _delete_snapshot(snapshot=base_snapshot)

    def start_instance(self, *, snapshot: object) -> Any:
        client = self.client_factory()
        instance = _call_with_supported_kwargs(
            client.instances.start,
            snapshot_id=morph_object_id(snapshot),
            metadata={"aec-bench-role": "trial"},
            ttl_seconds=self.instance_ttl_seconds,
            ttl_action="stop",
            timeout=self.command_timeout_seconds,
        )
        if hasattr(instance, "wait_until_ready"):
            instance.wait_until_ready()
        return instance

    def upload_directory(self, *, instance: Any, local_path: Path, remote_path: str) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive_path = Path(temp_dir) / "payload.tar.gz"
            _write_directory_archive(local_path=local_path, archive_path=archive_path)
            remote_archive_path = f"/tmp/aec-bench-upload-{uuid4().hex}.tar.gz"
            self.write_instance_file(
                instance=instance,
                remote_path=remote_archive_path,
                content=archive_path.read_bytes(),
            )
            self._run_host_command(
                instance,
                " && ".join(
                    (
                        f"mkdir -p {shlex.quote(remote_path)}",
                        f"tar -xzf {shlex.quote(remote_archive_path)} -C {shlex.quote(remote_path)}",
                        f"rm -f {shlex.quote(remote_archive_path)}",
                    )
                ),
            )

    def start_trial_container(self, *, instance: Any, workspace_dir: str, logs_dir: str) -> None:
        self._run_host_command(
            instance,
            " && ".join((f"mkdir -p {shlex.quote(workspace_dir)}", f"mkdir -p {shlex.quote(logs_dir)}")),
        )
        self._run_host_command(
            instance,
            f"docker rm -f {shlex.quote(self.trial_container_name)} >/dev/null 2>&1 || true",
        )
        self._run_host_command(
            instance,
            shlex.join(
                (
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    self.trial_container_name,
                    "--workdir",
                    workspace_dir,
                    "--volume",
                    f"{workspace_dir}:{workspace_dir}",
                    "--volume",
                    f"{logs_dir}:{logs_dir}",
                    self.runtime_image_name,
                    "sleep",
                    "infinity",
                )
            ),
        )

    def write_instance_file(self, *, instance: Any, remote_path: str, content: bytes) -> None:
        parent_dir = str(PurePosixPath(remote_path).parent)
        if parent_dir not in {"", ".", "/"}:
            self._run_host_command(instance, f"mkdir -p {shlex.quote(parent_dir)}")
        with tempfile.NamedTemporaryFile() as file_handle:
            file_handle.write(content)
            file_handle.flush()
            instance.upload(file_handle.name, remote_path, recursive=False)

    def run_container_command(
        self,
        *,
        instance: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.run_container_command_result(
            instance=instance,
            command=command,
            workdir=workdir,
            env=env,
            timeout_seconds=timeout_seconds,
        )

    def run_container_command_result(
        self,
        *,
        instance: Any,
        command: tuple[str, ...],
        workdir: str | None = None,
        env: dict[str, str] | None = None,
        timeout_seconds: int | None = None,
    ) -> "MorphCommandResult":
        return self._run_container_command_result(
            instance=instance,
            command=command,
            workdir=workdir,
            env=env,
            timeout_seconds=timeout_seconds,
        )

    def read_container_file(self, *, instance: Any, remote_path: str) -> bytes | None:
        script = (
            "import base64,pathlib,sys;"
            "path=pathlib.Path(sys.argv[1]);"
            "sys.exit(44) if not path.exists() else "
            "sys.stdout.write(base64.b64encode(path.read_bytes()).decode())"
        )
        result = self._run_container_command_result(
            instance=instance,
            command=("python", "-c", script, remote_path),
            workdir=None,
            env=None,
            check=False,
        )
        if result.exit_code == 44:
            return None
        if result.exit_code != 0:
            raise RuntimeError(_command_failure_message(result=result))
        return base64.b64decode(result.stdout.encode())

    def read_container_directory_archive(self, *, instance: Any, remote_path: str) -> bytes | None:
        script = (
            "import base64,io,pathlib,sys,tarfile;"
            "root=pathlib.Path(sys.argv[1]);"
            "sys.exit(44) if not root.is_dir() else None;"
            "buf=io.BytesIO();"
            "tar=tarfile.open(fileobj=buf,mode='w:gz');"
            "[tar.add(p,arcname=str(p.relative_to(root))) for p in sorted(root.rglob('*'))];"
            "tar.close();"
            "sys.stdout.write(base64.b64encode(buf.getvalue()).decode())"
        )
        result = self._run_container_command_result(
            instance=instance,
            command=("python", "-c", script, remote_path),
            workdir=None,
            env=None,
            check=False,
        )
        if result.exit_code == 44:
            return None
        if result.exit_code != 0:
            raise RuntimeError(_command_failure_message(result=result))
        return base64.b64decode(result.stdout.encode())

    def stop_instance(self, *, instance: Any) -> None:
        instance.stop()

    def _prepare_docker_host(self, instance: Any) -> None:
        self._run_host_command(
            instance,
            "command -v docker >/dev/null 2>&1 || "
            "(apt-get update && apt-get install -y docker.io && service docker start)",
            command_timeout_seconds=self.build_timeout_seconds,
        )
        self._run_host_command(instance, "service docker start >/dev/null 2>&1 || true")

    def _run_container_command_result(
        self,
        *,
        instance: Any,
        command: tuple[str, ...],
        workdir: str | None,
        env: dict[str, str] | None,
        timeout_seconds: int | None = None,
        check: bool = True,
    ) -> "MorphCommandResult":
        return self._run_host_command(
            instance,
            _docker_exec_command(
                container_name=self.trial_container_name,
                command=command,
                workdir=workdir,
                env=env,
            ),
            check=check,
            command_timeout_seconds=timeout_seconds,
        )

    def _run_host_command(
        self,
        instance: Any,
        command: str,
        *,
        check: bool = True,
        command_timeout_seconds: int | None = None,
    ) -> "MorphCommandResult":
        timeout_seconds = command_timeout_seconds or self.command_timeout_seconds
        raw_result = instance.exec(command, timeout=timeout_seconds)
        result = _normalize_command_result(raw_result)
        if check and result.exit_code != 0:
            raise RuntimeError(_command_failure_message(result=result))
        return result


@dataclass(frozen=True)
class MorphCommandResult:
    exit_code: int
    stdout: str
    stderr: str


def morph_object_id(value: object) -> str:
    if isinstance(value, dict):
        mapped_id = cast(object, value.get("id"))
        if isinstance(mapped_id, str):
            return mapped_id
    for attribute in ("id", "object_id"):
        object_id = getattr(value, attribute, None)
        if isinstance(object_id, str):
            return object_id
    msg = f"cannot resolve Morph object id from {type(value).__name__}"
    raise ValueError(msg)


def _morph_client() -> Any:
    try:
        from morphcloud.api import MorphCloudClient
    except ImportError as exc:
        msg = "Morph Cloud support requires the morphcloud package and MORPH_API_KEY configuration."
        raise RuntimeError(msg) from exc
    return MorphCloudClient()


def _call_with_supported_kwargs(function: Any, **kwargs: object) -> Any:
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return function(**kwargs)
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in signature.parameters.values()):
        return function(**kwargs)
    accepted_kwargs = {name: value for name, value in kwargs.items() if name in signature.parameters}
    return function(**accepted_kwargs)


def _delete_snapshot(*, snapshot: object) -> None:
    delete = getattr(snapshot, "delete", None)
    if not callable(delete):
        return
    try:
        delete()
    except Exception:
        logger.warning("failed to delete Morph build snapshot: %s", morph_object_id(snapshot), exc_info=True)


def _runtime_dockerfile(*, runtime_packages: tuple[str, ...]) -> str:
    quoted_packages = " ".join(shlex.quote(package) for package in runtime_packages)
    return "\n".join(
        (
            "FROM aec-bench-task-base",
            "RUN (python3 -m pip --version >/dev/null 2>&1 || "
            "python -m pip --version >/dev/null 2>&1 || "
            "(apt-get update && apt-get install -y python3-pip && rm -rf /var/lib/apt/lists/*))",
            f"RUN (python3 -m pip install --no-cache-dir {quoted_packages} || "
            f"python -m pip install --no-cache-dir {quoted_packages})",
            "COPY src/aec_bench /opt/aec_bench/aec_bench",
            "ENV PYTHONPATH=/opt/aec_bench",
            "",
        )
    )


def extract_archive(*, archive_bytes: bytes, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
        for member in archive.getmembers():
            destination = _archive_member_destination(target_root=target_root, member_name=member.name)
            if member.isdir():
                destination.mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                msg = f"unsupported archive member type: {member.name}"
                raise RuntimeError(msg)
            source = archive.extractfile(member)
            if source is None:
                msg = f"missing archive member content: {member.name}"
                raise RuntimeError(msg)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with source, destination.open("wb") as target_file:
                shutil.copyfileobj(source, target_file)


def _archive_member_destination(*, target_root: Path, member_name: str) -> Path:
    if not member_name or Path(member_name).is_absolute():
        msg = f"unsafe archive member: {member_name}"
        raise RuntimeError(msg)
    destination = (target_root / member_name).resolve()
    if destination != target_root and target_root not in destination.parents:
        msg = f"unsafe archive member: {member_name}"
        raise RuntimeError(msg)
    return destination


def _write_directory_archive(*, local_path: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        if local_path.is_dir():
            for child in sorted(local_path.iterdir()):
                archive.add(child, arcname=child.name)
        else:
            archive.add(local_path, arcname=local_path.name)


def _docker_exec_command(
    *,
    container_name: str,
    command: tuple[str, ...],
    workdir: str | None,
    env: dict[str, str] | None,
) -> str:
    docker_command = ["docker", "exec"]
    if workdir is not None:
        docker_command.extend(("--workdir", workdir))
    if env is not None:
        for key, value in sorted(env.items()):
            docker_command.extend(("--env", f"{key}={value}"))
    docker_command.append(container_name)
    docker_command.extend(command)
    return shlex.join(docker_command)


def _normalize_command_result(raw_result: object) -> MorphCommandResult:
    if isinstance(raw_result, str | bytes):
        return MorphCommandResult(exit_code=0, stdout=_as_text(raw_result), stderr="")
    exit_code_value = getattr(raw_result, "exit_code", getattr(raw_result, "returncode", 0))
    if exit_code_value is None:
        exit_code = 0
    else:
        exit_code = int(cast(int | str, exit_code_value))
    return MorphCommandResult(
        exit_code=exit_code,
        stdout=_as_text(getattr(raw_result, "stdout", "")),
        stderr=_as_text(getattr(raw_result, "stderr", "")),
    )


def _as_text(value: object) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _command_failure_message(*, result: MorphCommandResult) -> str:
    message = f"Morph command failed with exit code {result.exit_code}"
    if result.stderr:
        message = f"{message}\nstderr:\n{result.stderr}"
    if result.stdout:
        message = f"{message}\nstdout:\n{result.stdout}"
    return message


def _runtime_digest(
    *,
    context_dir: Path,
    project_src_dir: Path,
    runtime_packages: tuple[str, ...],
) -> str:
    digest = hashlib.sha256()
    _hash_directory(digest=digest, directory=context_dir)
    _hash_directory(digest=digest, directory=project_src_dir)
    for package in runtime_packages:
        digest.update(package.encode())
        digest.update(b"\0")
    return digest.hexdigest()


def _hash_directory(*, digest: "hashlib._Hash", directory: Path) -> None:
    for path in sorted(directory.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
