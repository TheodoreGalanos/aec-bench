# ABOUTME: Reduces complete program-necessity observations into family and study results.
# ABOUTME: Applies explicit design gates while retaining historical result compatibility.

from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.qualification.program_necessity.contracts import (
    ProgramNecessityArm,
    ProgramNecessityFamilyPlan,
    ProgramNecessityLineageContrast,
    ProgramNecessityLineageRole,
    ProgramNecessityMechanism,
    ProgramNecessityObservation,
    ProgramNecessityPreregistration,
    ProgramNecessityStudyPlan,
)


class ProgramNecessityFamilyResult(LegacyContentAddressedModel):
    """Complete family distribution with development and fresh replication."""

    schema_version: Literal["aecbench.program-necessity-family-result.v2"] = (
        "aecbench.program-necessity-family-result.v2"
    )
    plan: ProgramNecessityFamilyPlan
    observations: tuple[ProgramNecessityObservation, ...] = Field(min_length=1)
    lineage_contrasts: tuple[ProgramNecessityLineageContrast, ...] = Field(
        min_length=2,
    )
    evidence_valid: bool
    development_direction_consistent: bool
    replication_direction_confirmed: bool
    qualifies: bool

    @field_validator("observations")
    @classmethod
    def canonicalize_observations(
        cls,
        value: tuple[ProgramNecessityObservation, ...],
    ) -> tuple[ProgramNecessityObservation, ...]:
        keys = tuple(
            (
                item.review_lineage_id,
                item.matched_evidence_ref.coordinate_sha256,
                item.arm,
            )
            for item in value
        )
        if len(keys) != len(set(keys)):
            raise ValueError(
                "program-necessity observations must be unique by lineage, coordinate, and arm",
            )
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.review_lineage_id,
                    item.matched_evidence_ref.coordinate_sha256,
                    item.arm.value,
                ),
            ),
        )

    @field_validator("lineage_contrasts")
    @classmethod
    def canonicalize_lineage_contrasts(
        cls,
        value: tuple[ProgramNecessityLineageContrast, ...],
    ) -> tuple[ProgramNecessityLineageContrast, ...]:
        if len({item.review_lineage_id for item in value}) != len(value):
            raise ValueError(
                "program-necessity contrasts must be unique by lineage",
            )
        return tuple(sorted(value, key=lambda item: item.review_lineage_id))

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        derived = _derive_family(
            plan=self.plan,
            observations=self.observations,
        )
        if self.lineage_contrasts != derived.lineage_contrasts:
            raise ValueError(
                "family result contrasts do not match complete arm observations",
            )
        flags = (
            self.evidence_valid,
            self.development_direction_consistent,
            self.replication_direction_confirmed,
            self.qualifies,
        )
        expected = (
            derived.evidence_valid,
            derived.development_direction_consistent,
            derived.replication_direction_confirmed,
            derived.qualifies,
        )
        if flags != expected:
            raise ValueError(
                "family result flags do not match its lineage distribution",
            )
        return self


class ProgramNecessityStudyResult(LegacyContentAddressedModel):
    """Complete phase-neutral study result under its explicit design."""

    schema_version: Literal["aecbench.program-necessity-study-result.v1"] = "aecbench.program-necessity-study-result.v1"
    plan: ProgramNecessityStudyPlan
    family_results: tuple[ProgramNecessityFamilyResult, ...] = Field(
        min_length=1,
    )
    qualifying_family_ids: tuple[NonEmptyStr, ...]
    qualifying_mechanisms: tuple[ProgramNecessityMechanism, ...]
    all_evidence_valid: bool
    gate_open: bool

    @field_validator("family_results")
    @classmethod
    def canonicalize_family_results(
        cls,
        value: tuple[ProgramNecessityFamilyResult, ...],
    ) -> tuple[ProgramNecessityFamilyResult, ...]:
        return _canonicalize_family_results(value)

    @field_validator("qualifying_family_ids")
    @classmethod
    def canonicalize_qualifying_family_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _canonicalize_qualifying_family_ids(value)

    @field_validator("qualifying_mechanisms")
    @classmethod
    def canonicalize_qualifying_mechanisms(
        cls,
        value: tuple[ProgramNecessityMechanism, ...],
    ) -> tuple[ProgramNecessityMechanism, ...]:
        return _canonicalize_qualifying_mechanisms(value)

    @model_validator(mode="after")
    def validate_gate(self) -> Self:
        _validate_family_result_coverage(
            family_plans=self.plan.family_plans,
            family_results=self.family_results,
        )
        summary = _derive_gate_summary(
            family_results=self.family_results,
            required_qualifying_family_count=(self.plan.design.required_qualifying_family_count),
            required_distinct_mechanism_count=(self.plan.design.required_distinct_mechanism_count),
        )
        _validate_gate_summary(
            qualifying_family_ids=self.qualifying_family_ids,
            qualifying_mechanisms=self.qualifying_mechanisms,
            all_evidence_valid=self.all_evidence_valid,
            gate_open=self.gate_open,
            expected=summary,
        )
        return self


