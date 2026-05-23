# ABOUTME: Tests for harness trial lifecycle and planned-trial identifiers.
# ABOUTME: Verifies deterministic trial IDs and lifecycle transition validation.

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.harness.trial import PlannedTrial, TrialLifecycleState, transition_trial_state


def test_planned_trial_id_is_deterministic() -> None:
    planned = PlannedTrial(
        trial_id="experiment-001--mechanical-heat-load-alpha--agent-a--rep01",
        experiment_id="experiment-001",
        task_id="mechanical/heat-load/alpha",
        agent=AgentConfig(name="agent-a", adapter="tool_loop", model="gpt-5.4"),
        compute_backend="modal",
        repetition=1,
    )

    assert planned.trial_id == "experiment-001--mechanical-heat-load-alpha--agent-a--rep01"


def test_transition_trial_state_rejects_invalid_backward_transition() -> None:
    with pytest.raises(ValueError, match="invalid trial lifecycle transition"):
        transition_trial_state(TrialLifecycleState.COMPLETED, TrialLifecycleState.RUNNING)
