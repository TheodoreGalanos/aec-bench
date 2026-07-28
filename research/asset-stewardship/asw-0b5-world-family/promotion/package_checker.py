# ABOUTME: Independently checks the four-file certified reference package using only Python's standard library.
# ABOUTME: Recomputes canonical bytes, identities, field ownership, visibility, and compact reference shape.

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NoReturn, cast

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v1"
PAYLOAD_DOMAIN = b"asw-0b5.promoted-payload.v1\0"
PACKAGE_DOMAIN = b"asw-0b5.promoted-package.v1\0"
MANIFEST_DOMAIN = b"asw-0b5.promotion-manifest.v1\0"
FIELD_DOMAIN = b"asw-0b5.promoted-field.v1\0"
RESULT_DOMAIN = b"asw-0b5.package-conformance-result.v1\0"
SAFE_PATH = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
EXPECTED_FILES = {
    "physical-member.json",
    "physical-reference-checks.json",
    "promotion-manifest.json",
    "public-profile.json",
}
ROLE_PATHS = {
    "physical-member": "physical-member.json",
    "physical-reference-checks": "physical-reference-checks.json",
    "public-profile": "public-profile.json",
}
ROLE_VISIBILITY = {
    "physical-member": "host-private",
    "physical-reference-checks": "host-private",
    "public-profile": "public",
}
ROLE_SCHEMAS = {
    "physical-member": "asw-0b5.physical-member.v1",
    "physical-reference-checks": (
        "asw-0b5.physical-reference-checks.v1"
    ),
    "public-profile": "asw-0b5.public-profile.v1",
}


class PackageConformanceError(ValueError):
    """Raised when an exact package rule fails."""


def _fail(detail: str) -> NoReturn:
    raise PackageConformanceError(
        f"package-conformance: {detail}"
    )


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            _fail(f"duplicate key {key!r}")
        value[key] = child
    return value


def _canonical(value: object) -> bytes:
    def check(child: object) -> None:
        if child is None or isinstance(child, float):
            _fail("null and floating-point JSON values are forbidden")
        if isinstance(child, dict):
            for key, nested in child.items():
                if not isinstance(key, str):
                    _fail("object key is not text")
                check(nested)
        elif isinstance(child, list):
            for nested in child:
                check(nested)
        elif not isinstance(child, str | int | bool):
            _fail("unsupported JSON value")

    check(value)
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode()


