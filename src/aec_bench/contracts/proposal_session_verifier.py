# ABOUTME: Verifies proposal-session lineage, evidence, budgets, transitions, and terminal state.
# ABOUTME: Returns typed recomputation evidence independently of the persisted receipt contract.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationSuccess
from aec_bench.contracts.proposal_execution.graph import ExecutableCandidateGraph
from aec_bench.contracts.proposal_execution.session import (
    ProposalContainerTransitionRef,
    ProposalNodeReceipt,
    ProposalSessionReceipt,
)
from aec_bench.contracts.proposal_execution_budget import NodeBudgetReservation
from aec_bench.contracts.proposal_execution_context import CompiledNodeContextScope
from aec_bench.contracts.proposal_execution_profile import (
    ProposalSchedulingSemantics,
)
from aec_bench.contracts.proposal_execution_types import (
    ProposalCandidateFailureCode,
    ProposalNodeReceiptStatus,
    ProposalNodeSkipCause,
    ProposalSessionStatus,
)
from aec_bench.contracts.stage_execution import StageResourceEvidence


@dataclass(frozen=True, slots=True)
class ProposalSessionVerification:
    """Derived evidence summary for one internally consistent proposal session."""

    session_id: str
    plan_sha256: str
    candidate_id: str
    attempted_node_ids: tuple[str, ...]
    completed_node_ids: tuple[str, ...]
    candidate_failure_node_ids: tuple[str, ...]
    skipped_node_ids: tuple[str, ...]
    transition_artifact_sha256s: tuple[str, ...]
    final_output_verified: bool


_BUDGET_FAILURE_CODES = frozenset(
    {
        ProposalCandidateFailureCode.AGENT_TURN_BUDGET_EXHAUSTED,
        ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        ProposalCandidateFailureCode.COST_BUDGET_EXHAUSTED,
        ProposalCandidateFailureCode.TOOL_CALL_BUDGET_EXHAUSTED,
        ProposalCandidateFailureCode.CONTEXT_BUDGET_EXHAUSTED,
        ProposalCandidateFailureCode.RUNTIME_BUDGET_EXHAUSTED,
    }
)


def verify_proposal_session_receipt(
    session: ProposalSessionReceipt,
) -> ProposalSessionVerification:
    """Recompute all cross-record invariants for one proposal-session receipt."""

    compilation = session.plan.compilation
    graph = compilation.proposal_graph
    _validate_session_execution_binding(
        session,
        compilation=compilation,
    )
    receipts, scopes, reservations = _session_receipt_indexes(
        session,
        compilation=compilation,
    )
    attempted_receipts = _validate_attempted_receipt_evidence(session)
    transitions, topological_positions = _session_transition_evidence(
        session,
        receipts=receipts,
        attempted_receipts=attempted_receipts,
    )
    _validate_session_transition_policy(
        compilation=compilation,
        transitions=transitions,
    )
    _validate_session_receipt_graph(
        session,
        compilation=compilation,
        receipts=receipts,
        scopes=scopes,
        reservations=reservations,
        topological_positions=topological_positions,
    )
    _validate_session_terminal(
        session,
        graph=graph,
        receipts=receipts,
    )
    return _verification_result(
        session,
        compilation=compilation,
        transitions=transitions,
    )


def _verification_result(
    session: ProposalSessionReceipt,
    *,
    compilation: ProposalCompilationSuccess,
    transitions: tuple[ProposalContainerTransitionRef, ...],
) -> ProposalSessionVerification:
    ordered_receipts = tuple(
        next(receipt for receipt in session.node_receipts if receipt.node_id == node_id)
        for node_id in session.plan.topological_order
    )
    return ProposalSessionVerification(
        session_id=session.session_id,
        plan_sha256=session.plan.content_sha256,
        candidate_id=compilation.candidate_ref.candidate_id,
        attempted_node_ids=tuple(
            receipt.node_id for receipt in ordered_receipts if receipt.status is not ProposalNodeReceiptStatus.SKIPPED
        ),
        completed_node_ids=_node_ids_with_status(
            ordered_receipts,
            status=ProposalNodeReceiptStatus.COMPLETED,
        ),
        candidate_failure_node_ids=_node_ids_with_status(
            ordered_receipts,
            status=ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
        ),
        skipped_node_ids=_node_ids_with_status(
            ordered_receipts,
            status=ProposalNodeReceiptStatus.SKIPPED,
        ),
        transition_artifact_sha256s=tuple(transition.artifact_sha256 for transition in transitions),
        final_output_verified=(session.status is ProposalSessionStatus.COMPLETED),
    )


