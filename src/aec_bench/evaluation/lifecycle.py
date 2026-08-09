# ABOUTME: Computes reward-independent semantic transition diagnostics for evidence lifecycles.
# ABOUTME: Separates expected state acquisition and retention from verifier gates and operational efficiency.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from pydantic import Field, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel

_MISSING = object()


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
        expected_f1 = _f1(self.update_precision, self.update_recall)
        if self.update_f1 != expected_f1:
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
        expected_aggregate = _aggregate(self.transitions)
        if self.aggregate != expected_aggregate:
            raise ValueError("semantic aggregate must equal the sum of its transitions")
        return self


def score_semantic_transitions(
    *,
    checkpoint_ids: Sequence[str],
    expected: Mapping[str, Mapping[str, Any]],
    actual: Mapping[str, Mapping[str, Any]],
) -> LifecycleSemanticMetrics:
    """Compare task-extracted semantic atoms across one ordered lifecycle."""
    ordered = tuple(checkpoint_ids)
    if not ordered:
        raise ValueError("semantic transition scoring requires at least one checkpoint")
    if len(set(ordered)) != len(ordered):
        raise ValueError("semantic transition checkpoint ids must be unique")
    missing_expected = [checkpoint_id for checkpoint_id in ordered if checkpoint_id not in expected]
    missing_actual = [checkpoint_id for checkpoint_id in ordered if checkpoint_id not in actual]
    if missing_expected:
        raise ValueError(f"missing expected semantic checkpoints: {', '.join(missing_expected)}")
    if missing_actual:
        raise ValueError(f"missing actual semantic checkpoints: {', '.join(missing_actual)}")

    expected_states = {checkpoint_id: _canonical_atoms(expected[checkpoint_id]) for checkpoint_id in ordered}
    actual_states = {checkpoint_id: _canonical_atoms(actual[checkpoint_id]) for checkpoint_id in ordered}
    initial = _state_accuracy(expected_states[ordered[0]], actual_states[ordered[0]])
    transitions = [
        _score_transition(
            from_checkpoint_id=previous,
            to_checkpoint_id=current,
            expected_before=expected_states[previous],
            expected_after=expected_states[current],
            actual_before=actual_states[previous],
            actual_after=actual_states[current],
        )
        for previous, current in zip(ordered, ordered[1:], strict=False)
    ]
    aggregate = _aggregate(transitions)
    return LifecycleSemanticMetrics(
        initial_checkpoint_id=ordered[0],
        initial=initial,
        transitions=transitions,
        aggregate=aggregate,
    )


def _state_accuracy(expected: dict[str, Any], actual: dict[str, Any]) -> LifecycleSemanticStateAccuracy:
    atom_ids = set(expected) | set(actual)
    correct = sum(expected.get(atom_id, _MISSING) == actual.get(atom_id, _MISSING) for atom_id in atom_ids)
    return LifecycleSemanticStateAccuracy(
        correct_atoms=correct,
        total_atoms=len(atom_ids),
        accuracy=_rate(correct, len(atom_ids)),
    )


def _score_transition(
    *,
    from_checkpoint_id: str,
    to_checkpoint_id: str,
    expected_before: dict[str, Any],
    expected_after: dict[str, Any],
    actual_before: dict[str, Any],
    actual_after: dict[str, Any],
) -> LifecycleSemanticTransitionMetrics:
    atom_ids = set(expected_before) | set(expected_after) | set(actual_before) | set(actual_after)
    expected_updates = {
        atom_id
        for atom_id in atom_ids
        if expected_before.get(atom_id, _MISSING) != expected_after.get(atom_id, _MISSING)
    }
    actual_updates = {
        atom_id for atom_id in atom_ids if actual_before.get(atom_id, _MISSING) != actual_after.get(atom_id, _MISSING)
    }
    aligned_updates = {
        atom_id
        for atom_id in actual_updates
        if actual_after.get(atom_id, _MISSING) == expected_after.get(atom_id, _MISSING)
    }
    updated_to_expected = {
        atom_id
        for atom_id in expected_updates
        if actual_after.get(atom_id, _MISSING) == expected_after.get(atom_id, _MISSING)
    }
    acquired_updates = {
        atom_id
        for atom_id in updated_to_expected
        if actual_before.get(atom_id, _MISSING) == expected_before.get(atom_id, _MISSING)
    }
    expected_stable = atom_ids - expected_updates
    stable_correct_before = {
        atom_id
        for atom_id in expected_stable
        if actual_before.get(atom_id, _MISSING) == expected_before.get(atom_id, _MISSING)
    }
    retained = {
        atom_id
        for atom_id in stable_correct_before
        if actual_after.get(atom_id, _MISSING) == expected_after.get(atom_id, _MISSING)
    }
    summary = _transition_summary(
        expected_update_count=len(expected_updates),
        actual_update_count=len(actual_updates),
        aligned_update_count=len(aligned_updates),
        updated_to_expected_count=len(updated_to_expected),
        acquired_update_count=len(acquired_updates),
        stable_correct_before_count=len(stable_correct_before),
        retained_count=len(retained),
    )
    return LifecycleSemanticTransitionMetrics(
        from_checkpoint_id=from_checkpoint_id,
        to_checkpoint_id=to_checkpoint_id,
        **summary.model_dump(),
    )


