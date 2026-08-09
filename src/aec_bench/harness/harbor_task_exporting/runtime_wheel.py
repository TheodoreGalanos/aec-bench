# ABOUTME: Builds and validates the deterministic verifier-only Harbor runtime wheel.
# ABOUTME: Binds archive structure and bytes to one descriptor-backed source snapshot.

from __future__ import annotations

import base64
import csv
import hashlib
import io
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile, ZipInfo

from .constants import (
    CANONICAL_PACKAGE_ROOT,
    MAX_CANONICAL_SOURCE_FILE_BYTES,
    WHEEL_TIMESTAMP,
)
from .stable_io import (
    RegularFileSnapshot,
    canonical_sha256,
    file_sha256,
    read_stable_regular_file,
)


@dataclass(frozen=True)
class RuntimeWheel:
    path: Path
    sha256: str
    source_tree_sha256: str


def build_verifier_runtime_wheel(*, project_root: Path, output_dir: Path) -> RuntimeWheel:
    """Build a deterministic verifier-only-stage wheel from the canonical source tree."""
    pyproject = tomllib.loads((project_root / "pyproject.toml").read_text(encoding="utf-8"))
    project = cast(dict[str, Any], pyproject["project"])
    version = str(project["version"])
    wheel_name = f"aec_bench_verifier_runtime-{version}-py3-none-any.whl"
    wheel_path = output_dir / wheel_name
    package_root = project_root / "src" / "aec_bench"
    source_payloads = _canonical_source_payloads(package_root)
    source_tree_sha256 = _source_tree_sha256(source_payloads)

    records: list[tuple[str, str, int]] = []
    with ZipFile(wheel_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as wheel:
        for archive_path, content in source_payloads:
            _wheel_write(wheel, records, archive_path, content)
        dist_info = f"aec_bench_verifier_runtime-{version}.dist-info"
        _wheel_write(wheel, records, f"{dist_info}/METADATA", _wheel_metadata(version))
        _wheel_write(wheel, records, f"{dist_info}/WHEEL", _wheel_descriptor().encode("utf-8"))
        _wheel_write_record(wheel, f"{dist_info}/RECORD", records)

    return RuntimeWheel(
        path=wheel_path,
        sha256=file_sha256(wheel_path),
        source_tree_sha256=source_tree_sha256,
    )


def validate_verifier_runtime_wheel(
    runtime_wheel: RegularFileSnapshot,
    verifier: dict[str, Any],
) -> None:
    canonical_payloads = _canonical_source_payloads(CANONICAL_PACKAGE_ROOT)
    canonical_source_sha256 = _source_tree_sha256(canonical_payloads)
    if verifier["source_tree_sha256"] != canonical_source_sha256:
        raise ValueError("verifier runtime does not match the canonical verifier source tree")

    try:
        with ZipFile(io.BytesIO(runtime_wheel.payload)) as wheel:
            names = _validated_wheel_member_names(wheel)
            source_names = {archive_path for archive_path, _ in canonical_payloads}
            dist_info, version = _validated_wheel_identity(
                names=names,
                source_names=source_names,
                wheel_filename=runtime_wheel.path.name,
            )
            _validate_wheel_content(
                wheel=wheel,
                names=names,
                canonical_payloads=canonical_payloads,
                source_names=source_names,
                dist_info=dist_info,
                version=version,
            )
    except BadZipFile as exc:
        raise ValueError("verifier runtime wheel is invalid") from exc


def _canonical_source_payloads(package_root: Path) -> list[tuple[str, bytes]]:
    root = Path(package_root)
    candidates = [path for path in sorted(root.rglob("*")) if not _is_local_frontend_dependency(path, root=root)]
    unsafe_links = [path for path in candidates if path.is_symlink()]
    if unsafe_links:
        raise ValueError(f"canonical aec-bench source package contains a symbolic link: {unsafe_links[0]}")
    source_files = [
        path
        for path in candidates
        if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"}
    ]
    if not source_files:
        raise ValueError("canonical aec-bench source package is empty")
    return [
        (
            path.relative_to(root.parent).as_posix(),
            read_stable_regular_file(
                path,
                label=f"canonical verifier source {path.relative_to(package_root)}",
                max_bytes=MAX_CANONICAL_SOURCE_FILE_BYTES,
            ).payload,
        )
        for path in source_files
    ]


def _is_local_frontend_dependency(path: Path, *, root: Path) -> bool:
    return path.relative_to(root).parts[:3] == ("web", "frontend", "node_modules")


def _source_tree_sha256(source_payloads: list[tuple[str, bytes]]) -> str:
    return canonical_sha256(
        {archive_path: hashlib.sha256(content).hexdigest() for archive_path, content in source_payloads}
    )


def _wheel_metadata(version: str) -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        "Name: aec-bench-verifier-runtime\n"
        f"Version: {version}\n"
        "Summary: Isolated Harbor verifier-stage runtime for AEC-Bench lifecycle tasks\n"
        "Requires-Python: >=3.13\n\n"
    ).encode()


