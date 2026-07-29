# ABOUTME: Morph Cloud provider operations for remote sandbox instances.
# ABOUTME: Keeps Morph SDK calls, file transfer, and Docker host commands outside harness orchestration.

import base64
import hashlib
import inspect
import io
import logging
import re
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
_CONTAINER_ENVIRONMENT_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")


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
        dockerfile_relative_path = _dockerfile_relative_path(
            dockerfile_path=dockerfile_path,
            context_dir=context_dir,
        )
        base_snapshot = self._create_runtime_build_base_snapshot()
        builder: Any | None = None
        runtime_snapshot: object | None = None
        build_error: Exception | None = None
        try:
            builder = self.start_instance(snapshot=base_snapshot)
            runtime_snapshot = self._build_runtime_on_instance(
                builder=builder,
                dockerfile_relative_path=dockerfile_relative_path,
                context_dir=context_dir,
                project_src_dir=project_src_dir,
                runtime_packages=runtime_packages,
            )
        except Exception as error:
            build_error = error
        return self._complete_runtime_snapshot_build(
            builder=builder,
            base_snapshot=base_snapshot,
            runtime_snapshot=runtime_snapshot,
            build_error=build_error,
        )

    def _create_runtime_build_base_snapshot(self) -> object:
        client = self.client_factory()
        return _call_with_supported_kwargs(
            client.snapshots.create,
            image_id=self.base_image_id,
            vcpus=self.vcpus,
            memory=self.memory_mb,
            disk_size=self.disk_size_mb,
            metadata={"aec-bench-role": "runtime-build"},
            ttl_seconds=self.snapshot_ttl_seconds,
        )

    def _build_runtime_on_instance(
        self,
        *,
        builder: Any,
        dockerfile_relative_path: Path,
        context_dir: Path,
        project_src_dir: Path,
        runtime_packages: tuple[str, ...],
    ) -> object:
        remote_context_dir = PurePosixPath(self.build_root) / "task"
        remote_dockerfile_path = remote_context_dir / PurePosixPath(dockerfile_relative_path.as_posix())
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
                    str(remote_dockerfile_path),
                    str(remote_context_dir),
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

    def _complete_runtime_snapshot_build(
        self,
        *,
        builder: Any | None,
        base_snapshot: object,
        runtime_snapshot: object | None,
        build_error: Exception | None,
    ) -> object:
        cleanup_errors: list[Exception] = []
        if builder is not None:
            try:
                self.stop_instance(instance=builder)
            except Exception as error:
                cleanup_errors.append(error)
        try:
            self.delete_snapshot(snapshot=base_snapshot)
        except Exception as error:
            cleanup_errors.append(error)

        errors = ([build_error] if build_error is not None else []) + cleanup_errors
        if errors and runtime_snapshot is not None:
            try:
                self.delete_snapshot(snapshot=runtime_snapshot)
            except Exception as error:
                errors.append(error)
        if len(errors) == 1:
            raise errors[0]
        if errors:
            raise ExceptionGroup("Morph runtime build and cleanup failed", errors)
        if runtime_snapshot is None:
            raise RuntimeError("Morph runtime build produced no snapshot")
        return runtime_snapshot

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

    def start_trial_container(
        self,
        *,
        instance: Any,
        workspace_dir: str,
        logs_dir: str,
        tests_dir: str = "/tests",
    ) -> None:
        self._run_host_command(
            instance,
            " && ".join(
                (
                    f"mkdir -p {shlex.quote(workspace_dir)}",
                    f"mkdir -p {shlex.quote(logs_dir)}",
                    f"mkdir -p {shlex.quote(tests_dir)}",
                )
            ),
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
                    "--rm",
                    "--volume",
                    f"{workspace_dir}:/aec-bench-host-workspace",
                    "--network",
                    "none",
                    self.runtime_image_name,
                    "sh",
                    "-c",
                    "cp -a /workspace/. /aec-bench-host-workspace/",
                )
            ),
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
                    "--volume",
                    f"{tests_dir}:{tests_dir}",
                    "--network",
                    "none",
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
        self._run_container_command_result(
            instance=instance,
            command=command,
            workdir=workdir,
            env=env,
            timeout_seconds=timeout_seconds,
            check=True,
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
            check=False,
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

    def scrub_trial_instance(self, *, instance: Any) -> None:
        commands = (
            f"docker rm -f {shlex.quote(self.trial_container_name)} >/dev/null 2>&1 || true",
            "docker image rm -f "
            f"{shlex.quote(self.runtime_image_name)} {shlex.quote(self.base_task_image_name)} "
            ">/dev/null 2>&1 || true",
            "rm -rf -- /workspace /logs /tests " + shlex.quote(self.build_root),
            "find /tmp -maxdepth 1 -type f -name 'aec-bench-container-env-*.env' -delete",
            "find /tmp -maxdepth 1 -type f -name 'aec-bench-upload-*.tar.gz' -delete",
        )
        errors: list[Exception] = []
        for command in commands:
            try:
                self._run_host_command(instance, command)
            except Exception as error:
                errors.append(error)
        if errors:
            raise ExceptionGroup("Morph trial scrub failed", errors)

    def delete_snapshot(self, *, snapshot: object) -> None:
        delete = getattr(snapshot, "delete", None)
        if not callable(delete):
            raise RuntimeError("Morph runtime snapshot does not expose deletion")
        delete()

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
        if not env:
            return self._run_host_command(
                instance,
                _docker_exec_command(
                    container_name=self.trial_container_name,
                    command=command,
                    workdir=workdir,
                    env_file=None,
                ),
                check=check,
                command_timeout_seconds=timeout_seconds,
            )

        environment_content = _container_environment_file(env)
        environment_path = f"/tmp/aec-bench-container-env-{uuid4().hex}.env"
        result: MorphCommandResult | None = None
        execution_error: Exception | None = None
        try:
            self.write_instance_file(
                instance=instance,
                remote_path=environment_path,
                content=environment_content,
            )
            self._run_host_command(
                instance,
                f"chmod 600 {shlex.quote(environment_path)}",
            )
            result = self._run_host_command(
                instance,
                _docker_exec_command(
                    container_name=self.trial_container_name,
                    command=command,
                    workdir=workdir,
                    env_file=environment_path,
                ),
                check=check,
                command_timeout_seconds=timeout_seconds,
            )
        except Exception as error:
            execution_error = error

        cleanup_error: Exception | None = None
        try:
            cleanup = self._run_host_command(
                instance,
                f"rm -f {shlex.quote(environment_path)}",
                check=False,
            )
            if cleanup.exit_code != 0:
                cleanup_error = RuntimeError(
                    "failed to remove temporary Morph container environment file\n"
                    + _command_failure_message(result=cleanup)
                )
        except Exception as error:
            cleanup_error = error

        if execution_error is not None and cleanup_error is not None:
            raise ExceptionGroup(
                "Morph container execution and environment cleanup failed",
                [execution_error, cleanup_error],
            )
        if execution_error is not None:
            raise execution_error
        if cleanup_error is not None:
            raise cleanup_error
        if result is None:
            raise RuntimeError("Morph container execution produced no result")
        return result

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


def _dockerfile_relative_path(*, dockerfile_path: Path, context_dir: Path) -> Path:
    try:
        return dockerfile_path.relative_to(context_dir)
    except ValueError as error:
        raise ValueError("Morph Dockerfile must be inside its build context") from error


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
            "RUN (python3 -m venv /opt/aec-bench-venv || "
            "(apt-get update && apt-get install -y --no-install-recommends python3-venv && "
            "rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/aec-bench-venv))",
            f"RUN /opt/aec-bench-venv/bin/python -m pip install --no-cache-dir {quoted_packages}",
            "COPY src/aec_bench /opt/aec_bench/aec_bench",
            'ENV PATH="/opt/aec-bench-venv/bin:$PATH"',
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
                archive.add(child, arcname=child.name, filter=_archive_payload_filter)
        else:
            archive.add(local_path, arcname=local_path.name, filter=_archive_payload_filter)


def _archive_payload_filter(member: tarfile.TarInfo) -> tarfile.TarInfo | None:
    if _is_transient_python_cache(PurePosixPath(member.name)):
        return None
    return member


def _docker_exec_command(
    *,
    container_name: str,
    command: tuple[str, ...],
    workdir: str | None,
    env_file: str | None,
) -> str:
    docker_command = ["docker", "exec"]
    if workdir is not None:
        docker_command.extend(("--workdir", workdir))
    if env_file is not None:
        docker_command.extend(("--env-file", env_file))
    docker_command.append(container_name)
    docker_command.extend(command)
    return shlex.join(docker_command)


def _container_environment_file(environment: dict[str, str]) -> bytes:
    lines: list[str] = []
    for name, value in sorted(environment.items()):
        if _CONTAINER_ENVIRONMENT_NAME.fullmatch(name) is None:
            raise ValueError(f"invalid container environment name: {name!r}")
        if any(character in value for character in ("\n", "\r", "\0")):
            raise ValueError(f"container environment value for {name!r} must be single-line")
        lines.append(f"{name}={value}")
    return ("\n".join(lines) + "\n").encode("utf-8")


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
        if path.is_dir() or _is_transient_python_cache(path):
            continue
        digest.update(str(path.relative_to(directory)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")


def _is_transient_python_cache(path: Path | PurePosixPath) -> bool:
    return "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}
