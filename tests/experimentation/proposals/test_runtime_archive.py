# ABOUTME: Proves the proposal-session Python runtime archive is deterministic and physically minimal.
# ABOUTME: Guards executable imports against graph-bearing files, cache artifacts, and symbolic links.

from __future__ import annotations

import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

from aec_bench.experimentation.proposals.runtime_archive import (
    ProposalRuntimeArchiveError,
    build_proposal_runtime_archive,
    verify_proposal_runtime_archive,
)

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE_ROOT = _PROJECT_ROOT / "src" / "aec_bench"
_FORBIDDEN_PREFIXES = (
    "aec_bench/lifecycles/",
    "aec_bench/worlds/",
    "aec_bench/generation/",
    "aec_bench/evaluation/",
    "aec_bench/evolution/",
    "aec_bench/templates/builtin/",
)


def test_real_runtime_archive_is_deterministic_allowlisted_and_importable(tmp_path: Path) -> None:
    first = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "first.tar.gz",
    )
    second = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "second.tar.gz",
    )

    assert first.members == second.members
    assert first.content_sha256 == second.content_sha256
    assert first.archive_sha256 == second.archive_sha256
    assert first.path.read_bytes() == second.path.read_bytes()
    assert first.members == tuple(sorted(first.members))
    assert {
        "aec_bench/__init__.py",
        "aec_bench/adapters/rlm/adapter.py",
        "aec_bench/contracts/output_completion.py",
        "aec_bench/harness/execution_entrypoint.py",
        "aec_bench/harness/execution_payload.py",
        "aec_bench/harness/provider_broker.py",
        "aec_bench/harness/provider_broker_bootstrap.py",
        "aec_bench/harness/provider_broker_runtime.py",
        "aec_bench/trajectory/writer.py",
    }.issubset(first.members)

    with tarfile.open(first.path, mode="r:gz") as archive:
        archive_members = archive.getmembers()
        assert tuple(member.name for member in archive_members) == first.members
        assert all(member.isfile() for member in archive_members)
        assert all(not member.issym() and not member.islnk() for member in archive_members)

    assert not any(member.startswith(prefix) for member in first.members for prefix in _FORBIDDEN_PREFIXES)
    assert not any(member.startswith("aec_bench/experimentation/proposals/morph/") for member in first.members)
    assert not any(
        "__pycache__" in Path(member).parts or Path(member).suffix in {".pyc", ".pyo"} for member in first.members
    )

    extracted = tmp_path / "extracted"
    extracted.mkdir()
    with tarfile.open(first.path, mode="r:gz") as archive:
        archive.extractall(extracted, filter="data")

    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    probe = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import importlib, pathlib, sys;"
                "root=pathlib.Path(sys.argv[1]).resolve();"
                "sys.path.insert(0,str(root));"
                "entrypoint=importlib.import_module('aec_bench.harness.execution_entrypoint');"
                "bootstrap=importlib.import_module('aec_bench.harness.provider_broker_bootstrap');"
                "assert pathlib.Path(entrypoint.__file__).resolve().is_relative_to(root);"
                "assert pathlib.Path(bootstrap.__file__).resolve().is_relative_to(root);"
                "registry=entrypoint.default_execution_driver_registry(workspace_dir=root);"
                "assert set(registry.drivers)=="
                "{'direct','tool_loop','pydantic_ai','rlm','lambda-rlm','lambda_rlm'}"
            ),
            str(extracted),
        ],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert probe.returncode == 0, probe.stderr


def test_built_runtime_archive_reloads_against_both_exact_identities(
    tmp_path: Path,
) -> None:
    built = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "runtime.tar.gz",
    )

    verified = verify_proposal_runtime_archive(
        archive_path=built.path,
        expected_archive_sha256=built.archive_sha256,
        expected_content_sha256=built.content_sha256,
    )

    assert verified == built


def test_runtime_archive_verification_rejects_path_swap_before_descriptor_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    built = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "runtime.tar.gz",
    )
    replacement = tmp_path / "replacement.tar.gz"
    replacement.write_bytes(built.path.read_bytes())
    _replace_path_with_symlink_on_open(
        monkeypatch,
        source=built.path,
        target=replacement,
    )

    with pytest.raises(
        ProposalRuntimeArchiveError,
        match="cannot be opened safely|changed before it was read",
    ):
        verify_proposal_runtime_archive(
            archive_path=built.path,
            expected_archive_sha256=built.archive_sha256,
            expected_content_sha256=built.content_sha256,
        )


