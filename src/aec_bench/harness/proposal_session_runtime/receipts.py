# ABOUTME: Builds proposal-session execution references, node lineage, and terminal receipts.
# ABOUTME: Preserves deterministic receipt ordering and causal skip evidence.

from __future__ import annotations

import hashlib
import re

from aec_bench.contracts.program_proposal import MatchedEvaluationCoordinate
from aec_bench.contracts.proposal_execution import (
    FinalSynthesisSpec,
    NodeBudgetReservation,
    ProposalContainerTransitionRef,
    ProposalHandoff,
    ProposalHandoffArtifactRef,
    ProposalNodeReceipt,
    ProposalNodeReceiptStatus,
    ProposalNodeSkipCause,
    ProposalSessionExecutionRef,
    SemanticSubtaskSpec,
)
from aec_bench.harness.proposal_session_config import (
    LoadedProposalSessionHostInputs,
)
from aec_bench.harness.proposal_session_evidence import (
    PersistedProposalNodeEvidence,
    ProposalSessionEvidenceError,
)
from aec_bench.meta_harness.program_proposal_compilation import (
    ProposalRunSessionBundle,
)

from .contracts import (
    NodeReceiptLineage,
    PreparedProposalNodeInvocation,
    ProposalBackend,
    ProposalSessionRuntimeError,
)

_SAFE_INVOCATION_SEGMENT = re.compile(r"[^A-Za-z0-9._-]+")


def build_proposal_session_execution_ref(
    *,
    inputs: LoadedProposalSessionHostInputs,
    session_id: str,
    environment_session_id: str,
    backend: ProposalBackend,
) -> ProposalSessionExecutionRef:
    """Bind one Harbor environment to the exact host-validated proposal inputs."""

    return ProposalSessionExecutionRef(
        session_id=session_id,
        environment_session_id=environment_session_id,
        backend=backend,
        source_task_package_sha256=inputs.config.source_task_package_sha256,
        runtime_task_package_sha256=(inputs.derived_task_manifest.content_sha256),
        runtime_archive_content_sha256=(inputs.runtime_archive.content_sha256),
        runtime_archive_sha256=inputs.runtime_archive.archive_sha256,
        evaluation_coordinate=inputs.config.evaluation_coordinate,
        execution_schedule_sha256=(inputs.config.execution_schedule_sha256),
        execution_assignment_sha256=(inputs.config.execution_assignment_sha256),
    )


def _validate_session_execution_binding(
    *,
    bundle: ProposalRunSessionBundle,
    execution: ProposalSessionExecutionRef,
) -> None:
    if execution.source_task_package_sha256 != bundle.compilation.source_scope_manifest.task_package_sha256:
        raise ProposalSessionRuntimeError(
            "session_execution_mismatch",
            "proposal execution does not bind the compiled source task package",
        )
    _validate_evaluation_coordinate(
        bundle=bundle,
        coordinate=execution.evaluation_coordinate,
    )


def _validate_evaluation_coordinate(
    *,
    bundle: ProposalRunSessionBundle,
    coordinate: MatchedEvaluationCoordinate,
) -> None:
    freeze = bundle.compilation.proposal_freeze
    if (
        coordinate.task_id != bundle.task_snapshot.task_id
        or coordinate.task_revision != bundle.task_snapshot.definition_sha256
        or coordinate.split is not freeze.split
        or coordinate.world_lineage_id != freeze.selected_world_lineage_id
        or (
            freeze.provider_calibration_evaluation_seed is not None
            and coordinate.seed != freeze.provider_calibration_evaluation_seed
        )
    ):
        raise ProposalSessionRuntimeError(
            "session_execution_mismatch",
            "proposal execution evaluation coordinate differs from the compiled session",
        )


def _reservation(
    bundle: ProposalRunSessionBundle,
    *,
    node_id: str,
) -> NodeBudgetReservation:
    reservation = next(
        (item for item in bundle.compilation.budget_plan.reservations if item.node_id == node_id),
        None,
    )
    if reservation is None:
        raise ProposalSessionRuntimeError(
            "session_plan_mismatch",
            f"proposal node {node_id!r} has no fixed budget reservation",
        )
    return reservation


def _node(
    bundle: ProposalRunSessionBundle,
    *,
    node_id: str,
) -> SemanticSubtaskSpec | FinalSynthesisSpec:
    graph = bundle.compilation.proposal_graph
    node = next(
        (subtask for subtask in graph.semantic_subtasks if subtask.node_id == node_id),
        None,
    )
    if node is not None:
        return node
    if graph.finalizer.node_id == node_id:
        return graph.finalizer
    raise ProposalSessionRuntimeError(
        "session_plan_mismatch",
        f"unknown proposal node {node_id!r}",
    )


