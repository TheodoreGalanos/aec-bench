# ABOUTME: Independently certifies an ASW-8 v2 station-data candidate without importing its generator.
# ABOUTME: Rejects identity, topology, symmetry, inherited-value, claim, and canonical-byte drift.

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, NoReturn

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v2"
SOURCE_PACKAGE_ID = "642da8bdfad63d7324e0c5886f1f8f3866c9a6bd25f165fa2a5937d68e8a5e16"
SOURCE_MEMBER_ID = "55c1c11746ec59bac6632a96de1c2c97eb26b9b6642908ba23c187f0a8509133"
FILES = {
    "physical-member.json",
    "physical-reference-checks.json",
    "promotion-manifest.json",
    "public-profile.json",
}


class CertificationError(ValueError):
    """Raised when a v2 station-data candidate does not satisfy its contract."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise CertificationError(code, detail)


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _content_id(domain: str, value: object) -> str:
    return hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()


def _load(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    value = json.loads(raw)
    if not isinstance(value, dict) or _canonical(value) != raw:
        _fail("canonical-json", path.name)
    return value, raw


def certify(candidate_root: Path, source_root: Path) -> dict[str, str]:
    """Return independently recomputed candidate identities or fail closed."""
    if {path.name for path in candidate_root.iterdir()} != FILES:
        _fail("package-inventory", "candidate file set differs")
    documents: dict[str, dict[str, Any]] = {}
    raw_files: dict[str, bytes] = {}
    for name in FILES:
        documents[name], raw_files[name] = _load(candidate_root / name)
    source_manifest, _ = _load(source_root / "promotion-manifest.json")
    source_member, _ = _load(source_root / "physical-member.json")
    if source_manifest["package"]["package_content_id"] != SOURCE_PACKAGE_ID:
        _fail("source-identity", "source package differs")
    if source_member["member_content_id"] != SOURCE_MEMBER_ID:
        _fail("source-identity", "source member differs")

    member = documents["physical-member.json"]
    checks = documents["physical-reference-checks.json"]
    profile = documents["public-profile.json"]
    manifest = documents["promotion-manifest.json"]
    schemas = {
        member.get("schema_id"),
        checks.get("schema_id"),
        profile.get("schema_id"),
        manifest.get("schema_id"),
        manifest.get("package_schema_id"),
    }
    if schemas != {
        "pump-station-physical-member.v2",
        "pump-station-physical-reference-checks.v2",
        "pump-station-public-profile.v2",
        "pump-station-promotion-manifest.v2",
        "pump-station-reference-package.v2",
    }:
        _fail("schema-identity", "v2 schema set differs")
    if {value.get("profile_id") for value in documents.values()} != {PROFILE_ID}:
        _fail("profile-identity", "profile differs")
    if any(value.get("source_v1_package_content_id") != SOURCE_PACKAGE_ID for value in documents.values()):
        _fail("source-identity", "source package link differs")

    asset = member.get("asset")
    if not isinstance(asset, dict):
        _fail("topology", "asset is absent")
    if asset.get("component_ids") != ["pump-a", "pump-b", "pump-c"]:
        _fail("topology", "pump identities differ")
    if asset.get("maximum_running_pumps") != 2:
        _fail("topology", "maximum running count differs")
    if asset.get("service_capacity_units_per_running_pump") != 1:
        _fail("service-accounting", "running-pump SCU differs")
    if asset.get("test_running_service_capacity_units") != 0:
        _fail("service-accounting", "test-running pumps must supply zero SCU")
    pump_sets = member.get("pump_local_parameter_sets")
    if not isinstance(pump_sets, dict) or set(pump_sets) != {"pump-a", "pump-b", "pump-c"}:
        _fail("pump-symmetry", "pump parameter inventory differs")
    if len({_canonical(value) for value in pump_sets.values()}) != 1:
        _fail("pump-symmetry", "pump parameter values differ")

    source_parameters = {
        row["identity"]: row
        for row in source_member["parameters"]
        if row["identity"] not in {"topology.max_running_pumps", "topology.transfer_limit"}
    }
    candidate_parameters = {row["identity"]: row for row in member.get("parameters", [])}
    if candidate_parameters != source_parameters:
        _fail("inherited-constant-drift", "v1 physical constants differ")
    if member.get("composites") != source_member.get("composites"):
        _fail("inherited-constant-drift", "v1 composites differ")
    prohibited = set(profile.get("prohibited_claim_ids", []))
    if not {"REAL-STATION", "NETWORK-REPRESENTATION", "OPERATIONAL-ADVICE", "PARALLEL-PUMP-HYDRAULICS"} <= prohibited:
        _fail("claim-boundary", "required prohibited claims are absent")

    member_body = {key: value for key, value in member.items() if key != "member_content_id"}
    member_id = _content_id("pump-station-physical-member.v2", member_body)
    if member.get("member_content_id") != member_id:
        _fail("member-identity", "member content identity differs")
    if checks.get("member_content_id") != member_id or manifest.get("member_content_id") != member_id:
        _fail("identity-link", "member link differs")

    payloads = manifest.get("payloads")
    if not isinstance(payloads, list) or len(payloads) != 3:
        _fail("payload-inventory", "payload set differs")
    roles = ("physical-member", "physical-reference-checks", "public-profile")
    expected_files = ("physical-member.json", "physical-reference-checks.json", "public-profile.json")
    for row, role, name in zip(payloads, roles, expected_files, strict=True):
        raw = raw_files[name]
        if row.get("semantic_role") != role or row.get("relative_path") != name:
            _fail("payload-inventory", name)
        expected_payload_id = hashlib.sha256(
            b"pump-station-asw-8-promoted-payload.v1\0" + role.encode() + b"\0" + raw
        ).hexdigest()
        if (
            row.get("sha256") != hashlib.sha256(raw).hexdigest()
            or row.get("size_bytes") != len(raw)
            or row.get("payload_content_id") != expected_payload_id
        ):
            _fail("payload-identity", name)
    package_id = _content_id("pump-station-asw-8-promoted-package.v1", payloads)
    if manifest.get("package_content_id") != package_id:
        _fail("package-identity", "package content identity differs")
    return {
        "certification_receipt_id": str(manifest["certification_receipt_id"]),
        "generation_id": str(manifest["generation_id"]),
        "manifest_content_id": hashlib.sha256(
            b"pump-station-promotion-manifest.v2\0" + raw_files["promotion-manifest.json"]
        ).hexdigest(),
        "member_content_id": member_id,
        "package_content_id": package_id,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(certify(args.candidate_root, args.source_root), sort_keys=True))


if __name__ == "__main__":
    main()
