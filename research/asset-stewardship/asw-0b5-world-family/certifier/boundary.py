# ABOUTME: Implements an independent certifier-side reader for B5-W0 declarations and content identities.
# ABOUTME: Uses no generator, lineage, SWMM, hydraulic, or production implementation.

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NoReturn, cast

PROFILE = "AU-NSW-LH-SYN-SPS-v1"
REVIEWED_W1_DECLARATION = "4470e8af16bb6238a11045847199ffad95f1a7f57f64e85978a009bdda30ded9"

AUTHORITIES = (
    (
        "profile",
        "1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954",
    ),
    (
        "w1",
        "337aeab9465a8a1801b67c2ab0b408a2a2f07becddffc4a02161b64e6a8630de",
    ),
    (
        "w2",
        "66e96610b19920f93ddfa613a1f42e5d9bec6a4eb704905f82ce7b301961d130",
    ),
    (
        "w3",
        "2b0b13a6f9facaf2f0e18f19a5d41069d8e5708a2df77b6dc6d6ed6c9ec65cde",
    ),
    (
        "w4",
        "56502750816efec73ed821ac00ee5ead4ed76ba05e243992f794005980c19b7f",
    ),
    (
        "w2-w4-repair",
        "862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca",
    ),
    (
        "w5",
        "82adf876f18fe51d9f9cc7dfcb0ef02d15c2500993385fffe56974330cf5f3d3",
    ),
)

AMENDED_AUTHORITIES = AUTHORITIES + (
    (
        "w4-c-r07-amendment",
        "488c82d09696472533669f21017c19cd4156952f4d075b278de91b580bf2cbf2",
    ),
    (
        "w4-c-r08-amendment",
        "047576621781aa294b8251be433b9dba7c2efd66ffe759e633d67f26960d9a65",
    ),
)

W2_CASES = (
    "G00_ZERO_STATIC",
    "G10_CLEAN_A_BASE",
    "G11_CLEAN_B_BASE",
    "G12_CLEAN_ASSESS",
    "G20_OBSTRUCTION_HALF",
    "G21_OBSTRUCTION_TRIGGER",
    "G22_OBSTRUCTION_UPPER",
    "G30_CLEARANCE_HALF",
    "G31_CLEARANCE_UPPER",
    "G40_COMBINED_HALF",
    "G41_COMBINED_UPPER",
    "G50_CLEAR_A_PRE",
    "G51_CLEAR_A_POST",
    "G52_CLEAR_B_PRE",
    "G53_CLEAR_B_POST",
    "G60_REPAIR_PRE",
    "G61_REPAIR_POST",
    "G70_TRANSFER",
    "G80_NO_MAINTENANCE",
)

RECEIPT_PROFILE = (
    "generation-declaration",
    "engine-build",
    "generator-case",
    "certifier-case",
    "w4-case",
    "sensitivity-member",
    "family-decision",
    "gate-decision",
    "rights-review",
    "visibility-review",
    "package-conformance",
    "absence-proof",
    "promotion-decision",
)

SCALAR_ORDER = (
    "fluid.rho",
    "fluid.mu",
    "fluid.g",
    "topology.max_running_pumps",
    "topology.transfer_limit",
    "well.D_w",
    "well.h_stop",
    "well.h_start",
    "well.h_high",
    "well.h_overflow",
    "system.z_d",
    "system.L",
    "system.D",
    "system.epsilon",
    "system.K_minor",
    "system.Re_min",
    "inflow.Q_low",
    "inflow.Q_nominal",
    "inflow.Q_assess",
    "inflow.T_diagnostic",
    "pump.H_0",
    "pump.Q_0",
    "mechanism.a_o",
    "mechanism.b_o",
    "mechanism.a_c",
    "mechanism.b_c",
    "mechanism.r_o_runtime",
    "mechanism.r_o_start",
    "mechanism.r_c_runtime",
    "exposure.calendar_max",
    "exposure.runtime_max",
    "exposure.starts_max",
    "capability.t_draw_limit",
    "observation.level_resolution",
    "observation.level_bias",
    "observation.flow_resolution",
    "observation.flow_bias",
    "observation.runtime_resolution",
    "intervention.e_clear",
    "intervention.o_residual",
    "intervention.e_repair",
    "intervention.c_residual",
    "resource.kit_initial",
    "resource.kit_lead",
    "resource.access_duration",
    "resource.concurrent_limit",
)

