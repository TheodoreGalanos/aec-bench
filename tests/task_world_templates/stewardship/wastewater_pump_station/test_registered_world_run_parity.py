# ABOUTME: Proves current registered transitions reject forged actor and control content.
# ABOUTME: Keeps task-semantic validation on the episode and root-control paths.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_models import (
    PUMP_STATION_BOUND_CONTROL_VERSION,
    PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
    PumpStationBoundControlRequest,
    PumpStationCommonBoundaryRequest,
    PumpStationProposalError,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_state_machine import (
    apply_coupled_stewardship_proposal,
    apply_stewardship_control,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    bind_information_set,
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


def _start(root: Path) -> PumpStationWorldRun:
    return PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(root),
        run_id="semantic-run",
        episode_id="semantic-episode",
        world_branch_id="semantic-branch",
    )


def test_actor_semantics_reject_a_forged_view_identity(tmp_path: Path) -> None:
    root = tmp_path / "run"
    run = _start(root)
    opening = run.state
    host = PumpStationEpisodeHost(root)
    observation = host.observe()
    host.invoke(
        WorldActorActionRequest(
            request_id="actor-request",
            decision_id=observation.decision_id,
            action_name="continue_operation",
            arguments={"reason": "Create one bound actor proposal."},
        )
    )
    step = run.repository.command_steps()[0]
    assert step.proposal is not None
    assert step.information_set is not None
    forged_view = replace(step.information_set.base_view)
    object.__setattr__(forged_view, "view_id", "forged")
    object.__setattr__(forged_view, "view_id", "forged")
    forged_set = bind_information_set(
        forged_view,
        replace(step.information_set.observation_history, view_ids=("forged",)),
        step.information_set.current_context,
    )
    forged_proposal = replace(
        step.proposal,
        context=replace(
            step.proposal.context,
            base_view_id="forged",
            information_set_id=forged_set.information_set_id,
        ),
    )

    with pytest.raises(PumpStationProposalError, match="proposal-binding"):
        apply_coupled_stewardship_proposal(
            run.model,
            opening,
            forged_proposal,
            information_set=forged_set,
        )


def test_root_control_rejects_extra_persisted_command_arguments(tmp_path: Path) -> None:
    run = _start(tmp_path / "run")
    opening = run.state
    snapshot = run.snapshot()
    control = PumpStationCommonBoundaryRequest(
        version=PUMP_STATION_COMMON_BOUNDARY_CONTROL_VERSION,
        request_id="control-request",
        authority_id="operations-controller",
        boundary_kind="power",
        available=False,
        base_state_id=snapshot.state_id,
    )
    bound = PumpStationBoundControlRequest(
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
    command = run._control_command(bound)
    arguments = json.loads(command.arguments_json)
    arguments["ignored"] = "content"
    malformed = replace(
        command,
        arguments_json=json.dumps(arguments, ensure_ascii=False, separators=(",", ":"), sort_keys=True),
    )

    with pytest.raises(PumpStationWorldRunError, match="command-content"):
        run.repository.stage_command_transition(
            manifest=run.manifest,
            prior_snapshot=snapshot,
            command=malformed,
            transition=apply_stewardship_control(opening, control),
        )
