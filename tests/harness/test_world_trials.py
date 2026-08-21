# ABOUTME: Tests complete Interactive World trials and ordered experiment mapping.
# ABOUTME: Proves normal TrialRecord evidence and retained artifacts without paid providers.

from __future__ import annotations

import json
import os
from functools import partial
from pathlib import Path

import pytest

from aec_bench import worlds
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.harness.dam_seepage_trial import run_dam_seepage_trial
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.harness.pump_station_trial import run_pump_station_trial
from aec_bench.harness.world_trials import run_world_experiment
from aec_bench.ledger.writer import materialize_trial_record
from aec_bench.trials import plan_trials
from aec_bench.worlds.monitoring.dam_seepage.world import (
    DAM_SEEPAGE_TASK_WORLD_ID,
    SeepageAction,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import PUMP_STATION_TASK_WORLD_ID


@pytest.mark.asyncio
async def test_dam_trial_returns_materializable_world_record(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    task = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam and respond as conditions evolve.",
    )
    actions = [
        {"action_name": SeepageAction.CHECK_MEASUREMENT_SYSTEM.value, "arguments": {}, "request_id": "check"},
        {
            "action_name": SeepageAction.RECORD_CONFIRMATION_READING.value,
            "arguments": {},
            "request_id": "reading-2",
        },
        {
            "action_name": SeepageAction.RECORD_CONFIRMATION_READING.value,
            "arguments": {},
            "request_id": "reading-3",
        },
        {
            "action_name": SeepageAction.INSPECT_DOWNSTREAM_AREA.value,
            "arguments": {},
            "request_id": "inspect",
        },
        {
            "action_name": SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
            "arguments": {},
            "request_id": "submit",
        },
    ]
    agent = AgentConfig(
        name="prime",
        adapter="prime-agent",
        model="anthropic/test",
        parameters={
            "isolation": "development_same_user",
            "max_world_actions": 10,
            "max_model_calls": 10,
            "max_tokens": 1_000,
            "max_cost_usd": "10",
            "max_wall_seconds": 5,
            "executable": str(_fake_prime_agent(tmp_path)),
            "environment": {
                **os.environ,
                "FAKE_ACP_SCENARIO": "world",
                "FAKE_WORLD_ACTIONS": json.dumps(actions),
            },
        },
    )
    trials = plan_trials("dam-study", tasks=[task], agents=[agent])

    records = await run_world_experiment(
        tasks=[task],
        trials=trials,
        run_trial=partial(run_dam_seepage_trial, actor=run_prime_world_actor_session),
    )

    assert len(records) == 1
    record = records[0]
    assert record.input.task_kind == "world"
    assert record.evaluation is not None and record.evaluation.reward == 1.0
    assert record.authority_evidence
    assert record.pending_artifacts
    materialized = materialize_trial_record(artifact_root=tmp_path / "artifacts", record=record)
    assert materialized.provider_evidence is not None
    assert materialized.episode_artifact is not None
    assert materialized.outputs.artifacts


@pytest.mark.asyncio
async def test_world_experiment_rejects_plan_without_supplied_task() -> None:
    task = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam.",
    )
    other = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        task_id="another-task",
        instruction="Monitor another dam.",
    )
    trial = plan_trials(
        "missing-task",
        tasks=[other],
        agents=[AgentConfig(name="prime", adapter="prime-agent", model="test")],
    )[0]

    async def must_not_run(*args: object) -> object:
        raise AssertionError(args)

    with pytest.raises(ValueError, match="no supplied task"):
        await run_world_experiment(tasks=[task], trials=[trial], run_trial=must_not_run)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_pump_trial_returns_materializable_world_record(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    profile_id = worlds.profiles(PUMP_STATION_TASK_WORLD_ID)[0].id
    task = worlds.task(PUMP_STATION_TASK_WORLD_ID, profile=profile_id, instruction="Operate the pump station.")
    agent = AgentConfig(
        name="prime",
        adapter="prime-agent",
        model="anthropic/test",
        parameters={
            "isolation": "development_same_user",
            "max_sessions": 1,
            "max_host_controls": 1,
            "max_world_actions": 10,
            "max_model_calls": 10,
            "max_tokens": 1_000,
            "max_cost_usd": "10",
            "max_wall_seconds": 5,
            "executable": str(_fake_prime_agent(tmp_path)),
            "environment": {
                **os.environ,
                "FAKE_ACP_SCENARIO": "world",
                "FAKE_WORLD_ACTIONS": "[]",
            },
        },
    )
    trial = plan_trials("pump-study", tasks=[task], agents=[agent])[0]

    record = await run_pump_station_trial(
        task,
        trial,
        actor=run_prime_world_actor_session,
        scope="bounded_continuation",
    )

    assert record.input.task_kind == "world"
    assert record.evaluation is not None and record.evaluation.stewardship is not None
    assert record.authority_evidence[0].protocol == "aec-bench/actor-invocation-manifest/1"
    materialized = materialize_trial_record(artifact_root=tmp_path / "pump-artifacts", record=record)
    assert materialized.provider_evidence is not None
    assert materialized.episode_artifact is not None
