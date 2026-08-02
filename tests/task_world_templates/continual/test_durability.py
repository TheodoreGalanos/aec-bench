# ABOUTME: Tests the shared local lock used by real continual-world durability consumers.
# ABOUTME: Proves process exclusion, confinement, and task-owned error translation without fake worlds.

from __future__ import annotations

import ast
import multiprocessing
import stat
from contextlib import chdir
from pathlib import Path
from typing import Protocol

import pytest

from aec_bench.ledger.immutable_artifact_store import (
    ImmutableByteStore as LowerImmutableByteStore,
)
from aec_bench.ledger.local_lock import exclusive_local_file_lock as lower_exclusive_local_file_lock
from aec_bench.meta_harness.evidence_lifecycle import EvidenceLifecycleError, _lifecycle_state_lock
from aec_bench.task_world_templates.continual.durability import (
    ContinualWorldLockConfinementError,
    ContinualWorldLockError,
    ImmutableByteStore,
    exclusive_local_file_lock,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationWorldRunError,
    PumpStationWorldRunRepository,
)


class _ProcessSignal(Protocol):
    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


def _acquire_in_child(
    root: Path,
    ready: _ProcessSignal,
    start: _ProcessSignal,
    attempting: _ProcessSignal,
    acquired: _ProcessSignal,
) -> None:
    ready.set()
    if not start.wait(5):
        raise RuntimeError("lock test start signal was not received")
    attempting.set()
    with exclusive_local_file_lock(root, "world.lock"):
        acquired.set()


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def test_exclusive_local_file_lock_serializes_real_processes(tmp_path: Path) -> None:
    root = tmp_path / "nested"
    lock_path = root / "world.lock"
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    start = context.Event()
    attempting = context.Event()
    acquired = context.Event()
    process = context.Process(
        target=_acquire_in_child,
        args=(root, ready, start, attempting, acquired),
    )

    started = False
    try:
        process.start()
        started = True
        assert ready.wait(5)
        with exclusive_local_file_lock(root, "world.lock"):
            start.set()
            assert attempting.wait(5)
            assert not acquired.wait(0.5)
            assert process.is_alive()

        assert acquired.wait(5)
        process.join(5)
        assert not process.is_alive()
        assert process.exitcode == 0
    finally:
        start.set()
        if started:
            if process.is_alive():
                process.kill()
            process.join()

    assert stat.S_IMODE(lock_path.stat().st_mode) == 0o600


@pytest.mark.parametrize("unsafe_kind", ("symbolic-link", "directory"))
def test_exclusive_local_file_lock_rejects_unsafe_targets(
    tmp_path: Path,
    unsafe_kind: str,
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    lock_path = root / "world.lock"
    if unsafe_kind == "symbolic-link":
        outside = tmp_path / "outside.lock"
        outside.write_bytes(b"")
        lock_path.symlink_to(outside)
    else:
        lock_path.mkdir()

    with pytest.raises(ContinualWorldLockConfinementError):
        with exclusive_local_file_lock(root, "world.lock"):
            raise AssertionError("unsafe lock target must not be entered")


def test_exclusive_local_file_lock_accepts_external_path_alias(tmp_path: Path) -> None:
    physical_parent = tmp_path / "physical"
    physical_parent.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(physical_parent, target_is_directory=True)

    with exclusive_local_file_lock(alias / "run", "world.lock"):
        assert (physical_parent / "run" / "world.lock").is_file()


def test_exclusive_local_file_lock_rejects_internal_parent_alias(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / ".locks").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ContinualWorldLockConfinementError):
        with exclusive_local_file_lock(root, ".locks/world.lock"):
            raise AssertionError("internal lock parent alias must not be entered")


@pytest.mark.parametrize(
    "relative_path",
    ("../outside.lock", "/outside.lock", "locks//world.lock", "locks/./world.lock"),
)
def test_exclusive_local_file_lock_rejects_unconfined_relative_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    with pytest.raises(ContinualWorldLockConfinementError):
        with exclusive_local_file_lock(tmp_path / "run", relative_path):
            raise AssertionError("unconfined lock path must not be entered")


