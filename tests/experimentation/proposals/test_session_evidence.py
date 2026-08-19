# ABOUTME: Tests fail-closed persistence of proposal-node adapter and runtime evidence.
# ABOUTME: Proves candidate failures remain distinct from host, provider, and integrity faults.

from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterResult,
    AdapterStopReason,
    SerializedAdapterExecution,
)
from aec_bench.contracts.adapter_execution import (
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.execution_program import ExecutionProgramRef
from aec_bench.contracts.harness_instance import HarnessInstanceRef
from aec_bench.contracts.harness_kernel import KernelRef, canonical_json_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionEvaluation,
    OutputCompletionReason,
)
from aec_bench.contracts.proposal_execution.graph import ProposalHandoff
from aec_bench.contracts.proposal_execution.session import ProposalContainerTransitionRef, ProposalNodeReceipt
from aec_bench.contracts.proposal_execution_types import (
    ProposalCandidateFailureCode,
    ProposalContractCheckStatus,
    ProposalNodeReceiptStatus,
)
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.experimentation.proposals.node_contract import CanonicalProposalHandoff
from aec_bench.experimentation.proposals.session_evidence import (
    PersistedProposalNodeEvidence,
    ProposalSessionEvidenceError,
    persist_proposal_container_transition,
    persist_proposal_handoffs,
    persist_proposal_node_evidence,
)
from aec_bench.harness.execution_payload import (
    AdapterRequestPayload,
    ExecutionBundle,
    RuntimeExecutionAttestation,
    execution_request_sha256,
    read_execution_result,
)

_OUTPUT = b'# Node output\n\n```json\n{"summary":"complete"}\n```\n'
_MODEL = "claude-sonnet-4-6"


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class _CandidateTransition:
    invocation_id: str
    previous_container_identity: str
    current_container_identity: str
    runtime_archive_sha256: str
    receipt_path: Path


def _context(
    *,
    session_id: str = "session.1",
    invocation_id: str = "invocation.analyse.1",
    node_id: str = "analyse",
) -> MetaHarnessTrajectoryContext:
    return MetaHarnessTrajectoryContext(
        kernel_ref=KernelRef(kernel_id="aec-bench.adaptive-harness", version="1.6.0"),
        harness_ref=HarnessInstanceRef(instance_id="harness.fixed"),
        program_ref=ExecutionProgramRef(program_id="program.proposal", version="1.0.0"),
        plan_run_id="bundle.1",
        program_node_id=node_id,
        proposal_session_id=session_id,
        proposal_invocation_id=invocation_id,
    )


def _bundle(context: MetaHarnessTrajectoryContext) -> ExecutionBundle:
    return ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind="tool_loop",
            adapter_name="entrypoint",
            resolved_model=_MODEL,
        ),
        request=AdapterRequestPayload(
            instruction="Analyse the public drainage evidence.",
            system_prompt="Return the declared node contract.",
            tools=[],
            configuration={
                "meta_harness_context": context.model_dump(mode="json"),
            },
            output_path="/workspace/output.md",
            output_format="markdown",
        ),
    )


def _runtime_attestation(
    bundle: ExecutionBundle,
    context: MetaHarnessTrajectoryContext,
) -> RuntimeExecutionAttestation:
    return RuntimeExecutionAttestation(
        adapter_kind=bundle.execution.adapter_kind,
        adapter_name=bundle.execution.adapter_name,
        requested_model=bundle.execution.resolved_model,
        resolved_model=bundle.execution.resolved_model,
        execution_request_sha256=execution_request_sha256(bundle),
        meta_harness_context=context,
    )


def _commit(output: bytes = _OUTPUT) -> OutputCommitAttestation:
    return OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path="/workspace/output.md",
        output_sha256=hashlib.sha256(output).hexdigest(),
        output_size_bytes=len(output),
        completion_contract_sha256=_sha("node-output-contract"),
        completion_evaluation=OutputCompletionEvaluation(
            complete=True,
            reason=OutputCompletionReason.COMPLETE,
            present_top_level_keys=("summary",),
            final_json_block_count=1,
        ),
        initial_output_sha256=None,
        commit_turn=3,
    )


