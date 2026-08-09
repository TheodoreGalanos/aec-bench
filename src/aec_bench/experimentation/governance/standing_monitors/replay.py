# ABOUTME: Schedules and replays accepted authority-basis chains through the host ledger.
# ABOUTME: Binds replay evidence to canonical authority events, origins, and closure hashes.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
    StoredBasis,
)
from aec_bench.experimentation.governance.standing_monitors.models import (
    BasisReplayObservation,
    BasisReplayRequirement,
)


def schedule_basis_replay(
    *,
    ledger: AuthorityLedger,
    replay_id: str,
    authority_event_id: str,
    authority_event_sha256: str,
    due_cycle_index: int,
) -> BasisReplayRequirement:
    """Freeze a replay requirement from one currently valid stored authority basis chain."""
    stored = ledger.resolve_authority_event(
        event_id=authority_event_id,
        content_sha256=authority_event_sha256,
    )
    basis = ledger.validate_basis_closure(stored.event)
    return BasisReplayRequirement(
        replay_id=replay_id,
        authority_event_id=stored.event.event_id,
        authority_event_sha256=stored.event.content_sha256,
        basis_closure_sha256=_basis_closure_sha256(
            authority_event_sha256=stored.event.content_sha256,
            basis=basis,
        ),
        due_cycle_index=due_cycle_index,
    )


def replay_scheduled_basis(
    *,
    ledger: AuthorityLedger,
    requirement: BasisReplayRequirement,
) -> BasisReplayObservation:
    """Replay one scheduled authority chain through the real host-owned store."""
    selected = BasisReplayRequirement.model_validate(requirement.model_dump(mode="python"))
    try:
        stored = ledger.resolve_authority_event(
            event_id=selected.authority_event_id,
            content_sha256=selected.authority_event_sha256,
        )
        basis = ledger.validate_basis_closure(stored.event)
        observed_closure = _basis_closure_sha256(
            authority_event_sha256=stored.event.content_sha256,
            basis=basis,
        )
        return BasisReplayObservation(
            requirement_sha256=selected.content_sha256,
            replayed=True,
            closure_complete=observed_closure == selected.basis_closure_sha256,
            observed_basis_closure_sha256=observed_closure,
            evidence_sha256=canonical_content_sha256(
                {
                    "domain": "aecbench.basis-replay-evidence.v1",
                    "requirement_sha256": selected.content_sha256,
                    "authority_event_sha256": stored.event.content_sha256,
                    "basis_closure_sha256": observed_closure,
                }
            ),
        )
    except AuthorityLedgerError as error:
        return BasisReplayObservation(
            requirement_sha256=selected.content_sha256,
            replayed=True,
            closure_complete=False,
            evidence_sha256=canonical_content_sha256(
                {
                    "domain": "aecbench.basis-replay-failure.v1",
                    "requirement_sha256": selected.content_sha256,
                    "error_type": type(error).__name__,
                }
            ),
        )


def _basis_closure_sha256(
    *,
    authority_event_sha256: str,
    basis: tuple[StoredBasis, ...],
) -> str:
    return canonical_content_sha256(
        {
            "schema_version": "aecbench.authority-basis-closure.v1",
            "authority_event_sha256": authority_event_sha256,
            "basis": [
                {
                    "reference": item.reference.model_dump(mode="json"),
                    "origin_sha256": item.origin.content_sha256,
                }
                for item in basis
            ],
        }
    )
