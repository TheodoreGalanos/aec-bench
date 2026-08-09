# ABOUTME: Validates proposal child results, provider receipts, trajectories, and node contracts.
# ABOUTME: Converts malformed execution evidence into stable fail-closed runtime errors.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import JsonValue

from aec_bench.adapters.base import AdapterResult
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.proposal_execution.graph import ProposalHandoff, SemanticSubtaskSpec
from aec_bench.contracts.provider_broker import (
    ProviderBrokerCallPlane,
    ProviderBrokerPolicy,
    ProviderBrokerReceipt,
    ProviderBrokerStatus,
)
from aec_bench.contracts.trajectory import (
    MetaHarnessTrajectoryContext,
    TrajectoryEntry,
    read_trajectory,
)
from aec_bench.experimentation.proposals.node_context import (
    PersistedProposalHandoffArtifact,
)
from aec_bench.experimentation.proposals.node_contract import (
    ProposalNodeContractCheck,
    ProposalNodeContractError,
    check_finalizer_output,
    check_semantic_node_output,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.harness.execution_payload import (
    RuntimeExecutionAttestation,
    read_execution_result,
)
from aec_bench.harness.kernel_catalogue import (
    KernelOperationHandlerKey,
    KernelRuntimeRegistry,
)

from .contracts import (
    PreparedProposalNodeInvocation,
    ProposalSessionRuntimeError,
)
from .kernel import _operation_definition_for_proposal_runtime
from .receipts import _node


def _validate_provider_broker_call_budgets(
    *,
    policy: ProviderBrokerPolicy,
    receipt: ProviderBrokerReceipt,
) -> None:
    """Validate total and per-plane broker ceilings against durable call evidence."""

    if receipt.total_calls > policy.max_calls:
        raise ValueError(
            "provider broker receipt exceeds its call budget",
        )
    observed_main_calls = sum(call.call_plane is ProviderBrokerCallPlane.MAIN for call in receipt.calls) + sum(
        call.call_plane is ProviderBrokerCallPlane.MAIN for call in receipt.effect_unknown_calls
    )
    if observed_main_calls > policy.max_main_calls:
        raise ValueError(
            "provider broker receipt exceeds its main call budget",
        )
    observed_auxiliary_calls = sum(
        call.call_plane is ProviderBrokerCallPlane.AUXILIARY for call in receipt.calls
    ) + sum(call.call_plane is ProviderBrokerCallPlane.AUXILIARY for call in receipt.effect_unknown_calls)
    if observed_auxiliary_calls > policy.max_auxiliary_calls:
        raise ValueError(
            "provider broker receipt exceeds its auxiliary call budget",
        )


def _load_child_evidence(
    *,
    result_path: Path,
    trajectory_path: Path,
    provider_broker_receipt_path: Path,
    prepared: PreparedProposalNodeInvocation,
) -> tuple[AdapterResult, RuntimeExecutionAttestation]:
    try:
        result, attestation = _load_result_and_attestation(
            result_path=result_path,
        )
        receipt = ProviderBrokerReceipt.model_validate_json(
            provider_broker_receipt_path.read_text(encoding="utf-8"),
        )
        _validate_broker_binding(
            prepared=prepared,
            result=result,
            receipt=receipt,
        )
        _validate_completed_broker_usage(
            policy=prepared.provider_broker_policy,
            receipt=receipt,
            result=result,
        )
        entries = read_trajectory(trajectory_path)
        request_context = MetaHarnessTrajectoryContext.model_validate(
            prepared.execution_bundle.request.configuration["meta_harness_context"],
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise ProposalSessionRuntimeError(
            "child_evidence_malformed",
            f"proposal child evidence is malformed: {error}",
        ) from error
    _validate_trajectory_identity(
        entries=entries,
        request_context=request_context,
    )
    return result, attestation


def _load_result_and_attestation(
    *,
    result_path: Path,
) -> tuple[AdapterResult, RuntimeExecutionAttestation]:
    payload = json.loads(
        result_path.read_text(encoding="utf-8"),
    )
    if not isinstance(payload, dict):
        raise TypeError("child result must be a JSON object")
    attestation_payload = payload.get(
        "runtime_execution_attestation",
    )
    if not isinstance(attestation_payload, dict):
        raise TypeError("runtime execution attestation is missing")
    return (
        read_execution_result(result_path),
        RuntimeExecutionAttestation.model_validate(
            attestation_payload,
        ),
    )


def _validate_broker_binding(
    *,
    prepared: PreparedProposalNodeInvocation,
    result: AdapterResult,
    receipt: ProviderBrokerReceipt,
) -> None:
    broker_record = result.configuration_record["provider_broker"]
    if not isinstance(broker_record, dict):
        raise TypeError(
            "provider broker configuration evidence is malformed",
        )
    embedded_receipt = ProviderBrokerReceipt.model_validate(
        broker_record["receipt"],
    )
    if (
        broker_record.get("policy_sha256") != prepared.provider_broker_policy.content_sha256
        or receipt != embedded_receipt
        or receipt.policy_sha256 != prepared.provider_broker_policy.content_sha256
        or receipt.broker_id != prepared.provider_broker_policy.broker_id
    ):
        raise ValueError(
            "provider broker evidence does not bind the prepared policy",
        )
    _validate_provider_broker_call_budgets(
        policy=prepared.provider_broker_policy,
        receipt=receipt,
    )


def _validate_completed_broker_usage(
    *,
    policy: ProviderBrokerPolicy,
    receipt: ProviderBrokerReceipt,
    result: AdapterResult,
) -> None:
    if receipt.status is not ProviderBrokerStatus.COMPLETED:
        if result.agent_output.status is AgentOutputStatus.COMPLETED:
            raise ValueError(
                "completed adapter result cannot rely on a failed provider broker",
            )
        return
    observed_tokens = (
        receipt.total_input_tokens
        + receipt.total_output_tokens
        + receipt.total_cache_read_tokens
        + receipt.total_cache_write_tokens
    )
    if policy.max_total_tokens is not None and observed_tokens > policy.max_total_tokens:
        raise ValueError(
            "completed provider broker receipt exceeds its token budget",
        )
    if policy.max_cost_usd is not None and receipt.total_cost_usd > policy.max_cost_usd:
        raise ValueError(
            "completed provider broker receipt exceeds its cost budget",
        )
    if (
        receipt.total_input_tokens != (result.usage_input_tokens or 0)
        or receipt.total_output_tokens != (result.usage_output_tokens or 0)
        or receipt.total_cache_read_tokens != (result.usage_cache_read_tokens or 0)
        or receipt.total_cache_write_tokens != (result.usage_cache_write_tokens or 0)
    ):
        raise ValueError(
            "adapter usage differs from completed provider broker evidence",
        )


def _validate_trajectory_identity(
    *,
    entries: Sequence[TrajectoryEntry],
    request_context: MetaHarnessTrajectoryContext,
) -> None:
    runtime_entries = tuple(entry for entry in entries if entry.step > 0)
    if not runtime_entries or any(entry.meta_harness != request_context for entry in runtime_entries):
        raise ProposalSessionRuntimeError(
            "trajectory_identity_mismatch",
            "proposal child trajectory does not bind the exact node invocation",
        )


def _check_node_contract(
    *,
    bundle: ProposalRunSessionBundle,
    prepared: PreparedProposalNodeInvocation,
    result: AdapterResult,
    output_bytes: bytes | None,
    incoming_handoffs: tuple[ProposalHandoff, ...],
    handoffs_by_id: Mapping[
        str,
        PersistedProposalHandoffArtifact,
    ],
    registry: KernelRuntimeRegistry,
) -> ProposalNodeContractCheck:
    node = _node(bundle, node_id=prepared.node_id)
    if result.agent_output.status is not AgentOutputStatus.COMPLETED:
        return _closed_contract_miss(
            node_id=prepared.node_id,
            finding_code="adapter_not_completed",
        )
    operation_id = "check_subtask_contract.v1" if isinstance(node, SemanticSubtaskSpec) else "finalize_proposed_plan.v1"
    definition = _operation_definition_for_proposal_runtime(
        bundle=bundle,
        registry=registry,
        operation_id=operation_id,
    )
    handler_key = (
        definition.handler_key
        if definition is not None
        else (
            KernelOperationHandlerKey.CHECK_SUBTASK_CONTRACT
            if isinstance(node, SemanticSubtaskSpec)
            else KernelOperationHandlerKey.FINALIZE_PROPOSED_PLAN
        )
    )
    try:
        if handler_key is KernelOperationHandlerKey.CHECK_SUBTASK_CONTRACT:
            if not isinstance(node, SemanticSubtaskSpec):
                raise ProposalSessionRuntimeError(
                    "operation_handler_mismatch",
                    "semantic-subtask contract handler cannot execute a proposal finalizer",
                )
            if output_bytes is None:
                return _closed_contract_miss(
                    node_id=prepared.node_id,
                    finding_code="output_missing",
                )
            return check_semantic_node_output(
                node=node,
                output_contract=prepared.output_contract,
                raw_output_bytes=output_bytes,
                completion_commit=result.completion_commit,
                upstream_artifact_ids={
                    handoff.consumer_input_id: (handoffs_by_id[handoff.handoff_id].artifact_sha256)
                    for handoff in incoming_handoffs
                },
            )
        if handler_key is not KernelOperationHandlerKey.FINALIZE_PROPOSED_PLAN:
            raise ProposalSessionRuntimeError(
                "operation_handler_mismatch",
                f"proposal runtime cannot execute fixed-K handler {handler_key.value!r}",
            )
        if isinstance(node, SemanticSubtaskSpec):
            raise ProposalSessionRuntimeError(
                "operation_handler_mismatch",
                "proposal finalizer handler cannot execute a semantic subtask",
            )
        return check_finalizer_output(
            finalizer=node,
            output_contract=prepared.output_contract,
            raw_output_bytes=output_bytes,
            completion_commit=result.completion_commit,
        )
    except ProposalNodeContractError as error:
        raise ProposalSessionRuntimeError(
            error.code,
            f"proposal node contract check failed closed: {error}",
        ) from error


def _closed_contract_miss(
    *,
    node_id: str,
    finding_code: str,
) -> ProposalNodeContractCheck:
    details: dict[str, JsonValue] = {
        "schema_version": ("aecbench.proposal-node-runtime-contract-check.v1"),
        "check_kind": "runtime_outcome",
        "node_id": node_id,
        "satisfied": False,
        "finding_codes": [finding_code],
        "hidden_verifier_used": False,
    }
    encoded = (
        json.dumps(
            details,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )
    return ProposalNodeContractCheck(
        satisfied=False,
        details=details,
        canonical_details_bytes=encoded,
    )
