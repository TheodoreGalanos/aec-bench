# ABOUTME: Runs and evaluates one complete dam seepage Interactive World trial.
# ABOUTME: Keeps dam state, replay, verification, and evaluation meaning task-owned.

from __future__ import annotations

import json
import tempfile
from dataclasses import asdict
from pathlib import Path

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.world_trials import (
    WorldActorSessionRunner,
    build_prime_world_trial_record,
)
from aec_bench.trials import PlannedTrial
from aec_bench.worlds import load_profile
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageEvaluation,
    evaluate,
    transition,
)
from aec_bench.worlds.runtime.episode import EpisodeStatus
from aec_bench.worlds.runtime.world_logic import ActionRejected
from aec_bench.worlds.tasks import WorldTask

DAM_SEEPAGE_EVIDENCE_PROTOCOL = "aec-bench/dam-seepage-trial/1"

_READ_ONLY_CONTEXT_POLICY_SENTENCE = (
    "The following notes may contain lessons retained from prior complete monitoring episodes. "
    "They are not current scenario evidence, do not override released readings or instrument "
    "checks, and cannot be changed during this episode."
)


async def run_dam_seepage_trial(
    task: WorldTask,
    trial: PlannedTrial,
    *,
    actor: WorldActorSessionRunner,
    read_only_context_text: str | None = None,
) -> TrialRecord:
    """Run one bounded dam episode and return its normal TrialRecord.

    ``read_only_context_text``, when supplied, is composed into the instruction text delivered to
    the actor after a fixed policy sentence. ``task.instruction`` itself is never mutated, and
    nothing about the composed text reaches ``evaluate()``, ``_replay_valid()``, or the world
    evidence file.
    """

    if task.world.task_world_id != DAM_SEEPAGE_TASK_WORLD_ID:
        raise ValueError("dam seepage trial requires the registered dam world")
    if trial.task_id != task.task_id:
        raise ValueError("dam seepage trial plan does not match the task")
    loaded = load_profile(task)
    if not isinstance(loaded.value, DamSeepageProfile):
        raise TypeError("dam seepage task loaded another profile value")
    retained_root = Path(tempfile.mkdtemp(prefix=f"aec-bench-{trial.trial_id}-"))
    host = DamSeepageEpisodeHost(profile=loaded.value)
    composed_instruction = (
        task.instruction
        if read_only_context_text is None
        else f"{task.instruction}\n\n{_READ_ONLY_CONTEXT_POLICY_SENTENCE}\n\n{read_only_context_text}"
    )
    session = await actor(
        host=host,
        trial=trial,
        instruction=composed_instruction,
        actor_workspace=retained_root / "actor",
        evidence_directory=retained_root / "provider",
        private_paths=(retained_root / "world",),
    )
    task_evaluation = evaluate(host.state)
    replay_valid = _replay_valid(profile=loaded.value, host=host, evaluation=task_evaluation)
    evaluation = EvaluationResult(
        reward=1.0 if task_evaluation.successful else 0.0,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=replay_valid,
            errors=[] if replay_valid else ["dam seepage replay differs from accepted actions"],
        ),
        breakdown=asdict(task_evaluation),
    )
    world_evidence = retained_root / "dam-world-evidence.json"
    world_evidence.write_text(
        json.dumps(
            {
                "world": asdict(task.world),
                "profile": asdict(task.profile),
                "actions": [step.action.value for step in host.recorder.steps],
                "status": host.status.value,
                "replay_valid": replay_valid,
                "evaluation": asdict(task_evaluation),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    terminated = host.status is EpisodeStatus.TERMINATED
    truncated = host.status is EpisodeStatus.TRUNCATED
    execution_completed = session.prime.benchmark_valid and session.close_complete and replay_valid
    return build_prime_world_trial_record(
        task=task,
        trial=trial,
        session=session,
        evaluation=evaluation,
        world_evidence_file=world_evidence,
        world_evidence_protocol=DAM_SEEPAGE_EVIDENCE_PROTOCOL,
        execution_completed=execution_completed,
        terminated=terminated,
        truncated=truncated,
        final_reason=host.status.value,
    )


def _replay_valid(
    *,
    profile: DamSeepageProfile,
    host: DamSeepageEpisodeHost,
    evaluation: SeepageEvaluation,
) -> bool:
    state = profile.opening_state
    for recorded in host.recorder.steps:
        result = transition(state, recorded.action)
        if isinstance(result, ActionRejected) or result.state != recorded.next_state:
            return False
        state = result.state
    return state == host.state and evaluate(state) == evaluation


__all__ = ("run_dam_seepage_trial",)
