# ABOUTME: Generates the canonical ASW-8 three-pump station-data candidate from certified v1 bytes.
# ABOUTME: Writes only to a caller-selected candidate directory and never promotes production data.

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v2"
SOURCE_PACKAGE_ID = "642da8bdfad63d7324e0c5886f1f8f3866c9a6bd25f165fa2a5937d68e8a5e16"
SOURCE_MEMBER_ID = "55c1c11746ec59bac6632a96de1c2c97eb26b9b6642908ba23c187f0a8509133"
GENERATOR_ID = "pump-station-asw-8-station-data-generator.v1"
CERTIFIER_ID = "pump-station-asw-8-station-data-certifier.v1"
RIGHTS_ID = "repository-original-redistributable"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n").encode()


def _content_id(domain: str, value: object) -> str:
    return hashlib.sha256(domain.encode() + b"\0" + _canonical(value)).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain an object")
    return value


def build_candidate(source_root: Path) -> dict[str, dict[str, Any]]:
    """Build the exact v2 documents from one strict certified-v1 input."""
    source_manifest = _load(source_root / "promotion-manifest.json")
    source_member = _load(source_root / "physical-member.json")
    if source_manifest["package"]["package_content_id"] != SOURCE_PACKAGE_ID:
        raise ValueError("source v1 package content identity differs")
    if source_member["member_content_id"] != SOURCE_MEMBER_ID:
        raise ValueError("source v1 member content identity differs")

    inherited_parameters = [
        deepcopy(row)
        for row in source_member["parameters"]
        if row["identity"] not in {"topology.max_running_pumps", "topology.transfer_limit"}
    ]
    pump_parameter_set = {
        row["identity"]: deepcopy(row["value"])
        for row in inherited_parameters
        if row["identity"].startswith(("pump.", "mechanism."))
    }
    generation_basis = {
        "generator_id": GENERATOR_ID,
        "profile_id": PROFILE_ID,
        "source_v1_member_content_id": SOURCE_MEMBER_ID,
        "source_v1_package_content_id": SOURCE_PACKAGE_ID,
        "topology": {"component_ids": ["pump-a", "pump-b", "pump-c"], "maximum_running_pumps": 2},
    }
    generation_id = _content_id("pump-station-asw-8-generation.v1", generation_basis)
    member_body: dict[str, Any] = {
        "asset": {
            "asset_id": source_member["asset"]["asset_id"],
            "component_ids": ["pump-a", "pump-b", "pump-c"],
            "maximum_running_pumps": 2,
            "ordered_assignment_supported": True,
            "service_capacity_units_per_running_pump": 1,
            "test_running_service_capacity_units": 0,
        },
        "composites": deepcopy(source_member["composites"]),
        "generation_id": generation_id,
        "orderings": deepcopy(source_member["orderings"]),
        "parameters": inherited_parameters,
        "profile_id": PROFILE_ID,
        "pump_local_parameter_sets": {
            pump_id: deepcopy(pump_parameter_set) for pump_id in ("pump-a", "pump-b", "pump-c")
        },
        "rules": [rule for rule in source_member["rules"] if rule not in {"asw-0b4.rule.transfer.v1"}]
        + [
            "pump-station-asw-8.rule.ordered-assignment.v1",
            "pump-station-asw-8.rule.discrete-service-accounting.v1",
            "pump-station-asw-8.rule.test-running-exclusion.v1",
        ],
        "schema_id": "pump-station-physical-member.v2",
        "source_v1_member_content_id": SOURCE_MEMBER_ID,
        "source_v1_package_content_id": SOURCE_PACKAGE_ID,
    }
    member = {**member_body, "member_content_id": _content_id("pump-station-physical-member.v2", member_body)}
    checks_body: dict[str, Any] = {
        "checks": [
            {"check_id": "source-v1-identity", "result": "pass"},
            {"check_id": "three-pump-topology", "result": "pass"},
            {"check_id": "pump-local-symmetry", "result": "pass"},
            {"check_id": "inherited-constant-equality", "result": "pass"},
            {"check_id": "discrete-service-accounting", "result": "pass"},
            {"check_id": "test-running-service-exclusion", "result": "pass"},
            {"check_id": "synthetic-claim-boundary", "result": "pass"},
        ],
        "generation_id": generation_id,
        "member_content_id": member["member_content_id"],
        "profile_id": PROFILE_ID,
        "schema_id": "pump-station-physical-reference-checks.v2",
        "source_v1_member_content_id": SOURCE_MEMBER_ID,
        "source_v1_package_content_id": SOURCE_PACKAGE_ID,
    }
    certification_receipt_id = _content_id("pump-station-asw-8-certification.v1", checks_body)
    checks = {**checks_body, "certification_receipt_id": certification_receipt_id}
    profile: dict[str, Any] = {
        "asset": deepcopy(member["asset"]),
        "claim_ceiling": "construct-valid-synthetic-benchmark",
        "context": {
            "country": "Australia",
            "fictional": True,
            "region": "Lower Hunter",
            "state": "New South Wales",
        },
        "generation_id": generation_id,
        "license": {"identifier": "MIT", "notice": "Copyright (c) 2026 AEC-Bench contributors"},
        "permitted_claim_ids": [
            "SYNTHETIC-THREE-PUMP-TOPOLOGY",
            "DISCRETE-SCU-SERVICE-ACCOUNTING",
            "PUMP-LOCAL-PHYSICS-ONLY",
        ],
        "profile_id": PROFILE_ID,
        "prohibited_claim_ids": [
            "REAL-STATION",
            "NETWORK-REPRESENTATION",
            "OPERATIONAL-ADVICE",
            "PARALLEL-PUMP-HYDRAULICS",
        ],
        "schema_id": "pump-station-public-profile.v2",
        "source_v1_package_content_id": SOURCE_PACKAGE_ID,
    }
    payload_values = {
        "physical-member": member,
        "physical-reference-checks": checks,
        "public-profile": profile,
    }
    role_values = {
        "physical-member": ("physical-member.json", "pump-station-physical-member.v2", "host-private"),
        "physical-reference-checks": (
            "physical-reference-checks.json",
            "pump-station-physical-reference-checks.v2",
            "host-private",
        ),
        "public-profile": ("public-profile.json", "pump-station-public-profile.v2", "public"),
    }
    payloads: list[dict[str, Any]] = []
    for role, value in payload_values.items():
        relative_path, schema_id, visibility = role_values[role]
        raw = _canonical(value)
        payloads.append(
            {
                "media_type": "application/json",
                "payload_content_id": hashlib.sha256(
                    b"pump-station-asw-8-promoted-payload.v1\0" + role.encode() + b"\0" + raw
                ).hexdigest(),
                "relative_path": relative_path,
                "schema_id": schema_id,
                "semantic_role": role,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size_bytes": len(raw),
                "visibility": visibility,
            }
        )
    package_content_id = _content_id("pump-station-asw-8-promoted-package.v1", payloads)
    manifest: dict[str, Any] = {
        "certification_receipt_id": certification_receipt_id,
        "claims": {
            "permitted": deepcopy(profile["permitted_claim_ids"]),
            "prohibited": deepcopy(profile["prohibited_claim_ids"]),
        },
        "compatibility": {
            "migration": "none",
            "predecessor_profile": "AU-NSW-LH-SYN-SPS-v1",
            "unknown_fields": "reject",
            "unknown_files": "reject",
        },
        "generation_id": generation_id,
        "generator_id": GENERATOR_ID,
        "independent_certifier_id": CERTIFIER_ID,
        "member_content_id": member["member_content_id"],
        "package_content_id": package_content_id,
        "package_schema_id": "pump-station-reference-package.v2",
        "payloads": payloads,
        "profile_id": PROFILE_ID,
        "rights_decision_id": RIGHTS_ID,
        "schema_id": "pump-station-promotion-manifest.v2",
        "source_v1_member_content_id": SOURCE_MEMBER_ID,
        "source_v1_package_content_id": SOURCE_PACKAGE_ID,
    }
    return {
        "physical-member.json": member,
        "physical-reference-checks.json": checks,
        "promotion-manifest.json": manifest,
        "public-profile.json": profile,
    }


def write_candidate(source_root: Path, output_root: Path) -> None:
    """Write generated candidate bytes to an empty directory."""
    output_root.mkdir(parents=True, exist_ok=False)
    for name, value in build_candidate(source_root).items():
        (output_root / name).write_bytes(_canonical(value))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    write_candidate(args.source_root, args.output_root)


if __name__ == "__main__":
    main()