class ProgramNecessityGateResult(LegacyContentAddressedModel):
    """Historical complete campaign result with exact six-family cardinality."""

    schema_version: Literal["aecbench.program-necessity-gate-result.v2"] = "aecbench.program-necessity-gate-result.v2"
    plan: ProgramNecessityPreregistration
    family_results: tuple[ProgramNecessityFamilyResult, ...] = Field(
        min_length=6,
        max_length=6,
    )
    qualifying_family_ids: tuple[NonEmptyStr, ...]
    qualifying_mechanisms: tuple[ProgramNecessityMechanism, ...]
    all_evidence_valid: bool
    gate_open: bool

    @field_validator("family_results")
    @classmethod
    def canonicalize_family_results(
        cls,
        value: tuple[ProgramNecessityFamilyResult, ...],
    ) -> tuple[ProgramNecessityFamilyResult, ...]:
        return _canonicalize_family_results(value)

    @field_validator("qualifying_family_ids")
    @classmethod
    def canonicalize_qualifying_family_ids(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return _canonicalize_qualifying_family_ids(value)

    @field_validator("qualifying_mechanisms")
    @classmethod
    def canonicalize_qualifying_mechanisms(
        cls,
        value: tuple[ProgramNecessityMechanism, ...],
    ) -> tuple[ProgramNecessityMechanism, ...]:
        return _canonicalize_qualifying_mechanisms(value)

    @model_validator(mode="after")
    def validate_gate(self) -> Self:
        _validate_family_result_coverage(
            family_plans=self.plan.family_plans,
            family_results=self.family_results,
        )
        policy = self.plan.opening_policy
        summary = _derive_gate_summary(
            family_results=self.family_results,
            required_qualifying_family_count=(policy.required_qualifying_family_count),
            required_distinct_mechanism_count=(policy.required_distinct_mechanism_count),
        )
        _validate_gate_summary(
            qualifying_family_ids=self.qualifying_family_ids,
            qualifying_mechanisms=self.qualifying_mechanisms,
            all_evidence_valid=self.all_evidence_valid,
            gate_open=self.gate_open,
            expected=summary,
        )
        return self


@dataclass(frozen=True, slots=True)
class _DerivedFamily:
    lineage_contrasts: tuple[ProgramNecessityLineageContrast, ...]
    evidence_valid: bool
    development_direction_consistent: bool
    replication_direction_confirmed: bool
    qualifies: bool


@dataclass(frozen=True, slots=True)
class _GateSummary:
    qualifying_family_ids: tuple[str, ...]
    qualifying_mechanisms: tuple[ProgramNecessityMechanism, ...]
    all_evidence_valid: bool
    gate_open: bool


def build_program_necessity_family_result(
    *,
    plan: ProgramNecessityFamilyPlan,
    observations: tuple[ProgramNecessityObservation, ...],
) -> ProgramNecessityFamilyResult:
    """Reduce complete matched observations without treating executions as worlds."""

    derived = _derive_family(
        plan=plan,
        observations=observations,
    )
    return ProgramNecessityFamilyResult(
        plan=plan,
        observations=observations,
        lineage_contrasts=derived.lineage_contrasts,
        evidence_valid=derived.evidence_valid,
        development_direction_consistent=(derived.development_direction_consistent),
        replication_direction_confirmed=(derived.replication_direction_confirmed),
        qualifies=derived.qualifies,
    )


def evaluate_program_necessity_gate(
    *,
    plan: ProgramNecessityPreregistration,
    family_results: tuple[ProgramNecessityFamilyResult, ...],
) -> ProgramNecessityGateResult:
    """Apply the historical preregistered opening policy."""

    policy = plan.opening_policy
    summary = _derive_gate_summary(
        family_results=family_results,
        required_qualifying_family_count=(policy.required_qualifying_family_count),
        required_distinct_mechanism_count=(policy.required_distinct_mechanism_count),
    )
    return ProgramNecessityGateResult(
        plan=plan,
        family_results=family_results,
        qualifying_family_ids=summary.qualifying_family_ids,
        qualifying_mechanisms=summary.qualifying_mechanisms,
        all_evidence_valid=summary.all_evidence_valid,
        gate_open=summary.gate_open,
    )


def evaluate_program_necessity_study(
    *,
    plan: ProgramNecessityStudyPlan,
    family_results: tuple[ProgramNecessityFamilyResult, ...],
) -> ProgramNecessityStudyResult:
    """Apply the explicit phase-neutral design to complete family results."""

    design = plan.design
    summary = _derive_gate_summary(
        family_results=family_results,
        required_qualifying_family_count=(design.required_qualifying_family_count),
        required_distinct_mechanism_count=(design.required_distinct_mechanism_count),
    )
    return ProgramNecessityStudyResult(
        plan=plan,
        family_results=family_results,
        qualifying_family_ids=summary.qualifying_family_ids,
        qualifying_mechanisms=summary.qualifying_mechanisms,
        all_evidence_valid=summary.all_evidence_valid,
        gate_open=summary.gate_open,
    )


def _canonicalize_family_results(
    value: tuple[ProgramNecessityFamilyResult, ...],
) -> tuple[ProgramNecessityFamilyResult, ...]:
    if len({item.plan.family_id for item in value}) != len(value):
        raise ValueError(
            "program-necessity results must be unique by family",
        )
    return tuple(sorted(value, key=lambda item: item.plan.family_id))


def _canonicalize_qualifying_family_ids(
    value: tuple[str, ...],
) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError("qualifying family identities must be unique")
    return tuple(sorted(value))


def _canonicalize_qualifying_mechanisms(
    value: tuple[ProgramNecessityMechanism, ...],
) -> tuple[ProgramNecessityMechanism, ...]:
    return tuple(sorted(set(value), key=lambda mechanism: mechanism.value))


def _validate_family_result_coverage(
    *,
    family_plans: tuple[ProgramNecessityFamilyPlan, ...],
    family_results: tuple[ProgramNecessityFamilyResult, ...],
) -> None:
    plan_by_id = {family.family_id: family for family in family_plans}
    result_by_id = {result.plan.family_id: result for result in family_results}
    if set(result_by_id) != set(plan_by_id) or any(
        result.plan != plan_by_id[family_id] for family_id, result in result_by_id.items()
    ):
        raise ValueError(
            "program-necessity gate requires every exact preregistered family",
        )


def _derive_gate_summary(
    *,
    family_results: tuple[ProgramNecessityFamilyResult, ...],
    required_qualifying_family_count: int,
    required_distinct_mechanism_count: int,
) -> _GateSummary:
    qualifying_ids = tuple(
        sorted(result.plan.family_id for result in family_results if result.qualifies),
    )
    qualifying_mechanisms = tuple(
        sorted(
            {result.plan.mechanism for result in family_results if result.qualifies},
            key=lambda mechanism: mechanism.value,
        ),
    )
    all_valid = all(result.evidence_valid for result in family_results)
    return _GateSummary(
        qualifying_family_ids=qualifying_ids,
        qualifying_mechanisms=qualifying_mechanisms,
        all_evidence_valid=all_valid,
        gate_open=(
            all_valid
            and len(qualifying_ids) >= required_qualifying_family_count
            and len(qualifying_mechanisms) >= required_distinct_mechanism_count
        ),
    )


def _validate_gate_summary(
    *,
    qualifying_family_ids: tuple[str, ...],
    qualifying_mechanisms: tuple[ProgramNecessityMechanism, ...],
    all_evidence_valid: bool,
    gate_open: bool,
    expected: _GateSummary,
) -> None:
    if (
        qualifying_family_ids != expected.qualifying_family_ids
        or qualifying_mechanisms != expected.qualifying_mechanisms
        or all_evidence_valid != expected.all_evidence_valid
        or gate_open != expected.gate_open
    ):
        raise ValueError(
            "program-necessity gate summary does not match full family results",
        )


def _derive_family(
    *,
    plan: ProgramNecessityFamilyPlan,
    observations: tuple[ProgramNecessityObservation, ...],
) -> _DerivedFamily:
    lineages_by_id = {lineage.review_lineage_id: lineage for lineage in plan.lineage_plans}
    observations_by_key = {
        (
            observation.review_lineage_id,
            observation.matched_evidence_ref.coordinate_sha256,
            observation.arm,
        ): observation
        for observation in observations
    }
    expected_keys = {
        (
            lineage.review_lineage_id,
            coordinate.content_sha256,
            arm,
        )
        for lineage in plan.lineage_plans
        for coordinate in lineage.coordinates
        for arm in ProgramNecessityArm
    }
    if len(observations_by_key) != len(observations) or set(observations_by_key) != expected_keys:
        raise ValueError(
            "program-necessity observations require exact arm, lineage, seed, and repetition coverage",
        )

    for key, observation in observations_by_key.items():
        lineage_id, coordinate_sha256, arm = key
        lineage = lineages_by_id[lineage_id]
        if (
            observation.family_id != plan.family_id
            or observation.lineage_plan_sha256 != lineage.content_sha256
            or observation.candidate != lineage.candidate_for(arm)
            or observation.matched_evidence_ref.candidate_id != lineage.candidate_for(arm).candidate_id
            or observation.matched_evidence_ref.coordinate_sha256 != coordinate_sha256
        ):
            raise ValueError(
                "program-necessity observation does not bind the exact lineage candidate",
            )
        if (
            observation.study_ref_sha256 != lineage.study_ref.content_sha256
            or observation.evaluation_plan_ref != lineage.study_ref.evaluation_plan_ref
        ):
            raise ValueError(
                "program-necessity observation does not bind the exact lineage study and evaluation",
            )

    contrasts: list[ProgramNecessityLineageContrast] = []
    for lineage in plan.lineage_plans:
        arm_means = {
            arm: fmean(
                observations_by_key[
                    (
                        lineage.review_lineage_id,
                        coordinate.content_sha256,
                        arm,
                    )
                ].utility
                for coordinate in lineage.coordinates
            )
            for arm in ProgramNecessityArm
        }
        lineage_observations = tuple(
            observation for key, observation in observations_by_key.items() if key[0] == lineage.review_lineage_id
        )
        monolithic = arm_means[ProgramNecessityArm.MONOLITHIC]
        sham = arm_means[ProgramNecessityArm.SHAM]
        structural = arm_means[ProgramNecessityArm.STRUCTURAL]
        contrasts.append(
            ProgramNecessityLineageContrast(
                review_lineage_id=lineage.review_lineage_id,
                role=lineage.role,
                monolithic_mean=monolithic,
                sham_mean=sham,
                structural_mean=structural,
                splitting_value=sham - monolithic,
                structural_residual=structural - sham,
                total_program_value=structural - monolithic,
                validity_passed=all(observation.validity_passed for observation in lineage_observations),
                integrity_passed=all(observation.integrity_passed for observation in lineage_observations),
            ),
        )
    canonical_contrasts = tuple(
        sorted(contrasts, key=lambda contrast: contrast.review_lineage_id),
    )
    evidence_valid = all(contrast.validity_passed and contrast.integrity_passed for contrast in canonical_contrasts)
    development_direction = all(
        contrast.structural_residual > 0
        for contrast in canonical_contrasts
        if contrast.role is ProgramNecessityLineageRole.DEVELOPMENT
    )
    replication_direction = all(
        contrast.structural_residual > 0
        for contrast in canonical_contrasts
        if contrast.role is ProgramNecessityLineageRole.REPLICATION
    )
    return _DerivedFamily(
        lineage_contrasts=canonical_contrasts,
        evidence_valid=evidence_valid,
        development_direction_consistent=development_direction,
        replication_direction_confirmed=replication_direction,
        qualifies=(evidence_valid and development_direction and replication_direction),
    )
