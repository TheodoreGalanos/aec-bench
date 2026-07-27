# ABOUTME: Tests that fixed meta-harness APIs expose generic services rather than historical phases.
# ABOUTME: Allows pinned schema literals while preventing unused Stage 0 and G1 facade modules.

from __future__ import annotations

from importlib import import_module
from importlib.util import find_spec

import pytest


@pytest.mark.parametrize(
    "module_name",
    (
        "aec_bench.meta_harness.stage_zero",
        "aec_bench.meta_harness.stage_zero_cli",
        "aec_bench.meta_harness.adaptive_critic_stress",
        "aec_bench.meta_harness.critic_stress",
        "aec_bench.meta_harness.critic_stress_enforcement",
        "aec_bench.meta_harness.critic_stress_evidence",
        "aec_bench.meta_harness.critic_stress_selection",
    ),
)
def test_unused_historical_phase_facades_are_absent(module_name: str) -> None:
    assert find_spec(module_name) is None


def test_generic_factorial_and_critic_stress_owners_remain_importable() -> None:
    assert import_module("aec_bench.meta_harness.factorial_experiment")
    assert import_module("aec_bench.meta_harness.factorial_experiment_cli")
    assert import_module("aec_bench.meta_harness.critic_stress_runtime")
