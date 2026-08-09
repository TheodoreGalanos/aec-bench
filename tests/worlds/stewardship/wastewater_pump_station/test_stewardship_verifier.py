# ABOUTME: Integration-tests independent replay of current registered pump transitions.
# ABOUTME: Proves an altered current receipt fails verification without mutating stored state.

from __future__ import annotations

import copy
from pathlib import Path

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.stewardship_verifier import (
    PumpStationCoupledRunStep,
    PumpStationCoupledVerificationReport,
    verify_coupled_stewardship_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _record_step(root: Path) -> PumpStationWorldRun:
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="verifier-run",
        episode_id="verifier-episode",
        world_branch_id="verifier-branch",
    )
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="verifier-action",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Create current replay evidence."},
        )
    )
    return run


def _verify_steps(
    run: PumpStationWorldRun,
    steps: tuple[PumpStationCoupledRunStep, ...],
) -> PumpStationCoupledVerificationReport:
    manifest = run.manifest
    snapshot = run.snapshot()
    initial = run.repository.load_state(manifest.initial_state_id)
    return verify_coupled_stewardship_run(
        run.model,
        run.event_schedule,
        initial,
        steps,
        expected_final_state_id=snapshot.state_id,
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


def test_current_verifier_replays_without_mutating_the_run(tmp_path: Path) -> None:
    run = _record_step(tmp_path / "run")
    before = run.snapshot()

    report = _verify_steps(run, run.repository.command_steps())

    assert report.valid
    assert report.final_state_id == before.state_id
    assert run.snapshot() == before


def test_current_verifier_rejects_an_altered_receipt(tmp_path: Path) -> None:
    run = _record_step(tmp_path / "run")
    step = run.repository.command_steps()[0]
    altered = copy.deepcopy(step)
    object.__setattr__(altered.transition.receipt, "after_state_id", "altered-state")

    report = _verify_steps(run, (altered,))

    assert not report.valid
    assert any("transition-replay-mismatch" in issue for issue in report.issues)
