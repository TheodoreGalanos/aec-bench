# ABOUTME: Defines optional learning-family overlays for exact existing tasks.
# ABOUTME: Keeps authored transfer claims outside task and adaptation contracts.

from __future__ import annotations

from enum import StrEnum

from pydantic import field_validator, model_validator

from aec_bench.contracts.learning_study import ExperienceRelationPurpose
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class LearningDimensionKind(StrEnum):
    SURFACE = "surface"
    PARAMETER = "parameter"
    CAUSAL = "causal"
    APPLICABILITY = "applicability"
    OBSERVABILITY = "observability"
    AUTHORITY_OR_RESOURCE = "authority_or_resource"
    REGIME = "regime"
    COMPONENT = "component"


class LearningDimensionSpec(FrozenStrictModel):
    dimension_id: NonEmptyStr
    kind: LearningDimensionKind
    description: NonEmptyStr


class LearningFamilyMember(FrozenStrictModel):
    member_id: NonEmptyStr
    task_id: NonEmptyStr
    description: str | None = None
    probe_only: bool = False
    dimension_values: dict[NonEmptyStr, NonEmptyStr]


class LearningFamilyRelation(FrozenStrictModel):
    relation_id: NonEmptyStr
    purpose: ExperienceRelationPurpose
    source_member_ids: tuple[NonEmptyStr, ...]
    target_member_id: NonEmptyStr
    invariant_dimensions: tuple[NonEmptyStr, ...] = ()
    invariant_claims: tuple[NonEmptyStr, ...]
    changed_dimensions: tuple[NonEmptyStr, ...]
    rationale: NonEmptyStr

    @field_validator(
        "source_member_ids",
        "invariant_dimensions",
        "invariant_claims",
        "changed_dimensions",
    )
    @classmethod
    def validate_unique_values(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("learning-family relation values must be unique")
        return value


class LearningFamilySpec(FrozenStrictModel):
    family_id: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    source_task_paths: tuple[NonEmptyStr, ...]
    dimensions: tuple[LearningDimensionSpec, ...]
    members: tuple[LearningFamilyMember, ...]
    relations: tuple[LearningFamilyRelation, ...]

    @model_validator(mode="after")
    def validate_family(self) -> LearningFamilySpec:
        if not self.source_task_paths:
            raise ValueError("learning family requires at least one task-authority path")
        if len(self.members) < 2:
            raise ValueError("learning family requires at least two members")
        if not self.dimensions:
            raise ValueError("learning family requires at least one dimension")
        if not self.relations:
            raise ValueError("learning family requires at least one relation")

        _require_unique("dimension", [item.dimension_id for item in self.dimensions])
        _require_unique("member", [item.member_id for item in self.members])
        _require_unique("member task", [item.task_id for item in self.members])
        _require_unique("relation", [item.relation_id for item in self.relations])

        dimensions = {item.dimension_id: item for item in self.dimensions}
        members = {item.member_id: item for item in self.members}
        dimension_ids = set(dimensions)
        for member in self.members:
            supplied = set(member.dimension_values)
            if supplied != dimension_ids:
                missing = sorted(dimension_ids - supplied)
                unknown = sorted(supplied - dimension_ids)
                raise ValueError(
                    f"member {member.member_id} dimension values do not match declarations; "
                    f"missing={missing}, unknown={unknown}"
                )

        for relation in self.relations:
            _validate_relation(relation=relation, dimensions=dimensions, members=members)
        return self


def _validate_relation(
    *,
    relation: LearningFamilyRelation,
    dimensions: dict[str, LearningDimensionSpec],
    members: dict[str, LearningFamilyMember],
) -> None:
    if not relation.source_member_ids:
        raise ValueError(f"relation {relation.relation_id} requires at least one source")
    unknown_members = ({*relation.source_member_ids, relation.target_member_id}) - set(members)
    if unknown_members:
        raise ValueError(f"relation {relation.relation_id} has unknown members: {sorted(unknown_members)}")
    if relation.target_member_id in relation.source_member_ids:
        raise ValueError(f"relation {relation.relation_id} target must differ from its sources")

    if relation.purpose is ExperienceRelationPurpose.COMPOSITION:
        if len(relation.source_member_ids) < 2:
            raise ValueError(f"composition relation {relation.relation_id} requires at least two sources")
    elif len(relation.source_member_ids) != 1:
        raise ValueError(f"{relation.purpose.value} relation {relation.relation_id} requires exactly one source")

    referenced_dimensions = {*relation.invariant_dimensions, *relation.changed_dimensions}
    unknown_dimensions = referenced_dimensions - set(dimensions)
    if unknown_dimensions:
        raise ValueError(f"relation {relation.relation_id} has unknown dimensions: {sorted(unknown_dimensions)}")
    overlap = set(relation.invariant_dimensions).intersection(relation.changed_dimensions)
    if overlap:
        raise ValueError(
            f"relation {relation.relation_id} dimensions cannot be both invariant and changed: {sorted(overlap)}"
        )

    sources = [members[item] for item in relation.source_member_ids]
    target = members[relation.target_member_id]
    for dimension_id in relation.invariant_dimensions:
        values = {source.dimension_values[dimension_id] for source in sources}
        values.add(target.dimension_values[dimension_id])
        if len(values) != 1:
            raise ValueError(f"relation {relation.relation_id} invariant dimension differs: {dimension_id}")
    for dimension_id in relation.changed_dimensions:
        if all(source.dimension_values[dimension_id] == target.dimension_values[dimension_id] for source in sources):
            raise ValueError(f"relation {relation.relation_id} changed dimension does not differ: {dimension_id}")

    if relation.purpose is ExperienceRelationPurpose.TRANSFER:
        if not relation.invariant_dimensions and not relation.invariant_claims:
            raise ValueError(f"transfer relation {relation.relation_id} requires an invariant")
        if not target.probe_only:
            raise ValueError(f"transfer relation {relation.relation_id} target must be probe-only")
    if relation.purpose is ExperienceRelationPurpose.BOUNDARY:
        changed_kinds = {dimensions[item].kind for item in relation.changed_dimensions}
        if not changed_kinds.intersection({LearningDimensionKind.APPLICABILITY, LearningDimensionKind.CAUSAL}):
            raise ValueError(
                f"boundary relation {relation.relation_id} must change an applicability or causal dimension"
            )
    if relation.purpose is ExperienceRelationPurpose.COMPOSITION:
        changed_kinds = {dimensions[item].kind for item in relation.changed_dimensions}
        if LearningDimensionKind.COMPONENT not in changed_kinds and not any(
            "component" in claim.lower() for claim in relation.invariant_claims
        ):
            raise ValueError(f"composition relation {relation.relation_id} requires a component dimension or claim")


def _require_unique(label: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"learning-family {label} ids must be unique")


__all__ = (
    "LearningDimensionKind",
    "LearningDimensionSpec",
    "LearningFamilyMember",
    "LearningFamilyRelation",
    "LearningFamilySpec",
)
