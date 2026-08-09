# ABOUTME: Schedules proposal DAG nodes with deterministic dispatch and commit semantics.
# ABOUTME: Realizes sequential or bounded ready-set policy without owning provider environments.

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Generic, TypeVar

from aec_bench.contracts.proposal_execution_profile import (
    ProposalSchedulingPolicy,
)

_T = TypeVar("_T")


class ProposalDagNodeState(StrEnum):
    """Host-observed state of one scheduled proposal node."""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class ProposalDagNodeExecution(Generic[_T]):
    """Executor-owned value and candidate-success classification for one node."""

    value: _T
    succeeded: bool


@dataclass(frozen=True)
class ProposalDagNodeOutcome(Generic[_T]):
    """Deterministically committed result or upstream-failure skip."""

    node_id: str
    state: ProposalDagNodeState
    value: _T | None
    causal_node_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProposalDagScheduleResult(Generic[_T]):
    """Complete scheduler trace in stable graph order."""

    outcomes: tuple[ProposalDagNodeOutcome[_T], ...]
    dispatch_order: tuple[str, ...]
    commit_order: tuple[str, ...]
    max_observed_parallelism: int

    def outcome(self, node_id: str) -> ProposalDagNodeOutcome[_T]:
        """Resolve one committed node outcome by ID."""

        for outcome in self.outcomes:
            if outcome.node_id == node_id:
                return outcome
        raise KeyError(node_id)


@dataclass
class _ProposalDagSchedulerState(Generic[_T]):
    """Mutable scheduling state kept behind one deterministic host loop."""

    node_order: tuple[str, ...]
    dependencies: Mapping[str, tuple[str, ...]]
    scheduling: ProposalSchedulingPolicy
    execute: Callable[[str], Awaitable[ProposalDagNodeExecution[_T]]]
    commit_outcome: Callable[[ProposalDagNodeOutcome[_T]], None]
    committed_by_node: dict[str, ProposalDagNodeOutcome[_T]] = field(
        default_factory=dict,
    )
    buffered_by_position: dict[int, ProposalDagNodeOutcome[_T]] = field(
        default_factory=dict,
    )
    running_by_position: dict[
        int,
        asyncio.Task[ProposalDagNodeExecution[_T]],
    ] = field(default_factory=dict)
    position_by_task: dict[
        asyncio.Task[ProposalDagNodeExecution[_T]],
        int,
    ] = field(default_factory=dict)
    dispatch_order: list[str] = field(default_factory=list)
    commit_order: list[str] = field(default_factory=list)
    next_dispatch_position: int = 0
    next_commit_position: int = 0
    max_observed_parallelism: int = 0

    def result(self) -> ProposalDagScheduleResult[_T]:
        return ProposalDagScheduleResult(
            outcomes=tuple(self.committed_by_node[node_id] for node_id in self.node_order),
            dispatch_order=tuple(self.dispatch_order),
            commit_order=tuple(self.commit_order),
            max_observed_parallelism=self.max_observed_parallelism,
        )


async def run_proposal_dag(
    *,
    node_order: tuple[str, ...],
    dependencies: Mapping[str, tuple[str, ...]],
    scheduling: ProposalSchedulingPolicy,
    execute: Callable[[str], Awaitable[ProposalDagNodeExecution[_T]]],
    commit: Callable[[ProposalDagNodeOutcome[_T]], None] | None = None,
) -> ProposalDagScheduleResult[_T]:
    """Execute a topologically ordered DAG under deterministic commit policy."""

    _validate_schedule_inputs(
        node_order=node_order,
        dependencies=dependencies,
    )
    state = _ProposalDagSchedulerState(
        node_order=node_order,
        dependencies=dependencies,
        scheduling=scheduling,
        execute=execute,
        commit_outcome=commit or (lambda _outcome: None),
    )
    try:
        await _drive_schedule(state)
    except BaseException:
        await _cancel_running(state)
        raise
    return state.result()


async def _drive_schedule(
    state: _ProposalDagSchedulerState[_T],
) -> None:
    while state.next_commit_position < len(state.node_order):
        _advance_until_blocked(state)
        if state.next_commit_position == len(state.node_order):
            return
        if not state.running_by_position:
            raise ValueError(
                "proposal DAG cannot make progress under its declared node order",
            )
        await _buffer_first_completed(state)


