# ABOUTME: Records and replays the exact causal authority chain for scored proposal imports.
# ABOUTME: Joins provider, execution, node, session, verifier, trial, and import evidence.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    OriginStamp,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import ContentAddressedModel
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.harness.harbor_importing.proposal_evidence import ProposalHarborImportEvidence
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    StoredBasis,
)
from aec_bench.meta_harness.immutable_artifact_store import EvidenceRepository
from aec_bench.meta_harness.proposal_dispatch_governance import (
    GovernedProposalDispatchAuthorization,
)
from aec_bench.meta_harness.proposal_harbor_runtime import (
    ProposalHarborExecutionReceipt,
)
from aec_bench.meta_harness.proposal_trial_importing.contracts import (
    GovernedProposalTrialImport,
    ProposalNodeImportAuthority,
    ProposalTrialImportAuthority,
    ProposalTrialImportError,
    ProposalTrialImportReceipt,
    ProposalVerifierEvidence,
)
from aec_bench.meta_harness.proposal_trial_importing.persistence import (
    canonical_model_bytes,
    load_repository_bytes,
    load_session_receipt_from_artifact,
    safe_segment,
)


def resolve_unique_event_model[ModelT: ContentAddressedModel](
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
    model_type: type[ModelT],
    expected_content_sha256: str,
    label: str,
) -> ModelT:
    """Resolve one canonical model from an authority event's evidence bases."""
    matches: list[ModelT] = []
    for reference in event.basis:
        if reference.kind is not BasisKind.EVIDENCE:
            continue
        stored = ledger.resolve_basis(reference)
        try:
            model = model_type.model_validate_json(
                stored.content_path.read_bytes(),
            )
        except ValueError:
            continue
        if (
            model.content_sha256 == expected_content_sha256
            and canonical_model_bytes(model) == stored.content_path.read_bytes()
        ):
            matches.append(model)
    if len(matches) != 1:
        raise ProposalTrialImportError(
            f"freeze authority has no unique canonical {label} basis",
        )
    return matches[0]


def basis_origin_sha256s(
    *,
    ledger: AuthorityLedger,
    event: AuthorityEvent,
) -> tuple[str, ...]:
    """Return the canonical origin identities behind one event's basis."""
    return tuple(
        sorted(ledger.resolve_basis(reference).origin.content_sha256 for reference in event.basis),
    )


def resolve_exact_basis(
    *,
    ledger: AuthorityLedger,
    expected: StoredBasis,
) -> StoredBasis:
    """Resolve a basis and reject any content or origin path drift."""
    observed = ledger.resolve_basis(expected.reference)
    if (
        observed.origin != expected.origin
        or observed.content_path != expected.content_path
        or observed.origin_path != expected.origin_path
    ):
        raise ProposalTrialImportError(
            f"authority basis drifted: {expected.reference.artifact_id}",
        )
    return observed


def require_exact_parents(
    origin: OriginStamp,
    expected: tuple[str, ...],
    *,
    label: str,
) -> None:
    """Require an origin to have exactly the declared causal parents."""
    if origin.parent_origin_sha256s != tuple(sorted(set(expected))):
        raise ProposalTrialImportError(
            f"{label} origin parentage drifted",
        )


