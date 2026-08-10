# ABOUTME: Defines validated lifecycle evaluation records at the runtime-to-evaluation boundary.
# ABOUTME: Keeps persisted verification shapes independent from lifecycle progression code.

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class LifecycleSemanticStateAccuracy(StrictModel):
    correct_atoms: int = Field(ge=0)
    total_atoms: int = Field(ge=0)
    accuracy: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_support(self) -> LifecycleSemanticStateAccuracy:
        if self.correct_atoms > self.total_atoms:
            raise ValueError("correct_atoms cannot exceed total_atoms")
        _validate_rate(self.accuracy, self.correct_atoms, self.total_atoms, "accuracy")
        return self


class LifecycleSemanticTransitionSummary(StrictModel):
    expected_update_count: int = Field(ge=0)
    actual_update_count: int = Field(ge=0)
    aligned_update_count: int = Field(ge=0)
    updated_to_expected_count: int = Field(ge=0)
    acquired_update_count: int = Field(ge=0)
    unsupported_update_count: int = Field(ge=0)
    stable_correct_before_count: int = Field(ge=0)
    retained_count: int = Field(ge=0)
    interference_count: int = Field(ge=0)
    acquisition: float | None = Field(default=None, ge=0.0, le=1.0)
    update_precision: float | None = Field(default=None, ge=0.0, le=1.0)
    update_recall: float | None = Field(default=None, ge=0.0, le=1.0)
    update_f1: float | None = Field(default=None, ge=0.0, le=1.0)
    retention: float | None = Field(default=None, ge=0.0, le=1.0)
    interference: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_counts_and_support(self) -> LifecycleSemanticTransitionSummary:
        if self.aligned_update_count > self.actual_update_count:
            raise ValueError("aligned_update_count cannot exceed actual_update_count")
        if self.updated_to_expected_count > self.expected_update_count:
            raise ValueError("updated_to_expected_count cannot exceed expected_update_count")
        if self.acquired_update_count > self.updated_to_expected_count:
            raise ValueError("acquired_update_count cannot exceed updated_to_expected_count")
        if self.unsupported_update_count != self.actual_update_count - self.aligned_update_count:
            raise ValueError("unsupported_update_count must equal actual updates minus aligned updates")
        if self.retained_count + self.interference_count != self.stable_correct_before_count:
            raise ValueError("retained and interference counts must partition stable prior-correct atoms")
        _validate_rate(self.acquisition, self.acquired_update_count, self.expected_update_count, "acquisition")
        _validate_rate(self.update_precision, self.aligned_update_count, self.actual_update_count, "update_precision")
        _validate_rate(
            self.update_recall,
            self.updated_to_expected_count,
            self.expected_update_count,
            "update_recall",
        )
        if self.update_f1 != _f1(self.update_precision, self.update_recall):
            raise ValueError("update_f1 must match update precision and recall")
        _validate_rate(self.retention, self.retained_count, self.stable_correct_before_count, "retention")
        _validate_rate(
            self.interference,
            self.interference_count,
            self.stable_correct_before_count,
            "interference",
        )
        return self


class LifecycleSemanticTransitionMetrics(LifecycleSemanticTransitionSummary):
    from_checkpoint_id: NonEmptyStr
    to_checkpoint_id: NonEmptyStr


class LifecycleSemanticMetrics(StrictModel):
    schema_version: Literal["1"] = "1"
    initial_checkpoint_id: NonEmptyStr
    initial: LifecycleSemanticStateAccuracy
    transitions: list[LifecycleSemanticTransitionMetrics]
    aggregate: LifecycleSemanticTransitionSummary

    @model_validator(mode="after")
    def validate_transition_chain(self) -> LifecycleSemanticMetrics:
        previous = self.initial_checkpoint_id
        for transition in self.transitions:
            if transition.from_checkpoint_id != previous:
                raise ValueError("semantic transitions must form one contiguous checkpoint chain")
            previous = transition.to_checkpoint_id
        if self.aggregate != _aggregate(self.transitions):
            raise ValueError("semantic aggregate must equal the sum of its transitions")
        return self


class LifecycleGateResult(StrictModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    failures: list[str] = Field(default_factory=list)


class LifecycleVerificationResult(StrictModel):
    template_id: str | None = None
    lifecycle_id: NonEmptyStr
    overall: Literal["pass", "fail", "incomplete"]
    passed: bool
    reward: float = Field(ge=0.0, le=1.0)
    gates: dict[str, LifecycleGateResult] = Field(min_length=1)
    semantic_metrics: LifecycleSemanticMetrics | None = None

    @model_validator(mode="after")
    def validate_outcome_consistency(self) -> LifecycleVerificationResult:
        gates_pass = all(gate.passed for gate in self.gates.values())
        if self.passed != (self.overall == "pass"):
            raise ValueError("passed must agree with overall")
        if self.passed != gates_pass:
            raise ValueError("passed must agree with verifier gates")
        return self


def _aggregate(transitions: list[LifecycleSemanticTransitionMetrics]) -> LifecycleSemanticTransitionSummary:
    expected = sum(item.expected_update_count for item in transitions)
    actual = sum(item.actual_update_count for item in transitions)
    aligned = sum(item.aligned_update_count for item in transitions)
    updated = sum(item.updated_to_expected_count for item in transitions)
    acquired = sum(item.acquired_update_count for item in transitions)
    stable = sum(item.stable_correct_before_count for item in transitions)
    retained = sum(item.retained_count for item in transitions)
    precision = _rate(aligned, actual)
    recall = _rate(updated, expected)
    return LifecycleSemanticTransitionSummary(
        expected_update_count=expected,
        actual_update_count=actual,
        aligned_update_count=aligned,
        updated_to_expected_count=updated,
        acquired_update_count=acquired,
        unsupported_update_count=actual - aligned,
        stable_correct_before_count=stable,
        retained_count=retained,
        interference_count=stable - retained,
        acquisition=_rate(acquired, expected),
        update_precision=precision,
        update_recall=recall,
        update_f1=_f1(precision, recall),
        retention=_rate(retained, stable),
        interference=_rate(stable - retained, stable),
    )


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 6)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0.0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 6)


def _validate_rate(value: float | None, numerator: int, denominator: int, field_name: str) -> None:
    if value != _rate(numerator, denominator):
        raise ValueError(f"{field_name} must match its numerator and denominator")
