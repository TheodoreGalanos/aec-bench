# ABOUTME: Proves registered pump worlds use the existing session and separate host-control surfaces.
# ABOUTME: Covers exact actor binding, durable retry, continuity, temporal access, and V4 verification.

from __future__ import annotations

import json
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import JsonValue

from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldControlRequest,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.world_interface import invoke_world_actor, observe_world_actor
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.actor_interface import (
    PUMP_STATION_ACTOR_ACTION_NAMES_V2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.continual_definition import (
    pump_station_continual_world_definition,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationCoupledModel,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PUMP_STATION_OPERATIONS_REVIEW_VERSION,
    PUMP_STATION_PROCESS_OUTCOME_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationCoupledStewardshipState,
    PumpStationOperationsBoundaryReviewRequest,
    PumpStationProcessOutcomeRequest,
    PumpStationRootControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationWorldControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_SESSION_HOST_AUTHORITY_ID,
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)

type RegisteredRun = PumpStationWorldRun[
    PumpStationCoupledModel,
    PumpStationCoupledStewardshipState,
]


def _session_request(
    *,
    run_id: str = "registered-session-run",
    episode_id: str = "registered-session-episode",
    world_branch_id: str = "registered-session-branch",
    session_id: str = "registered-session",
    agent_tenure_id: str = "registered-tenure",
    open_mode: WorldSessionOpenMode = WorldSessionOpenMode.START,
    start_snapshot: StewardshipStateSnapshotRef | None = None,
) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=open_mode,
        session_id=session_id,
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=agent_tenure_id,
        run_id=run_id,
        episode_id=episode_id,
        world_branch_id=world_branch_id,
        start_snapshot=start_snapshot,
    )


def _shared_snapshot(run: RegisteredRun) -> StewardshipStateSnapshotRef:
    snapshot = run.snapshot()
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _create_registered_run(root: Path) -> RegisteredRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="registered-session-run",
        episode_id="registered-session-episode",
        world_branch_id="registered-session-branch",
    )


def _resume_registered_session(
    root: Path,
    run: RegisteredRun,
    *,
    session_id: str = "registered-session",
    agent_tenure_id: str = "registered-tenure",
    host_authority_id: str = PUMP_STATION_SESSION_HOST_AUTHORITY_ID,
) -> PumpStationWorldSession:
    return PumpStationWorldSessionFactory(
        root,
        host_authority_id=host_authority_id,
    ).open(
        _session_request(
            open_mode=WorldSessionOpenMode.RESUME,
            start_snapshot=_shared_snapshot(run),
            session_id=session_id,
            agent_tenure_id=agent_tenure_id,
        )
    )


def _condition_check_request(
    session: PumpStationWorldSession,
    *,
    request_id: str,
    pump_id: str = "pump-a",
) -> WorldActorActionRequest:
    return WorldActorActionRequest(
        request_id=request_id,
        action_name="request_condition_check",
        binding=observe_world_actor(session).binding,
        arguments={
            "pump_id": pump_id,
            "reason": f"Record the visible condition of {pump_id}.",
        },
    )


def _common_boundary_request(
    run: RegisteredRun,
    *,
    request_id: str,
) -> PumpStationBoundControlRequest:
    snapshot = run.snapshot()
    return PumpStationBoundControlRequest(
        control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
        request_id=request_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=PumpStationCommonBoundaryRequest(
            version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
            request_id=request_id,
            authority_id="operations-controller",
            boundary_kind="power",
            available=False,
            base_state_id=snapshot.state_id,
        ),
    )


def _bound_root_control_request(
    run: RegisteredRun,
    control: PumpStationRootControl,
) -> PumpStationBoundControlRequest:
    snapshot = run.snapshot()
    request_id = (
        control.review_id if isinstance(control, PumpStationOperationsBoundaryReviewRequest) else control.request_id
    )
    return PumpStationBoundControlRequest(
        control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
        request_id=request_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=control,
    )


def _opaque_reference(value: JsonValue) -> str:
    assert isinstance(value, list)
    assert value
    first = value[0]
    assert isinstance(first, dict)
    reference = first.get("opaque_reference")
    assert isinstance(reference, str)
    return reference