def record_import_authority(
    *,
    repository: EvidenceRepository,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    execution_artifact: ArtifactReference,
    evidence: ProposalHarborImportEvidence,
    verifier_evidence: ProposalVerifierEvidence,
    record: TrialRecord,
    record_path: Path,
    import_receipt: ProposalTrialImportReceipt,
    import_receipt_path: Path,
    import_id: str,
    authority_event_id: str,
) -> ProposalTrialImportAuthority:
    """Persist the non-circular scored-import causal chain and authority event."""
    host_runtime = authorization.compile_event.principal
    if host_runtime.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
        raise ProposalTrialImportError(
            "proposal import requires the dispatch host-runtime principal",
        )
    scope = f"proposal-trial-import.{safe_segment(import_id)}"
    provider_parent_origins = basis_origin_sha256s(
        ledger=ledger,
        event=authorization.provider_dispatch_event,
    )
    provider_basis = ledger.observe_model_basis(
        kind=BasisKind.AUTHORITY_EVENT,
        artifact_id=f"{scope}.provider-dispatch-authority",
        model=authorization.provider_dispatch_event,
        producer=host_runtime,
        producer_process_id="aecbench.authority-ledger",
        observed_by=host_runtime,
        channel="proposal-trial-import",
        operation_id="proposal-import.observe-provider-dispatch",
        invocation_id=import_id,
        parent_origin_sha256s=provider_parent_origins,
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    execution_basis = ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"{scope}.harbor-execution-receipt",
        content=load_repository_bytes(
            repository=repository,
            path=Path(execution_artifact.path),
            label="proposal Harbor execution receipt",
        ),
        producer=host_runtime,
        producer_process_id="aecbench.proposal-harbor-runtime",
        observed_by=host_runtime,
        channel="proposal-trial-import",
        operation_id="proposal-import.observe-harbor-execution",
        invocation_id=import_id,
        parent_origin_sha256s=(provider_basis.origin.content_sha256,),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    node_by_sha256: dict[str, StoredBasis] = {}
    node_bindings: list[ProposalNodeImportAuthority] = []
    node_by_id = {node.node_id: node for node in evidence.session_receipt.node_receipts}
    model_principal = AuthorityPrincipal(
        principal_id=f"model.{record.agent.model}",
        kind=AuthorityPrincipalKind.MODEL,
    )
    for node_id in evidence.session_receipt.plan.topological_order:
        node = node_by_id[node_id]
        upstream_origins = tuple(
            node_by_sha256[digest].origin.content_sha256 for digest in node.upstream_receipt_sha256s
        )
        basis = ledger.observe_model_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{scope}.node-receipt.{safe_segment(node.node_id)}",
            model=node,
            producer=model_principal,
            producer_process_id=f"proposal-session.{evidence.session_id}",
            observed_by=host_runtime,
            channel="proposal-trial-import",
            operation_id="proposal-import.observe-node-receipt",
            invocation_id=import_id,
            parent_origin_sha256s=(
                execution_basis.origin.content_sha256,
                *upstream_origins,
            ),
            operation_taint=(
                TaintLabel.MODEL_REPORTED,
                TaintLabel.RUNTIME_OBSERVED,
            ),
        )
        node_by_sha256[node.content_sha256] = basis
        node_bindings.append(
            ProposalNodeImportAuthority(
                node_id=node.node_id,
                receipt_sha256=node.content_sha256,
                basis=basis,
            )
        )
    session_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"{scope}.session-receipt",
        model=evidence.session_receipt,
        producer=host_runtime,
        producer_process_id="aecbench.proposal-session",
        observed_by=host_runtime,
        channel="proposal-trial-import",
        operation_id="proposal-import.observe-session-receipt",
        invocation_id=import_id,
        parent_origin_sha256s=(
            execution_basis.origin.content_sha256,
            *(binding.basis.origin.content_sha256 for binding in node_bindings),
        ),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    verifier_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"{scope}.verifier-evidence",
        model=verifier_evidence,
        producer=AuthorityPrincipal(
            principal_id=f"task-verifier.{record.task.task_id}",
            kind=AuthorityPrincipalKind.TASK_AUTHORITY,
        ),
        producer_process_id=f"harbor-verifier.{record.trial_id}",
        observed_by=host_runtime,
        channel="proposal-trial-import",
        operation_id="proposal-import.observe-verifier-evidence",
        invocation_id=import_id,
        parent_origin_sha256s=(session_basis.origin.content_sha256,),
        operation_taint=(
            TaintLabel.RUNTIME_OBSERVED,
            TaintLabel.TASK_AUTHORITY,
        ),
    )
    trial_basis = ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"{scope}.trial-record",
        content=load_repository_bytes(
            repository=repository,
            path=record_path,
            label="proposal TrialRecord",
        ),
        producer=model_principal,
        producer_process_id=f"harbor-import.{record.trial_id}",
        observed_by=host_runtime,
        channel="proposal-trial-import",
        operation_id="proposal-import.observe-trial-record",
        invocation_id=import_id,
        parent_origin_sha256s=(
            session_basis.origin.content_sha256,
            verifier_basis.origin.content_sha256,
        ),
        operation_taint=(
            TaintLabel.MODEL_REPORTED,
            TaintLabel.RUNTIME_OBSERVED,
        ),
    )
    import_basis = ledger.observe_model_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id=f"{scope}.import-receipt",
        model=import_receipt,
        producer=host_runtime,
        producer_process_id="aecbench.proposal-trial-import",
        observed_by=host_runtime,
        channel="proposal-trial-import",
        operation_id="proposal-import.observe-import-receipt",
        invocation_id=import_id,
        parent_origin_sha256s=(
            execution_basis.origin.content_sha256,
            session_basis.origin.content_sha256,
            verifier_basis.origin.content_sha256,
        ),
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    event = AuthorityEvent(
        event_id=authority_event_id,
        principal=host_runtime,
        action=AuthorityAction.SCORED_EVIDENCE_IMPORT,
        decision=AuthorityDecision.GRANTED,
        subject_id=import_receipt.import_id,
        subject_sha256=import_receipt.content_sha256,
        basis=(
            trial_basis.reference,
            import_basis.reference,
        ),
        kernel_sha256=authorization.dispatch.bundle.fixed_harness.kernel_ref.content_sha256,
        reasons=("exact complete proposal TrialRecord and non-circular import receipt persisted",),
        revalidation_triggers=(
            "basis_replay_due",
            "evaluation_plan_change",
            "proposal_execution_evidence_change",
        ),
    )
    stored_event = ledger.issue_authority_event(event)
    return ProposalTrialImportAuthority(
        provider_dispatch_authority=provider_basis,
        execution_receipt=execution_basis,
        node_receipts=tuple(node_bindings),
        session_receipt=session_basis,
        verifier_evidence=verifier_basis,
        trial_record=trial_basis,
        import_receipt=import_basis,
        authority_event=stored_event,
    )


