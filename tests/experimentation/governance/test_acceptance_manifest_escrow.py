# ABOUTME: Tests durable host-owned storage for hidden acceptance cases and scoring policy.
# ABOUTME: Proves critic commitments reload exact escrow bytes and fail closed on drift or exposure.

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    CriticFeedbackVisibility,
    CriticRole,
    CriticSpec,
)
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.experimentation.governance.acceptance_manifest_escrow import (
    AcceptanceManifestEscrowCollisionError,
    AcceptanceManifestEscrowConfinementError,
    AcceptanceManifestEscrowIntegrityError,
    escrow_acceptance_manifest,
    load_acceptance_manifest_escrow,
)
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _ledger(tmp_path: Path) -> AuthorityLedger:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir(exist_ok=True)
    return AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
    )


def _material() -> tuple[dict[str, JsonValue], dict[str, JsonValue], str]:
    return (
        {"case_ids": ["hidden-01"], "split": "acceptance"},
        {"threshold": 0.8, "denominator": "all_planned_cases"},
        "retirement-escrow-salt",
    )


def _critic(
    *,
    receipt_sha256: str,
    cases: dict[str, JsonValue],
    scoring: dict[str, JsonValue],
    salt: str,
) -> CriticSpec:
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
        publication_receipt_sha256=receipt_sha256,
    )
    return CriticSpec(
        critic_id="critic.acceptance",
        version="2.0.0",
        role=CriticRole.ACCEPTANCE,
        implementation_sha256=_sha("implementation"),
        rubric_policy_sha256=canonical_content_sha256(scoring),
        case_manifest_sha256=canonical_content_sha256(cases),
        eligibility_policy_sha256=_sha("eligibility"),
        denominator_policy_sha256=_sha("denominator"),
        threshold_policy_sha256=_sha("threshold"),
        evidence_inclusion_policy_sha256=_sha("inclusion"),
        runtime_environment_sha256=_sha("runtime"),
        feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
        execution_principal_id="principal.acceptance-2.0.0",
        compatibility_generation="evaluation-generation-2",
        acceptance_manifest_commitment=commitment,
    )


def test_escrow_is_published_before_commitment_and_reloads_from_fresh_host_state(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()

    stored = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    critic = _critic(
        receipt_sha256=stored.publication_receipt.content_sha256,
        cases=cases,
        scoring=scoring,
        salt=salt,
    )

    reloaded_ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(tmp_path / "candidate",),
    )
    reloaded = load_acceptance_manifest_escrow(
        ledger=reloaded_ledger,
        critic_spec=critic,
    )

    assert reloaded == stored
    assert reloaded.payload.case_manifest == cases
    assert reloaded.payload.scoring_policy == scoring
    assert reloaded.payload.salt == salt
    assert reloaded.publication_receipt.payload_sha256 == reloaded.payload.content_sha256
    assert reloaded.publication_receipt.content_sha256 == (
        critic.acceptance_manifest_commitment.publication_receipt_sha256
    )
    assert os.stat(reloaded.payload_path).st_mode & 0o077 == 0
    assert os.stat(reloaded.publication_receipt_path).st_mode & 0o077 == 0


def test_escrow_preserves_v1_content_addresses_paths_and_canonical_bytes(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()

    stored = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )

    assert stored.payload.content_sha256 == ("9db65479f66e920bcb092f43b7aa6ff73ff1e649dd709547e822b3c86d98c0c7")
    assert stored.publication_receipt.content_sha256 == (
        "540a7e0c549eaaef6173f69d9e7c61a1577d38b57200b605a905f95e12baea19"
    )
    assert stored.payload_path.relative_to(ledger.root).as_posix() == (
        "acceptance-manifest-escrow/payloads/"
        "9db65479f66e920bcb092f43b7aa6ff73ff1e649dd709547e822b3c86d98c0c7/payload.json"
    )
    assert stored.publication_receipt_path.relative_to(ledger.root).as_posix() == (
        "acceptance-manifest-escrow/receipts/"
        "540a7e0c549eaaef6173f69d9e7c61a1577d38b57200b605a905f95e12baea19/receipt.json"
    )
    assert stored.claim_path.relative_to(ledger.root).as_posix() == (
        "acceptance-manifest-escrow/claims/83e53d174f555d91a8a0a3f16367440d038d565e885469eb9bc9068331b6197c/claim.json"
    )
    assert stored.payload_path.read_bytes() == (
        b'{"case_manifest":{"case_ids":["hidden-01"],"split":"acceptance"},'
        b'"content_sha256":"9db65479f66e920bcb092f43b7aa6ff73ff1e649dd709547e822b3c86d98c0c7",'
        b'"critic_id":"critic.acceptance","critic_version":"2.0.0",'
        b'"salt":"retirement-escrow-salt",'
        b'"schema_version":"aecbench.acceptance-manifest-escrow-payload.v1",'
        b'"scoring_policy":{"denominator":"all_planned_cases","threshold":0.8}}\n'
    )


def test_escrow_identity_is_idempotent_but_cannot_be_rebound(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    first = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )

    repeated = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    assert repeated == first

    with pytest.raises(
        AcceptanceManifestEscrowCollisionError,
        match="already bound",
    ):
        escrow_acceptance_manifest(
            ledger=ledger,
            critic_id="critic.acceptance",
            critic_version="2.0.0",
            case_manifest={
                "case_ids": ["changed-hidden-case"],
                "split": "acceptance",
            },
            scoring_policy=scoring,
            salt=salt,
        )


def test_escrow_load_rejects_a_commitment_for_unpublished_material(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    critic = _critic(
        receipt_sha256=_sha("invented-publication-receipt"),
        cases=cases,
        scoring=scoring,
        salt=salt,
    )

    with pytest.raises(
        AcceptanceManifestEscrowIntegrityError,
        match="not published",
    ):
        load_acceptance_manifest_escrow(
            ledger=ledger,
            critic_spec=critic,
        )


def test_escrow_load_rejects_tampered_or_overexposed_hidden_bytes(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    stored = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    critic = _critic(
        receipt_sha256=stored.publication_receipt.content_sha256,
        cases=cases,
        scoring=scoring,
        salt=salt,
    )

    stored.payload_path.chmod(0o644)
    with pytest.raises(
        AcceptanceManifestEscrowConfinementError,
        match="host-only permissions",
    ):
        load_acceptance_manifest_escrow(
            ledger=ledger,
            critic_spec=critic,
        )

    stored.payload_path.chmod(0o600)
    stored.payload_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        AcceptanceManifestEscrowIntegrityError,
        match="corrupt|canonical|hash",
    ):
        load_acceptance_manifest_escrow(
            ledger=ledger,
            critic_spec=critic,
        )


def test_escrow_load_rejects_internal_symlink_redirection(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    stored = escrow_acceptance_manifest(
        ledger=ledger,
        critic_id="critic.acceptance",
        critic_version="2.0.0",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    critic = _critic(
        receipt_sha256=stored.publication_receipt.content_sha256,
        cases=cases,
        scoring=scoring,
        salt=salt,
    )
    external = tmp_path / "external-secret.json"
    external.write_bytes(stored.payload_path.read_bytes())
    stored.payload_path.unlink()
    stored.payload_path.symlink_to(external)

    with pytest.raises(
        AcceptanceManifestEscrowConfinementError,
        match="symlink",
    ):
        load_acceptance_manifest_escrow(
            ledger=ledger,
            critic_spec=critic,
        )
