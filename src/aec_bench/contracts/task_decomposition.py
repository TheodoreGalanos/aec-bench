# ABOUTME: Contract models for LLM-reviewed task part decomposition sidecars.
# ABOUTME: Validates recombinable task parts used by population and crossover workflows.

from typing import Literal

from pydantic import Field, field_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel, ensure_relative_path

PartKind = Literal[
    "context",
    "input",
    "lookup",
    "formula",
    "intermediate",
    "threshold",
    "output",
    "verifier",
    "difficulty",
]


class TaskPart(StrictModel):
    id: NonEmptyStr
    kind: PartKind
    summary: NonEmptyStr
    depends_on: list[str] = Field(default_factory=list)
    recombinable: bool
    crossover_role: NonEmptyStr

    @field_validator("summary", "crossover_role")
    @classmethod
    def validate_complete_text(cls, value: str) -> str:
        return _ensure_complete_text(value)


class TaskDecomposition(StrictModel):
    task_id: NonEmptyStr
    source_genome_path: NonEmptyStr
    parts: list[TaskPart]
    trajectory_checks: list[str] = Field(default_factory=list)
    crossover_notes: list[str] = Field(default_factory=list)

    @field_validator("source_genome_path")
    @classmethod
    def validate_source_genome_path(cls, value: str) -> str:
        return ensure_relative_path(value)

    @field_validator("trajectory_checks", "crossover_notes")
    @classmethod
    def validate_text_items(cls, value: list[str]) -> list[str]:
        return [_ensure_complete_text(item) for item in value]


class TaskDecompositionBatch(StrictModel):
    version: int = 1
    reviewer: NonEmptyStr
    scope: NonEmptyStr
    decompositions: list[TaskDecomposition]


def _ensure_complete_text(value: str) -> str:
    if "..." in value:
        msg = "decomposition text must not contain ellipses"
        raise ValueError(msg)
    dangling_terms = {
        "and",
        "or",
        "from",
        "with",
        "using",
        "then",
        "plus",
        "by",
        "for",
        "to",
        "of",
    }
    last_word = value.rstrip(" .,;:").split(" ")[-1].lower()
    if last_word in dangling_terms:
        msg = f"decomposition text appears incomplete: {value}"
        raise ValueError(msg)
    return value