def _advance_until_blocked(
    state: _ProposalDagSchedulerState[_T],
) -> None:
    while True:
        dispatched = _dispatch_ready_nodes(state)
        committed = _commit_buffered_nodes(state)
        if not dispatched and not committed:
            return


def _dispatch_ready_nodes(
    state: _ProposalDagSchedulerState[_T],
) -> bool:
    made_progress = False
    while (
        state.next_dispatch_position < len(state.node_order)
        and len(state.running_by_position) < state.scheduling.max_parallelism
    ):
        position = state.next_dispatch_position
        node_id = state.node_order[position]
        node_dependencies = state.dependencies[node_id]
        if any(dependency not in state.committed_by_node for dependency in node_dependencies):
            break
        failed_dependencies = tuple(
            dependency
            for dependency in node_dependencies
            if state.committed_by_node[dependency].state is not ProposalDagNodeState.COMPLETED
        )
        if failed_dependencies:
            state.buffered_by_position[position] = ProposalDagNodeOutcome(
                node_id=node_id,
                state=ProposalDagNodeState.SKIPPED,
                value=None,
                causal_node_ids=failed_dependencies,
            )
        else:
            _dispatch_node(state, position=position, node_id=node_id)
        state.next_dispatch_position += 1
        made_progress = True
    return made_progress


def _dispatch_node(
    state: _ProposalDagSchedulerState[_T],
    *,
    position: int,
    node_id: str,
) -> None:
    task: asyncio.Task[ProposalDagNodeExecution[_T]] = asyncio.create_task(
        _await_execution(state.execute(node_id)),
        name=f"proposal-node:{node_id}",
    )
    state.running_by_position[position] = task
    state.position_by_task[task] = position
    state.dispatch_order.append(node_id)
    state.max_observed_parallelism = max(
        state.max_observed_parallelism,
        len(state.running_by_position),
    )


def _commit_buffered_nodes(
    state: _ProposalDagSchedulerState[_T],
) -> bool:
    made_progress = False
    while state.next_commit_position in state.buffered_by_position:
        outcome = state.buffered_by_position.pop(state.next_commit_position)
        state.commit_outcome(outcome)
        state.committed_by_node[outcome.node_id] = outcome
        state.commit_order.append(outcome.node_id)
        state.next_commit_position += 1
        made_progress = True
    return made_progress


async def _buffer_first_completed(
    state: _ProposalDagSchedulerState[_T],
) -> None:
    completed, _pending = await asyncio.wait(
        tuple(state.running_by_position.values()),
        return_when=asyncio.FIRST_COMPLETED,
    )
    for task in completed:
        position = state.position_by_task.pop(task)
        state.running_by_position.pop(position)
        execution = task.result()
        state.buffered_by_position[position] = ProposalDagNodeOutcome(
            node_id=state.node_order[position],
            state=(ProposalDagNodeState.COMPLETED if execution.succeeded else ProposalDagNodeState.FAILED),
            value=execution.value,
        )


async def _cancel_running(
    state: _ProposalDagSchedulerState[_T],
) -> None:
    for task in state.running_by_position.values():
        task.cancel()
    if state.running_by_position:
        await asyncio.gather(
            *state.running_by_position.values(),
            return_exceptions=True,
        )


async def _await_execution(
    execution: Awaitable[ProposalDagNodeExecution[_T]],
) -> ProposalDagNodeExecution[_T]:
    return await execution


def _validate_schedule_inputs(
    *,
    node_order: tuple[str, ...],
    dependencies: Mapping[str, tuple[str, ...]],
) -> None:
    if not node_order:
        raise ValueError("proposal DAG scheduling requires at least one node")
    if len(node_order) != len(set(node_order)):
        raise ValueError("proposal DAG node order must be unique")
    if set(dependencies) != set(node_order):
        raise ValueError(
            "proposal DAG dependencies must cover the exact scheduled node set",
        )
    positions = {node_id: position for position, node_id in enumerate(node_order)}
    for node_id in node_order:
        node_dependencies = dependencies[node_id]
        if len(node_dependencies) != len(set(node_dependencies)):
            raise ValueError(
                f"proposal DAG node {node_id!r} declares duplicate dependencies",
            )
        unknown = tuple(dependency for dependency in node_dependencies if dependency not in positions)
        if unknown:
            raise ValueError(
                f"proposal DAG node {node_id!r} depends on unknown nodes",
            )
        if any(positions[dependency] >= positions[node_id] for dependency in node_dependencies):
            raise ValueError(
                "proposal DAG node order must place every dependency first",
            )
