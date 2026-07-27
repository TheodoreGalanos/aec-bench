# ABOUTME: Revalidates governed proposal-freeze authority and complete ledger basis closure.
# ABOUTME: Fails closed when the exact freeze, event, replay, or calibration lifecycle drifts.

from __future__ import annotations

from aec_bench.contracts.program_proposal import ProposalFreeze
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
    StoredAuthorityEvent,
)
from aec_bench.meta_harness.monitors import replay_scheduled_basis
from aec_bench.meta_harness.proposal_freezing.contracts import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
)
from aec_bench.meta_harness.proposal_freezing.validation import (
    ProposalFreezeLifecyclePolicy,
    assert_calibration_freeze_active,
)


def assert_proposal_freeze_authority(
    *,
    ledger: AuthorityLedger,
    result: GovernedProposalFreezeResult,
    freeze: ProposalFreeze | None = None,
    lifecycle_policy: ProposalFreezeLifecyclePolicy | None = None,
) -> StoredAuthorityEvent:
    """Fail closed unless the exact freeze event and complete basis still resolve."""

    try:
        validated = GovernedProposalFreezeResult.model_validate(
            result.model_dump(mode="python"),
        )
        selected_freeze = (
            validated.freeze
            if freeze is None
            else ProposalFreeze.model_validate(
                freeze.model_dump(mode="python"),
            )
        )
    except ValueError as error:
        raise GovernedProposalFreezeError(
            f"proposal freeze authority contract is invalid: {error}",
        ) from error
    if selected_freeze != validated.freeze:
        raise GovernedProposalFreezeError(
            "proposal freeze authority does not authorize the exact proposal freeze",
        )
    try:
        stored = ledger.resolve_authority_event(
            event_id=validated.authority_event.event_id,
            content_sha256=validated.authority_event.content_sha256,
        )
        if stored.event != validated.authority_event:
            raise GovernedProposalFreezeError(
                "stored proposal freeze authority differs from the supplied event",
            )
        if stored.event.basis != validated.basis.references:
            raise GovernedProposalFreezeError(
                "stored proposal freeze authority basis is incomplete",
            )
        for reference in validated.basis.references:
            ledger.resolve_basis(reference)
        current_replay = replay_scheduled_basis(
            ledger=ledger,
            requirement=validated.replay_requirement,
        )
        if (
            not current_replay.closure_complete
            or current_replay.observed_basis_closure_sha256 != validated.replay_requirement.basis_closure_sha256
        ):
            raise GovernedProposalFreezeError(
                "proposal freeze basis is no longer complete",
            )
        assert_calibration_freeze_active(
            ledger=ledger,
            result=validated,
            lifecycle_policy=lifecycle_policy,
        )
        return stored
    except AuthorityLedgerError as error:
        raise GovernedProposalFreezeError(
            f"proposal freeze basis cannot be resolved: {error}",
        ) from error
