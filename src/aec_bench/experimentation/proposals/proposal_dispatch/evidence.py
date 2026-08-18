# ABOUTME: Resolves proposal dispatch authority bases, evidence, and origin closure.
# ABOUTME: Rejects noncanonical evidence and exact-ledger drift during replay.

from __future__ import annotations

from aec_bench.contracts.authority import (
    AuthorityEvent,
    BasisReference,
    OriginStamp,
)
from aec_bench.contracts.harness_kernel import FrozenStrictModel
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
    StoredAuthorityEvent,
    StoredBasis,
)
from aec_bench.experimentation.proposals.proposal_dispatch.errors import (
    ProposalDispatchGovernanceError,
)
from aec_bench.experimentation.proposals.proposal_dispatch.serialization import (
    canonical_model_bytes,
)


def basis_origins(
    *,
    ledger: AuthorityLedger,
    references: tuple[BasisReference, ...],
) -> tuple[OriginStamp, ...]:
    """Resolve the exact origin for each ordered authority basis."""

    return tuple(ledger.resolve_basis(reference).origin for reference in references)


def origin_sha256s(origins: tuple[OriginStamp, ...]) -> tuple[str, ...]:
    """Return the canonical set of origin identities."""

    return tuple(
        sorted({origin.content_sha256 for origin in origins}),
    )


def resolve_event_basis(
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
    expected_origin: OriginStamp,
    expected_event: AuthorityEvent,
) -> tuple[StoredBasis, AuthorityEvent]:
    """Resolve one exact authority-event basis and its origin."""

    try:
        stored, event = ledger.resolve_model_basis(
            reference,
            AuthorityEvent,
        )
    except AuthorityLedgerError as error:
        raise ProposalDispatchGovernanceError(
            f"proposal authority event basis or origin closure cannot be replayed: {error}",
        ) from error
    if stored.origin != expected_origin or event != expected_event:
        raise ProposalDispatchGovernanceError(
            "proposal authority event basis or origin drifted",
        )
    return stored, event


def resolve_evidence_model[ModelT: FrozenStrictModel](
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
    expected_origin: OriginStamp,
    model_type: type[ModelT],
    label: str,
) -> tuple[StoredBasis, ModelT]:
    """Resolve and canonically reload one exact content-addressed evidence model."""

    stored = ledger.resolve_basis(reference)
    if stored.origin != expected_origin:
        raise ProposalDispatchGovernanceError(
            f"{label} origin drifted from the exact authorization",
        )
    try:
        encoded = stored.content_path.read_bytes()
        model = model_type.model_validate_json(encoded)
    except (OSError, ValueError) as error:
        raise ProposalDispatchGovernanceError(
            f"{label} evidence cannot be reloaded: {error}",
        ) from error
    if encoded != canonical_model_bytes(model):
        raise ProposalDispatchGovernanceError(
            f"{label} evidence is not canonically serialized",
        )
    return stored, model


def resolve_exact_event(
    *,
    ledger: AuthorityLedger,
    expected: AuthorityEvent,
    label: str,
) -> StoredAuthorityEvent:
    """Resolve one authority event by exact ID, digest, and model value."""

    try:
        stored = ledger.resolve_authority_event(
            event_id=expected.event_id,
            content_sha256=expected.content_sha256,
        )
    except AuthorityLedgerError as error:
        raise ProposalDispatchGovernanceError(
            f"{label} authority event drift prevents replay: {error}",
        ) from error
    if stored.event != expected:
        raise ProposalDispatchGovernanceError(
            f"{label} authority event drifted from its exact ledger record",
        )
    return stored


def assert_exact_origin_parents(
    *,
    origin: OriginStamp,
    expected: tuple[str, ...],
    label: str,
) -> None:
    """Reject incomplete or drifted parent-origin closure."""

    if origin.parent_origin_sha256s != expected:
        raise ProposalDispatchGovernanceError(
            f"{label} origin closure is incomplete or drifted",
        )
