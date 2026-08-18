# ABOUTME: Defines immutable adaptive-cycle plans, terminal reports, and in-memory results.
# ABOUTME: Keeps lifecycle invariants explicit while delegating factor binding to pure helpers.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelRef,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.evolution.repair_lifecycle import (
    RepairCandidate,
    RepairLoopRequest,
    RepairLoopStatus,
)
from aec_bench.experimentation.governance.applicability import MotifApplicabilityAttestation
from aec_bench.experimentation.governance.motifs import (
    MotifLibraryArtifact,
    MotifPromotionPolicy,
    MotifStatus,
)
from aec_bench.experimentation.qualification.adaptive_cycle_runtime.factor_bindings import (
    source_request_contains_repair_parent,
    task_source_refs,
    validate_attestation_visibility,
)
from aec_bench.experimentation.qualification.adaptive_diagnosis import (
    AdaptiveDiagnosisConfiguration,
    validate_adaptive_diagnosis_feasibility,
)
from aec_bench.experimentation.qualification.harness_program_study import (
    HarnessProgramStudyRunResult,
    HarnessProgramStudySpec,
)
from aec_bench.experimentation.qualification.motif_learning import MotifLearningResult
from aec_bench.experimentation.qualification.motif_materialization import (
    MotifHarnessProgramInstantiationRequest,
)
from aec_bench.experimentation.qualification.repair_runtime import (
    RepairRuntimeExecution,
    RepairVerifierPolicy,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor


class AdaptiveCycleOutcome(StrEnum):
    """Whether the governed cycle completed transfer evaluation or stopped at an evidence gate."""

    STOPPED = "stopped"


class AdaptiveCycleTerminalStage(StrEnum):
    """Last governed stage represented by one durable cycle report."""

    REPAIR = "repair"
    MOTIF_PROMOTION = "motif_promotion"


class AdaptiveCycleTerminalReason(StrEnum):
    """Closed terminal reasons that distinguish negative evidence from runtime exceptions."""

    REPAIR_REJECTED = "repair_rejected"
    REPAIR_CHILD_EVIDENCE_INCOMPLETE = "repair_child_evidence_incomplete"
    REPAIR_RECOVERED_UNSCORED = "repair_recovered_unscored"
    REPAIR_RECOVERY_FAILED = "repair_recovery_failed"
    REPAIR_NO_REPAIR_REQUIRED = "repair_no_repair_required"
    REPAIR_NO_APPLICABLE_REPAIR = "repair_no_applicable_repair"
    MOTIF_NOT_REUSABLE = "motif_not_reusable"


class AdaptiveHarnessProgramStageSpec(FrozenStrictModel):
    """Fixed controls for a post-repair calibration or frozen transfer harness-program."""

    policy_id: NonEmptyStr
    split: Literal["calibration", "holdout"]
    instantiation: MotifHarnessProgramInstantiationRequest
    applicability: MotifApplicabilityAttestation
    randomization_seed: int
    confidence_level: float = Field(default=0.95, gt=0.0, lt=1.0)
    bootstrap_replicates: PositiveInt = 2_000
    bootstrap_seed: int = 42

    @model_validator(mode="after")
    def validate_applicability(self) -> Self:
        if self.applicability.kernel_ref != self.instantiation.kernel_ref:
            raise ValueError("adaptive harness-program applicability does not use the stage fixed kernel")
        task_refs = tuple(projection.snapshot.task_id for projection in self.applicability.projections)
        if task_refs != self.instantiation.task_refs:
            raise ValueError("adaptive harness-program applicability must cover the exact stage tasks")
        if task_source_refs(self.instantiation.fixed_harness_recipe) != self.instantiation.task_refs:
            raise ValueError("adaptive harness-program fixed harness task-source binding must match the stage tasks")
        return self


class AdaptiveCycleSpec(LegacyContentAddressedModel):
    """Immutable plan for source search, paired repair, child calibration, and transfer."""

    schema_version: Literal["aecbench.adaptive-cycle-spec.v2"] = "aecbench.adaptive-cycle-spec.v2"
    source_stage: HarnessProgramStudySpec
    repair_request: RepairLoopRequest
    repair_parent: RepairCandidate
    repair_verifier_policy: RepairVerifierPolicy
    diagnosis_rule: AdaptiveDiagnosisConfiguration
    child_calibration: AdaptiveHarnessProgramStageSpec
    promotion_policy: MotifPromotionPolicy
    transfer: AdaptiveHarnessProgramStageSpec
    input_motif_library: MotifLibraryArtifact
    harness_generator_sha256: str
    program_generator_sha256: str

    @field_validator("harness_generator_sha256", "program_generator_sha256")
    @classmethod
    def validate_generator_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_cycle(self) -> Self:
        _validate_cycle_kernel_and_splits(self)
        _validate_cycle_applicability(self)
        _validate_cycle_task_surfaces(self)
        _validate_cycle_source_identity(self)
        _validate_cycle_generators_and_diagnosis(self)
        return self


@dataclass(frozen=True)
class AdaptiveCycleExecutors:
    """Optional protocol-compatible executors injected independently at each external boundary."""

    source: HarborCommandExecutor | None = None
    repair: HarborCommandExecutor | None = None
    child_calibration: HarborCommandExecutor | None = None


class AdaptiveCycleReport(LegacyContentAddressedModel):
    """Durable causal index over one complete or evidence-gated fixed-K cycle prefix."""

    schema_version: Literal["aecbench.adaptive-cycle-report.v2"] = "aecbench.adaptive-cycle-report.v2"
    conclusion: Literal["fixed_k_adaptive_cycle"] = "fixed_k_adaptive_cycle"
    outcome: AdaptiveCycleOutcome
    terminal_stage: AdaptiveCycleTerminalStage
    terminal_reason: AdaptiveCycleTerminalReason
    spec_sha256: str
    spec_artifact: ArtifactReference
    kernel_ref: KernelRef
    input_motif_library: MotifLibraryArtifact
    source_stage_report: ArtifactReference
    repair_terminal: ArtifactReference
    repaired_candidate: ArtifactReference | None = None
    child_calibration_report: ArtifactReference | None = None
    motif_learning_report: ArtifactReference | None = None
    learning_motif_library: ArtifactReference | None = None
    motif_library: ArtifactReference
    learned_motif_sha256: str | None = None
    learning_archive_sha256: str | None = None
    final_motif_sha256: str | None = None
    final_archive_sha256: str
    final_status: MotifStatus | None = None

    @field_validator(
        "spec_sha256",
        "final_archive_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "learned_motif_sha256",
        "learning_archive_sha256",
        "final_motif_sha256",
    )
    @classmethod
    def validate_optional_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_terminal_shape(self) -> Self:
        _validate_report_artifact_kinds(self)
        _validate_report_artifact_shape(self)
        if self.terminal_stage is AdaptiveCycleTerminalStage.REPAIR:
            _validate_repair_terminal(self)
        elif self.terminal_stage is AdaptiveCycleTerminalStage.MOTIF_PROMOTION:
            _validate_motif_terminal(self)
        return self


@dataclass(frozen=True)
class AdaptiveCycleResult:
    """In-memory stage results plus the persisted top-level cycle report."""

    source_stage: HarnessProgramStudyRunResult
    repair: RepairRuntimeExecution
    repaired_candidate: RepairCandidate | None
    child_calibration: HarnessProgramStudyRunResult | None
    learning: MotifLearningResult | None
    report: AdaptiveCycleReport
    path: Path


def _validate_cycle_kernel_and_splits(cycle: AdaptiveCycleSpec) -> None:
    source_stage = cycle.source_stage
    kernel_ref = source_stage.candidate_requests[0].kernel_ref
    if cycle.repair_parent.harness_request.kernel_ref != kernel_ref:
        raise ValueError("adaptive cycle repair parent does not use the source fixed kernel")
    if cycle.repair_parent.candidate_id != cycle.repair_request.parent_candidate_id:
        raise ValueError("adaptive cycle repair parent does not match its request")
    if cycle.child_calibration.instantiation.kernel_ref != kernel_ref:
        raise ValueError("adaptive cycle child calibration does not use the source fixed kernel")
    if cycle.transfer.instantiation.kernel_ref != kernel_ref:
        raise ValueError("adaptive cycle transfer does not use the source fixed kernel")
    if source_stage.split != "discovery":
        raise ValueError("adaptive cycle source stage must use the discovery split")
    if cycle.repair_request.pairing.split != "repair_gate":
        raise ValueError("adaptive cycle repair must use the repair_gate split")
    if cycle.child_calibration.split != "calibration":
        raise ValueError("adaptive cycle child stage must use the calibration split")
    if cycle.transfer.split != "holdout":
        raise ValueError("adaptive cycle transfer stage must use the holdout split")


def _validate_cycle_applicability(cycle: AdaptiveCycleSpec) -> None:
    source_applicability = cycle.source_stage.applicability
    child_applicability = cycle.child_calibration.applicability
    transfer_applicability = cycle.transfer.applicability
    validate_attestation_visibility(
        source_applicability,
        expected=Visibility.PUBLIC,
        label="source",
    )
    validate_attestation_visibility(
        child_applicability,
        expected=Visibility.PUBLIC,
        label="child calibration",
    )
    validate_attestation_visibility(
        transfer_applicability,
        expected=Visibility.HOLDOUT,
        label="transfer",
    )
    if child_applicability.descriptor != source_applicability.descriptor:
        raise ValueError("adaptive cycle child calibration must use the source applicability bucket")
    if set(child_applicability.review_lineage_ids).intersection(source_applicability.review_lineage_ids):
        raise ValueError("adaptive cycle child calibration review lineages must be independent")
    if transfer_applicability.descriptor != source_applicability.descriptor:
        raise ValueError("adaptive cycle transfer must use the source applicability bucket")
    selection_lineages = set(source_applicability.review_lineage_ids) | set(child_applicability.review_lineage_ids)
    if selection_lineages.intersection(transfer_applicability.review_lineage_ids):
        raise ValueError("adaptive cycle holdout review lineages must be unseen during selection")


def _validate_cycle_task_surfaces(cycle: AdaptiveCycleSpec) -> None:
    parent_task_refs = task_source_refs(cycle.repair_parent.harness_request.recipe)
    if cycle.repair_request.pairing.task_ids != parent_task_refs:
        raise ValueError("adaptive cycle repair pairing must match the parent task-source binding")
    stage_task_counts = {
        len(parent_task_refs),
        len(cycle.child_calibration.instantiation.task_refs),
        len(cycle.transfer.instantiation.task_refs),
    }
    if len(stage_task_counts) != 1:
        raise ValueError(
            "adaptive cycle program task rebinding requires one-to-one task cardinality "
            "across source, child calibration, and transfer"
        )
    source_task_sets = {request.task_refs for request in cycle.source_stage.candidate_requests}
    if parent_task_refs not in source_task_sets:
        raise ValueError("adaptive cycle repair parent tasks must come from the source preregistration")


def _validate_cycle_source_identity(cycle: AdaptiveCycleSpec) -> None:
    if not any(
        source_request_contains_repair_parent(request, cycle.repair_parent)
        for request in cycle.source_stage.candidate_requests
    ):
        raise ValueError("adaptive cycle repair parent Hx/px must come from the source preregistration")
    if (
        cycle.source_stage.harness_generator_sha256 != cycle.harness_generator_sha256
        or cycle.source_stage.program_generator_sha256 != cycle.program_generator_sha256
    ):
        raise ValueError("adaptive cycle generator identities must match source preregistration")


def _validate_cycle_generators_and_diagnosis(cycle: AdaptiveCycleSpec) -> None:
    validate_adaptive_diagnosis_feasibility(
        cycle.diagnosis_rule,
        candidate=cycle.repair_parent,
        pairing=cycle.repair_request.pairing,
    )


def _validate_report_artifact_kinds(report: AdaptiveCycleReport) -> None:
    expected_artifact_kinds = {
        "spec_artifact": "adaptive-cycle-spec",
        "source_stage_report": "harness-program-study-report",
        "repair_terminal": "repair-terminal",
        "repaired_candidate": "repair-candidate",
        "child_calibration_report": "harness-program-study-report",
        "motif_learning_report": "motif-learning-report",
        "learning_motif_library": "motif-library",
        "motif_library": "motif-library",
    }
    for field_name, expected_kind in expected_artifact_kinds.items():
        artifact = getattr(report, field_name)
        if artifact is not None and artifact.kind != expected_kind:
            raise ValueError(f"adaptive cycle {field_name} artifact kind must be {expected_kind}")


def _validate_report_artifact_shape(report: AdaptiveCycleReport) -> None:
    downstream = {
        "repaired_candidate": report.repaired_candidate,
        "child_calibration_report": report.child_calibration_report,
        "motif_learning_report": report.motif_learning_report,
        "learning_motif_library": report.learning_motif_library,
    }
    present = frozenset(name for name, value in downstream.items() if value is not None)
    required = {
        AdaptiveCycleTerminalStage.REPAIR: frozenset(),
        AdaptiveCycleTerminalStage.MOTIF_PROMOTION: frozenset(
            {
                "repaired_candidate",
                "child_calibration_report",
                "motif_learning_report",
                "learning_motif_library",
            }
        ),
    }[report.terminal_stage]
    if present != required:
        raise ValueError("adaptive cycle terminal artifact shape does not match its terminal stage")


def _validate_repair_terminal(report: AdaptiveCycleReport) -> None:
    repair_reasons = {
        AdaptiveCycleTerminalReason.REPAIR_REJECTED,
        AdaptiveCycleTerminalReason.REPAIR_CHILD_EVIDENCE_INCOMPLETE,
        AdaptiveCycleTerminalReason.REPAIR_RECOVERED_UNSCORED,
        AdaptiveCycleTerminalReason.REPAIR_RECOVERY_FAILED,
        AdaptiveCycleTerminalReason.REPAIR_NO_REPAIR_REQUIRED,
        AdaptiveCycleTerminalReason.REPAIR_NO_APPLICABLE_REPAIR,
    }
    if report.outcome is not AdaptiveCycleOutcome.STOPPED or report.terminal_reason not in repair_reasons:
        raise ValueError("adaptive cycle repair terminal has an invalid outcome or reason")
    if any(
        value is not None
        for value in (
            report.learned_motif_sha256,
            report.learning_archive_sha256,
            report.final_motif_sha256,
            report.final_status,
        )
    ):
        raise ValueError("adaptive cycle repair terminal cannot claim a learned motif")
    if report.final_archive_sha256 != report.input_motif_library.archive_sha256:
        raise ValueError("adaptive cycle repair terminal must preserve the input archive")


def _validate_motif_terminal(report: AdaptiveCycleReport) -> None:
    if (
        report.outcome is not AdaptiveCycleOutcome.STOPPED
        or report.terminal_reason is not AdaptiveCycleTerminalReason.MOTIF_NOT_REUSABLE
    ):
        raise ValueError("adaptive cycle motif terminal has an invalid outcome or reason")
    if any(
        value is None
        for value in (
            report.learned_motif_sha256,
            report.learning_archive_sha256,
            report.final_motif_sha256,
            report.final_status,
        )
    ):
        raise ValueError("adaptive cycle motif terminal requires its learned motif identity")
    if report.final_status in {
        MotifStatus.REUSABLE,
        MotifStatus.TRANSFER_VALIDATED,
    }:
        raise ValueError("adaptive cycle stopped motif cannot already be reusable")
    if report.final_archive_sha256 != report.learning_archive_sha256:
        raise ValueError("adaptive cycle motif terminal archive must equal its learning archive")


def repair_terminal_reason(
    status: RepairLoopStatus,
) -> AdaptiveCycleTerminalReason:
    """Translate a non-accepted repair status into its durable cycle reason."""

    try:
        return {
            RepairLoopStatus.REJECTED: AdaptiveCycleTerminalReason.REPAIR_REJECTED,
            RepairLoopStatus.CHILD_EVIDENCE_INCOMPLETE: (AdaptiveCycleTerminalReason.REPAIR_CHILD_EVIDENCE_INCOMPLETE),
            RepairLoopStatus.RECOVERED_UNSCORED: (AdaptiveCycleTerminalReason.REPAIR_RECOVERED_UNSCORED),
            RepairLoopStatus.RECOVERY_FAILED: (AdaptiveCycleTerminalReason.REPAIR_RECOVERY_FAILED),
            RepairLoopStatus.NO_REPAIR_REQUIRED: (AdaptiveCycleTerminalReason.REPAIR_NO_REPAIR_REQUIRED),
            RepairLoopStatus.NO_APPLICABLE_REPAIR: (AdaptiveCycleTerminalReason.REPAIR_NO_APPLICABLE_REPAIR),
        }[status]
    except KeyError as error:
        raise ValueError(f"accepted repair cannot produce an early-stop terminal: {status.value}") from error
