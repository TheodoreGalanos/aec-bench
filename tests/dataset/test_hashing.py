# ABOUTME: Tests for dataset content hashing — per-task directory and manifest-level.
# ABOUTME: Uses tmp_path fixtures to verify deterministic hash computation.

import shutil
from pathlib import Path

from aec_bench.dataset.hashing import compute_manifest_hash, hash_task_directory


def test_hash_task_directory_basic(tmp_path: Path) -> None:
    task_dir = tmp_path / "tasks" / "electrical" / "vd"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text("[metadata]\ndifficulty = 'easy'")
    (task_dir / "instruction.md").write_text("# Calculate voltage drop")
    h = hash_task_directory(task_dir)
    assert isinstance(h, str)
    assert len(h) == 64


def test_hash_task_directory_deterministic(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "a.txt").write_text("hello")
    (task_dir / "b.txt").write_text("world")
    h1 = hash_task_directory(task_dir)
    h2 = hash_task_directory(task_dir)
    assert h1 == h2


def test_hash_task_directory_excludes_pycache(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "engine.py").write_text("def compute(): pass")
    cache_dir = task_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "engine.cpython-312.pyc").write_bytes(b"compiled")
    h_with_cache = hash_task_directory(task_dir)
    shutil.rmtree(cache_dir)
    h_without_cache = hash_task_directory(task_dir)
    assert h_with_cache == h_without_cache


def test_hash_task_directory_content_change_changes_hash(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "task.toml").write_text("v1")
    h1 = hash_task_directory(task_dir)
    (task_dir / "task.toml").write_text("v2")
    h2 = hash_task_directory(task_dir)
    assert h1 != h2


def test_hash_task_directory_handles_binary_files(tmp_path: Path) -> None:
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    (task_dir / "drawing.pdf").write_bytes(b"%PDF-1.4 fake content")
    h = hash_task_directory(task_dir)
    assert len(h) == 64


def test_compute_manifest_hash_deterministic() -> None:
    pairs = [("electrical/voltage-drop", "abc123"), ("civil/rational-method", "def456")]
    h1 = compute_manifest_hash(pairs)
    h2 = compute_manifest_hash(pairs)
    assert h1 == h2


def test_compute_manifest_hash_order_independent() -> None:
    pairs_a = [("electrical/voltage-drop", "abc123"), ("civil/rational-method", "def456")]
    pairs_b = [("civil/rational-method", "def456"), ("electrical/voltage-drop", "abc123")]
    assert compute_manifest_hash(pairs_a) == compute_manifest_hash(pairs_b)


def test_compute_manifest_hash_changes_on_different_input() -> None:
    pairs_a = [("a", "hash1")]
    pairs_b = [("a", "hash2")]
    assert compute_manifest_hash(pairs_a) != compute_manifest_hash(pairs_b)
