# ABOUTME: Defines executable identities and policies for program-necessity studies.
# ABOUTME: Separates context-splitting value from structure-aligned value across independent worlds.

from __future__ import annotations

import math
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, FiniteFloat, field_validator, model_validator

from aec_bench.contracts.evaluation_plane import EvaluationPlanRef
from aec_bench.contracts.harness_instance import HarnessBudget
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.study import MatchedCandidateEvidenceRef, MatchedEvaluationCoordinate
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.task_snapshot import (
    graph_hidden_task_snapshot_sha256,
)


class ProgramNecessityArm(StrEnum):
    """Closed confirmatory arms used to isolate splitting from structure."""

    MONOLITHIC = "monolithic"
    SHAM = "sham"
    STRUCTURAL = "structural"


class ProgramNecessityMechanism(StrEnum):
    """Preregistered task mechanisms whose topology may be load-bearing."""

    EVIDENCE_FANOUT_JOIN = "evidence_fanout_join"
    DEPENDENCY_ORDER = "dependency_order"
    MATCHED_EFFICIENCY = "matched_efficiency"
    INFORMATION_PRESERVATION = "information_preservation"
    LOCAL_GLOBAL_CONFLICT = "local_global_conflict"
    RECOVERY_BRANCH = "recovery_branch"


class ProgramNecessityLineageRole(StrEnum):
    """Whether one independent world informs development or frozen replication."""

    DEVELOPMENT = "development"
    REPLICATION = "replication"


