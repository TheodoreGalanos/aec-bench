# ABOUTME: Defines content-pinned continual-world definition and profile references.
# ABOUTME: Keeps task state, actions, controls, paths, and verifier data outside the shared boundary.

from __future__ import annotations

from typing import Final, Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, validate_sha256
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

CONTINUAL_WORLD_DEFINITION_SCHEMA_VERSION: Final[Literal["aecbench.continual-world-definition.v1"]] = (
    "aecbench.continual-world-definition.v1"
)
CONTINUAL_WORLD_PROFILE_SCHEMA_VERSION: Final[Literal["aecbench.continual-world-profile-ref.v1"]] = (
    "aecbench.continual-world-profile-ref.v1"
)


class ContinualWorldProfileRef(FrozenStrictModel):
    """Exact identity of one task-owned continual-world profile."""

    schema_version: Literal["aecbench.continual-world-profile-ref.v1"] = CONTINUAL_WORLD_PROFILE_SCHEMA_VERSION
    task_world_id: NonEmptyStr
    profile_id: NonEmptyStr
    profile_version: NonEmptyStr
    profile_content_sha256: str

    @field_validator("profile_content_sha256")
    @classmethod
    def validate_profile_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class ContinualWorldDefinitionRef(FrozenStrictModel):
    """Content-pinned recovery reference for one registered world definition."""

    task_world_id: NonEmptyStr
    definition_version: NonEmptyStr
    content_sha256: str

    @field_validator("content_sha256")
    @classmethod
    def validate_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class ContinualWorldDefinitionSpec(ContentAddressedModel):
    """Serializable identity and supported profiles for one task world."""

    schema_version: Literal["aecbench.continual-world-definition.v1"] = CONTINUAL_WORLD_DEFINITION_SCHEMA_VERSION
    task_world_id: NonEmptyStr
    definition_version: NonEmptyStr
    implementation_content_sha256: str
    profiles: tuple[ContinualWorldProfileRef, ...]

    @field_validator("implementation_content_sha256")
    @classmethod
    def validate_implementation_content_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_profiles(self) -> Self:
        if not self.profiles:
            raise ValueError("continual-world definition requires at least one profile")
        if any(profile.task_world_id != self.task_world_id for profile in self.profiles):
            raise ValueError("continual-world profiles must belong to the same task world")
        keys = tuple((profile.profile_id, profile.profile_version) for profile in self.profiles)
        if len(keys) != len(set(keys)):
            raise ValueError("continual-world profile identities must be distinct")
        if keys != tuple(sorted(keys)):
            raise ValueError("continual-world profiles must use stable order")
        return self

    @property
    def ref(self) -> ContinualWorldDefinitionRef:
        """Return the exact definition reference used by new runs and recovery."""
        return ContinualWorldDefinitionRef(
            task_world_id=self.task_world_id,
            definition_version=self.definition_version,
            content_sha256=self.content_sha256,
        )
