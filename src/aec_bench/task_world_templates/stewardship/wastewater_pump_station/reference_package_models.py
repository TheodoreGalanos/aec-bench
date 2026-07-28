# ABOUTME: Defines immutable models for the wastewater pump-station reference package.
# ABOUTME: Deeply freezes validated JSON documents before production code can consume them.

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Self

type JsonScalar = str | int | bool
type MutableJsonValue = JsonScalar | list[MutableJsonValue] | dict[str, MutableJsonValue]
type MutableJsonObject = dict[str, MutableJsonValue]
type FrozenJsonValue = JsonScalar | tuple[FrozenJsonValue, ...] | MappingProxyType[str, FrozenJsonValue]
type FrozenJsonObject = MappingProxyType[str, FrozenJsonValue]


def _freeze_json(value: MutableJsonValue) -> FrozenJsonValue:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze_json(child) for key, child in value.items()})
    if isinstance(value, list):
        return tuple(_freeze_json(child) for child in value)
    return value


def _freeze_object(value: MutableJsonObject) -> FrozenJsonObject:
    return MappingProxyType({key: _freeze_json(child) for key, child in value.items()})


@dataclass(frozen=True)
class ReferencePackage:
    """An exact, deeply immutable wastewater pump-station reference package."""

    profile_id: str
    generation_id: str
    package_content_id: str
    manifest_content_id: str
    manifest: FrozenJsonObject
    physical_member: FrozenJsonObject
    physical_reference_checks: FrozenJsonObject
    public_profile: FrozenJsonObject

    @classmethod
    def from_documents(
        cls,
        *,
        profile_id: str,
        generation_id: str,
        package_content_id: str,
        manifest_content_id: str,
        manifest: MutableJsonObject,
        physical_member: MutableJsonObject,
        physical_reference_checks: MutableJsonObject,
        public_profile: MutableJsonObject,
    ) -> Self:
        """Copy validated documents into immutable production-owned data."""
        return cls(
            profile_id=profile_id,
            generation_id=generation_id,
            package_content_id=package_content_id,
            manifest_content_id=manifest_content_id,
            manifest=_freeze_object(manifest),
            physical_member=_freeze_object(physical_member),
            physical_reference_checks=_freeze_object(physical_reference_checks),
            public_profile=_freeze_object(public_profile),
        )
