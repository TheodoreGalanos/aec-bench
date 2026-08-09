# ABOUTME: Replays proposal imports through typed index, artifact, and authority stages.
# ABOUTME: Makes each validation boundary explicit while preserving fail-closed v1 errors.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.contracts.trial_record import Completeness, TrialRecord
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.experimentation.proposals.proposal_dispatch import (
    GovernedProposalDispatchAuthorization,
    ProposalDispatchGovernanceError,
    replay_governed_proposal_dispatch,
)
from aec_bench.experimentation.proposals.proposal_import_consumption import (
    ProposalImportConsumptionError,
    StoredProposalImportConsumptionClaim,
    StoredProposalImportTerminalRecord,
    claim_proposal_import_consumption,
    load_proposal_import_terminal,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.authority import (
    replay_scored_import_authority,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.contracts import (
    GovernedProposalTrialImport,
    ProposalTrialImportError,
    ProposalTrialImportReceipt,
)
from aec_bench.experimentation.proposals.proposal_trial_importing.persistence import (
    load_repository_bytes,
    load_repository_model,
    open_host_artifacts_repository,
    verify_artifact,
)
from aec_bench.ledger.immutable_artifact_store import EvidenceRepository


@dataclass(frozen=True)
class ScoredReplayIndex:
    """Exact first-writer claim and terminal selected for a scored replay."""

    consumption: StoredProposalImportConsumptionClaim
    terminal: StoredProposalImportTerminalRecord


@dataclass(frozen=True)
class ScoredReplayArtifacts:
    """Hash-checked scored artifacts loaded from the immutable repository."""

    repository: EvidenceRepository
    record: TrialRecord
    receipt: ProposalTrialImportReceipt


def replay_governed_proposal_trial_import(
    *,
    ledger: AuthorityLedger,
    authorization: GovernedProposalDispatchAuthorization,
    result: GovernedProposalTrialImport,
) -> GovernedProposalTrialImport:
    """Replay every persisted artifact, basis, origin, and event in a scored import."""
    try:
        replayed = replay_governed_proposal_dispatch(
            ledger=ledger,
            authorization=authorization,
        )
        index = _replay_scored_index(
            ledger=ledger,
            result=result,
        )
        artifacts = _replay_scored_artifacts(
            authorization=replayed,
            result=result,
            index=index,
        )
        replay_scored_import_authority(
            ledger=ledger,
            authorization=replayed,
            result=result,
            record=artifacts.record,
            receipt=artifacts.receipt,
            repository=artifacts.repository,
        )
    except ProposalTrialImportError:
        raise
    except (
        AuthorityLedgerError,
        OSError,
        ProposalImportConsumptionError,
        ProposalDispatchGovernanceError,
        ValueError,
    ) as error:
        raise ProposalTrialImportError(
            f"proposal TrialRecord import authority replay failed: {error}",
        ) from error
    return result


def _replay_scored_index(
    *,
    ledger: AuthorityLedger,
    result: GovernedProposalTrialImport,
) -> ScoredReplayIndex:
    consumption = claim_proposal_import_consumption(
        ledger_root=ledger.root,
        proposed=result.consumption_claim,
    )
    if consumption.claim != result.consumption_claim or consumption.path != result.consumption_claim_path:
        raise ProposalTrialImportError(
            "proposal import consumption claim differs from the finalized result",
        )
    terminal = load_proposal_import_terminal(
        ledger_root=ledger.root,
        execution_sha256=result.consumption_claim.harbor_execution_receipt_sha256,
    )
    if terminal is None or terminal.record != result.terminal_record or terminal.path != result.terminal_record_path:
        raise ProposalTrialImportError(
            "proposal import terminal index differs from the finalized result",
        )
    return ScoredReplayIndex(
        consumption=consumption,
        terminal=terminal,
    )


def _replay_scored_artifacts(
    *,
    authorization: GovernedProposalDispatchAuthorization,
    result: GovernedProposalTrialImport,
    index: ScoredReplayIndex,
) -> ScoredReplayArtifacts:
    repository = open_host_artifacts_repository(
        Path(index.consumption.claim.artifacts_root),
    )
    verify_artifact(
        result.record_artifact,
        repository=repository,
    )
    record = TrialRecord.model_validate_json(
        load_repository_bytes(
            repository=repository,
            path=result.record_path,
            label="persisted proposal TrialRecord",
        )
    )
    if record != result.record or record.completeness is not Completeness.COMPLETE:
        raise ProposalTrialImportError(
            "persisted proposal TrialRecord differs from the finalized record",
        )
    for artifact in record.outputs.artifacts or ():
        verify_artifact(
            artifact,
            repository=repository,
        )
    verify_artifact(
        result.import_receipt_artifact,
        repository=repository,
    )
    receipt = load_repository_model(
        repository=repository,
        path=result.import_receipt_path,
        model_type=ProposalTrialImportReceipt,
        label="persisted proposal import receipt",
    )
    if receipt != result.import_receipt:
        raise ProposalTrialImportError(
            "persisted proposal import receipt differs from the finalized receipt",
        )
    if (
        receipt.dispatch_sha256 != authorization.dispatch.content_sha256
        or receipt.trial_record != result.record_artifact
        or receipt.trial_id != record.trial_id
        or index.terminal.record.terminal_artifact != result.import_receipt_artifact
        or index.terminal.record.trial_record != result.record_artifact
    ):
        raise ProposalTrialImportError(
            "proposal import receipt differs from its dispatch or TrialRecord",
        )
    return ScoredReplayArtifacts(
        repository=repository,
        record=record,
        receipt=receipt,
    )
