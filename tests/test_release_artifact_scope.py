# ABOUTME: Tests release archive scope and unsafe path rejection.
# ABOUTME: Keeps package verification fail-closed for private, local, and traversal entries.

from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_release_artifacts import release_archives, verify_archive


def _write_zip(path: Path, names: tuple[str, ...]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name in names:
            archive.writestr(name, b"content")


def _write_tar(path: Path, names: tuple[str, ...]) -> None:
    with tarfile.open(path, "w:gz") as archive:
        for name in names:
            info = tarfile.TarInfo(name)
            info.size = len(b"content")
            archive.addfile(info, io.BytesIO(b"content"))


def test_release_scope_accepts_public_wheel_and_source_package(tmp_path: Path) -> None:
    wheel = tmp_path / "aec_bench-0.1.0-py3-none-any.whl"
    sdist = tmp_path / "aec-bench-0.1.0.tar.gz"
    _write_zip(
        wheel,
        (
            "aec_bench/__init__.py",
            "aec_bench/web/frontend/src/runs/RailItem.svelte",
            "aec_bench-0.1.0.dist-info/METADATA",
        ),
    )
    _write_tar(sdist, ("aec-bench-0.1.0/src/aec_bench/__init__.py", "aec-bench-0.1.0/.env.example"))

    assert len(verify_archive(wheel)) == 3
    assert len(verify_archive(sdist)) == 2
    assert release_archives(tmp_path) == (wheel, sdist)


def test_release_scope_requires_one_wheel_and_one_source_package(tmp_path: Path) -> None:
    wheel = tmp_path / "aec_bench-0.1.0-py3-none-any.whl"
    sdist = tmp_path / "aec-bench-0.1.0.tar.gz"
    _write_zip(wheel, ("aec_bench/__init__.py",))
    _write_tar(sdist, ("aec-bench-0.1.0/src/aec_bench/__init__.py",))
    _write_zip(tmp_path / "aec_bench-0.1.0-py3-none-any-second.whl", ("aec_bench/__init__.py",))

    with pytest.raises(ValueError, match="exactly one wheel"):
        release_archives(tmp_path)


@pytest.mark.parametrize("member", ("private/secret.txt", "runs/local.json", "aec_bench/.env"))
def test_release_scope_rejects_private_entries(tmp_path: Path, member: str) -> None:
    archive = tmp_path / "aec_bench-0.1.0-py3-none-any.whl"
    _write_zip(archive, ("aec_bench/__init__.py", member))

    with pytest.raises(ValueError, match="forbidden"):
        verify_archive(archive)


@pytest.mark.parametrize(
    "member",
    (
        "/absolute.txt",
        "../outside.txt",
        "aec_bench/../outside.txt",
        "..\\outside.txt",
        "C:\\outside.txt",
        "aec_bench\\..\\outside.txt",
    ),
)
def test_release_scope_rejects_unsafe_archive_paths(tmp_path: Path, member: str) -> None:
    archive = tmp_path / "aec-bench-0.1.0.tar.gz"
    _write_tar(archive, ("aec-bench-0.1.0/src/aec_bench/__init__.py", member))

    with pytest.raises(ValueError, match="unsafe archive path"):
        verify_archive(archive)