def _validated_wheel_member_names(wheel: ZipFile) -> list[str]:
    members = wheel.infolist()
    names = [member.filename for member in members]
    if len(names) != len(set(names)):
        raise ValueError("verifier runtime wheel contains duplicate archive members")
    if any(_unsafe_wheel_member_name(name) for name in names):
        raise ValueError("verifier runtime wheel contains an unsafe archive member")
    if any((member.external_attr >> 16) != 0o100644 for member in members):
        raise ValueError("verifier runtime wheel contains a non-canonical file mode")
    return names


def _unsafe_wheel_member_name(name: str) -> bool:
    path = Path(name)
    return "\\" in name or path.is_absolute() or ".." in path.parts or name.endswith("/")


def _validated_wheel_identity(
    *,
    names: list[str],
    source_names: set[str],
    wheel_filename: str,
) -> tuple[str, str]:
    dist_names = set(names) - source_names
    dist_roots = {name.partition("/")[0] for name in dist_names}
    if len(dist_roots) != 1:
        raise ValueError("verifier runtime wheel does not have one canonical dist-info directory")
    dist_info = dist_roots.pop()
    prefix = "aec_bench_verifier_runtime-"
    suffix = ".dist-info"
    if not dist_info.startswith(prefix) or not dist_info.endswith(suffix):
        raise ValueError("verifier runtime wheel dist-info identity is not canonical")
    version = dist_info.removeprefix(prefix).removesuffix(suffix)
    if wheel_filename != f"aec_bench_verifier_runtime-{version}-py3-none-any.whl":
        raise ValueError("verifier runtime wheel filename is not canonical")
    return dist_info, version


def _validate_wheel_content(
    *,
    wheel: ZipFile,
    names: list[str],
    canonical_payloads: list[tuple[str, bytes]],
    source_names: set[str],
    dist_info: str,
    version: str,
) -> None:
    expected_names = source_names | {
        f"{dist_info}/METADATA",
        f"{dist_info}/RECORD",
        f"{dist_info}/WHEEL",
    }
    if set(names) != expected_names:
        raise ValueError("verifier runtime wheel contains non-canonical executable content")
    expected_records = _validate_wheel_source_payloads(
        wheel=wheel,
        canonical_payloads=canonical_payloads,
    )
    _validate_wheel_distribution_payloads(
        wheel=wheel,
        dist_info=dist_info,
        version=version,
        expected_records=expected_records,
    )


def _validate_wheel_source_payloads(
    *,
    wheel: ZipFile,
    canonical_payloads: list[tuple[str, bytes]],
) -> list[tuple[str, str, int]]:
    expected_records: list[tuple[str, str, int]] = []
    for archive_path, expected_content in canonical_payloads:
        if wheel.read(archive_path) != expected_content:
            raise ValueError("verifier runtime wheel does not match the canonical verifier source")
        expected_records.append(_wheel_record(archive_path, expected_content))
    return expected_records


def _validate_wheel_distribution_payloads(
    *,
    wheel: ZipFile,
    dist_info: str,
    version: str,
    expected_records: list[tuple[str, str, int]],
) -> None:
    metadata_path = f"{dist_info}/METADATA"
    metadata = _wheel_metadata(version)
    if wheel.read(metadata_path) != metadata:
        raise ValueError("verifier runtime wheel metadata is not canonical")
    expected_records.append(_wheel_record(metadata_path, metadata))
    descriptor_path = f"{dist_info}/WHEEL"
    descriptor = _wheel_descriptor().encode()
    if wheel.read(descriptor_path) != descriptor:
        raise ValueError("verifier runtime wheel descriptor is not canonical")
    expected_records.append(_wheel_record(descriptor_path, descriptor))
    record_path = f"{dist_info}/RECORD"
    if wheel.read(record_path) != _wheel_record_payload(record_path, expected_records):
        raise ValueError("verifier runtime wheel record is not canonical")


def _wheel_write(
    wheel: ZipFile,
    records: list[tuple[str, str, int]],
    archive_path: str,
    content: bytes,
) -> None:
    info = ZipInfo(archive_path, date_time=WHEEL_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    wheel.writestr(info, content)
    records.append(_wheel_record(archive_path, content))


def _wheel_write_record(
    wheel: ZipFile,
    record_path: str,
    records: list[tuple[str, str, int]],
) -> None:
    content = _wheel_record_payload(record_path, records)
    info = ZipInfo(record_path, date_time=WHEEL_TIMESTAMP)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    wheel.writestr(info, content)


def _wheel_record(archive_path: str, content: bytes) -> tuple[str, str, int]:
    digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).rstrip(b"=").decode("ascii")
    return archive_path, f"sha256={digest}", len(content)


def _wheel_record_payload(record_path: str, records: list[tuple[str, str, int]]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerows(records)
    writer.writerow((record_path, "", ""))
    return buffer.getvalue().encode()


def _wheel_descriptor() -> str:
    return (
        "Wheel-Version: 1.0\nGenerator: aec-bench Harbor verifier exporter\nRoot-Is-Purelib: true\nTag: py3-none-any\n"
    )