def _node_ids_with_status(
    receipts: tuple[ProposalNodeReceipt, ...],
    *,
    status: ProposalNodeReceiptStatus,
) -> tuple[str, ...]:
    return tuple(receipt.node_id for receipt in receipts if receipt.status is status)


def _validate_session_execution_binding(
    session: ProposalSessionReceipt,
    *,
    compilation: ProposalCompilationSuccess,
) -> None:
    if session.execution.session_id != session.session_id:
        raise ValueError("proposal execution session id does not match its receipt")
    coordinate = session.execution.evaluation_coordinate
    freeze = compilation.proposal_freeze
    if (
        coordinate.task_id != freeze.problem_view.task_id
        or coordinate.task_revision != freeze.problem_view.task_revision
        or coordinate.split is not freeze.split
        or coordinate.review_lineage_id != freeze.selected_review_lineage_id
    ):
        raise ValueError(
            "proposal execution evaluation coordinate does not bind the compiled task, split, and world",
        )


def _session_receipt_indexes(
    session: ProposalSessionReceipt,
    *,
    compilation: ProposalCompilationSuccess,
) -> tuple[
    dict[str, ProposalNodeReceipt],
    dict[str, CompiledNodeContextScope],
    dict[str, NodeBudgetReservation],
]:
    if (
        session.planned_node_ids != session.plan.planned_node_ids
        or tuple(receipt.node_id for receipt in session.node_receipts) != session.plan.planned_node_ids
    ):
        raise ValueError("session requires the exact planned node receipt multiset")
    return (
        {receipt.node_id: receipt for receipt in session.node_receipts},
        {scope.node_id: scope for scope in compilation.source_scope_manifest.node_scopes},
        {reservation.node_id: reservation for reservation in compilation.budget_plan.reservations},
    )


def _validate_attempted_receipt_evidence(
    session: ProposalSessionReceipt,
) -> tuple[ProposalNodeReceipt, ...]:
    attempted_receipts = tuple(
        receipt for receipt in session.node_receipts if receipt.status is not ProposalNodeReceiptStatus.SKIPPED
    )
    invocation_ids = tuple(receipt.invocation_id for receipt in attempted_receipts)
    if len(invocation_ids) != len(set(invocation_ids)):
        raise ValueError("proposal node invocation ids must be unique within a session")
    persisted_paths = tuple(path for receipt in attempted_receipts for path in _attempted_receipt_paths(receipt))
    if len(persisted_paths) != len(set(persisted_paths)):
        raise ValueError("proposal node evidence artifact paths must be unique")
    return attempted_receipts


def _attempted_receipt_paths(
    receipt: ProposalNodeReceipt,
) -> tuple[str, ...]:
    candidates = (
        (receipt.container_transition.session_relative_path if receipt.container_transition is not None else None),
        (receipt.execution_result.session_relative_path if receipt.execution_result is not None else None),
        (receipt.contract_check_result.session_relative_path if receipt.contract_check_result is not None else None),
    )
    return tuple(path for path in candidates if path is not None)


def _session_transition_evidence(
    session: ProposalSessionReceipt,
    *,
    receipts: dict[str, ProposalNodeReceipt],
    attempted_receipts: tuple[ProposalNodeReceipt, ...],
) -> tuple[
    tuple[ProposalContainerTransitionRef, ...],
    dict[str, int],
]:
    topological_positions = {node_id: position for position, node_id in enumerate(session.plan.topological_order)}
    attempted_topological = tuple(
        receipts[node_id]
        for node_id in session.plan.topological_order
        if receipts[node_id].status is not ProposalNodeReceiptStatus.SKIPPED
    )
    transitions = tuple(
        receipt.container_transition for receipt in attempted_topological if receipt.container_transition is not None
    )
    if len(transitions) != len(attempted_receipts):
        raise ValueError("every attempted proposal node requires a container transition")
    if any(transition.runtime_archive_sha256 != session.execution.runtime_archive_sha256 for transition in transitions):
        raise ValueError("proposal container transitions must bind the session runtime archive")
    return transitions, topological_positions


