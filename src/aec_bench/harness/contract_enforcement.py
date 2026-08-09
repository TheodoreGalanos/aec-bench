# ABOUTME: Defines the closed harness-contract schemas that fixed kernel K can enforce truthfully.
# ABOUTME: Validates contract placement at compile time and imported trial evidence at runtime.

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aec_bench.contracts.harness_instance import (
    CompiledHarnessBinding,
    HarnessBindingKind,
    HarnessBindingSpec,
    HarnessContractEnforcement,
    HarnessContractKind,
    HarnessContractSpec,
)
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord

ContractValidator = Literal[
    "task_ref_set",
    "trial_record",
    "verified_trial_record",
    "candidate_manifest",
]


class HarnessContractError(ValueError):
    """Closed contract failure with a stable diagnostic code and causal subjects."""

    def __init__(self, code: str, message: str, *, subject_ids: tuple[str, ...] = ()) -> None:
        self.code = code
        self.subject_ids = tuple(sorted(set(subject_ids)))
        super().__init__(message)


@dataclass(frozen=True)
class HarnessContractRule:
    """Trusted enforcement mapping for one exact schema, role, and lifecycle point."""

    kind: HarnessContractKind
    enforcement: HarnessContractEnforcement
    binding_kinds: frozenset[HarnessBindingKind]
    validator: ContractValidator


TRUSTED_HARNESS_CONTRACTS: dict[str, HarnessContractRule] = {
    "aecbench://task-ref-set/v1": HarnessContractRule(
        kind=HarnessContractKind.INPUT,
        enforcement=HarnessContractEnforcement.COMPILE_TIME,
        binding_kinds=frozenset({HarnessBindingKind.TASK_SOURCE}),
        validator="task_ref_set",
    ),
    "aecbench://trial-record/v1": HarnessContractRule(
        kind=HarnessContractKind.OUTPUT,
        enforcement=HarnessContractEnforcement.RUNTIME,
        binding_kinds=frozenset({HarnessBindingKind.RESULT_IMPORT}),
        validator="trial_record",
    ),
    "aecbench://verified-trial-record/v1": HarnessContractRule(
        kind=HarnessContractKind.OUTPUT,
        enforcement=HarnessContractEnforcement.RUNTIME,
        binding_kinds=frozenset(
            {
                HarnessBindingKind.VERIFICATION,
                HarnessBindingKind.RESULT_IMPORT,
            }
        ),
        validator="verified_trial_record",
    ),
    "aecbench://candidate-manifest/v1": HarnessContractRule(
        kind=HarnessContractKind.INVARIANT,
        enforcement=HarnessContractEnforcement.RUNTIME,
        binding_kinds=frozenset({HarnessBindingKind.RESULT_IMPORT}),
        validator="candidate_manifest",
    ),
}


def validate_harness_contracts(
    *,
    contracts: tuple[HarnessContractSpec, ...],
    bindings: tuple[HarnessBindingSpec, ...] | tuple[CompiledHarnessBinding, ...],
) -> None:
    """Reject schemas or placements that have no trusted implementation in fixed K."""
    bindings_by_contract: dict[str, list[HarnessBindingSpec | CompiledHarnessBinding]] = {
        contract.contract_id: [] for contract in contracts
    }
    for binding in bindings:
        for contract_id in binding.contract_ids:
            bindings_by_contract[contract_id].append(binding)

    for contract in contracts:
        rule = TRUSTED_HARNESS_CONTRACTS.get(contract.schema_ref)
        if rule is None:
            raise HarnessContractError(
                "contract_schema_unsupported",
                f"fixed kernel has no trusted validator for contract schema {contract.schema_ref!r}",
                subject_ids=(contract.contract_id, contract.schema_ref),
            )
        if contract.kind is not rule.kind or contract.enforcement is not rule.enforcement:
            raise HarnessContractError(
                "contract_enforcement_mismatch",
                f"contract {contract.contract_id!r} does not match the trusted schema enforcement rule",
                subject_ids=(contract.contract_id, contract.schema_ref),
            )
        attached = bindings_by_contract[contract.contract_id]
        if not attached:
            raise HarnessContractError(
                "contract_not_attached",
                f"contract {contract.contract_id!r} is not attached to an execution-bearing binding",
                subject_ids=(contract.contract_id,),
            )
        unsupported = tuple(
            sorted(binding.binding_id for binding in attached if binding.configuration.kind not in rule.binding_kinds)
        )
        if unsupported:
            raise HarnessContractError(
                "contract_binding_unsupported",
                f"contract {contract.contract_id!r} is attached to unsupported binding roles",
                subject_ids=(contract.contract_id, *unsupported),
            )


def enforce_runtime_harness_contracts(
    *,
    contracts: tuple[HarnessContractSpec, ...],
    record: TrialRecord,
    candidate_manifest: ArtifactReference,
) -> None:
    """Apply every declared runtime validator to one imported TrialRecord."""
    for contract in contracts:
        rule = TRUSTED_HARNESS_CONTRACTS[contract.schema_ref]
        if rule.enforcement is not HarnessContractEnforcement.RUNTIME:
            continue
        if rule.validator == "trial_record":
            continue
        if rule.validator == "verified_trial_record":
            validity = record.evaluation.validity
            if not (validity.verifier_completed and validity.output_parseable and validity.schema_valid):
                raise HarnessContractError(
                    "verified_trial_contract_failed",
                    f"trial {record.trial_id!r} does not satisfy verified output validity",
                    subject_ids=(contract.contract_id, record.trial_id),
                )
            continue
        if rule.validator == "candidate_manifest":
            artifacts = record.outputs.artifacts or []
            if candidate_manifest not in artifacts:
                raise HarnessContractError(
                    "candidate_manifest_contract_failed",
                    f"trial {record.trial_id!r} is not bound to its candidate manifest",
                    subject_ids=(contract.contract_id, record.trial_id),
                )
            continue
        raise AssertionError(f"runtime contract validator is not implemented: {rule.validator}")
