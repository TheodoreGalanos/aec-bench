# ABOUTME: Persists hidden acceptance cases and scoring policy before their public critic commitment.
# ABOUTME: Keeps exact host-only escrow bytes under the governance owner for release and audit reveal.

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Never

from pydantic import JsonValue, TypeAdapter, field_validator

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    AcceptanceManifestRevealRule,
    CriticRole,
    CriticSpec,
)
from aec_bench.contracts.harness_kernel import (
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.ledger.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStoreError,
)


class AcceptanceManifestEscrowError(RuntimeError):
    """Base failure for hidden acceptance-manifest persistence."""


class AcceptanceManifestEscrowCollisionError(AcceptanceManifestEscrowError):
    """Raised when one critic generation is rebound to different hidden bytes."""


class AcceptanceManifestEscrowConfinementError(AcceptanceManifestEscrowError):
    """Raised when escrow bytes are redirected or are not host-only."""


class AcceptanceManifestEscrowIntegrityError(AcceptanceManifestEscrowError):
    """Raised when persisted escrow bytes do not verify against their commitment."""


class AcceptanceManifestEscrowPayload(LegacyContentAddressedModel):
    """Host-only recoverable material needed to reveal one retired acceptance critic."""

    schema_version: Literal["aecbench.acceptance-manifest-escrow-payload.v1"] = (
        "aecbench.acceptance-manifest-escrow-payload.v1"
    )
    critic_id: NonEmptyStr
    critic_version: NonEmptyStr
    case_manifest: JsonValue
    scoring_policy: JsonValue
    salt: NonEmptyStr


class AcceptanceManifestEscrowPublicationReceipt(LegacyContentAddressedModel):
    """Publicly safe proof identity for one durably published hidden payload."""

    schema_version: Literal["aecbench.acceptance-manifest-escrow-publication.v1"] = (
        "aecbench.acceptance-manifest-escrow-publication.v1"
    )
    critic_id: NonEmptyStr
    critic_version: NonEmptyStr
    payload_sha256: str
    reveal_rule: AcceptanceManifestRevealRule = AcceptanceManifestRevealRule.ON_GENERATION_RETIREMENT

    @field_validator("payload_sha256")
    @classmethod
    def validate_payload_hash(cls, value: str) -> str:
        return validate_sha256(value)


