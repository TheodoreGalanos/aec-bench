# ABOUTME: Tests ready-set proposal compilation and isolated-pool session execution.
# ABOUTME: Proves real receipt integration, fail-closed pool capacity, and ordered publication.

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import cast

import pytest

from aec_bench.contracts.proposal_execution import (
    ProposalCandidateFailureCode,
    ProposalCompilationRejection,
    ProposalExecutionSemantics,
    ProposalNodeReceiptStatus,
    ProposalNodeSkipCause,
    ProposalSessionStatus,
)
from aec_bench.contracts.proposal_execution_profile import (
    ProposalEnvironmentPolicy,
    ProposalExecutionProfile,
    ProposalSchedulingPolicy,
    ProposalSchedulingSemantics,
)
from aec_bench.harness.proposal_session import (
    ProposalSessionEnvironment,
    ProposalSessionRuntimeError,
    run_proposal_session,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
    compile_governed_proposal,
)
from tests.harness.test_proposal_session import (
    _execution_ref,
    _RecordedExecResult,
    _RecordingProposalEnvironment,
)
from tests.meta_harness.test_program_proposal_compilation import (
    _compile_arguments,
    _governed_graph_fixture,
)
from tests.meta_harness.test_proposal_freeze import _issue


def test_compiler_accepts_profile_bound_ready_set_semantics(
    tmp_path: Path,
) -> None:
    bundle, _source_task_root = _ready_set_bundle(tmp_path)

    assert bundle.execution_semantics is ProposalExecutionSemantics.READY_SET_DATAFLOW
    assert bundle.compilation.budget_plan.execution_semantics is ProposalExecutionSemantics.READY_SET_DATAFLOW
    assert bundle.compilation.lowered_program.limits.max_parallelism == 2


def test_ready_set_session_uses_isolated_pool_and_commits_canonical_receipts(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    pool = _RecordingProposalEnvironmentPool(
        root=tmp_path / "pool",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        capacity=2,
    )

    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=tmp_path / "session",
            environment_pool=pool,
        )
    )

    assert receipt.status is ProposalSessionStatus.COMPLETED
    assert receipt.trial_record_permitted is True
    assert tuple(node.node_id for node in receipt.node_receipts) == (
        "analyse",
        "assess-a",
        "assess-b",
        "finalize",
    )
    assert all(node.status is ProposalNodeReceiptStatus.COMPLETED for node in receipt.node_receipts)
    assert pool.max_observed_leases == 2
    assert pool.execution_completion_order == [
        "analyse",
        "assess-b",
        "assess-a",
        "finalize",
    ]
    assert pool.leased_node_ids == [
        "analyse",
        "assess-a",
        "assess-b",
        "finalize",
    ]


