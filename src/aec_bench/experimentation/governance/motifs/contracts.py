# ABOUTME: Defines content-addressed Hx/px motif records and their evidence contracts.
# ABOUTME: Provides canonical identity helpers consumed by promotion, persistence, and selection.

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Annotated, Any, Literal, cast

from pydantic import Field, FiniteFloat, JsonValue, PositiveInt, field_validator, model_validator

from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

UnitFloat = Annotated[FiniteFloat, Field(ge=0.0, le=1.0)]
NonNegativeFiniteFloat = Annotated[FiniteFloat, Field(ge=0.0)]
TemplateKind = Literal["hx", "px"]
EvidenceSplit = Literal["discovery", "repair_gate", "calibration", "holdout"]
StateMode = Literal["stateless", "ephemeral", "persistent"]
FanoutCharacteristic = Literal["none", "bounded", "unbounded"]
BranchingCharacteristic = Literal["none", "conditional", "iterative"]


class MotifStatus(StrEnum):
    """Lifecycle state for one immutable motif evidence record."""

    CANDIDATE = "candidate"
    PROVISIONAL = "provisional"
    REUSABLE = "reusable"
    TRANSFER_VALIDATED = "transfer_validated"
    RETIRED = "retired"


class MotifTemplate(FrozenStrictModel):
    """Canonical JSON template for either the learned harness Hx or program px."""

    template_sha256: NonEmptyStr
    kind: TemplateKind
    payload: dict[str, JsonValue]

    @field_validator("template_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_identity(self) -> MotifTemplate:
        expected = _canonical_sha256({"kind": self.kind, "payload": self.payload})
        if self.template_sha256 != expected:
            raise ValueError("template_sha256 must bind the canonical motif template")
        return self

    @classmethod
    def create(cls, *, kind: str, payload: dict[str, Any]) -> MotifTemplate:
        resolved_kind = cast(TemplateKind, kind)
        copied_payload = json.loads(_canonical_json(payload))
        identity = {"kind": resolved_kind, "payload": copied_payload}
        return cls(
            template_sha256=_canonical_sha256(identity),
            kind=resolved_kind,
            payload=copied_payload,
        )


class MotifApplicabilityDescriptor(FrozenStrictModel):
    """Reward-free task-review characteristics used to look up an applicable motif."""

    task_pattern: NonEmptyStr
    stage_pattern: NonEmptyStr
    stage_count: PositiveInt
    fanout_characteristic: FanoutCharacteristic
    branching_characteristic: BranchingCharacteristic
    evidence_surfaces: tuple[NonEmptyStr, ...]
    required_tool_surface: tuple[NonEmptyStr, ...] = ()
    state_mode: StateMode

    @field_validator("evidence_surfaces", "required_tool_surface")
    @classmethod
    def canonicalize_surfaces(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("applicability descriptor surfaces must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_evidence_surfaces(self) -> MotifApplicabilityDescriptor:
        if not self.evidence_surfaces:
            raise ValueError("applicability descriptor requires at least one evidence surface")
        return self


class MotifStructuralDescriptor(FrozenStrictModel):
    """Derived coordinates describing how an Hx/px solution decomposes and orchestrates work."""

    decomposition_pattern: NonEmptyStr
    orchestration_pattern: NonEmptyStr
    decomposition_depth: int = Field(ge=0)
    maximum_parallelism: PositiveInt
    tool_surface: tuple[NonEmptyStr, ...]
    state_mode: StateMode

    @field_validator("tool_surface")
    @classmethod
    def canonicalize_tool_surface(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("structural descriptor requires at least one tool surface")
        if len(value) != len(set(value)):
            raise ValueError("structural descriptor tool surfaces must be unique")
        return tuple(sorted(value))


class PairedRepairEvidenceReference(FrozenStrictModel):
    """Content-bound reference to a verifier-guided paired repair decision."""

    reference_sha256: NonEmptyStr
    attempt_id: NonEmptyStr
    decision_sha256: NonEmptyStr
    review_lineage_id: NonEmptyStr
    split: EvidenceSplit
    accepted: bool
    mean_reward_delta: FiniteFloat
    validity_rate: UnitFloat
    estimated_cost_usd: NonNegativeFiniteFloat

    @field_validator("reference_sha256", "decision_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_identity(self) -> PairedRepairEvidenceReference:
        _validate_bound_hash(self, "reference_sha256")
        return self

    @classmethod
    def create(
        cls,
        *,
        attempt_id: str,
        decision_sha256: str,
        review_lineage_id: str,
        split: str,
        accepted: bool,
        mean_reward_delta: float,
        validity_rate: float,
        estimated_cost_usd: float,
    ) -> PairedRepairEvidenceReference:
        payload: dict[str, Any] = {
            "attempt_id": attempt_id,
            "decision_sha256": decision_sha256,
            "review_lineage_id": review_lineage_id,
            "split": split,
            "accepted": accepted,
            "mean_reward_delta": mean_reward_delta,
            "validity_rate": validity_rate,
            "estimated_cost_usd": estimated_cost_usd,
        }
        return cls(reference_sha256=_canonical_sha256(payload), **payload)


class HarnessProgramEvidenceReference(FrozenStrictModel):
    """Content-bound harness-program effects for one or more calibration review lineages."""

    reference_sha256: NonEmptyStr
    analysis_sha256: NonEmptyStr
    subject_hx_template_sha256: NonEmptyStr
    subject_px_template_sha256: NonEmptyStr
    review_lineage_ids: tuple[NonEmptyStr, ...]
    split: EvidenceSplit
    harness_main_effect: FiniteFloat
    program_main_effect: FiniteFloat
    interaction: FiniteFloat
    joint_uplift: FiniteFloat
    joint_incremental_uplift: FiniteFloat
    joint_incremental_uplift_lower_bound: FiniteFloat
    validity_rate: UnitFloat
    estimated_cost_usd: NonNegativeFiniteFloat
    holdout_accessed_during_selection: bool = False

    @field_validator(
        "reference_sha256",
        "analysis_sha256",
        "subject_hx_template_sha256",
        "subject_px_template_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("review_lineage_ids")
    @classmethod
    def canonicalize_review_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_review_lineages(value)

    @model_validator(mode="after")
    def validate_identity(self) -> HarnessProgramEvidenceReference:
        _validate_bound_hash(self, "reference_sha256")
        return self

    @classmethod
    def create(
        cls,
        *,
        analysis_sha256: str,
        subject_hx_template_sha256: str,
        subject_px_template_sha256: str,
        review_lineage_ids: tuple[str, ...],
        split: str,
        harness_main_effect: float,
        program_main_effect: float,
        interaction: float,
        joint_uplift: float,
        joint_incremental_uplift: float,
        joint_incremental_uplift_lower_bound: float,
        validity_rate: float,
        estimated_cost_usd: float,
        holdout_accessed_during_selection: bool = False,
    ) -> HarnessProgramEvidenceReference:
        payload: dict[str, Any] = {
            "analysis_sha256": analysis_sha256,
            "subject_hx_template_sha256": subject_hx_template_sha256,
            "subject_px_template_sha256": subject_px_template_sha256,
            "review_lineage_ids": _canonical_review_lineages(review_lineage_ids),
            "split": split,
            "harness_main_effect": harness_main_effect,
            "program_main_effect": program_main_effect,
            "interaction": interaction,
            "joint_uplift": joint_uplift,
            "joint_incremental_uplift": joint_incremental_uplift,
            "joint_incremental_uplift_lower_bound": joint_incremental_uplift_lower_bound,
            "validity_rate": validity_rate,
            "estimated_cost_usd": estimated_cost_usd,
            "holdout_accessed_during_selection": holdout_accessed_during_selection,
        }
        return cls(reference_sha256=_canonical_sha256(payload), **payload)


class QualityEvidenceReference(FrozenStrictModel):
    """Calibration objective, validity, and cost evidence kept outside the structural descriptor."""

    reference_sha256: NonEmptyStr
    evaluation_sha256: NonEmptyStr
    subject_hx_template_sha256: NonEmptyStr
    subject_px_template_sha256: NonEmptyStr
    review_lineage_ids: tuple[NonEmptyStr, ...]
    split: EvidenceSplit
    objective_reward: UnitFloat
    validity_rate: UnitFloat
    estimated_cost_usd: NonNegativeFiniteFloat
    holdout_accessed_during_selection: bool = False
    included_in_harness_program_reference_sha256: str | None = None

    @field_validator(
        "reference_sha256",
        "evaluation_sha256",
        "subject_hx_template_sha256",
        "subject_px_template_sha256",
        "included_in_harness_program_reference_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else _validate_sha256(value)

    @field_validator("review_lineage_ids")
    @classmethod
    def canonicalize_review_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_review_lineages(value)

    @model_validator(mode="after")
    def validate_identity(self) -> QualityEvidenceReference:
        _validate_bound_hash(self, "reference_sha256")
        return self

    @classmethod
    def create(
        cls,
        *,
        evaluation_sha256: str,
        subject_hx_template_sha256: str,
        subject_px_template_sha256: str,
        review_lineage_ids: tuple[str, ...],
        split: str,
        objective_reward: float,
        validity_rate: float,
        estimated_cost_usd: float,
        holdout_accessed_during_selection: bool = False,
        included_in_harness_program_reference_sha256: str | None = None,
    ) -> QualityEvidenceReference:
        payload: dict[str, Any] = {
            "evaluation_sha256": evaluation_sha256,
            "subject_hx_template_sha256": subject_hx_template_sha256,
            "subject_px_template_sha256": subject_px_template_sha256,
            "review_lineage_ids": _canonical_review_lineages(review_lineage_ids),
            "split": split,
            "objective_reward": objective_reward,
            "validity_rate": validity_rate,
            "estimated_cost_usd": estimated_cost_usd,
            "holdout_accessed_during_selection": holdout_accessed_during_selection,
            "included_in_harness_program_reference_sha256": included_in_harness_program_reference_sha256,
        }
        return cls(reference_sha256=_canonical_sha256(payload), **payload)


class TransferEvidenceReference(FrozenStrictModel):
    """Frozen-archive holdout evidence for transfer beyond supporting review lineages."""

    reference_sha256: NonEmptyStr
    evaluation_sha256: NonEmptyStr
    review_lineage_ids: tuple[NonEmptyStr, ...]
    split: EvidenceSplit
    objective_reward: UnitFloat
    validity_rate: UnitFloat
    joint_uplift: FiniteFloat
    joint_incremental_uplift: FiniteFloat
    joint_incremental_uplift_lower_bound: FiniteFloat
    estimated_cost_usd: NonNegativeFiniteFloat
    selected_before_holdout: bool
    archive_frozen: bool

    @field_validator("reference_sha256", "evaluation_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("review_lineage_ids")
    @classmethod
    def canonicalize_review_lineages(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_review_lineages(value)

    @model_validator(mode="after")
    def validate_identity(self) -> TransferEvidenceReference:
        _validate_bound_hash(self, "reference_sha256")
        return self

    @classmethod
    def create(
        cls,
        *,
        evaluation_sha256: str,
        review_lineage_ids: tuple[str, ...],
        split: str,
        objective_reward: float,
        validity_rate: float,
        joint_uplift: float,
        joint_incremental_uplift: float,
        joint_incremental_uplift_lower_bound: float,
        estimated_cost_usd: float,
        selected_before_holdout: bool,
        archive_frozen: bool,
    ) -> TransferEvidenceReference:
        payload: dict[str, Any] = {
            "evaluation_sha256": evaluation_sha256,
            "review_lineage_ids": _canonical_review_lineages(review_lineage_ids),
            "split": split,
            "objective_reward": objective_reward,
            "validity_rate": validity_rate,
            "joint_uplift": joint_uplift,
            "joint_incremental_uplift": joint_incremental_uplift,
            "joint_incremental_uplift_lower_bound": joint_incremental_uplift_lower_bound,
            "estimated_cost_usd": estimated_cost_usd,
            "selected_before_holdout": selected_before_holdout,
            "archive_frozen": archive_frozen,
        }
        return cls(reference_sha256=_canonical_sha256(payload), **payload)


class HarnessProgramMotif(FrozenStrictModel):
    """Immutable Hx/px motif record with structural coordinates and auditable evidence."""

    schema_version: Literal["2"] = "2"
    motif_sha256: NonEmptyStr
    status: MotifStatus
    kernel_abi_sha256: NonEmptyStr
    hx_template: MotifTemplate
    px_template: MotifTemplate
    applicability: MotifApplicabilityDescriptor
    descriptor: MotifStructuralDescriptor
    supporting_review_lineage_ids: tuple[NonEmptyStr, ...]
    accepted_repair_refs: tuple[PairedRepairEvidenceReference, ...] = ()
    harness_program_evidence_refs: tuple[HarnessProgramEvidenceReference, ...] = ()
    quality_evidence_refs: tuple[QualityEvidenceReference, ...] = ()
    transfer_evidence_refs: tuple[TransferEvidenceReference, ...] = ()
    parent_motif_sha256: str | None = None

    @field_validator("motif_sha256", "kernel_abi_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("parent_motif_sha256")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_sha256(value)

    @field_validator("supporting_review_lineage_ids")
    @classmethod
    def canonicalize_support(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @field_validator("accepted_repair_refs")
    @classmethod
    def canonicalize_repairs(
        cls,
        value: tuple[PairedRepairEvidenceReference, ...],
    ) -> tuple[PairedRepairEvidenceReference, ...]:
        return _canonical_references(value)

    @field_validator("harness_program_evidence_refs")
    @classmethod
    def canonicalize_harness_program(
        cls,
        value: tuple[HarnessProgramEvidenceReference, ...],
    ) -> tuple[HarnessProgramEvidenceReference, ...]:
        return _canonical_references(value)

    @field_validator("quality_evidence_refs")
    @classmethod
    def canonicalize_quality(
        cls,
        value: tuple[QualityEvidenceReference, ...],
    ) -> tuple[QualityEvidenceReference, ...]:
        return _canonical_references(value)

    @field_validator("transfer_evidence_refs")
    @classmethod
    def canonicalize_transfer(
        cls,
        value: tuple[TransferEvidenceReference, ...],
    ) -> tuple[TransferEvidenceReference, ...]:
        return _canonical_references(value)

    @model_validator(mode="after")
    def validate_record(self) -> HarnessProgramMotif:
        _validate_template_pair(self)
        _validate_repair_evidence(self)
        _validate_evidence_subjects(self)
        _validate_selection_isolation(self)
        _validate_evidence_links(self)
        _validate_lineage_and_identity(self)
        return self

    @property
    def objective_reward(self) -> float | None:
        """Conservative calibration objective, deliberately separate from descriptor coordinates."""

        if not self.quality_evidence_refs:
            return None
        return min(float(reference.objective_reward) for reference in self.quality_evidence_refs)

    @property
    def validity_rate(self) -> float | None:
        """Lowest observed validity across repair, harness-program, and calibration quality evidence."""

        values = [float(reference.validity_rate) for reference in self.accepted_repair_refs]
        values.extend(float(reference.validity_rate) for reference in self.harness_program_evidence_refs)
        values.extend(float(reference.validity_rate) for reference in self.quality_evidence_refs)
        return min(values) if values else None

    @property
    def estimated_cost_usd(self) -> float:
        """Total recorded selection cost across repair, harness-program, and quality evidence."""

        repair_cost = sum(float(reference.estimated_cost_usd) for reference in self.accepted_repair_refs)
        harness_program_cost = sum(
            float(reference.estimated_cost_usd) for reference in self.harness_program_evidence_refs
        )
        quality_cost = sum(
            float(reference.estimated_cost_usd)
            for reference in self.quality_evidence_refs
            if reference.included_in_harness_program_reference_sha256 is None
        )
        return repair_cost + harness_program_cost + quality_cost

    @classmethod
    def create(
        cls,
        *,
        status: MotifStatus | str,
        kernel_abi_sha256: str,
        hx_template: MotifTemplate,
        px_template: MotifTemplate,
        applicability: MotifApplicabilityDescriptor,
        descriptor: MotifStructuralDescriptor,
        accepted_repair_refs: tuple[PairedRepairEvidenceReference, ...] = (),
        harness_program_evidence_refs: tuple[HarnessProgramEvidenceReference, ...] = (),
        quality_evidence_refs: tuple[QualityEvidenceReference, ...] = (),
        transfer_evidence_refs: tuple[TransferEvidenceReference, ...] = (),
        parent_motif_sha256: str | None = None,
    ) -> HarnessProgramMotif:
        repairs = _canonical_references(accepted_repair_refs)
        harness_program = _canonical_references(harness_program_evidence_refs)
        quality = _canonical_references(quality_evidence_refs)
        transfer = _canonical_references(transfer_evidence_refs)
        support = _supporting_review_lineages(repairs, harness_program, quality)
        resolved_status = MotifStatus(status)
        payload: dict[str, Any] = {
            "schema_version": "2",
            "status": resolved_status.value,
            "kernel_abi_sha256": kernel_abi_sha256,
            "hx_template": hx_template.model_dump(mode="json"),
            "px_template": px_template.model_dump(mode="json"),
            "applicability": applicability.model_dump(mode="json"),
            "descriptor": descriptor.model_dump(mode="json"),
            "supporting_review_lineage_ids": support,
            "accepted_repair_refs": [reference.model_dump(mode="json") for reference in repairs],
            "harness_program_evidence_refs": [reference.model_dump(mode="json") for reference in harness_program],
            "quality_evidence_refs": [reference.model_dump(mode="json") for reference in quality],
            "transfer_evidence_refs": [reference.model_dump(mode="json") for reference in transfer],
            "parent_motif_sha256": parent_motif_sha256,
        }
        return cls(motif_sha256=_canonical_sha256(payload), **payload)


def _validate_template_pair(motif: HarnessProgramMotif) -> None:
    if motif.hx_template.kind != "hx" or motif.px_template.kind != "px":
        raise ValueError("motif requires one Hx harness template and one px program template")


def _validate_repair_evidence(motif: HarnessProgramMotif) -> None:
    if any(not reference.accepted for reference in motif.accepted_repair_refs):
        raise ValueError("motif may contain only accepted paired repair references")
    if any(reference.split == "holdout" for reference in motif.accepted_repair_refs):
        raise ValueError("holdout evidence cannot support motif repair")


def _validate_evidence_subjects(motif: HarnessProgramMotif) -> None:
    expected_subject = (
        motif.hx_template.template_sha256,
        motif.px_template.template_sha256,
    )
    if any(
        (
            reference.subject_hx_template_sha256,
            reference.subject_px_template_sha256,
        )
        != expected_subject
        for reference in motif.harness_program_evidence_refs
    ):
        raise ValueError("harness-program evidence subject does not match the motif Hx/px templates")
    if any(
        (
            reference.subject_hx_template_sha256,
            reference.subject_px_template_sha256,
        )
        != expected_subject
        for reference in motif.quality_evidence_refs
    ):
        raise ValueError("quality evidence subject does not match the motif Hx/px templates")


def _validate_selection_isolation(motif: HarnessProgramMotif) -> None:
    harness_program_leaked = any(
        reference.split == "holdout" or reference.holdout_accessed_during_selection
        for reference in motif.harness_program_evidence_refs
    )
    quality_leaked = any(
        reference.split == "holdout" or reference.holdout_accessed_during_selection
        for reference in motif.quality_evidence_refs
    )
    if harness_program_leaked or quality_leaked:
        raise ValueError("holdout evidence cannot support motif selection")


def _validate_evidence_links(motif: HarnessProgramMotif) -> None:
    harness_program_addresses = {reference.reference_sha256 for reference in motif.harness_program_evidence_refs}
    if any(
        reference.included_in_harness_program_reference_sha256 is not None
        and reference.included_in_harness_program_reference_sha256 not in harness_program_addresses
        for reference in motif.quality_evidence_refs
    ):
        raise ValueError("quality evidence cost inclusion must identify a stored harness-program reference")
    if any(reference.split != "holdout" for reference in motif.transfer_evidence_refs):
        raise ValueError("transfer evidence must come from the holdout split")


def _validate_lineage_and_identity(motif: HarnessProgramMotif) -> None:
    expected_support = _supporting_review_lineages(
        motif.accepted_repair_refs,
        motif.harness_program_evidence_refs,
        motif.quality_evidence_refs,
    )
    if motif.supporting_review_lineage_ids != expected_support:
        raise ValueError("supporting review lineages must equal distinct calibration evidence lineages")
    if motif.parent_motif_sha256 == motif.motif_sha256:
        raise ValueError("motif cannot identify itself as its parent")
    expected_hash = _canonical_sha256(motif.model_dump(mode="json", exclude={"motif_sha256"}))
    if motif.motif_sha256 != expected_hash:
        raise ValueError("motif_sha256 must bind the canonical motif record")


def _supporting_review_lineages(
    repairs: tuple[PairedRepairEvidenceReference, ...],
    harness_program: tuple[HarnessProgramEvidenceReference, ...],
    quality: tuple[QualityEvidenceReference, ...],
) -> tuple[str, ...]:
    lineages = {reference.review_lineage_id for reference in repairs}
    lineages.update(lineage for reference in harness_program for lineage in reference.review_lineage_ids)
    lineages.update(lineage for reference in quality for lineage in reference.review_lineage_ids)
    return tuple(sorted(lineages))


def _canonical_review_lineages(value: tuple[str, ...]) -> tuple[str, ...]:
    if not value:
        raise ValueError("evidence requires at least one review lineage")
    return tuple(sorted(set(value)))


def _canonical_references[ReferenceT](value: tuple[ReferenceT, ...]) -> tuple[ReferenceT, ...]:
    ordered = tuple(sorted(value, key=lambda reference: cast(Any, reference).reference_sha256))
    addresses = [cast(Any, reference).reference_sha256 for reference in ordered]
    if len(addresses) != len(set(addresses)):
        raise ValueError("evidence references must be unique")
    return ordered


def _validate_bound_hash(model: FrozenStrictModel, field_name: str) -> None:
    expected = _canonical_sha256(model.model_dump(mode="json", exclude={field_name}))
    if getattr(model, field_name) != expected:
        raise ValueError(f"{field_name} must bind the canonical evidence reference")


def _validate_sha256(value: str) -> str:
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError("sha256 must contain 64 lowercase hexadecimal characters")
    return value


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _canonical_sha256(payload: object) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