UNIT_BY_SCALAR = {
    "fluid.rho": "kg/m³",
    "fluid.mu": "Pa·s",
    "fluid.g": "m/s²",
    "topology.max_running_pumps": "count",
    "topology.transfer_limit": "count",
    "well.D_w": "m",
    "well.h_stop": "m",
    "well.h_start": "m",
    "well.h_high": "m",
    "well.h_overflow": "m",
    "system.z_d": "m",
    "system.L": "m",
    "system.D": "m",
    "system.epsilon": "m",
    "system.K_minor": "1",
    "system.Re_min": "1",
    "inflow.Q_low": "m³/s",
    "inflow.Q_nominal": "m³/s",
    "inflow.Q_assess": "m³/s",
    "inflow.T_diagnostic": "s",
    "pump.H_0": "m",
    "pump.Q_0": "m³/s",
    "mechanism.a_o": "1",
    "mechanism.b_o": "1",
    "mechanism.a_c": "1",
    "mechanism.b_c": "1",
    "mechanism.r_o_runtime": "s^-1",
    "mechanism.r_o_start": "start^-1",
    "mechanism.r_c_runtime": "s^-1",
    "exposure.calendar_max": "s",
    "exposure.runtime_max": "s",
    "exposure.starts_max": "count",
    "capability.t_draw_limit": "s",
    "observation.level_resolution": "m",
    "observation.level_bias": "m",
    "observation.flow_resolution": "m³/s",
    "observation.flow_bias": "1",
    "observation.runtime_resolution": "s",
    "intervention.e_clear": "1",
    "intervention.o_residual": "1",
    "intervention.e_repair": "1",
    "intervention.c_residual": "1",
    "resource.kit_initial": "boolean",
    "resource.kit_lead": "s",
    "resource.access_duration": "s",
    "resource.concurrent_limit": "count",
}

COUNT_SCALARS = frozenset(
    {
        "topology.max_running_pumps",
        "topology.transfer_limit",
        "exposure.starts_max",
        "resource.concurrent_limit",
    }
)
BOOLEAN_SCALARS = frozenset({"resource.kit_initial"})

FIXED_COMPOSITES: list[dict[str, Any]] = [
    {
        "identity": "inflow.base_pattern",
        "kind": "piecewise-constant",
        "members": [
            {
                "end_second": 5400,
                "start_second": 0,
                "value_parameter": "inflow.Q_low",
            },
            {
                "end_second": 10800,
                "start_second": 5400,
                "value_parameter": "inflow.Q_nominal",
            },
            {
                "end_second": 14400,
                "start_second": 10800,
                "value_parameter": "inflow.Q_assess",
            },
            {
                "end_second": 21600,
                "start_second": 14400,
                "value_parameter": "inflow.Q_nominal",
            },
            {
                "end_second": 28800,
                "start_second": 21600,
                "value_parameter": "inflow.Q_low",
            },
        ],
        "unit": "m³/s",
    },
    {
        "identity": "mechanism.severity_domain",
        "kind": "closed-interval",
        "members": ["0", "1"],
        "unit": "1",
    },
    {
        "identity": "observation.inspection_band_edges",
        "kind": "ordered-thresholds",
        "members": ["0.25", "0.60"],
        "unit": "1",
    },
]

RULE_IDENTITIES = [
    "asw-0b4.rule.wet-well-balance.v1",
    "asw-0b4.rule.system-curve.v1",
    "asw-0b4.rule.clean-pump-curve.v1",
    "asw-0b4.rule.combined-pump-curve.v1",
    "asw-0b4.rule.obstruction-progression.v1",
    "asw-0b4.rule.clearance-progression.v1",
    "asw-0b4.rule.capability-predicate.v1",
    "asw-0b4.rule.observation-quantization.v1",
    "asw-0b4.rule.obstruction-clearing.v1",
    "asw-0b4.rule.clearance-repair.v1",
    "asw-0b4.rule.transfer.v1",
    "asw-0b4.rule.physical-interval-order.v1",
]

CANONICAL_DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z")
LOWER_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
SAFE_SEGMENT = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
SAFE_VERSION = re.compile(r"[0-9][a-z0-9.+-]*\Z")


