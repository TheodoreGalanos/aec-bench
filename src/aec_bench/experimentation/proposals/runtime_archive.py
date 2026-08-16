# ABOUTME: Builds the deterministic, allowlisted Python runtime archive for proposal sessions.
# ABOUTME: Keeps graph-bearing task, learning, evaluation, and meta-harness sources outside sandboxes.

from __future__ import annotations

import gzip
import hashlib
import io
import os
import stat
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

_ARCHIVE_PREFIX = PurePosixPath("aec_bench")
_ALLOWED_TREE_PATHS = (
    PurePosixPath("adapters"),
    PurePosixPath("contracts"),
    PurePosixPath("synthesis"),
    PurePosixPath("templates/report"),
    PurePosixPath("trajectory"),
)
_ALLOWED_FILE_PATHS = (
    PurePosixPath("__init__.py"),
    PurePosixPath("harness/__init__.py"),
    PurePosixPath("harness/execution_entrypoint.py"),
    PurePosixPath("harness/execution_payload.py"),
    PurePosixPath("harness/provider_broker.py"),
    PurePosixPath("harness/provider_broker_bootstrap.py"),
    PurePosixPath("harness/provider_broker_runtime.py"),
    PurePosixPath("providers/__init__.py"),
    PurePosixPath("providers/behavioral_llm.py"),
    PurePosixPath("providers/morph_cloud.py"),
    PurePosixPath("templates/__init__.py"),
    PurePosixPath("templates/contracts.py"),
)
_RUNTIME_SUFFIXES = frozenset({".py", ".toml"})
_REQUIRED_FILE_PATHS = frozenset(
    {
        PurePosixPath("__init__.py"),
        PurePosixPath("harness/__init__.py"),
        PurePosixPath("harness/execution_entrypoint.py"),
        PurePosixPath("harness/execution_payload.py"),
        PurePosixPath("harness/provider_broker.py"),
        PurePosixPath("harness/provider_broker_bootstrap.py"),
        PurePosixPath("harness/provider_broker_runtime.py"),
    }
)
_CONTENT_DOMAIN = b"aecbench.proposal-runtime-archive.v1\0"
_MAX_COMPRESSED_ARCHIVE_BYTES = 64 * 1024 * 1024
_MAX_RUNTIME_MEMBERS = 2048
_MAX_RUNTIME_MEMBER_BYTES = 16 * 1024 * 1024
_MAX_RUNTIME_CONTENT_BYTES = 128 * 1024 * 1024


class ProposalRuntimeArchiveError(ValueError):
    """Reject an incomplete or unsafe proposal runtime source surface."""


@dataclass(frozen=True)
class ProposalRuntimeArchive:
    """Content identities and exact member list for one completed archive."""

    path: Path
    members: tuple[str, ...]
    content_sha256: str
    archive_sha256: str


@dataclass(frozen=True)
class _RuntimeMember:
    source: Path
    archive_path: str
    content: bytes


@dataclass(frozen=True)
class _SelectedRuntimeFile:
    source: Path
    inspected: os.stat_result


@dataclass(frozen=True)
class _DescriptorReadErrors:
    open: str
    changed_before: str
    byte_limit: str
    read: str
    changed_during: str


def build_proposal_runtime_archive(
    *,
    package_root: Path,
    archive_path: Path,
) -> ProposalRuntimeArchive:
    """Write one deterministic archive from the fixed proposal-runtime allowlist."""

    root = Path(package_root)
    output = Path(archive_path)
    members = _collect_runtime_members(root)
    content_sha256 = _runtime_content_sha256(members)

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_symlink():
        raise ProposalRuntimeArchiveError(f"archive output must not be a symbolic link: {output}")

    temporary_path: Path | None = None
    try:
        descriptor, raw_temporary_path = tempfile.mkstemp(
            prefix=f".{output.name}.",
            suffix=".tmp",
            dir=output.parent,
        )
        os.close(descriptor)
        temporary_path = Path(raw_temporary_path)
        _write_archive(temporary_path, members)
        temporary_path.replace(output)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)

    return ProposalRuntimeArchive(
        path=output,
        members=tuple(member.archive_path for member in members),
        content_sha256=content_sha256,
        archive_sha256=hashlib.sha256(_read_archive_bytes(output)).hexdigest(),
    )