def _validate_session_transition_policy(
    *,
    compilation: ProposalCompilationSuccess,
    transitions: tuple[ProposalContainerTransitionRef, ...],
) -> None:
    execution_profile = compilation.execution_profile
    if execution_profile is None:
        raise ValueError(
            "proposal session receipt requires a profile-bound compilation",
        )
    if execution_profile.scheduling.semantics is ProposalSchedulingSemantics.SEQUENTIAL_DATAFLOW:
        _validate_sequential_transition_chain(transitions)
        return
    _validate_isolated_transition_chains(transitions)


def _validate_sequential_transition_chain(
    transitions: tuple[ProposalContainerTransitionRef, ...],
) -> None:
    transition_identities = (
        (transitions[0].previous_container_identity,)
        + tuple(transition.current_container_identity for transition in transitions)
        if transitions
        else ()
    )
    if len(transition_identities) != len(set(transition_identities)):
        raise ValueError(
            "proposal container transition identities must be fresh within a session",
        )
    if any(
        current.previous_container_identity != previous.current_container_identity
        for previous, current in zip(
            transitions,
            transitions[1:],
            strict=False,
        )
    ):
        raise ValueError("proposal container transition chain must be continuous")


def _validate_isolated_transition_chains(
    transitions: tuple[ProposalContainerTransitionRef, ...],
) -> None:
    current_identities = tuple(transition.current_container_identity for transition in transitions)
    previous_identities = tuple(transition.previous_container_identity for transition in transitions)
    if len(current_identities) != len(set(current_identities)):
        raise ValueError(
            "ready-set proposal transitions require fresh container identities",
        )
    if len(previous_identities) != len(set(previous_identities)):
        raise ValueError(
            "ready-set proposal transitions cannot lease one environment concurrently",
        )
    current_positions = {identity: position for position, identity in enumerate(current_identities)}
    if any(
        transition.previous_container_identity == transition.current_container_identity for transition in transitions
    ):
        raise ValueError(
            "ready-set proposal transitions must rotate every leased environment",
        )
    if any(
        (
            predecessor_position := current_positions.get(
                transition.previous_container_identity,
            )
        )
        is not None
        and predecessor_position >= position
        for position, transition in enumerate(transitions)
    ):
        raise ValueError(
            "ready-set proposal transition chains must follow commit order",
        )


def _validate_session_receipt_graph(
    session: ProposalSessionReceipt,
    *,
    compilation: ProposalCompilationSuccess,
    receipts: dict[str, ProposalNodeReceipt],
    scopes: dict[str, CompiledNodeContextScope],
    reservations: dict[str, NodeBudgetReservation],
    topological_positions: dict[str, int],
) -> None:
    graph = compilation.proposal_graph
    receipts_by_sha256 = {receipt.content_sha256: receipt for receipt in session.node_receipts}
    for receipt in session.node_receipts:
        _validate_node_receipt_bindings(
            receipt=receipt,
            session=session,
            compilation=compilation,
            scope=scopes[receipt.node_id],
            reservation=reservations[receipt.node_id],
        )
        producer_ids = _receipt_producer_ids(
            receipt,
            graph=graph,
        )
        expected_upstream = tuple(sorted(receipts[node_id].content_sha256 for node_id in producer_ids))
        if receipt.upstream_receipt_sha256s != expected_upstream:
            raise ValueError(f"node {receipt.node_id!r} upstream receipt identities do not match")
        if receipt.status is ProposalNodeReceiptStatus.COMPLETED:
            _validate_completed_receipt_handoffs(
                receipt,
                graph=graph,
            )
        producer_receipts = tuple(receipts[node_id] for node_id in producer_ids)
        if receipt.status is ProposalNodeReceiptStatus.SKIPPED:
            _validate_skipped_receipt_causality(
                receipt,
                producer_receipts=producer_receipts,
                receipts_by_sha256=receipts_by_sha256,
                topological_positions=topological_positions,
            )
        elif any(producer.status is not ProposalNodeReceiptStatus.COMPLETED for producer in producer_receipts):
            raise ValueError(f"attempted node {receipt.node_id!r} cannot consume a failed or skipped upstream receipt")


