# ABOUTME: Verifies registered V4 reference transitions and task-semantic rejection paths.
# ABOUTME: Replays the canonical journey without treating a tenure handover as a world transition.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_controller import (
    run_pump_station_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationProposalError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_stewardship_control_v4,
    apply_stewardship_proposal_v4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    verify_stewardship_run_v4,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    bind_information_set,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationWorldRunError,
    PumpStationWorldRunManifestV2,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PumpStationWorldSession,
    PumpStationWorldSessionFactory,
)


def _open_registered_session(
    run: PumpStationWorldRun,
    *,
    session_id: str,
    agent_tenure_id: str,
) -> PumpStationWorldSession:
    manifest = run.manifest
    snapshot = run.snapshot()
    assert isinstance(manifest, PumpStationWorldRunManifestV2)
    return PumpStationWorldSessionFactory(run.repository.root).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=session_id,
            task_world_id=manifest.task_world_id,
            agent_tenure_id=agent_tenure_id,
            run_id=manifest.run_id,
            episode_id=manifest.episode_id,
            world_branch_id=manifest.world_branch_id,
            start_snapshot=StewardshipStateSnapshotRef(
                run_id=snapshot.run_id,
                episode_id=snapshot.episode_id,
                world_branch_id=snapshot.world_branch_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
            ),
        )
    )


def test_registered_reference_journey_replays_each_world_transition(
    tmp_path: Path,
) -> None:
    result = run_pump_station_reference_controller(
        repository_root=tmp_path / "run",
        run_id="registered-reference-journey",
        episode_id="registered-reference-episode",
        world_branch_id="registered-reference-branch",
    )
    steps = result.run.repository.v4_steps()
    report = result.run.verify_v4()

    assert len(steps) == 25
    assert result.run.state == steps[-1].transition.state
    assert report.valid
    assert report.replayed_transition_ids == tuple(step.transition.receipt.transition_id for step in steps)
    assert not (tmp_path / "run" / "HEAD").exists()
    assert not (tmp_path / "run" / "generations").exists()


def test_v4_task_semantics_reject_pending_actor_view_identity(
    tmp_path: Path,
) -> None:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "pending-view"),
        run_id="pending-view-run",
        episode_id="pending-view-episode",
        world_branch_id="pending-view-branch",
    )
    initial_state = run.state
    session = _open_registered_session(
        run,
        session_id="pending-view-session",
        agent_tenure_id="pending-view-tenure",
    )
    observation = session.observe_actor()
    session.invoke_actor_action(
        WorldActorActionRequest(
            request_id="pending-view-request",
            action_name="request_post_maintenance_verification",
            binding=observation.binding,
            arguments={
                "pump_id": "pump-a",
                "backlog_item_id": "backlog-a-verification-001",
                "reason": "Test the actor-view identity boundary.",
            },
        )
    )
    step = run.repository.v4_steps()[0]
    assert step.proposal is not None
    assert step.information_set is not None
    forged_view = replace(
        step.information_set.base_view,
        view_id="pending",
        episode_id="foreign-episode",
    )
    object.__setattr__(forged_view, "view_id", "pending")
    forged_information_set = bind_information_set(
        forged_view,
        replace(
            step.information_set.observation_history,
            view_ids=("pending",),
        ),
        step.information_set.current_context,
    )
    forged_proposal = replace(
        step.proposal,
        context=replace(
            step.proposal.context,
            base_view_id="pending",
            information_set_id=forged_information_set.information_set_id,
        ),
    )

    with pytest.raises(PumpStationProposalError) as raised:
        apply_stewardship_proposal_v4(
            run.model,
            initial_state,
            forged_proposal,
            information_set=forged_information_set,
        )

    assert raised.value.code == "proposal-binding"


def test_v4_root_control_rejects_extra_command_arguments(
    tmp_path: Path,
) -> None:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "extra-control"),
        run_id="extra-control-run",
        episode_id="extra-control-episode",
        world_branch_id="extra-control-branch",
    )
    initial_state = run.state
    snapshot = run.snapshot()
    control = PumpStationCommonBoundaryRequest(
        version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
        request_id="extra-control-request",
        authority_id="operations-controller",
        boundary_kind="power",
        available=False,
        base_state_id=snapshot.state_id,
    )
    bound_control = PumpStationBoundControlRequest(
        control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
        request_id=control.request_id,
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        base_state_id=snapshot.state_id,
        base_commit_id=snapshot.commit_id,
        based_on_sequence=snapshot.sequence,
        control=control,
    )
    command = run._v4_control_command(bound_control)
    arguments = json.loads(command.arguments_json)
    arguments["ignored"] = "content"
    malformed_command = replace(
        command,
        arguments_json=json.dumps(
            arguments,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ),
    )
    transition = apply_stewardship_control_v4(initial_state, control)
    manifest = run.manifest
    assert isinstance(manifest, PumpStationWorldRunManifestV2)

    with pytest.raises(PumpStationWorldRunError) as raised:
        run.repository.stage_v4_transition(
            manifest=manifest,
            prior_snapshot=snapshot,
            command=malformed_command,
            transition=transition,
        )

    assert raised.value.code == "command-content"

    valid_transition = run.apply_v4_control(bound_control)
    step = run.repository.v4_steps()[0]
    report = verify_stewardship_run_v4(
        run.model,
        initial_state,
        (replace(step, command=malformed_command),),
        expected_final_state_id=valid_transition.state.state_id,
        expected_task_world_id=manifest.task_world_id,
        expected_run_id=manifest.run_id,
        expected_episode_id=manifest.episode_id,
        expected_world_branch_id=manifest.world_branch_id,
        expected_actor_id="pump-station-actor",
        expected_source_artifact_ids=(
            manifest.reference_system_content_id,
            manifest.package_content_id,
            manifest.temporal_bundle_content_id,
        ),
    )

    assert report.valid is False
    assert any("command-content" in issue for issue in report.issues)
