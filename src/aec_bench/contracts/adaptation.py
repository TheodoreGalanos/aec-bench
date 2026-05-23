# ABOUTME: Pure contract models and deterministic expansion for adaptation task families.
# ABOUTME: Provides variation axes, derivation steps, and candidate generation.

from itertools import product

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel, ensure_non_empty_string


class VariationAxis(StrictModel):
    axis: NonEmptyStr
    values: list[str]

    @field_validator("values")
    @classmethod
    def validate_values(cls, values: list[str]) -> list[str]:
        if not values:
            msg = "values must not be empty"
            raise ValueError(msg)
        normalized = [ensure_non_empty_string(value) for value in values]
        if len(set(normalized)) != len(normalized):
            msg = "values must be unique"
            raise ValueError(msg)
        return normalized


class DerivationStep(StrictModel):
    axis: NonEmptyStr
    value: NonEmptyStr
    parent_value: NonEmptyStr


class AdaptationSpec(StrictModel):
    family_id: NonEmptyStr
    seed_task_id: NonEmptyStr
    seed_variation: dict[str, str] = Field(default_factory=dict)
    axes: list[VariationAxis]
    include_seed: bool = False

    @field_validator("seed_variation")
    @classmethod
    def validate_seed_variation(cls, value: dict[str, str]) -> dict[str, str]:
        return {
            ensure_non_empty_string(axis): ensure_non_empty_string(axis_value) for axis, axis_value in value.items()
        }

    @model_validator(mode="after")
    def validate_axes(self) -> "AdaptationSpec":
        axis_names = [axis.axis for axis in self.axes]
        if not axis_names:
            msg = "axes must not be empty"
            raise ValueError(msg)
        if len(set(axis_names)) != len(axis_names):
            msg = "axes must be unique"
            raise ValueError(msg)

        if set(self.seed_variation) != set(axis_names):
            msg = "seed_variation must define every axis"
            raise ValueError(msg)

        allowed_values = {axis.axis: set(axis.values) for axis in self.axes}
        for axis_name, axis_value in self.seed_variation.items():
            if axis_value not in allowed_values[axis_name]:
                msg = "seed_variation value must exist in axis values"
                raise ValueError(msg)
        return self


class AdaptationCandidate(StrictModel):
    family_id: NonEmptyStr
    seed_task_id: NonEmptyStr
    variation_key: NonEmptyStr
    variation: dict[str, str]
    derivation_lineage: list[DerivationStep] = Field(default_factory=list)

    @field_validator("variation")
    @classmethod
    def validate_variation(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            msg = "variation must not be empty"
            raise ValueError(msg)
        return {
            ensure_non_empty_string(axis): ensure_non_empty_string(axis_value) for axis, axis_value in value.items()
        }


def expand_adaptation_spec(spec: AdaptationSpec) -> list[AdaptationCandidate]:
    axis_order = [axis.axis for axis in spec.axes]
    axis_values = [axis.values for axis in spec.axes]
    candidates: list[AdaptationCandidate] = []

    for combination in product(*axis_values):
        variation = dict(zip(axis_order, combination, strict=True))
        if not spec.include_seed and variation == spec.seed_variation:
            continue

        derivation_lineage = [
            DerivationStep(
                axis=axis_name,
                parent_value=spec.seed_variation[axis_name],
                value=variation[axis_name],
            )
            for axis_name in axis_order
            if variation[axis_name] != spec.seed_variation[axis_name]
        ]
        variation_key = "__".join(f"{axis_name}={variation[axis_name]}" for axis_name in axis_order)
        candidates.append(
            AdaptationCandidate(
                family_id=spec.family_id,
                seed_task_id=spec.seed_task_id,
                variation_key=variation_key,
                variation=variation,
                derivation_lineage=derivation_lineage,
            )
        )

    return candidates
