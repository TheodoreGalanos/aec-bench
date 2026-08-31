# ABOUTME: Tests the shared ledger durability values used by real world consumers.
# ABOUTME: Proves process exclusion, confinement, and task-owned error translation without fake worlds.

from __future__ import annotations

import ast
import multiprocessing
import stat
import sys
from contextlib import chdir
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol

import pytest

import aec_bench.ledger.durability as lower_durability
import aec_bench.ledger.local_lock as local_lock
import aec_bench.lifecycles.runtime.operation_store as lifecycle_operation_store
import aec_bench.lifecycles.runtime.request_store as lifecycle_store
import aec_bench.worlds.runtime.rollout_repository as rollout_repository
import aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository as pump_repository
from aec_bench.ledger.durability import mkdir_durable, replace_file_bytes_durable
from aec_bench.ledger.immutable_byte_store import ImmutableByteStore
from aec_bench.ledger.local_lock import (
    LocalFileLockConfinementError,
    LocalFileLockError,
    exclusive_local_file_lock,
)
from aec_bench.lifecycles.runtime.lifecycle import EvidenceLifecycleError, _lifecycle_state_lock
from aec_bench.worlds.stewardship.wastewater_pump_station import (
    PumpStationWorldRunError,
    PumpStationWorldRunRepository,
)


class _ProcessSignal(Protocol):
    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


class _ProcessBarrier(Protocol):
    def wait(self, timeout: float | None = None) -> int: ...


class _ProcessResultQueue(Protocol):
    def put(self, value: str) -> None: ...


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


def _create_lock_in_child(
    root: Path,
    barrier: _ProcessBarrier,
    results: _ProcessResultQueue,
) -> None:
    barrier.wait(5)
    try:
        with exclusive_local_file_lock(root, "world.lock"):
            pass
    except BaseException as error:
        results.put(f"{type(error).__name__}: {error}")
    else:
        results.put("acquired")


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


def _function_body(path: Path, name: str) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"function not found: {name}")


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


def test_exclusive_local_file_lock_allows_concurrent_first_acquisition(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(3)
    results = context.Queue()
    processes = tuple(
        context.Process(
            target=_create_lock_in_child,
            args=(root, barrier, results),
        )
        for _ in range(2)
    )

    try:
        for process in processes:
            process.start()
        barrier.wait(5)
        observed = tuple(results.get(timeout=5) for _ in processes)
        for process in processes:
            process.join(5)
        assert observed == ("acquired", "acquired")
        assert all(process.exitcode == 0 for process in processes)
    finally:
        for process in processes:
            if process.is_alive():
                process.kill()
            process.join()


def test_exclusive_local_file_lock_uses_windows_backend(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[int, int]] = []
    windows_backend = SimpleNamespace(
        LK_LOCK=1,
        LK_UNLCK=2,
        locking=lambda descriptor, operation, length: calls.append(
            (operation, length),
        ),
    )
    monkeypatch.setattr(local_lock, "_PLATFORM_NAME", "nt")
    monkeypatch.setitem(sys.modules, "msvcrt", windows_backend)

    with exclusive_local_file_lock(tmp_path / "run", "locks/world.lock"):
        assert (tmp_path / "run" / "locks" / "world.lock").read_bytes() == b"\0"

    assert calls == [(1, 1), (2, 1)]


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

    with pytest.raises(LocalFileLockConfinementError):
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

    with pytest.raises(LocalFileLockConfinementError):
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
    with pytest.raises(LocalFileLockConfinementError):
        with exclusive_local_file_lock(tmp_path / "run", relative_path):
            raise AssertionError("unconfined lock path must not be entered")


def test_exclusive_local_file_lock_rejects_insecure_regular_file(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir()
    lock_path = root / "world.lock"
    lock_path.write_bytes(b"")
    lock_path.chmod(0o644)

    with pytest.raises(LocalFileLockConfinementError):
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

    with pytest.raises(LocalFileLockConfinementError):
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
    pump_body_error = LocalFileLockError("pump body failed")

    with pytest.raises(LocalFileLockError) as pump_raised:
        with repository.locked():
            raise pump_body_error
    assert pump_raised.value is pump_body_error

    lifecycle_body_error = LocalFileLockError("lifecycle body failed")
    with pytest.raises(LocalFileLockError) as lifecycle_raised:
        with _lifecycle_state_lock(tmp_path / "lifecycle-run"):
            raise lifecycle_body_error
    assert lifecycle_raised.value is lifecycle_body_error


def test_world_consumers_use_the_shared_ledger_lock() -> None:
    assert vars(pump_repository)["exclusive_local_file_lock"] is exclusive_local_file_lock
    assert vars(rollout_repository)["exclusive_local_file_lock"] is exclusive_local_file_lock


def test_world_consumers_use_the_shared_immutable_byte_store() -> None:
    assert vars(pump_repository)["ImmutableByteStore"] is ImmutableByteStore
    assert vars(rollout_repository)["ImmutableByteStore"] is ImmutableByteStore


def test_real_consumers_use_the_same_durable_directory_creation_owner() -> None:
    assert mkdir_durable is lower_durability.mkdir_durable
    assert vars(pump_repository)["mkdir_durable"] is mkdir_durable
    assert vars(lifecycle_operation_store)["mkdir_durable"] is lower_durability.mkdir_durable

    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    repository_path = source_root / "worlds" / "stewardship" / "wastewater_pump_station" / "world_run_repository.py"
    source = repository_path.read_text(encoding="utf-8")

    assert "def _mkdir_durable" not in source
    assert "def _fsync_directory" not in source


def test_real_consumers_use_the_same_durable_file_replacement_owner() -> None:
    assert replace_file_bytes_durable is lower_durability.replace_file_bytes_durable
    assert vars(pump_repository)["replace_file_bytes_durable"] is replace_file_bytes_durable
    assert vars(lifecycle_store)["replace_file_bytes_durable"] is lower_durability.replace_file_bytes_durable

    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    pump_body = _function_body(
        source_root / "worlds" / "stewardship" / "wastewater_pump_station" / "world_run_repository.py",
        "_replace_current",
    )
    lifecycle_body = _function_body(
        source_root / "lifecycles" / "runtime" / "request_store.py",
        "_write_json_atomic_durable",
    )

    for body in (pump_body, lifecycle_body):
        assert "replace_file_bytes_durable" in body
        assert "os.replace" not in body
        assert "os.fsync" not in body


def test_real_consumers_do_not_own_parallel_local_lock_implementations() -> None:
    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    consumer_paths = (
        source_root / "worlds" / "stewardship" / "wastewater_pump_station" / "world_run_repository.py",
        source_root / "lifecycles" / "runtime" / "lifecycle.py",
    )

    expected_modules = (
        "aec_bench.ledger.local_lock",
        "aec_bench.ledger.local_lock",
    )
    for path, expected_module in zip(consumer_paths, expected_modules, strict=True):
        imported = _imported_modules(path)
        assert "fcntl" not in imported
        assert expected_module in imported


def test_pump_repository_does_not_own_parallel_immutable_byte_mechanics() -> None:
    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    repository_path = source_root / "worlds" / "stewardship" / "wastewater_pump_station" / "world_run_repository.py"
    source = repository_path.read_text(encoding="utf-8")

    assert "os.link(" not in source
    assert "def _require_regular_file" not in source
