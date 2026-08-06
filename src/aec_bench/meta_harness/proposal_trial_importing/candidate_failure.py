# ABOUTME: Preserves and replays terminal proposal candidate failures without scored authority.
# ABOUTME: Keeps failure-only evidence complete while forbidding TrialRecord and import claims.

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.harness.harbor_importing.proposal_evidence import (
    ProposalHarborImportEvidence,
    load_proposal_harbor_candidate_failure_evidence,
)
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.meta_harness.immutable_artifact_store import EvidenceRepository
from aec_bench.meta_harness.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
    replay_governed_proposal_dispatch,
)
from aec_bench.meta_harness.proposal_harbor_runtime import (
    ProposalHarborExecutionReceipt,
    load_proposal_harbor_execution,
)
from aec_bench.meta_harness.proposal_import_consumption import (
    ProposalImportConsumptionError,
    ProposalImportTerminalRecord,
    StoredProposalImportConsumptionClaim,
    StoredProposalImportTerminalRecord,
    claim_proposal_import_consumption,
    load_proposal_import_terminal,
)
from aec_bench.meta_harness.proposal_trial_importing.contracts import (
    GovernedProposalCandidateFailureImport,
    PersistedProposalArtifacts,
    ProposalCandidateFailureRecord,
    ProposalTrialImportError,
)
from aec_bench.meta_harness.proposal_trial_importing.persistence import (
    canonical_model_bytes,
    load_repository_bytes,
    merge_artifacts,
    object_root,
    open_host_artifacts_repository,
    persist_model_path,
    repository_reference,
    snapshot_evidence_artifacts,
    verify_artifact,
)
from aec_bench.meta_harness.proposal_trial_importing.validation import (
    validate_candidate_failure_artifacts,
    validate_candidate_failure_lineage,
    validate_exact_evidence,
)


class TerminalPersister(Protocol):
    """Callable boundary for publishing one immutable proposal terminal."""

    def __call__(
        self,
        *,
        ledger_root: Path,
        record: ProposalImportTerminalRecord,
    ) -> StoredProposalImportTerminalRecord: ...


def preserve_candidate_failure(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    execution_artifact: ArtifactReference,
    trial_dir: Path,
    repo_root: Path,
    repository: EvidenceRepository,
    artifacts_root: Path,
    persisted: PersistedProposalArtifacts,
    consumption: StoredProposalImportConsumptionClaim,
    receipt_path: Path,
    persist_terminal: TerminalPersister,
) -> GovernedProposalCandidateFailureImport:
    """Persist one candidate failure and replay it before returning."""
    import_id = consumption.claim.import_id
    evidence = load_proposal_harbor_candidate_failure_evidence(
        trial_dir=trial_dir,
        repo_root=repo_root,
    )
    if evidence is None:
        raise ProposalTrialImportError(
            "candidate-failure Harbor result has no proposal evidence",
        )
    validate_exact_evidence(
        authorization=authorization,
        evidence=evidence,
    )
    copied, _copied_by_identity = snapshot_evidence_artifacts(
        repository=repository,
        evidence=evidence,
        repo_root=repo_root,
        object_root=object_root(artifacts_root, authorization),
    )
    failure_record = ProposalCandidateFailureRecord(
        import_id=import_id,
        dispatch_id=authorization.dispatch.dispatch_id,
        dispatch_sha256=authorization.dispatch.content_sha256,
        harbor_execution_receipt_sha256=execution.content_sha256,
        candidate_id=evidence.candidate_id,
        candidate_artifact_sha256=evidence.candidate_artifact_sha256,
        proposal_graph_sha256=evidence.proposal_graph_sha256,
        compilation_sha256=evidence.compilation_sha256,
        session_plan_sha256=evidence.session_plan_sha256,
        session_receipt=evidence.session_receipt,
        artifacts=tuple(
            merge_artifacts(
                copied,
                list(persisted.all),
                [execution_artifact],
            )
        ),
    )
    path = persist_model_path(
        repository=repository,
        model=failure_record,
        filename="proposal-candidate-failure.json",
        object_root=object_root(artifacts_root, authorization),
    )
    artifact = repository_reference(
        repository=repository,
        kind="proposal-candidate-failure",
        path=path,
        media_type="application/json",
    )
    terminal = persist_terminal(
        ledger_root=ledger.root,
        record=ProposalImportTerminalRecord(
            harbor_execution_receipt_sha256=execution.content_sha256,
            dispatch_sha256=authorization.dispatch.content_sha256,
            import_id=import_id,
            outcome="candidate_failure",
            terminal_artifact=artifact,
        ),
    )
    result = GovernedProposalCandidateFailureImport(
        evidence=evidence,
        failure_record=failure_record,
        failure_record_path=path,
        failure_record_artifact=artifact,
        harbor_execution_receipt_path=receipt_path,
        consumption_claim=consumption.claim,
        consumption_claim_path=consumption.path,
        terminal_record=terminal.record,
        terminal_record_path=terminal.path,
    )
    return replay_governed_proposal_candidate_failure_import(
        ledger=AuthorityLedger(ledger.root),
        authorization=authorization,
        result=result,
    )