def test_registered_factory_exactly_reattaches_then_replaces_with_fresh_session(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    profile_ref = pump_station_continual_world_definition().spec.profiles[0]
    start = _session_request()
    started = PumpStationWorldSessionFactory(
        root,
        profile_ref=profile_ref,
    ).open(start)
    observation = observe_world_actor(started)

    assert observation.binding.session_id == start.session_id
    assert observation.binding.agent_tenure_id == start.agent_tenure_id
    assert observation.binding.commit_id == started.result.snapshot.commit_id
    assert observation.binding.actor_view_id == started.result.actor_view_id
    assert observation.binding.information_set_id == started.result.information_set_id
    assert tuple(action.name for action in started.actor_capabilities.actions) == (PUMP_STATION_ACTOR_ACTION_NAMES_V2)
    assert observation.view["projection_policy_id"] == "pump-station-current-state.v5"
    serialized_view = json.dumps(observation.view, sort_keys=True)
    assert '"obstruction":' not in serialized_view
    assert '"clearance_loss":' not in serialized_view
    opening_activation = started.run.repository.load_selected_session_activation()

    reattached = PumpStationWorldSessionFactory(root).open(
        _session_request(
            open_mode=WorldSessionOpenMode.RESUME,
            start_snapshot=started.result.snapshot,
        )
    )

    assert observe_world_actor(reattached) == observation
    assert reattached.run.repository.load_selected_session_activation() == opening_activation

    replacement = PumpStationWorldSessionFactory(root).open(
        _session_request(
            open_mode=WorldSessionOpenMode.RESUME,
            start_snapshot=started.result.snapshot,
            session_id="registered-session-resumed",
            agent_tenure_id="registered-tenure-resumed",
        )
    )
    replacement_observation = observe_world_actor(replacement)
    replacement_activation = replacement.run.repository.load_selected_session_activation()

    assert replacement.result.snapshot == started.result.snapshot
    assert replacement_observation.binding.session_id == "registered-session-resumed"
    assert replacement_observation.binding.agent_tenure_id == "registered-tenure-resumed"
    assert replacement_activation.prior_binding_id == opening_activation.binding_id


def test_registered_control_opens_the_existing_session_interface(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    profile_ref = pump_station_continual_world_definition().spec.profiles[0]
    session_request = _session_request()
    control = PumpStationWorldControl(
        root,
        authorised_principal_ids=("session-host",),
        profile_ref=profile_ref,
    )

    opened = control.execute(
        WorldControlRequest(
            request_id="open-registered-session",
            operation="create_session",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="session-host",
            session_request=session_request,
        )
    )

    assert opened.session_result is not None
    assert opened.session_result.session_id == session_request.session_id
    assert opened.session_result.tool_names == PUMP_STATION_ACTOR_ACTION_NAMES_V2
    reattached = PumpStationWorldSessionFactory(
        root,
        host_authority_id="session-host",
    ).open(
        _session_request(
            open_mode=WorldSessionOpenMode.RESUME,
            start_snapshot=opened.session_result.snapshot,
        )
    )
    assert observe_world_actor(reattached).binding.session_id == session_request.session_id


def test_interrupted_first_session_activation_recovers_on_resume(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    factory = PumpStationWorldSessionFactory(root)

    def interrupt_activation(_: object) -> None:
        raise OSError("simulated interruption before first session selection")

    monkeypatch.setattr(
        factory._repository,
        "_publish_session_activation_under_lock",
        interrupt_activation,
    )
    with pytest.raises(OSError, match="simulated interruption"):
        factory.open(
            _session_request(
                open_mode=WorldSessionOpenMode.RESUME,
                start_snapshot=_shared_snapshot(run),
            )
        )

    recovered = _resume_registered_session(root, run)

    assert observe_world_actor(recovered).binding.session_id == "registered-session"
    assert run.verify_v4().valid


def test_interrupted_recipient_activation_recovers_without_reopening_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    source = _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    factory = PumpStationWorldSessionFactory(root)

    def interrupt_activation(_: object) -> None:
        raise OSError("simulated interruption before recipient selection")

    monkeypatch.setattr(
        factory._repository,
        "_publish_session_activation_under_lock",
        interrupt_activation,
    )
    with pytest.raises(OSError, match="simulated interruption"):
        factory.open(
            _session_request(
                open_mode=WorldSessionOpenMode.RESUME,
                start_snapshot=_shared_snapshot(run),
                session_id="recipient-session",
                agent_tenure_id="recipient-tenure",
            )
        )

    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )

    assert observe_world_actor(recipient).binding.session_id == "recipient-session"
    with pytest.raises(WorldInterfaceError) as closed:
        observe_world_actor(source)
    assert closed.value.code == "actor-session-revoked"
    assert run.verify_v4().valid


def test_registered_actor_retry_survives_reopen_and_rejects_stale_or_foreign_scope(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    request = _condition_check_request(
        session,
        request_id="condition-check-durable-session",
    )

    first = invoke_world_actor(session, request)
    selected = run.snapshot()
    reopened = _resume_registered_session(root, run)
    retried = invoke_world_actor(reopened, request)

    assert retried == first
    assert run.snapshot() == selected
    assert len(run.repository.v4_steps()) == 1

    stale = WorldActorActionRequest(
        request_id="condition-check-stale-session",
        action_name="request_condition_check",
        binding=request.binding,
        arguments={
            "pump_id": "pump-b",
            "reason": "Try to act from the prior session snapshot.",
        },
    )
    with pytest.raises(WorldInterfaceError) as stale_failure:
        invoke_world_actor(reopened, stale)
    assert stale_failure.value.code == "actor-stale-sequence"

    foreign = WorldActorActionRequest(
        request_id="condition-check-foreign-session",
        action_name="request_condition_check",
        binding=reopened.current_actor_binding.model_copy(
            update={"world_branch_id": "foreign-branch"},
        ),
        arguments={
            "pump_id": "pump-b",
            "reason": "Try to act in another world branch.",
        },
    )
    with pytest.raises(WorldInterfaceError) as foreign_failure:
        invoke_world_actor(reopened, foreign)
    assert foreign_failure.value.code == "actor-wrong-world"
    assert run.snapshot() == selected


def test_registered_actor_retry_preserves_exact_effect_and_current_view_after_newer_action(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    first_request = _condition_check_request(
        session,
        request_id="earlier-condition-check",
        pump_id="pump-a",
    )
    first = invoke_world_actor(session, first_request)
    second = invoke_world_actor(
        session,
        _condition_check_request(
            session,
            request_id="later-condition-check",
            pump_id="pump-b",
        ),
    )
    current = observe_world_actor(session)

    retried = invoke_world_actor(session, first_request)

    assert retried.request_content_sha256 == first.request_content_sha256
    assert retried.action_name == first.action_name
    assert retried.status == first.status
    assert retried.pre_binding == first.pre_binding
    assert retried.task_receipt == first.task_receipt
    assert retried.post_binding == second.post_binding
    assert retried.next_observation == current
    assert observe_world_actor(session) == current
    assert len(run.repository.v4_steps()) == 2


def test_registered_actor_retry_refreshes_current_view_after_root_control(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    request = _condition_check_request(
        session,
        request_id="condition-check-before-root-control",
    )
    first = invoke_world_actor(session, request)
    PumpStationWorldControl(
        root,
        authorised_principal_ids=("operations-controller",),
    ).execute(
        _common_boundary_request(
            run,
            request_id="root-control-before-actor-retry",
        )
    )

    retried = invoke_world_actor(session, request)

    assert retried.request_content_sha256 == first.request_content_sha256
    assert retried.status == first.status
    assert retried.pre_binding == first.pre_binding
    assert retried.task_receipt == first.task_receipt
    assert retried.post_binding.sequence == run.snapshot().sequence
    assert retried.next_observation.view["sequence"] == run.snapshot().sequence
    assert observe_world_actor(session) == retried.next_observation
    assert len(run.repository.v4_steps()) == 2


def test_closed_session_cannot_retry_committed_actor_action_after_replacement(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    source = _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    source_request = _condition_check_request(
        source,
        request_id="source-condition-check-before-replacement",
    )
    invoke_world_actor(source, source_request)
    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    invoke_world_actor(
        recipient,
        _condition_check_request(
            recipient,
            request_id="recipient-condition-check-after-replacement",
            pump_id="pump-b",
        ),
    )

    with pytest.raises(WorldInterfaceError) as revoked:
        invoke_world_actor(source, source_request)

    assert revoked.value.code == "actor-session-revoked"
    assert len(run.repository.v4_steps()) == 2


def test_registered_actor_projection_refresh_runs_inside_world_lock(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    request = _condition_check_request(
        session,
        request_id="condition-check-under-session-lock",
    )
    original_locked = session.run.repository.locked
    original_refresh = session._refresh_registered_projection_if_needed
    lock_depth = 0

    @contextmanager
    def tracked_lock() -> Iterator[None]:
        nonlocal lock_depth
        with original_locked():
            lock_depth += 1
            try:
                yield
            finally:
                lock_depth -= 1

    def require_locked_refresh(*, run_lock_held: bool = False) -> None:
        assert lock_depth == 1
        assert run_lock_held
        original_refresh(run_lock_held=run_lock_held)

    monkeypatch.setattr(session.run.repository, "locked", tracked_lock)
    monkeypatch.setattr(
        session,
        "_refresh_registered_projection_if_needed",
        require_locked_refresh,
    )

    result = invoke_world_actor(session, request)

    assert result.status == "applied"
    assert lock_depth == 0


def test_registered_temporal_projection_and_handover_do_not_create_a_world_transition(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    source = _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    opening = run.snapshot()
    search = invoke_world_actor(
        source,
        WorldActorActionRequest(
            request_id="registered-search",
            action_name="search_evidence",
            binding=observe_world_actor(source).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    reference = _opaque_reference(search.task_receipt["references"])

    assert search.pre_binding.sequence == search.post_binding.sequence
    assert search.pre_binding.state_id == search.post_binding.state_id
    assert search.pre_binding.commit_id == search.post_binding.commit_id
    assert search.pre_binding.actor_view_id == search.post_binding.actor_view_id
    assert search.pre_binding.information_set_id != search.post_binding.information_set_id
    assert run.snapshot() == opening

    fetched = invoke_world_actor(
        source,
        WorldActorActionRequest(
            request_id="registered-fetch",
            action_name="fetch_evidence",
            binding=search.post_binding,
            arguments={"reference": reference},
        ),
    )
    assert fetched.pre_binding.sequence == fetched.post_binding.sequence
    assert fetched.pre_binding.state_id == fetched.post_binding.state_id
    assert fetched.pre_binding.commit_id == fetched.post_binding.commit_id
    assert fetched.pre_binding.information_set_id != fetched.post_binding.information_set_id
    assert run.snapshot() == opening

    carrier = source.create_retrieval_handover(
        to_tenure_id="recipient-tenure",
        to_session_id="recipient-session",
        include_fetched_content=True,
    )
    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    before_handover_information_set_id = recipient.result.information_set_id
    handover = recipient.create_structured_handover(
        maximum_history_entries=8,
    )
    recipient.install_structured_handover(handover)
    recipient.install_retrieval_handover(carrier)

    assert recipient.result.information_set_id != before_handover_information_set_id
    assert run.snapshot() == opening
    assert len(run.repository.v4_steps()) == 0
    assert run.repository.load_structured_handover(handover.handover_id) == handover

    reopened_recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    assert reopened_recipient.structured_handover == handover

    with pytest.raises(WorldInterfaceError) as revoked:
        invoke_world_actor(
            source,
            _condition_check_request(
                source,
                request_id="revoked-source-condition-check",
            ),
        )
    assert revoked.value.code == "actor-session-revoked"
    assert run.snapshot() == opening

    invoked = invoke_world_actor(
        recipient,
        _condition_check_request(
            recipient,
            request_id="recipient-condition-check",
        ),
    )
    assert invoked.post_binding.sequence == opening.sequence + 1


def test_registered_temporal_retry_survives_session_reopen(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    request = WorldActorActionRequest(
        request_id="durable-session-search",
        action_name="search_evidence",
        binding=observe_world_actor(session).binding,
        arguments={
            "query": "controlled test permit",
            "scope": "operations",
            "limit": 1,
        },
    )
    first = invoke_world_actor(session, request)
    selected = run.snapshot()
    reopened = _resume_registered_session(root, run)

    retried = invoke_world_actor(reopened, request)

    assert retried == first
    assert run.snapshot() == selected
    assert len(run.repository.v4_steps()) == 0

    with pytest.raises(WorldInterfaceError) as changed:
        invoke_world_actor(
            reopened,
            request.model_copy(
                update={
                    "arguments": {
                        "query": "another document",
                        "scope": "operations",
                        "limit": 1,
                    }
                }
            ),
        )
    assert changed.value.code == "actor-request-id-conflict"
    assert run.snapshot() == selected


def test_registered_temporal_retry_preserves_exact_effect_and_current_view_after_newer_access(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    first_request = WorldActorActionRequest(
        request_id="earlier-durable-session-search",
        action_name="search_evidence",
        binding=observe_world_actor(session).binding,
        arguments={
            "query": "controlled test permit",
            "scope": "operations",
            "limit": 1,
        },
    )
    first = invoke_world_actor(session, first_request)
    second_request = WorldActorActionRequest(
        request_id="later-durable-session-search",
        action_name="search_evidence",
        binding=first.post_binding,
        arguments={
            "query": "pump obstruction procedure",
            "scope": "operations",
            "limit": 1,
        },
    )
    second = invoke_world_actor(session, second_request)
    reopened = _resume_registered_session(root, run)
    current = observe_world_actor(reopened)

    retried = invoke_world_actor(reopened, first_request)

    assert retried.request_content_sha256 == first.request_content_sha256
    assert retried.action_name == first.action_name
    assert retried.status == first.status
    assert retried.pre_binding == first.pre_binding
    assert retried.task_receipt == first.task_receipt
    assert retried.post_binding == second.post_binding
    assert retried.next_observation == current
    assert observe_world_actor(reopened) == current


def test_interrupted_temporal_session_binding_recovers_on_reopen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    request = WorldActorActionRequest(
        request_id="interrupted-session-search",
        action_name="search_evidence",
        binding=observe_world_actor(session).binding,
        arguments={
            "query": "controlled test permit",
            "scope": "operations",
            "limit": 1,
        },
    )

    def interrupt_session_binding(**_: object) -> None:
        raise OSError("simulated interruption before session binding selection")

    monkeypatch.setattr(
        session,
        "_publish_registered_session_binding",
        interrupt_session_binding,
    )
    with pytest.raises(OSError, match="simulated interruption"):
        invoke_world_actor(session, request)
    assert run.snapshot().sequence == 0

    reopened = _resume_registered_session(root, run)
    recovered = invoke_world_actor(reopened, request)

    assert recovered.status == "OK"
    assert run.snapshot().sequence == 0
    assert run.verify_v4().valid


def test_registered_verifier_requires_the_full_visible_handover(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    handover = recipient.create_structured_handover(
        maximum_history_entries=8,
    )
    recipient.install_structured_handover(handover)
    assert run.verify_v4().valid
    (root / "session-authority" / "handovers" / f"{handover.handover_id}.json").unlink()

    report = run.verify_v4()

    assert not report.valid
    assert any(issue.startswith("session-evidence-invalid:") for issue in report.issues)


def test_interrupted_handover_binding_recovers_full_content_on_reopen(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    handover = recipient.create_structured_handover(
        maximum_history_entries=8,
    )

    def interrupt_session_binding(**_: object) -> None:
        raise OSError("simulated interruption before handover binding selection")

    monkeypatch.setattr(
        recipient,
        "_publish_registered_session_binding",
        interrupt_session_binding,
    )
    with pytest.raises(OSError, match="simulated interruption"):
        recipient.install_structured_handover(handover)
    assert run.repository.load_structured_handover(handover.handover_id) == handover

    reopened = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    reopened.install_structured_handover(handover)

    assert reopened.structured_handover == handover
    assert run.snapshot().sequence == 0
    assert run.verify_v4().valid


def test_actor_action_and_handover_admission_share_one_world_lock(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    handover = recipient.create_structured_handover(
        maximum_history_entries=8,
    )
    action = _condition_check_request(
        recipient,
        request_id="concurrent-recipient-condition-check",
    )
    start = Barrier(3)

    def install_handover() -> tuple[str, str]:
        start.wait()
        try:
            recipient.install_structured_handover(handover)
        except (PumpStationWorldRunError, ValueError, WorldInterfaceError) as error:
            return "handover", type(error).__name__
        return "handover", "accepted"

    def invoke_action() -> tuple[str, str]:
        start.wait()
        try:
            invoke_world_actor(recipient, action)
        except (ValueError, WorldInterfaceError) as error:
            return "action", type(error).__name__
        return "action", "accepted"

    with ThreadPoolExecutor(max_workers=2) as executor:
        handover_result = executor.submit(install_handover)
        action_result = executor.submit(invoke_action)
        start.wait()
        outcomes = (handover_result.result(), action_result.result())

    assert sum(status == "accepted" for _, status in outcomes) == 1
    assert run.snapshot().sequence in {0, 1}
    assert len(run.repository.v4_steps()) == run.snapshot().sequence
    assert run.verify_v4().valid


def test_foreign_session_host_cannot_change_or_poison_the_selected_authority(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
        host_authority_id="primary-session-host",
    )
    opening = run.snapshot()
    temporal_root = root / "temporal-evidence"
    temporal_files_before = tuple(
        sorted(path.relative_to(temporal_root).as_posix() for path in temporal_root.rglob("*") if path.is_file())
    )

    with pytest.raises(WorldInterfaceError) as foreign:
        _resume_registered_session(
            root,
            run,
            session_id="recipient-session",
            agent_tenure_id="recipient-tenure",
            host_authority_id="foreign-session-host",
        )

    assert foreign.value.code == "actor-session-authority"
    assert run.snapshot() == opening
    assert (
        tuple(sorted(path.relative_to(temporal_root).as_posix() for path in temporal_root.rglob("*") if path.is_file()))
        == temporal_files_before
    )

    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
        host_authority_id="primary-session-host",
    )
    assert observe_world_actor(recipient).binding.session_id == "recipient-session"


def test_closed_session_reopen_does_not_publish_temporal_context(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    invoke_world_actor(
        recipient,
        _condition_check_request(
            recipient,
            request_id="advance-after-source-session-closes",
        ),
    )
    temporal_root = root / "temporal-evidence"
    before = {
        path.relative_to(temporal_root).as_posix(): path.read_bytes()
        for path in temporal_root.rglob("*")
        if path.is_file()
    }

    with pytest.raises(WorldInterfaceError) as closed:
        _resume_registered_session(
            root,
            run,
            session_id="source-session",
            agent_tenure_id="source-tenure",
        )

    assert closed.value.code == "actor-session-revoked"
    assert {
        path.relative_to(temporal_root).as_posix(): path.read_bytes()
        for path in temporal_root.rglob("*")
        if path.is_file()
    } == before


def test_closed_session_cannot_recover_orphaned_temporal_binding_after_replacement(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    source = _resume_registered_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    search = WorldActorActionRequest(
        request_id="orphaned-source-search",
        action_name="search_evidence",
        binding=observe_world_actor(source).binding,
        arguments={
            "query": "controlled test permit",
            "scope": "operations",
            "limit": 1,
        },
    )

    def interrupt_activation(_: object) -> None:
        raise OSError("simulated interruption after temporal publication")

    monkeypatch.setattr(
        source.run.repository,
        "_publish_session_activation_under_lock",
        interrupt_activation,
    )
    with pytest.raises(OSError, match="after temporal publication"):
        invoke_world_actor(source, search)

    recipient = _resume_registered_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )

    with pytest.raises(WorldInterfaceError) as closed:
        _resume_registered_session(
            root,
            run,
            session_id="source-session",
            agent_tenure_id="source-tenure",
        )

    assert closed.value.code == "actor-session-revoked"
    assert observe_world_actor(recipient).binding.session_id == "recipient-session"


def test_registered_root_control_is_authorised_durable_and_absent_from_actor_capabilities(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    request = _common_boundary_request(
        run,
        request_id="registered-power-unavailable",
    )
    control = PumpStationWorldControl(
        root,
        authorised_principal_ids=("operations-controller",),
    )

    actor_names = {item.name for item in session.actor_capabilities.actions}
    control_names = {item.operation for item in control.capabilities("operations-controller").operations}
    assert actor_names.isdisjoint(control_names)
    assert "common_boundary" in control_names

    applied = control.execute(request)
    selected = run.snapshot()
    restarted = PumpStationWorldControl(
        root,
        authorised_principal_ids=("operations-controller",),
    )
    retried = restarted.execute(request)

    assert retried == applied
    assert applied.receipt.state_changed
    assert applied.transition_receipt["action_or_control_kind"] == ("common_boundary_control")
    assert run.snapshot() == selected
    assert len(run.repository.v4_steps()) == 1
    assert "common_boundary" not in actor_names

    unauthorised = PumpStationWorldControl(
        root,
        authorised_principal_ids=("different-controller",),
    )
    with pytest.raises(WorldInterfaceError) as rejected:
        unauthorised.execute(request)
    assert rejected.value.code == "control-unauthorised"
    assert run.snapshot() == selected

    with pytest.raises(WorldInterfaceError) as wrong_envelope:
        restarted.execute(
            WorldControlRequest(
                request_id="generic-common-boundary",
                operation="common_boundary",
                task_world_id=PUMP_STATION_TASK_WORLD_ID,
                authority_id="operations-controller",
            )
        )
    assert wrong_envelope.value.code == "control-request-invalid"
    assert run.snapshot() == selected


def test_registered_process_outcome_uses_the_host_control_surface(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id="start-verification-for-process-outcome",
            action_name="request_post_maintenance_verification",
            binding=observe_world_actor(session).binding,
            arguments={
                "pump_id": "pump-a",
                "backlog_item_id": "backlog-a-verification-001",
                "reason": "Start the independent Pump A verification.",
            },
        ),
    )
    process = run.state.processes[-1]
    request = _bound_root_control_request(
        run,
        PumpStationProcessOutcomeRequest(
            version=PUMP_STATION_PROCESS_OUTCOME_VERSION,
            request_id="record-failed-verification",
            authority_id="verification-engineer-01",
            process_id=process.process_id,
            outcome="failed",
            evidence_id="evidence-verification-failed-001",
            base_state_id=run.state.state_id,
        ),
    )
    control = PumpStationWorldControl(
        root,
        authorised_principal_ids=("verification-engineer-01",),
    )

    result = control.execute(request)

    assert result.receipt.operation == "process_outcome"
    assert result.receipt.state_changed
    assert result.transition_receipt["action_or_control_kind"] == "process_outcome"
    assert run.repository.v4_steps()[-1].command.kind == "process_outcome"


def test_registered_operations_review_uses_the_host_control_surface(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id="start-verification-for-review",
            action_name="request_post_maintenance_verification",
            binding=observe_world_actor(session).binding,
            arguments={
                "pump_id": "pump-a",
                "backlog_item_id": "backlog-a-verification-001",
                "reason": "Start the independent Pump A verification.",
            },
        ),
    )
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id="complete-verification-for-review",
            action_name="continue_operation",
            binding=observe_world_actor(session).binding,
            arguments={
                "reason": "Continue to the verification result.",
            },
        ),
    )
    request = _bound_root_control_request(
        run,
        PumpStationOperationsBoundaryReviewRequest(
            version=PUMP_STATION_OPERATIONS_REVIEW_VERSION,
            review_id="release-verified-pump-a",
            review_kind="post_verification_restriction",
            pump_id="pump-a",
            restriction_or_isolation_permit_id="restriction-a-run-in-001",
            accepted_evidence_id="evidence-pump-a-verification-pass-001",
            requested_outcome="release",
            base_state_id=run.state.state_id,
            operations_authority_id="operations-controller",
            reason="Release the matched restriction after accepted verification.",
        ),
    )
    control = PumpStationWorldControl(
        root,
        authorised_principal_ids=("operations-controller",),
    )

    result = control.execute(request)

    assert result.receipt.operation == "operations_review"
    assert result.receipt.state_changed
    assert result.transition_receipt["action_or_control_kind"] == ("operations_boundary_review")
    assert run.repository.v4_steps()[-1].command.kind == "operations_review"


def test_registered_session_and_control_report_the_selected_v4_verification(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        _condition_check_request(
            session,
            request_id="verification-condition-check",
        ),
    )
    control = PumpStationWorldControl(
        root,
        authorised_principal_ids=("operations-controller",),
    )
    control.execute(
        _common_boundary_request(
            run,
            request_id="verification-power-unavailable",
        )
    )
    expected = run.verify_v4()

    session_report = session.verify()
    control_result = control.execute(
        WorldControlRequest(
            request_id="verify-registered-run",
            operation="verify",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            authority_id="operations-controller",
        )
    )

    assert session_report.valid == expected.valid
    assert session_report.issues == expected.issues
    assert session_report.replayed_transition_ids == expected.replayed_transition_ids
    assert session_report.final_state_id == expected.final_state_id
    assert control_result.verification is not None
    assert control_result.verification.valid == expected.valid
    assert control_result.verification.issues == expected.issues
    assert control_result.verification.replayed_transition_ids == (expected.replayed_transition_ids)
    assert control_result.verification.final_state_id == expected.final_state_id


def test_registered_verifier_replays_dynamic_session_information_and_binding(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id="verification-search",
            action_name="search_evidence",
            binding=observe_world_actor(session).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    invoke_world_actor(
        session,
        _condition_check_request(
            session,
            request_id="verification-dynamic-condition-check",
        ),
    )

    step = run.repository.v4_steps()[0]
    report = run.verify_v4()

    assert step.command.session_binding_id is not None
    assert report.valid
    assert report.issues == ()


def test_registered_verifier_rejects_a_superseded_binding_at_the_actor_parent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    superseded = run.repository.load_selected_session_activation()
    active = replace(
        superseded,
        active_activation_id="superseding-session-activation",
        prior_binding_id=superseded.binding_id,
        session_event_sequence=superseded.session_event_sequence + 1,
    )
    run.repository.publish_session_activation(active)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        _condition_check_request(
            session,
            request_id="verification-superseded-binding-condition-check",
        ),
    )
    step = run.repository.v4_steps()[0]
    tampered_step = replace(
        step,
        command=replace(
            step.command,
            session_binding_id=superseded.binding_id,
        ),
    )
    monkeypatch.setattr(run.repository, "v4_steps", lambda: (tampered_step,))

    report = run.verify_v4()

    assert not report.valid
    assert any("binding-not-active-at-parent" in issue for issue in report.issues)


def test_registered_run_rejects_actor_identity_without_a_host_session(
    tmp_path: Path,
) -> None:
    run = _create_registered_run(tmp_path / "run")

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.observe_v4_actor(
            session_id="caller-selected-session",
            agent_tenure_id="caller-selected-tenure",
        )

    assert raised.value.code == "session-activation-missing"


def test_registered_verifier_reports_missing_temporal_session_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        _condition_check_request(
            session,
            request_id="missing-session-evidence-condition-check",
        ),
    )
    command = run.repository.v4_steps()[0].command
    assert command.session_binding_id is not None
    binding = run.repository.load_session_activation(command.session_binding_id)
    (
        root
        / "temporal-evidence"
        / "private"
        / "session-information-sets-v2"
        / f"{binding.information_set_manifest_content_id}.json"
    ).unlink()

    report = run.verify_v4()

    assert not report.valid
    assert any(issue.startswith("session-evidence-invalid:") for issue in report.issues)


def test_registered_verifier_checks_session_context_without_a_world_transition(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id="non-transition-session-search",
            action_name="search_evidence",
            binding=observe_world_actor(session).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    assert run.verify_v4().valid
    binding = run.repository.load_selected_session_activation()
    (
        root
        / "temporal-evidence"
        / "private"
        / "session-information-sets-v2"
        / f"{binding.information_set_manifest_content_id}.json"
    ).unlink()

    report = run.verify_v4()

    assert not report.valid
    assert any(issue.startswith("session-evidence-invalid:") for issue in report.issues)


def test_registered_verifier_checks_superseded_non_transition_session_context(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run = _create_registered_run(root)
    session = _resume_registered_session(root, run)
    superseded = run.repository.load_selected_session_activation()
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id="supersede-session-context-with-search",
            action_name="search_evidence",
            binding=observe_world_actor(session).binding,
            arguments={
                "query": "controlled test permit",
                "scope": "operations",
                "limit": 1,
            },
        ),
    )
    assert run.repository.load_selected_session_activation() != superseded
    assert run.verify_v4().valid
    (
        root
        / "temporal-evidence"
        / "private"
        / "session-information-sets-v2"
        / f"{superseded.information_set_manifest_content_id}.json"
    ).unlink()

    report = run.verify_v4()

    assert not report.valid
    assert any(issue.startswith("session-evidence-invalid:") for issue in report.issues)
