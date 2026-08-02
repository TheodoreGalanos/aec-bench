# ABOUTME: Strictly validates the promoted ASW-8 three-pump station-data package.
# ABOUTME: Keeps v2 identities and checks separate from the byte-stable v1 reader path.

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_models import (
    MutableJsonObject,
    ReferencePackage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.reference_package_reader import (
    REFERENCE_PACKAGE_FILE_NAMES,
    REFERENCE_PROFILE_V2,
    _canonical_json,
    _fail,
    _read_object,
    _safe_package_files,
)

EXPECTED_V2_PACKAGE_CONTENT_ID = "79eac8f916a15fe7463eba5faf44edeb8776ce79dc3fe7bd8b2cb1574988b1c1"
EXPECTED_V2_MANIFEST_CONTENT_ID = "c1b6d6e5e4cfc8aeb43178aeceb8ab767e34c1a287b78d1f72adac0800787828"
EXPECTED_V2_GENERATION_ID = "afac5355a2866f20215846ea0140f08f6581a80312b72c464329ba7b6e7dc840"
EXPECTED_V2_MEMBER_CONTENT_ID = "e3ef3a2f391635d0f97710b6d988acdf05ece22503c0e82d83afc8522f7d9a94"
SOURCE_V1_PACKAGE_CONTENT_ID = "642da8bdfad63d7324e0c5886f1f8f3866c9a6bd25f165fa2a5937d68e8a5e16"
SOURCE_V1_MEMBER_CONTENT_ID = "55c1c11746ec59bac6632a96de1c2c97eb26b9b6642908ba23c187f0a8509133"
_EXPECTED_FILES = {
    "physical-member.json": (5642, "a9e6d000fd7631a84b6ee512550145ccc578652dec87d2b743cd12ed6a937e34"),
    "physical-reference-checks.json": (
        952,
        "61653f866c438acfb813a83c63e5296e6085d4e5dfd2745b07c43b1c5e197c07",
    ),
    "promotion-manifest.json": (2359, "6952a4d051c584c44f132d31cb8f65b0a46430f1b1ad6a806d8b25aeecde7b10"),
    "public-profile.json": (980, "fdc81a1f7ccc9a3f0778c954a1a446255364964b150a8e4c50a9ba3977a7c9f6"),
}
_SCHEMAS = {
    "physical-member.json": "pump-station-physical-member.v2",
    "physical-reference-checks.json": "pump-station-physical-reference-checks.v2",
    "promotion-manifest.json": "pump-station-promotion-manifest.v2",
    "public-profile.json": "pump-station-public-profile.v2",
}


def _mapping(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("payload-shape", f"{label} is not an object")
    return cast(dict[str, Any], value)


def _validate_exact_files(raw_files: dict[str, bytes]) -> None:
    for name, raw in raw_files.items():
        expected_size, expected_hash = _EXPECTED_FILES[name]
        if len(raw) != expected_size or hashlib.sha256(raw).hexdigest() != expected_hash:
            _fail("file-content-drift", name)


def _validate_semantics(documents: dict[str, MutableJsonObject], raw_files: dict[str, bytes]) -> None:
    for name, document in documents.items():
        if document.get("schema_id") != _SCHEMAS[name] or document.get("profile_id") != REFERENCE_PROFILE_V2:
            _fail("payload-schema", name)
        if document.get("source_v1_package_content_id") != SOURCE_V1_PACKAGE_CONTENT_ID:
            _fail("identity-link", f"{name} source package")
    member = documents["physical-member.json"]
    checks = documents["physical-reference-checks.json"]
    profile = documents["public-profile.json"]
    manifest = documents["promotion-manifest.json"]
    if set(member) != {
        "asset",
        "composites",
        "generation_id",
        "member_content_id",
        "orderings",
        "parameters",
        "profile_id",
        "pump_local_parameter_sets",
        "rules",
        "schema_id",
        "source_v1_member_content_id",
        "source_v1_package_content_id",
    }:
        _fail("payload-shape", "physical-member fields differ")
    asset = _mapping(member["asset"], "asset")
    if asset != {
        "asset_id": "synthetic-wastewater-pump-station",
        "component_ids": ["pump-a", "pump-b", "pump-c"],
        "maximum_running_pumps": 2,
        "ordered_assignment_supported": True,
        "service_capacity_units_per_running_pump": 1,
        "test_running_service_capacity_units": 0,
    }:
        _fail("topology", "three-pump service topology differs")
    pump_sets = _mapping(member["pump_local_parameter_sets"], "pump parameter sets")
    if set(pump_sets) != {"pump-a", "pump-b", "pump-c"}:
        _fail("topology", "pump parameter inventory differs")
    if len({_canonical_json(value) for value in pump_sets.values()}) != 1:
        _fail("pump-symmetry", "pump-local values differ")
    if (
        member.get("member_content_id") != EXPECTED_V2_MEMBER_CONTENT_ID
        or checks.get("member_content_id") != EXPECTED_V2_MEMBER_CONTENT_ID
        or manifest.get("member_content_id") != EXPECTED_V2_MEMBER_CONTENT_ID
    ):
        _fail("identity-link", "member identity differs")
    if {
        member.get("generation_id"),
        checks.get("generation_id"),
        profile.get("generation_id"),
        manifest.get("generation_id"),
    } != {EXPECTED_V2_GENERATION_ID}:
        _fail("identity-link", "generation identity differs")
    if (
        manifest.get("package_schema_id") != "pump-station-reference-package.v2"
        or manifest.get("package_content_id") != EXPECTED_V2_PACKAGE_CONTENT_ID
    ):
        _fail("package-identity", "package identity differs")
    payloads = manifest.get("payloads")
    if not isinstance(payloads, list) or len(payloads) != 3:
        _fail("manifest-package", "payload inventory differs")
    for row in payloads:
        row_value = _mapping(row, "payload")
        path = row_value.get("relative_path")
        if not isinstance(path, str) or path not in raw_files or path == "promotion-manifest.json":
            _fail("manifest-package", "payload path differs")
        raw = raw_files[path]
        if row_value.get("size_bytes") != len(raw) or row_value.get("sha256") != hashlib.sha256(raw).hexdigest():
            _fail("payload-identity", path)


def load_v2_reference_package(root: Path) -> ReferencePackage:
    """Load the exact independently promoted v2 station-data package."""
    files = _safe_package_files(root)
    documents: dict[str, MutableJsonObject] = {}
    raw_files: dict[str, bytes] = {}
    for name in REFERENCE_PACKAGE_FILE_NAMES:
        documents[name], raw_files[name] = _read_object(files[name])
    _validate_exact_files(raw_files)
    _validate_semantics(documents, raw_files)
    return ReferencePackage.from_documents(
        profile_id=REFERENCE_PROFILE_V2,
        generation_id=EXPECTED_V2_GENERATION_ID,
        package_content_id=EXPECTED_V2_PACKAGE_CONTENT_ID,
        manifest_content_id=EXPECTED_V2_MANIFEST_CONTENT_ID,
        manifest=documents["promotion-manifest.json"],
        physical_member=documents["physical-member.json"],
        physical_reference_checks=documents["physical-reference-checks.json"],
        public_profile=documents["public-profile.json"],
    )
