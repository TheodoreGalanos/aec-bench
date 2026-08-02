# ABOUTME: Proves full V4 structured handovers survive durable publication and recovery.
# ABOUTME: Checks bounded actor-only history, exact session scope, and fail-closed reload.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from world_run_support import create_world_run

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.world_interface import invoke_world_actor, observe_world_actor
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    PumpStationCoupledActorView,
    PumpStationStructuredHandoverV4,
    actor_history_entry_v4,
    create_structured_handover_v4,
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
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session_activation import (
    PumpStationSessionActivationBinding,
)


def _snapshot_ref(run: PumpStationWorldRun) -> StewardshipStateSnapshotRef:
    snapshot = run.snapshot()
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _resume_session(
    root: Path,
    run: PumpStationWorldRun,
    *,
    session_id: str,
    agent_tenure_id: str,
) -> PumpStationWorldSession:
    return PumpStationWorldSessionFactory(root).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=session_id,
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id=agent_tenure_id,
            run_id=run.manifest.run_id,
            episode_id=run.manifest.episode_id,
            world_branch_id=run.manifest.world_branch_id,
            start_snapshot=_snapshot_ref(run),
        )
    )


def _invoke_condition_check(
    session: PumpStationWorldSession,
    *,
    request_id: str,
    pump_id: str,
) -> None:
    invoke_world_actor(
        session,
        WorldActorActionRequest(
            request_id=request_id,
            action_name="request_condition_check",
            binding=observe_world_actor(session).binding,
            arguments={
                "pump_id": pump_id,
                "reason": f"Record the visible condition of {pump_id}.",
            },
        ),
    )


def _apply_common_boundary_control(run: PumpStationWorldRun) -> str:
    snapshot = run.snapshot()
    request_id = "withdraw-common-power-boundary"
    run.apply_v4_control(
        PumpStationBoundControlRequest(
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
    )
    return request_id


def _handover_context(
    root: Path,
) -> tuple[
    PumpStationWorldRun,
    PumpStationStructuredHandoverV4,
    PumpStationSessionActivationBinding,
    PumpStationSessionActivationBinding,
    str,
]:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="structured-handover-run",
        episode_id="structured-handover-episode",
        world_branch_id="structured-handover-branch",
    )
    source = _resume_session(
        root,
        run,
        session_id="source-session",
        agent_tenure_id="source-tenure",
    )
    _invoke_condition_check(
        source,
        request_id="condition-check-pump-a",
        pump_id="pump-a",
    )
    _invoke_condition_check(
        source,
        request_id="condition-check-pump-b",
        pump_id="pump-b",
    )
    control_request_id = _apply_common_boundary_control(run)
    observe_world_actor(source)
    source_binding = run.repository.load_active_session_activation()

    recipient = _resume_session(
        root,
        run,
        session_id="recipient-session",
        agent_tenure_id="recipient-tenure",
    )
    recipient_binding = run.repository.load_active_session_activation()
    assert recipient_binding.prior_binding_id == source_binding.binding_id
    assert isinstance(recipient.actor_view, PumpStationCoupledActorView)
    history = tuple(
        actor_history_entry_v4(step.transition, step.proposal)
        for step in run.repository.v4_steps()
        if step.proposal is not None
    )
    handover = create_structured_handover_v4(
        recipient.actor_view,
        run_id=run.manifest.run_id,
        commit_id=run.snapshot().commit_id,
        from_session_id=source_binding.session_id,
        from_tenure_id=source_binding.agent_tenure_id,
        from_session_binding_id=source_binding.binding_id,
        to_session_id=recipient_binding.session_id,
        to_session_binding_id=recipient_binding.binding_id,
        history=history,
        maximum_history_entries=1,
    )
    return run, handover, source_binding, recipient_binding, control_request_id


def test_v4_handover_history_is_bounded_to_actor_visible_actions(
    tmp_path: Path,
) -> None:
    run, handover, _, _, control_request_id = _handover_context(tmp_path / "run")
    steps = run.repository.v4_steps()
    control_step = next(step for step in steps if step.command.kind != "actor")
    actor_proposal = next(step.proposal for step in steps if step.proposal is not None)
    assert actor_proposal is not None

    assert handover.maximum_history_entries == 1
    assert tuple(item.proposal_id for item in handover.history) == ("condition-check-pump-b",)
    assert control_request_id not in {item.proposal_id for item in handover.history}
    with pytest.raises(ValueError, match="actor transition"):
        actor_history_entry_v4(control_step.transition, actor_proposal)


def test_full_v4_handover_reopens_without_changing_the_world_snapshot(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run, handover, _, _, _ = _handover_context(root)
    selected = run.snapshot()

    published = run.repository.publish_structured_handover(handover)
    reopened = PumpStationWorldRunRepository(root)
    repeated = reopened.publish_structured_handover(handover)
    recovered = reopened.load_structured_handover(handover.handover_id)

    assert published == handover
    assert repeated == handover
    assert recovered == handover
    assert recovered.current_actor_view == handover.current_actor_view
    assert recovered.history == handover.history
    assert reopened.current_snapshot() == selected
    assert tuple((root / "session-authority" / "handovers").glob("*.json")) == (
        root / "session-authority" / "handovers" / f"{handover.handover_id}.json",
    )


def test_structured_handover_lookup_rejects_non_content_identifiers(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run, handover, _, _, _ = _handover_context(root)
    run.repository.publish_structured_handover(handover)

    assert (root / "manifest.json").is_file()
    assert run.repository.has_structured_handover(handover.handover_id)
    assert not run.repository.has_structured_handover("../../manifest")


@pytest.mark.parametrize(
    ("change", "expected_code"),
    (
        ({"run_id": "foreign-run"}, "structured-handover-scope"),
        ({"commit_id": "f" * 64}, "structured-handover-stale"),
        ({"to_session_binding_id": "e" * 64}, "structured-handover-session"),
    ),
)
def test_v4_handover_publication_rejects_foreign_stale_or_unselected_content(
    tmp_path: Path,
    change: dict[str, object],
    expected_code: str,
) -> None:
    run, handover, _, _, _ = _handover_context(tmp_path / "run")

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_structured_handover(replace(handover, **change))

    assert raised.value.code == expected_code


def test_v4_handover_publication_rejects_history_not_derived_from_actor_steps(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run, handover, _, _, _ = _handover_context(root)
    fabricated = replace(
        handover,
        history=(
            replace(
                handover.history[0],
                reason="Report a history that did not occur.",
            ),
        ),
    )

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.publish_structured_handover(fabricated)

    assert raised.value.code == "artifact-integrity"
    assert not (root / "session-authority" / "handovers" / f"{fabricated.handover_id}.json").exists()


def test_v4_handover_reload_fails_closed_for_changed_full_content(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    run, handover, _, _, _ = _handover_context(root)
    run.repository.publish_structured_handover(handover)
    handover_path = root / "session-authority" / "handovers" / f"{handover.handover_id}.json"
    handover_path.write_bytes(b"{}\n")

    with pytest.raises(PumpStationWorldRunError):
        PumpStationWorldRunRepository(root).load_structured_handover(
            handover.handover_id,
        )


def test_legacy_run_does_not_create_structured_handover_storage(
    tmp_path: Path,
) -> None:
    registered_root = tmp_path / "registered-run"
    _, handover, _, _, _ = _handover_context(registered_root)
    legacy = create_world_run(tmp_path / "legacy-run")

    with pytest.raises(PumpStationWorldRunError) as raised:
        legacy.repository.publish_structured_handover(handover)

    assert raised.value.code == "record-versions"
    assert not (legacy.repository.root / "session-authority" / "handovers").exists()