def _completed_result() -> AdapterResult:
    commit = _commit()
    return AdapterResult(
        adapter_name="entrypoint",
        resolved_model=_MODEL,
        configuration_record={"max_turns": 8},
        agent_output=AgentOutput(
            status=AgentOutputStatus.COMPLETED,
            output_path=commit.output_path,
            output_format="markdown",
        ),
        transcript=[
            TranscriptEntry(
                role=TranscriptRole.USER,
                content="Analyse the public drainage evidence.",
            ),
            TranscriptEntry(
                role=TranscriptRole.ASSISTANT,
                content='{"query":"drainage"}',
                event=TranscriptEvent.TOOL_CALL,
                tool_name="search",
                tool_call_id="tool.1",
            ),
            TranscriptEntry(
                role=TranscriptRole.TOOL,
                content="evidence",
                event=TranscriptEvent.TOOL_RESULT,
                tool_name="search",
                tool_call_id="tool.1",
            ),
        ],
        completion_reason=AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED,
        completion_commit=commit,
        turns_used=3,
        max_turns=8,
        raw_output_text=_OUTPUT.decode("utf-8"),
        usage_input_tokens=1_000,
        usage_output_tokens=200,
        usage_cache_read_tokens=100,
        usage_cache_write_tokens=50,
        usage_advisor_calls=1,
        usage_advisor_input_tokens=50,
        usage_advisor_output_tokens=10,
    )


def _failed_result(
    failure_kind: AdapterFailureKind,
    *,
    stop_reason: AdapterStopReason | None = None,
) -> AdapterResult:
    return AdapterResult(
        adapter_name="entrypoint",
        resolved_model=_MODEL,
        configuration_record={"max_turns": 8},
        agent_output=AgentOutput(
            status=AgentOutputStatus.PARTIAL,
            output_path="/workspace/output.md",
            output_format="markdown",
            error_message=failure_kind.value,
        ),
        transcript=[],
        failure_kind=failure_kind,
        stop_reason=stop_reason,
        turns_used=8,
        max_turns=8,
        usage_input_tokens=1_000,
        usage_output_tokens=200,
        usage_cache_read_tokens=100,
        usage_cache_write_tokens=50,
    )


def _persist(
    root: Path,
    *,
    context: MetaHarnessTrajectoryContext | None = None,
    result: AdapterResult | None = None,
    attestation: RuntimeExecutionAttestation | None = None,
    output_bytes: bytes | None = _OUTPUT,
    structural_contract_satisfied: bool = True,
    contract_check_details: Mapping[str, JsonValue] | None = None,
) -> PersistedProposalNodeEvidence:
    resolved_context = context or _context()
    bundle = _bundle(resolved_context)
    return persist_proposal_node_evidence(
        session_root=root,
        session_id=resolved_context.proposal_session_id or "",
        node_id=resolved_context.program_node_id,
        invocation_id=resolved_context.proposal_invocation_id or "",
        execution_bundle=bundle,
        result=result or _completed_result(),
        runtime_attestation=attestation or _runtime_attestation(bundle, resolved_context),
        output_bytes=output_bytes,
        structural_contract_satisfied=structural_contract_satisfied,
        contract_check_details=contract_check_details or {"required_output_ids": ["summary"]},
        node_contract_sha256=_sha("contract"),
        wall_seconds=2.5,
    )