def _read_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    if (
        not raw.endswith(b"\n")
        or raw.endswith(b"\n\n")
        or b"\r" in raw
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        _fail(f"{path.name} has non-canonical line bytes")
    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(f"{path.name}: {error}")
    if not isinstance(parsed, dict):
        _fail(f"{path.name} is not an object")
    value = cast(dict[str, Any], parsed)
    if _canonical(value) != raw:
        _fail(f"{path.name} is not canonical")
    return value, raw


def _safe_root(root: Path) -> None:
    if not root.is_dir() or root.is_symlink():
        _fail("package root is not a plain directory")
    names: set[str] = set()
    for path in root.iterdir():
        mode = path.lstat().st_mode
        if (
            path.name in names
            or SAFE_PATH.fullmatch(path.name) is None
            or not stat.S_ISREG(mode)
            or path.is_symlink()
        ):
            _fail("package contains an unsafe entry")
        names.add(path.name)
    if names != EXPECTED_FILES:
        _fail("root inventory differs")


def _payload_id(role: str, raw: bytes) -> str:
    return hashlib.sha256(
        PAYLOAD_DOMAIN
        + role.encode("ascii")
        + b"\0"
        + raw
    ).hexdigest()


def _escape_pointer(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _leaves(
    value: object,
    pointer: str = "",
) -> list[str]:
    if isinstance(value, dict):
        return [
            nested
            for key, child in value.items()
            for nested in _leaves(
                child,
                pointer + "/" + _escape_pointer(key),
            )
        ]
    if isinstance(value, list):
        return [
            nested
            for index, child in enumerate(value)
            for nested in _leaves(child, pointer + f"/{index}")
        ]
    return [pointer]


def _field_id(role: str, pointer: str) -> str:
    return hashlib.sha256(
        FIELD_DOMAIN
        + role.encode("ascii")
        + b"\0"
        + pointer.encode("utf-8")
    ).hexdigest()


def _check_manifest_shape(manifest: dict[str, Any]) -> None:
    if set(manifest) != {
        "authority",
        "claims",
        "compatibility",
        "evidence",
        "fields",
        "generation",
        "package",
        "retirement",
        "versions",
        "visibility",
    }:
        _fail("manifest top-level shape differs")
    if (
        manifest["authority"].get("profile_id") != PROFILE_ID
        or manifest["package"].get("root_file_count") != 4
        or manifest["package"].get("external_dependencies") != []
        or manifest["generation"].get("v0") != "pass"
        or manifest["generation"].get("v1") != "pass"
        or manifest["generation"].get("v2") != "pass"
        or manifest["generation"].get("v3") != "pass"
        or manifest["generation"].get("v4") != "unclaimed"
        or manifest["compatibility"].get("unknown_fields")
        != "reject"
        or manifest["compatibility"].get("unknown_files")
        != "reject"
    ):
        _fail("manifest authority or maturity differs")


def _check_payload_shapes(
    payloads: dict[str, dict[str, Any]],
) -> None:
    common = {
        "physical-member": {
            "asset",
            "composites",
            "member_content_id",
            "orderings",
            "parameters",
            "profile_id",
            "rules",
            "schema_id",
        },
        "physical-reference-checks": {
            "checks",
            "generation_id",
            "member_content_id",
            "profile_id",
            "schema_id",
        },
        "public-profile": {
            "asset",
            "claim_ceiling",
            "context",
            "generation_id",
            "license",
            "manifest_specification_id",
            "permitted_claim_ids",
            "profile_id",
            "prohibited_claim_ids",
            "schema_id",
        },
    }
    for role, value in payloads.items():
        if (
            set(value) != common[role]
            or value["profile_id"] != PROFILE_ID
            or value["schema_id"] != ROLE_SCHEMAS[role]
        ):
            _fail(f"{role} payload shape differs")
    profile = payloads["public-profile"]
    member = payloads["physical-member"]
    references = payloads["physical-reference-checks"]
    if (
        profile["asset"] != member["asset"]
        or profile["generation_id"] != references["generation_id"]
        or member["member_content_id"]
        != references["member_content_id"]
        or profile["context"].get("fictional") is not True
        or profile["claim_ceiling"]
        != "construct-valid-synthetic-benchmark"
        or profile["license"].get("identifier") != "MIT"
    ):
        _fail("payload cross-link differs")


def _check_references(value: dict[str, Any]) -> int:
    checks = value.get("checks")
    expected_roles = {
        "ambiguity",
        "boundary",
        "clean",
        "degraded",
        "intervention",
        "label-symmetry",
        "no-maintenance",
        "transfer",
        "zero-flow",
    }
    if (
        not isinstance(checks, list)
        or len(checks) != len(expected_roles)
        or {check.get("role") for check in checks} != expected_roles
    ):
        _fail("compact reference inventory differs")
    for check in checks:
        expected = check.get("expected")
        if (
            not isinstance(expected, dict)
            or expected.get("classification") != "pass"
            or not isinstance(expected.get("unit"), str)
            or not expected["unit"]
            or not isinstance(expected.get("finite_scalar"), str)
        ):
            _fail("compact reference result differs")
        try:
            scalar = Decimal(expected["finite_scalar"])
        except InvalidOperation as error:
            _fail(f"compact reference scalar differs: {error}")
        if not math.isfinite(float(scalar)):
            _fail("compact reference scalar is not finite")
        if (
            not isinstance(check.get("input_state_ids"), list)
            or not check["input_state_ids"]
            or any(
                not isinstance(identity, str)
                or SHA256.fullmatch(identity) is None
                for identity in check["input_state_ids"]
            )
            or not isinstance(check.get("rule_ids"), list)
            or not check["rule_ids"]
            or SHA256.fullmatch(
                str(check.get("w3_result_content_id"))
            )
            is None
            or SHA256.fullmatch(
                str(check.get("w4_result_content_id"))
            )
            is None
        ):
            _fail("compact reference authority differs")
    return len(checks)


def _check_fields(
    manifest: dict[str, Any],
    payloads: dict[str, dict[str, Any]],
) -> None:
    rows = manifest.get("fields")
    if not isinstance(rows, list):
        _fail("field register is absent")
    expected = {
        (role, pointer): _field_id(role, pointer)
        for role, payload in payloads.items()
        for pointer in _leaves(payload)
    }
    actual: dict[tuple[str, str], str] = {}
    for row in rows:
        if not isinstance(row, dict) or set(row) != {
            "assumption_link_set_id",
            "certification_link_set_id",
            "claim_id",
            "evidence_link_set_id",
            "field_semantic_id",
            "generation_link_set_id",
            "json_pointer",
            "later_consumer",
            "quantity",
            "rights_decision_id",
            "semantic_role",
            "sensitivity_link_set_id",
            "source_link_set_id",
            "transformation_link_set_id",
            "visibility_class",
        }:
            _fail("field row shape differs")
        key = (
            str(row["semantic_role"]),
            str(row["json_pointer"]),
        )
        if key in actual:
            _fail("field ownership is duplicated")
        actual[key] = str(row["field_semantic_id"])
        if (
            row["visibility_class"]
            != ROLE_VISIBILITY.get(key[0])
            or row["rights_decision_id"]
            != "repository-original-redistributable"
            or row["later_consumer"] not in {"ASW-2A0", "ASW-2A1"}
        ):
            _fail("field authority differs")
    if actual != expected:
        _fail("field ownership is incomplete or changed")


def check_package(root: Path) -> dict[str, Any]:
    """Check one package without any research, generator, or solver import."""
    root = root.resolve()
    _safe_root(root)
    manifest, manifest_raw = _read_json(
        root / "promotion-manifest.json"
    )
    _check_manifest_shape(manifest)
    payloads: dict[str, dict[str, Any]] = {}
    payload_raw: dict[str, bytes] = {}
    for role, name in ROLE_PATHS.items():
        payload, raw = _read_json(root / name)
        payloads[role] = payload
        payload_raw[role] = raw
    _check_payload_shapes(payloads)
    compact_count = _check_references(
        payloads["physical-reference-checks"]
    )
    inventory = manifest["package"].get("payloads")
    if (
        not isinstance(inventory, list)
        or [row.get("relative_path") for row in inventory]
        != sorted(ROLE_PATHS.values())
    ):
        _fail("payload inventory differs")
    for row in inventory:
        role = row.get("semantic_role")
        if (
            role not in ROLE_PATHS
            or row.get("relative_path") != ROLE_PATHS[role]
            or row.get("media_type") != "application/json"
            or row.get("schema_identity") != ROLE_SCHEMAS[role]
            or row.get("visibility_class") != ROLE_VISIBILITY[role]
        ):
            _fail("payload inventory authority differs")
        raw = payload_raw[role]
        if (
            row.get("payload_content_id") != _payload_id(role, raw)
            or row.get("sha256") != hashlib.sha256(raw).hexdigest()
            or row.get("size_bytes") != len(raw)
        ):
            _fail("payload inventory identity differs")
    package_id = hashlib.sha256(
        PACKAGE_DOMAIN + _canonical(inventory)
    ).hexdigest()
    if manifest["package"].get("package_content_id") != package_id:
        _fail("package identity differs")
    _check_fields(manifest, payloads)
    field_ids = {
        role: [
            row["field_semantic_id"]
            for row in manifest["fields"]
            if row["semantic_role"] == role
        ]
        for role in ROLE_PATHS
    }
    for row in inventory:
        if row.get("field_semantic_ids") != field_ids[
            row["semantic_role"]
        ]:
            _fail("payload field inventory differs")
    manifest_id = hashlib.sha256(
        MANIFEST_DOMAIN + manifest_raw
    ).hexdigest()
    result = {
        "compact_reference_count": compact_count,
        "first_failure": "none",
        "manifest_content_id": manifest_id,
        "package_content_id": package_id,
        "profile_id": PROFILE_ID,
        "promotable": False,
        "schema_id": "asw-0b5.package-conformance-result.v1",
        "terminal_state": "package-conformance-pass",
    }
    result["result_content_id"] = hashlib.sha256(
        RESULT_DOMAIN + _canonical(result)
    ).hexdigest()
    return result


def main(arguments: list[str] | None = None) -> int:
    """Run the package-only checker and print one canonical result."""
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    parsed = parser.parse_args(arguments)
    try:
        result = check_package(parsed.package_root)
    except PackageConformanceError as error:
        sys.stderr.write(f"{error}\n")
        return 1
    sys.stdout.buffer.write(_canonical(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