def test_runtime_archive_verification_validates_identities_before_archive_path(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "missing.tar.gz"

    with pytest.raises(
        ProposalRuntimeArchiveError,
        match="expected proposal runtime compressed SHA-256",
    ):
        verify_proposal_runtime_archive(
            archive_path=archive_path,
            expected_archive_sha256="INVALID",
            expected_content_sha256="INVALID",
        )

    with pytest.raises(
        ProposalRuntimeArchiveError,
        match="expected proposal runtime content SHA-256",
    ):
        verify_proposal_runtime_archive(
            archive_path=archive_path,
            expected_archive_sha256="0" * 64,
            expected_content_sha256="INVALID",
        )


def test_runtime_archive_requires_broker_execution_modules(tmp_path: Path) -> None:
    package_root = _minimal_package(tmp_path / "package")
    (package_root / "harness" / "provider_broker.py").unlink()

    with pytest.raises(ProposalRuntimeArchiveError, match="provider_broker.py"):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def test_runtime_archive_verification_rejects_transport_tamper(
    tmp_path: Path,
) -> None:
    built = build_proposal_runtime_archive(
        package_root=_PACKAGE_ROOT,
        archive_path=tmp_path / "runtime.tar.gz",
    )
    built.path.write_bytes(built.path.read_bytes() + b"transport-tamper")

    with pytest.raises(ProposalRuntimeArchiveError, match="compressed SHA-256"):
        verify_proposal_runtime_archive(
            archive_path=built.path,
            expected_archive_sha256=built.archive_sha256,
            expected_content_sha256=built.content_sha256,
        )


def test_runtime_archive_verification_rejects_non_allowlisted_member(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "unsafe.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        payload = b"FORBIDDEN = True\n"
        info = tarfile.TarInfo("aec_bench/meta_harness/leak.py")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    with pytest.raises(ProposalRuntimeArchiveError, match="outside the proposal runtime allowlist"):
        verify_proposal_runtime_archive(
            archive_path=archive_path,
            expected_archive_sha256=_sha256(archive_path.read_bytes()),
            expected_content_sha256="0" * 64,
        )


def test_runtime_archive_verification_rejects_compressed_decompression_bomb(
    tmp_path: Path,
) -> None:
    archive_path = tmp_path / "oversized.tar.gz"
    with tarfile.open(archive_path, mode="w:gz") as archive:
        payload = b"0" * (16 * 1024 * 1024 + 1)
        info = tarfile.TarInfo("aec_bench/adapters/bomb.py")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))

    assert archive_path.stat().st_size < 64 * 1024
    with pytest.raises(ProposalRuntimeArchiveError, match="member exceeds its byte limit"):
        verify_proposal_runtime_archive(
            archive_path=archive_path,
            expected_archive_sha256=_sha256(archive_path.read_bytes()),
            expected_content_sha256="0" * 64,
        )


def test_archive_content_hash_changes_only_when_allowlisted_content_changes(tmp_path: Path) -> None:
    package_root = _minimal_package(tmp_path / "package")
    first = build_proposal_runtime_archive(
        package_root=package_root,
        archive_path=tmp_path / "first.tar.gz",
    )

    probe = package_root / "adapters" / "probe.py"
    probe.write_text("VALUE = 2\n", encoding="utf-8")
    second = build_proposal_runtime_archive(
        package_root=package_root,
        archive_path=tmp_path / "second.tar.gz",
    )

    assert first.members == second.members
    assert first.content_sha256 != second.content_sha256
    assert first.archive_sha256 != second.archive_sha256


def test_archive_physically_excludes_forbidden_trees_and_cache_files(tmp_path: Path) -> None:
    package_root = _minimal_package(tmp_path / "package")
    forbidden_files = (
        package_root / "engineering" / "hydraulics" / "kernel.py",
        package_root / "lifecycles" / "catalogue.py",
        package_root / "worlds" / "catalogue.py",
        package_root / "generation" / "gold.py",
        package_root / "evaluation" / "critic.py",
        package_root / "evolution" / "optimizer.py",
        package_root / "templates" / "builtin" / "task.py",
        package_root / "adapters" / "__pycache__" / "probe.cpython-313.pyc",
    )
    for path in forbidden_files:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"forbidden")

    result = build_proposal_runtime_archive(
        package_root=package_root,
        archive_path=tmp_path / "runtime.tar.gz",
    )

    assert not any(member.startswith(prefix) for member in result.members for prefix in _FORBIDDEN_PREFIXES)
    assert not any("__pycache__" in Path(member).parts for member in result.members)


