# ABOUTME: Loads self-contained authored Learning Study protocol directories.
# ABOUTME: Composes family members and relations into the existing executable study contract.

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import ValidationError

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_family import LearningFamilySpec
from aec_bench.contracts.learning_study import (
    ExperienceRelationSpec,
    ExperienceRole,
    LearningExperienceSpec,
    LearningStudyProtocolSpec,
    LearningStudySpec,
)
from aec_bench.experimentation.learning_studies.families import load_learning_family

BUILTIN_LEARNING_STUDY_PROTOCOLS = Path(__file__).with_name("protocols")
_STUDY_FILENAME = "study.toml"
_FAMILY_FILENAME = "family.toml"


def iter_learning_study_protocol_dirs(root: Path) -> tuple[Path, ...]:
    """List complete authored protocol directories in stable identity order."""

    if not root.is_dir():
        return ()
    return tuple(
        path
        for path in sorted(root.iterdir(), key=lambda item: item.name)
        if path.is_dir() and (path / _STUDY_FILENAME).is_file() and (path / _FAMILY_FILENAME).is_file()
    )


def load_learning_study_protocol(
    path: Path,
    *,
    agent: AgentConfig,
    compute: ComputeConfig,
    repetitions: int = 1,
) -> LearningStudySpec:
    """Load one protocol directory and bind its fixed plan to run configuration."""

    protocol = _load_protocol_spec(path / _STUDY_FILENAME)
    family = load_learning_family(path / _FAMILY_FILENAME)
    experiences, member_experiences = _compose_experiences(protocol, family)
    relations = _compose_relations(protocol, family, member_experiences)
    _validate_controlled_relation_coverage(protocol, experiences, relations)
    return LearningStudySpec(
        study_id=protocol.study_id,
        title=protocol.title,
        research_question=protocol.research_question,
        agent=agent,
        compute=compute,
        repetitions=repetitions,
        experiences=experiences,
        relations=relations,
        measurements=protocol.measurements,
        arms=protocol.arms,
    )


def _load_protocol_spec(path: Path) -> LearningStudyProtocolSpec:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return LearningStudyProtocolSpec.model_validate(data)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise ValueError(f"could not load learning study protocol {path}: {error}") from error


def _compose_experiences(
    protocol: LearningStudyProtocolSpec,
    family: LearningFamilySpec,
) -> tuple[tuple[LearningExperienceSpec, ...], dict[str, str]]:
    family_members = {item.member_id: item for item in family.members}
    experiences: list[LearningExperienceSpec] = []
    member_experiences: dict[str, str] = {}
    for declaration in protocol.experiences:
        member_id = declaration.family_member_id
        if member_id is None:
            assert declaration.task_id is not None
            task_id = declaration.task_id
        else:
            member = family_members.get(member_id)
            if member is None:
                raise ValueError(
                    f"protocol {protocol.study_id} experience {declaration.experience_id} references unknown "
                    f"family member {member_id!r}"
                )
            if member.probe_only != (declaration.role is ExperienceRole.PROBE):
                expected = "probe" if member.probe_only else "non-probe"
                raise ValueError(
                    f"protocol {protocol.study_id} experience {declaration.experience_id} must use family member "
                    f"{member_id!r} as {expected}"
                )
            task_id = member.task_id
            member_experiences[member_id] = declaration.experience_id
        experiences.append(
            LearningExperienceSpec(
                experience_id=declaration.experience_id,
                task_id=task_id,
                role=declaration.role,
            )
        )
    return tuple(experiences), member_experiences


def _compose_relations(
    protocol: LearningStudyProtocolSpec,
    family: LearningFamilySpec,
    member_experiences: dict[str, str],
) -> tuple[ExperienceRelationSpec, ...]:
    family_relations = {item.relation_id: item for item in family.relations}
    relations: list[ExperienceRelationSpec] = []
    for relation_id in protocol.relation_ids:
        relation = family_relations.get(relation_id)
        if relation is None:
            raise ValueError(f"protocol {protocol.study_id} references unknown family relation {relation_id!r}")
        referenced_members = {*relation.source_member_ids, relation.target_member_id}
        missing = referenced_members - set(member_experiences)
        if missing:
            raise ValueError(
                f"protocol {protocol.study_id} relation {relation_id} has members without experiences: "
                f"{sorted(missing)}"
            )
        relations.append(
            ExperienceRelationSpec(
                relation_id=relation.relation_id,
                purpose=relation.purpose,
                source_experience_ids=tuple(member_experiences[item] for item in relation.source_member_ids),
                target_experience_id=member_experiences[relation.target_member_id],
                invariant_claims=relation.invariant_claims,
                changed_dimensions=relation.changed_dimensions,
                rationale=relation.rationale,
            )
        )
    return tuple(relations)


def _validate_controlled_relation_coverage(
    protocol: LearningStudyProtocolSpec,
    experiences: tuple[LearningExperienceSpec, ...],
    relations: tuple[ExperienceRelationSpec, ...],
) -> None:
    probe_ids = {
        measurement.target_experience_id
        for measurement in protocol.measurements
        if measurement.comparator_arm_id is not None
    }
    uncovered = probe_ids - {item.target_experience_id for item in relations}
    if uncovered:
        raise ValueError(
            f"compared protocol {protocol.study_id} has probes without selected family relations: {sorted(uncovered)}"
        )


__all__ = (
    "BUILTIN_LEARNING_STUDY_PROTOCOLS",
    "iter_learning_study_protocol_dirs",
    "load_learning_study_protocol",
)