class CertifierBoundaryError(ValueError):
    """Independent certifier declaration rejection."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(f"certifier:{reason}: {detail}")


def _reject(reason: str, detail: str) -> NoReturn:
    raise CertifierBoundaryError(reason, detail)


def _pairs_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    names = [name for name, _ in pairs]
    if len(names) != len(set(names)):
        _reject("input-duplicate-name", "an object member name occurs more than once")
    return dict(pairs)


def _walk_json(value: Any) -> None:
    if value is None:
        _reject("input-null", "null has no canonical meaning")
    if isinstance(value, float):
        _reject("input-json-number", "physical decimal JSON numbers are forbidden")
    if isinstance(value, dict):
        for name, member in value.items():
            if not isinstance(name, str):
                _reject("input-member-name", "object names must be strings")
            _walk_json(member)
    elif isinstance(value, list):
        for member in value:
            _walk_json(member)
    elif not isinstance(value, str | int | bool):
        _reject("input-type", f"unsupported JSON type {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    _walk_json(value)
    encoder = json.JSONEncoder(
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return (encoder.encode(value) + "\n").encode("utf-8")


def _parse_canonical_object(raw: bytes) -> dict[str, Any]:
    if raw[:3] == b"\xef\xbb\xbf":
        _reject("input-bom", "BOM is forbidden")
    if len(raw) < 2 or raw[-1:] != b"\n" or raw[-2:] == b"\n\n":
        _reject("input-final-newline", "one and only one final LF is required")
    if b"\r" in raw:
        _reject("input-line-ending", "CR is forbidden")
    try:
        decoded_text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        _reject("input-utf8", str(error))
    decoder = json.JSONDecoder(object_pairs_hook=_pairs_without_duplicates)
    try:
        value = decoder.decode(decoded_text)
    except json.JSONDecodeError as error:
        _reject("input-json", str(error))
    _walk_json(value)
    if not isinstance(value, dict):
        _reject("input-root", "the declaration root must be an object")
    result = cast(dict[str, Any], value)
    if raw != canonical_json_bytes(result):
        _reject("input-not-canonical", "independent byte reconstruction differs")
    return result


def _object_with_names(
    value: Any,
    names: frozenset[str],
    reason: str,
) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != names:
        _reject(reason, f"required names are {sorted(names)!r}")
    return cast(dict[str, Any], value)


def _sha256(value: Any, reason: str = "generation-content-id") -> str:
    if not isinstance(value, str) or LOWER_SHA256.fullmatch(value) is None:
        _reject(reason, "expected lower-case SHA-256")
    return value


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or CANONICAL_DECIMAL.fullmatch(value) is None:
        _reject("declaration-decimal", f"bad decimal {value!r}")
    try:
        number = Decimal(value)
    except InvalidOperation:
        _reject("declaration-decimal", f"bad decimal {value!r}")
    if number.is_zero() and value.startswith("-"):
        _reject("declaration-decimal", "negative zero is forbidden")
    return number


def _check_scalar_records(records: Any) -> None:
    if not isinstance(records, list) or len(records) != 46:
        _reject("declaration-parameters", "46 scalar records are required")
    record_names = frozenset(
        {
            "anchor",
            "evidence_class",
            "fixed",
            "identity",
            "lower",
            "unit",
            "upper",
            "value_kind",
        }
    )
    observed_order: list[str] = []
    for record_value in records:
        record = _object_with_names(
            record_value,
            record_names,
            "declaration-parameter-shape",
        )
        identity = record["identity"]
        if not isinstance(identity, str) or identity not in UNIT_BY_SCALAR:
            _reject("declaration-parameter-id", f"unknown parameter {identity!r}")
        observed_order.append(identity)
        if record["unit"] != UNIT_BY_SCALAR[identity]:
            _reject("declaration-unit", f"unit mismatch for {identity}")
        expected_evidence = "N" if identity == "fluid.g" else "S"
        if record["evidence_class"] != expected_evidence:
            _reject("declaration-evidence", f"evidence mismatch for {identity}")

        bounds: tuple[Any, Any, Any] = (
            record["lower"],
            record["anchor"],
            record["upper"],
        )
        if identity in BOOLEAN_SCALARS:
            kind = "boolean"
            if any(type(item) is not bool for item in bounds):
                _reject("declaration-boolean", f"boolean required for {identity}")
            ordered = bounds[0] == bounds[1] == bounds[2]
        elif identity in COUNT_SCALARS:
            kind = "integer"
            if any(type(item) is not int for item in bounds):
                _reject("declaration-integer", f"integer required for {identity}")
            ordered = bounds[0] <= bounds[1] <= bounds[2]
        else:
            kind = "decimal"
            low, anchor, high = (_decimal(item) for item in bounds)
            ordered = low <= anchor <= high
        if record["value_kind"] != kind:
            _reject("declaration-value-kind", f"wrong value kind for {identity}")
        if not ordered:
            _reject("declaration-bounds", f"bad bounds for {identity}")
        fixed = bounds[0] == bounds[2]
        if type(record["fixed"]) is not bool or record["fixed"] is not fixed:
            _reject("declaration-fixed", f"wrong fixed flag for {identity}")
    if tuple(observed_order) != SCALAR_ORDER:
        _reject("declaration-parameter-order", "parameter order is not W1 order")


def read_w1_declaration(raw: bytes) -> dict[str, Any]:
    document = _parse_canonical_object(raw)
    _object_with_names(
        document,
        frozenset(
            {
                "authority",
                "composites",
                "disposition",
                "orderings",
                "parameters",
                "rules",
            }
        ),
        "declaration-top-level",
    )
    authority = _object_with_names(
        document["authority"],
        frozenset(
            {
                "claim_profile_sha256",
                "declaration_schema_id",
                "evidence_rights_sha256",
                "profile_id",
                "scope",
                "w1_sha256",
            }
        ),
        "declaration-authority-shape",
    )
    if authority != {
        "claim_profile_sha256": AUTHORITIES[0][1],
        "declaration_schema_id": "asw-0b5.w1-member-authority.v1",
        "evidence_rights_sha256": ("8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96"),
        "profile_id": PROFILE,
        "scope": "research-private",
        "w1_sha256": AUTHORITIES[1][1],
    }:
        _reject("declaration-authority", "authority identity mismatch")
    if document["composites"] != FIXED_COMPOSITES:
        _reject("declaration-composite", "fixed composite mismatch")
    if document["disposition"] != {
        "claim_ceiling": "synthetic-v3-candidate-only",
        "current_visibility": "research-private",
        "later_visibility": "runtime-internal",
        "rights_class": "redistributable-repository-licence",
    }:
        _reject("declaration-disposition", "rights or claim boundary mismatch")
    if document["orderings"] != {
        "inflow": ["inflow.Q_low", "inflow.Q_nominal", "inflow.Q_assess"],
        "levels": [
            "well.h_stop",
            "well.h_start",
            "well.h_high",
            "well.h_overflow",
        ],
    }:
        _reject("declaration-ordering", "ordering mismatch")
    if document["rules"] != RULE_IDENTITIES:
        _reject("declaration-rule", "rule identity mismatch")
    _check_scalar_records(document["parameters"])
    if hashlib.sha256(raw).hexdigest() != REVIEWED_W1_DECLARATION:
        _reject("declaration-content", "reviewed declaration content changed")
    return document


def _check_generation_programs(document: dict[str, Any]) -> None:
    generator = _object_with_names(
        document["generator"],
        frozenset(
            {
                "configuration_id",
                "dependency_inventory_id",
                "source_inventory_id",
            }
        ),
        "generation-generator-shape",
    )
    certifier = _object_with_names(
        document["certifier"],
        frozenset(
            {
                "dependency_inventory_id",
                "environment_id",
                "source_inventory_id",
            }
        ),
        "generation-certifier-shape",
    )
    for identity in list(generator.values()) + list(certifier.values()):
        _sha256(identity)


def read_generation_declaration(raw: bytes) -> dict[str, Any]:
    document = _parse_canonical_object(raw)
    _object_with_names(
        document,
        frozenset(
            {
                "authorities",
                "cases",
                "certifier",
                "engine",
                "generator",
                "manifest_specification_id",
                "member_content_id",
                "package_profile_id",
                "profile_id",
                "receipt_profile",
                "replay_policy",
                "schema_id",
                "w4_probe_catalogue_content_id",
            }
        ),
        "generation-shape",
    )
    schema_id = document["schema_id"]
    authority_inventory: tuple[tuple[str, str], ...]
    if schema_id == "asw-0b5.generation-declaration.v1":
        authority_inventory = AUTHORITIES
    elif schema_id == "asw-0b5.generation-declaration.v2":
        authority_inventory = AMENDED_AUTHORITIES
    else:
        _reject("generation-schema", "schema mismatch")
    if document["authorities"] != [{"role": role, "sha256": sha256} for role, sha256 in authority_inventory]:
        _reject("generation-authorities", "wrong authority inventory")
    cases = document["cases"]
    if not isinstance(cases, list) or len(cases) != len(W2_CASES):
        _reject("generation-cases", "wrong case count")
    for position, expected_case in enumerate(W2_CASES):
        case = _object_with_names(
            cases[position],
            frozenset({"case_id", "content_id"}),
            "generation-case-shape",
        )
        if case["case_id"] != expected_case:
            _reject("generation-case-order", f"expected {expected_case}")
        _sha256(case["content_id"])
    _check_generation_programs(document)

    engine = _object_with_names(
        document["engine"],
        frozenset(
            {
                "commit",
                "configuration_id",
                "patch_sha256",
                "repository",
                "version",
            }
        ),
        "generation-engine-shape",
    )
    fixed_engine = {
        "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
        "patch_sha256": ("522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894"),
        "repository": "https://github.com/USEPA/Stormwater-Management-Model.git",
        "version": "5.2.4",
    }
    if any(engine[key] != value for key, value in fixed_engine.items()):
        _reject("generation-engine", "SWMM pin mismatch")
    _sha256(engine["configuration_id"])
    _sha256(document["member_content_id"])
    _sha256(document["w4_probe_catalogue_content_id"])

    if document["profile_id"] != PROFILE:
        _reject("generation-profile", "profile mismatch")
    if document["manifest_specification_id"] != "asw-0b5.promotion-manifest-specification.v1":
        _reject("generation-manifest-spec", "manifest specification mismatch")
    if document["package_profile_id"] != "asw-au-nsw-lh-syn-sps.package.v1":
        _reject("generation-package-profile", "package profile mismatch")
    if document["receipt_profile"] != {
        "identity": "asw-0b5.research-receipts.v1",
        "kinds": list(RECEIPT_PROFILE),
    }:
        _reject("generation-receipt-profile", "receipt profile mismatch")
    if document["replay_policy"] != {
        "ordinals": [0, 1],
        "workspace_policy": "fresh-absent-root",
    }:
        _reject("generation-replay", "replay policy mismatch")
    return document


def world_generation_id(raw: bytes) -> str:
    read_generation_declaration(raw)
    hasher = hashlib.sha256()
    hasher.update(b"asw-0b5.world-generation.v1")
    hasher.update(b"\0")
    hasher.update(raw)
    return hasher.hexdigest()


def validate_safe_relative_path(path: str) -> None:
    if not path or path[0] == "/" or "\\" in path or ":" in path or "%" in path:
        _reject("unsafe-path", repr(path))
    if any(ord(character) < 32 or ord(character) > 126 for character in path):
        _reject("unsafe-path", repr(path))
    parts = path.split("/")
    for part in parts:
        if part in {"", ".", ".."} or SAFE_SEGMENT.fullmatch(part) is None:
            _reject("unsafe-path", repr(path))


def capture_source_identity(root: Path, relative_paths: Sequence[str]) -> str:
    if root.is_symlink() or not root.is_dir():
        _reject("source-root", "root must be a non-symlink directory")
    paths = tuple(relative_paths)
    if not paths or paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
        _reject("source-inventory", "paths must be unique lexical entries")
    entries: list[dict[str, str]] = []
    for name in paths:
        validate_safe_relative_path(name)
        candidate = root.joinpath(*name.split("/"))
        try:
            mode = candidate.lstat().st_mode
        except OSError as error:
            _reject("source-file", str(error))
        if candidate.is_symlink() or not stat.S_ISREG(mode):
            _reject("source-file-type", f"{name} is not a regular file")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        entries.append({"content_sha256": digest, "path": name})
    encoded = canonical_json_bytes({"files": entries})
    hasher = hashlib.sha256()
    hasher.update(b"asw-0b5.certifier-source-inventory.v1\0")
    hasher.update(encoded)
    return hasher.hexdigest()


def capture_dependency_identity(
    dependencies: Sequence[tuple[str, str]],
) -> str:
    items = tuple(dependencies)
    if not items or items != tuple(sorted(items)) or len(items) != len(set(items)):
        _reject("dependency-inventory", "dependencies must be unique and lexical")
    records: list[dict[str, str]] = []
    for name, version in items:
        if SAFE_SEGMENT.fullmatch(name) is None:
            _reject("dependency-name", repr(name))
        if SAFE_VERSION.fullmatch(version) is None:
            _reject("dependency-version", repr(version))
        records.append({"name": name, "version": version})
    encoded = canonical_json_bytes({"dependencies": records})
    hasher = hashlib.sha256()
    hasher.update(b"asw-0b5.certifier-dependency-inventory.v1\0")
    hasher.update(encoded)
    return hasher.hexdigest()
