# ABOUTME: Executes one proposal node and persists its exact child and handoff evidence.
# ABOUTME: Keeps provider effects separate from graph scheduling and receipt publication.

from __future__ import annotations

import time
from collections.abc import Mapping
from pathlib import Path

from aec_bench.contracts.proposal_execution.graph import ProposalHandoff, SemanticSubtaskSpec
from aec_bench.contracts.proposal_execution.session import (
    ProposalHandoffArtifactRef,
    ProposalNodeReceipt,
    ProposalSessionExecutionRef,
)
from aec_bench.contracts.proposal_execution_types import ProposalNodeReceiptStatus
from aec_bench.experimentation.proposals.node_context import (
    PersistedProposalHandoffArtifact,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.session_evidence import (
    ProposalSessionEvidenceError,
    persist_proposal_container_transition,
    persist_proposal_handoffs,
    persist_proposal_node_evidence,
)
from aec_bench.harness.execution_payload import (
    write_execution_bundle,
)
from aec_bench.harness.kernel_catalogue import (
    KernelRuntimeRegistry,
)

from .child_evidence import (
    _check_node_contract,
    _load_child_evidence,
)
from .contracts import (
    ExecutedProposalNode,
    ProposalSessionEnvironment,
    ProposalSessionRuntimeError,
)
from .preparation import prepare_proposal_node_invocation
from .receipts import (
    _attempted_node_receipt,
    _node,
    _reservation,
    _runtime_error_from_evidence,
)
from .transport import (
    REMOTE_EXECUTION_RESULT,
    REMOTE_PROVIDER_BROKER_RECEIPT,
    REMOTE_TRAJECTORY,
    download_optional_output,
    download_required,
    execute_child,
    reset_candidate_container,
    upload_invocation,
)


async def execute_proposal_node(
    *,
    bundle: ProposalRunSessionBundle,
    execution: ProposalSessionExecutionRef,
    source_task_root: Path,
    session_root: Path,
    environment: ProposalSessionEnvironment,
    child_environment: Mapping[str, str] | None,
    registry: KernelRuntimeRegistry,
    node_id: str,
    invocation_id: str,
    producer_receipts: tuple[ProposalNodeReceipt, ...],
    incoming_handoffs: tuple[ProposalHandoff, ...],
    upstream_handoff_artifacts: tuple[
        PersistedProposalHandoffArtifact,
        ...,
    ],
) -> ExecutedProposalNode:
    invocation_root = session_root / "invocations" / invocation_id
    context_workspace = invocation_root / "context"
    prepared = prepare_proposal_node_invocation(
        bundle=bundle,
        source_task_root=source_task_root,
        session_id=execution.session_id,
        node_id=node_id,
        invocation_id=invocation_id,
        invocation_workspace=context_workspace,
        upstream_handoff_artifacts=upstream_handoff_artifacts,
        evaluation_coordinate=execution.evaluation_coordinate,
        registry=registry,
    )
    execution_bundle_path = invocation_root / "execution-bundle.json"
    provider_broker_policy_path = invocation_root / "provider-broker-policy.json"
    try:
        write_execution_bundle(
            path=execution_bundle_path,
            bundle=prepared.execution_bundle,
        )
        provider_broker_policy_path.write_text(
            prepared.provider_broker_policy.model_dump_json() + "\n",
            encoding="utf-8",
        )
    except (OSError, TypeError, ValueError) as error:
        raise ProposalSessionRuntimeError(
            "child_bundle_materialization_failed",
            f"proposal child execution bundle could not be written: {error}",
        ) from error

    transition = await reset_candidate_container(
        environment=environment,
        invocation_id=invocation_id,
        runtime_archive_sha256=(execution.runtime_archive_sha256),
    )
    try:
        persisted_transition = persist_proposal_container_transition(
            session_root=session_root,
            invocation_id=invocation_id,
            expected_runtime_archive_sha256=(execution.runtime_archive_sha256),
            transition=transition,
        )
    except ProposalSessionEvidenceError as error:
        raise _runtime_error_from_evidence(error) from error

    await upload_invocation(
        environment=environment,
        context_workspace=context_workspace,
        execution_bundle_path=execution_bundle_path,
        provider_broker_policy_path=(provider_broker_policy_path),
    )
    reservation = _reservation(
        bundle,
        node_id=node_id,
    )
    started_at = time.monotonic()
    child_result = await execute_child(
        environment=environment,
        timeout_seconds=reservation.max_runtime_seconds,
        child_environment=child_environment,
    )
    wall_seconds = time.monotonic() - started_at
    if child_result.return_code != 0:
        raise ProposalSessionRuntimeError(
            "child_entrypoint_failed",
            f"proposal child execution entrypoint returned {child_result.return_code}",
        )

    result_path = invocation_root / "agent-result.json"
    trajectory_path = invocation_root / "trajectory.jsonl"
    provider_broker_receipt_path = invocation_root / "provider-broker-receipt.json"
    output_path = invocation_root / "output.bin"
    await download_required(
        environment=environment,
        remote_path=REMOTE_EXECUTION_RESULT,
        local_path=result_path,
        label="child result",
    )
    await download_required(
        environment=environment,
        remote_path=REMOTE_TRAJECTORY,
        local_path=trajectory_path,
        label="child trajectory",
    )
    await download_required(
        environment=environment,
        remote_path=REMOTE_PROVIDER_BROKER_RECEIPT,
        local_path=provider_broker_receipt_path,
        label="provider broker receipt",
    )
    output_downloaded = await download_optional_output(
        environment=environment,
        remote_path=prepared.output_contract.output_path,
        local_path=output_path,
    )
    output_bytes = output_path.read_bytes() if output_downloaded else None
    result, runtime_attestation = _load_child_evidence(
        result_path=result_path,
        trajectory_path=trajectory_path,
        provider_broker_receipt_path=(provider_broker_receipt_path),
        prepared=prepared,
    )
    handoffs_by_id = {handoff.handoff_id: handoff for handoff in upstream_handoff_artifacts}
    contract_check = _check_node_contract(
        bundle=bundle,
        prepared=prepared,
        result=result,
        output_bytes=output_bytes,
        incoming_handoffs=incoming_handoffs,
        handoffs_by_id=handoffs_by_id,
        registry=registry,
    )
    try:
        persisted = persist_proposal_node_evidence(
            session_root=session_root,
            session_id=execution.session_id,
            node_id=node_id,
            invocation_id=invocation_id,
            execution_bundle=prepared.execution_bundle,
            result=result,
            runtime_attestation=runtime_attestation,
            output_bytes=output_bytes,
            structural_contract_satisfied=(contract_check.satisfied),
            contract_check_details=contract_check.details,
            node_contract_sha256=(prepared.node_contract_sha256),
            wall_seconds=wall_seconds,
        )
    except ProposalSessionEvidenceError as error:
        raise _runtime_error_from_evidence(error) from error

    emitted_handoffs: tuple[
        ProposalHandoffArtifactRef,
        ...,
    ] = ()
    stored_handoffs: tuple[
        PersistedProposalHandoffArtifact,
        ...,
    ] = ()
    if persisted.failure_code is None:
        node = _node(bundle, node_id=node_id)
        if isinstance(node, SemanticSubtaskSpec):
            try:
                persisted_handoffs = persist_proposal_handoffs(
                    session_root=session_root,
                    producer_node_id=node_id,
                    graph_handoffs=tuple(
                        handoff
                        for handoff in bundle.compilation.proposal_graph.handoffs
                        if (handoff.producer_node_id == node_id)
                    ),
                    canonical_handoffs=(contract_check.handoffs),
                )
            except ProposalSessionEvidenceError as error:
                raise _runtime_error_from_evidence(
                    error,
                ) from error
            emitted_handoffs = persisted_handoffs.receipt_refs
            stored_handoffs = persisted_handoffs.context_refs

    upstream_receipt_sha256s = tuple(sorted(receipt.content_sha256 for receipt in producer_receipts))
    node_receipt = _attempted_node_receipt(
        bundle=bundle,
        execution=execution,
        prepared=prepared,
        persisted=persisted,
        container_transition=persisted_transition,
        upstream_receipt_sha256s=(upstream_receipt_sha256s),
        emitted_handoffs=emitted_handoffs,
    )
    final_output_sha256: str | None = None
    final_commit_sha256: str | None = None
    if (
        node_id == bundle.compilation.proposal_graph.finalizer.node_id
        and node_receipt.status is ProposalNodeReceiptStatus.COMPLETED
    ):
        if result.completion_commit is None:
            raise ProposalSessionRuntimeError(
                "finalizer_commit_missing",
                "completed proposal finalizer lacks an output commit",
            )
        final_output_sha256 = persisted.output_artifact_sha256
        final_commit_sha256 = result.completion_commit.content_sha256
    return ExecutedProposalNode(
        receipt=node_receipt,
        handoffs=stored_handoffs,
        final_output_sha256=final_output_sha256,
        final_commit_sha256=final_commit_sha256,
    )
