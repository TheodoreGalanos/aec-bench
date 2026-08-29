# ABOUTME: Defines the typed identity and manifest contracts for one recorded lifecycle invocation.
# ABOUTME: Keeps recording, finalization, and study composition on one small contract boundary.

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Annotated, Any, Literal, Self, TypedDict

from pydantic import Field, StrictBool, model_validator

from aec_bench.contracts.artifacts import Sha256
from aec_bench.contracts.lifecycle_evaluation import LifecycleSemanticMetrics
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr, StrictModel
from aec_bench.lifecycles.compiled import CompiledLifecycleEnvelope

_StrictPositiveInt = Annotated[int, Field(strict=True, gt=0)]
_StrictNonNegativeInt = Annotated[int, Field(strict=True, ge=0)]
_StrictNonNegativeFloat = Annotated[float, Field(strict=True, ge=0.0)]


class LifecycleExperimentSweepContext(StrictModel):
    schema_version: Literal["1"] = "1"
    sweep_experiment_id: NonEmptyStr
    planned_trial_id: NonEmptyStr
    plan_sha256: NonEmptyStr
    condition_id: NonEmptyStr
    repetition: _StrictPositiveInt


class LifecycleExperimentTrialContext(StrictModel):
    """Bind one invocation to its exact planned and compiled trial identity."""

    schema_version: Literal["1"] = "1"
    trial_id: NonEmptyStr
    planned_experiment_id: NonEmptyStr
    task_id: NonEmptyStr
    repetition: _StrictPositiveInt
    run_id: NonEmptyStr
    compiled: CompiledLifecycleEnvelope


class LifecycleExperimentMetrics(StrictModel):
    """Store the normalized metrics published for one lifecycle invocation."""

    schema_version: Literal["1", "2", "3"] = "3"
    checkpoint_count: _StrictNonNegativeInt
    requests: _StrictNonNegativeInt
    tool_calls: _StrictNonNegativeInt
    reads: _StrictNonNegativeInt
    revisits: _StrictNonNegativeInt
    evidence_request_calls: _StrictNonNegativeInt = 0
    accepted_evidence_requests: _StrictNonNegativeInt = 0
    already_released_evidence_requests: _StrictNonNegativeInt = 0
    rejected_evidence_requests: _StrictNonNegativeInt = 0
    evidence_request_budget_consumed: _StrictNonNegativeInt = 0
    evidence_request_artifacts_released: _StrictNonNegativeInt = 0
    operation_calls: _StrictNonNegativeInt = 0
    completed_operations: _StrictNonNegativeInt = 0
    already_current_operations: _StrictNonNegativeInt = 0
    rejected_operations: _StrictNonNegativeInt = 0
    operation_budget_consumed: _StrictNonNegativeInt = 0
    operation_artifacts_produced: _StrictNonNegativeInt = 0
    retries: _StrictNonNegativeInt
    failures: _StrictNonNegativeInt
    input_tokens: _StrictNonNegativeInt
    output_tokens: _StrictNonNegativeInt
    cache_read_tokens: _StrictNonNegativeInt
    cache_write_tokens: _StrictNonNegativeInt
    estimated_cost_usd: _StrictNonNegativeFloat | None = None
    checkpoint_seconds: dict[str, _StrictNonNegativeFloat] = Field(default_factory=dict)
    whole_run_seconds: _StrictNonNegativeFloat | None = None
    semantic_transition: LifecycleSemanticMetrics | None = None


_V3_OPERATION_METRIC_FIELDS = (
    "operation_calls",
    "completed_operations",
    "already_current_operations",
    "rejected_operations",
    "operation_budget_consumed",
    "operation_artifacts_produced",
)


def lifecycle_experiment_metrics_payload(metrics: LifecycleExperimentMetrics) -> dict[str, Any]:
    """Preserve each metrics version's exact public field projection."""
    payload = metrics.model_dump(mode="json")
    if metrics.schema_version != "3":
        for field_name in _V3_OPERATION_METRIC_FIELDS:
            payload.pop(field_name)
    return payload


class LifecycleCallableProvenanceIdentity(FrozenStrictModel):
    """Bind a callable name to its exact source bytes without trusting a path."""

    qualified_name: NonEmptyStr
    source_sha256: Sha256


class LifecycleCallableProvenance(LifecycleCallableProvenanceIdentity):
    """Capture the complete callable provenance block written by the recorder."""

    source_path: NonEmptyStr


class LifecycleRepositoryProvenanceIdentity(FrozenStrictModel):
    """Bind repository source identity fields that a study preregisters."""

    commit: NonEmptyStr
    source_inventory_sha256: Sha256

    @model_validator(mode="after")
    def validate_commit(self) -> Self:
        is_git_commit = len(self.commit) == 40 and all(character in "0123456789abcdef" for character in self.commit)
        is_source_tree_commit = self.commit == f"source-sha256:{self.source_inventory_sha256}"
        if not is_git_commit and not is_source_tree_commit:
            raise ValueError("lifecycle repository commit does not match its source identity")
        return self

    @property
    def expected_repository_kind(self) -> Literal["git", "source_tree"]:
        return "source_tree" if self.commit.startswith("source-sha256:") else "git"


