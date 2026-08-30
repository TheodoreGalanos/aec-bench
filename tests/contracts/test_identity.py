# ABOUTME: Tests shared UUIDv7 identity and portable path value contracts.
# ABOUTME: Covers malformed values, display references, and symlink containment.

from pathlib import Path
from uuid import RFC_4122, UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from aec_bench.contracts.identity import (
    EntityIdentity,
    EntityKey,
    EntityKind,
    PortableRelativePath,
    _build_uuidv7,
    format_display_ref,
    new_entity_id,
    resolve_below,
    validate_portable_relative_path,
    validate_uuidv7,
)


def test_new_entity_id_creates_uuidv7() -> None:
    entity_id = new_entity_id(EntityKind.TASK)

    assert isinstance(entity_id, UUID)
    assert validate_uuidv7(entity_id) == entity_id
    assert entity_id.version == 7
    assert entity_id.variant == RFC_4122


@pytest.mark.parametrize(
    "value",
    [
        "not-a-uuid",
        "550e8400-e29b-41d4-a716-446655440000",
    ],
)
def test_validate_uuidv7_rejects_invalid_versions(value: str) -> None:
    with pytest.raises(ValueError, match="entity ID"):
        validate_uuidv7(value)


def test_uuidv7_layout_encodes_epoch_milliseconds_and_random_fields() -> None:
    timestamp_ms = 1_706_000_123_456
    random_a = 0xABC
    random_b = 0x1234_5678_9ABC_DEF

    entity_id = _build_uuidv7(timestamp_ms, random_a, random_b)

    expected_int = (timestamp_ms << 80) | (7 << 76) | (random_a << 64) | (0b10 << 62) | random_b
    assert entity_id == UUID(int=expected_int)
    assert entity_id.int >> 80 == timestamp_ms


def test_new_entity_id_accepts_string_kind_and_rejects_unknown_kind() -> None:
    assert new_entity_id("run").version == 7

    with pytest.raises(ValueError, match="unsupported entity kind"):
        new_entity_id("unknown")


def test_entity_identity_validates_key_and_positive_version() -> None:
    identity = EntityIdentity(id=new_entity_id("task"), key=EntityKey("civil/drainage/pipe-sizing"), version=3)

    assert isinstance(identity.key, EntityKey)
    assert format_display_ref(identity.key, identity.id) == "civil/drainage/pipe-sizing · " + identity.id.hex[-8:]

    for invalid_version in (0, -1, True, 1.0, "1"):
        with pytest.raises(ValidationError):
            EntityIdentity.model_validate(
                {
                    "id": identity.id,
                    "key": "civil/drainage/pipe-sizing",
                    "version": invalid_version,
                }
            )


@pytest.mark.parametrize(
    "key",
    [
        "",
        " ",
        "/leading",
        "trailing/",
        "repeated//separator",
        ".",
        "a/.",
        "a/..",
        "a\\b",
        "a\x00b",
        "Éngineering/task",
        "UPPER/task",
        "a b/task",
    ],
)
def test_entity_key_rejects_unsafe_values(key: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        EntityKey(key)


@pytest.mark.parametrize(
    "path",
    [
        "",
        "/absolute/path",
        "C:/Windows/path",
        "C:relative-drive-path",
        "//server/share",
        "a\\b",
        "a\x00b",
        "a/../outside",
        "a/./inside",
        "a//b",
        "a/",
        "CON/file.txt",
        "report:name.txt",
    ],
)
def test_portable_relative_path_rejects_unsafe_values(path: str) -> None:
    with pytest.raises((TypeError, ValueError)):
        PortableRelativePath(path)


def test_portable_relative_path_allows_unicode_and_exposes_components() -> None:
    path = PortableRelativePath("données/rapport-01.txt")

    assert path.parts == ("données", "rapport-01.txt")
    assert validate_portable_relative_path(path) == path


@given(
    st.text(
        alphabet=st.characters(whitelist_categories=("L", "M", "N")),
        min_size=1,
        max_size=40,
    )
)
def test_portable_relative_path_accepts_unicode_components(component: str) -> None:
    path = PortableRelativePath(f"engineering-{component}/report")

    assert path.parts == (f"engineering-{component}", "report")


@given(st.lists(st.sampled_from((".", "..")), min_size=1, max_size=4))
def test_portable_relative_path_rejects_traversal_components(components: list[str]) -> None:
    with pytest.raises(ValueError):
        PortableRelativePath("/".join(("workspace", *components, "output")))


@given(st.integers(min_value=2, max_value=512))
def test_portable_relative_path_rejects_repeated_separators(component_count: int) -> None:
    path = "segment" + ("/segment" * component_count) + "//output"

    with pytest.raises(ValueError):
        PortableRelativePath(path)


@given(
    st.sampled_from(("C:", "D:", "Z:")),
    st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=24),
)
def test_portable_relative_path_rejects_windows_drive_forms(drive: str, component: str) -> None:
    with pytest.raises(ValueError):
        PortableRelativePath(f"{drive}/{component}")


@given(st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=24))
def test_portable_relative_path_rejects_backslash_forms(component: str) -> None:
    with pytest.raises(ValueError):
        PortableRelativePath(f"workspace\\{component}")


@given(st.text(alphabet=st.characters(whitelist_categories=("Ll", "Nd")), max_size=24))
def test_portable_relative_path_rejects_null_bytes(component: str) -> None:
    with pytest.raises(ValueError):
        PortableRelativePath(f"workspace/{component}\x00/output")


@given(st.integers(min_value=1, max_value=255))
def test_portable_relative_path_allows_components_up_to_255_utf8_bytes(component_length: int) -> None:
    component = "x" * component_length

    assert PortableRelativePath(component).parts == (component,)


@given(st.integers(min_value=256, max_value=2_048))
def test_portable_relative_path_rejects_ascii_components_over_255_bytes(component_length: int) -> None:
    with pytest.raises(ValueError, match="255 UTF-8 bytes"):
        PortableRelativePath("x" * component_length)


@given(st.integers(min_value=128, max_value=1_024))
def test_portable_relative_path_rejects_multibyte_components_over_255_bytes(component_length: int) -> None:
    with pytest.raises(ValueError, match="255 UTF-8 bytes"):
        PortableRelativePath("é" * component_length)


def test_resolve_below_returns_descendant(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()

    assert resolve_below(root, PortableRelativePath("aec-bench/output.json")) == root / "aec-bench/output.json"


def test_resolve_below_keeps_encoded_traversal_literal(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    relative = PortableRelativePath("workspace/%2e%2e/out.json")

    assert resolve_below(root, relative) == root / "workspace/%2e%2e/out.json"


def test_resolve_below_rejects_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "root"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    (root / "linked").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError, match="escapes"):
        resolve_below(root, PortableRelativePath("linked/secret.txt"))


def test_resolve_below_accepts_symlink_that_stays_inside(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = root / "real"
    target.mkdir()
    (root / "linked").symlink_to(target, target_is_directory=True)

    assert resolve_below(root, PortableRelativePath("linked/file.txt")) == target / "file.txt"
