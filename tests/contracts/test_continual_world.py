# ABOUTME: Tests current unversioned continual-world build, profile, and installed command values.
# ABOUTME: Rejects invalid artifact hashes, mixed ownership, stale profiles, and operation payload bags.

from __future__ import annotations

from collections.abc import Callable

import pytest
from pydantic import TypeAdapter, ValidationError

from aec_bench.contracts.continual_world import (
    ContinualControlCapabilitiesRequest,
    ContinualWorldControlRequest,
    ContinualWorldProfileRef,
    WorldBuildRef,
)
from aec_bench.worlds.runtime.definition import ContinualWorldDefinition, LoadedContinualWorldProfile


def _profile(profile_id: str, *, task_world_id: str = "world-a", digest: str = "a" * 64) -> ContinualWorldProfileRef:
    return ContinualWorldProfileRef(
        task_world_id=task_world_id,
        profile_id=profile_id,
        profile_content_sha256=digest,
    )


def _build(*, task_world_id: str = "world-a", digest: str = "b" * 64) -> WorldBuildRef:
    return WorldBuildRef(
        task_world_id=task_world_id,
        entry_point="example.world:definition",
        artifact_sha256=digest,
    )


def _definition(*profiles: ContinualWorldProfileRef) -> ContinualWorldDefinition:
    return ContinualWorldDefinition(
        build=_build(),
        profiles=profiles,
        profile_loader=lambda reference: LoadedContinualWorldProfile(reference=reference, value=object()),
    )


def test_definition_requires_at_least_one_profile() -> None:
    with pytest.raises(ValueError, match="at least one profile"):
        _definition()


def test_definition_rejects_cross_world_duplicate_or_unstable_profiles() -> None:
    with pytest.raises(ValueError, match="same task world"):
        _definition(_profile("profile-a", task_world_id="world-b"))
    profile = _profile("profile-a")
    with pytest.raises(ValueError, match="identities must be distinct"):
        _definition(profile, profile)
    with pytest.raises(ValueError, match="stable order"):
        _definition(_profile("profile-b"), _profile("profile-a"))


@pytest.mark.parametrize("factory", (lambda: _profile("profile-a", digest="bad"), lambda: _build(digest="bad")))
def test_current_artifact_references_require_sha256(factory: Callable[[], object]) -> None:
    with pytest.raises(ValueError, match="64 lowercase hexadecimal"):
        factory()


def test_installed_control_payload_is_a_strict_discriminated_union() -> None:
    adapter: TypeAdapter[ContinualWorldControlRequest] = TypeAdapter(ContinualWorldControlRequest)
    request = adapter.validate_python({"operation": "capabilities", "authority_id": "host"})

    assert request == ContinualControlCapabilitiesRequest(operation="capabilities", authority_id="host")
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {
                "operation": "capabilities",
                "authority_id": "host",
                "control_request": {"unexpected": True},
            }
        )
