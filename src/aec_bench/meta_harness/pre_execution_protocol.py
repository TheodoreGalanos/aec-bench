# ABOUTME: Records phase-neutral proposal readiness before candidate execution may begin.
# ABOUTME: Replays freeze authority and persists an exact, content-addressed claim boundary.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    BaseModel,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    TypeAdapter,
    field_validator,
    model_validator,
)

from aec_bench.contracts.authority import AuthorityPrincipalKind, TaintLabel
from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
)
from aec_bench.meta_harness.decomposition_optimization import (
    DecompositionExecutionSchedule,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactStoreError,
)
from aec_bench.meta_harness.proposal_freeze import (
    GovernedProposalFreezeError,
    GovernedProposalFreezeResult,
    assert_proposal_freeze_authority,
)
from aec_bench.meta_harness.structural_generalization_corpus import (
    StructuralSplitManifest,
)

_REPORT_COLLECTION = "pre-execution-protocol-reports"
_REPORT_FILENAME = "pre-execution-protocol-report.json"


class PreExecutionProtocolSpec(ContentAddressedModel):
    """Versioned claim policy for one pre-execution readiness gate."""

    schema_version: Literal["aecbench.pre-execution-protocol-spec.v1"] = "aecbench.pre-execution-protocol-spec.v1"
    protocol_id: NonEmptyStr
    conclusion: NonEmptyStr
    proposal_generation_mode: NonEmptyStr
    proposal_origin_policy: Literal[
        "governed_freeze",
        "optimizer_only",
    ] = "governed_freeze"
    provider_call_policy: Literal[
        "recorded",
        "zero",
    ] = "recorded"
    deferred_status: NonEmptyStr
    limitations: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @field_validator("limitations")
    @classmethod
    def canonicalize_limitations(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("pre-execution protocol limitations must be unique")
        return tuple(sorted(value))


class PreExecutionProtocolReport(ContentAddressedModel):
    """Replayable proposal-readiness report with no candidate execution authority."""

    schema_version: Literal["aecbench.pre-execution-protocol-report.v1"] = "aecbench.pre-execution-protocol-report.v1"
    spec: PreExecutionProtocolSpec
    kernel_sha256: str
    fixed_harness_sha256: str
    harness_policy_sha256: str
    structural_split_sha256: str
    task_manifest_sha256: str
    proposal_freeze_result: GovernedProposalFreezeResult
    execution_schedule: DecompositionExecutionSchedule
    scheduled_candidate_count: int = Field(ge=2)
    scheduled_coordinate_count: int = Field(ge=1)
    scheduled_assignment_count: int = Field(ge=2)
    compile_dispatch_started: Literal[False] = False
    evaluation_started: Literal[False] = False
    evaluation_outcome_count: Literal[0] = 0
    trial_record_count: Literal[0] = 0
    provider_calls: NonNegativeInt = 0
    provider_cost_usd: NonNegativeFloat = 0.0
    promotion_permitted: Literal[False] = False
    promotion_event_count: Literal[0] = 0

    @field_validator(
        "kernel_sha256",
        "fixed_harness_sha256",
        "harness_policy_sha256",
        "structural_split_sha256",
        "task_manifest_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_protocol_boundary(self) -> Self:
        validate_pre_execution_bindings(
            proposal_freeze_result=self.proposal_freeze_result,
            execution_schedule=self.execution_schedule,
            kernel_sha256=self.kernel_sha256,
            fixed_harness_sha256=self.fixed_harness_sha256,
            harness_policy_sha256=self.harness_policy_sha256,
            structural_split_sha256=self.structural_split_sha256,
            scheduled_candidate_count=self.scheduled_candidate_count,
            scheduled_coordinate_count=self.scheduled_coordinate_count,
            scheduled_assignment_count=self.scheduled_assignment_count,
        )
        if self.spec.provider_call_policy == "zero" and (self.provider_calls != 0 or self.provider_cost_usd != 0):
            raise ValueError(
                "zero-provider pre-execution protocol cannot record provider effects",
            )
        return self


@dataclass(frozen=True)
class PreExecutionProtocolRunResult:
    """Persisted phase-neutral protocol report and its exact physical path."""

    report: PreExecutionProtocolReport
    path: Path


@dataclass(frozen=True)
class PreExecutionProtocolEvidence:
    """Authority-replayed report and the exact governed structural split."""

    report: PreExecutionProtocolReport
    structural_split: StructuralSplitManifest


def record_pre_execution_protocol(
    *,
    spec: PreExecutionProtocolSpec,
    ledger: AuthorityLedger,
    structural_split: StructuralSplitManifest,
    proposal_freeze_result: GovernedProposalFreezeResult,
    execution_schedule: DecompositionExecutionSchedule,
    output_root: Path,
    provider_calls: int = 0,
    provider_cost_usd: float = 0.0,
) -> PreExecutionProtocolRunResult:
    """Replay the frozen proposal boundary and persist one readiness report."""

    root = Path(output_root).resolve()
    if ledger.root != (root / "authority").resolve():
        raise ValueError(
            "pre-execution authority ledger must live under the report root",
        )
    validated_spec = _validate_model(spec, PreExecutionProtocolSpec, "protocol spec")
    validated_split = _validate_model(
        structural_split,
        StructuralSplitManifest,
        "structural split",
    )
    validated_result = _validate_model(
        proposal_freeze_result,
        GovernedProposalFreezeResult,
        "proposal freeze result",
    )
    validated_schedule = _validate_model(
        execution_schedule,
        DecompositionExecutionSchedule,
        "execution schedule",
    )
    replay_pre_execution_authority(
        ledger=ledger,
        result=validated_result,
        structural_split=validated_split,
        require_optimizer_origin=(validated_spec.proposal_origin_policy == "optimizer_only"),
    )
    freeze = validated_result.freeze
    if validated_split.content_sha256 != freeze.structural_split_sha256:
        raise ValueError(
            "structural split differs from the governed proposal freeze",
        )
    report = PreExecutionProtocolReport(
        spec=validated_spec,
        kernel_sha256=validated_schedule.kernel_sha256,
        fixed_harness_sha256=validated_schedule.fixed_harness_sha256,
        harness_policy_sha256=freeze.problem_view.fixed_harness.harness_policy_sha256,
        structural_split_sha256=validated_split.content_sha256,
        task_manifest_sha256=validated_split.task_manifest_sha256,
        proposal_freeze_result=validated_result,
        execution_schedule=validated_schedule,
        scheduled_candidate_count=1 + len(freeze.realized_candidates),
        scheduled_coordinate_count=len(validated_schedule.coordinates),
        scheduled_assignment_count=len(validated_schedule.assignments),
        provider_calls=provider_calls,
        provider_cost_usd=provider_cost_usd,
    )
    try:
        stored = EvidenceRepository(root).publish_content_addressed_model(
            collection=_REPORT_COLLECTION,
            filename=_REPORT_FILENAME,
            model=report,
            adapter=TypeAdapter(PreExecutionProtocolReport),
        )
    except ImmutableArtifactStoreError as error:
        raise ValueError(
            f"pre-execution protocol persistence failed: {error}",
        ) from error
    return PreExecutionProtocolRunResult(
        report=stored.model,
        path=stored.artifact.path,
    )


def load_pre_execution_protocol_report(
    path: Path,
) -> PreExecutionProtocolReport:
    """Load and authority-replay one phase-neutral readiness report."""

    return load_pre_execution_protocol_evidence(path).report


def load_pre_execution_protocol_evidence(
    path: Path,
) -> PreExecutionProtocolEvidence:
    """Load a readiness report together with its governed structural basis."""

    report_path = Path(path).resolve()
    run_root = _report_root(report_path)
    try:
        repository = EvidenceRepository(run_root)
        stored = repository.load_content_addressed_model(
            collection=_REPORT_COLLECTION,
            content_sha256=report_path.parent.name,
            filename=_REPORT_FILENAME,
            adapter=TypeAdapter(PreExecutionProtocolReport),
        )
        if stored.artifact.path != report_path:
            raise ValueError(
                "pre-execution protocol path is not its canonical content path",
            )
        report = stored.model
        structural_split = load_pre_execution_structural_basis(
            ledger=AuthorityLedger(run_root / "authority"),
            result=report.proposal_freeze_result,
            require_optimizer_origin=(report.spec.proposal_origin_policy == "optimizer_only"),
        )
        if (
            structural_split.content_sha256 != report.structural_split_sha256
            or structural_split.task_manifest_sha256 != report.task_manifest_sha256
        ):
            raise ValueError(
                "stored structural manifest differs from the pre-execution report",
            )
    except (
        AuthorityLedgerError,
        GovernedProposalFreezeError,
        ImmutableArtifactStoreError,
        OSError,
        ValueError,
    ) as error:
        raise ValueError(
            f"pre-execution authority replay failed: {error}",
        ) from error
    return PreExecutionProtocolEvidence(
        report=report,
        structural_split=structural_split,
    )


def validate_pre_execution_bindings(
    *,
    proposal_freeze_result: GovernedProposalFreezeResult,
    execution_schedule: DecompositionExecutionSchedule,
    kernel_sha256: str,
    fixed_harness_sha256: str,
    harness_policy_sha256: str,
    structural_split_sha256: str,
    scheduled_candidate_count: int,
    scheduled_coordinate_count: int,
    scheduled_assignment_count: int,
) -> None:
    """Recompute the exact proposal-to-schedule bindings for one report."""

    freeze = proposal_freeze_result.freeze
    schedule = execution_schedule
    comparisons = (
        (
            schedule.proposal_freeze == freeze,
            "schedule does not bind the governed proposal freeze",
        ),
        (
            kernel_sha256 == schedule.kernel_sha256,
            "kernel does not match the frozen schedule",
        ),
        (
            fixed_harness_sha256 == schedule.fixed_harness_sha256,
            "fixed harness does not match the frozen schedule",
        ),
        (
            harness_policy_sha256 == freeze.problem_view.fixed_harness.harness_policy_sha256,
            "harness policy does not match the safe problem view",
        ),
        (
            structural_split_sha256 == freeze.structural_split_sha256,
            "structural split does not match the governed freeze",
        ),
        (
            scheduled_candidate_count == 1 + len(freeze.realized_candidates),
            "scheduled candidate count is not exact",
        ),
        (
            scheduled_coordinate_count == len(schedule.coordinates),
            "scheduled coordinate count is not exact",
        ),
        (
            scheduled_assignment_count == len(schedule.assignments),
            "scheduled assignment count is not exact",
        ),
        (
            scheduled_assignment_count == scheduled_candidate_count * scheduled_coordinate_count,
            "schedule is not the complete candidate-coordinate matrix",
        ),
    )
    failure = next((message for valid, message in comparisons if not valid), None)
    if failure is not None:
        raise ValueError(failure)


def replay_pre_execution_authority(
    *,
    ledger: AuthorityLedger,
    result: GovernedProposalFreezeResult,
    structural_split: StructuralSplitManifest,
    require_optimizer_origin: bool,
) -> None:
    """Replay freeze authority and require the supplied structural basis exactly."""

    try:
        assert_proposal_freeze_authority(
            ledger=ledger,
            result=result,
        )
        stored = load_pre_execution_structural_basis(
            ledger=ledger,
            result=result,
            require_optimizer_origin=require_optimizer_origin,
        )
        if stored != structural_split:
            raise ValueError(
                "supplied structural manifest differs from the governed freeze basis",
            )
    except (
        AuthorityLedgerError,
        GovernedProposalFreezeError,
        OSError,
        ValueError,
    ) as error:
        raise ValueError(f"pre-execution authority replay failed: {error}") from error


def load_pre_execution_structural_basis(
    *,
    ledger: AuthorityLedger,
    result: GovernedProposalFreezeResult,
    require_optimizer_origin: bool,
) -> StructuralSplitManifest:
    """Resolve the exact structural basis and optional optimizer-only origin policy."""

    assert_proposal_freeze_authority(
        ledger=ledger,
        result=result,
    )
    stored = ledger.resolve_basis(result.basis.structural_split)
    structural_split = StructuralSplitManifest.model_validate_json(
        stored.content_path.read_bytes(),
    )
    if require_optimizer_origin:
        assert_optimizer_proposal_origins(
            ledger=ledger,
            result=result,
        )
    return structural_split


def assert_optimizer_proposal_origins(
    *,
    ledger: AuthorityLedger,
    result: GovernedProposalFreezeResult,
) -> None:
    """Require every frozen proposal artifact to be optimizer-authored and non-model-tainted."""

    for reference in result.basis.proposal_artifacts:
        origin = ledger.resolve_basis(reference).origin
        if (
            origin.producer.kind is not AuthorityPrincipalKind.OPTIMIZER
            or TaintLabel.MODEL_REPORTED in origin.taint_labels
        ):
            raise ValueError(
                "provider-free proposal provenance requires optimizer-authored, non-model-tainted artifacts",
            )


def _report_root(report_path: Path) -> Path:
    if report_path.name != _REPORT_FILENAME or report_path.parent.parent.name != _REPORT_COLLECTION:
        raise ValueError(
            "pre-execution protocol path is not a canonical report path",
        )
    validate_sha256(report_path.parent.name)
    return report_path.parents[2]


def _validate_model[ModelT: BaseModel](
    value: ModelT,
    model_type: type[ModelT],
    label: str,
) -> ModelT:
    try:
        return model_type.model_validate(value.model_dump(mode="python"))
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"pre-execution {label} is invalid: {error}") from error
