# ABOUTME: Runs one bounded Bedrock agent check on a governed rollout child.
# ABOUTME: Persists model token use, replay verification, privacy, and lineage evidence.

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_rollout_model_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
    PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
    PumpStationPhysicalTreatmentClass,
    PumpStationPhysicalTreatmentRequest,
    PumpStationTreatmentSeverity,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_control import (
    PumpStationRolloutControl,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PumpStationRolloutChildRequest,
    PumpStationRolloutGroupRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    arguments = parser.parse_args()
    output = arguments.output_dir
    output.mkdir(parents=True, exist_ok=False)
    parent_root = output / "parent-world"
    parent = PumpStationWorldSessionFactory(parent_root, evidence_health=True).open(
        WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.START,
            session_id="session.asw7.agent.parent",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="tenure.asw7.agent.parent",
            run_id="run.asw7.agent.parent",
            episode_id="episode.asw7.agent",
            world_branch_id="branch.asw7.agent.parent",
        )
    )
    parent_snapshot = parent.run.snapshot()
    group_request = PumpStationRolloutGroupRequest(
        request_id="rollout.asw7.agent-check",
        group_id="group.asw7.agent-check",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="asw7-agent-check-host",
        parent_snapshot=parent_snapshot,
        origin_verification_id="verified-current-world-state",
        information_boundary_id="pump-station-actor-view.v3",
        event_schedule_id="agent-check-fixed-future.v1",
        fixed_future_condition_id="agent-check-future.v1",
        future_condition_seed=83,
        split_group_id="split.asw7.agent-check",
        children=(
            PumpStationRolloutChildRequest(
                child_id="control",
                run_id="run.asw7.agent.control",
                world_branch_id="branch.asw7.agent.control",
                agent_condition_id="bedrock-control",
                agent_seed=83,
            ),
            PumpStationRolloutChildRequest(
                child_id="treated",
                run_id="run.asw7.agent.treated",
                world_branch_id="branch.asw7.agent.treated",
                agent_condition_id="bedrock-treated",
                agent_seed=89,
            ),
        ),
    )
    control = PumpStationRolloutControl(
        parent_repository_root=parent_root,
        rollout_repository_root=output / "rollouts",
        authorised_principal_ids=("asw7-agent-check-host",),
        evidence_health=True,
    )
    lineage = control.create_group(group_request)
    treated = control.open_actor_session(
        group_id=group_request.group_id,
        child_id="treated",
        session_id="session.asw7.agent.treatment",
        agent_tenure_id="tenure.asw7.agent.treatment",
    )
    child_snapshot = treated.run.snapshot()
    treatment = PumpStationPhysicalTreatmentRequest(
        request_id="treatment.asw7.agent.maintenance-induced",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        authority_id="asw7-agent-check-host",
        group_id=group_request.group_id,
        child_id="treated",
        child_run_id=child_snapshot.run_id,
        child_episode_id=child_snapshot.episode_id,
        child_world_branch_id=child_snapshot.world_branch_id,
        base_state_id=child_snapshot.state_id,
        base_commit_id=child_snapshot.commit_id,
        based_on_sequence=child_snapshot.sequence,
        parent_state_id=parent_snapshot.state_id,
        treatment_class=PumpStationPhysicalTreatmentClass.MAINTENANCE_INDUCED_CLEARANCE_LOSS,
        treatment_version=PUMP_STATION_PHYSICAL_TREATMENT_VERSION,
        affected_pump_ids=("pump-a",),
        activation_calendar_seconds=treated.run.state.physical.calendar_seconds,
        severity=PumpStationTreatmentSeverity.MODERATE,
        random_stream_id="stream.asw7.agent-check",
        random_seed=83,
        visibility_policy=PUMP_STATION_PHYSICAL_TREATMENT_VISIBILITY,
        decision_right_id=PUMP_STATION_PHYSICAL_TREATMENT_DECISION_RIGHT,
    )
    control.schedule_treatment(treatment)
    activation = control.recover_treatment(
        group_id=group_request.group_id,
        child_id="treated",
        treatment_request_id=treatment.request_id,
    )
    completed = run_pump_station_rollout_model_session(
        control=control,
        group_id=group_request.group_id,
        child_id="treated",
        output_dir=output / "agent-evidence",
        session_identity="asw7.agent-check",
        model=arguments.model,
        max_turns=4,
        forbidden_private_tokens=(
            group_request.group_id,
            group_request.split_group_id,
            treatment.request_id,
            treatment.treatment_class.value,
            treatment.random_stream_id,
        ),
    )
    summary = {
        "model": arguments.model,
        "adapter_status": completed.adapter_result.agent_output.status.value,
        "turns_used": completed.adapter_result.turns_used,
        "input_tokens": completed.adapter_result.usage_input_tokens or 0,
        "output_tokens": completed.adapter_result.usage_output_tokens or 0,
        "cache_read_tokens": completed.adapter_result.usage_cache_read_tokens or 0,
        "cache_write_tokens": completed.adapter_result.usage_cache_write_tokens or 0,
        "verification_valid": completed.verification.valid,
        "parent_unchanged": control.parent_snapshot() == parent_snapshot,
        "lineage": asdict(lineage),
        "activation": asdict(activation),
    }
    (output / "agent-check-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
