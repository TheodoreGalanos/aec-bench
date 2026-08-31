# ABOUTME: Runs the maintained local artifact workspace conformance checks.
# ABOUTME: Exercises full-copy setup, private staging, exact deltas, and cleanup through production paths.

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from aec_bench.harness.artifact.workspace_port import resolve_workspace_path
from aec_bench.harness.local_runtime import (
    cleanup_workspace,
    setup_workspace,
    stage_verifier_assets,
    unstage_verifier_assets,
)
from aec_bench.harness.workspace_evidence import capture_workspace_manifest, compare_workspace_manifests

REQUIRED_GUARANTEES = frozenset(
    {
        "workspace_root_confinement",
        "cross_trial_isolation",
        "hard_link_source_safety",
        "actor_private_staging",
        "exact_workspace_delta",
        "workspace_cleanup",
        "full_copy_equivalence",
    }
)


def run_workspace_conformance(*, seed: int = 0) -> dict[str, Any]:
    """Run full-copy workspace checks against the local artifact workspace path."""

    del seed
    with TemporaryDirectory(prefix="aec-bench-workspace-conformance-") as temporary:
        root = Path(temporary)
        task = root / "task"
        task.mkdir()
        (task / "instruction.md").write_text("Write output", encoding="utf-8")
        (task / "input.txt").write_text("input", encoding="utf-8")
        private = task / "tests"
        private.mkdir()
        (private / "verify.py").write_text("# private verifier", encoding="utf-8")
        (private / "secret.json").write_text('{"answer": 42}', encoding="utf-8")

        first = Path(setup_workspace(str(task), work_root=root / "attempts"))
        second = Path(setup_workspace(str(task), work_root=root / "attempts"))
        assert first != second
        assert first.resolve().is_relative_to((root / "attempts").resolve())
        assert second.resolve().is_relative_to((root / "attempts").resolve())
        try:
            resolve_workspace_path(first, "../outside.txt")
        except ValueError as error:
            assert "inside" in str(error)
        else:
            raise AssertionError("workspace path traversal was accepted")
        assert (first / "input.txt").read_text(encoding="utf-8") == (task / "input.txt").read_text(encoding="utf-8")
        assert (first / "input.txt").stat().st_ino != (task / "input.txt").stat().st_ino
        (first / "input.txt").write_text("trial one", encoding="utf-8")
        assert (task / "input.txt").read_text(encoding="utf-8") == "input"
        assert (second / "input.txt").read_text(encoding="utf-8") == "input"
        assert not (first / "tests").exists()

        (first / "deleted.txt").write_text("delete", encoding="utf-8")
        base = capture_workspace_manifest(first)
        (first / "input.txt").write_text("changed", encoding="utf-8")
        (first / "added.txt").write_text("add", encoding="utf-8")
        (first / "deleted.txt").unlink()
        final = capture_workspace_manifest(first, default_source_role="actor_output")
        delta = compare_workspace_manifests(base, final)
        assert [str(item.relative_path) for item in delta.modified] == ["input.txt"]
        assert [str(item.relative_path) for item in delta.added] == ["added.txt"]
        assert [str(item.relative_path) for item in delta.deleted] == ["deleted.txt"]

        stage_verifier_assets(task, first)
        assert (first / "tests/secret.json").is_file()
        unstage_verifier_assets(first)
        assert not (first / "tests").exists()
        (first / "tests").mkdir()
        try:
            stage_verifier_assets(task, first)
        except ValueError as error:
            assert "must not already exist" in str(error)
        else:
            raise AssertionError("private verifier assets replaced an actor-created directory")
        unstage_verifier_assets(first)

        cleanup_workspace(first)
        cleanup_workspace(second)
        assert not first.exists() and not second.exists()

        hard_linked = root / "hard-linked-task"
        hard_linked.mkdir()
        source = hard_linked / "source.txt"
        source.write_text("shared", encoding="utf-8")
        (hard_linked / "alias.txt").hardlink_to(source)
        copied = Path(setup_workspace(str(hard_linked), work_root=root / "attempts"))
        try:
            assert (copied / "source.txt").stat().st_ino != (copied / "alias.txt").stat().st_ino
            assert (copied / "source.txt").stat().st_nlink == 1
            assert (copied / "alias.txt").stat().st_nlink == 1
        finally:
            cleanup_workspace(copied)

        outside = root / "outside.txt"
        outside.write_text("outside", encoding="utf-8")
        escaped = root / "escaped-task"
        escaped.mkdir()
        (escaped / "link.txt").symlink_to(outside)
        try:
            setup_workspace(str(escaped), work_root=root / "attempts")
        except ValueError as error:
            assert "symbolic link" in str(error)
        else:
            raise AssertionError("full-copy setup accepted a symbolic-link source")

    return {"proven": sorted(REQUIRED_GUARANTEES)}


__all__ = ("REQUIRED_GUARANTEES", "run_workspace_conformance")
