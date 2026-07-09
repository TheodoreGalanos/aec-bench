# ABOUTME: Contract models for task-world profiles and materialised run evidence.
# ABOUTME: Keeps logic and operation profiles typed before LLM review consumes them.

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel

DEFAULT_REVIEW_MODES = [
    "verifier_result",
    "output_artifacts",
    "trace",
    "source_authority",
    "rubric_scores",
    "contradiction_ledger",
]


class ClosureGate(StrictModel):
    id: NonEmptyStr
    evidence_key: NonEmptyStr
    proposition: str | None = None
    expected: Any = True
    authority: str | None = None
    failure_effect: str | None = None


class ConstructionGate(StrictModel):
    id: NonEmptyStr
    proposition: str | None = None
    construction_required: list[NonEmptyStr] = Field(default_factory=list)
    failure_effect: str | None = None


class ContainmentGate(StrictModel):
    id: NonEmptyStr
    contradiction: str | None = None
    when: dict[str, Any] = Field(default_factory=dict)
    record_key: str | None = None
    required_record: list[NonEmptyStr] = Field(default_factory=list)
    failure_effect: str | None = None


class EventTrigger(StrictModel):
    id: NonEmptyStr
    classification: str | None = None
    when: dict[str, Any] = Field(default_factory=dict)
    repair_targets: list[NonEmptyStr] = Field(default_factory=list)


class AgenticReviewProfile(StrictModel):
    required: bool = True
    review_modes: list[NonEmptyStr] = Field(default_factory=lambda: list(DEFAULT_REVIEW_MODES))
    guidance: str | None = None

    @field_validator("review_modes")
    @classmethod
    def validate_review_modes(cls, value: list[str]) -> list[str]:
        if not value:
            msg = "review_modes must contain at least one mode"
            raise ValueError(msg)
        return value


class LogicProfile(StrictModel):
    closure_gates: list[ClosureGate] = Field(default_factory=list)
    construction_gates: list[ConstructionGate] = Field(default_factory=list)
    containment_gates: list[ContainmentGate] = Field(default_factory=list)
    event_triggers: list[EventTrigger] = Field(default_factory=list)
    agentic_review: AgenticReviewProfile = Field(default_factory=AgenticReviewProfile)


class OperationProfile(StrictModel):
    subset_axes: list[NonEmptyStr] = Field(default_factory=list)
    difference_axes: list[NonEmptyStr] = Field(default_factory=list)
    projection_axes: list[NonEmptyStr] = Field(default_factory=list)
    product_axes: list[NonEmptyStr] = Field(default_factory=list)
    extension_policy: str | None = None


class TaskWorldProfile(StrictModel):
    world_id: NonEmptyStr
    name: NonEmptyStr
    task_unit: NonEmptyStr
    logic_profile: LogicProfile
    operation_profile: OperationProfile = Field(default_factory=OperationProfile)


class MaterializedTaskWorldRun(StrictModel):
    world_profile: TaskWorldProfile
    evidence: dict[str, Any]

    def to_review_payload(self) -> dict[str, Any]:
        world = self.world_profile.model_dump(mode="json", exclude_none=True)
        return {
            "world": world,
            "logic_profile": world["logic_profile"],
            "operation_profile": world.get("operation_profile", {}),
            **self.evidence,
        }