def verify_proposal_runtime_archive(
    *,
    archive_path: Path,
    expected_archive_sha256: str,
    expected_content_sha256: str,
) -> ProposalRuntimeArchive:
    """Reload one runtime archive and prove exact transport and allowlisted content."""

    archive_file = Path(archive_path)
    _validate_expected_sha256(
        expected_archive_sha256,
        label="expected proposal runtime compressed SHA-256",
    )
    _validate_expected_sha256(
        expected_content_sha256,
        label="expected proposal runtime content SHA-256",
    )
    archive_bytes, observed_archive_sha256 = _verify_archive_transport(
        archive_file=archive_file,
        expected_archive_sha256=expected_archive_sha256,
    )
    payloads = _load_runtime_payloads(
        archive_file=archive_file,
        archive_bytes=archive_bytes,
    )
    member_names = tuple(name for name, _ in payloads)
    _require_runtime_files(member_names)
    observed_content_sha256 = _runtime_payloads_sha256(payloads)
    if observed_content_sha256 != expected_content_sha256:
        raise ProposalRuntimeArchiveError(
            "proposal runtime content SHA-256 does not match the expected allowlisted bytes"
        )
    return ProposalRuntimeArchive(
        path=archive_file,
        members=member_names,
        content_sha256=observed_content_sha256,
        archive_sha256=observed_archive_sha256,
    )


def _verify_archive_transport(
    *,
    archive_file: Path,
    expected_archive_sha256: str,
) -> tuple[bytes, str]:
    archive_bytes = _read_archive_bytes(archive_file)
    observed_archive_sha256 = hashlib.sha256(archive_bytes).hexdigest()
    if observed_archive_sha256 != expected_archive_sha256:
        raise ProposalRuntimeArchiveError("proposal runtime compressed SHA-256 does not match the expected archive")
    return archive_bytes, observed_archive_sha256


def _read_archive_bytes(archive_file: Path) -> bytes:
    if archive_file.is_symlink():
        raise ProposalRuntimeArchiveError(f"proposal runtime archive must not be a symbolic link: {archive_file}")
    try:
        archive_stat = archive_file.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalRuntimeArchiveError(f"proposal runtime archive cannot be inspected: {archive_file}") from error
    if not stat.S_ISREG(archive_stat.st_mode):
        raise ProposalRuntimeArchiveError(f"proposal runtime archive must be a regular file: {archive_file}")
    if archive_stat.st_size > _MAX_COMPRESSED_ARCHIVE_BYTES:
        raise ProposalRuntimeArchiveError("proposal runtime archive exceeds its compressed-byte limit")
    return _read_descriptor_bound_bytes(
        path=archive_file,
        inspected=archive_stat,
        max_bytes=_MAX_COMPRESSED_ARCHIVE_BYTES,
        errors=_DescriptorReadErrors(
            open=f"proposal runtime archive cannot be opened safely: {archive_file}",
            changed_before=f"proposal runtime archive changed before it was read: {archive_file}",
            byte_limit="proposal runtime archive exceeds its compressed-byte limit",
            read=f"proposal runtime archive cannot be read safely: {archive_file}",
            changed_during=f"proposal runtime archive changed while it was read: {archive_file}",
        ),
    )


def _load_runtime_payloads(
    *,
    archive_file: Path,
    archive_bytes: bytes,
) -> list[tuple[str, bytes]]:
    try:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as archive:
            members = archive.getmembers()
            _validate_archive_member_sequence(members)
            return _read_archive_payloads(archive=archive, members=members)
    except (tarfile.TarError, OSError, EOFError) as error:
        raise ProposalRuntimeArchiveError(f"proposal runtime archive cannot be decoded: {archive_file}") from error


def _validate_archive_member_sequence(members: list[tarfile.TarInfo]) -> None:
    if len(members) > _MAX_RUNTIME_MEMBERS:
        raise ProposalRuntimeArchiveError("proposal runtime archive exceeds its member-count limit")
    names = tuple(member.name for member in members)
    if names != tuple(sorted(names)) or len(names) != len(set(names)):
        raise ProposalRuntimeArchiveError("proposal runtime archive members must be sorted and unique")


def _read_archive_payloads(
    *,
    archive: tarfile.TarFile,
    members: list[tarfile.TarInfo],
) -> list[tuple[str, bytes]]:
    payloads: list[tuple[str, bytes]] = []
    total_content_bytes = 0
    for member in members:
        _validate_archive_member(member)
        total_content_bytes += member.size
        if total_content_bytes > _MAX_RUNTIME_CONTENT_BYTES:
            raise ProposalRuntimeArchiveError("proposal runtime archive exceeds its uncompressed-byte limit")
        payloads.append((member.name, _read_archive_member(archive=archive, member=member)))
    return payloads