def test_persists_canonical_content_addressed_node_evidence(tmp_path: Path) -> None:
    result = _completed_result()
    stored = _persist(tmp_path, result=result)

    result_path = tmp_path / stored.execution_result.session_relative_path
    attestation_path = tmp_path / stored.runtime_attestation.session_relative_path
    check_path = tmp_path / stored.contract_check_result.session_relative_path
    for path in (result_path, attestation_path, check_path):
        assert stat.S_ISREG(path.stat().st_mode)
        encoded = path.read_bytes()
        assert encoded.endswith(b"\n")
        assert encoded == (
            json.dumps(
                json.loads(encoded),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
            + b"\n"
        )

    assert read_execution_result(result_path) == result
    assert (
        RuntimeExecutionAttestation.model_validate_json(attestation_path.read_text(encoding="utf-8")).content_sha256
        == stored.runtime_execution_attestation_sha256
    )
    assert hashlib.sha256(result_path.read_bytes()).hexdigest() == stored.execution_result.artifact_sha256
    assert hashlib.sha256(attestation_path.read_bytes()).hexdigest() == stored.runtime_attestation.artifact_sha256
    assert hashlib.sha256(check_path.read_bytes()).hexdigest() == stored.contract_check_result.artifact_sha256
    assert json.loads(check_path.read_text(encoding="utf-8"))["node_contract_sha256"] == _sha("contract")
    assert stored.contract_check_result.status is ProposalContractCheckStatus.PASSED
    assert stored.failure_code is None
    assert stored.output_artifact_sha256 == hashlib.sha256(_OUTPUT).hexdigest()
    assert stored.resources.wall_seconds == 2.5
    assert stored.resources.tokens_in == 1_050
    assert stored.resources.tokens_out == 210
    assert stored.resources.cache_read_tokens == 100
    assert stored.resources.cache_write_tokens == 50
    assert stored.resources.agent_turns == 3
    assert stored.resources.tool_calls == 1
    assert stored.resources.estimated_cost_usd is not None

    assert _persist(tmp_path, result=result) == stored


def test_distinct_invocations_use_distinct_session_relative_paths(
    tmp_path: Path,
) -> None:
    first = _persist(tmp_path)
    second = _persist(
        tmp_path,
        context=_context(invocation_id="invocation.analyse.2"),
    )

    assert first.execution_result.session_relative_path != second.execution_result.session_relative_path
    assert first.runtime_attestation.session_relative_path != second.runtime_attestation.session_relative_path
    assert first.contract_check_result.session_relative_path != second.contract_check_result.session_relative_path


@pytest.mark.parametrize(
    ("failure_kind", "stop_reason", "expected"),
    [
        (
            AdapterFailureKind.TURN_LIMIT_REACHED,
            AdapterStopReason.ITERATION_CAP,
            ProposalCandidateFailureCode.AGENT_TURN_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.TOKEN_BUDGET_REACHED,
            AdapterStopReason.TOKEN_BUDGET,
            ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.BILLABLE_INPUT_BUDGET_REACHED,
            AdapterStopReason.BILLABLE_INPUT_BUDGET,
            ProposalCandidateFailureCode.TOKEN_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.COST_BUDGET_REACHED,
            AdapterStopReason.COST_BUDGET,
            ProposalCandidateFailureCode.COST_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.SUBCALL_LIMIT_REACHED,
            AdapterStopReason.SUBCALL_LIMIT,
            ProposalCandidateFailureCode.TOOL_CALL_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.TOOL_CALL_LIMIT_REACHED,
            None,
            ProposalCandidateFailureCode.TOOL_CALL_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.CONTEXT_LIMIT_REACHED,
            AdapterStopReason.CONTEXT_LIMIT,
            ProposalCandidateFailureCode.CONTEXT_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.TIMEOUT,
            None,
            ProposalCandidateFailureCode.RUNTIME_BUDGET_EXHAUSTED,
        ),
        (
            AdapterFailureKind.MISSING_OUTPUT,
            None,
            ProposalCandidateFailureCode.OUTPUT_COMMIT_MISSING,
        ),
        (
            AdapterFailureKind.UNDECLARED_TOOL_REQUEST,
            None,
            ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED,
        ),
    ],
)
def test_classifies_only_closed_candidate_owned_adapter_outcomes(
    tmp_path: Path,
    failure_kind: AdapterFailureKind,
    stop_reason: AdapterStopReason | None,
    expected: ProposalCandidateFailureCode,
) -> None:
    stored = _persist(
        tmp_path,
        result=_failed_result(failure_kind, stop_reason=stop_reason),
        output_bytes=None,
    )

    assert stored.failure_code is expected
    assert stored.contract_check_result.status is ProposalContractCheckStatus.FAILED
    assert stored.contract_check_result.failure_code is expected
    assert stored.output_artifact_sha256 is None


@pytest.mark.parametrize(
    ("result", "expected_code"),
    [
        (
            _failed_result(AdapterFailureKind.PROVIDER_ERROR),
            "provider_execution_error",
        ),
        (
            replace(
                _failed_result(AdapterFailureKind.TOKEN_BUDGET_REACHED),
                provider_error="bedrock connection failed",
            ),
            "provider_execution_error",
        ),
        (
            _failed_result(AdapterFailureKind.TOOL_EXECUTION_FAILED),
            "host_execution_error",
        ),
    ],
)
def test_provider_and_host_faults_never_become_candidate_failures(
    tmp_path: Path,
    result: AdapterResult,
    expected_code: str,
) -> None:
    with pytest.raises(ProposalSessionEvidenceError) as exc_info:
        _persist(tmp_path, result=result, output_bytes=None)

    assert exc_info.value.code == expected_code
    assert not tmp_path.exists() or not tuple(tmp_path.rglob("*.json"))


def test_rejects_request_session_invocation_and_node_identity_mismatch(
    tmp_path: Path,
) -> None:
    context = _context()
    bundle = _bundle(context)
    attestation_payload = _runtime_attestation(bundle, context).model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    attestation_payload["execution_request_sha256"] = _sha("wrong-request")
    wrong_request = RuntimeExecutionAttestation.model_validate(attestation_payload)

    with pytest.raises(ProposalSessionEvidenceError) as request_error:
        _persist(tmp_path / "request", context=context, attestation=wrong_request)
    assert request_error.value.code == "execution_identity_mismatch"

    for field, value in (
        ("proposal_session_id", "session.other"),
        ("proposal_invocation_id", "invocation.other"),
        ("program_node_id", "other-node"),
    ):
        wrong_context_payload = context.model_dump(mode="json")
        wrong_context_payload[field] = value
        wrong_context = MetaHarnessTrajectoryContext.model_validate(wrong_context_payload)
        attestation_payload = _runtime_attestation(bundle, context).model_dump(
            mode="json",
            exclude={"content_sha256"},
        )
        attestation_payload["meta_harness_context"] = wrong_context.model_dump(mode="json")
        wrong_attestation = RuntimeExecutionAttestation.model_validate(attestation_payload)
        with pytest.raises(ProposalSessionEvidenceError) as identity_error:
            _persist(
                tmp_path / field,
                context=context,
                attestation=wrong_attestation,
            )
        assert identity_error.value.code == "execution_identity_mismatch"


def test_missing_child_metrics_and_false_output_commit_are_evidence_errors(
    tmp_path: Path,
) -> None:
    missing_metrics = replace(
        _failed_result(AdapterFailureKind.TOKEN_BUDGET_REACHED),
        turns_used=None,
        usage_input_tokens=None,
    )
    with pytest.raises(ProposalSessionEvidenceError) as missing_error:
        _persist(tmp_path / "missing", result=missing_metrics, output_bytes=None)
    assert missing_error.value.code == "child_evidence_missing"

    with pytest.raises(ProposalSessionEvidenceError) as integrity_error:
        _persist(tmp_path / "integrity", output_bytes=b"tampered output")
    assert integrity_error.value.code == "output_integrity_failure"


def test_missing_commit_is_candidate_owned_but_malformed_check_evidence_is_not(
    tmp_path: Path,
) -> None:
    uncommitted = replace(
        _completed_result(),
        completion_reason=None,
        completion_commit=None,
    )
    missing_commit = _persist(
        tmp_path / "missing-commit",
        result=uncommitted,
    )
    assert missing_commit.failure_code is ProposalCandidateFailureCode.OUTPUT_COMMIT_MISSING

    with pytest.raises(ProposalSessionEvidenceError) as malformed_error:
        _persist(
            tmp_path / "malformed",
            contract_check_details={"not_finite": float("nan")},
        )
    assert malformed_error.value.code == "child_evidence_malformed"


def test_persisted_evidence_builds_terminal_receipts_end_to_end(tmp_path: Path) -> None:
    completed = _persist(tmp_path / "completed")
    completed_receipt = _receipt(
        completed,
        status=ProposalNodeReceiptStatus.COMPLETED,
    )
    assert completed_receipt.status is ProposalNodeReceiptStatus.COMPLETED

    failed = _persist(
        tmp_path / "failed",
        structural_contract_satisfied=False,
    )
    failed_receipt = _receipt(
        failed,
        status=ProposalNodeReceiptStatus.CANDIDATE_FAILURE,
    )
    assert failed_receipt.failure_code is ProposalCandidateFailureCode.CONTRACT_CHECK_FAILED
    assert failed_receipt.contract_check_result is not None
    assert failed_receipt.contract_check_result.status is ProposalContractCheckStatus.FAILED


def test_content_address_collision_fails_closed_without_overwrite(tmp_path: Path) -> None:
    stored = _persist(tmp_path)
    result_path = tmp_path / stored.execution_result.session_relative_path
    result_path.write_bytes(b"corrupt")

    with pytest.raises(ProposalSessionEvidenceError) as exc_info:
        _persist(tmp_path)

    assert exc_info.value.code == "artifact_integrity_failure"
    assert result_path.read_bytes() == b"corrupt"


def test_session_relative_artifacts_reject_symlink_escape_before_writing(
    tmp_path: Path,
) -> None:
    session_root = tmp_path / "session"
    outside = tmp_path / "outside"
    session_root.mkdir()
    outside.mkdir()
    (session_root / "artifacts").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ProposalSessionEvidenceError) as exc_info:
        _persist(session_root)

    assert exc_info.value.code == "artifact_integrity_failure"
    assert not tuple(outside.iterdir())


