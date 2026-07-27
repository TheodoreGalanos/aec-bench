# ABOUTME: Tests deterministic scheduling of proposal DAG nodes under execution-profile policy.
# ABOUTME: Covers readiness, concurrency bounds, ordered commits, failure cascades, and serial parity.

from __future__ import annotations

import asyncio

from aec_bench.contracts.proposal_execution_profile import (
    ProposalEnvironmentPolicy,
    ProposalSchedulingPolicy,
    ProposalSchedulingSemantics,
)
from aec_bench.harness.proposal_scheduler import (
    ProposalDagNodeExecution,
    ProposalDagNodeState,
    ProposalDagScheduleResult,
    run_proposal_dag,
)


def test_ready_set_runs_fanout_concurrently_and_waits_for_fanin() -> None:
    started: list[str] = []
    release_branches = asyncio.Event()

    async def execute(node_id: str) -> ProposalDagNodeExecution[str]:
        started.append(node_id)
        if node_id in {"assess-a", "assess-b"}:
            if {"assess-a", "assess-b"} <= set(started):
                release_branches.set()
            await release_branches.wait()
        if node_id == "finalize":
            assert {"assess-a", "assess-b"} <= set(committed)
        return ProposalDagNodeExecution(value=node_id, succeeded=True)

    committed: list[str] = []
    result = asyncio.run(
        run_proposal_dag(
            node_order=("analyse", "assess-a", "assess-b", "finalize"),
            dependencies={
                "analyse": (),
                "assess-a": ("analyse",),
                "assess-b": ("analyse",),
                "finalize": ("assess-a", "assess-b"),
            },
            scheduling=_ready_set_policy(max_parallelism=2),
            execute=execute,
            commit=lambda outcome: committed.append(outcome.node_id),
        )
    )

    assert result.dispatch_order == (
        "analyse",
        "assess-a",
        "assess-b",
        "finalize",
    )
    assert result.commit_order == result.dispatch_order
    assert result.max_observed_parallelism == 2
    assert committed == list(result.commit_order)


def test_ready_set_never_exceeds_profile_parallelism() -> None:
    active = 0
    observed = 0

    async def execute(node_id: str) -> ProposalDagNodeExecution[str]:
        nonlocal active, observed
        active += 1
        observed = max(observed, active)
        await asyncio.sleep(0.001)
        active -= 1
        return ProposalDagNodeExecution(value=node_id, succeeded=True)

    result = asyncio.run(
        run_proposal_dag(
            node_order=("a", "b", "c", "d", "e"),
            dependencies={node_id: () for node_id in ("a", "b", "c", "d", "e")},
            scheduling=_ready_set_policy(max_parallelism=2),
            execute=execute,
        )
    )

    assert observed == 2
    assert result.max_observed_parallelism == 2


def test_ready_set_buffers_completion_to_preserve_stable_commit_order() -> None:
    completion_order: list[str] = []
    commit_order: list[str] = []
    release_first = asyncio.Event()

    async def execute(node_id: str) -> ProposalDagNodeExecution[str]:
        if node_id == "a":
            await release_first.wait()
        else:
            release_first.set()
        completion_order.append(node_id)
        return ProposalDagNodeExecution(value=node_id, succeeded=True)

    result = asyncio.run(
        run_proposal_dag(
            node_order=("a", "b"),
            dependencies={"a": (), "b": ()},
            scheduling=_ready_set_policy(max_parallelism=2),
            execute=execute,
            commit=lambda outcome: commit_order.append(outcome.node_id),
        )
    )

    assert completion_order[:2] == ["b", "a"]
    assert result.dispatch_order == ("a", "b")
    assert result.commit_order == ("a", "b")
    assert commit_order == ["a", "b"]


def test_failure_skips_every_downstream_node_without_dispatching_it() -> None:
    executed: list[str] = []

    async def execute(node_id: str) -> ProposalDagNodeExecution[str]:
        executed.append(node_id)
        return ProposalDagNodeExecution(
            value=node_id,
            succeeded=node_id != "analyse",
        )

    result = asyncio.run(
        run_proposal_dag(
            node_order=("analyse", "assess", "finalize"),
            dependencies={
                "analyse": (),
                "assess": ("analyse",),
                "finalize": ("analyse", "assess"),
            },
            scheduling=_ready_set_policy(max_parallelism=2),
            execute=execute,
        )
    )

    assert executed == ["analyse"]
    assert result.dispatch_order == ("analyse",)
    assert result.commit_order == ("analyse", "assess", "finalize")
    assert _states(result) == {
        "analyse": ProposalDagNodeState.FAILED,
        "assess": ProposalDagNodeState.SKIPPED,
        "finalize": ProposalDagNodeState.SKIPPED,
    }
    assert result.outcome("assess").causal_node_ids == ("analyse",)
    assert result.outcome("finalize").causal_node_ids == (
        "analyse",
        "assess",
    )


def test_sequential_policy_matches_one_at_a_time_topological_execution() -> None:
    active = 0
    calls: list[str] = []

    async def execute(node_id: str) -> ProposalDagNodeExecution[str]:
        nonlocal active
        active += 1
        assert active == 1
        calls.append(node_id)
        await asyncio.sleep(0)
        active -= 1
        return ProposalDagNodeExecution(value=node_id, succeeded=True)

    result = asyncio.run(
        run_proposal_dag(
            node_order=("analyse", "assess", "finalize"),
            dependencies={
                "analyse": (),
                "assess": ("analyse",),
                "finalize": ("analyse", "assess"),
            },
            scheduling=_serial_policy(),
            execute=execute,
        )
    )

    assert calls == ["analyse", "assess", "finalize"]
    assert result.dispatch_order == tuple(calls)
    assert result.commit_order == tuple(calls)
    assert result.max_observed_parallelism == 1


def _states(
    result: ProposalDagScheduleResult[str],
) -> dict[str, ProposalDagNodeState]:
    return {outcome.node_id: outcome.state for outcome in result.outcomes}


def _ready_set_policy(
    *,
    max_parallelism: int,
) -> ProposalSchedulingPolicy:
    return ProposalSchedulingPolicy(
        semantics=ProposalSchedulingSemantics.READY_SET_DATAFLOW,
        max_parallelism=max_parallelism,
        environment_policy=ProposalEnvironmentPolicy.ISOLATED_ENVIRONMENT_POOL,
        deterministic_commit_order=True,
    )


def _serial_policy() -> ProposalSchedulingPolicy:
    return ProposalSchedulingPolicy(
        semantics=ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW,
        max_parallelism=1,
        environment_policy=ProposalEnvironmentPolicy.ROTATED_SINGLE_ENVIRONMENT,
        deterministic_commit_order=True,
    )
