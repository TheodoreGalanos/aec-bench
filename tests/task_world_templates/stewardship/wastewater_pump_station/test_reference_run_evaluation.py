# ABOUTME: Proves current replay owns conservation and stewardship evaluation.
# ABOUTME: Checks actual opening identities, step-type integrity, and transport-neutral outcomes.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.evaluation.stewardship import evaluate_pump_station_reference_run, pump_station_semantic_outcome
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
    PumpStationPoolReservation,
    PumpStationPoolReservationStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationObligationStatus,
    PumpStationStewardshipState,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledRunStep,
    PumpStationCoupledVerificationReport,
    derive_pump_station_conservation_report,
    verify_coupled_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationRegisteredWorldRunManifest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

type ReferenceRun = PumpStationWorldRun


def _create_run(root: Path, suffix: str) -> ReferenceRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id=f"evaluation-run-{suffix}",
        episode_id=f"evaluation-episode-{suffix}",
        world_branch_id=f"evaluation-branch-{suffix}",
    )


def _verify_steps(
    run: ReferenceRun,
    opening_state: PumpStationStewardshipState,
    steps: tuple[PumpStationCoupledRunStep, ...] | None = None,
) -> PumpStationCoupledVerificationReport:
    manifest = run.manifest
    assert isinstance(manifest, PumpStationRegisteredWorldRunManifest)
    return verify_coupled_stewardship_run(
        run.model,
        opening_state,
        steps if steps is not None else run.repository.command_steps(),
        expected_final_state_id=run.state.state_id,
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


def test_conservation_uses_the_run_opening_state_and_detects_each_balance_mismatch(
    tmp_path: Path,
) -> None:
    run = _create_run(tmp_path / "conservation", "conservation")
    opening = run.state

    report = derive_pump_station_conservation_report(opening, opening)

    assert report.valid
    assert report.work.opening_ids == tuple(sorted(item.item_id for item in opening.backlog))
    assert report.liabilities.opening_ids == tuple(sorted(opening.active_liability_ids))

    duty_state = replace(
        opening,
        collateral_runtime=(("injected-interval", "pump-a", 1),),
    )
    resource_state = replace(
        opening,
        resource_reservations=(
            PumpStationPoolReservation(
                reservation_id="injected-reservation",
                pool_id=opening.resources.pools[0].pool_id,
                quantity=1,
                process_id="injected-process",
                target_id="pump-a",
                status=PumpStationPoolReservationStatus.ACTIVE,
                created_at_calendar_seconds=opening.calendar_seconds,
                released_at_calendar_seconds=None,
                retain_on_suspension=False,
                prior_reservation_id=None,
                disposition=None,
            ),
        ),
    )
    work_state = replace(
        opening,
        backlog=(
            *opening.backlog,
            replace(
                opening.backlog[0],
                item_id="injected-work",
                status=PumpStationBacklogStatus.CLOSED,
            ),
        ),
    )
    liability_state = replace(
        opening,
        obligations=(
            *opening.obligations,
            replace(
                opening.obligations[0],
                obligation_id="injected-liability",
                status=PumpStationObligationStatus.ACTIVE,
                created_sequence=0,
            ),
        ),
    )

    assert not derive_pump_station_conservation_report(opening, duty_state).duty.valid
    assert not derive_pump_station_conservation_report(opening, resource_state).resources.valid
    assert not derive_pump_station_conservation_report(opening, work_state).work.valid
    assert not derive_pump_station_conservation_report(opening, liability_state).liabilities.valid


def test_verification_reports_actor_actions_and_host_controls_separately(
    tmp_path: Path,
) -> None:
    root = tmp_path / "mixed-run"
    run = _create_run(root, "mixed")
    opening = run.state
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="evaluation-condition-check",
            decision_id=observation.decision_id,
            action_name="request_condition_check",
            arguments={
                "pump_id": "pump-a",
                "reason": "Record one current condition check.",
            },
        )
    )
    snapshot = run.snapshot()
    control = PumpStationCommonBoundaryRequest(
        request_id="evaluation-power-boundary",
        authority_id="operations-controller",
        boundary_kind="power",
        available=False,
        base_state_id=snapshot.state_id,
    )
    run.apply_control(
        PumpStationBoundControlRequest(
            request_id=control.request_id,
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            base_state_id=snapshot.state_id,
            base_commit_id=snapshot.commit_id,
            based_on_sequence=snapshot.sequence,
            control=control,
        )
    )

    report = _verify_steps(run, opening)
    steps = run.repository.command_steps()
    altered_actor = replace(
        steps[0],
        transition=replace(
            steps[0].transition,
            receipt=replace(steps[0].transition.receipt, actor_action=False),
        ),
    )
    altered_control = replace(
        steps[1],
        transition=replace(
            steps[1].transition,
            receipt=replace(steps[1].transition.receipt, actor_action=True),
        ),
    )
    actor_report = _verify_steps(run, opening, (altered_actor, steps[1]))
    control_report = _verify_steps(run, opening, (steps[0], altered_control))

    assert report.actor_actions_valid
    assert report.host_controls_valid
    assert report.conservation.valid
    assert not actor_report.actor_actions_valid
    assert actor_report.host_controls_valid
    assert "actor-action-integrity" in actor_report.issues
    assert control_report.actor_actions_valid
    assert not control_report.host_controls_valid
    assert "host-control-integrity" in control_report.issues


def test_reference_evaluation_and_semantic_outcome_are_transport_neutral(
    tmp_path: Path,
) -> None:
    first = _create_run(tmp_path / "first", "first")
    second = _create_run(tmp_path / "second", "second")

    evaluation = evaluate_pump_station_reference_run(first)
    first_outcome = pump_station_semantic_outcome(first)
    second_outcome = pump_station_semantic_outcome(second)

    assert evaluation.evidence.initial_state_id == first.manifest.initial_state_id
    assert evaluation.evidence.terminal_state_id == first.state.state_id
    assert not evaluation.valid
    assert first_outcome == second_outcome
    assert first_outcome.evaluation.evaluation_valid == evaluation.valid