def _validate_node_receipt_bindings(
    *,
    receipt: ProposalNodeReceipt,
    session: ProposalSessionReceipt,
    compilation: ProposalCompilationSuccess,
    scope: CompiledNodeContextScope,
    reservation: NodeBudgetReservation,
) -> None:
    graph = compilation.proposal_graph
    expected_contract = (
        next(
            (
                subtask.evidence_contract.content_sha256
                for subtask in graph.semantic_subtasks
                if subtask.node_id == receipt.node_id
            ),
            None,
        )
        or graph.finalizer.output_completion_contract_sha256
    )
    expected = (
        session.execution.content_sha256,
        session.plan.content_sha256,
        compilation.content_sha256,
        compilation.candidate_ref.candidate_id,
        graph.content_sha256,
        graph.problem_view_sha256,
        compilation.kernel_ref,
        compilation.fixed_harness_ref,
        graph.proposal_policy_sha256,
        scope.content_sha256,
        reservation.content_sha256,
        expected_contract,
    )
    actual = (
        receipt.session_execution_sha256,
        receipt.session_plan_sha256,
        receipt.compilation_sha256,
        receipt.candidate_id,
        receipt.proposal_graph_sha256,
        receipt.problem_view_sha256,
        receipt.kernel_ref,
        receipt.fixed_harness_ref,
        receipt.proposal_policy_sha256,
        receipt.node_source_scope_sha256,
        receipt.node_budget_reservation_sha256,
        receipt.node_contract_sha256,
    )
    if actual != expected or receipt.session_id != session.session_id:
        raise ValueError(f"node {receipt.node_id!r} receipt lineage does not match session")
    if receipt.resources is None:
        return
    _validate_receipt_resources(
        receipt=receipt,
        resources=receipt.resources,
        reservation=reservation,
    )


def _validate_receipt_resources(
    *,
    receipt: ProposalNodeReceipt,
    resources: StageResourceEvidence,
    reservation: NodeBudgetReservation,
) -> None:
    if resources.wall_seconds > reservation.max_runtime_seconds:
        raise ValueError(f"node {receipt.node_id!r} exceeds its runtime reservation")
    if resources.agent_turns is None or resources.agent_turns > reservation.max_agent_turns:
        raise ValueError(f"node {receipt.node_id!r} lacks or exceeds turn evidence")
    if resources.tool_calls is None or resources.tool_calls > reservation.max_tool_calls:
        raise ValueError(f"node {receipt.node_id!r} lacks or exceeds tool-call evidence")
    if reservation.max_tokens is not None:
        if resources.tokens_in is None or resources.tokens_out is None:
            raise ValueError(f"node {receipt.node_id!r} lacks token evidence")
        if resources.tokens_in + resources.tokens_out > reservation.max_tokens:
            raise ValueError(f"node {receipt.node_id!r} exceeds its token reservation")
    if reservation.max_cost_usd is not None:
        if resources.estimated_cost_usd is None:
            raise ValueError(f"node {receipt.node_id!r} lacks cost evidence")
        if resources.estimated_cost_usd > reservation.max_cost_usd:
            raise ValueError(f"node {receipt.node_id!r} exceeds its cost reservation")


def _receipt_producer_ids(
    receipt: ProposalNodeReceipt,
    *,
    graph: ExecutableCandidateGraph,
) -> set[str]:
    if receipt.node_id == graph.finalizer.node_id:
        return {subtask.node_id for subtask in graph.semantic_subtasks}
    return {handoff.producer_node_id for handoff in graph.handoffs if handoff.consumer_node_id == receipt.node_id}


def _validate_completed_receipt_handoffs(
    receipt: ProposalNodeReceipt,
    *,
    graph: ExecutableCandidateGraph,
) -> None:
    expected_handoffs = tuple(
        sorted(
            (handoff for handoff in graph.handoffs if handoff.producer_node_id == receipt.node_id),
            key=lambda handoff: handoff.handoff_id,
        )
    )
    if tuple(reference.handoff_id for reference in receipt.emitted_handoffs) != tuple(
        handoff.handoff_id for handoff in expected_handoffs
    ):
        raise ValueError(f"node {receipt.node_id!r} emitted handoff identities do not match")
    for reference, handoff in zip(
        receipt.emitted_handoffs,
        expected_handoffs,
        strict=True,
    ):
        if (
            reference.producer_node_id,
            reference.producer_output_id,
            reference.consumer_node_id,
            reference.consumer_input_id,
        ) != (
            handoff.producer_node_id,
            handoff.producer_output_id,
            handoff.consumer_node_id,
            handoff.consumer_input_id,
        ):
            raise ValueError(f"node {receipt.node_id!r} emitted handoff does not match its frozen graph edge")
    _validate_fanout_artifact_identity(receipt)