def test_exclusive_local_file_lock_rejects_insecure_regular_file(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    lock_path = root / "world.lock"
    lock_path.write_bytes(b"")
    lock_path.chmod(0o644)

    with pytest.raises(ContinualWorldLockConfinementError):
        with exclusive_local_file_lock(root, "world.lock"):
            raise AssertionError("insecure lock file must not be entered")


def test_exclusive_local_file_lock_accepts_dot_as_trusted_root(tmp_path: Path) -> None:
    with chdir(tmp_path):
        with exclusive_local_file_lock(Path("."), "world.lock"):
            assert (tmp_path / "world.lock").is_file()


def test_exclusive_local_file_lock_rejects_symbolic_link_root(tmp_path: Path) -> None:
    physical_root = tmp_path / "physical"
    physical_root.mkdir()
    alias_root = tmp_path / "alias"
    alias_root.symlink_to(physical_root, target_is_directory=True)

    with pytest.raises(ContinualWorldLockConfinementError):
        with exclusive_local_file_lock(alias_root, "world.lock"):
            raise AssertionError("symbolic-link root must not be entered")


def test_pump_repository_translates_unsafe_shared_lock_target(tmp_path: Path) -> None:
    repository = PumpStationWorldRunRepository(tmp_path / "run")
    outside = tmp_path / "outside.lock"
    outside.write_bytes(b"")
    (repository.root / ".world-run.lock").symlink_to(outside)

    with pytest.raises(PumpStationWorldRunError, match="artifact-confinement"):
        with repository.locked():
            raise AssertionError("unsafe pump lock target must not be entered")


def test_lifecycle_translates_unsafe_shared_lock_target(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    lock_dir = run_dir / ".locks"
    lock_dir.mkdir(parents=True)
    outside = tmp_path / "outside.lock"
    outside.write_bytes(b"")
    (lock_dir / "lifecycle-state.lock").symlink_to(outside)

    with pytest.raises(EvidenceLifecycleError, match="lifecycle state lock"):
        with _lifecycle_state_lock(run_dir):
            raise AssertionError("unsafe lifecycle lock target must not be entered")


def test_lifecycle_translates_lock_parent_file(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    (run_dir / ".locks").write_bytes(b"not a directory")

    with pytest.raises(EvidenceLifecycleError, match="lifecycle state lock"):
        with _lifecycle_state_lock(run_dir):
            raise AssertionError("invalid lifecycle lock parent must not be entered")


def test_consumer_body_lock_errors_are_not_reclassified(tmp_path: Path) -> None:
    repository = PumpStationWorldRunRepository(tmp_path / "pump-run")
    pump_body_error = ContinualWorldLockError("pump body failed")

    with pytest.raises(ContinualWorldLockError) as pump_raised:
        with repository.locked():
            raise pump_body_error
    assert pump_raised.value is pump_body_error

    lifecycle_body_error = ContinualWorldLockError("lifecycle body failed")
    with pytest.raises(ContinualWorldLockError) as lifecycle_raised:
        with _lifecycle_state_lock(tmp_path / "lifecycle-run"):
            raise lifecycle_body_error
    assert lifecycle_raised.value is lifecycle_body_error


def test_continual_lock_is_the_lower_shared_ledger_primitive() -> None:
    assert exclusive_local_file_lock is lower_exclusive_local_file_lock


def test_continual_immutable_byte_store_is_the_lower_shared_ledger_primitive() -> None:
    assert ImmutableByteStore is LowerImmutableByteStore


def test_real_consumers_do_not_own_parallel_local_lock_implementations() -> None:
    source_root = Path(__file__).parents[3] / "src" / "aec_bench"
    consumer_paths = (
        source_root / "task_world_templates" / "stewardship" / "wastewater_pump_station" / "world_run_repository.py",
        source_root / "meta_harness" / "evidence_lifecycle.py",
    )

    expected_modules = (
        "aec_bench.task_world_templates.continual.durability",
        "aec_bench.ledger.local_lock",
    )
    for path, expected_module in zip(consumer_paths, expected_modules, strict=True):
        imported = _imported_modules(path)
        assert "fcntl" not in imported
        assert expected_module in imported


def test_pump_repository_does_not_own_parallel_immutable_byte_mechanics() -> None:
    source_root = Path(__file__).parents[3] / "src" / "aec_bench"
    repository_path = (
        source_root / "task_world_templates" / "stewardship" / "wastewater_pump_station" / "world_run_repository.py"
    )
    source = repository_path.read_text(encoding="utf-8")

    assert "os.link(" not in source
    assert "def _require_regular_file" not in source
