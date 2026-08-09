# ABOUTME: Tests the lower confined store for exact immutable byte publication and reload.
# ABOUTME: Proves first-writer behavior, path safety, private modes, and process concurrency.

from __future__ import annotations

import ast
import multiprocessing
import os
import stat
import uuid
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Protocol

import pytest

from aec_bench.ledger.immutable_byte_store import (
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStoreError,
    ImmutableByteStore,
)


class _ProcessSignal(Protocol):
    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


def _publish_in_child(
    root: Path,
    payload: bytes,
    ready: _ProcessSignal,
    start: _ProcessSignal,
    results: Queue[tuple[str, str]],
) -> None:
    store = ImmutableByteStore(root, host_private=True)
    ready.set()
    if not start.wait(5):
        raise RuntimeError("immutable publication start signal was not received")
    try:
        artifact = store.publish_bytes("shared/value.bin", payload)
    except ImmutableArtifactCollisionError:
        results.put(("collision", ""))
    else:
        results.put(("published", artifact.sha256))


def _load_in_child(
    root: Path,
    relative_path: str,
    results: Queue[tuple[str, str]],
) -> None:
    store = ImmutableByteStore(root)
    try:
        store.load_bytes(relative_path)
    except ImmutableArtifactIntegrityError as error:
        results.put(("integrity", str(error)))
    except BaseException as error:
        results.put((type(error).__name__, str(error)))
    else:
        results.put(("loaded", ""))


def _publish_with_restrictive_umask_in_child(
    root: Path,
    results: Queue[tuple[str, int | str]],
) -> None:
    previous_umask = os.umask(0o777)
    try:
        store = ImmutableByteStore(root)
        try:
            artifact = store.publish_bytes("value.bin", b"value")
        except BaseException as error:
            results.put((type(error).__name__, str(error)))
        else:
            results.put(("published", stat.S_IMODE(artifact.path.stat().st_mode)))
    finally:
        os.umask(previous_umask)


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
    return modules