def _validate_fanout_artifact_identity(
    receipt: ProposalNodeReceipt,
) -> None:
    artifacts_by_output: dict[
        tuple[str, str],
        tuple[str, str, int],
    ] = {}
    for reference in receipt.emitted_handoffs:
        output_key = (
            reference.producer_node_id,
            reference.producer_output_id,
        )
        artifact_identity = (
            reference.session_relative_path,
            reference.artifact_sha256,
            reference.byte_size,
        )
        previous_artifact = artifacts_by_output.setdefault(
            output_key,
            artifact_identity,
        )
        if previous_artifact != artifact_identity:
            raise ValueError(f"node {receipt.node_id!r} fan-out handoffs do not share one canonical artifact")


def _validate_skipped_receipt_causality(
    receipt: ProposalNodeReceipt,
    *,
    producer_receipts: tuple[ProposalNodeReceipt, ...],
    receipts_by_sha256: dict[str, ProposalNodeReceipt],
    topological_positions: dict[str, int],
) -> None:
    unknown_causes = tuple(digest for digest in receipt.causal_receipt_sha256s if digest not in receipts_by_sha256)
    if unknown_causes or receipt.content_sha256 in receipt.causal_receipt_sha256s:
        raise ValueError(f"skipped node {receipt.node_id!r} references an unknown or self causal receipt")
    causal_receipts = tuple(receipts_by_sha256[digest] for digest in receipt.causal_receipt_sha256s)
    if receipt.skip_cause is ProposalNodeSkipCause.UPSTREAM_FAILURE:
        _validate_upstream_skip_causes(
            receipt,
            producer_receipts=producer_receipts,
        )
        return
    if any(
        cause.status is not ProposalNodeReceiptStatus.CANDIDATE_FAILURE
        or cause.failure_code not in _BUDGET_FAILURE_CODES
        or topological_positions[cause.node_id] >= topological_positions[receipt.node_id]
        for cause in causal_receipts
    ):
        raise ValueError(f"skipped node {receipt.node_id!r} requires an earlier candidate-owned budget failure")


def _validate_upstream_skip_causes(
    receipt: ProposalNodeReceipt,
    *,
    producer_receipts: tuple[ProposalNodeReceipt, ...],
) -> None:
    expected_causes = tuple(
        sorted(
            producer.content_sha256
            for producer in producer_receipts
            if producer.status is not ProposalNodeReceiptStatus.COMPLETED
        )
    )
    if not expected_causes or receipt.causal_receipt_sha256s != expected_causes:
        raise ValueError(f"skipped node {receipt.node_id!r} requires the exact failed or skipped upstream causes")


def _validate_session_terminal(
    session: ProposalSessionReceipt,
    *,
    graph: ExecutableCandidateGraph,
    receipts: dict[str, ProposalNodeReceipt],
) -> None:
    if session.status is ProposalSessionStatus.COMPLETED:
        _validate_completed_session(
            session,
            finalizer_receipt=receipts[graph.finalizer.node_id],
        )
        return
    _validate_candidate_failure_session(session)


def _validate_completed_session(
    session: ProposalSessionReceipt,
    *,
    finalizer_receipt: ProposalNodeReceipt,
) -> None:
    if (
        session.final_output_artifact_sha256 is None
        or session.output_commit_attestation_sha256 is None
        or not session.trial_record_permitted
        or session.failure_code is not None
        or any(receipt.status is not ProposalNodeReceiptStatus.COMPLETED for receipt in session.node_receipts)
    ):
        raise ValueError(
            "completed session requires completed nodes, committed output, and TrialRecord import permission"
        )
    if finalizer_receipt.output_artifact_sha256 != session.final_output_artifact_sha256:
        raise ValueError("session final output artifact does not match finalizer receipt")


def _validate_candidate_failure_session(
    session: ProposalSessionReceipt,
) -> None:
    if session.trial_record_permitted:
        raise ValueError("candidate failure cannot permit TrialRecord import")
    if session.final_output_artifact_sha256 is not None or session.output_commit_attestation_sha256 is not None:
        raise ValueError("candidate failure cannot bind final output or commit evidence")
    failed_receipts = tuple(
        receipt for receipt in session.node_receipts if receipt.status is ProposalNodeReceiptStatus.CANDIDATE_FAILURE
    )
    if session.failure_code is None or not failed_receipts:
        raise ValueError("candidate-failure session requires typed failed-node evidence")
    if session.failure_code not in {receipt.failure_code for receipt in failed_receipts}:
        raise ValueError("candidate-failure session code must match failed-node evidence")
