# ABOUTME: Defines typed runtime observations and explicit provider resolution mappings.
# ABOUTME: Keeps requested run identities separate from observed provider and runtime identities.

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, JsonValue, field_validator, model_validator

from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.trial_record import ProviderRoute
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr

RuntimeObservationStatus = Literal["complete", "incomplete", "invalid"]
ResolutionKind = Literal["identity", "declared_alias", "declared_dated"]
MismatchKind = Literal["provider_route", "model_family", "model_identity", "tools", "limits", "resolved_identity"]


class ProviderResolutionMapping(FrozenStrictModel):
    """One versioned declaration for an expected provider resolution."""

    schema_version: Literal[1] = 1
    mapping_id: NonEmptyStr
    mapping_version: Annotated[int, Field(strict=True, gt=0)]
    requested_route: ProviderRoute
    resolved_route: ProviderRoute
    requested_model: NonEmptyStr
    resolved_model: NonEmptyStr
    requested_model_family: NonEmptyStr
    resolved_model_family: NonEmptyStr
    kind: ResolutionKind

    @model_validator(mode="after")
    def validate_mapping(self) -> Self:
        if self.kind == "identity":
            if (
                self.requested_route != self.resolved_route
                or self.requested_model != self.resolved_model
                or self.requested_model_family != self.resolved_model_family
            ):
                raise ValueError("identity provider resolution must preserve route, model, and model family")
        elif self.requested_model_family != self.resolved_model_family:
            raise ValueError("declared provider resolution must preserve model family")
        return self


class RuntimeMismatch(FrozenStrictModel):
    """One typed difference between requested and observed runtime state."""

    kind: MismatchKind
    requested: JsonValue | None = None
    observed: JsonValue | None = None
    detail: NonEmptyStr


