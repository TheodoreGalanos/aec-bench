# ABOUTME: Tests the closed schema registry that makes Hx contracts executable rather than decorative.
# ABOUTME: Covers trusted binding placement and verified-trial runtime checks.

from __future__ import annotations

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.harness_instance import (
    HarnessBindingSpec,
    HarnessContractEnforcement,
    HarnessContractKind,
    HarnessContractSpec,
    HarnessTopologyRole,
    ResultImportBindingConfig,
)
from aec_bench.contracts.harness_kernel import KernelCapabilityKind, KernelCapabilitySpec
from aec_bench.harness.contract_enforcement import (
    HarnessContractError,
    enforce_runtime_harness_contracts,
    validate_harness_contracts,
)
from tests.support.trial_record_factories import make_trial_record


def _contract(schema_ref: str, *, contract_id: str) -> HarnessContractSpec:
    return HarnessContractSpec(
        contract_id=contract_id,
        kind=HarnessContractKind.OUTPUT,
        schema_ref=schema_ref,
        enforcement=HarnessContractEnforcement.RUNTIME,
        summary=f"Enforce {schema_ref}.",
    )


def _import_binding(*contract_ids: str) -> HarnessBindingSpec:
    capability = KernelCapabilitySpec(
        capability_id="aecbench.results.trial-record",
        version="1.0.0",
        kind=KernelCapabilityKind.RESULT_IMPORTER,
        summary="Import validated trial records.",
    )
    return HarnessBindingSpec(
        binding_id="import",
        capability_ref=capability.ref,
        topology_role=HarnessTopologyRole.SINK,
        contract_ids=contract_ids,
        configuration=ResultImportBindingConfig(ledger_namespace="contract-tests"),
    )


def test_trusted_runtime_contract_must_be_attached_to_supported_binding_role() -> None:
    contract = _contract("aecbench://verified-trial-record/v1", contract_id="verified")

    validate_harness_contracts(
        contracts=(contract,),
        bindings=(_import_binding(contract.contract_id),),
    )
    with pytest.raises(HarnessContractError) as captured:
        validate_harness_contracts(contracts=(contract,), bindings=(_import_binding(),))
    assert captured.value.code == "contract_not_attached"


def test_verified_trial_contract_rejects_incomplete_verifier_evidence() -> None:
    contract = _contract("aecbench://verified-trial-record/v1", contract_id="verified")
    invalid = make_trial_record(
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=False,
            ),
        )
    )

    with pytest.raises(HarnessContractError) as captured:
        enforce_runtime_harness_contracts(
            contracts=(contract,),
            record=invalid,
        )

    assert captured.value.code == "verified_trial_contract_failed"


def test_verified_trial_contract_rejects_missing_evaluation_evidence() -> None:
    contract = _contract("aecbench://verified-trial-record/v1", contract_id="verified")
    invalid = make_trial_record(evaluation=None)

    with pytest.raises(HarnessContractError) as captured:
        enforce_runtime_harness_contracts(
            contracts=(contract,),
            record=invalid,
        )

    assert captured.value.code == "verified_trial_contract_failed"
