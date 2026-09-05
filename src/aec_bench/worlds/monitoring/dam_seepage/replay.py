# ABOUTME: Checks dam episode steps against the task-owned transition and evaluation rules.
# ABOUTME: Shares the same replay check between provider trials and deterministic experiments.

from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
from aec_bench.worlds.monitoring.dam_seepage.episode_runtime import DamSeepageEpisodeHost
from aec_bench.worlds.monitoring.dam_seepage.world import SeepageEvaluation, evaluate, transition
from aec_bench.worlds.runtime.world_logic import ActionRejected


def dam_replay_valid(
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