def replay_governed_proposal_candidate_failure_import(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    result: GovernedProposalCandidateFailureImport,
) -> GovernedProposalCandidateFailureImport:
    """Replay one terminal candidate failure without granting scored authority."""
    try:
        replayed = replay_governed_proposal_dispatch(
            ledger=ledger,
            authorization=authorization,
        )
        execution = load_proposal_harbor_execution(
            receipt_path=result.harbor_execution_receipt_path,
            ledger=ledger,
            authorization=replayed,
        )
        consumption = _replay_failure_consumption(
            ledger=ledger,
            authorization=replayed,
            execution=execution,
            result=result,
        )
        terminal = load_proposal_import_terminal(
            ledger_root=ledger.root,
            execution_sha256=execution.content_sha256,
        )
        if (
            terminal is None
            or terminal.record != result.terminal_record
            or terminal.path != result.terminal_record_path
        ):
            raise ProposalTrialImportError(
                "candidate-failure terminal index differs from the finalized result",
            )
        repository = open_host_artifacts_repository(
            Path(consumption.claim.artifacts_root),
        )
        failure_record = _load_exact_failure_record(
            repository=repository,
            result=result,
        )
        _validate_replayed_failure(
            ledger=ledger,
            authorization=replayed,
            execution=execution,
            evidence=result.evidence,
            failure_record=failure_record,
            result=result,
            repository=repository,
        )
    except ProposalTrialImportError:
        raise
    except (
        AuthorityLedgerError,
        OSError,
        ProposalImportConsumptionError,
        ProposalDispatchGovernanceError,
        RuntimeError,
        ValueError,
    ) as error:
        raise ProposalTrialImportError(
            f"proposal candidate-failure import replay failed: {error}",
        ) from error
    return result


def _replay_failure_consumption(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    result: GovernedProposalCandidateFailureImport,
) -> StoredProposalImportConsumptionClaim:
    consumption = claim_proposal_import_consumption(
        ledger_root=ledger.root,
        proposed=result.consumption_claim,
    )
    if (
        consumption.claim != result.consumption_claim
        or consumption.path != result.consumption_claim_path
        or consumption.claim.dispatch_sha256 != authorization.dispatch.content_sha256
        or consumption.claim.harbor_execution_receipt_sha256 != execution.content_sha256
    ):
        raise ProposalTrialImportError(
            "candidate-failure consumption claim differs from its exact execution",
        )
    return consumption


def _load_exact_failure_record(
    *,
    repository: EvidenceRepository,
    result: GovernedProposalCandidateFailureImport,
) -> ProposalCandidateFailureRecord:
    verify_artifact(
        result.failure_record_artifact,
        repository=repository,
    )
    failure_record_bytes = load_repository_bytes(
        repository=repository,
        path=result.failure_record_path,
        label="proposal candidate-failure record",
    )
    if result.failure_record_path.resolve(strict=False) != Path(result.failure_record_artifact.path).resolve(
        strict=False
    ):
        raise ProposalTrialImportError(
            "candidate-failure record path differs from its artifact",
        )
    failure_record = ProposalCandidateFailureRecord.model_validate_json(
        failure_record_bytes,
    )
    if failure_record != result.failure_record or canonical_model_bytes(failure_record) != failure_record_bytes:
        raise ProposalTrialImportError(
            "persisted candidate-failure record differs from the finalized record",
        )
    for artifact in failure_record.artifacts:
        verify_artifact(
            artifact,
            repository=repository,
        )
    return failure_record


def _validate_replayed_failure(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    execution: ProposalHarborExecutionReceipt,
    evidence: ProposalHarborImportEvidence,
    failure_record: ProposalCandidateFailureRecord,
    result: GovernedProposalCandidateFailureImport,
    repository: EvidenceRepository,
) -> None:
    validate_exact_evidence(
        authorization=authorization,
        evidence=evidence,
    )
    validate_candidate_failure_lineage(
        authorization=authorization,
        execution=execution,
        evidence=evidence,
        failure_record=failure_record,
        consumption=result.consumption_claim,
        terminal=result.terminal_record,
        terminal_artifact=result.failure_record_artifact,
    )
    validate_candidate_failure_artifacts(
        authorization=authorization,
        evidence=evidence,
        failure_record=failure_record,
        harbor_execution_receipt_path=result.harbor_execution_receipt_path,
        repository=repository,
    )
    if (
        ledger.authority_event_for_id(
            result.consumption_claim.requested_authority_event_id,
        )
        is not None
    ):
        raise ProposalTrialImportError(
            "candidate failure cannot claim scored authority",
        )