def test_persists_exact_fresh_container_transition_and_rejects_identity_drift(
    tmp_path: Path,
) -> None:
    runtime_sha256 = _sha("proposal-runtime-archive")
    invocation_id = "invocation.analyse.1"
    transition_payload = {
        "schema_version": "aecbench.proposal-candidate-transition.v1",
        "status": "completed",
        "invocation_id": invocation_id,
        "runtime_archive_sha256": runtime_sha256,
        "previous_container_identity": "container.initial",
        "current_container_identity": "container.analyse",
        "previous_container_stopped": True,
        "workspace_wiped": True,
        "candidate_logs_wiped": True,
    }
    transition_payload["content_sha256"] = canonical_json_sha256(transition_payload)
    receipt_path = tmp_path / "boundary" / "transition.json"
    receipt_path.parent.mkdir()
    receipt_bytes = json.dumps(transition_payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    receipt_path.write_bytes(receipt_bytes)
    transition = _CandidateTransition(
        invocation_id=invocation_id,
        previous_container_identity="container.initial",
        current_container_identity="container.analyse",
        runtime_archive_sha256=runtime_sha256,
        receipt_path=receipt_path,
    )

    stored = persist_proposal_container_transition(
        session_root=tmp_path / "session",
        invocation_id=invocation_id,
        expected_runtime_archive_sha256=runtime_sha256,
        transition=transition,
    )

    assert stored.invocation_id == invocation_id
    assert stored.previous_container_identity == "container.initial"
    assert stored.current_container_identity == "container.analyse"
    assert stored.artifact_sha256 == hashlib.sha256(receipt_bytes).hexdigest()
    assert (tmp_path / "session" / stored.session_relative_path).read_bytes() == receipt_bytes

    with pytest.raises(ProposalSessionEvidenceError) as exc_info:
        persist_proposal_container_transition(
            session_root=tmp_path / "other-session",
            invocation_id=invocation_id,
            expected_runtime_archive_sha256=_sha("wrong-runtime"),
            transition=transition,
        )
    assert exc_info.value.code == "container_transition_identity_mismatch"


def test_persists_one_canonical_output_for_every_fanout_edge(
    tmp_path: Path,
) -> None:
    canonical_bytes = b'{"output_id":"findings","value":["A"]}\n'
    canonical = CanonicalProposalHandoff(
        output_id="findings",
        artifact_sha256=hashlib.sha256(canonical_bytes).hexdigest(),
        canonical_bytes=canonical_bytes,
    )
    edges = tuple(
        ProposalHandoff(
            handoff_id=f"handoff.findings.{consumer}",
            producer_node_id="analyse",
            producer_output_id="findings",
            consumer_node_id=consumer,
            consumer_input_id=f"input-{consumer}",
        )
        for consumer in ("assess-a", "assess-b")
    )

    persisted = persist_proposal_handoffs(
        session_root=tmp_path / "session",
        producer_node_id="analyse",
        graph_handoffs=edges,
        canonical_handoffs=(canonical,),
    )

    assert len(persisted.receipt_refs) == 2
    assert len(persisted.context_refs) == 2
    assert len({reference.session_relative_path for reference in persisted.receipt_refs}) == 1
    assert len({reference.artifact_sha256 for reference in persisted.receipt_refs}) == 1
    assert persisted.context_refs[0].artifact_path.read_bytes() == canonical_bytes

    with pytest.raises(ProposalSessionEvidenceError) as exc_info:
        persist_proposal_handoffs(
            session_root=tmp_path / "tampered",
            producer_node_id="analyse",
            graph_handoffs=edges,
            canonical_handoffs=(replace(canonical, artifact_sha256=_sha("tampered")),),
        )
    assert exc_info.value.code == "handoff_integrity_failure"


def _receipt(
    stored: PersistedProposalNodeEvidence,
    *,
    status: ProposalNodeReceiptStatus,
) -> ProposalNodeReceipt:
    return ProposalNodeReceipt(
        receipt_id=f"receipt.{status.value}",
        session_id=stored.session_id,
        session_execution_sha256=_sha("session-execution"),
        session_plan_sha256=_sha("session-plan"),
        compilation_sha256=_sha("compilation"),
        candidate_id="candidate.1",
        proposal_graph_sha256=_sha("proposal-graph"),
        problem_view_sha256=_sha("problem-view"),
        kernel_ref=KernelRef(kernel_id="aec-bench.adaptive-harness", version="1.6.0"),
        fixed_harness_ref=HarnessInstanceRef(instance_id="harness.fixed"),
        proposal_policy_sha256=_sha("proposal-policy"),
        node_id=stored.node_id,
        attempt=1,
        node_source_scope_sha256=_sha("source-scope"),
        node_budget_reservation_sha256=_sha("budget"),
        node_contract_sha256=stored.node_contract_sha256,
        status=status,
        invocation_id=stored.invocation_id,
        container_transition=ProposalContainerTransitionRef(
            invocation_id=stored.invocation_id,
            session_relative_path="artifacts/transitions/analyse.json",
            artifact_sha256=_sha("container-transition"),
            byte_size=384,
            media_type="application/json",
            previous_container_identity="container.initial",
            current_container_identity="container.analyse",
            runtime_archive_sha256=_sha("proposal-runtime-archive"),
            previous_container_stopped=True,
            workspace_wiped=True,
            candidate_logs_wiped=True,
        ),
        node_context_sha256=_sha("node-context"),
        execution_request_sha256=stored.execution_request_sha256,
        runtime_execution_attestation_sha256=stored.runtime_execution_attestation_sha256,
        execution_result=stored.execution_result,
        contract_check_result=stored.contract_check_result,
        output_artifact_sha256=stored.output_artifact_sha256,
        failure_code=stored.failure_code,
        resources=stored.resources,
        skip_cause=None,
    )
