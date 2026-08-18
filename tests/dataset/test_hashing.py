# ABOUTME: Tests retained task-tree hashing used by Prime packages and v1 migration.
# ABOUTME: Schema-2 datasets use enclosing artifact or Git identity instead.

import shutil
from pathlib import Path

from aec_bench.dataset.hashing import hash_task_directory


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
