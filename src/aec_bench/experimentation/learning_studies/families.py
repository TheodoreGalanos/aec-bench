# ABOUTME: Loads and resolves optional TOML learning-family overlays.
# ABOUTME: Converts authored members to exact task inputs without task execution or a global catalogue.

from __future__ import annotations

import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from aec_bench.contracts.learning_family import LearningFamilyRelation, LearningFamilySpec
from aec_bench.contracts.learning_study import ExperienceRole, LearningExperienceSpec
from aec_bench.tasks.instance import ResolvedTaskInstance


@dataclass(frozen=True)
class ResolvedLearningFamilyMember:
    member_id: str
    probe_only: bool
    task: ResolvedTaskInstance


@dataclass(frozen=True)
class ResolvedLearningFamily:
    spec: LearningFamilySpec
    members: tuple[ResolvedLearningFamilyMember, ...]


@dataclass(frozen=True)
class ResolvedLearningRelation:
    relation: LearningFamilyRelation
    sources: tuple[ResolvedLearningFamilyMember, ...]
    target: ResolvedLearningFamilyMember


def load_learning_family(path: Path) -> LearningFamilySpec:
    """Parse one caller-selected family file with strict TOML validation."""

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return LearningFamilySpec.model_validate(data)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as error:
        raise ValueError(f"could not load learning family {path}: {error}") from error


def resolve_learning_family(
    family: LearningFamilySpec,
    resolve_task: Callable[[str], ResolvedTaskInstance],
) -> ResolvedLearningFamily:
    """Resolve every exact member task before a protocol builder uses the family."""

    resolved: list[ResolvedLearningFamilyMember] = []
    for member in family.members:
        try:
            task = resolve_task(member.task_id)
        except Exception as error:
            raise ValueError(
                f"family {family.family_id} member {member.member_id} could not resolve task {member.task_id}: {error}"
            ) from error
        if task.task.task_id != member.task_id:
            raise ValueError(
                f"family {family.family_id} member {member.member_id} resolved task {task.task.task_id}, "
                f"expected {member.task_id}"
            )
        resolved.append(
            ResolvedLearningFamilyMember(
                member_id=member.member_id,
                probe_only=member.probe_only,
                task=task,
            )
        )
    return ResolvedLearningFamily(spec=family, members=tuple(resolved))


def resolve_learning_relation(
    family: ResolvedLearningFamily,
    relation_id: str,
) -> ResolvedLearningRelation:
    """Return one directed, author-declared relation by exact identity."""

    relation = next((item for item in family.spec.relations if item.relation_id == relation_id), None)
    if relation is None:
        raise ValueError(f"unknown relation {relation_id!r} in family {family.spec.family_id}")
    members = {item.member_id: item for item in family.members}
    return ResolvedLearningRelation(
        relation=relation,
        sources=tuple(members[item] for item in relation.source_member_ids),
        target=members[relation.target_member_id],
    )


def relation_to_experience_specs(
    relation: ResolvedLearningRelation,
) -> tuple[LearningExperienceSpec, ...]:
    """Create acquisition sources and a protected probe from one resolved relation."""

    protected_sources = [source.member_id for source in relation.sources if source.probe_only]
    if protected_sources:
        raise ValueError(f"probe-only members cannot become acquisition experiences: {protected_sources}")
    if not relation.target.probe_only:
        raise ValueError(f"relation target must be probe-only: {relation.target.member_id}")
    return (
        *(
            LearningExperienceSpec(
                experience_id=source.member_id,
                task_id=source.task.task.task_id,
                role=ExperienceRole.ACQUISITION,
            )
            for source in relation.sources
        ),
        LearningExperienceSpec(
            experience_id=relation.target.member_id,
            task_id=relation.target.task.task.task_id,
            role=ExperienceRole.PROBE,
        ),
    )


__all__ = (
    "ResolvedLearningFamily",
    "ResolvedLearningFamilyMember",
    "ResolvedLearningRelation",
    "load_learning_family",
    "relation_to_experience_specs",
    "resolve_learning_family",
    "resolve_learning_relation",
)
