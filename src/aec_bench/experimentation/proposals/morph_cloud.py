# ABOUTME: Provides Morph host operations for source-filtered proposal runtime images and container rotation.
# ABOUTME: Keeps full project source out of proposal snapshots and reads handoff evidence only after agent stop.

from __future__ import annotations

import base64
import hashlib
import json
import os
import shlex
import shutil
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

from aec_bench.contracts.execution_environment import RUNTIME_PYTHON_PACKAGES
from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.experimentation.proposals.runtime_archive import (
    ProposalRuntimeArchiveError,
    verify_proposal_runtime_archive,
)
from aec_bench.experimentation.proposals.task_package import (
    verify_proposal_task_build_context as verify_default_proposal_task_build_context,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageError,
    VerifiedProposalTaskBuildContext,
)
from aec_bench.providers.morph_cloud import (
    MorphCloudOperations,
    _call_with_supported_kwargs,
)

_MAX_RUNTIME_ARCHIVE_BYTES = 64 * 1024 * 1024
PROPOSAL_EXACT_ARTIFACT_LIMITS = {
    "/workspace/.scratchpad.json": 16 * 1024 * 1024,
    "/workspace/agent_result.json": 16 * 1024 * 1024,
    "/workspace/conversation.jsonl": 16 * 1024 * 1024,
    "/workspace/model_reasoning.jsonl": 16 * 1024 * 1024,
    "/workspace/output.md": 16 * 1024 * 1024,
    "/workspace/symbolic_state.json": 16 * 1024 * 1024,
    "/workspace/trajectory.jsonl": 16 * 1024 * 1024,
}
PROPOSAL_SESSION_ROOT = "/workspace/proposal-session"
PROPOSAL_SESSION_MAX_FILES = 512
PROPOSAL_SESSION_MAX_ENTRIES = 2048
PROPOSAL_SESSION_MAX_FILE_BYTES = 8 * 1024 * 1024
PROPOSAL_SESSION_MAX_TOTAL_BYTES = 32 * 1024 * 1024
PROPOSAL_HANDOFF_MAX_TOTAL_BYTES = 64 * 1024 * 1024


class ProposalMorphRuntimeBuildError(ValueError):
    """Reject an unsafe or identity-mismatched proposal runtime build input."""