@pytest.mark.parametrize(
    "payload",
    (
        b"",
        b"\x00\xff\x10binary",
        "asset condition: café Δ".encode(),
        b'{"value":1}\n',
    ),
)
def test_store_publishes_and_reloads_exact_arbitrary_bytes(
    tmp_path: Path,
    payload: bytes,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")

    first = store.publish_bytes("nested/value.bin", payload)
    repeated = store.publish_bytes("nested/value.bin", payload)

    assert repeated == first
    assert first.size_bytes == len(payload)
    assert store.load_bytes("nested/value.bin", expected_sha256=first.sha256) == payload
    assert store.reference("nested/value.bin") == first
    assert store.exists("nested/value.bin") is True
    assert store.exists("nested/missing.bin") is False


def test_store_rejects_collision_without_changing_first_bytes(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    first = store.publish_bytes("value.bin", b"first")

    with pytest.raises(ImmutableArtifactCollisionError):
        store.publish_bytes("value.bin", b"second")

    assert store.load_bytes("value.bin", expected_sha256=first.sha256) == b"first"


def test_exists_checks_safe_metadata_without_reading_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    store.publish_bytes("value.bin", b"value")

    def fail_read(descriptor: int, size: int) -> bytes:
        del descriptor, size
        raise AssertionError("exists must not read artifact content")

    monkeypatch.setattr(os, "read", fail_read)

    assert store.exists("value.bin") is True
    assert store.exists("missing.bin") is False


def test_missing_exists_result_rechecks_root_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "store"
    store = ImmutableByteStore(root)
    original = tmp_path / "original-store"
    original_stat = os.stat
    replaced = False

    def stat_and_replace(
        path: os.PathLike[str] | str | int,
        *,
        dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> os.stat_result:
        nonlocal replaced
        if path == "missing.bin" and dir_fd is not None and not replaced:
            root.rename(original)
            root.mkdir()
            replaced = True
        return original_stat(path, dir_fd=dir_fd, follow_symlinks=follow_symlinks)

    monkeypatch.setattr(os, "stat", stat_and_replace)

    with pytest.raises(ImmutableArtifactConfinementError, match="identity"):
        store.exists("missing.bin")


@pytest.mark.parametrize(
    ("payloads", "expected_statuses"),
    (
        ((b"same", b"same"), ["published", "published"]),
        ((b"first", b"second"), ["collision", "published"]),
    ),
)
def test_store_has_one_process_safe_first_writer(
    tmp_path: Path,
    payloads: tuple[bytes, bytes],
    expected_statuses: list[str],
) -> None:
    root = tmp_path / "store"
    root.mkdir(mode=0o700)
    context = multiprocessing.get_context("spawn")
    ready = (context.Event(), context.Event())
    start = context.Event()
    results = context.Queue()
    processes = tuple(
        context.Process(
            target=_publish_in_child,
            args=(root, payload, process_ready, start, results),
        )
        for payload, process_ready in zip(payloads, ready, strict=True)
    )
    started: list[BaseProcess] = []
    try:
        for process in processes:
            process.start()
            started.append(process)
        assert all(signal.wait(5) for signal in ready)
        start.set()
        for process in processes:
            process.join(5)
            assert not process.is_alive()
            assert process.exitcode == 0
        outcomes = [results.get(timeout=5), results.get(timeout=5)]
    finally:
        start.set()
        for started_process in started:
            if started_process.is_alive():
                started_process.kill()
            started_process.join()
        results.close()
        results.join_thread()

    assert sorted(status for status, _ in outcomes) == expected_statuses
    assert ImmutableByteStore(root, host_private=True).load_bytes("shared/value.bin") in payloads


@pytest.mark.parametrize(
    "relative_path",
    ("", ".", "../outside.bin", "/outside.bin", "nested//value.bin", "nested/./value.bin"),
)
def test_store_rejects_unconfined_relative_paths(
    tmp_path: Path,
    relative_path: str,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")

    with pytest.raises(ImmutableArtifactConfinementError):
        store.publish_bytes(relative_path, b"forbidden")


def test_store_fails_closed_before_writes_without_required_posix_features(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "store"
    monkeypatch.delattr(os, "O_NOFOLLOW")

    with pytest.raises(ImmutableArtifactConfinementError, match="POSIX"):
        ImmutableByteStore(selected)

    assert not selected.exists()


def test_store_accepts_alias_above_root_but_rejects_alias_as_root(tmp_path: Path) -> None:
    physical_parent = tmp_path / "physical"
    physical_parent.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(physical_parent, target_is_directory=True)

    store = ImmutableByteStore(alias / "run")
    store.publish_bytes("value.bin", b"value")

    assert (physical_parent / "run" / "value.bin").read_bytes() == b"value"
    with pytest.raises(ImmutableArtifactConfinementError):
        ImmutableByteStore(alias)


def test_store_rejects_final_root_symlink_inserted_after_prospective_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "store"
    outside = tmp_path / "outside"
    outside.mkdir()
    original_resolve = Path.resolve
    inserted = False

    def resolve_and_insert(path: Path, strict: bool = False) -> Path:
        nonlocal inserted
        resolved = original_resolve(path, strict=strict)
        if path == selected and not strict and not inserted:
            selected.symlink_to(outside, target_is_directory=True)
            inserted = True
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_and_insert)

    with pytest.raises(ImmutableArtifactConfinementError, match="symbolic-link"):
        ImmutableByteStore(selected)

    assert tuple(outside.iterdir()) == ()


def test_store_rejects_replacement_of_its_trusted_root(tmp_path: Path) -> None:
    root = tmp_path / "store"
    store = ImmutableByteStore(root)
    root.rename(tmp_path / "original-store")
    root.mkdir()

    with pytest.raises(ImmutableArtifactConfinementError, match="identity"):
        store.publish_bytes("value.bin", b"forbidden")

    assert tuple(root.iterdir()) == ()


def test_store_binds_canonical_root_and_identity_to_one_checked_descriptor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "store"
    root.mkdir()
    original = tmp_path / "original-store"
    initial = root.stat()
    initial_identity = (initial.st_dev, initial.st_ino)
    original_close = os.close
    replaced = False

    def close_and_replace(descriptor: int) -> None:
        nonlocal replaced
        details = os.fstat(descriptor)
        original_close(descriptor)
        if not replaced and (details.st_dev, details.st_ino) == initial_identity:
            root.rename(original)
            root.mkdir()
            replaced = True

    monkeypatch.setattr(os, "close", close_and_replace)

    with pytest.raises(ImmutableArtifactConfinementError, match="identity"):
        ImmutableByteStore(root)


def test_root_validation_preserves_active_error_when_close_also_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "store"
    root.mkdir(mode=0o755)
    original_close = os.close

    def close_then_fail(descriptor: int) -> None:
        original_close(descriptor)
        raise OSError("forced close failure")

    monkeypatch.setattr(os, "close", close_then_fail)

    with pytest.raises(ImmutableArtifactConfinementError, match="permissions"):
        ImmutableByteStore(root, host_private=True)


def test_store_rechecks_root_identity_after_artifact_operation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "store"
    store = ImmutableByteStore(root)
    store.publish_bytes("value.bin", b"value")
    original = tmp_path / "original-store"
    original_read = os.read
    replaced = False

    def read_and_replace(descriptor: int, size: int) -> bytes:
        nonlocal replaced
        if not replaced:
            root.rename(original)
            root.mkdir()
            replaced = True
        return original_read(descriptor, size)

    monkeypatch.setattr(os, "read", read_and_replace)

    with pytest.raises(ImmutableArtifactConfinementError, match="identity"):
        store.load_bytes("value.bin")

    assert tuple(root.iterdir()) == ()


def test_compatibility_path_rechecks_root_identity_after_symlink_scan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "store"
    store = ImmutableByteStore(root)
    original = tmp_path / "original-store"
    original_is_symlink = Path.is_symlink
    replaced = False

    def inspect_and_replace(path: Path) -> bool:
        nonlocal replaced
        if path == root / "value.bin" and not replaced:
            root.rename(original)
            root.mkdir()
            replaced = True
        return original_is_symlink(path)

    monkeypatch.setattr(Path, "is_symlink", inspect_and_replace)

    with pytest.raises(ImmutableArtifactConfinementError, match="identity"):
        store._path("value.bin")


def test_store_rejects_disjoint_overlap_before_creating_root(tmp_path: Path) -> None:
    protected = tmp_path / "protected"
    protected.mkdir()
    selected = protected / "store"

    with pytest.raises(ImmutableArtifactConfinementError, match="overlap"):
        ImmutableByteStore(selected, disjoint_roots=(protected,))

    assert not selected.exists()


def test_store_rejects_relative_disjoint_root_before_creating_root(
    tmp_path: Path,
) -> None:
    selected = tmp_path / "store"

    with pytest.raises(ImmutableArtifactConfinementError, match="absolute"):
        ImmutableByteStore(selected, disjoint_roots=(Path("protected"),))

    assert not selected.exists()


def test_store_rechecks_disjoint_root_before_descriptor_bound_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safe_parent = tmp_path / "safe"
    safe_parent.mkdir()
    original_parent = tmp_path / "original-safe"
    protected = tmp_path / "protected"
    protected.mkdir()
    selected = safe_parent / "store"
    original_resolve = Path.resolve
    swapped = False

    def resolve_and_swap(path: Path, strict: bool = False) -> Path:
        nonlocal swapped
        resolved = original_resolve(path, strict=strict)
        if path == selected and not strict and not swapped:
            safe_parent.rename(original_parent)
            safe_parent.symlink_to(protected, target_is_directory=True)
            swapped = True
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_and_swap)

    with pytest.raises(ImmutableArtifactConfinementError, match="overlap"):
        ImmutableByteStore(selected, disjoint_roots=(protected,))

    assert not (protected / "store").exists()


def test_store_does_not_follow_replaced_intermediate_root_ancestor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safe_ancestor = tmp_path / "safe"
    safe_parent = safe_ancestor / "parent"
    safe_parent.mkdir(parents=True)
    original_ancestor = tmp_path / "original-safe"
    protected = tmp_path / "protected"
    (protected / "parent").mkdir(parents=True)
    selected = safe_parent / "store"
    original_resolve = Path.resolve
    swapped = False

    def resolve_and_swap(path: Path, strict: bool = False) -> Path:
        nonlocal swapped
        resolved = original_resolve(path, strict=strict)
        if path == safe_parent and strict and not swapped:
            safe_ancestor.rename(original_ancestor)
            safe_ancestor.symlink_to(protected, target_is_directory=True)
            swapped = True
        return resolved

    monkeypatch.setattr(Path, "resolve", resolve_and_swap)

    with pytest.raises(ImmutableArtifactConfinementError):
        ImmutableByteStore(selected, disjoint_roots=(protected,))

    assert not (protected / "parent" / "store").exists()


def test_store_rejects_symbolic_link_parent_without_external_write(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ImmutableArtifactConfinementError):
        store.publish_bytes("linked/value.bin", b"forbidden")

    assert tuple(outside.iterdir()) == ()


def test_store_rejects_symbolic_link_and_non_file_targets(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    (store.root / "linked.bin").symlink_to(outside)
    (store.root / "directory.bin").mkdir()

    with pytest.raises(ImmutableArtifactConfinementError):
        store.load_bytes("linked.bin")
    with pytest.raises(ImmutableArtifactIntegrityError):
        store.load_bytes("directory.bin")

    assert outside.read_bytes() == b"outside"


def test_store_classifies_unreadable_regular_file_as_integrity_failure(
    tmp_path: Path,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    path = store.publish_bytes("value.bin", b"value").path
    path.chmod(0o000)
    try:
        with pytest.raises(ImmutableArtifactIntegrityError, match="cannot be opened"):
            store.load_bytes("value.bin")
    finally:
        path.chmod(0o600)


def test_store_rejects_fifo_in_a_bounded_child_process(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir()
    os.mkfifo(root / "value.bin")
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    process = context.Process(
        target=_load_in_child,
        args=(root, "value.bin", results),
    )
    process.start()
    try:
        process.join(2)
        assert not process.is_alive(), "loading a FIFO blocked the child process"
        assert process.exitcode == 0
        status, detail = results.get(timeout=2)
    finally:
        if process.is_alive():
            process.kill()
        process.join()
        results.close()
        results.join_thread()

    assert status == "integrity"
    assert "regular file" in detail


def test_store_detects_digest_drift_and_public_file_mode(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store", host_private=True)
    artifact = store.publish_bytes("value.bin", b"original")
    artifact.path.write_bytes(b"changed")

    with pytest.raises(ImmutableArtifactIntegrityError, match="digest"):
        store.load_bytes("value.bin", expected_sha256=artifact.sha256)

    artifact.path.chmod(0o644)
    with pytest.raises(ImmutableArtifactConfinementError, match="permissions"):
        store.load_bytes("value.bin")


def test_host_private_store_rechecks_root_mode_during_operations(
    tmp_path: Path,
) -> None:
    store = ImmutableByteStore(tmp_path / "store", host_private=True)
    store.publish_bytes("value.bin", b"value")
    store.root.chmod(0o755)

    with pytest.raises(ImmutableArtifactConfinementError, match="permissions"):
        store.load_bytes("value.bin")


def test_store_preserves_sha256_validation_error_text(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    store.publish_bytes("value.bin", b"value")

    with pytest.raises(
        ValueError,
        match="^SHA-256 digest must contain 64 lowercase hexadecimal characters$",
    ):
        store.load_bytes("value.bin", expected_sha256="not-a-digest")


def test_host_private_store_creates_private_directories_and_files(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store", host_private=True)
    artifact = store.publish_bytes("nested/deeper/value.bin", b"private")

    assert stat.S_IMODE(store.root.stat().st_mode) == 0o700
    assert stat.S_IMODE((store.root / "nested").stat().st_mode) == 0o700
    assert stat.S_IMODE((store.root / "nested" / "deeper").stat().st_mode) == 0o700
    assert stat.S_IMODE(artifact.path.stat().st_mode) == 0o600


def test_host_private_store_makes_every_new_root_component_private(
    tmp_path: Path,
) -> None:
    components = (
        tmp_path / "first",
        tmp_path / "first" / "second",
        tmp_path / "first" / "second" / "store",
    )

    store = ImmutableByteStore(components[-1], host_private=True)

    assert store.root == components[-1]
    assert [stat.S_IMODE(path.stat().st_mode) for path in components] == [
        0o700,
        0o700,
        0o700,
    ]


def test_host_private_root_creation_flushes_created_directories_and_parents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "first" / "second" / "store"
    flushed: set[tuple[int, int]] = set()
    original_fsync = os.fsync

    def record_fsync(descriptor: int) -> None:
        details = os.fstat(descriptor)
        flushed.add((details.st_dev, details.st_ino))
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", record_fsync)

    store = ImmutableByteStore(selected, host_private=True)

    expected_paths = (tmp_path, selected.parent.parent, selected.parent, store.root)
    expected = {(path.stat().st_dev, path.stat().st_ino) for path in expected_paths}
    assert expected <= flushed


def test_root_creation_race_flushes_winning_directory_and_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "store"
    flushed: set[tuple[int, int]] = set()
    original_mkdir = os.mkdir
    original_fsync = os.fsync
    simulated_winner = False

    def competing_mkdir(
        path: str | bytes,
        mode: int = 0o777,
        *,
        dir_fd: int | None = None,
    ) -> None:
        nonlocal simulated_winner
        if os.fsdecode(path) == selected.name and dir_fd is not None and not simulated_winner:
            original_mkdir(path, mode, dir_fd=dir_fd)
            simulated_winner = True
            raise FileExistsError(path)
        original_mkdir(path, mode, dir_fd=dir_fd)

    def record_fsync(descriptor: int) -> None:
        details = os.fstat(descriptor)
        flushed.add((details.st_dev, details.st_ino))
        original_fsync(descriptor)

    monkeypatch.setattr(os, "mkdir", competing_mkdir)
    monkeypatch.setattr(os, "fsync", record_fsync)

    store = ImmutableByteStore(selected)

    parent_details = tmp_path.stat()
    root_details = store.root.stat()
    assert (parent_details.st_dev, parent_details.st_ino) in flushed
    assert (root_details.st_dev, root_details.st_ino) in flushed


def test_stable_existing_root_does_not_repeat_root_creation_flushes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "store"
    root.mkdir()
    flushed: list[int] = []
    original_fsync = os.fsync

    def record_fsync(descriptor: int) -> None:
        flushed.append(descriptor)
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", record_fsync)

    ImmutableByteStore(root)

    assert flushed == []


def test_child_creation_and_equal_replay_flush_the_changed_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    flushed: list[tuple[int, int]] = []
    original_fsync = os.fsync

    def record_fsync(descriptor: int) -> None:
        details = os.fstat(descriptor)
        flushed.append((details.st_dev, details.st_ino))
        original_fsync(descriptor)

    monkeypatch.setattr(os, "fsync", record_fsync)
    store.publish_bytes("nested/value.bin", b"value")

    root_details = store.root.stat()
    assert (root_details.st_dev, root_details.st_ino) in flushed

    flushed.clear()
    store.publish_bytes("nested/value.bin", b"value")

    assert (root_details.st_dev, root_details.st_ino) in flushed
    parent_details = (store.root / "nested").stat()
    assert (parent_details.st_dev, parent_details.st_ino) in flushed


def test_orphan_temporary_file_cannot_become_published_content(tmp_path: Path) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    orphan = store.root / ".value.bin.orphan.tmp"
    orphan.write_bytes(b"orphan")

    artifact = store.publish_bytes("value.bin", b"published")

    assert artifact.path.read_bytes() == b"published"
    assert orphan.read_bytes() == b"orphan"


def test_published_file_mode_is_private_under_a_restrictive_umask(tmp_path: Path) -> None:
    root = tmp_path / "store"
    root.mkdir(mode=0o700)
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    process = context.Process(
        target=_publish_with_restrictive_umask_in_child,
        args=(root, results),
    )
    process.start()
    try:
        process.join(5)
        assert not process.is_alive()
        assert process.exitcode == 0
        outcome = results.get(timeout=2)
    finally:
        if process.is_alive():
            process.kill()
        process.join()
        results.close()
        results.join_thread()

    assert outcome == ("published", 0o600)
    assert (root / "value.bin").read_bytes() == b"value"


def test_temporary_name_collision_preserves_file_not_created_by_this_call(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    fixed = uuid.UUID(int=0)
    temporary = store.root / f".value.bin.{fixed.hex}.tmp"
    temporary.write_bytes(b"pre-existing")
    monkeypatch.setattr(uuid, "uuid4", lambda: fixed)

    with pytest.raises(ImmutableArtifactStoreError, match="cannot be created"):
        store.publish_bytes("value.bin", b"published")

    assert temporary.read_bytes() == b"pre-existing"
    assert not (store.root / "value.bin").exists()


def test_temporary_replacement_cannot_become_published_or_be_deleted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    original_link = os.link
    replacement_name: str | None = None

    def link_after_replacement(
        source: str | bytes,
        destination: str | bytes,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        nonlocal replacement_name
        replacement_name = os.fsdecode(source)
        os.unlink(source, dir_fd=src_dir_fd)
        descriptor = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=src_dir_fd,
        )
        try:
            os.write(descriptor, b"intruder")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        original_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "link", link_after_replacement)

    with pytest.raises(ImmutableArtifactIntegrityError):
        store.publish_bytes("value.bin", b"expected")

    assert replacement_name is not None
    assert not (store.root / "value.bin").exists()
    assert (store.root / replacement_name).read_bytes() == b"intruder"


def test_unsafe_temporary_replacement_is_removed_only_from_final_name(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ImmutableByteStore(tmp_path / "store")
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    original_link = os.link
    replacement_name: str | None = None

    def link_after_symlink_replacement(
        source: str | bytes,
        destination: str | bytes,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        nonlocal replacement_name
        replacement_name = os.fsdecode(source)
        os.unlink(source, dir_fd=src_dir_fd)
        os.symlink(outside, source, dir_fd=src_dir_fd)
        original_link(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )

    monkeypatch.setattr(os, "link", link_after_symlink_replacement)

    with pytest.raises(ImmutableArtifactConfinementError):
        store.publish_bytes("value.bin", b"expected")

    assert replacement_name is not None
    assert not os.path.lexists(store.root / "value.bin")
    replacement = store.root / replacement_name
    assert replacement.is_symlink()
    assert replacement.resolve() == outside


def test_lower_store_has_no_meta_harness_or_task_dependency() -> None:
    source = Path(__file__).parents[2] / "src" / "aec_bench" / "ledger" / "immutable_byte_store.py"
    imported = _imported_modules(source)

    assert all(not module.startswith("aec_bench.contracts") for module in imported)
    assert all(not module.startswith("aec_bench.meta_harness") for module in imported)
    assert all(not module.startswith("aec_bench.task_world_templates") for module in imported)
