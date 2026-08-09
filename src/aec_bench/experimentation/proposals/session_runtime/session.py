# ABOUTME: Schedules proposal DAG nodes and publishes one deterministic session receipt.
# ABOUTME: Supports sequential and isolated ready-set execution without sharing candidate state.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from aec_bench.contracts.proposal_execution.graph import ProposalHandoff
from aec_bench.contracts.proposal_execution.session import (
    ProposalNodeReceipt,
    ProposalSessionExecutionRef,
    ProposalSessionReceipt,
)
from aec_bench.contracts.proposal_execution_profile import (
    ProposalSchedulingPolicy,
    ProposalSchedulingSemantics,
)
from aec_bench.contracts.proposal_execution_types import ProposalNodeReceiptStatus, ProposalSessionStatus
from aec_bench.experimentation.proposals.node_context import (
    PersistedProposalHandoffArtifact,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.scheduler import (
    ProposalDagNodeExecution,
    ProposalDagNodeOutcome,
    ProposalDagNodeState,
    run_proposal_dag,
)
from aec_bench.harness.kernel_catalogue import (
    KernelOperationHandlerKey,
    KernelRuntimeRegistry,
    default_kernel_registry,
)

from .contracts import (
    ExecutedProposalNode,
    ProposalSessionEnvironment,
    ProposalSessionEnvironmentPool,
    ProposalSessionRuntimeError,
)
from .kernel import (
    _require_proposal_operation_handler,
    _validate_kernel,
)
from .node_execution import execute_proposal_node
from .receipts import (
    _incoming_handoffs,
    _proposal_invocation_id,
    _receipt_producer_ids,
    _skipped_node_receipt,
    _validate_session_execution_binding,
)


@dataclass
class _ProposalSessionState:
    bundle: ProposalRunSessionBundle
    execution: ProposalSessionExecutionRef
    source_task_root: Path
    session_root: Path
    environment: ProposalSessionEnvironment | None
    environment_pool: ProposalSessionEnvironmentPool | None
    child_environment: Mapping[str, str] | None
    registry: KernelRuntimeRegistry
    scheduling: ProposalSchedulingPolicy
    invocation_index_by_node: dict[str, int]
    receipts_by_node: dict[str, ProposalNodeReceipt] = field(
        default_factory=dict,
    )
    handoffs_by_id: dict[
        str,
        PersistedProposalHandoffArtifact,
    ] = field(default_factory=dict)
    final_output_sha256: str | None = None
    final_commit_sha256: str | None = None

    async def execute_node(
        self,
        node_id: str,
    ) -> ProposalDagNodeExecution[ExecutedProposalNode]:
        producer_receipts = tuple(
            self.receipts_by_node[producer_id]
            for producer_id in _receipt_producer_ids(
                bundle=self.bundle,
                node_id=node_id,
            )
        )
        invocation_id = _proposal_invocation_id(
            index=self.invocation_index_by_node[node_id],
            node_id=node_id,
        )
        incoming_handoffs = _incoming_handoffs(
            bundle=self.bundle,
            node_id=node_id,
        )
        try:
            upstream_handoff_artifacts = tuple(self.handoffs_by_id[handoff.handoff_id] for handoff in incoming_handoffs)
        except KeyError as error:
            raise ProposalSessionRuntimeError(
                "handoff_evidence_missing",
                f"proposal node {node_id!r} lacks a persisted upstream handoff",
            ) from error
        executed = await self._execute_in_environment(
            node_id=node_id,
            invocation_id=invocation_id,
            producer_receipts=producer_receipts,
            incoming_handoffs=incoming_handoffs,
            upstream_handoff_artifacts=(upstream_handoff_artifacts),
        )
        return ProposalDagNodeExecution(
            value=executed,
            succeeded=(executed.receipt.status is ProposalNodeReceiptStatus.COMPLETED),
        )

    async def _execute_in_environment(
        self,
        *,
        node_id: str,
        invocation_id: str,
        producer_receipts: tuple[ProposalNodeReceipt, ...],
        incoming_handoffs: tuple[ProposalHandoff, ...],
        upstream_handoff_artifacts: tuple[
            PersistedProposalHandoffArtifact,
            ...,
        ],
    ) -> ExecutedProposalNode:
        if self.scheduling.semantics is ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW:
            if self.environment is None:
                raise ProposalSessionRuntimeError(
                    "environment_required",
                    "sequential proposal execution lacks its rotated environment",
                )
            return await self._execute_with(
                environment=self.environment,
                node_id=node_id,
                invocation_id=invocation_id,
                producer_receipts=producer_receipts,
                incoming_handoffs=incoming_handoffs,
                upstream_handoff_artifacts=(upstream_handoff_artifacts),
            )
        if self.environment_pool is None:
            raise ProposalSessionRuntimeError(
                "environment_pool_required",
                "ready-set proposal execution lacks its isolated environment pool",
            )
        try:
            async with self.environment_pool.lease(
                invocation_id=invocation_id,
            ) as isolated_environment:
                return await self._execute_with(
                    environment=isolated_environment,
                    node_id=node_id,
                    invocation_id=invocation_id,
                    producer_receipts=producer_receipts,
                    incoming_handoffs=incoming_handoffs,
                    upstream_handoff_artifacts=(upstream_handoff_artifacts),
                )
        except ProposalSessionRuntimeError:
            raise
        except Exception as error:
            raise ProposalSessionRuntimeError(
                "environment_pool_failed",
                f"proposal environment lease failed: {error}",
            ) from error

    async def _execute_with(
        self,
        *,
        environment: ProposalSessionEnvironment,
        node_id: str,
        invocation_id: str,
        producer_receipts: tuple[ProposalNodeReceipt, ...],
        incoming_handoffs: tuple[ProposalHandoff, ...],
        upstream_handoff_artifacts: tuple[
            PersistedProposalHandoffArtifact,
            ...,
        ],
    ) -> ExecutedProposalNode:
        return await execute_proposal_node(
            bundle=self.bundle,
            execution=self.execution,
            source_task_root=self.source_task_root,
            session_root=self.session_root,
            environment=environment,
            child_environment=self.child_environment,
            registry=self.registry,
            node_id=node_id,
            invocation_id=invocation_id,
            producer_receipts=producer_receipts,
            incoming_handoffs=incoming_handoffs,
            upstream_handoff_artifacts=(upstream_handoff_artifacts),
        )

    def commit_node(
        self,
        outcome: ProposalDagNodeOutcome[ExecutedProposalNode],
    ) -> None:
        if outcome.state is ProposalDagNodeState.SKIPPED:
            self._commit_skipped_node(outcome)
            return
        executed = outcome.value
        if executed is None:
            raise ProposalSessionRuntimeError(
                "scheduler_result_missing",
                f"attempted proposal node {outcome.node_id!r} lacks execution evidence",
            )
        self.receipts_by_node[outcome.node_id] = executed.receipt
        self.handoffs_by_id.update({handoff.handoff_id: handoff for handoff in executed.handoffs})
        if executed.final_output_sha256 is not None:
            self.final_output_sha256 = executed.final_output_sha256
            self.final_commit_sha256 = executed.final_commit_sha256

    def _commit_skipped_node(
        self,
        outcome: ProposalDagNodeOutcome[ExecutedProposalNode],
    ) -> None:
        producer_receipts = tuple(
            self.receipts_by_node[producer_id]
            for producer_id in _receipt_producer_ids(
                bundle=self.bundle,
                node_id=outcome.node_id,
            )
        )
        causal_receipts = tuple(self.receipts_by_node[producer_id] for producer_id in outcome.causal_node_ids)
        self.receipts_by_node[outcome.node_id] = _skipped_node_receipt(
            bundle=self.bundle,
            execution=self.execution,
            node_id=outcome.node_id,
            upstream_receipt_sha256s=tuple(sorted(receipt.content_sha256 for receipt in producer_receipts)),
            causal_receipt_sha256s=tuple(sorted(receipt.content_sha256 for receipt in causal_receipts)),
        )

    def build_receipt(self) -> ProposalSessionReceipt:
        failed_receipt = next(
            (
                self.receipts_by_node[node_id]
                for node_id in self.bundle.session_plan.topological_order
                if (self.receipts_by_node[node_id].status is ProposalNodeReceiptStatus.CANDIDATE_FAILURE)
            ),
            None,
        )
        ordered_receipts = tuple(
            self.receipts_by_node[node_id] for node_id in self.bundle.session_plan.planned_node_ids
        )
        try:
            if failed_receipt is None:
                return ProposalSessionReceipt(
                    session_id=self.execution.session_id,
                    execution=self.execution,
                    plan=self.bundle.session_plan,
                    planned_node_ids=(self.bundle.session_plan.planned_node_ids),
                    node_receipts=ordered_receipts,
                    status=ProposalSessionStatus.COMPLETED,
                    final_output_artifact_sha256=(self.final_output_sha256),
                    output_commit_attestation_sha256=(self.final_commit_sha256),
                    trial_record_permitted=True,
                    failure_code=None,
                )
            return ProposalSessionReceipt(
                session_id=self.execution.session_id,
                execution=self.execution,
                plan=self.bundle.session_plan,
                planned_node_ids=(self.bundle.session_plan.planned_node_ids),
                node_receipts=ordered_receipts,
                status=ProposalSessionStatus.CANDIDATE_FAILURE,
                final_output_artifact_sha256=None,
                output_commit_attestation_sha256=None,
                trial_record_permitted=False,
                failure_code=failed_receipt.failure_code,
            )
        except ValueError as error:
            raise ProposalSessionRuntimeError(
                "session_evidence_invalid",
                f"proposal session receipt failed closed validation: {error}",
            ) from error


async def run_proposal_session(
    *,
    bundle: ProposalRunSessionBundle,
    execution: ProposalSessionExecutionRef,
    source_task_root: Path,
    session_root: Path,
    environment: ProposalSessionEnvironment | None = None,
    environment_pool: ProposalSessionEnvironmentPool | None = None,
    child_environment: Mapping[str, str] | None = None,
    registry: KernelRuntimeRegistry | None = None,
) -> ProposalSessionReceipt:
    """Execute one compiled proposal as isolated graph-bound child invocations."""

    resolved_registry = registry or default_kernel_registry()
    _validate_session_execution_binding(
        bundle=bundle,
        execution=execution,
    )
    _validate_kernel(
        bundle=bundle,
        registry=resolved_registry,
    )
    _require_proposal_operation_handler(
        bundle=bundle,
        registry=resolved_registry,
        operation_id="run_proposal_session.v1",
        expected=(KernelOperationHandlerKey.RUN_PROPOSAL_SESSION),
    )
    execution_profile = bundle.compilation.execution_profile
    if execution_profile is None:
        raise ProposalSessionRuntimeError(
            "execution_profile_missing",
            "proposal session execution requires a profile-bound compilation",
        )
    scheduling = execution_profile.scheduling
    _validate_session_environment_surface(
        scheduling_semantics=scheduling.semantics,
        max_parallelism=scheduling.max_parallelism,
        environment=environment,
        environment_pool=environment_pool,
    )
    node_order = bundle.session_plan.topological_order
    state = _ProposalSessionState(
        bundle=bundle,
        execution=execution,
        source_task_root=Path(source_task_root),
        session_root=Path(session_root),
        environment=environment,
        environment_pool=environment_pool,
        child_environment=child_environment,
        registry=resolved_registry,
        scheduling=scheduling,
        invocation_index_by_node={
            node_id: index
            for index, node_id in enumerate(
                node_order,
                start=1,
            )
        },
    )
    await run_proposal_dag(
        node_order=node_order,
        dependencies={
            node_id: _receipt_producer_ids(
                bundle=bundle,
                node_id=node_id,
            )
            for node_id in node_order
        },
        scheduling=scheduling,
        execute=state.execute_node,
        commit=state.commit_node,
    )
    return state.build_receipt()


def _validate_session_environment_surface(
    *,
    scheduling_semantics: ProposalSchedulingSemantics,
    max_parallelism: int,
    environment: ProposalSessionEnvironment | None,
    environment_pool: ProposalSessionEnvironmentPool | None,
) -> None:
    if scheduling_semantics is ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW:
        if environment is None:
            raise ProposalSessionRuntimeError(
                "environment_required",
                "sequential proposal execution requires one rotated environment",
            )
        if environment_pool is not None:
            raise ProposalSessionRuntimeError(
                "environment_policy_mismatch",
                "sequential proposal execution cannot use an environment pool",
            )
        return
    if environment is not None:
        raise ProposalSessionRuntimeError(
            "environment_policy_mismatch",
            "ready-set proposal execution cannot share one mutable environment",
        )
    if environment_pool is None:
        raise ProposalSessionRuntimeError(
            "environment_pool_required",
            "ready-set proposal execution requires an isolated environment pool",
        )
    if (
        not isinstance(environment_pool.capacity, int)
        or isinstance(environment_pool.capacity, bool)
        or environment_pool.capacity < max_parallelism
    ):
        raise ProposalSessionRuntimeError(
            "environment_pool_insufficient",
            "proposal environment pool capacity is below the profiled parallelism",
        )