def replay_scored_import_authority(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    result: GovernedProposalTrialImport,
    record: TrialRecord,
    receipt: ProposalTrialImportReceipt,
    repository: EvidenceRepository,
) -> None:
    """Replay the scored import's basis graph and terminal authority binding."""
    authority = result.authority
    provider_basis = resolve_exact_basis(
        ledger=ledger,
        expected=authority.provider_dispatch_authority,
    )
    expected_provider_parents = basis_origin_sha256s(
        ledger=ledger,
        event=authorization.provider_dispatch_event,
    )
    require_exact_parents(
        provider_basis.origin,
        expected_provider_parents,
        label="provider dispatch authority",
    )
    execution_basis = resolve_exact_basis(
        ledger=ledger,
        expected=authority.execution_receipt,
    )
    require_exact_parents(
        execution_basis.origin,
        (provider_basis.origin.content_sha256,),
        label="proposal Harbor execution receipt",
    )
    node_by_sha256 = {
        binding.receipt_sha256: resolve_exact_basis(
            ledger=ledger,
            expected=binding.basis,
        )
        for binding in authority.node_receipts
    }
    proposal_session = record.meta_harness_provenance
    if proposal_session is None or proposal_session.proposal_session is None:
        raise ProposalTrialImportError(
            "replayed proposal TrialRecord lacks nested session provenance",
        )
    session_model = load_session_receipt_from_artifact(
        proposal_session.proposal_session.session_receipt,
        repository=repository,
    )
    for node in session_model.node_receipts:
        node_basis = node_by_sha256.get(node.content_sha256)
        if node_basis is None:
            raise ProposalTrialImportError(
                "proposal node authority does not cover every session receipt",
            )
        upstream_origins = tuple(
            node_by_sha256[digest].origin.content_sha256 for digest in node.upstream_receipt_sha256s
        )
        require_exact_parents(
            node_basis.origin,
            (
                execution_basis.origin.content_sha256,
                *upstream_origins,
            ),
            label=f"proposal node receipt {node.node_id}",
        )
    session_basis = resolve_exact_basis(
        ledger=ledger,
        expected=authority.session_receipt,
    )
    require_exact_parents(
        session_basis.origin,
        (
            execution_basis.origin.content_sha256,
            *(basis.origin.content_sha256 for basis in node_by_sha256.values()),
        ),
        label="proposal session receipt",
    )
    verifier_basis = resolve_exact_basis(
        ledger=ledger,
        expected=authority.verifier_evidence,
    )
    require_exact_parents(
        verifier_basis.origin,
        (session_basis.origin.content_sha256,),
        label="proposal verifier evidence",
    )
    trial_basis = resolve_exact_basis(
        ledger=ledger,
        expected=authority.trial_record,
    )
    require_exact_parents(
        trial_basis.origin,
        (
            session_basis.origin.content_sha256,
            verifier_basis.origin.content_sha256,
        ),
        label="proposal TrialRecord",
    )
    import_basis = resolve_exact_basis(
        ledger=ledger,
        expected=authority.import_receipt,
    )
    require_exact_parents(
        import_basis.origin,
        (
            execution_basis.origin.content_sha256,
            session_basis.origin.content_sha256,
            verifier_basis.origin.content_sha256,
        ),
        label="proposal import receipt",
    )
    stored_event = ledger.resolve_authority_event(
        event_id=authority.authority_event.event.event_id,
        content_sha256=authority.authority_event.event.content_sha256,
    )
    terminal = result.terminal_record
    if (
        stored_event.event != authority.authority_event.event
        or stored_event.event.action is not AuthorityAction.SCORED_EVIDENCE_IMPORT
        or stored_event.event.subject_id != receipt.import_id
        or stored_event.event.subject_sha256 != receipt.content_sha256
        or set(stored_event.event.basis) != {trial_basis.reference, import_basis.reference}
        or terminal.authority_event_id != stored_event.event.event_id
        or terminal.authority_event_sha256 != stored_event.event.content_sha256
    ):
        raise ProposalTrialImportError(
            "scored proposal import authority differs from its exact evidence",
        )