class ProgramNecessityArmTemplateRef(ContentAddressedModel):
    """Evergreen family-level construction identity for one confirmatory arm."""

    schema_version: Literal["aecbench.program-necessity-arm-template-ref.v1"] = (
        "aecbench.program-necessity-arm-template-ref.v1"
    )
    template_id: NonEmptyStr
    arm: ProgramNecessityArm
    candidate_kind: ProgramCandidateKind
    template_artifact_sha256: str

    @field_validator("template_artifact_sha256")
    @classmethod
    def validate_template_artifact(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_candidate_kind(self) -> Self:
        expected = (
            ProgramCandidateKind.INCUMBENT
            if self.arm is ProgramNecessityArm.MONOLITHIC
            else ProgramCandidateKind.PROPOSAL
        )
        if self.candidate_kind is not expected:
            raise ValueError(
                "program-necessity arm template has the wrong candidate kind",
            )
        return self


class ProgramTopologyProfile(ContentAddressedModel):
    """Small topology signature used only when sham topology matching is feasible."""

    schema_version: Literal["aecbench.program-topology-profile.v1"] = "aecbench.program-topology-profile.v1"
    edge_count: int = Field(ge=0)
    max_depth: int = Field(ge=1)
    max_width: int = Field(ge=1)
    max_fan_in: int = Field(ge=0)
    max_fan_out: int = Field(ge=0)


class ProgramComplexityDerivationRef(ContentAddressedModel):
    """Auditable derivation receipt over exact graph, source, and budget bytes."""

    schema_version: Literal["aecbench.program-complexity-derivation-ref.v1"] = (
        "aecbench.program-complexity-derivation-ref.v1"
    )
    derivation_id: NonEmptyStr
    candidate_artifact_sha256: str
    program_graph_sha256: str
    source_scope_sha256: str
    aggregate_budget_sha256: str
    measurement_policy_sha256: str
    derivation_receipt_sha256: str
    derived_from_actual_artifacts: Literal[True]

    @field_validator(
        "candidate_artifact_sha256",
        "program_graph_sha256",
        "source_scope_sha256",
        "aggregate_budget_sha256",
        "measurement_policy_sha256",
        "derivation_receipt_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class ProgramComplexityEvidence(ContentAddressedModel):
    """Measured program shape bound to the artifacts from which it was derived."""

    schema_version: Literal["aecbench.program-complexity-evidence.v1"] = "aecbench.program-complexity-evidence.v1"
    candidate: ProgramCandidateRef
    derivation: ProgramComplexityDerivationRef
    node_count: int = Field(ge=1)
    model_invocation_count: int = Field(ge=1)
    aggregate_budget: HarnessBudget
    input_token_mass: int = Field(ge=1)
    context_duplication_tokens: int = Field(ge=0)
    finalizer_sha256: str
    output_contract_sha256: str
    topology: ProgramTopologyProfile | None = None

    @field_validator("finalizer_sha256", "output_contract_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_derivation(self) -> Self:
        if self.derivation.candidate_artifact_sha256 != self.candidate.candidate_artifact_sha256:
            raise ValueError(
                "complexity derivation does not bind the actual candidate artifact",
            )
        budget_sha256 = canonical_content_sha256(
            self.aggregate_budget.model_dump(mode="json"),
        )
        if self.derivation.aggregate_budget_sha256 != budget_sha256:
            raise ValueError(
                "complexity derivation does not bind the actual aggregate budget",
            )
        return self


class ShamMatchAttestation(ContentAddressedModel):
    """Host evidence that sham and structural arms differ mainly in semantics."""

    schema_version: Literal["aecbench.sham-match-attestation.v1"] = "aecbench.sham-match-attestation.v1"
    attestation_id: NonEmptyStr
    sham_evidence: ProgramComplexityEvidence
    structural_evidence: ProgramComplexityEvidence
    max_input_token_mass_relative_delta: FiniteFloat = Field(
        ge=0.0,
        le=1.0,
    )
    max_context_duplication_relative_delta: FiniteFloat = Field(
        ge=0.0,
        le=1.0,
    )
    topology_match_required: bool
    matched: Literal[True]

    @model_validator(mode="after")
    def validate_match(self) -> Self:
        sham = self.sham_evidence
        structural = self.structural_evidence
        _validate_sham_identity(sham=sham, structural=structural)
        _validate_sham_shape(sham=sham, structural=structural)
        _validate_sham_tolerances(
            sham=sham,
            structural=structural,
            max_input_token_mass_relative_delta=(self.max_input_token_mass_relative_delta),
            max_context_duplication_relative_delta=(self.max_context_duplication_relative_delta),
            topology_match_required=self.topology_match_required,
        )
        return self


def _validate_sham_identity(
    *,
    sham: ProgramComplexityEvidence,
    structural: ProgramComplexityEvidence,
) -> None:
    if sham.candidate == structural.candidate:
        raise ValueError(
            "sham and structural evidence require distinct candidates",
        )
    if (
        sham.candidate.kind is not ProgramCandidateKind.PROPOSAL
        or structural.candidate.kind is not ProgramCandidateKind.PROPOSAL
    ):
        raise ValueError(
            "sham and structural complexity evidence require proposal candidates",
        )
    if sham.derivation.source_scope_sha256 != structural.derivation.source_scope_sha256:
        raise ValueError(
            "sham and structural complexity evidence must share one source scope",
        )
    if sham.derivation.measurement_policy_sha256 != structural.derivation.measurement_policy_sha256:
        raise ValueError(
            "sham and structural complexity evidence must share one measurement policy",
        )


def _validate_sham_shape(
    *,
    sham: ProgramComplexityEvidence,
    structural: ProgramComplexityEvidence,
) -> None:
    if sham.node_count != structural.node_count or sham.model_invocation_count != structural.model_invocation_count:
        raise ValueError(
            "sham and structural node and invocation counts must match",
        )
    if sham.aggregate_budget != structural.aggregate_budget:
        raise ValueError(
            "sham and structural aggregate budgets must match",
        )
    if (
        sham.finalizer_sha256 != structural.finalizer_sha256
        or sham.output_contract_sha256 != structural.output_contract_sha256
    ):
        raise ValueError(
            "sham and structural finalizer and output contract must match",
        )


def _validate_sham_tolerances(
    *,
    sham: ProgramComplexityEvidence,
    structural: ProgramComplexityEvidence,
    max_input_token_mass_relative_delta: float,
    max_context_duplication_relative_delta: float,
    topology_match_required: bool,
) -> None:
    if (
        _relative_delta(
            sham.input_token_mass,
            structural.input_token_mass,
        )
        > max_input_token_mass_relative_delta
    ):
        raise ValueError(
            "sham and structural input-token mass exceeds its tolerance",
        )
    if (
        _relative_delta(
            sham.context_duplication_tokens,
            structural.context_duplication_tokens,
        )
        > max_context_duplication_relative_delta
    ):
        raise ValueError(
            "sham and structural context duplication exceeds its tolerance",
        )
    if topology_match_required and (
        sham.topology is None or structural.topology is None or sham.topology != structural.topology
    ):
        raise ValueError(
            "sham and structural topology profiles must match when required",
        )


class ProgramNecessityProblemViewRef(ContentAddressedModel):
    """Opaque problem-view identity tied to one exact public task snapshot."""

    schema_version: Literal["aecbench.program-necessity-problem-view-ref.v1"] = (
        "aecbench.program-necessity-problem-view-ref.v1"
    )
    problem_id: NonEmptyStr
    problem_view_sha256: str
    task_id: NonEmptyStr
    task_revision: str
    public_task_snapshot_sha256: str
    fixed_harness_projection_sha256: str

    @field_validator(
        "problem_view_sha256",
        "task_revision",
        "public_task_snapshot_sha256",
        "fixed_harness_projection_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class ProgramNecessityLineageCandidateRef(ContentAddressedModel):
    """One lineage-specific candidate tied to its family arm template."""

    schema_version: Literal["aecbench.program-necessity-lineage-candidate-ref.v1"] = (
        "aecbench.program-necessity-lineage-candidate-ref.v1"
    )
    arm: ProgramNecessityArm
    template_ref_sha256: str
    candidate: ProgramCandidateRef

    @field_validator("template_ref_sha256")
    @classmethod
    def validate_template_ref(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_candidate_kind(self) -> Self:
        expected = (
            ProgramCandidateKind.INCUMBENT
            if self.arm is ProgramNecessityArm.MONOLITHIC
            else ProgramCandidateKind.PROPOSAL
        )
        if self.candidate.kind is not expected:
            raise ValueError(
                "lineage candidate kind does not match its program-necessity arm",
            )
        return self


class ProgramNecessityExecutionScheduleRef(ContentAddressedModel):
    """Exact identity of one lineage-specific executable candidate matrix."""

    schema_version: Literal["aecbench.program-necessity-execution-schedule-ref.v1"] = (
        "aecbench.program-necessity-execution-schedule-ref.v1"
    )
    schedule_id: NonEmptyStr
    schedule_sha256: str
    kernel_sha256: str
    fixed_harness_sha256: str
    evaluation_plan_ref: EvaluationPlanRef
    world_lineage_id: str
    candidate_ref_sha256s: tuple[str, ...] = Field(
        min_length=3,
        max_length=3,
    )
    coordinate_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "schedule_sha256",
        "kernel_sha256",
        "fixed_harness_sha256",
        "world_lineage_id",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("candidate_ref_sha256s", "coordinate_sha256s")
    @classmethod
    def canonicalize_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError(
                "execution schedule identities must be unique",
            )
        return tuple(sorted(value))


class ProgramNecessityStudyRef(ContentAddressedModel):
    """Exact identity of one completed lineage-specific matched study."""

    schema_version: Literal["aecbench.program-necessity-study-ref.v2"] = "aecbench.program-necessity-study-ref.v2"
    study_id: NonEmptyStr
    study_sha256: str
    execution_schedule_ref_sha256: str
    evaluation_plan_ref: EvaluationPlanRef
    world_lineage_id: str
    candidate_ref_sha256s: tuple[str, ...] = Field(
        min_length=3,
        max_length=3,
    )
    coordinate_sha256s: tuple[str, ...] = Field(min_length=1)

    @field_validator(
        "study_sha256",
        "execution_schedule_ref_sha256",
        "world_lineage_id",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("candidate_ref_sha256s", "coordinate_sha256s")
    @classmethod
    def canonicalize_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("program-necessity study identities must be unique")
        return tuple(sorted(value))


class ProgramNecessityLineagePlan(ContentAddressedModel):
    """Exact executable three-arm plan for one independent task world."""

    schema_version: Literal["aecbench.program-necessity-lineage-plan.v1"] = "aecbench.program-necessity-lineage-plan.v1"
    lineage_plan_id: NonEmptyStr
    world_lineage_id: str
    role: ProgramNecessityLineageRole
    task_snapshot: TaskSnapshotRef
    problem_view: ProgramNecessityProblemViewRef
    candidate_refs: tuple[ProgramNecessityLineageCandidateRef, ...] = Field(
        min_length=3,
        max_length=3,
    )
    evaluation_seeds: tuple[int, ...] = Field(min_length=1)
    repetitions_per_seed: int = Field(ge=1)
    coordinates: tuple[MatchedEvaluationCoordinate, ...] = Field(min_length=1)
    execution_schedule_ref: ProgramNecessityExecutionScheduleRef
    study_ref: ProgramNecessityStudyRef
    sham_match: ShamMatchAttestation

    @field_validator("world_lineage_id")
    @classmethod
    def validate_world_lineage_id(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("candidate_refs")
    @classmethod
    def canonicalize_candidates(
        cls,
        value: tuple[ProgramNecessityLineageCandidateRef, ...],
    ) -> tuple[ProgramNecessityLineageCandidateRef, ...]:
        arms = tuple(candidate.arm for candidate in value)
        ids = tuple(candidate.candidate.candidate_id for candidate in value)
        hashes = tuple(candidate.candidate.content_sha256 for candidate in value)
        if set(arms) != set(ProgramNecessityArm):
            raise ValueError(
                "lineage plan requires exactly one candidate for every arm",
            )
        if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
            raise ValueError("lineage candidates must be unique")
        return tuple(sorted(value, key=lambda candidate: candidate.arm.value))

    @field_validator("evaluation_seeds")
    @classmethod
    def canonicalize_seeds(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if any(seed < 0 for seed in value):
            raise ValueError("program-necessity seeds cannot be negative")
        if len(value) != len(set(value)):
            raise ValueError("program-necessity seeds must be unique")
        return tuple(sorted(value))

    @field_validator("coordinates")
    @classmethod
    def canonicalize_coordinates(
        cls,
        value: tuple[MatchedEvaluationCoordinate, ...],
    ) -> tuple[MatchedEvaluationCoordinate, ...]:
        ids = tuple(coordinate.coordinate_id for coordinate in value)
        hashes = tuple(coordinate.content_sha256 for coordinate in value)
        if len(ids) != len(set(ids)) or len(hashes) != len(set(hashes)):
            raise ValueError(
                "program-necessity coordinates must be unique",
            )
        return tuple(sorted(value, key=lambda coordinate: coordinate.coordinate_id))

    @model_validator(mode="after")
    def validate_exact_lineage(self) -> Self:
        snapshot = self.task_snapshot
        view = self.problem_view
        if (
            view.task_id != snapshot.task_id
            or view.task_revision != snapshot.definition_sha256
            or view.public_task_snapshot_sha256 != graph_hidden_task_snapshot_sha256(snapshot)
        ):
            raise ValueError(
                "program-necessity problem view does not bind its task snapshot",
            )

        actual_coordinates = {
            (
                coordinate.seed,
                coordinate.repetition,
            )
            for coordinate in self.coordinates
        }
        expected_coordinates = {
            (seed, repetition) for seed in self.evaluation_seeds for repetition in range(self.repetitions_per_seed)
        }
        if actual_coordinates != expected_coordinates or any(
            coordinate.task_id != snapshot.task_id
            or coordinate.task_revision != snapshot.definition_sha256
            or coordinate.world_lineage_id != self.world_lineage_id
            for coordinate in self.coordinates
        ):
            raise ValueError(
                "lineage plan requires exact seed and repetition coordinates",
            )

        candidate_sha256s = tuple(
            sorted(candidate.candidate.content_sha256 for candidate in self.candidate_refs),
        )
        coordinate_sha256s = tuple(
            sorted(coordinate.content_sha256 for coordinate in self.coordinates),
        )
        schedule = self.execution_schedule_ref
        if (
            schedule.world_lineage_id != self.world_lineage_id
            or schedule.candidate_ref_sha256s != candidate_sha256s
            or schedule.coordinate_sha256s != coordinate_sha256s
        ):
            raise ValueError(
                "execution schedule does not bind the exact lineage matrix",
            )
        study = self.study_ref
        if (
            study.execution_schedule_ref_sha256 != schedule.content_sha256
            or study.evaluation_plan_ref != schedule.evaluation_plan_ref
            or study.world_lineage_id != self.world_lineage_id
            or study.candidate_ref_sha256s != candidate_sha256s
            or study.coordinate_sha256s != coordinate_sha256s
        ):
            raise ValueError(
                "program-necessity study does not bind the exact schedule",
            )

        if self.sham_match.sham_evidence.candidate != self.candidate_for(
            ProgramNecessityArm.SHAM
        ) or self.sham_match.structural_evidence.candidate != self.candidate_for(ProgramNecessityArm.STRUCTURAL):
            raise ValueError(
                "sham match evidence does not bind the lineage candidates",
            )
        return self

    def candidate_binding_for(
        self,
        arm: ProgramNecessityArm,
    ) -> ProgramNecessityLineageCandidateRef:
        """Resolve one exact lineage candidate and its family template binding."""
        return next(candidate for candidate in self.candidate_refs if candidate.arm is arm)

    def candidate_for(
        self,
        arm: ProgramNecessityArm,
    ) -> ProgramCandidateRef:
        """Resolve one exact lineage-specific program candidate."""
        return self.candidate_binding_for(arm).candidate


class ProgramNecessityFamilyPlan(ContentAddressedModel):
    """Frozen templates and independent executable worlds for one task mechanism."""

    schema_version: Literal["aecbench.program-necessity-family-plan.v2"] = "aecbench.program-necessity-family-plan.v2"
    family_id: NonEmptyStr
    mechanism: ProgramNecessityMechanism
    arm_templates: tuple[ProgramNecessityArmTemplateRef, ...] = Field(
        min_length=3,
        max_length=3,
    )
    lineage_plans: tuple[ProgramNecessityLineagePlan, ...] = Field(
        min_length=2,
    )
    expected_structural_direction: Literal["positive"]
    preregistered: Literal[True]

    @field_validator("arm_templates")
    @classmethod
    def canonicalize_templates(
        cls,
        value: tuple[ProgramNecessityArmTemplateRef, ...],
    ) -> tuple[ProgramNecessityArmTemplateRef, ...]:
        arms = tuple(template.arm for template in value)
        identities = tuple(template.content_sha256 for template in value)
        if set(arms) != set(ProgramNecessityArm):
            raise ValueError(
                "family plan requires exactly one template for every arm",
            )
        if len(identities) != len(set(identities)):
            raise ValueError(
                "program-necessity arm templates must be unique",
            )
        return tuple(sorted(value, key=lambda template: template.arm.value))

    @field_validator("lineage_plans")
    @classmethod
    def canonicalize_lineages(
        cls,
        value: tuple[ProgramNecessityLineagePlan, ...],
    ) -> tuple[ProgramNecessityLineagePlan, ...]:
        world_ids = tuple(lineage.world_lineage_id for lineage in value)
        plan_ids = tuple(lineage.lineage_plan_id for lineage in value)
        if len(world_ids) != len(set(world_ids)) or len(plan_ids) != len(set(plan_ids)):
            raise ValueError(
                "program-necessity family lineages must be independent",
            )
        return tuple(
            sorted(
                value,
                key=lambda lineage: (
                    lineage.role is ProgramNecessityLineageRole.REPLICATION,
                    lineage.world_lineage_id,
                ),
            ),
        )

    @model_validator(mode="after")
    def validate_family(self) -> Self:
        development = self.development_lineages
        replication = tuple(
            lineage for lineage in self.lineage_plans if lineage.role is ProgramNecessityLineageRole.REPLICATION
        )
        if not development or not replication:
            raise ValueError(
                "program necessity requires development and fresh replication lineages",
            )

        templates_by_arm = {template.arm: template for template in self.arm_templates}
        candidate_hashes: list[str] = []
        candidate_ids: list[str] = []
        for lineage in self.lineage_plans:
            for candidate in lineage.candidate_refs:
                template = templates_by_arm[candidate.arm]
                if (
                    candidate.template_ref_sha256 != template.content_sha256
                    or candidate.candidate.kind is not template.candidate_kind
                ):
                    raise ValueError(
                        "lineage candidate does not bind its family arm template",
                    )
                candidate_hashes.append(candidate.candidate.content_sha256)
                candidate_ids.append(candidate.candidate.candidate_id)
        if len(candidate_hashes) != len(set(candidate_hashes)) or len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError(
                "program-necessity family lineage candidates must be unique",
            )
        return self

    @property
    def development_lineages(
        self,
    ) -> tuple[ProgramNecessityLineagePlan, ...]:
        """Return the three independent development worlds."""
        return tuple(
            lineage for lineage in self.lineage_plans if lineage.role is ProgramNecessityLineageRole.DEVELOPMENT
        )

    @property
    def replication_lineage(self) -> ProgramNecessityLineagePlan:
        """Return the sole replication world used by the historical v1 design."""

        replication = self.replication_lineages
        if len(replication) != 1:
            raise ValueError(
                "replication_lineage requires a design with exactly one replication",
            )
        return replication[0]

    @property
    def replication_lineages(
        self,
    ) -> tuple[ProgramNecessityLineagePlan, ...]:
        """Return the independent frozen replication worlds."""

        return tuple(
            lineage for lineage in self.lineage_plans if lineage.role is ProgramNecessityLineageRole.REPLICATION
        )

    @property
    def all_lineage_ids(self) -> tuple[str, ...]:
        """Return every exact world identity in canonical family order."""
        return tuple(lineage.world_lineage_id for lineage in self.lineage_plans)

    def lineage_for(self, world_lineage_id: str) -> ProgramNecessityLineagePlan:
        """Resolve one exact executable lineage plan."""
        return next(lineage for lineage in self.lineage_plans if lineage.world_lineage_id == world_lineage_id)


class ProgramNecessityMeasurementPolicy(ContentAddressedModel):
    """Frozen estimand and aggregation semantics for the confirmatory study."""

    schema_version: Literal["aecbench.program-necessity-measurement-policy.v1"] = (
        "aecbench.program-necessity-measurement-policy.v1"
    )
    unit_of_analysis: Literal["world_lineage"] = "world_lineage"
    within_lineage_aggregation: Literal["arithmetic_mean_across_seed_repetitions"] = (
        "arithmetic_mean_across_seed_repetitions"
    )
    splitting_estimand: Literal["sham_minus_monolithic"] = "sham_minus_monolithic"
    structural_estimand: Literal["structural_minus_sham"] = "structural_minus_sham"
    total_program_estimand: Literal["structural_minus_monolithic"] = "structural_minus_monolithic"
    directional_threshold: Literal["strictly_positive"] = "strictly_positive"
    report_full_family_distribution: Literal[True] = True


class ProgramNecessityMissingDataPolicy(ContentAddressedModel):
    """Fail-closed handling for absent, invalid, or compromised evidence."""

    schema_version: Literal["aecbench.program-necessity-missing-data-policy.v1"] = (
        "aecbench.program-necessity-missing-data-policy.v1"
    )
    imputation: Literal["forbidden"] = "forbidden"
    incomplete_lineage: Literal["invalidate_family"] = "invalidate_family"
    invalid_evidence: Literal["invalidate_family"] = "invalidate_family"
    any_invalid_family: Literal["close_campaign_gate"] = "close_campaign_gate"


class ProgramNecessityDesign(ContentAddressedModel):
    """Phase-neutral family, lineage, replication, and opening requirements."""

    schema_version: Literal["aecbench.program-necessity-design.v1"] = "aecbench.program-necessity-design.v1"
    family_count: int = Field(ge=1)
    development_lineages_per_family: int = Field(ge=1)
    replication_lineages_per_family: int = Field(ge=1)
    required_qualifying_family_count: int = Field(ge=1)
    required_distinct_mechanism_count: int = Field(ge=1)
    required_mechanisms: tuple[ProgramNecessityMechanism, ...] = Field(
        min_length=1,
    )
    measurement_policy_sha256: str
    missing_data_policy_sha256: str
    development_rule: Literal["all_development_lineages_positive"] = "all_development_lineages_positive"
    replication_rule: Literal["all_replication_lineages_positive"] = "all_replication_lineages_positive"
    evidence_rule: Literal["all_families_valid"] = "all_families_valid"

    @field_validator(
        "measurement_policy_sha256",
        "missing_data_policy_sha256",
    )
    @classmethod
    def validate_policy_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("required_mechanisms")
    @classmethod
    def canonicalize_required_mechanisms(
        cls,
        value: tuple[ProgramNecessityMechanism, ...],
    ) -> tuple[ProgramNecessityMechanism, ...]:
        if len(value) != len(set(value)):
            raise ValueError(
                "program-necessity design mechanisms must be unique",
            )
        return tuple(sorted(value, key=lambda mechanism: mechanism.value))

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.required_qualifying_family_count > self.family_count:
            raise ValueError(
                "qualifying-family threshold cannot exceed the study family count",
            )
        if self.required_distinct_mechanism_count > len(
            self.required_mechanisms,
        ):
            raise ValueError(
                "distinct-mechanism threshold cannot exceed required mechanisms",
            )
        if self.required_distinct_mechanism_count > self.required_qualifying_family_count:
            raise ValueError(
                "distinct-mechanism threshold cannot exceed qualifying families",
            )
        if len(self.required_mechanisms) > self.family_count:
            raise ValueError(
                "required mechanisms cannot outnumber study families",
            )
        return self


class ProgramNecessityOpeningPolicy(ContentAddressedModel):
    """Preregistered family-level directional replication gate."""

    schema_version: Literal["aecbench.program-necessity-opening-policy.v1"] = (
        "aecbench.program-necessity-opening-policy.v1"
    )
    required_qualifying_family_count: Literal[2] = 2
    required_distinct_mechanism_count: Literal[2] = 2
    development_rule: Literal["all_three_lineages_positive"] = "all_three_lineages_positive"
    replication_rule: Literal["fresh_lineage_positive"] = "fresh_lineage_positive"
    evidence_rule: Literal["all_families_valid"] = "all_families_valid"


class ProgramNecessityStudyPlan(ContentAddressedModel):
    """Phase-neutral preregistration governed by an explicit study design."""

    schema_version: Literal["aecbench.program-necessity-study-plan.v1"] = "aecbench.program-necessity-study-plan.v1"
    study_id: NonEmptyStr
    kernel_sha256: str
    fixed_harness_sha256: str
    evaluation_plan_ref: EvaluationPlanRef
    monitor_policy_sha256: str
    monitor_cycle_plan_sha256: str
    monitor_instrumentation_sha256: str
    design: ProgramNecessityDesign
    family_plans: tuple[ProgramNecessityFamilyPlan, ...] = Field(min_length=1)
    measurement_policy: ProgramNecessityMeasurementPolicy
    missing_data_policy: ProgramNecessityMissingDataPolicy
    preregistered: Literal[True]

    @field_validator(
        "kernel_sha256",
        "fixed_harness_sha256",
        "monitor_policy_sha256",
        "monitor_cycle_plan_sha256",
        "monitor_instrumentation_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("family_plans")
    @classmethod
    def canonicalize_family_plans(
        cls,
        value: tuple[ProgramNecessityFamilyPlan, ...],
    ) -> tuple[ProgramNecessityFamilyPlan, ...]:
        family_ids = tuple(family.family_id for family in value)
        if len(family_ids) != len(set(family_ids)):
            raise ValueError(
                "program-necessity family identities must be unique",
            )
        lineage_ids = tuple(lineage.world_lineage_id for family in value for lineage in family.lineage_plans)
        if len(lineage_ids) != len(set(lineage_ids)):
            raise ValueError(
                "program necessity requires disjoint world lineages",
            )
        return tuple(sorted(value, key=lambda family: family.family_id))

    @model_validator(mode="after")
    def validate_design_and_execution_planes(self) -> Self:
        design = self.design
        if (
            design.measurement_policy_sha256 != self.measurement_policy.content_sha256
            or design.missing_data_policy_sha256 != self.missing_data_policy.content_sha256
        ):
            raise ValueError(
                "program-necessity design does not bind its measurement and missing-data policies",
            )
        if len(self.family_plans) != design.family_count:
            raise ValueError(
                "program-necessity family count differs from its design",
            )
        if {family.mechanism for family in self.family_plans} != set(
            design.required_mechanisms,
        ):
            raise ValueError(
                "program-necessity mechanisms differ from its design",
            )
        for family in self.family_plans:
            if (
                len(family.development_lineages) != design.development_lineages_per_family
                or len(family.replication_lineages) != design.replication_lineages_per_family
            ):
                raise ValueError(
                    "program-necessity lineage counts differ from its design",
                )
            for lineage in family.lineage_plans:
                schedule = lineage.execution_schedule_ref
                study = lineage.study_ref
                if (
                    schedule.kernel_sha256 != self.kernel_sha256
                    or schedule.fixed_harness_sha256 != self.fixed_harness_sha256
                    or schedule.evaluation_plan_ref != self.evaluation_plan_ref
                    or study.evaluation_plan_ref != self.evaluation_plan_ref
                ):
                    raise ValueError(
                        "lineage schedule or study does not bind the preregistered kernel, H0, or evaluation",
                    )
        return self


class ProgramNecessityPreregistration(ContentAddressedModel):
    """Top-level freeze for all six families and all evaluation-plane identities."""

    schema_version: Literal["aecbench.program-necessity-preregistration.v1"] = (
        "aecbench.program-necessity-preregistration.v1"
    )
    preregistration_id: NonEmptyStr
    kernel_sha256: str
    fixed_harness_sha256: str
    evaluation_plan_ref: EvaluationPlanRef
    monitor_policy_sha256: str
    monitor_cycle_plan_sha256: str
    monitor_instrumentation_sha256: str
    family_plans: tuple[ProgramNecessityFamilyPlan, ...] = Field(
        min_length=6,
        max_length=6,
    )
    measurement_policy: ProgramNecessityMeasurementPolicy
    missing_data_policy: ProgramNecessityMissingDataPolicy
    opening_policy: ProgramNecessityOpeningPolicy
    preregistered: Literal[True]

    @field_validator(
        "kernel_sha256",
        "fixed_harness_sha256",
        "monitor_policy_sha256",
        "monitor_cycle_plan_sha256",
        "monitor_instrumentation_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("family_plans")
    @classmethod
    def canonicalize_family_plans(
        cls,
        value: tuple[ProgramNecessityFamilyPlan, ...],
    ) -> tuple[ProgramNecessityFamilyPlan, ...]:
        family_ids = tuple(family.family_id for family in value)
        if len(family_ids) != len(set(family_ids)):
            raise ValueError(
                "program-necessity family identities must be unique",
            )
        if {family.mechanism for family in value} != set(
            ProgramNecessityMechanism,
        ):
            raise ValueError(
                "program necessity requires one family for every mechanism",
            )
        if any(len(family.development_lineages) != 3 or len(family.replication_lineages) != 1 for family in value):
            raise ValueError(
                "historical program necessity requires three development lineages and one fresh replication",
            )
        lineage_ids = tuple(lineage.world_lineage_id for family in value for lineage in family.lineage_plans)
        if len(lineage_ids) != 24 or len(lineage_ids) != len(set(lineage_ids)):
            raise ValueError(
                "program necessity requires 24 disjoint world lineages",
            )
        return tuple(sorted(value, key=lambda family: family.family_id))

    @model_validator(mode="after")
    def validate_execution_planes(self) -> Self:
        for family in self.family_plans:
            for lineage in family.lineage_plans:
                schedule = lineage.execution_schedule_ref
                study = lineage.study_ref
                if (
                    schedule.kernel_sha256 != self.kernel_sha256
                    or schedule.fixed_harness_sha256 != self.fixed_harness_sha256
                    or schedule.evaluation_plan_ref != self.evaluation_plan_ref
                    or study.evaluation_plan_ref != self.evaluation_plan_ref
                ):
                    raise ValueError(
                        "lineage schedule or study does not bind the preregistered kernel, H0, or evaluation",
                    )
        return self


class ProgramNecessityObservation(ContentAddressedModel):
    """One utility bound to an exact lineage, candidate, study, and outcome."""

    schema_version: Literal["aecbench.program-necessity-observation.v2"] = "aecbench.program-necessity-observation.v2"
    observation_id: NonEmptyStr
    family_id: NonEmptyStr
    world_lineage_id: str
    lineage_plan_sha256: str
    arm: ProgramNecessityArm
    candidate: ProgramCandidateRef
    study_ref_sha256: str
    evaluation_plan_ref: EvaluationPlanRef
    matched_evidence_ref: MatchedCandidateEvidenceRef
    utility: FiniteFloat
    validity_passed: bool
    integrity_passed: bool

    @field_validator(
        "world_lineage_id",
        "lineage_plan_sha256",
        "study_ref_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_evidence_binding(self) -> Self:
        evidence = self.matched_evidence_ref
        if evidence.candidate_id != self.candidate.candidate_id:
            raise ValueError(
                "observation evidence does not bind its candidate",
            )
        if self.integrity_passed != evidence.integrity_passed:
            raise ValueError(
                "observation integrity does not match its evidence",
            )
        if self.validity_passed and not evidence.evidence_complete:
            raise ValueError(
                "valid observation requires complete matched evidence",
            )
        return self


class ProgramNecessityLineageContrast(ContentAddressedModel):
    """Lineage-level arm means and the three preregistered contrasts."""

    schema_version: Literal["aecbench.program-necessity-lineage-contrast.v1"] = (
        "aecbench.program-necessity-lineage-contrast.v1"
    )
    world_lineage_id: str
    role: ProgramNecessityLineageRole
    monolithic_mean: FiniteFloat
    sham_mean: FiniteFloat
    structural_mean: FiniteFloat
    splitting_value: FiniteFloat
    structural_residual: FiniteFloat
    total_program_value: FiniteFloat
    validity_passed: bool
    integrity_passed: bool

    @field_validator("world_lineage_id")
    @classmethod
    def validate_world_lineage_id(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_contrasts(self) -> Self:
        expected = (
            self.sham_mean - self.monolithic_mean,
            self.structural_mean - self.sham_mean,
            self.structural_mean - self.monolithic_mean,
        )
        observed = (
            self.splitting_value,
            self.structural_residual,
            self.total_program_value,
        )
        if any(
            not math.isclose(
                actual,
                target,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            for actual, target in zip(observed, expected, strict=True)
        ):
            raise ValueError(
                "program-necessity contrasts do not match their arm means",
            )
        return self


def _relative_delta(left: int, right: int) -> float:
    return abs(left - right) / max(left, right, 1)