def _validate_archive_member(member: tarfile.TarInfo) -> None:
    if not member.isfile() or member.issym() or member.islnk():
        raise ProposalRuntimeArchiveError(f"proposal runtime archive member must be a regular file: {member.name}")
    if not _archive_member_is_allowlisted(member.name):
        raise ProposalRuntimeArchiveError(
            f"proposal runtime archive member is outside the proposal runtime allowlist: {member.name}"
        )
    if member.size > _MAX_RUNTIME_MEMBER_BYTES:
        raise ProposalRuntimeArchiveError(f"proposal runtime archive member exceeds its byte limit: {member.name}")


def _read_archive_member(
    *,
    archive: tarfile.TarFile,
    member: tarfile.TarInfo,
) -> bytes:
    extracted = archive.extractfile(member)
    if extracted is None:
        raise ProposalRuntimeArchiveError(f"proposal runtime archive member cannot be read: {member.name}")
    content = extracted.read(_MAX_RUNTIME_MEMBER_BYTES + 1)
    if len(content) > _MAX_RUNTIME_MEMBER_BYTES:
        raise ProposalRuntimeArchiveError(f"proposal runtime archive member exceeds its byte limit: {member.name}")
    return content


def _require_runtime_files(member_names: tuple[str, ...]) -> None:
    missing = tuple(
        sorted(
            (_ARCHIVE_PREFIX / path).as_posix()
            for path in _REQUIRED_FILE_PATHS
            if (_ARCHIVE_PREFIX / path).as_posix() not in member_names
        )
    )
    if missing:
        raise ProposalRuntimeArchiveError("required proposal runtime files are missing: " + ", ".join(missing))


def _collect_runtime_members(package_root: Path) -> tuple[_RuntimeMember, ...]:
    _validate_package_root(package_root)
    selected: dict[PurePosixPath, _SelectedRuntimeFile] = {}
    _collect_allowed_runtime_files(package_root=package_root, selected=selected)
    _collect_allowed_runtime_trees(package_root=package_root, selected=selected)
    _require_selected_runtime_files(selected)
    runtime_members = tuple(
        _materialize_runtime_member(
            relative_path=relative_path,
            selected_file=selected_file,
        )
        for relative_path, selected_file in sorted(selected.items(), key=lambda item: item[0].as_posix())
    )
    _validate_runtime_member_collection(runtime_members)
    return runtime_members


def _validate_package_root(package_root: Path) -> None:
    if package_root.is_symlink():
        raise ProposalRuntimeArchiveError(f"package root must not be a symbolic link: {package_root}")
    if not package_root.is_dir():
        raise ProposalRuntimeArchiveError(f"package root is not a directory: {package_root}")


def _collect_allowed_runtime_files(
    *,
    package_root: Path,
    selected: dict[PurePosixPath, _SelectedRuntimeFile],
) -> None:
    for relative_path in _ALLOWED_FILE_PATHS:
        source = package_root / relative_path
        if source.exists() or source.is_symlink():
            _select_regular_file(selected, relative_path=relative_path, source=source)


def _collect_allowed_runtime_trees(
    *,
    package_root: Path,
    selected: dict[PurePosixPath, _SelectedRuntimeFile],
) -> None:
    for relative_root in _ALLOWED_TREE_PATHS:
        source_root = package_root / relative_root
        if not source_root.exists() and not source_root.is_symlink():
            continue
        _collect_runtime_tree(
            package_root=package_root,
            source_root=source_root,
            selected=selected,
        )


def _collect_runtime_tree(
    *,
    package_root: Path,
    source_root: Path,
    selected: dict[PurePosixPath, _SelectedRuntimeFile],
) -> None:
    if source_root.is_symlink():
        raise ProposalRuntimeArchiveError(f"allowlisted runtime tree must not be a symbolic link: {source_root}")
    if not source_root.is_dir():
        raise ProposalRuntimeArchiveError(f"allowlisted runtime tree is not a directory: {source_root}")
    for source in sorted(source_root.rglob("*")):
        relative_path = PurePosixPath(source.relative_to(package_root).as_posix())
        if "node_modules" in relative_path.parts:
            continue
        if source.is_symlink():
            raise ProposalRuntimeArchiveError(f"allowlisted runtime surface contains a symbolic link: {relative_path}")
        if source.is_dir():
            continue
        if _runtime_source_is_ignored(source=source, relative_path=relative_path):
            continue
        _select_regular_file(selected, relative_path=relative_path, source=source)


