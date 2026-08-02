# ABOUTME: Tests exact crash-safe replacement of one mutable file below a trusted directory.
# ABOUTME: Proves atomic visibility, confinement, durability order, private modes, and safe cleanup.

from __future__ import annotations

import multiprocessing
import os
import stat
import uuid
from multiprocessing.queues import Queue
from pathlib import Path
from typing import Never

import pytest

import aec_bench.ledger.durability as durability_runtime
from aec_bench.ledger.durability import (
    DurableFileReplaceConfinementError,
    DurableFileReplaceError,
    DurableFileReplaceIntegrityError,
    replace_file_bytes_durable,
)

_CRASH_EXIT_CODE = 94
_ORIGINAL_REPLACE = os.replace
type _PathArgument = str | bytes | os.PathLike[str] | os.PathLike[bytes]


def _crash() -> Never:
    os._exit(_CRASH_EXIT_CODE)


def _replace_and_crash(directory: Path, boundary: str) -> None:
    def crash_replace(
        src: _PathArgument,
        dst: _PathArgument,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        if boundary == "before-replace":
            _crash()
        _ORIGINAL_REPLACE(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )
        if boundary == "after-replace":
            _crash()

    os.replace = crash_replace
    replace_file_bytes_durable(directory, "value.bin", b"new")


def _replace_with_restrictive_umask(
    directory: Path,
    results: Queue[tuple[str, int | str]],
) -> None:
    previous_umask = os.umask(0o777)
    try:
        try:
            replace_file_bytes_durable(
                directory,
                "value.bin",
                b"private",
                host_private=True,
            )
        except BaseException as error:
            results.put((type(error).__name__, str(error)))
        else:
            results.put(
                (
                    "replaced",
                    stat.S_IMODE((directory / "value.bin").stat().st_mode),
                )
            )
    finally:
        os.umask(previous_umask)


def test_replacement_preserves_exact_bytes_on_first_and_later_writes(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()

    replace_file_bytes_durable(directory, "value.bin", b"\x00first\xff")
    assert (directory / "value.bin").read_bytes() == b"\x00first\xff"

    replace_file_bytes_durable(directory, "value.bin", b"second\n")

    assert (directory / "value.bin").read_bytes() == b"second\n"
    assert sorted(path.name for path in directory.iterdir()) == ["value.bin"]


def test_replacement_flushes_file_before_replace_and_directory_after_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    events: list[str] = []
    original_fsync = os.fsync
    original_replace = os.replace

    def record_fsync(descriptor: int) -> None:
        details = os.fstat(descriptor)
        events.append("directory-fsync" if stat.S_ISDIR(details.st_mode) else "file-fsync")
        original_fsync(descriptor)

    def record_replace(
        source: _PathArgument,
        destination: _PathArgument,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        assert Path(os.fsdecode(source)).parent == Path(".")
        assert os.fsdecode(destination) == "value.bin"
        assert src_dir_fd is not None
        assert dst_dir_fd == src_dir_fd
        events.append("replace")
        original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "fsync", record_fsync)
    monkeypatch.setattr(os, "replace", record_replace)

    replace_file_bytes_durable(directory, "value.bin", b"durable")

    assert events == ["file-fsync", "replace", "directory-fsync"]


@pytest.mark.parametrize(
    "file_name",
    ("", ".", "..", "../outside.bin", "/outside.bin", "nested/value.bin"),
)
def test_replacement_rejects_names_outside_one_directory_entry(
    tmp_path: Path,
    file_name: str,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()

    with pytest.raises(DurableFileReplaceConfinementError):
        replace_file_bytes_durable(directory, file_name, b"forbidden")

    assert not (tmp_path / "outside.bin").exists()


def test_replacement_rejects_symbolic_link_directory_and_destination(
    tmp_path: Path,
) -> None:
    physical = tmp_path / "physical"
    physical.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(physical, target_is_directory=True)

    with pytest.raises(DurableFileReplaceConfinementError):
        replace_file_bytes_durable(alias, "value.bin", b"forbidden")

    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    destination = physical / "value.bin"
    destination.symlink_to(outside)

    with pytest.raises(DurableFileReplaceConfinementError):
        replace_file_bytes_durable(physical, "value.bin", b"forbidden")

    assert destination.is_symlink()
    assert outside.read_bytes() == b"outside"


def test_replacement_accepts_trusted_alias_above_directory(tmp_path: Path) -> None:
    physical_parent = tmp_path / "physical"
    directory = physical_parent / "store"
    directory.mkdir(parents=True)
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(physical_parent, target_is_directory=True)

    replace_file_bytes_durable(alias_parent / "store", "value.bin", b"trusted")

    assert (directory / "value.bin").read_bytes() == b"trusted"


def test_directory_close_failure_does_not_mask_binding_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    original_close = os.close
    unclosed_descriptors: list[int] = []

    def reject_binding(_directory: Path, _descriptor: int) -> None:
        raise DurableFileReplaceConfinementError("injected binding failure")

    def fail_close(descriptor: int) -> None:
        unclosed_descriptors.append(descriptor)
        raise OSError("injected close failure")

    with monkeypatch.context() as patcher:
        patcher.setattr(
            durability_runtime,
            "_require_durable_directory_binding",
            reject_binding,
        )
        patcher.setattr(os, "close", fail_close)
        with pytest.raises(
            DurableFileReplaceConfinementError,
            match="injected binding failure",
        ) as raised:
            replace_file_bytes_durable(directory, "value.bin", b"forbidden")

    for descriptor in unclosed_descriptors:
        original_close(descriptor)
    assert raised.value.__notes__ == [
        "durable file directory descriptor cannot be closed after validation failure: injected close failure"
    ]


def test_replacement_rejects_non_regular_existing_destination(tmp_path: Path) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    (directory / "value.bin").mkdir()

    with pytest.raises(DurableFileReplaceConfinementError, match="regular file"):
        replace_file_bytes_durable(directory, "value.bin", b"forbidden")

    assert (directory / "value.bin").is_dir()


def test_replacement_fails_closed_without_descriptor_relative_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    supported = set(os.supports_dir_fd)
    supported.discard(os.rename)
    monkeypatch.setattr(os, "supports_dir_fd", supported)

    with pytest.raises(DurableFileReplaceConfinementError, match=r"rename\(dir_fd\)"):
        replace_file_bytes_durable(directory, "value.bin", b"forbidden")

    assert not tuple(directory.iterdir())


def test_replacement_maps_unavailable_descriptor_replace_and_cleans_temporary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    destination = directory / "value.bin"
    destination.write_bytes(b"old")

    def unavailable_replace(*_args: object, **_kwargs: object) -> None:
        raise NotImplementedError("injected unavailable descriptor replace")

    monkeypatch.setattr(os, "replace", unavailable_replace)

    with pytest.raises(DurableFileReplaceError, match="cannot replace value.bin"):
        replace_file_bytes_durable(directory, "value.bin", b"new")

    assert destination.read_bytes() == b"old"
    assert not tuple(directory.glob(".value.bin.*.tmp"))


def test_host_private_replacement_forces_mode_under_restrictive_umask(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir(mode=0o700)
    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    process = context.Process(
        target=_replace_with_restrictive_umask,
        args=(directory, results),
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

    assert outcome == ("replaced", 0o600)
    assert (directory / "value.bin").read_bytes() == b"private"


@pytest.mark.parametrize(
    ("boundary", "expected"),
    (("before-replace", b"old"), ("after-replace", b"new")),
)
def test_process_death_exposes_only_old_or_new_complete_bytes(
    tmp_path: Path,
    boundary: str,
    expected: bytes,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    (directory / "value.bin").write_bytes(b"old")
    context = multiprocessing.get_context("spawn")
    process = context.Process(
        target=_replace_and_crash,
        args=(directory, boundary),
    )
    process.start()
    process.join(5)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("fault-injection process did not stop")

    assert process.exitcode == _CRASH_EXIT_CODE
    assert (directory / "value.bin").read_bytes() == expected
    temporaries = tuple(directory.glob(".value.bin.*.tmp"))
    if boundary == "before-replace":
        assert len(temporaries) == 1
        assert temporaries[0].read_bytes() == b"new"
    else:
        assert not temporaries


def test_replacement_does_not_delete_a_substituted_temporary_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    (directory / "value.bin").write_bytes(b"old")
    fixed = uuid.UUID(int=0)
    temporary = directory / f".value.bin.{fixed.hex}.tmp"

    def fail_after_substitution(
        source: _PathArgument,
        destination: _PathArgument,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        del destination, dst_dir_fd
        os.unlink(source, dir_fd=src_dir_fd)
        descriptor = os.open(
            source,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
            dir_fd=src_dir_fd,
        )
        try:
            os.write(descriptor, b"substituted")
        finally:
            os.close(descriptor)
        raise OSError("injected replace failure")

    monkeypatch.setattr(uuid, "uuid4", lambda: fixed)
    monkeypatch.setattr(os, "replace", fail_after_substitution)

    with pytest.raises(DurableFileReplaceError, match="cannot replace value.bin"):
        replace_file_bytes_durable(directory, "value.bin", b"new")

    assert temporary.read_bytes() == b"substituted"
    assert (directory / "value.bin").read_bytes() == b"old"


def test_replacement_reports_final_byte_drift_as_integrity_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    directory = tmp_path / "store"
    directory.mkdir()
    original_replace = os.replace

    def replace_with_different_bytes(
        source: _PathArgument,
        destination: _PathArgument,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        descriptor = os.open(source, os.O_WRONLY | os.O_TRUNC, dir_fd=src_dir_fd)
        try:
            os.write(descriptor, b"different")
        finally:
            os.close(descriptor)
        original_replace(
            source,
            destination,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    monkeypatch.setattr(os, "replace", replace_with_different_bytes)

    with pytest.raises(DurableFileReplaceIntegrityError, match="bytes changed"):
        replace_file_bytes_durable(directory, "value.bin", b"expected")

    assert (directory / "value.bin").read_bytes() == b"different"