def _aggregate(transitions: list[LifecycleSemanticTransitionMetrics]) -> LifecycleSemanticTransitionSummary:
    return _transition_summary(
        expected_update_count=sum(item.expected_update_count for item in transitions),
        actual_update_count=sum(item.actual_update_count for item in transitions),
        aligned_update_count=sum(item.aligned_update_count for item in transitions),
        updated_to_expected_count=sum(item.updated_to_expected_count for item in transitions),
        acquired_update_count=sum(item.acquired_update_count for item in transitions),
        stable_correct_before_count=sum(item.stable_correct_before_count for item in transitions),
        retained_count=sum(item.retained_count for item in transitions),
    )


def _transition_summary(
    *,
    expected_update_count: int,
    actual_update_count: int,
    aligned_update_count: int,
    updated_to_expected_count: int,
    acquired_update_count: int,
    stable_correct_before_count: int,
    retained_count: int,
) -> LifecycleSemanticTransitionSummary:
    precision = _rate(aligned_update_count, actual_update_count)
    recall = _rate(updated_to_expected_count, expected_update_count)
    return LifecycleSemanticTransitionSummary(
        expected_update_count=expected_update_count,
        actual_update_count=actual_update_count,
        aligned_update_count=aligned_update_count,
        updated_to_expected_count=updated_to_expected_count,
        acquired_update_count=acquired_update_count,
        unsupported_update_count=actual_update_count - aligned_update_count,
        stable_correct_before_count=stable_correct_before_count,
        retained_count=retained_count,
        interference_count=stable_correct_before_count - retained_count,
        acquisition=_rate(acquired_update_count, expected_update_count),
        update_precision=precision,
        update_recall=recall,
        update_f1=_f1(precision, recall),
        retention=_rate(retained_count, stable_correct_before_count),
        interference=_rate(stable_correct_before_count - retained_count, stable_correct_before_count),
    )


def _canonical_atoms(atoms: Mapping[str, Any]) -> dict[str, Any]:
    canonical: dict[str, Any] = {}
    for atom_id, value in atoms.items():
        if not isinstance(atom_id, str) or not atom_id.strip():
            raise ValueError("semantic atom ids must be non-empty strings")
        canonical[atom_id] = _canonical_value(value)
    return canonical


def _canonical_value(value: Any) -> Any:
    if isinstance(value, list):
        canonical = [_canonical_value(item) for item in value]
        unique = {_sort_key(item): item for item in canonical}
        return ("set", tuple(unique[key] for key in sorted(unique)))
    if isinstance(value, dict):
        return ("object", tuple(sorted((str(key), _canonical_value(item)) for key, item in value.items())))
    if value is None:
        return ("null", None)
    if isinstance(value, bool):
        return ("boolean", value)
    if isinstance(value, int):
        return ("integer", value)
    if isinstance(value, float):
        return ("number", value)
    if isinstance(value, str):
        return ("string", value)
    return (type(value).__name__, repr(value))


def _sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, default=repr)


def _rate(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else round(numerator / denominator, 6)


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None:
        return None
    if precision + recall == 0.0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 6)


def _validate_rate(value: float | None, numerator: int, denominator: int, field_name: str) -> None:
    expected = _rate(numerator, denominator)
    if value != expected:
        raise ValueError(f"{field_name} must match its numerator and denominator")
