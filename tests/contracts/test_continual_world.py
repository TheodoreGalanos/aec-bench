# ABOUTME: Tests content-pinned continual-world definition and profile references.
# ABOUTME: Rejects empty, mixed, duplicate, unstable, or changed registration data.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.continual_world import (
    ContinualWorldDefinitionSpec,
    ContinualWorldProfileRef,
)


def _profile(
    profile_id: str,
    *,
    task_world_id: str = "world-a",
    profile_version: str = "1",
    digest: str = "a" * 64,
) -> ContinualWorldProfileRef:
    return ContinualWorldProfileRef(
        task_world_id=task_world_id,
        profile_id=profile_id,
        profile_version=profile_version,
        profile_content_sha256=digest,
    )


def test_definition_requires_at_least_one_profile() -> None:
    with pytest.raises(ValidationError, match="at least one profile"):
        ContinualWorldDefinitionSpec(
            task_world_id="world-a",
            definition_version="1",
            implementation_content_sha256="b" * 64,
            profiles=(),
        )


def test_definition_rejects_cross_world_profile() -> None:
    with pytest.raises(ValidationError, match="same task world"):
        ContinualWorldDefinitionSpec(
            task_world_id="world-a",
            definition_version="1",
            implementation_content_sha256="b" * 64,
            profiles=(_profile("profile-a", task_world_id="world-b"),),
        )


def test_definition_rejects_duplicate_profile_version() -> None:
    profile = _profile("profile-a")

    with pytest.raises(ValidationError, match="profile identities must be distinct"):
        ContinualWorldDefinitionSpec(
            task_world_id="world-a",
            definition_version="1",
            implementation_content_sha256="b" * 64,
            profiles=(profile, profile),
        )


def test_definition_requires_stable_profile_order() -> None:
    with pytest.raises(ValidationError, match="profiles must use stable order"):
        ContinualWorldDefinitionSpec(
            task_world_id="world-a",
            definition_version="1",
            implementation_content_sha256="b" * 64,
            profiles=(_profile("profile-b"), _profile("profile-a")),
        )


def test_profile_ref_rejects_invalid_content_hash() -> None:
    with pytest.raises(ValidationError, match="64 lowercase hexadecimal"):
        _profile("profile-a", digest="NOT-A-SHA256")


def test_definition_rejects_invalid_implementation_hash() -> None:
    with pytest.raises(ValidationError, match="64 lowercase hexadecimal"):
        ContinualWorldDefinitionSpec(
            task_world_id="world-a",
            definition_version="1",
            implementation_content_sha256="NOT-A-SHA256",
            profiles=(_profile("profile-a"),),
        )


def test_definition_rejects_changed_content_identity() -> None:
    with pytest.raises(ValidationError, match="does not match canonical model content"):
        ContinualWorldDefinitionSpec(
            task_world_id="world-a",
            definition_version="1",
            implementation_content_sha256="b" * 64,
            profiles=(_profile("profile-a"),),
            content_sha256="f" * 64,
        )