class RuntimeObservation(FrozenStrictModel):
    """One immutable observation of provider and runtime identity for a trial."""

    schema_version: Literal[1] = 1
    observation_id: UUID
    trial_id: UUID
    attempt_id: UUID
    backend: NonEmptyStr
    runtime_image: NonEmptyStr
    runtime_version: NonEmptyStr
    requested_route: ProviderRoute
    resolved_route: ProviderRoute | None = None
    requested_model: NonEmptyStr
    resolved_model: NonEmptyStr | None = None
    requested_model_family: NonEmptyStr
    resolved_model_family: NonEmptyStr | None = None
    adapter_version: NonEmptyStr
    requested_tool_versions: dict[str, str] = Field(default_factory=dict)
    observed_tool_versions: dict[str, str] = Field(default_factory=dict)
    requested_limits: dict[str, JsonValue] = Field(default_factory=dict)
    observed_limits: dict[str, JsonValue] = Field(default_factory=dict)
    resource_observations: dict[str, JsonValue] = Field(default_factory=dict)
    resolution: ProviderResolutionMapping | None = None
    status: RuntimeObservationStatus
    mismatches: tuple[RuntimeMismatch, ...] = ()
    started_at: datetime
    finished_at: datetime | None = None

    @field_validator("observation_id", "trial_id", "attempt_id")
    @classmethod
    def validate_ids(cls, value: UUID) -> UUID:
        return validate_uuidv7(value)

    @field_validator("started_at", "finished_at")
    @classmethod
    def validate_aware_times(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("runtime observation timestamps must include a timezone")
        return value

    @field_validator("requested_tool_versions", "observed_tool_versions")
    @classmethod
    def validate_tool_versions(cls, value: dict[str, str]) -> dict[str, str]:
        if any(not name.strip() or not version.strip() for name, version in value.items()):
            raise ValueError("runtime observation tool names and versions must not be blank")
        return value

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        if self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("runtime observation cannot finish before it starts")
        mismatch_kinds = [mismatch.kind for mismatch in self.mismatches]
        if len(mismatch_kinds) != len(set(mismatch_kinds)):
            raise ValueError("runtime observation mismatch kinds must be unique")
        expected_mismatches: set[MismatchKind] = set()
        mapped_resolution = self.resolution is not None
        if self.resolved_route is None or self.resolved_model is None or self.resolved_model_family is None:
            expected_mismatches.add("resolved_identity")
        if self.resolved_route is not None and self.resolved_route != self.requested_route and not mapped_resolution:
            expected_mismatches.add("provider_route")
        if self.resolved_model_family is not None and self.resolved_model_family != self.requested_model_family:
            expected_mismatches.add("model_family")
        if self.resolved_model is not None and self.resolved_model != self.requested_model and not mapped_resolution:
            expected_mismatches.add("model_identity")
        if self.requested_tool_versions != self.observed_tool_versions:
            expected_mismatches.add("tools")
        if self.requested_limits != self.observed_limits:
            expected_mismatches.add("limits")
        actual_mismatches = {mismatch.kind for mismatch in self.mismatches}
        if actual_mismatches != expected_mismatches:
            raise ValueError("runtime observation mismatches must exactly describe observed differences")
        expected_status: RuntimeObservationStatus
        if not expected_mismatches:
            expected_status = "complete"
        elif expected_mismatches == {"resolved_identity"}:
            expected_status = "incomplete"
        else:
            expected_status = "invalid"
        if self.status != expected_status:
            raise ValueError(f"runtime observation differences require status {expected_status}")
        if self.resolution is not None:
            if self.resolved_route is None or self.resolved_model is None or self.resolved_model_family is None:
                raise ValueError("provider resolution mapping requires a complete observed identity")
            if self.resolution.requested_route != self.requested_route:
                raise ValueError("provider resolution mapping requested route does not match observation")
            if self.resolution.requested_model != self.requested_model:
                raise ValueError("provider resolution mapping requested model does not match observation")
            if self.resolution.requested_model_family != self.requested_model_family:
                raise ValueError("provider resolution mapping requested model family does not match observation")
            if self.resolved_route is not None and self.resolution.resolved_route != self.resolved_route:
                raise ValueError("provider resolution mapping resolved route does not match observation")
            if self.resolved_model is not None and self.resolution.resolved_model != self.resolved_model:
                raise ValueError("provider resolution mapping resolved model does not match observation")
            if (
                self.resolved_model_family is not None
                and self.resolution.resolved_model_family != self.resolved_model_family
            ):
                raise ValueError("provider resolution mapping resolved model family does not match observation")
        return self


def observe_runtime(
    *,
    observation_id: UUID,
    trial_id: UUID,
    attempt_id: UUID,
    backend: str,
    runtime_image: str,
    runtime_version: str,
    requested_route: ProviderRoute,
    requested_model: str,
    requested_model_family: str,
    adapter_version: str,
    requested_tool_versions: dict[str, str],
    observed_tool_versions: dict[str, str],
    requested_limits: dict[str, JsonValue],
    observed_limits: dict[str, JsonValue],
    resource_observations: dict[str, JsonValue],
    started_at: datetime,
    finished_at: datetime | None = None,
    resolved_route: ProviderRoute | None = None,
    resolved_model: str | None = None,
    resolved_model_family: str | None = None,
    resolution: ProviderResolutionMapping | None = None,
) -> RuntimeObservation:
    """Classify one observed runtime against the requested provider condition."""

    mismatches: list[RuntimeMismatch] = []
    if resolved_route is None or resolved_model is None or resolved_model_family is None:
        mismatches.append(
            RuntimeMismatch(kind="resolved_identity", detail="provider did not return a complete identity")
        )
        status: RuntimeObservationStatus = "incomplete"
    else:
        status = "complete"
    if resolved_route is not None and resolved_route != requested_route and resolution is None:
        mismatches.append(
            RuntimeMismatch(
                kind="provider_route",
                requested=requested_route.model_dump(mode="json"),
                observed=resolved_route.model_dump(mode="json"),
                detail="provider route changed without a declared mapping",
            )
        )
    if resolved_model_family is not None and resolved_model_family != requested_model_family:
        mismatches.append(
            RuntimeMismatch(
                kind="model_family",
                requested=requested_model_family,
                observed=resolved_model_family,
                detail="resolved model family differs from the requested family",
            )
        )
    if resolved_model is not None and resolved_model != requested_model and resolution is None:
        mismatches.append(
            RuntimeMismatch(
                kind="model_identity",
                requested=requested_model,
                observed=resolved_model,
                detail="resolved model differs without a declared mapping",
            )
        )
    if requested_tool_versions != observed_tool_versions:
        mismatches.append(
            RuntimeMismatch(
                kind="tools",
                requested={name: version for name, version in requested_tool_versions.items()},
                observed={name: version for name, version in observed_tool_versions.items()},
                detail="runtime tool versions differ from the requested tool set",
            )
        )
    if requested_limits != observed_limits:
        mismatches.append(
            RuntimeMismatch(
                kind="limits",
                requested=requested_limits,
                observed=observed_limits,
                detail="runtime limits differ from the requested limits",
            )
        )
    if mismatches and {mismatch.kind for mismatch in mismatches} != {"resolved_identity"}:
        status = "invalid"
    return RuntimeObservation(
        observation_id=observation_id,
        trial_id=trial_id,
        attempt_id=attempt_id,
        backend=backend,
        runtime_image=runtime_image,
        runtime_version=runtime_version,
        requested_route=requested_route,
        resolved_route=resolved_route,
        requested_model=requested_model,
        resolved_model=resolved_model,
        requested_model_family=requested_model_family,
        resolved_model_family=resolved_model_family,
        adapter_version=adapter_version,
        requested_tool_versions=requested_tool_versions,
        observed_tool_versions=observed_tool_versions,
        requested_limits=requested_limits,
        observed_limits=observed_limits,
        resource_observations=resource_observations,
        resolution=resolution,
        status=status,
        mismatches=tuple(mismatches),
        started_at=started_at,
        finished_at=finished_at,
    )


__all__ = (
    "ProviderResolutionMapping",
    "RuntimeMismatch",
    "RuntimeObservation",
    "RuntimeObservationStatus",
    "observe_runtime",
)