def _attempted_node_receipt(
    *,
    bundle: ProposalRunSessionBundle,
    execution: ProposalSessionExecutionRef,
    prepared: PreparedProposalNodeInvocation,
    persisted: PersistedProposalNodeEvidence,
    container_transition: ProposalContainerTransitionRef,
    upstream_receipt_sha256s: tuple[str, ...],
    emitted_handoffs: tuple[ProposalHandoffArtifactRef, ...],
) -> ProposalNodeReceipt:
    status = (
        ProposalNodeReceiptStatus.COMPLETED
        if persisted.failure_code is None
        else ProposalNodeReceiptStatus.CANDIDATE_FAILURE
    )
    return ProposalNodeReceipt(
        **_node_receipt_lineage(
            bundle=bundle,
            execution=execution,
            node_id=prepared.node_id,
            node_contract_sha256=prepared.node_contract_sha256,
        ),
        receipt_id=(f"proposal-node-receipt.{execution.session_id}.{prepared.invocation_id}"),
        upstream_receipt_sha256s=upstream_receipt_sha256s,
        attempt=1,
        status=status,
        invocation_id=prepared.invocation_id,
        container_transition=container_transition,
        node_context_sha256=prepared.context_manifest.content_sha256,
        execution_request_sha256=persisted.execution_request_sha256,
        runtime_execution_attestation_sha256=(persisted.runtime_execution_attestation_sha256),
        execution_result=persisted.execution_result,
        contract_check_result=persisted.contract_check_result,
        output_artifact_sha256=persisted.output_artifact_sha256,
        emitted_handoffs=emitted_handoffs,
        failure_code=persisted.failure_code,
        resources=persisted.resources,
        skip_cause=None,
        causal_receipt_sha256s=(),
    )


def _skipped_node_receipt(
    *,
    bundle: ProposalRunSessionBundle,
    execution: ProposalSessionExecutionRef,
    node_id: str,
    upstream_receipt_sha256s: tuple[str, ...],
    causal_receipt_sha256s: tuple[str, ...],
) -> ProposalNodeReceipt:
    return ProposalNodeReceipt(
        **_node_receipt_lineage(
            bundle=bundle,
            execution=execution,
            node_id=node_id,
            node_contract_sha256=_node_contract_sha256(
                bundle=bundle,
                node_id=node_id,
            ),
        ),
        receipt_id=(f"proposal-node-receipt.{execution.session_id}.{node_id}.skipped"),
        upstream_receipt_sha256s=upstream_receipt_sha256s,
        attempt=None,
        status=ProposalNodeReceiptStatus.SKIPPED,
        invocation_id=None,
        container_transition=None,
        node_context_sha256=None,
        execution_request_sha256=None,
        runtime_execution_attestation_sha256=None,
        execution_result=None,
        contract_check_result=None,
        output_artifact_sha256=None,
        emitted_handoffs=(),
        failure_code=None,
        resources=None,
        skip_cause=ProposalNodeSkipCause.UPSTREAM_FAILURE,
        causal_receipt_sha256s=causal_receipt_sha256s,
    )


def _node_receipt_lineage(
    *,
    bundle: ProposalRunSessionBundle,
    execution: ProposalSessionExecutionRef,
    node_id: str,
    node_contract_sha256: str,
) -> NodeReceiptLineage:
    compilation = bundle.compilation
    graph = compilation.proposal_graph
    scope = next(scope for scope in compilation.source_scope_manifest.node_scopes if scope.node_id == node_id)
    return {
        "session_id": execution.session_id,
        "session_execution_sha256": execution.content_sha256,
        "session_plan_sha256": bundle.session_plan.content_sha256,
        "compilation_sha256": compilation.content_sha256,
        "candidate_id": compilation.candidate_ref.candidate_id,
        "proposal_graph_sha256": graph.content_sha256,
        "problem_view_sha256": graph.problem_view_sha256,
        "kernel_sha256": compilation.kernel_sha256,
        "fixed_harness_sha256": bundle.fixed_harness.content_sha256,
        "proposal_policy_sha256": graph.proposal_policy_sha256,
        "node_id": node_id,
        "node_source_scope_sha256": scope.content_sha256,
        "node_budget_reservation_sha256": _reservation(
            bundle,
            node_id=node_id,
        ).content_sha256,
        "node_contract_sha256": node_contract_sha256,
    }


def _node_contract_sha256(
    *,
    bundle: ProposalRunSessionBundle,
    node_id: str,
) -> str:
    node = _node(bundle, node_id=node_id)
    if isinstance(node, SemanticSubtaskSpec):
        return node.evidence_contract.content_sha256
    return node.output_completion_contract_sha256


def _incoming_handoffs(
    *,
    bundle: ProposalRunSessionBundle,
    node_id: str,
) -> tuple[ProposalHandoff, ...]:
    return tuple(
        sorted(
            (handoff for handoff in bundle.compilation.proposal_graph.handoffs if handoff.consumer_node_id == node_id),
            key=lambda handoff: handoff.handoff_id,
        )
    )


def _receipt_producer_ids(
    *,
    bundle: ProposalRunSessionBundle,
    node_id: str,
) -> tuple[str, ...]:
    graph = bundle.compilation.proposal_graph
    if node_id == graph.finalizer.node_id:
        return tuple(sorted(subtask.node_id for subtask in graph.semantic_subtasks))
    return tuple(
        sorted({handoff.producer_node_id for handoff in graph.handoffs if handoff.consumer_node_id == node_id})
    )


def _proposal_invocation_id(
    *,
    index: int,
    node_id: str,
) -> str:
    segment = _SAFE_INVOCATION_SEGMENT.sub("-", node_id).strip(
        "._-",
    )
    if not segment:
        segment = "node"
    if segment != node_id or len(segment) > 64:
        digest = hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:12]
        segment = f"{segment[:48]}.{digest}"
    return f"invoke.{index:04d}.{segment}"


def _runtime_error_from_evidence(
    error: ProposalSessionEvidenceError,
) -> ProposalSessionRuntimeError:
    return ProposalSessionRuntimeError(error.code, str(error))
