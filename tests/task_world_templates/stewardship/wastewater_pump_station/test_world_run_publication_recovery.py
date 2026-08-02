# ABOUTME: Kills real pump-station processes after each durable publication boundary.
# ABOUTME: Proves retry and reconciliation prevent torn authority and duplicate effects.

from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable
from pathlib import Path
from typing import Never

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PumpStationInformationSet,
    PumpStationWorldRun,
    PumpStationWorldRunRepository,
    RequestConditionalDeferral,
    TransferDuty,
    load_reference_package,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationProposal,
)
from tests.task_world_templates.stewardship.wastewater_pump_station.world_run_support import (
    bind_proposal,
    create_world_run,
)

_CRASH_EXIT_CODE = 93
_INITIALIZATION_ARTIFACTS = ("manifest", "state", "commit")
_TRANSITION_ARTIFACTS = (
    "state",
    "proposal",
    "information-set",
    "receipt",
    "event",
    "commit",
)
_LINK_PHASES = ("before-link", "after-link")
_INITIALIZATION_BOUNDARIES = tuple(
    f"{artifact}-{phase}" for artifact in _INITIALIZATION_ARTIFACTS for phase in _LINK_PHASES
) + (
    "current-before-replace",
    "current-after-replace",
)
_TRANSITION_BOUNDARIES = tuple(
    f"{artifact}-{phase}" for artifact in _TRANSITION_ARTIFACTS for phase in _LINK_PHASES
) + (
    "current-before-replace",
    "current-after-replace",
)
type _PathArgument = str | bytes | os.PathLike[str] | os.PathLike[bytes]
_ORIGINAL_LINK = os.link
_ORIGINAL_REPLACE = os.replace


def _crash() -> Never:
    os._exit(_CRASH_EXIT_CODE)


def _path_from_directory_descriptor(
    root: Path,
    path: _PathArgument,
    directory_descriptor: int | None,
) -> Path:
    selected = Path(os.fsdecode(path))
    if selected.is_absolute() or directory_descriptor is None:
        return selected

    target = os.fstat(directory_descriptor)
    candidates = (root, *(item for item in root.iterdir() if item.is_dir()))
    for candidate in candidates:
        details = candidate.stat()
        if (details.st_dev, details.st_ino) == (target.st_dev, target.st_ino):
            return candidate / selected
    raise AssertionError("publication directory descriptor is outside the pump run")


def _artifact_for_path(
    root: Path,
    path: _PathArgument,
    directory_descriptor: int | None = None,
) -> str | None:
    absolute = _path_from_directory_descriptor(root, path, directory_descriptor)
    relative = absolute.relative_to(root)
    key = relative.name if len(relative.parts) == 1 else relative.parts[0]
    return {
        "manifest.json": "manifest",
        "states": "state",
        "proposals": "proposal",
        "information-sets": "information-set",
        "receipts": "receipt",
        "events": "event",
        "commits": "commit",
    }.get(key)


def _install_publication_crash(root: Path, boundary: str) -> None:
    def crash_link(
        src: _PathArgument,
        dst: _PathArgument,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
        follow_symlinks: bool = True,
    ) -> None:
        artifact = _artifact_for_path(root, dst, dst_dir_fd)
        if boundary == f"{artifact}-before-link":
            _crash()
        _ORIGINAL_LINK(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
            follow_symlinks=follow_symlinks,
        )
        if boundary == f"{artifact}-after-link":
            _crash()

    def crash_replace(
        src: _PathArgument,
        dst: _PathArgument,
        *,
        src_dir_fd: int | None = None,
        dst_dir_fd: int | None = None,
    ) -> None:
        if Path(os.fsdecode(dst)) == root / "current.json":
            if boundary == "current-before-replace":
                _crash()
            _ORIGINAL_REPLACE(
                src,
                dst,
                src_dir_fd=src_dir_fd,
                dst_dir_fd=dst_dir_fd,
            )
            if boundary == "current-after-replace":
                _crash()
            return
        _ORIGINAL_REPLACE(
            src,
            dst,
            src_dir_fd=src_dir_fd,
            dst_dir_fd=dst_dir_fd,
        )

    os.link = crash_link
    os.replace = crash_replace


def _crash_during_initialization(root: Path, boundary: str) -> None:
    _install_publication_crash(root, boundary)
    create_world_run(root)


def _crash_during_transition(
    root: Path,
    boundary: str,
    proposal: PumpStationProposal,
    information_set: PumpStationInformationSet,
) -> None:
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    repository = PumpStationWorldRunRepository(root)
    run = PumpStationWorldRun.resume(
        repository=repository,
        package=package,
        model=model,
        snapshot=repository.current_snapshot(),
    )
    _install_publication_crash(root, boundary)
    run.apply(proposal, information_set=information_set)


def _assert_expected_crash(target: Callable[..., object], *args: object) -> None:
    context = multiprocessing.get_context("spawn")
    process = context.Process(target=target, args=args)
    process.start()
    process.join(20)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("fault-injection process did not stop")
    assert process.exitcode == _CRASH_EXIT_CODE


@pytest.mark.parametrize("boundary", _INITIALIZATION_BOUNDARIES)
def test_initialization_recovers_at_every_publication_boundary(
    tmp_path: Path,
    boundary: str,
) -> None:
    root = tmp_path / "run"

    _assert_expected_crash(_crash_during_initialization, root, boundary)
    recovered = create_world_run(root)

    assert recovered.snapshot().sequence == 0
    assert len(recovered.repository.commits()) == 1
    assert recovered.steps() == ()


@pytest.mark.parametrize("boundary", _TRANSITION_BOUNDARIES)
@pytest.mark.parametrize(
    ("proposal_type", "proposal_id"),
    (
        (RequestConditionalDeferral, "proposal-resource-effect"),
        (TransferDuty, "proposal-physical-effect"),
    ),
)
def test_transition_recovers_once_at_every_publication_boundary(
    tmp_path: Path,
    boundary: str,
    proposal_type: type[PumpStationProposal],
    proposal_id: str,
) -> None:
    root = tmp_path / "run"
    run = create_world_run(root)
    proposal, information_set = bind_proposal(
        run,
        proposal_type,
        proposal_id,
        **({"pump_id": "pump-a"} if proposal_type is RequestConditionalDeferral else {}),
    )

    _assert_expected_crash(
        _crash_during_transition,
        root,
        boundary,
        proposal,
        information_set,
    )
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    repository = PumpStationWorldRunRepository(root)
    recovered = PumpStationWorldRun.resume(
        repository=repository,
        package=package,
        model=model,
        snapshot=repository.current_snapshot(),
    )
    first = recovered.apply(proposal, information_set=information_set)
    repeated = recovered.apply(proposal, information_set=information_set)

    assert repeated == first
    assert recovered.state.sequence == 1
    assert len(recovered.steps()) == 1
    if proposal_type is RequestConditionalDeferral:
        assert len(recovered.state.restrictions) == 1
        assert len(recovered.state.obligations) == 1
        assert len(recovered.state.work_orders) == 1
    else:
        assert recovered.state.physical.duty_pump_id == "pump-b"
        assert recovered.state.physical.duty_transfer_count == 1
