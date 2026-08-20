# ABOUTME: Tests for the adaptation coordinator that compiles family candidates.
# ABOUTME: Verifies metadata-driven task resolution and adaptation provenance on planned runs.

import pytest

from aec_bench.contracts.adaptation import AdaptationSpec, VariationAxis
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.harness.adaptation_run import (
    AdaptationCoordinationError,
    build_adaptation_trial_plan,
)
from tests.support.task_factories import make_task_definition


def test_build_adaptation_trial_plan_resolves_metadata_variants() -> None:
    tasks = [
        make_task_definition(
            task_id="mechanical/heat-load/au-office",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {
                    "jurisdiction": "au",
                    "building_type": "office",
                },
            },
        ),
        make_task_definition(
            task_id="mechanical/heat-load/au-school",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {
                    "jurisdiction": "au",
                    "building_type": "school",
                },
            },
        ),
        make_task_definition(
            task_id="mechanical/heat-load/us-office",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {
                    "jurisdiction": "us",
                    "building_type": "office",
                },
            },
        ),
        make_task_definition(
            task_id="mechanical/heat-load/us-school",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {
                    "jurisdiction": "us",
                    "building_type": "school",
                },
            },
        ),
    ]
    spec = AdaptationSpec(
        family_id="heat-load-family",
        seed_task_id="mechanical/heat-load/au-office",
        seed_variation={"jurisdiction": "au", "building_type": "office"},
        axes=[
            VariationAxis(axis="jurisdiction", values=["au", "us"]),
            VariationAxis(axis="building_type", values=["office", "school"]),
        ],
    )
    agents = [AgentConfig(name="tool-loop", adapter="tool_loop", model="gpt-5.4-mini")]

    plan = build_adaptation_trial_plan(
        experiment_id="experiment-001",
        spec=spec,
        tasks=tasks,
        agents=agents,
        compute=ComputeConfig(backend="modal"),
    )

    assert [item.task_id for item in plan] == [
        "mechanical/heat-load/au-school",
        "mechanical/heat-load/us-office",
        "mechanical/heat-load/us-school",
    ]
    assert plan[0].extensions["adaptation"].variation_key == "jurisdiction=au__building_type=school"
    assert plan[1].extensions["adaptation"].variation_key == "jurisdiction=us__building_type=office"
    assert plan[2].extensions["adaptation"].derivation_lineage[0].axis == "jurisdiction"
    assert plan[2].extensions["adaptation"].derivation_lineage[1].axis == "building_type"
    assert plan[0].compute.backend == "modal"


def test_build_adaptation_trial_plan_supports_repetitions() -> None:
    tasks = [
        make_task_definition(
            task_id="mechanical/heat-load/us-office",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {"jurisdiction": "us"},
            },
        )
    ]
    spec = AdaptationSpec(
        family_id="heat-load-family",
        seed_task_id="mechanical/heat-load/au-office",
        seed_variation={"jurisdiction": "au"},
        axes=[VariationAxis(axis="jurisdiction", values=["au", "us"])],
    )
    agents = [AgentConfig(name="tool-loop", adapter="tool_loop", model="gpt-5.4-mini")]

    plan = build_adaptation_trial_plan(
        experiment_id="experiment-001",
        spec=spec,
        tasks=tasks,
        agents=agents,
        compute=ComputeConfig(backend="modal"),
        repetitions=2,
    )

    assert [item.repetition for item in plan] == [1, 2]
    assert plan[0].trial_id.endswith("--rep01")
    assert plan[1].trial_id.endswith("--rep02")


def test_build_adaptation_trial_plan_rejects_missing_task_match() -> None:
    spec = AdaptationSpec(
        family_id="heat-load-family",
        seed_task_id="mechanical/heat-load/au-office",
        seed_variation={"jurisdiction": "au"},
        axes=[VariationAxis(axis="jurisdiction", values=["au", "us"])],
    )

    with pytest.raises(AdaptationCoordinationError, match="no task matches candidate"):
        build_adaptation_trial_plan(
            experiment_id="experiment-001",
            spec=spec,
            tasks=[],
            agents=[AgentConfig(name="tool-loop", adapter="tool_loop", model="gpt-5.4-mini")],
            compute=ComputeConfig(backend="modal"),
        )


def test_build_adaptation_trial_plan_rejects_ambiguous_task_match() -> None:
    tasks = [
        make_task_definition(
            task_id="mechanical/heat-load/us-office-a",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {"jurisdiction": "us"},
            },
        ),
        make_task_definition(
            task_id="mechanical/heat-load/us-office-b",
            metadata={
                "adaptation_family_id": "heat-load-family",
                "adaptation_variation": {"jurisdiction": "us"},
            },
        ),
    ]
    spec = AdaptationSpec(
        family_id="heat-load-family",
        seed_task_id="mechanical/heat-load/au-office",
        seed_variation={"jurisdiction": "au"},
        axes=[VariationAxis(axis="jurisdiction", values=["au", "us"])],
    )

    with pytest.raises(AdaptationCoordinationError, match="multiple tasks match candidate"):
        build_adaptation_trial_plan(
            experiment_id="experiment-001",
            spec=spec,
            tasks=tasks,
            agents=[AgentConfig(name="tool-loop", adapter="tool_loop", model="gpt-5.4-mini")],
            compute=ComputeConfig(backend="modal"),
        )