def _runtime_source_is_ignored(
    *,
    source: Path,
    relative_path: PurePosixPath,
) -> bool:
    return (
        "__pycache__" in relative_path.parts
        or source.suffix in {".pyc", ".pyo"}
        or source.suffix not in _RUNTIME_SUFFIXES
    )


def _require_selected_runtime_files(
    selected: dict[PurePosixPath, _SelectedRuntimeFile],
) -> None:
    missing = tuple(sorted(str(path) for path in _REQUIRED_FILE_PATHS - selected.keys()))
    if missing:
        raise ProposalRuntimeArchiveError("required proposal runtime files are missing: " + ", ".join(missing))


def _validate_runtime_member_collection(
    runtime_members: tuple[_RuntimeMember, ...],
) -> None:
    archive_paths = tuple(member.archive_path for member in runtime_members)
    if len(archive_paths) != len(set(archive_paths)):
        raise ProposalRuntimeArchiveError("proposal runtime archive member paths must be unique")
    if len(runtime_members) > _MAX_RUNTIME_MEMBERS:
        raise ProposalRuntimeArchiveError("proposal runtime archive exceeds its member-count limit")
    if sum(len(member.content) for member in runtime_members) > _MAX_RUNTIME_CONTENT_BYTES:
        raise ProposalRuntimeArchiveError("proposal runtime archive exceeds its uncompressed-byte limit")


def _select_regular_file(
    selected: dict[PurePosixPath, _SelectedRuntimeFile],
    *,
    relative_path: PurePosixPath,
    source: Path,
) -> None:
    inspected = _inspect_runtime_source(
        relative_path=relative_path,
        source=source,
    )
    if relative_path in selected:
        raise ProposalRuntimeArchiveError(f"duplicate allowlisted runtime member: {relative_path}")
    selected[relative_path] = _SelectedRuntimeFile(
        source=source,
        inspected=inspected,
    )


def _inspect_runtime_source(
    *,
    relative_path: PurePosixPath,
    source: Path,
) -> os.stat_result:
    if source.is_symlink():
        raise ProposalRuntimeArchiveError(f"allowlisted runtime file must not be a symbolic link: {relative_path}")
    try:
        source_stat = source.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalRuntimeArchiveError(f"allowlisted runtime file cannot be inspected: {relative_path}") from error
    if not stat.S_ISREG(source_stat.st_mode):
        raise ProposalRuntimeArchiveError(f"allowlisted runtime member is not a regular file: {relative_path}")
    if source_stat.st_size > _MAX_RUNTIME_MEMBER_BYTES:
        raise ProposalRuntimeArchiveError(f"allowlisted runtime member exceeds its byte limit: {relative_path}")
    return source_stat


def _materialize_runtime_member(
    *,
    relative_path: PurePosixPath,
    selected_file: _SelectedRuntimeFile,
) -> _RuntimeMember:
    content = _read_descriptor_bound_bytes(
        path=selected_file.source,
        inspected=selected_file.inspected,
        max_bytes=_MAX_RUNTIME_MEMBER_BYTES,
        errors=_DescriptorReadErrors(
            open=f"allowlisted runtime file cannot be opened safely: {relative_path}",
            changed_before=f"allowlisted runtime file changed before it was read: {relative_path}",
            byte_limit=f"allowlisted runtime member exceeds its byte limit: {relative_path}",
            read=f"allowlisted runtime file cannot be read safely: {relative_path}",
            changed_during=f"allowlisted runtime file changed while it was read: {relative_path}",
        ),
    )
    return _RuntimeMember(
        source=selected_file.source,
        archive_path=(_ARCHIVE_PREFIX / relative_path).as_posix(),
        content=content,
    )


def _read_descriptor_bound_bytes(
    *,
    path: Path,
    inspected: os.stat_result,
    max_bytes: int,
    errors: _DescriptorReadErrors,
) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise ProposalRuntimeArchiveError(errors.open) from error
    try:
        return _read_open_descriptor(
            descriptor=descriptor,
            inspected=inspected,
            max_bytes=max_bytes,
            errors=errors,
        )
    finally:
        os.close(descriptor)


