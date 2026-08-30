# ABOUTME: Defines exact family-owned release bindings for planned world and lifecycle trials.
# ABOUTME: Keeps explicit UUID versions separate from hashes that verify executable content.

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from aec_bench.contracts.artifacts import Sha256
from aec_bench.contracts.identity import EntityIdentity
from aec_bench.contracts.interactive_world import InteractiveWorldProfileRef, WorldBuildRef
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr


class WorldExecutionRelease(FrozenStrictModel):
    """Bind a planned world trial to one versioned world and profile release."""

    kind: Literal["world"] = "world"
    world_identity: EntityIdentity
    profile_identity: EntityIdentity
    world_build: WorldBuildRef
    profile: InteractiveWorldProfileRef

    @model_validator(mode="after")
    def validate_world_relationship(self) -> Self:
        if self.profile.task_world_id != self.world_build.task_world_id:
            raise ValueError("planned world profile must belong to the planned world build")
        return self


class LifecycleExecutionRelease(FrozenStrictModel):
    """Bind a planned lifecycle trial to one versioned lifecycle and optional variant."""

    kind: Literal["lifecycle"] = "lifecycle"
    lifecycle_identity: EntityIdentity
    variant_identity: EntityIdentity | None = None
    visibility: Literal["public", "holdout"]
    template_id: NonEmptyStr
    lifecycle_id: NonEmptyStr
    variant_id: NonEmptyStr | None = None
    lifecycle_spec_sha256: Sha256
    package_sha256: Sha256
    executable_artifact_sha256: Sha256
    operation_protocol_sha256: Sha256 | None = None

    @model_validator(mode="after")
    def validate_variant_relationship(self) -> Self:
        if (self.variant_identity is None) != (self.variant_id is None):
            raise ValueError("planned lifecycle variant identity and variant ID must be supplied together")
        return self


type FamilyExecutionRelease = Annotated[
    WorldExecutionRelease | LifecycleExecutionRelease,
    Field(discriminator="kind"),
]


__all__ = (
    "FamilyExecutionRelease",
    "LifecycleExecutionRelease",
    "WorldExecutionRelease",
)
