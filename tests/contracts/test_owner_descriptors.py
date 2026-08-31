# ABOUTME: Tests stable identities and member ownership for registered worlds and lifecycles.
# ABOUTME: Proves UUIDv7, key, version, parent, uniqueness, and registration coverage rules.

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from aec_bench.contracts.identity import EntityIdentity, EntityKey, MemberIdentity
from aec_bench.lifecycles.catalogue import (
    lifecycle_definition,
    lifecycle_identity,
    lifecycle_template_ids,
    lifecycle_variant_identity,
)
from aec_bench.worlds.catalogue import _catalogue


def test_entity_identity_requires_uuidv7_readable_key_and_positive_version() -> None:
    valid = EntityIdentity(
        id=UUID("01a056f1-af83-7516-90f6-ceddb36390bd"),
        key=EntityKey("worlds/example"),
        version=1,
    )

    assert valid.id.version == 7
    assert isinstance(valid.key, EntityKey)
    assert valid.version == 1

    with pytest.raises(ValueError, match="UUIDv7"):
        EntityIdentity(id=uuid4(), key=EntityKey("worlds/example"), version=1)
    with pytest.raises(ValueError, match="lowercase ASCII"):
        EntityIdentity.model_validate({"id": valid.id, "key": "Worlds/Example", "version": 1})
    with pytest.raises(ValueError, match="greater than 0"):
        EntityIdentity(id=valid.id, key=EntityKey("worlds/example"), version=0)


def test_member_identity_requires_uuidv7_parent_and_definition_membership() -> None:
    parent = EntityIdentity(
        id=UUID("01a056f1-af83-7516-90f6-ceddb36390bd"),
        key=EntityKey("worlds/example"),
        version=1,
    )
    member = MemberIdentity(
        id=UUID("01a056f1-af83-760b-baf8-525a9b37e150"),
        key=EntityKey("worlds/example/profile"),
        version=1,
        parent_id=parent.id,
        registration_id="profile.external.v1",
    )

    assert member.parent_id == parent.id
    with pytest.raises(ValueError, match="UUIDv7"):
        MemberIdentity(
            id=member.id,
            key=member.key,
            version=1,
            parent_id=UUID(int=0),
            registration_id=member.registration_id,
        )
    with pytest.raises(ValueError, match="must differ"):
        MemberIdentity(
            id=member.id,
            key=member.key,
            version=1,
            parent_id=member.id,
            registration_id=member.registration_id,
        )
    with pytest.raises(ValueError, match="non-empty"):
        MemberIdentity(
            id=member.id,
            key=member.key,
            version=1,
            parent_id=member.parent_id,
            registration_id=" ",
        )


def test_current_world_and_lifecycle_registrations_have_unique_complete_identity_sets() -> None:
    worlds = _catalogue().definitions
    lifecycles = tuple(lifecycle_definition(template_id) for template_id in sorted(lifecycle_template_ids()))
    identities = [
        identity for definition in worlds for identity in (definition.identity, *definition.profile_identities)
    ] + [identity for definition in lifecycles for identity in (definition.identity, *definition.variant_identities)]

    assert all(identity.id.version == 7 for identity in identities)
    assert all(identity.version == 1 for identity in identities)
    assert len(identities) == len({identity.id for identity in identities})
    assert len(identities) == len({identity.key for identity in identities})
    for world_definition in worlds:
        assert all(member.parent_id == world_definition.identity.id for member in world_definition.profile_identities)
        for profile in world_definition.profiles:
            assert world_definition.profile_identity(profile.profile_id).registration_id == profile.profile_id
    for lifecycle_definition_value in lifecycles:
        assert (
            lifecycle_identity(lifecycle_definition_value.metadata.template_id) == lifecycle_definition_value.identity
        )
        assert all(
            member.parent_id == lifecycle_definition_value.identity.id
            for member in lifecycle_definition_value.variant_identities
        )
        for variant in lifecycle_definition_value.variant_identities:
            assert (
                lifecycle_variant_identity(
                    lifecycle_definition_value.metadata.template_id,
                    variant.registration_id,
                )
                == variant
            )
