# ABOUTME: Guards the stable critic-governance surface while lifecycle ownership is decomposed.
# ABOUTME: Proves public contracts and transactions retain exact identity through the legacy facade.

from __future__ import annotations

from aec_bench.meta_harness import critic_governance
from aec_bench.meta_harness.critic_lifecycle import contracts, release, retirement, reveal


def test_critic_governance_contract_facade_preserves_object_identity() -> None:
    public_contracts = (
        "CriticGenerationRetirement",
        "StoredCriticGenerationRetirement",
        "StoredAcceptanceManifestReveal",
        "AcceptanceAuditClosure",
    )

    for name in public_contracts:
        assert getattr(critic_governance, name) is getattr(contracts, name)


def test_critic_governance_transaction_facade_preserves_object_identity() -> None:
    owners = {
        "release_critic_generation": release,
        "release_acceptance_critic_generation": release,
        "assert_critic_generation_released": release,
        "prepare_critic_generation_retirement": retirement,
        "retire_critic_generation": retirement,
        "retire_acceptance_critic_generation": retirement,
        "load_critic_generation_retirement": retirement,
        "prepare_acceptance_manifest_reveal": reveal,
        "reveal_retired_acceptance_manifest": reveal,
        "load_acceptance_manifest_reveal": reveal,
        "assert_acceptance_audit_closed": reveal,
    }

    for name, owner in owners.items():
        assert getattr(critic_governance, name) is getattr(owner, name)
