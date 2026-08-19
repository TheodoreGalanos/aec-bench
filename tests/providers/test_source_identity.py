# ABOUTME: Tests clean Git and reconstructive provider source identity selection.
# ABOUTME: Proves dirty source produces deterministic retained bytes without local paths.

import hashlib
import subprocess
import tarfile
from pathlib import Path

from aec_bench.providers.source_identity import resolve_provider_adapter_identity


def _git(path: Path, *args: str) -> None:
    subprocess.run(("git", *args), cwd=path, check=True, capture_output=True, text=True)


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "source"
    package = root / "src" / "adapter"
    package.mkdir(parents=True)
    (package / "runtime.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "tests@example.com")
    _git(root, "config", "user.name", "AEC Bench Tests")
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "initial")
    return root, package


def test_clean_source_uses_one_full_git_revision(tmp_path: Path) -> None:
    root, package = _repository(tmp_path)
    snapshot = tmp_path / "source.tar"

    identity = resolve_provider_adapter_identity(
        adapter_id="test-adapter",
        package_version="1.0",
        source_root=root,
        source_paths=(package,),
        snapshot_path=snapshot,
        snapshot_artifact_id="provider/source.tar",
    )

    assert identity.source_revision is not None
    assert len(identity.source_revision) == 40
    assert identity.source_snapshot is None
    assert not snapshot.exists()


def test_dirty_source_uses_one_deterministic_snapshot(tmp_path: Path) -> None:
    root, package = _repository(tmp_path)
    (package / "runtime.py").write_text("VALUE = 2\n", encoding="utf-8")
    first_path = tmp_path / "first.tar"
    second_path = tmp_path / "second.tar"

    first = resolve_provider_adapter_identity(
        adapter_id="test-adapter",
        package_version="1.0",
        source_root=root,
        source_paths=(package,),
        snapshot_path=first_path,
        snapshot_artifact_id="provider/source.tar",
    )
    second = resolve_provider_adapter_identity(
        adapter_id="test-adapter",
        package_version="1.0",
        source_root=root,
        source_paths=(package,),
        snapshot_path=second_path,
        snapshot_artifact_id="provider/source.tar",
    )

    assert first.source_revision is None
    assert first.source_snapshot == second.source_snapshot
    assert first_path.read_bytes() == second_path.read_bytes()
    assert first.source_snapshot is not None
    assert first.source_snapshot.sha256 == hashlib.sha256(first_path.read_bytes()).hexdigest()
    with tarfile.open(first_path) as archive:
        assert archive.getnames() == ["src/adapter/runtime.py"]
        assert archive.extractfile("src/adapter/runtime.py").read() == b"VALUE = 2\n"  # type: ignore[union-attr]


def test_ignored_source_file_requires_a_snapshot(tmp_path: Path) -> None:
    root, package = _repository(tmp_path)
    (root / ".gitignore").write_text("*.local\n", encoding="utf-8")
    _git(root, "add", ".gitignore")
    _git(root, "commit", "-qm", "ignore local source")
    (package / "runtime.local").write_text("local configuration\n", encoding="utf-8")
    snapshot = tmp_path / "source.tar"

    identity = resolve_provider_adapter_identity(
        adapter_id="test-adapter",
        package_version="1.0",
        source_root=root,
        source_paths=(package,),
        snapshot_path=snapshot,
        snapshot_artifact_id="provider/source.tar",
    )

    assert identity.source_revision is None
    assert identity.source_snapshot is not None
    with tarfile.open(snapshot) as archive:
        assert "src/adapter/runtime.local" in archive.getnames()
