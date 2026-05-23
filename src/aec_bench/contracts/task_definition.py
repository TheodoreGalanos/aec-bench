# ABOUTME: Contract models for runnable task definitions in the aec-bench Python implementation.
# ABOUTME: Defines task metadata, environment, verifier, and tool declarations at the task boundary.

from enum import StrEnum
from typing import Any

from pydantic import Field, PositiveInt, field_validator

from aec_bench.contracts.validators import (
    NonEmptyStr,
    StrictModel,
    ensure_optional_non_empty_string,
    ensure_optional_relative_path,
    ensure_relative_path,
)


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Lifecycle(StrEnum):
    PROPOSED = "proposed"
    ACTIVE = "active"
    DEPRECATED = "deprecated"
    RETIRED = "retired"


class Visibility(StrEnum):
    PUBLIC = "public"
    HOLDOUT = "holdout"


class ToolSpec(StrictModel):
    name: NonEmptyStr
    source: str
    description: NonEmptyStr
    returns_image: bool = False

    @field_validator("source")
    @classmethod
    def validate_relative_source(cls, value: str) -> str:
        return ensure_relative_path(value)


class EnvironmentSpec(StrictModel):
    dockerfile: str
    compose_file: str | None = None
    manifest: str | None = None
    build_args: dict[str, str] = Field(default_factory=dict)
    tools: list[ToolSpec] = Field(default_factory=list)

    @field_validator("dockerfile")
    @classmethod
    def validate_dockerfile(cls, value: str) -> str:
        return ensure_relative_path(value)

    @field_validator("compose_file", "manifest")
    @classmethod
    def validate_optional_relative_paths(cls, value: str | None) -> str | None:
        return ensure_optional_relative_path(value)


class VerifierSpec(StrictModel):
    script: NonEmptyStr
    expected_output_path: NonEmptyStr
    reward_path: NonEmptyStr
    details_path: str | None = None

    @field_validator("details_path")
    @classmethod
    def validate_optional_path(cls, value: str | None) -> str | None:
        return ensure_optional_non_empty_string(value)


class TaskDefinition(StrictModel):
    task_id: NonEmptyStr
    task_type: NonEmptyStr
    domain: NonEmptyStr
    category: NonEmptyStr
    difficulty: Difficulty
    lifecycle: Lifecycle
    visibility: Visibility
    instruction: NonEmptyStr
    environment: EnvironmentSpec
    verifier: VerifierSpec
    timeout_seconds: PositiveInt
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def runnable(self) -> bool:
        return self.lifecycle not in {Lifecycle.PROPOSED, Lifecycle.RETIRED}
