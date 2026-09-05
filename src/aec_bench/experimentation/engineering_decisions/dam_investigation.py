# ABOUTME: Measures costed dam decisions through the existing actor episode host.
# ABOUTME: Separates outcome, evidence, timeliness, rejection, and private cost-bound diagnostics.

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aec_bench import worlds
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.experimentation.engineering_decisions.definitions import DamExperiment
from aec_bench.experimentation.engineering_decisions.policies import dam_policy
from aec_bench.experimentation.engineering_decisions.records import publish_record, world_record, write_plan
from aec_bench.harness.world_trials import run_world_experiment
from aec_bench.trials import PlannedTrial, plan_trials
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.monitoring.dam_seepage.investigation import minimum_successful_investigation_cost
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageAction,
    SeepageObservation,
    SeepageScenario,
    evaluate,
    initial_state,
    observe,
)
from aec_bench.worlds.tasks import WorldTask


def run_dam_investigation(
    scenario: SeepageScenario,
    policy: Callable[[SeepageObservation], SeepageAction],
    *,
    max_actions: int = 16,
) -> dict[str, Any]:
    """Run one public-observation policy with bounded calls and real actor request validation."""
    if max_actions < 1:
        raise ValueError("max_actions must be positive")
    profile = DamSeepageProfile(scenario, initial_state(scenario))
    host = DamSeepageEpisodeHost(profile=profile, actor_id="deterministic-control")
    actions: list[str] = []
    rejections: list[str] = []
    for index in range(max_actions):
        if host.state.response is not None:
            break
        action = policy(observe(host.state))
        result = host.invoke(
            WorldActorActionRequest(
                request_id=f"investigation-{index}",
                decision_id=host.observe().decision_id,
                action_name=action.value,
                arguments={},
            )
        )
        actions.append(action.value)
        if result.status != "applied":
            rejections.append(result.status)
    evaluation = evaluate(host.state)
    from aec_bench.worlds.monitoring.dam_seepage.replay import dam_replay_valid

    return {
        "replay_valid": dam_replay_valid(profile=profile, host=host, evaluation=evaluation),
        "accepted_actions": [step.action.value for step in host.recorder.steps],
        "status": host.status.value,
        "profile_id": scenario.profile_id,
        "actions": actions,
        "rejections": rejections,
        "evaluation": asdict(evaluation),
        "elapsed_minutes": host.state.elapsed_minutes,
        "perfect_information_minimum_cost": minimum_successful_investigation_cost(scenario),
        "action_limit_reached": host.state.response is None and len(actions) == max_actions,
    }


def run_dam_experiment(output: Path, definition: DamExperiment | None = None) -> list[TrialRecord]:
    definition = definition or DamExperiment()
    tasks = [
        worlds.task(
            DAM_SEEPAGE_TASK_WORLD_ID,
            profile=profile,
            instruction="Investigate the released evidence and submit a supported response within the declared limits.",
        )
        for profile in definition.profiles
    ]
    agents = [
        AgentConfig(
            name=name,
            adapter="deterministic",
            model=name,
            parameters={"policy": name, "max_actions": definition.max_actions},
        )
        for name in definition.policies
    ]
    trials = plan_trials(
        experiment_id=definition.experiment_id, tasks=tasks, agents=agents, compute=ComputeConfig(backend="local")
    )
    write_plan(output, definition, trials)

    async def execute(task: WorldTask, trial: PlannedTrial) -> TrialRecord:
        loaded = worlds.load_profile(task).value
        if not isinstance(loaded, DamSeepageProfile):
            raise TypeError("dam experiment requires a dam profile")
        started = datetime.now(UTC)
        report = run_dam_investigation(
            loaded.scenario, dam_policy(trial.agent.name), max_actions=definition.max_actions
        )
        evaluation = EvaluationResult(
            reward=float(report["evaluation"]["successful"] and report["replay_valid"]),
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=report["replay_valid"],
                errors=[] if report["replay_valid"] else ["dam replay failed"],
            ),
            breakdown=report["evaluation"],
        )
        path = output / trial.trial_id / "world-evidence.json"
        record = world_record(
            task=task,
            trial=trial,
            evaluation=evaluation,
            evidence=report,
            evidence_file=path,
            started_at=started,
            completed_at=datetime.now(UTC),
            terminated=not report["action_limit_reached"],
        )
        diagnostic_path = path.with_name("diagnostics.json")
        diagnostic_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        record.attach_artifact("experiment_diagnostics", diagnostic_path, media_type="application/json")
        return record

    records = asyncio.run(run_world_experiment(tasks=tasks, trials=trials, run_trial=execute))
    return [publish_record(output, record) for record in records]