def _read_open_descriptor(
    *,
    descriptor: int,
    inspected: os.stat_result,
    max_bytes: int,
    errors: _DescriptorReadErrors,
) -> bytes:
    try:
        observed = os.fstat(descriptor)
    except OSError as error:
        raise ProposalRuntimeArchiveError(errors.read) from error
    if not stat.S_ISREG(observed.st_mode) or not _same_file_snapshot(inspected, observed):
        raise ProposalRuntimeArchiveError(errors.changed_before)
    if observed.st_size > max_bytes:
        raise ProposalRuntimeArchiveError(errors.byte_limit)
    content = _read_bounded_descriptor(
        descriptor=descriptor,
        max_bytes=max_bytes,
        errors=errors,
    )
    try:
        after = os.fstat(descriptor)
    except OSError as error:
        raise ProposalRuntimeArchiveError(errors.read) from error
    if not _same_file_snapshot(observed, after):
        raise ProposalRuntimeArchiveError(errors.changed_during)
    return content


def _read_bounded_descriptor(
    *,
    descriptor: int,
    max_bytes: int,
    errors: _DescriptorReadErrors,
) -> bytes:
    content = bytearray()
    try:
        while len(content) <= max_bytes:
            chunk = os.read(
                descriptor,
                min(1024 * 1024, max_bytes + 1 - len(content)),
            )
            if not chunk:
                break
            content.extend(chunk)
    except OSError as error:
        raise ProposalRuntimeArchiveError(errors.read) from error
    if len(content) > max_bytes:
        raise ProposalRuntimeArchiveError(errors.byte_limit)
    return bytes(content)


def _same_file_identity(
    left: os.stat_result,
    right: os.stat_result,
) -> bool:
    return left.st_dev == right.st_dev and left.st_ino == right.st_ino


def _same_file_snapshot(
    before: os.stat_result,
    after: os.stat_result,
) -> bool:
    return (
        _same_file_identity(before, after)
        and before.st_size == after.st_size
        and before.st_mtime_ns == after.st_mtime_ns
        and before.st_ctime_ns == after.st_ctime_ns
    )


def _runtime_content_sha256(members: tuple[_RuntimeMember, ...]) -> str:
    return _runtime_payloads_sha256([(member.archive_path, member.content) for member in members])


def _runtime_payloads_sha256(payloads: list[tuple[str, bytes]]) -> str:
    digest = hashlib.sha256()
    digest.update(_CONTENT_DOMAIN)
    for archive_path, content in payloads:
        path_bytes = archive_path.encode("utf-8")
        digest.update(len(path_bytes).to_bytes(8, byteorder="big"))
        digest.update(path_bytes)
        digest.update(len(content).to_bytes(8, byteorder="big"))
        digest.update(content)
    return digest.hexdigest()


def _archive_member_is_allowlisted(member_name: str) -> bool:
    path = PurePosixPath(member_name)
    if (
        path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or not path.is_relative_to(_ARCHIVE_PREFIX)
    ):
        return False
    relative = path.relative_to(_ARCHIVE_PREFIX)
    if relative in _ALLOWED_FILE_PATHS:
        return True
    return (
        relative.suffix in _RUNTIME_SUFFIXES
        and "__pycache__" not in relative.parts
        and any(relative.is_relative_to(root) for root in _ALLOWED_TREE_PATHS)
    )


def _validate_expected_sha256(value: str, *, label: str) -> None:
    if len(value) != 64:
        raise ProposalRuntimeArchiveError(f"{label} must contain 64 lowercase hexadecimal characters")
    try:
        parsed = bytes.fromhex(value)
    except ValueError as error:
        raise ProposalRuntimeArchiveError(f"{label} must contain 64 lowercase hexadecimal characters") from error
    if len(parsed) != 32 or value != value.lower():
        raise ProposalRuntimeArchiveError(f"{label} must contain 64 lowercase hexadecimal characters")


def _write_archive(path: Path, members: tuple[_RuntimeMember, ...]) -> None:
    with path.open("wb") as raw_archive:
        with gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=raw_archive,
            compresslevel=9,
            mtime=0,
        ) as compressed:
            with tarfile.open(
                fileobj=compressed,
                mode="w",
                format=tarfile.PAX_FORMAT,
            ) as archive:
                for member in members:
                    info = tarfile.TarInfo(name=member.archive_path)
                    info.size = len(member.content)
                    info.mode = 0o644
                    info.mtime = 0
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.type = tarfile.REGTYPE
                    archive.addfile(info, io.BytesIO(member.content))