def test_archive_rejects_symbolic_links_on_the_allowlisted_surface(tmp_path: Path) -> None:
    package_root = _minimal_package(tmp_path / "package")
    target = package_root / "adapters" / "target.py"
    target.write_text("VALUE = 1\n", encoding="utf-8")
    (package_root / "adapters" / "alias.py").symlink_to(target)

    with pytest.raises(ProposalRuntimeArchiveError, match="symbolic link"):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def test_archive_rejects_allowlisted_source_swapped_before_descriptor_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _minimal_package(tmp_path / "package")
    source = package_root / "adapters" / "probe.py"
    replacement = tmp_path / "replacement.py"
    replacement.write_text("FORBIDDEN = True\n", encoding="utf-8")
    _replace_path_with_symlink_on_open(
        monkeypatch,
        source=source,
        target=replacement,
    )

    with pytest.raises(
        ProposalRuntimeArchiveError,
        match="cannot be opened safely|changed before it was read",
    ):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def test_archive_rejects_allowlisted_source_changed_during_descriptor_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _minimal_package(tmp_path / "package")
    source = package_root / "adapters" / "probe.py"
    _mutate_path_after_descriptor_read(
        monkeypatch,
        source=source,
        replacement=b"CHANGED WHILE READ\n",
    )

    with pytest.raises(ProposalRuntimeArchiveError, match="changed while it was read"):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def test_archive_rejects_allowlisted_source_identity_replaced_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _minimal_package(tmp_path / "package")
    source = package_root / "adapters" / "probe.py"
    _replace_path_content_on_open(
        monkeypatch,
        source=source,
        replacement=b"FORBIDDEN = True\n",
    )

    with pytest.raises(ProposalRuntimeArchiveError, match="changed before it was read"):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def test_archive_rejects_allowlisted_source_modified_in_place_before_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _minimal_package(tmp_path / "package")
    source = package_root / "adapters" / "probe.py"
    _mutate_path_content_on_open(
        monkeypatch,
        source=source,
        replacement=b"FORBIDDEN = True\n",
    )

    with pytest.raises(ProposalRuntimeArchiveError, match="changed before it was read"):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def test_required_runtime_file_error_precedes_deferred_source_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = _minimal_package(tmp_path / "package")
    (package_root / "harness" / "provider_broker.py").unlink()
    source = package_root / "adapters" / "probe.py"
    replacement = tmp_path / "replacement.py"
    replacement.write_text("FORBIDDEN = True\n", encoding="utf-8")
    _replace_path_with_symlink_on_open(
        monkeypatch,
        source=source,
        target=replacement,
    )

    with pytest.raises(
        ProposalRuntimeArchiveError, match="required proposal runtime files are missing:.*provider_broker"
    ):
        build_proposal_runtime_archive(
            package_root=package_root,
            archive_path=tmp_path / "runtime.tar.gz",
        )


def _minimal_package(package_root: Path) -> Path:
    files = {
        "__init__.py": "",
        "adapters/__init__.py": "",
        "adapters/probe.py": "VALUE = 1\n",
        "contracts/__init__.py": "",
        "harness/__init__.py": "",
        "harness/execution_entrypoint.py": "ENTRYPOINT = True\n",
        "harness/execution_payload.py": "PAYLOAD = True\n",
        "harness/provider_broker.py": "BROKER = True\n",
        "harness/provider_broker_bootstrap.py": "BOOTSTRAP = True\n",
        "harness/provider_broker_runtime.py": "RUNTIME = True\n",
        "trajectory/__init__.py": "",
        "trajectory/writer.py": "WRITER = True\n",
    }
    for relative_path, content in files.items():
        path = package_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return package_root


def _sha256(content: bytes) -> str:
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _replace_path_with_symlink_on_open(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: Path,
    target: Path,
) -> None:
    real_open = os.open
    replaced = False

    def open_after_replacement(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal replaced
        if not replaced and Path(path) == source:
            replaced = True
            source.unlink()
            source.symlink_to(target)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", open_after_replacement)


def _mutate_path_after_descriptor_read(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: Path,
    replacement: bytes,
) -> None:
    real_read = os.read
    source_stat = source.stat()
    mutated = False

    def read_then_mutate(descriptor: int, length: int) -> bytes:
        nonlocal mutated
        content = real_read(descriptor, length)
        observed = os.fstat(descriptor)
        if not mutated and observed.st_dev == source_stat.st_dev and observed.st_ino == source_stat.st_ino:
            mutated = True
            source.write_bytes(replacement)
        return content

    monkeypatch.setattr(os, "read", read_then_mutate)


def _replace_path_content_on_open(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: Path,
    replacement: bytes,
) -> None:
    real_open = os.open
    replaced = False

    def open_after_replacement(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal replaced
        if not replaced and Path(path) == source:
            replaced = True
            source.unlink()
            source.write_bytes(replacement)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", open_after_replacement)


def _mutate_path_content_on_open(
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: Path,
    replacement: bytes,
) -> None:
    real_open = os.open
    mutated = False

    def open_after_mutation(
        path: str | bytes | os.PathLike[str] | os.PathLike[bytes],
        flags: int,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> int:
        nonlocal mutated
        if not mutated and Path(path) == source:
            mutated = True
            source.write_bytes(replacement)
        return real_open(path, flags, mode, dir_fd=dir_fd)

    monkeypatch.setattr(os, "open", open_after_mutation)
