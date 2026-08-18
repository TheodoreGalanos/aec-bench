# ABOUTME: Tests durable host-owned storage for hidden acceptance cases and scoring policy.
# ABOUTME: Proves critic commitments reload exact escrow bytes and fail closed on drift or exposure.

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.contracts.evaluation_plane import (
    AcceptanceManifestCommitment,
    Critic,
    CriticFeedbackVisibility,
    RepositoryCriticSource,
)
from aec_bench.contracts.evaluation_refs import CriticRole
from aec_bench.experimentation.governance.acceptance_manifest_escrow import (
    AcceptanceManifestEscrowCollisionError,
    AcceptanceManifestEscrowConfinementError,
    AcceptanceManifestEscrowIntegrityError,
    escrow_acceptance_manifest,
    load_acceptance_manifest_escrow,
)
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from tests.support.evaluation_regimes import fake_regime_ref


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
    cases: dict[str, JsonValue],
    scoring: dict[str, JsonValue],
    salt: str,
) -> Critic:
    commitment = AcceptanceManifestCommitment.create(
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    return Critic(
        critic_id="critic.acceptance",
        role=CriticRole.ACCEPTANCE,
        source=RepositoryCriticSource(
            source_revision="1" * 40,
            entrypoint="aec_bench.evaluation.acceptance:run",
        ),
        configuration={"runtime_mode": "host_only"},
        feedback_visibility=CriticFeedbackVisibility.HOST_ONLY,
        execution_principal_id="principal.acceptance-2.0.0",
        acceptance_manifest_commitment=commitment,
    )


def test_escrow_is_published_before_commitment_and_reloads_from_fresh_host_state(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    regime_ref = fake_regime_ref()

    stored = escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    critic = _critic(
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
        evaluation_regime=regime_ref,
        critic=critic,
    )

    assert reloaded == stored
    assert reloaded.payload.case_manifest == cases
    assert reloaded.payload.scoring_policy == scoring
    assert reloaded.payload.salt == salt
    assert reloaded.publication_receipt.payload_sha256 == reloaded.payload.content_sha256
    assert reloaded.publication_receipt.evaluation_regime == regime_ref
    assert os.stat(reloaded.payload_path).st_mode & 0o077 == 0
    assert os.stat(reloaded.publication_receipt_path).st_mode & 0o077 == 0


def test_escrow_uses_content_addressed_paths_and_canonical_bytes(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    regime_ref = fake_regime_ref()

    stored = escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )

    assert stored.payload_path.parent.name == stored.payload.content_sha256
    assert stored.publication_receipt_path.parent.name == stored.publication_receipt.content_sha256
    payload = json.loads(stored.payload_path.read_bytes())
    assert payload == stored.payload.model_dump(mode="json")
    assert payload["evaluation_regime"] == regime_ref.model_dump(mode="json")


def test_escrow_identity_is_idempotent_but_cannot_be_rebound(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    regime_ref = fake_regime_ref()
    first = escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )

    repeated = escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id="critic.acceptance",
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
            evaluation_regime=regime_ref,
            critic_id="critic.acceptance",
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
    regime_ref = fake_regime_ref()
    critic = _critic(
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
            evaluation_regime=regime_ref,
            critic=critic,
        )


def test_escrow_load_rejects_tampered_or_overexposed_hidden_bytes(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    regime_ref = fake_regime_ref()
    stored = escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    critic = _critic(
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
            evaluation_regime=regime_ref,
            critic=critic,
        )

    stored.payload_path.chmod(0o600)
    stored.payload_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(
        AcceptanceManifestEscrowIntegrityError,
        match="corrupt|canonical|hash",
    ):
        load_acceptance_manifest_escrow(
            ledger=ledger,
            evaluation_regime=regime_ref,
            critic=critic,
        )


def test_escrow_load_rejects_internal_symlink_redirection(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    cases, scoring, salt = _material()
    regime_ref = fake_regime_ref()
    stored = escrow_acceptance_manifest(
        ledger=ledger,
        evaluation_regime=regime_ref,
        critic_id="critic.acceptance",
        case_manifest=cases,
        scoring_policy=scoring,
        salt=salt,
    )
    critic = _critic(
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
            evaluation_regime=regime_ref,
            critic=critic,
        )