class ProposalMorphCloudOperations(MorphCloudOperations):
    """Morph operations that never accept a full project-source directory."""

    def build_proposal_runtime_snapshot(
        self,
        *,
        dockerfile_path: Path,
        context_dir: Path,
        runtime_archive_path: Path,
        runtime_archive_sha256: str,
        runtime_archive_content_sha256: str,
        runtime_packages: tuple[str, ...],
    ) -> object:
        """Build one runtime snapshot from a verified filtered archive."""

        archive_path, archive_bytes = _verified_proposal_runtime_archive(
            runtime_archive_path=runtime_archive_path,
            runtime_archive_sha256=runtime_archive_sha256,
            runtime_archive_content_sha256=runtime_archive_content_sha256,
            runtime_packages=runtime_packages,
        )
        (
            dockerfile_relative_path,
            verified_context,
            staging_root,
            context,
        ) = _stage_verified_proposal_context(
            dockerfile_path=dockerfile_path,
            context_dir=context_dir,
        )
        base_snapshot = self._create_proposal_runtime_base_snapshot(staging_root=staging_root)
        builder: Any | None = None
        runtime_snapshot: object | None = None
        build_error: Exception | None = None
        try:
            builder = self.start_instance(snapshot=base_snapshot)
            runtime_snapshot = self._build_proposal_runtime_on_instance(
                builder=builder,
                archive_path=archive_path,
                archive_bytes=archive_bytes,
                context=context,
                dockerfile_relative_path=dockerfile_relative_path,
                verified_context=verified_context,
                runtime_archive_sha256=runtime_archive_sha256,
                runtime_archive_content_sha256=runtime_archive_content_sha256,
                runtime_packages=runtime_packages,
            )
        except Exception as error:
            build_error = error
        return self._complete_proposal_runtime_snapshot_build(
            builder=builder,
            base_snapshot=base_snapshot,
            runtime_snapshot=runtime_snapshot,
            build_error=build_error,
            staging_root=staging_root,
        )

    def _create_proposal_runtime_base_snapshot(self, *, staging_root: Path) -> object:
        try:
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
        except Exception:
            shutil.rmtree(staging_root, ignore_errors=True)
            raise

    def _build_proposal_runtime_on_instance(
        self,
        *,
        builder: Any,
        archive_path: Path,
        archive_bytes: bytes,
        context: Path,
        dockerfile_relative_path: Path,
        verified_context: VerifiedProposalTaskBuildContext,
        runtime_archive_sha256: str,
        runtime_archive_content_sha256: str,
        runtime_packages: tuple[str, ...],
    ) -> object:
        remote_context = PurePosixPath(self.build_root) / "task"
        remote_dockerfile = remote_context / PurePosixPath(dockerfile_relative_path.as_posix())
        remote_archive = PurePosixPath(self.build_root) / "proposal-runtime.tar.gz"
        remote_runtime = PurePosixPath(self.build_root) / "proposal-runtime"
        if hasattr(builder, "wait_until_ready"):
            builder.wait_until_ready()
        self._prepare_docker_host(builder)
        self._run_host_command(
            builder,
            f"rm -rf {shlex.quote(self.build_root)}",
        )
        self._run_host_command(
            builder,
            f"mkdir -p {shlex.quote(self.build_root)}",
        )
        self.upload_directory(
            instance=builder,
            local_path=context,
            remote_path=remote_context.as_posix(),
        )
        self._upload_file_path(
            instance=builder,
            local_path=archive_path,
            remote_path=remote_archive.as_posix(),
            content=archive_bytes,
        )
        self._run_host_command(
            builder,
            " && ".join(
                (
                    (
                        'test "$(sha256sum '
                        f"{shlex.quote(remote_archive.as_posix())} | cut -d ' ' -f 1)\" "
                        f"= {shlex.quote(runtime_archive_sha256)}"
                    ),
                    f"mkdir -p {shlex.quote(remote_runtime.as_posix())}",
                    (f"tar -xzf {shlex.quote(remote_archive.as_posix())} -C {shlex.quote(remote_runtime.as_posix())}"),
                )
            ),
        )
        self.write_instance_file(
            instance=builder,
            remote_path=f"{self.build_root}/Dockerfile",
            content=_proposal_runtime_dockerfile(runtime_packages=runtime_packages).encode("utf-8"),
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
                    remote_dockerfile.as_posix(),
                    remote_context.as_posix(),
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
        self._run_host_command(
            builder,
            "rm -rf -- "
            + " ".join(
                shlex.quote(path)
                for path in (
                    remote_context.as_posix(),
                    remote_archive.as_posix(),
                    remote_runtime.as_posix(),
                    f"{self.build_root}/Dockerfile",
                )
            ),
        )
        return _call_with_supported_kwargs(
            builder.snapshot,
            digest=_proposal_runtime_digest(
                context_content_sha256=verified_context.content_sha256,
                archive_sha256=runtime_archive_sha256,
                archive_content_sha256=runtime_archive_content_sha256,
                runtime_packages=runtime_packages,
                base_image_id=self.base_image_id,
            ),
            metadata={"aec-bench-role": "proposal-runtime"},
            ttl_seconds=self.snapshot_ttl_seconds,
        )

    def _complete_proposal_runtime_snapshot_build(
        self,
        *,
        builder: Any | None,
        base_snapshot: object,
        runtime_snapshot: object | None,
        build_error: Exception | None,
        staging_root: Path,
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
        try:
            shutil.rmtree(staging_root)
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
            raise ExceptionGroup(
                "Morph proposal runtime build and cleanup failed",
                errors,
            )
        if runtime_snapshot is None:
            raise RuntimeError("Morph proposal runtime build produced no snapshot")
        return runtime_snapshot

    def _upload_file_path(
        self,
        *,
        instance: Any,
        local_path: Path,
        remote_path: str,
        content: bytes,
    ) -> None:
        del local_path
        self.write_instance_file(
            instance=instance,
            remote_path=remote_path,
            content=content,
        )

    def start_proposal_container(
        self,
        *,
        instance: Any,
        role: str,
        workspace_dir: str,
        logs_dir: str,
        tests_dir: str,
    ) -> str:
        """Start a fresh trial container and return its provider identity."""

        allowed_characters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        if not role or any(character not in allowed_characters for character in role):
            raise ValueError("proposal container role is invalid")
        existing = self._run_host_command(
            instance,
            shlex.join(
                (
                    "docker",
                    "inspect",
                    "--format",
                    "{{.Id}}",
                    self.trial_container_name,
                )
            ),
            check=False,
        )
        if existing.exit_code == 0:
            raise RuntimeError("proposal container start found an unexpected existing trial container")
        self.start_trial_container(
            instance=instance,
            workspace_dir=workspace_dir,
            logs_dir=logs_dir,
            tests_dir=tests_dir,
        )
        return self.trial_container_identity(instance=instance)

    def trial_container_identity(self, *, instance: Any) -> str:
        result = self._run_host_command(
            instance,
            shlex.join(
                (
                    "docker",
                    "inspect",
                    "--format",
                    "{{.Id}}",
                    self.trial_container_name,
                )
            ),
        )
        identity = result.stdout.strip()
        if not identity:
            raise RuntimeError("Morph proposal trial container has no identity")
        return identity

    def stop_trial_container(
        self,
        *,
        instance: Any,
        expected_container_identity: str,
    ) -> None:
        observed_identity = self.trial_container_identity(instance=instance)
        if observed_identity != expected_container_identity:
            raise RuntimeError("proposal trial container identity changed before removal")
        self._run_host_command(
            instance,
            (f"docker rm -f {shlex.quote(expected_container_identity)} >/dev/null 2>&1"),
        )

    def reset_trial_mounts(self, *, instance: Any) -> None:
        self._run_host_command(
            instance,
            " && ".join(
                (
                    "rm -rf -- /workspace /logs /tests",
                    "mkdir -p /workspace /logs/agent /logs/verifier /logs/artifacts /tests",
                )
            ),
        )

    def read_stopped_trial_artifacts(
        self,
        *,
        instance: Any,
    ) -> dict[str, bytes]:
        """Read only allowlisted regular artifacts from a stopped container mount."""

        policy = {
            "exact": PROPOSAL_EXACT_ARTIFACT_LIMITS,
            "tree_root": PROPOSAL_SESSION_ROOT,
            "tree_max_entries": PROPOSAL_SESSION_MAX_ENTRIES,
            "tree_max_files": PROPOSAL_SESSION_MAX_FILES,
            "tree_max_file_bytes": PROPOSAL_SESSION_MAX_FILE_BYTES,
            "tree_max_total_bytes": PROPOSAL_SESSION_MAX_TOTAL_BYTES,
            "handoff_max_total_bytes": PROPOSAL_HANDOFF_MAX_TOTAL_BYTES,
        }
        encoded_policy = base64.b64encode(
            json.dumps(policy, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        result = self._run_host_command(
            instance,
            shlex.join(
                (
                    "python3",
                    "-c",
                    _STOPPED_ARTIFACT_INVENTORY_READER,
                    encoded_policy,
                )
            ),
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise RuntimeError("Morph proposal stopped-artifact response is invalid") from error
        if not isinstance(payload, list):
            raise RuntimeError("Morph proposal stopped-artifact response is not a list")
        artifacts: dict[str, bytes] = {}
        total_bytes = 0
        for item in payload:
            if (
                not isinstance(item, dict)
                or set(item) != {"path", "size_bytes"}
                or not isinstance(item["path"], str)
                or isinstance(item["size_bytes"], bool)
                or not isinstance(item["size_bytes"], int)
                or item["size_bytes"] < 0
            ):
                raise RuntimeError("Morph proposal stopped-artifact response has invalid entries")
            raw_path = item["path"]
            expected_size = item["size_bytes"]
            limit = _artifact_limit(raw_path)
            if expected_size > limit:
                raise RuntimeError(f"Morph proposal stopped artifact exceeds its byte limit: {raw_path}")
            content_result = self._run_host_command(
                instance,
                shlex.join(
                    (
                        "python3",
                        "-c",
                        _STOPPED_ARTIFACT_FILE_READER,
                        raw_path,
                        str(expected_size),
                        str(limit),
                    )
                ),
            )
            try:
                content = base64.b64decode(
                    content_result.stdout.encode("ascii"),
                    validate=True,
                )
            except (ValueError, UnicodeEncodeError) as error:
                raise RuntimeError("Morph proposal stopped-artifact content is invalid") from error
            if len(content) != expected_size:
                raise RuntimeError(f"Morph proposal stopped-artifact size changed: {raw_path}")
            total_bytes += len(content)
            if total_bytes > PROPOSAL_HANDOFF_MAX_TOTAL_BYTES:
                raise RuntimeError("Morph proposal stopped artifacts exceed their total-byte limit")
            artifacts[raw_path] = content
        return artifacts


def _verified_proposal_runtime_archive(
    *,
    runtime_archive_path: Path,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    runtime_packages: tuple[str, ...],
) -> tuple[Path, bytes]:
    validate_sha256(runtime_archive_sha256)
    validate_sha256(runtime_archive_content_sha256)
    if tuple(runtime_packages) != RUNTIME_PYTHON_PACKAGES:
        raise ProposalMorphRuntimeBuildError("proposal runtime packages must match the governed runtime lock")
    archive_path = Path(runtime_archive_path)
    archive_bytes = _read_regular_file(
        archive_path,
        label="proposal runtime archive",
        max_bytes=_MAX_RUNTIME_ARCHIVE_BYTES,
    )
    if hashlib.sha256(archive_bytes).hexdigest() != runtime_archive_sha256:
        raise ProposalMorphRuntimeBuildError("proposal runtime archive SHA-256 does not match")
    try:
        verify_proposal_runtime_archive(
            archive_path=archive_path,
            expected_archive_sha256=runtime_archive_sha256,
            expected_content_sha256=runtime_archive_content_sha256,
        )
    except ProposalRuntimeArchiveError as error:
        raise ProposalMorphRuntimeBuildError(str(error)) from error
    return archive_path, archive_bytes


def _stage_verified_proposal_context(
    *,
    dockerfile_path: Path,
    context_dir: Path,
) -> tuple[Path, VerifiedProposalTaskBuildContext, Path, Path]:
    source_context = Path(context_dir)
    dockerfile = Path(dockerfile_path)
    try:
        dockerfile_relative_path = dockerfile.relative_to(source_context)
    except ValueError as error:
        raise ProposalMorphRuntimeBuildError("proposal Morph Dockerfile must be inside its build context") from error
    if dockerfile_relative_path != Path("Dockerfile"):
        raise ProposalMorphRuntimeBuildError("proposal Morph Dockerfile must be the manifest-bound Dockerfile")
    try:
        verified_context = verify_default_proposal_task_build_context(source_context)
    except ProposalTaskPackageError as error:
        raise ProposalMorphRuntimeBuildError(str(error)) from error
    staging_root = Path(tempfile.mkdtemp(prefix="aec-bench-proposal-morph-context-"))
    context = staging_root / "environment"
    _write_verified_context(context, verified_context)
    return dockerfile_relative_path, verified_context, staging_root, context


def _read_regular_file(path: Path, *, label: str, max_bytes: int) -> bytes:
    if path.is_symlink():
        raise ProposalMorphRuntimeBuildError(f"{label} must not be a symbolic link")
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProposalMorphRuntimeBuildError(f"{label} cannot be opened safely") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise ProposalMorphRuntimeBuildError(f"{label} must be a regular file")
        if observed.st_size > max_bytes:
            raise ProposalMorphRuntimeBuildError(f"{label} exceeds its byte limit")
        content = bytearray()
        while len(content) <= max_bytes:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, max_bytes + 1 - len(content)),
            )
            if not chunk:
                break
            content.extend(chunk)
        if len(content) > max_bytes:
            raise ProposalMorphRuntimeBuildError(f"{label} exceeds its byte limit")
        after = os.fstat(descriptor)
        if (
            observed.st_dev != after.st_dev
            or observed.st_ino != after.st_ino
            or observed.st_mtime_ns != after.st_mtime_ns
            or observed.st_size != after.st_size
        ):
            raise ProposalMorphRuntimeBuildError(f"{label} changed while it was read")
        return bytes(content)
    finally:
        os.close(descriptor)


def _write_verified_context(
    destination: Path,
    context: VerifiedProposalTaskBuildContext,
) -> None:
    destination.mkdir(parents=True)
    for relative, content in context.payloads:
        target = destination.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def _proposal_runtime_dockerfile(*, runtime_packages: tuple[str, ...]) -> str:
    quoted_packages = " ".join(shlex.quote(package) for package in runtime_packages)
    return "\n".join(
        (
            "FROM aec-bench-task-base",
            "RUN (python3 -m venv /opt/aec-bench-venv || "
            "(apt-get update && apt-get install -y --no-install-recommends python3-venv && "
            "rm -rf /var/lib/apt/lists/* && python3 -m venv /opt/aec-bench-venv))",
            f"RUN /opt/aec-bench-venv/bin/python -m pip install --no-cache-dir {quoted_packages}",
            "COPY proposal-runtime/aec_bench /opt/aec_bench/aec_bench",
            'ENV PATH="/opt/aec-bench-venv/bin:$PATH"',
            "ENV PYTHONPATH=/opt/aec_bench",
            "",
        )
    )


def _proposal_runtime_digest(
    *,
    context_content_sha256: str,
    archive_sha256: str,
    archive_content_sha256: str,
    runtime_packages: tuple[str, ...],
    base_image_id: str,
) -> str:
    digest = hashlib.sha256(b"aecbench.proposal-morph-runtime.v1\0")
    for value in (
        context_content_sha256,
        archive_sha256,
        archive_content_sha256,
        base_image_id,
        *runtime_packages,
    ):
        encoded = value.encode("utf-8")
        digest.update(len(encoded).to_bytes(8, byteorder="big"))
        digest.update(encoded)
    return digest.hexdigest()


def _artifact_limit(path: str) -> int:
    if path in PROPOSAL_EXACT_ARTIFACT_LIMITS:
        return PROPOSAL_EXACT_ARTIFACT_LIMITS[path]
    if path.startswith(f"{PROPOSAL_SESSION_ROOT}/"):
        return PROPOSAL_SESSION_MAX_FILE_BYTES
    raise RuntimeError(f"Morph proposal stopped-artifact inventory contains an unallowlisted path: {path}")


_STOPPED_ARTIFACT_INVENTORY_READER = """\
import base64,json,os,pathlib,stat,sys
policy=json.loads(base64.b64decode(sys.argv[1]).decode())
inventory=[]
for raw_path,limit in policy["exact"].items():
    path=pathlib.Path(raw_path)
    if path.exists() or path.is_symlink():
        observed=path.lstat()
        if not stat.S_ISREG(observed.st_mode):
            raise RuntimeError("proposal handoff artifact is not a regular file: "+raw_path)
        if observed.st_size>int(limit):
            raise RuntimeError("proposal handoff artifact exceeds byte limit: "+raw_path)
        inventory.append({"path":raw_path,"size_bytes":observed.st_size})
tree=pathlib.Path(policy["tree_root"])
tree_file_count=0
tree_total=0
tree_entry_count=0
if tree.exists() or tree.is_symlink():
    tree_stat=tree.lstat()
    if not stat.S_ISDIR(tree_stat.st_mode):
        raise RuntimeError("proposal session artifact root is not a regular directory")
    pending=[tree]
    while pending:
        directory=pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                tree_entry_count+=1
                if tree_entry_count>int(policy["tree_max_entries"]):
                    raise RuntimeError("proposal session artifact entry-count limit exceeded")
                path=pathlib.Path(entry.path)
                observed=entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(observed.st_mode):
                    pending.append(path)
                    continue
                if not stat.S_ISREG(observed.st_mode):
                    raise RuntimeError("proposal session artifact is not regular: "+path.as_posix())
                tree_file_count+=1
                if tree_file_count>int(policy["tree_max_files"]):
                    raise RuntimeError("proposal session artifact file-count limit exceeded")
                if observed.st_size>int(policy["tree_max_file_bytes"]):
                    raise RuntimeError("proposal session artifact exceeds byte limit: "+path.as_posix())
                tree_total+=observed.st_size
                if tree_total>int(policy["tree_max_total_bytes"]):
                    raise RuntimeError("proposal session artifact total-byte limit exceeded")
                inventory.append({"path":path.as_posix(),"size_bytes":observed.st_size})
handoff_total=sum(item["size_bytes"] for item in inventory)
if handoff_total>int(policy["handoff_max_total_bytes"]):
    raise RuntimeError("proposal handoff total-byte limit exceeded")
sys.stdout.write(json.dumps(sorted(inventory,key=lambda item:item["path"]),separators=(",",":")))
"""


_STOPPED_ARTIFACT_FILE_READER = """\
import base64,os,pathlib,stat,sys
raw_path=sys.argv[1]
expected_size=int(sys.argv[2])
limit=int(sys.argv[3])
path=pathlib.Path(raw_path)
before=path.lstat()
if not stat.S_ISREG(before.st_mode):
    raise RuntimeError("proposal handoff artifact is not a regular file: "+raw_path)
if before.st_size!=expected_size or before.st_size>limit:
    raise RuntimeError("proposal handoff artifact size changed: "+raw_path)
flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
fd=os.open(path,flags)
try:
    observed=os.fstat(fd)
    if not stat.S_ISREG(observed.st_mode) or observed.st_dev!=before.st_dev or observed.st_ino!=before.st_ino:
        raise RuntimeError("proposal handoff artifact identity changed: "+raw_path)
    content=b""
    while len(content)<=limit:
        chunk=os.read(fd,min(1048576,limit+1-len(content)))
        if not chunk:
            break
        content+=chunk
    after=os.fstat(fd)
    if observed.st_mtime_ns!=after.st_mtime_ns or observed.st_size!=after.st_size:
        raise RuntimeError("proposal handoff artifact changed while read: "+raw_path)
finally:
    os.close(fd)
if len(content)!=expected_size or len(content)>limit:
    raise RuntimeError("proposal handoff artifact content size changed: "+raw_path)
sys.stdout.write(base64.b64encode(content).decode())
"""
