# ABOUTME: Integration-tests strict loading of the wastewater pump-station reference package.
# ABOUTME: Covers exact inventory, schema, identity, rights, visibility, and content drift.

from __future__ import annotations

import json
import shutil
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    EXPECTED_MANIFEST_CONTENT_ID,
    EXPECTED_PACKAGE_CONTENT_ID,
    REFERENCE_PACKAGE_FILE_NAMES,
    ReferencePackageError,
    bundled_reference_package_root,
    load_reference_package,
)

Mutation = Callable[[dict[str, Any]], None]


def _package_copy(tmp_path: Path) -> Path:
    return Path(
        shutil.copytree(
            bundled_reference_package_root(),
            tmp_path / "reference-package",
        )
    )


def _rewrite(path: Path, mutate: Mutation) -> None:
    value = cast(dict[str, Any], json.loads(path.read_bytes()))
    mutate(value)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _add_unknown_field(value: dict[str, Any]) -> None:
    value["unknown"] = "blocked"


def _change_version(value: dict[str, Any]) -> None:
    cast(dict[str, Any], value["versions"])["package"] = "unsupported"


def _change_rights(value: dict[str, Any]) -> None:
    cast(list[dict[str, Any]], value["fields"])[0]["rights_decision_id"] = "denied"


def _change_visibility(value: dict[str, Any]) -> None:
    package = cast(dict[str, Any], value["package"])
    cast(list[dict[str, Any]], package["payloads"])[0]["visibility_class"] = "public"


def _change_member_identity(value: dict[str, Any]) -> None:
    value["member_content_id"] = "0" * 64


def test_bundled_reference_package_loads_exact_certified_identity() -> None:
    package = load_reference_package()

    assert package.profile_id == "AU-NSW-LH-SYN-SPS-v1"
    assert package.generation_id == "738bc2b31f40ae7ea7831a54826c10c7e1f8084e64a6c0e0883bc6290aa84c8e"
    assert package.package_content_id == EXPECTED_PACKAGE_CONTENT_ID
    assert package.manifest_content_id == EXPECTED_MANIFEST_CONTENT_ID
    assert set(path.name for path in bundled_reference_package_root().iterdir()) == set(REFERENCE_PACKAGE_FILE_NAMES)


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        ("missing", "package-inventory"),
        ("additional", "package-inventory"),
        ("symlink", "unsafe-package-entry"),
    ],
)
def test_reader_rejects_package_inventory_drift(
    tmp_path: Path,
    change: str,
    expected_code: str,
) -> None:
    package_root = _package_copy(tmp_path)
    target = package_root / "public-profile.json"
    if change == "missing":
        target.unlink()
    elif change == "additional":
        (package_root / "extra.json").write_text("{}\n", encoding="utf-8")
    else:
        target.unlink()
        target.symlink_to(bundled_reference_package_root() / "public-profile.json")

    with pytest.raises(ReferencePackageError) as raised:
        load_reference_package(package_root)

    assert raised.value.code == expected_code


@pytest.mark.parametrize(
    ("file_name", "mutate", "expected_code"),
    [
        ("public-profile.json", _add_unknown_field, "payload-shape"),
        ("promotion-manifest.json", _change_version, "version-drift"),
        ("promotion-manifest.json", _change_rights, "rights-policy"),
        ("promotion-manifest.json", _change_visibility, "visibility-policy"),
        ("physical-member.json", _change_member_identity, "identity-link"),
    ],
)
def test_reader_rejects_semantic_or_identity_drift(
    tmp_path: Path,
    file_name: str,
    mutate: Mutation,
    expected_code: str,
) -> None:
    package_root = _package_copy(tmp_path)
    _rewrite(package_root / file_name, mutate)

    with pytest.raises(ReferencePackageError) as raised:
        load_reference_package(package_root)

    assert raised.value.code == expected_code


def test_reader_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    package_root = _package_copy(tmp_path)
    profile_path = package_root / "public-profile.json"
    raw = profile_path.read_bytes()
    profile_path.write_bytes(b'{"profile_id":"duplicate",' + raw[1:])

    with pytest.raises(ReferencePackageError) as raised:
        load_reference_package(package_root)

    assert raised.value.code == "duplicate-json-key"
