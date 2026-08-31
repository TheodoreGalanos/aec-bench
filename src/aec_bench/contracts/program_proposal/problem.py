# ABOUTME: Defines reward-blind public problem views and their leakage-audit contracts.
# ABOUTME: Keeps proposer-visible task material separate from privileged evaluation state.

from __future__ import annotations

import re
from typing import Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelRef,
    validate_sha256,
)
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.program_proposal._canonical import (
    canonical_unique_models,
    canonical_unique_strings,
)
from aec_bench.contracts.validators import NonEmptyStr


class PublicSourceRef(ContentAddressedModel):
    """Path-free public source identity exposed through an opaque proposer handle."""

    schema_version: Literal["aecbench.public-source-ref.v1"] = "aecbench.public-source-ref.v1"
    source_id: NonEmptyStr
    opaque_handle: NonEmptyStr
    media_type: NonEmptyStr
    byte_size: int = Field(ge=0)
    source_sha256: str

    @field_validator("source_sha256")
    @classmethod
    def validate_source_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("opaque_handle")
    @classmethod
    def validate_opaque_handle(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if "/" in normalized or normalized.startswith("file:") or ".." in normalized:
            raise ValueError("public source handle must be opaque and path-free")
        return value


class PublicDataGapBoundary(FrozenStrictModel):
    """Public instruction for handling one known absence without inventing data."""

    boundary_id: NonEmptyStr
    statement: NonEmptyStr


class PublicAuthorityBoundary(FrozenStrictModel):
    """Public statement of an action the candidate may not authorize."""

    boundary_id: NonEmptyStr
    statement: NonEmptyStr


class FixedHarnessCapabilityProjection(ContentAddressedModel):
    """Safe H0 projection containing identities, allowlisted capabilities, and one budget."""

    schema_version: Literal["aecbench.fixed-harness-capability-projection.v1"] = (
        "aecbench.fixed-harness-capability-projection.v1"
    )
    kernel_ref: KernelRef
    harness_policy_sha256: str
    capability_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    aggregate_budget: HarnessBudget

    @field_validator(
        "harness_policy_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("capability_ids")
    @classmethod
    def canonicalize_capability_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="capability ids")


class DecompositionProblemView(ContentAddressedModel):
    """Reward-blind public task surface from which a proposer may create a program."""

    schema_version: Literal["aecbench.decomposition-problem-view.v2"] = "aecbench.decomposition-problem-view.v2"
    problem_id: NonEmptyStr
    task_id: NonEmptyStr
    task_revision: NonEmptyStr
    public_instruction: NonEmptyStr
    public_sources: tuple[PublicSourceRef, ...] = Field(min_length=1)
    output_contract: OutputCompletionContract
    fixed_harness: FixedHarnessCapabilityProjection
    public_domain_id: NonEmptyStr
    public_task_family_id: NonEmptyStr
    data_gap_boundaries: tuple[PublicDataGapBoundary, ...] = ()
    authority_boundaries: tuple[PublicAuthorityBoundary, ...] = ()

    @model_validator(mode="before")
    @classmethod
    def reject_recursive_privileged_leakage(cls, value: Any) -> Any:
        leaking_key = _find_privileged_key(value)
        if leaking_key is not None:
            raise ValueError(f"decomposition problem view rejects privileged leakage key {leaking_key!r}")
        return value

    @field_validator("task_revision")
    @classmethod
    def validate_task_snapshot_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("public_sources")
    @classmethod
    def canonicalize_sources(
        cls,
        value: tuple[PublicSourceRef, ...],
    ) -> tuple[PublicSourceRef, ...]:
        return canonical_unique_models(value, identity="source_id", label="public sources")

    @field_validator("data_gap_boundaries")
    @classmethod
    def canonicalize_data_gap_boundaries(
        cls,
        value: tuple[PublicDataGapBoundary, ...],
    ) -> tuple[PublicDataGapBoundary, ...]:
        return canonical_unique_models(
            value,
            identity="boundary_id",
            label="data-gap boundaries",
        )

    @field_validator("authority_boundaries")
    @classmethod
    def canonicalize_authority_boundaries(
        cls,
        value: tuple[PublicAuthorityBoundary, ...],
    ) -> tuple[PublicAuthorityBoundary, ...]:
        return canonical_unique_models(
            value,
            identity="boundary_id",
            label="authority boundaries",
        )


class DecompositionLeakageAudit(ContentAddressedModel):
    """Host audit that either binds a safe view or records preconstruction rejection."""

    schema_version: Literal["aecbench.decomposition-leakage-audit.v1"] = "aecbench.decomposition-leakage-audit.v1"
    audit_id: NonEmptyStr
    audited_input_sha256: str
    audit_policy_sha256: str
    passed: bool
    finding_codes: tuple[NonEmptyStr, ...] = ()
    problem_view_sha256: str | None = None

    @field_validator(
        "audited_input_sha256",
        "audit_policy_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("problem_view_sha256")
    @classmethod
    def validate_optional_problem_view_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("finding_codes")
    @classmethod
    def canonicalize_findings(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="leakage finding codes")

    @model_validator(mode="after")
    def validate_audit_outcome(self) -> Self:
        if self.passed:
            if self.finding_codes or self.problem_view_sha256 is None:
                raise ValueError("passed leakage audit requires a problem view and no findings")
        elif not self.finding_codes or self.problem_view_sha256 is not None:
            raise ValueError("failed leakage audit requires findings and cannot bind a problem view")
        return self


_KEY_SEPARATOR = re.compile(r"[^a-z0-9]+")
_PRIVILEGED_EXACT_KEYS = frozenset(
    {
        "evaluation_regime",
        "evaluation_regime_ref",
        "graph",
        "world",
        "world_json",
        "route",
        "routes",
        "stage",
        "stage_id",
        "stage_ids",
        "stage_count",
        "topology",
        "topology_signature",
        "verifier",
        "oracle",
        "reward",
        "trajectory",
        "compiler",
        "compiler_diagnostics",
        "prior_outcome",
        "holdout_motif",
        "critic",
        "critic_spec",
        "authority_policy",
        "eligibility",
        "eligibility_policy",
        "denominator",
        "denominator_policy",
        "evidence_rule",
        "evidence_inclusion_rule",
    }
)
_PRIVILEGED_KEY_TOKENS = frozenset(
    {
        "critic",
        "compiler",
        "denominator",
        "eligibility",
        "graph",
        "holdout",
        "oracle",
        "outcome",
        "reward",
        "route",
        "stage",
        "topology",
        "trajectory",
        "verifier",
        "world",
    }
)


def _normalize_key(key: object) -> str:
    return _KEY_SEPARATOR.sub("_", str(key).strip().lower()).strip("_")


def _is_privileged_key(key: object) -> bool:
    normalized = _normalize_key(key)
    if normalized in _PRIVILEGED_EXACT_KEYS:
        return True
    tokens = frozenset(normalized.split("_"))
    if tokens & _PRIVILEGED_KEY_TOKENS:
        return True
    return "authority" in tokens and "policy" in tokens


def _find_privileged_key(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _is_privileged_key(key):
                return str(key)
            leaking_key = _find_privileged_key(nested)
            if leaking_key is not None:
                return leaking_key
    elif isinstance(value, list | tuple):
        for nested in value:
            leaking_key = _find_privileged_key(nested)
            if leaking_key is not None:
                return leaking_key
    return None