class _AcceptanceManifestEscrowClaim(LegacyContentAddressedModel):
    """Exclusive logical binding from one critic generation to its escrow receipt."""

    schema_version: Literal["aecbench.acceptance-manifest-escrow-claim.v1"] = (
        "aecbench.acceptance-manifest-escrow-claim.v1"
    )
    critic_id: NonEmptyStr
    critic_version: NonEmptyStr
    publication_receipt_sha256: str
    payload_sha256: str

    @field_validator(
        "publication_receipt_sha256",
        "payload_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


_PAYLOAD_ADAPTER = TypeAdapter(AcceptanceManifestEscrowPayload)
_PUBLICATION_RECEIPT_ADAPTER = TypeAdapter(AcceptanceManifestEscrowPublicationReceipt)
_CLAIM_ADAPTER = TypeAdapter(_AcceptanceManifestEscrowClaim)


@dataclass(frozen=True)
class StoredAcceptanceManifestEscrow:
    """Verified hidden payload, public receipt, and their immutable physical paths."""

    payload: AcceptanceManifestEscrowPayload
    publication_receipt: AcceptanceManifestEscrowPublicationReceipt
    payload_path: Path
    publication_receipt_path: Path
    claim_path: Path


def escrow_acceptance_manifest(
    *,
    ledger: AuthorityLedger,
    critic_id: str,
    critic_version: str,
    case_manifest: JsonValue,
    scoring_policy: JsonValue,
    salt: str,
) -> StoredAcceptanceManifestEscrow:
    """Durably publish hidden material before returning its public commitment receipt."""
    payload = AcceptanceManifestEscrowPayload(
        critic_id=critic_id,
        critic_version=critic_version,
        case_manifest=case_manifest,
        scoring_policy=scoring_policy,
        salt=salt,
    )
    receipt = AcceptanceManifestEscrowPublicationReceipt(
        critic_id=critic_id,
        critic_version=critic_version,
        payload_sha256=payload.content_sha256,
    )
    claim = _AcceptanceManifestEscrowClaim(
        critic_id=critic_id,
        critic_version=critic_version,
        publication_receipt_sha256=receipt.content_sha256,
        payload_sha256=payload.content_sha256,
    )
    repository = _prepare_escrow_repository(ledger)
    try:
        repository.publish_content_addressed_model(
            collection="payloads",
            filename="payload.json",
            model=payload,
            adapter=_PAYLOAD_ADAPTER,
        )
        repository.publish_content_addressed_model(
            collection="receipts",
            filename="receipt.json",
            model=receipt,
            adapter=_PUBLICATION_RECEIPT_ADAPTER,
        )
        try:
            repository.publish_logical_model(
                collection="claims",
                logical_identity=_claim_identity(critic_id, critic_version),
                filename="claim.json",
                model=claim,
                adapter=_CLAIM_ADAPTER,
            )
        except ImmutableArtifactCollisionError:
            raise AcceptanceManifestEscrowCollisionError(
                "acceptance critic generation is already bound to different escrow material"
            ) from None
    except ImmutableArtifactStoreError as error:
        _raise_escrow_store_error(error)

    return _load_claimed_escrow(
        repository=repository,
        critic_id=critic_id,
        critic_version=critic_version,
        expected_receipt_sha256=receipt.content_sha256,
    )


def load_acceptance_manifest_escrow(
    *,
    ledger: AuthorityLedger,
    critic_spec: CriticSpec,
) -> StoredAcceptanceManifestEscrow:
    """Reload and verify one critic's recoverable hidden material and public receipt."""
    selected = CriticSpec.model_validate(critic_spec.model_dump(mode="python"))
    commitment = selected.acceptance_manifest_commitment
    if selected.role is not CriticRole.ACCEPTANCE or commitment is None:
        raise AcceptanceManifestEscrowIntegrityError(
            "acceptance manifest escrow requires a committed acceptance critic"
        )
    repository = _existing_escrow_repository(ledger)
    stored = _load_claimed_escrow(
        repository=repository,
        critic_id=selected.critic_id,
        critic_version=selected.version,
        expected_receipt_sha256=commitment.publication_receipt_sha256,
    )
    expected_commitment = AcceptanceManifestCommitment.create(
        critic_id=selected.critic_id,
        critic_version=selected.version,
        case_manifest=stored.payload.case_manifest,
        scoring_policy=stored.payload.scoring_policy,
        salt=stored.payload.salt,
        publication_receipt_sha256=stored.publication_receipt.content_sha256,
    )
    if expected_commitment != commitment:
        raise AcceptanceManifestEscrowIntegrityError("persisted acceptance escrow does not match the critic commitment")
    if canonical_json_sha256(stored.payload.case_manifest) != selected.case_manifest_sha256:
        raise AcceptanceManifestEscrowIntegrityError(
            "persisted acceptance case manifest does not match the critic spec"
        )
    if canonical_json_sha256(stored.payload.scoring_policy) != selected.rubric_policy_sha256:
        raise AcceptanceManifestEscrowIntegrityError(
            "persisted acceptance scoring policy does not match the critic spec"
        )
    return stored


def _load_claimed_escrow(
    *,
    repository: EvidenceRepository,
    critic_id: str,
    critic_version: str,
    expected_receipt_sha256: str,
) -> StoredAcceptanceManifestEscrow:
    claim_identity = _claim_identity(critic_id, critic_version)
    claim_relative_path = repository.logical_model_path(
        collection="claims",
        logical_identity=claim_identity,
        filename="claim.json",
    )
    if not repository.exists(claim_relative_path):
        raise AcceptanceManifestEscrowIntegrityError(
            "acceptance manifest escrow was not published for this critic generation"
        )
    try:
        stored_claim = repository.load_logical_model(
            collection="claims",
            logical_identity=claim_identity,
            filename="claim.json",
            adapter=_CLAIM_ADAPTER,
        )
    except ImmutableArtifactStoreError as error:
        _raise_escrow_store_error(error)
    claim = stored_claim.model
    if (claim.critic_id, claim.critic_version) != (critic_id, critic_version):
        raise AcceptanceManifestEscrowIntegrityError("acceptance escrow claim does not match its critic generation")
    if claim.publication_receipt_sha256 != expected_receipt_sha256:
        raise AcceptanceManifestEscrowIntegrityError(
            "acceptance escrow publication receipt does not match the critic commitment"
        )
    try:
        stored_receipt = repository.load_content_addressed_model(
            collection="receipts",
            content_sha256=claim.publication_receipt_sha256,
            filename="receipt.json",
            adapter=_PUBLICATION_RECEIPT_ADAPTER,
        )
    except ImmutableArtifactStoreError as error:
        _raise_escrow_store_error(error)
    receipt = stored_receipt.model
    if (receipt.critic_id, receipt.critic_version) != (critic_id, critic_version):
        raise AcceptanceManifestEscrowIntegrityError(
            "acceptance escrow publication receipt does not match its critic generation"
        )
    if receipt.payload_sha256 != claim.payload_sha256:
        raise AcceptanceManifestEscrowIntegrityError(
            "acceptance escrow publication receipt does not match its hidden payload"
        )
    try:
        stored_payload = repository.load_content_addressed_model(
            collection="payloads",
            content_sha256=claim.payload_sha256,
            filename="payload.json",
            adapter=_PAYLOAD_ADAPTER,
        )
    except ImmutableArtifactStoreError as error:
        _raise_escrow_store_error(error)
    payload = stored_payload.model
    if (payload.critic_id, payload.critic_version) != (critic_id, critic_version):
        raise AcceptanceManifestEscrowIntegrityError("acceptance escrow payload does not match its critic generation")
    return StoredAcceptanceManifestEscrow(
        payload=payload,
        publication_receipt=receipt,
        payload_path=stored_payload.artifact.path,
        publication_receipt_path=stored_receipt.artifact.path,
        claim_path=stored_claim.artifact.path,
    )


def _prepare_escrow_repository(ledger: AuthorityLedger) -> EvidenceRepository:
    root = ledger.root / "acceptance-manifest-escrow"
    try:
        return EvidenceRepository(root, host_private=True)
    except ImmutableArtifactStoreError as error:
        _raise_escrow_store_error(error)


def _existing_escrow_repository(ledger: AuthorityLedger) -> EvidenceRepository:
    root = ledger.root / "acceptance-manifest-escrow"
    if not os.path.lexists(root):
        raise AcceptanceManifestEscrowIntegrityError(
            "acceptance manifest escrow was not published for this critic generation"
        )
    try:
        return EvidenceRepository(root, host_private=True)
    except ImmutableArtifactStoreError as error:
        _raise_escrow_store_error(error)


def _claim_identity(
    critic_id: str,
    critic_version: str,
) -> dict[str, JsonValue]:
    return {
        "critic_id": critic_id,
        "critic_version": critic_version,
    }


def _raise_escrow_store_error(error: ImmutableArtifactStoreError) -> Never:
    if isinstance(error, ImmutableArtifactCollisionError):
        raise AcceptanceManifestEscrowCollisionError(
            "acceptance escrow content-addressed path contains different bytes"
        ) from error
    if isinstance(error, ImmutableArtifactConfinementError):
        message = (
            str(error)
            .replace("symbolic-link", "symlink")
            .replace("symbolic link", "symlink")
            .replace("permissions are not host-private", "does not have host-only permissions")
        )
        raise AcceptanceManifestEscrowConfinementError(message) from error
    if isinstance(error, ImmutableArtifactIntegrityError):
        raise AcceptanceManifestEscrowIntegrityError(f"acceptance escrow artifact is corrupt: {error}") from error
    raise AcceptanceManifestEscrowError(str(error)) from error