def test_ready_set_candidate_failure_skips_join_after_sibling_completes(
    tmp_path: Path,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    pool = _RecordingProposalEnvironmentPool(
        root=tmp_path / "pool",
        bundle=bundle,
        runtime_archive_sha256=execution.runtime_archive_sha256,
        capacity=2,
        failed_node_ids={"assess-a"},
    )

    receipt = asyncio.run(
        run_proposal_session(
            bundle=bundle,
            execution=execution,
            source_task_root=source_task_root,
            session_root=tmp_path / "session",
            environment_pool=pool,
        )
    )

    by_node = {node.node_id: node for node in receipt.node_receipts}
    assert receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE
    assert receipt.failure_code is ProposalCandidateFailureCode.AGENT_TURN_BUDGET_EXHAUSTED
    assert by_node["assess-a"].status is ProposalNodeReceiptStatus.CANDIDATE_FAILURE
    assert by_node["assess-b"].status is ProposalNodeReceiptStatus.COMPLETED
    assert by_node["finalize"].status is ProposalNodeReceiptStatus.SKIPPED
    assert by_node["finalize"].skip_cause is ProposalNodeSkipCause.UPSTREAM_FAILURE
    assert by_node["finalize"].causal_receipt_sha256s == (by_node["assess-a"].content_sha256,)
    assert "finalize" not in pool.leased_node_ids


@pytest.mark.parametrize(
    ("capacity", "code"),
    (
        (None, "environment_pool_required"),
        (1, "environment_pool_insufficient"),
    ),
)
def test_ready_set_session_fails_closed_without_sufficient_isolated_pool(
    tmp_path: Path,
    capacity: int | None,
    code: str,
) -> None:
    bundle, source_task_root = _ready_set_bundle(tmp_path / "fixture")
    execution = _execution_ref(bundle)
    pool = (
        None
        if capacity is None
        else _RecordingProposalEnvironmentPool(
            root=tmp_path / "pool",
            bundle=bundle,
            runtime_archive_sha256=execution.runtime_archive_sha256,
            capacity=capacity,
        )
    )

    with pytest.raises(ProposalSessionRuntimeError) as exc_info:
        asyncio.run(
            run_proposal_session(
                bundle=bundle,
                execution=execution,
                source_task_root=source_task_root,
                session_root=tmp_path / "session",
                environment_pool=pool,
            )
        )

    assert exc_info.value.code == code
    if pool is not None:
        assert pool.leased_node_ids == []


def _ready_set_bundle(
    tmp_path: Path,
) -> tuple[ProposalRunSessionBundle, Path]:
    fixture, governed, _graph = _governed_graph_fixture(
        tmp_path,
        shape="fork_join",
        agent_capability_id="aecbench.adapter.rlm-output-commit",
        include_tool_binding=False,
    )
    sequential_arguments = _compile_arguments(fixture, governed)
    sequential = cast(
        ProposalExecutionProfile,
        sequential_arguments["execution_profile"],
    )
    profile_payload = sequential.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    profile_payload["profile_id"] = "aecbench.proposal-execution.ready-set"
    profile_payload["version"] = "1.0.0"
    profile_payload["scheduling"] = ProposalSchedulingPolicy(
        semantics=ProposalSchedulingSemantics.READY_SET_DATAFLOW,
        max_parallelism=2,
        environment_policy=(ProposalEnvironmentPolicy.ISOLATED_ENVIRONMENT_POOL),
        deterministic_commit_order=True,
    ).model_dump(mode="json")
    ready_set_profile = ProposalExecutionProfile.model_validate(
        profile_payload,
    )
    governed = _issue(
        fixture,
        execution_profile=ready_set_profile,
        freeze_id="freeze.phase9.dev.ready-set",
        event_id="authority.freeze.phase9.dev.ready-set",
        replay_id="replay.freeze.phase9.dev.ready-set",
    )
    arguments = _compile_arguments(fixture, governed)
    arguments["execution_profile"] = ready_set_profile
    compile_call = cast(
        Callable[..., object],
        compile_governed_proposal,
    )
    compiled = compile_call(**arguments)
    assert not isinstance(compiled, ProposalCompilationRejection)
    assert isinstance(compiled, ProposalRunSessionBundle)
    return (
        compiled,
        fixture.ledger.root.parent / "tasks" / compiled.task_snapshot.task_id,
    )


class _BranchOrderingEnvironment(_RecordingProposalEnvironment):
    def __init__(
        self,
        *,
        branch_b_completed: asyncio.Event,
        execution_completion_order: list[str],
        initial_identity: str,
        root: Path,
        bundle: ProposalRunSessionBundle,
        runtime_archive_sha256: str,
        failed_node_ids: set[str],
    ) -> None:
        super().__init__(
            root=root,
            bundle=bundle,
            runtime_archive_sha256=runtime_archive_sha256,
            failed_node_ids=failed_node_ids,
        )
        self._branch_b_completed = branch_b_completed
        self._execution_completion_order = execution_completion_order
        self._container_identity = initial_identity

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> _RecordedExecResult:
        node_id = self.reset_node_ids[-1]
        if node_id == "assess-a":
            await self._branch_b_completed.wait()
        result = await super().exec(
            command,
            cwd=cwd,
            env=env,
            timeout_sec=timeout_sec,
        )
        self._execution_completion_order.append(node_id)
        if node_id == "assess-b":
            self._branch_b_completed.set()
        return result


class _RecordingProposalEnvironmentPool:
    def __init__(
        self,
        *,
        root: Path,
        bundle: ProposalRunSessionBundle,
        runtime_archive_sha256: str,
        capacity: int,
        failed_node_ids: set[str] | None = None,
    ) -> None:
        self.root = root
        self.bundle = bundle
        self.runtime_archive_sha256 = runtime_archive_sha256
        self.capacity = capacity
        self.failed_node_ids = failed_node_ids or set()
        self.leased_node_ids: list[str] = []
        self.execution_completion_order: list[str] = []
        self.max_observed_leases = 0
        self._active_leases = 0
        self._branch_b_completed = asyncio.Event()

    @asynccontextmanager
    async def lease(
        self,
        *,
        invocation_id: str,
    ) -> AsyncIterator[ProposalSessionEnvironment]:
        node_id = invocation_id.rsplit(".", maxsplit=1)[-1]
        self.leased_node_ids.append(node_id)
        self._active_leases += 1
        self.max_observed_leases = max(
            self.max_observed_leases,
            self._active_leases,
        )
        environment = _BranchOrderingEnvironment(
            root=self.root / invocation_id,
            bundle=self.bundle,
            runtime_archive_sha256=self.runtime_archive_sha256,
            failed_node_ids=self.failed_node_ids,
            branch_b_completed=self._branch_b_completed,
            execution_completion_order=self.execution_completion_order,
            initial_identity=f"container.initial.{invocation_id}",
        )
        try:
            yield cast(ProposalSessionEnvironment, environment)
        finally:
            self._active_leases -= 1
