# ABOUTME: Kills real pump-station processes after each durable publication boundary.
# ABOUTME: Proves retry and reconciliation prevent torn authority and duplicate effects.

from __future__ import annotations

import multiprocessing
import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Never, Protocol

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station import (
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PUMP_STATION_RECORD_VERSIONS_V3,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    PumpStationInformationSet,
    PumpStationPhysicalTreatmentActivationRequest,
    PumpStationPhysicalTreatmentClass,
    PumpStationSchedule,
    PumpStationStagedTransition,
    PumpStationTreatmentSeverity,
    PumpStationWorldRun,
    PumpStationWorldRunError,
    PumpStationWorldRunRepository,
    RequestConditionalDeferral,
    TransferDuty,
    apply_stewardship_proposal,
    create_evidence_health_reference_state,
    load_reference_package,
    pump_station_model_from_package,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationProposal,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_physical_treatment_activation,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    pump_station_artifact_id,
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


class _ProcessSignal(Protocol):
    def set(self) -> None: ...

    def wait(self, timeout: float | None = None) -> bool: ...


class _ProcessResults(Protocol):
    def get(self, timeout: float | None = None) -> object: ...

    def put(self, value: object) -> None: ...


class _ChildProcess(Protocol):
    @property
    def exitcode(self) -> int | None: ...

    def is_alive(self) -> bool: ...

    def join(self, timeout: float | None = None) -> None: ...

    def kill(self) -> None: ...


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
        if _path_from_directory_descriptor(root, dst, dst_dir_fd) == root / "current.json":
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


def _publish_staged_in_child(
    root: Path,
    staged: PumpStationStagedTransition,
    ready: _ProcessSignal,
    start: _ProcessSignal,
    finished: _ProcessSignal,
    results: _ProcessResults,
) -> None:
    repository = PumpStationWorldRunRepository(root)
    ready.set()
    if not start.wait(5):
        raise RuntimeError("staged publication start signal was not received")
    try:
        repository.publish_staged_transition(staged)
    except PumpStationWorldRunError as error:
        results.put(("error", error.code))
    else:
        results.put(("published", staged.snapshot.commit_id))
    finally:
        finished.set()


def _crash_during_staged_publication(
    root: Path,
    boundary: str,
    staged: PumpStationStagedTransition,
) -> None:
    repository = PumpStationWorldRunRepository(root)
    _install_publication_crash(root, boundary)
    repository.publish_staged_transition(staged)


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


def _join_process(process: _ChildProcess) -> None:
    process.join(10)
    if process.is_alive():
        process.kill()
        process.join()
        pytest.fail("staged publication process did not stop")
    assert process.exitcode == 0


def test_direct_staged_publication_waits_for_the_run_lock(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-lock-owner",
        pump_id="pump-a",
    )
    staged = run.stage(proposal, information_set=information_set)
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    start = context.Event()
    finished = context.Event()
    results = context.Queue()
    process = context.Process(
        target=_publish_staged_in_child,
        args=(run.repository.root, staged, ready, start, finished, results),
    )

    process.start()
    try:
        assert ready.wait(5)
        with run.repository.locked():
            start.set()
            assert not finished.wait(0.5)
        assert finished.wait(5)
        _join_process(process)
    finally:
        start.set()
        if process.is_alive():
            process.kill()
            process.join()

    assert results.get(timeout=5) == ("published", staged.snapshot.commit_id)
    assert run.snapshot() == staged.snapshot


def test_combined_transition_paths_enter_the_run_lock_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_run = create_world_run(tmp_path / "actor-run")
    actor_proposal, actor_information = bind_proposal(
        actor_run,
        RequestConditionalDeferral,
        "proposal-single-lock",
        pump_id="pump-a",
    )
    physical_run = create_world_run(tmp_path / "physical-run")
    physical_snapshot = physical_run.snapshot()
    physical_request = PumpStationPhysicalTreatmentActivationRequest(
        request_id="treatment-single-lock.activation",
        schedule_request_id="treatment-single-lock",
        run_id=physical_snapshot.run_id,
        episode_id=physical_snapshot.episode_id,
        world_branch_id=physical_snapshot.world_branch_id,
        base_state_id=physical_snapshot.state_id,
        base_commit_id=physical_snapshot.commit_id,
        based_on_sequence=physical_snapshot.sequence,
        parent_state_id=physical_snapshot.state_id,
        treatment_class=PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=("pump-a",),
        activation_calendar_seconds=physical_run.state.physical.calendar_seconds,
        severity=PumpStationTreatmentSeverity.LOW,
        random_stream_id="treatment-single-lock-stream",
        random_seed=17,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id=PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    )
    package = load_reference_package()
    model = pump_station_model_from_package(package)
    schedule = PumpStationSchedule(
        access_available_after_seconds=86_400,
        repair_kit_available_after_seconds=86_400,
        decision_point_after_seconds=(3_600,),
    )
    evidence_run = PumpStationWorldRun.create(
        repository=PumpStationWorldRunRepository(tmp_path / "evidence-run"),
        package=package,
        model=model,
        initial_state=create_evidence_health_reference_state(
            model,
            schedule=schedule,
        ),
        run_id="run-single-lock-evidence",
        episode_id="episode-single-lock-evidence",
        world_branch_id="branch-single-lock-evidence",
        record_versions=PUMP_STATION_RECORD_VERSIONS_V3,
    )
    evidence_snapshot = evidence_run.snapshot()
    decision_point = min(
        event.scheduled_seconds
        for event in evidence_run.state.scheduled_events
        if event.event_type.value == "decision_point"
    )
    evidence_request = PumpStationEvidenceTreatmentRequest(
        request_id="treatment-single-lock-evidence",
        run_id=evidence_snapshot.run_id,
        episode_id=evidence_snapshot.episode_id,
        world_branch_id=evidence_snapshot.world_branch_id,
        base_state_id=evidence_snapshot.state_id,
        base_commit_id=evidence_snapshot.commit_id,
        based_on_sequence=evidence_snapshot.sequence,
        treatment_class=PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE,
        treatment_version=PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        target_source_id="station-condition-sensor",
        effective_decision_point_seconds=decision_point,
        visibility_policy=PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    )
    original_locked = PumpStationWorldRunRepository.locked
    lock_depth = 0
    lock_entries = 0

    @contextmanager
    def single_entry_lock(
        repository: PumpStationWorldRunRepository,
    ) -> Iterator[None]:
        nonlocal lock_depth, lock_entries
        if lock_depth:
            raise AssertionError("combined transition entered the run lock twice")
        lock_depth += 1
        lock_entries += 1
        try:
            with original_locked(repository):
                yield
        finally:
            lock_depth -= 1

    monkeypatch.setattr(
        PumpStationWorldRunRepository,
        "locked",
        single_entry_lock,
    )

    actor_run.apply(actor_proposal, information_set=actor_information)
    evidence_run.schedule_evidence_treatment(evidence_request)
    physical_run.apply_physical_treatment(physical_request)

    assert lock_entries == 3
    assert lock_depth == 0


def test_concurrent_staged_publications_select_exactly_one_transition(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    first_proposal, first_information = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-concurrent-first",
        pump_id="pump-a",
    )
    second_proposal, second_information = bind_proposal(
        run,
        TransferDuty,
        "proposal-concurrent-second",
    )
    staged = (
        run.stage(first_proposal, information_set=first_information),
        run.stage(second_proposal, information_set=second_information),
    )
    context = multiprocessing.get_context("spawn")
    ready = (context.Event(), context.Event())
    start = context.Event()
    finished = (context.Event(), context.Event())
    results = context.Queue()
    processes = tuple(
        context.Process(
            target=_publish_staged_in_child,
            args=(run.repository.root, item, ready[index], start, finished[index], results),
        )
        for index, item in enumerate(staged)
    )

    for process in processes:
        process.start()
    try:
        assert all(signal.wait(5) for signal in ready)
        start.set()
        assert all(signal.wait(5) for signal in finished)
        for process in processes:
            _join_process(process)
    finally:
        start.set()
        for process in processes:
            if process.is_alive():
                process.kill()
                process.join()

    outcomes = {results.get(timeout=5) for _ in processes}
    assert {outcome[0] for outcome in outcomes} == {"error", "published"}
    assert ("error", "stale-publication") in outcomes
    selected = run.snapshot()
    assert selected in tuple(item.snapshot for item in staged)
    assert len(run.steps()) == 1


def test_selected_staged_publication_retries_without_another_effect(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-direct-retry",
        pump_id="pump-a",
    )
    staged = run.stage(proposal, information_set=information_set)

    first = run.repository.publish_staged_transition(staged)
    repeated = run.repository.publish_staged_transition(staged)

    assert repeated == first
    assert run.snapshot() == staged.snapshot
    assert len(run.repository.commits()) == 2
    assert len(run.steps()) == 1


def test_selected_staged_retry_rejects_a_mismatched_commit(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    first_proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-selected-retry",
        pump_id="pump-a",
    )
    second_proposal, second_information = bind_proposal(
        run,
        TransferDuty,
        "proposal-unselected-retry",
    )
    selected = run.stage(first_proposal, information_set=information_set)
    unselected = run.stage(second_proposal, information_set=second_information)
    run.repository.publish_staged_transition(selected)

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_staged_transition(
            replace(selected, commit=unselected.commit),
        )

    assert raised.value.code == "transition-integrity"
    assert run.snapshot() == selected.snapshot
    assert len(run.steps()) == 1


def test_staged_publication_returns_the_durable_transition(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    selected_proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-durable-return",
        pump_id="pump-a",
    )
    other_proposal, other_information = bind_proposal(
        run,
        TransferDuty,
        "proposal-caller-transition",
    )
    selected = run.stage(selected_proposal, information_set=information_set)
    other = run.stage(other_proposal, information_set=other_information)

    returned = run.repository.publish_staged_transition(
        replace(selected, transition=other.transition),
    )

    assert returned == selected.transition
    assert run.snapshot() == selected.snapshot
    assert run.steps()[0].transition == selected.transition


def test_staged_publication_rejects_a_snapshot_that_differs_from_its_commit(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-snapshot-integrity",
        pump_id="pump-a",
    )
    staged = run.stage(proposal, information_set=information_set)
    corrupted = replace(
        staged,
        snapshot=replace(
            staged.snapshot,
            state_id=staged.prior_snapshot.state_id,
        ),
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_staged_transition(corrupted)

    assert raised.value.code == "transition-integrity"
    assert run.snapshot() == staged.prior_snapshot
    assert run.steps() == ()


def test_staged_publication_rejects_a_missing_immutable_commit(tmp_path: Path) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-missing-commit",
        pump_id="pump-a",
    )
    staged = run.stage(proposal, information_set=information_set)
    (run.repository.root / "commits" / f"{staged.snapshot.commit_id}.json").unlink()

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_staged_transition(staged)

    assert raised.value.code == "artifact-integrity"
    assert run.snapshot() == staged.prior_snapshot
    assert run.steps() == ()


def test_staged_publication_rejects_a_receipt_from_another_parent_state(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-receipt-parent",
        pump_id="pump-a",
    )
    staged = run.stage(proposal, information_set=information_set)
    receipt = replace(
        staged.transition.receipt,
        pre_state_id="state-from-another-parent",
    )
    receipt_content_id = pump_station_artifact_id(receipt)
    run.repository._publish_content("receipts", receipt_content_id, receipt)
    commit = replace(
        staged.commit,
        receipt_content_id=receipt_content_id,
    )
    commit_id = pump_station_artifact_id(commit)
    run.repository._publish_content("commits", commit_id, commit)
    corrupted = replace(
        staged,
        snapshot=replace(staged.snapshot, commit_id=commit_id),
        transition=replace(staged.transition, receipt=receipt),
        commit=commit,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_staged_transition(corrupted)

    assert raised.value.code == "transition-integrity"
    assert run.snapshot() == staged.prior_snapshot
    assert run.steps() == ()


def test_staged_publication_rejects_an_actor_input_from_another_sequence(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-actor-parent",
        pump_id="pump-a",
    )
    prior = run.snapshot()
    transition = apply_stewardship_proposal(
        run.model,
        run.state,
        proposal,
        information_set=information_set,
    )
    mismatched = replace(
        proposal,
        context=replace(
            proposal.context,
            based_on_sequence=prior.sequence + 9,
        ),
    )
    staged = run.repository.stage_transition(
        manifest=run.manifest,
        prior_snapshot=prior,
        proposal=mismatched,
        information_set=information_set,
        transition=transition,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_staged_transition(staged)

    assert raised.value.code == "transition-integrity"
    assert run.snapshot() == prior
    assert run.steps() == ()


def test_staged_publication_rejects_a_control_input_from_another_commit(
    tmp_path: Path,
) -> None:
    run = create_world_run(tmp_path / "run")
    prior = run.snapshot()
    request = PumpStationPhysicalTreatmentActivationRequest(
        request_id="treatment-parent-binding.activation",
        schedule_request_id="treatment-parent-binding",
        run_id=prior.run_id,
        episode_id=prior.episode_id,
        world_branch_id=prior.world_branch_id,
        base_state_id=prior.state_id,
        base_commit_id=prior.commit_id,
        based_on_sequence=prior.sequence,
        parent_state_id=prior.state_id,
        treatment_class=PumpStationPhysicalTreatmentClass.RECURRENT_OBSTRUCTION,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=("pump-a",),
        activation_calendar_seconds=run.state.physical.calendar_seconds,
        severity=PumpStationTreatmentSeverity.LOW,
        random_stream_id="treatment-parent-binding-stream",
        random_seed=11,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id=PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    )
    transition = apply_physical_treatment_activation(run.state, request)
    staged = run.repository.stage_control_transition(
        manifest=run.manifest,
        prior_snapshot=prior,
        control_request=request,
        transition=transition,
    )
    mismatched = replace(
        request,
        base_commit_id="commit-from-another-parent",
    )
    request_content_id = pump_station_artifact_id(mismatched)
    run.repository._publish_content(
        "control-requests",
        request_content_id,
        mismatched,
    )
    commit = replace(
        staged.commit,
        proposal_content_id=request_content_id,
    )
    commit_id = pump_station_artifact_id(commit)
    run.repository._publish_content("commits", commit_id, commit)
    corrupted = replace(
        staged,
        snapshot=replace(staged.snapshot, commit_id=commit_id),
        commit=commit,
        control_request=mismatched,
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_staged_transition(corrupted)

    assert raised.value.code == "transition-integrity"
    assert run.snapshot() == prior
    assert run.steps() == ()


@pytest.mark.parametrize(
    "boundary",
    ("current-before-replace", "current-after-replace"),
)
def test_direct_staged_publication_recovers_once_after_process_death(
    tmp_path: Path,
    boundary: str,
) -> None:
    run = create_world_run(tmp_path / "run")
    proposal, information_set = bind_proposal(
        run,
        RequestConditionalDeferral,
        "proposal-direct-crash",
        pump_id="pump-a",
    )
    staged = run.stage(proposal, information_set=information_set)

    _assert_expected_crash(
        _crash_during_staged_publication,
        run.repository.root,
        boundary,
        staged,
    )
    recovered = run.repository.publish_staged_transition(staged)
    repeated = run.repository.publish_staged_transition(staged)

    assert repeated == recovered == staged.transition
    assert run.snapshot() == staged.snapshot
    assert len(run.repository.commits()) == 2
    assert len(run.steps()) == 1


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