class LifecycleRepositoryProvenance(LifecycleRepositoryProvenanceIdentity):
    """Capture the complete repository provenance block written by the recorder."""

    root: NonEmptyStr
    dirty: StrictBool
    dirty_digest: Sha256
    repository_kind: Literal["git", "source_tree"]

    @model_validator(mode="after")
    def validate_repository_state(self) -> Self:
        if self.repository_kind != self.expected_repository_kind:
            raise ValueError("lifecycle repository kind does not match its source identity")
        empty_digest = hashlib.sha256(b"").hexdigest()
        if self.dirty != (self.dirty_digest != empty_digest):
            raise ValueError("lifecycle repository dirty state does not match its digest")
        if self.repository_kind == "source_tree" and self.dirty:
            raise ValueError("lifecycle source-tree repository must be clean")
        return self


class LifecycleRuntimeProvenance(FrozenStrictModel):
    """Capture the exact adapter dependency closure written by the recorder."""

    adapter: NonEmptyStr
    provider: NonEmptyStr
    distributions: tuple[NonEmptyStr, ...]
    dependency_inventory_sha256: Sha256

    @model_validator(mode="after")
    def validate_distributions(self) -> Self:
        if not self.distributions or tuple(sorted(set(self.distributions))) != self.distributions:
            raise ValueError("lifecycle runtime distributions must be non-empty, sorted, and unique")
        return self


class LifecycleVerifierProvenanceCapture(FrozenStrictModel):
    """Capture the registered verifier and the invoked verifier entrypoint."""

    registered: LifecycleCallableProvenance
    entrypoint: LifecycleCallableProvenance

    def manifest_payload(self) -> dict[str, Any]:
        """Return the exact verifier block written to an invocation manifest."""
        registered = self.registered.model_dump(mode="json")
        entrypoint = self.entrypoint.model_dump(mode="json")
        chain = [entrypoint] if entrypoint == registered else [entrypoint, registered]
        return {**registered, "entrypoint": entrypoint, "chain": chain}


class LifecycleVerifierProvenanceExpectation(FrozenStrictModel):
    """Bind verifier fields that a study preregisters without inventing source paths."""

    registered: LifecycleCallableProvenanceIdentity
    entrypoint: LifecycleCallableProvenanceIdentity


class LifecycleInvocationRecorderCapture(FrozenStrictModel):
    """Bind every recorder-owned invocation field through its canonical manifest bytes."""

    kind: Literal["recorded_capture"] = "recorded_capture"
    manifest_sha256: Sha256


class LifecycleInvocationPlanExpectation(FrozenStrictModel):
    """Preserve preregistered identities, excluding unplanned creation time and Python version."""

    kind: Literal["planned_expectation"] = "planned_expectation"
    repository: LifecycleRepositoryProvenanceIdentity
    runtime: LifecycleRuntimeProvenance
    verifier: LifecycleVerifierProvenanceExpectation


type LifecycleInvocationFinalizationAuthority = LifecycleInvocationRecorderCapture | LifecycleInvocationPlanExpectation


class LifecycleExperimentRecordingResult(TypedDict):
    """Identify the immutable files produced by one lifecycle recorder."""

    experiment_id: str
    manifest: str
    canonical_manifest: str
    manifest_sha256: str
    metrics: str
    verification: str
    index: str
    finalization_authority: LifecycleInvocationFinalizationAuthority


class LifecycleExperimentManifest(StrictModel):
    """Describe one recorded invocation, including historical version 1 manifests."""

    schema_version: Literal["1", "2"] = "1"
    experiment_id: NonEmptyStr
    created_at: NonEmptyStr
    repository: dict[str, Any]
    environment: dict[str, Any]
    lifecycle: dict[str, Any]
    verifier: dict[str, Any]
    model: dict[str, Any]
    execution: dict[str, Any]
    interaction: dict[str, Any]
    outputs: dict[str, Any]
    sweep: LifecycleExperimentSweepContext | None = None
    trial: LifecycleExperimentTrialContext | None = None

    @model_validator(mode="after")
    def validate_trial_identity_version(self) -> Self:
        if self.schema_version == "1" and self.trial is not None:
            raise ValueError("lifecycle invocation manifest version 1 cannot contain trial identity")
        if self.schema_version == "2" and self.trial is None:
            raise ValueError("lifecycle invocation manifest version 2 requires trial identity")
        return self


def single_resolved_lifecycle_identity(
    identities: Iterable[str],
    *,
    kind: Literal["model", "adapter"],
) -> str:
    """Return the one resolved session identity or reject an ambiguous invocation."""
    resolved = sorted({identity for identity in identities if identity and identity != "unresolved"})
    if len(resolved) > 1:
        raise ValueError(f"lifecycle sessions contain multiple resolved {kind} identities")
    return resolved[0] if resolved else "unresolved"


__all__ = (
    "LifecycleCallableProvenance",
    "LifecycleCallableProvenanceIdentity",
    "LifecycleExperimentManifest",
    "LifecycleExperimentMetrics",
    "LifecycleExperimentRecordingResult",
    "LifecycleExperimentSweepContext",
    "LifecycleExperimentTrialContext",
    "LifecycleInvocationFinalizationAuthority",
    "LifecycleInvocationPlanExpectation",
    "LifecycleInvocationRecorderCapture",
    "LifecycleRepositoryProvenance",
    "LifecycleRepositoryProvenanceIdentity",
    "LifecycleRuntimeProvenance",
    "LifecycleVerifierProvenanceCapture",
    "LifecycleVerifierProvenanceExpectation",
    "lifecycle_experiment_metrics_payload",
    "single_resolved_lifecycle_identity",
)
