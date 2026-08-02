# ABOUTME: Compares registered V4 world-run transitions with the retained coupled behaviour oracle.
# ABOUTME: Runs the reference journey without treating a tenure handover as a world-state mutation.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_execution import (
    execute_asw_8_reference_controller,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    create_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationOperationsBoundaryReviewRequest,
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


def test_registered_run_matches_each_reference_journey_transition(
    tmp_path: Path,
) -> None:
    source = execute_asw_8_reference_controller(
        run_id="source-reference-journey",
        world_branch_id="source-reference-branch",
    ).run
    oracle = create_coupled_run(
        run_id="oracle-reference-journey",
        world_branch_id="oracle-reference-branch",
    )
    registered = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(tmp_path / "run"),
        run_id="registered-reference-journey",
        episode_id="registered-reference-episode",
        world_branch_id="registered-reference-branch",
    )
    compared_transition_ids: list[str] = []

    for command in source.commands:
        if command.kind == "handover":
            continue
        if command.kind == "actor":
            arguments = command.arguments
            backlog_item_id = arguments.get("backlog_item_id")
            if isinstance(backlog_item_id, str) and not any(
                item.item_id == backlog_item_id for item in oracle.state.backlog
            ):
                work_type = {
                    "request_functional_check": "minimum_functional_check",
                    "request_post_maintenance_verification": "post_maintenance_verification",
                    "request_inspection": "collateral_duty_inspection",
                }[command.action_name]
                candidates = tuple(
                    item.item_id
                    for item in oracle.state.backlog
                    if item.work_type == work_type
                    and item.target_id == arguments.get("pump_id")
                    and item.status.value in {"open", "planned"}
                )
                assert len(candidates) == 1
                arguments["backlog_item_id"] = candidates[0]
            oracle = oracle.apply_actor(
                request_id=command.request_id,
                action_name=command.action_name,
                arguments=arguments,
            )
            observation = registered.observe_v4_actor(
                session_id="registered-reference-session",
                agent_tenure_id="reference-controller",
            )
            transition = registered.apply_v4_actor_action(
                WorldActorActionRequest(
                    request_id=command.request_id,
                    action_name=command.action_name,
                    binding=observation.binding,
                    arguments=arguments,
                )
            )
        else:
            assert command.kind == "operations_review"
            arguments = {
                **command.arguments,
                "base_state_id": oracle.state.state_id,
            }
            review = PumpStationOperationsBoundaryReviewRequest(**arguments)
            oracle = oracle.apply_review(review)
            snapshot = registered.snapshot()
            transition = registered.apply_v4_control(
                PumpStationBoundControlRequest(
                    control_envelope_version=PUMP_STATION_BOUND_CONTROL_VERSION,
                    request_id=review.review_id,
                    run_id=snapshot.run_id,
                    episode_id=snapshot.episode_id,
                    world_branch_id=snapshot.world_branch_id,
                    base_state_id=snapshot.state_id,
                    base_commit_id=snapshot.commit_id,
                    based_on_sequence=snapshot.sequence,
                    control=review,
                )
            )
        assert transition.state == oracle.state
        assert transition.receipt == oracle.receipts[-1]
        compared_transition_ids.append(transition.receipt.transition_id)

    report = registered.verify_v4()

    assert len(compared_transition_ids) == len(source.commands) - 1
    assert registered.state == oracle.state
    assert report.valid
    assert report.replayed_transition_ids == tuple(compared_transition_ids)
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
    observation = run.observe_v4_actor(
        session_id="pending-view-session",
        agent_tenure_id="pending-view-tenure",
    )
    run.apply_v4_actor_action(
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
