# ABOUTME: Tests the maintained L01 real-model pilot configuration without running a provider.
# ABOUTME: Keeps unsupported lifecycle token and timeout limits out of tool-loop trials.

from __future__ import annotations

from scripts.run_l01_pilot import _build_agent, _build_compute


def test_l01_pilot_uses_only_the_enforceable_lifecycle_turn_limit() -> None:
    agent = _build_agent()
    compute = _build_compute()

    assert agent.parameters == {"max_turns_per_session": 120}
    assert compute.resource_limits == {"n_concurrent_trials": 1}
    assert compute.timeout_override is None
