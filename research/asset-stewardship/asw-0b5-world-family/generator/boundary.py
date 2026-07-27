# ABOUTME: Implements the generator-side canonical declaration, hashing, path, and source-identity boundary for B5-W0.
# ABOUTME: Remains independent of the certifier, lineage reader, SWMM, hydraulics, and production code.

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, NoReturn, cast

PROFILE_ID = "AU-NSW-LH-SYN-SPS-v1"
W1_DECLARATION_SHA256 = "4470e8af16bb6238a11045847199ffad95f1a7f57f64e85978a009bdda30ded9"

AUTHORITY_HASHES = (
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

CASE_IDS = (
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

RECEIPT_KINDS = (
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

PARAMETER_IDENTITIES = (
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

EXPECTED_UNITS = {
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

INTEGER_PARAMETERS = {
    "topology.max_running_pumps",
    "topology.transfer_limit",
    "exposure.starts_max",
    "resource.concurrent_limit",
}
BOOLEAN_PARAMETERS = {"resource.kit_initial"}

EXPECTED_COMPOSITES: list[dict[str, Any]] = [
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

EXPECTED_RULES = (
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
)

DECIMAL_PATTERN = re.compile(r"-?(0|[1-9][0-9]*)(\.[0-9]+)?\Z")
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
PATH_SEGMENT_PATTERN = re.compile(r"[a-z0-9][a-z0-9._-]*\Z")
DEPENDENCY_VERSION_PATTERN = re.compile(r"[0-9][a-z0-9.+-]*\Z")


class GeneratorBoundaryError(ValueError):
    """Fail-closed generator-side declaration boundary error."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"generator:{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise GeneratorBoundaryError(code, detail)


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("bytes.duplicate-key", f"duplicate object key {key!r}")
        result[key] = value
    return result


def _reject_noncanonical_json_types(value: Any) -> None:
    if value is None:
        _fail("bytes.null", "null is forbidden")
    if isinstance(value, float):
        _fail("bytes.number", "JSON floating-point numbers are forbidden")
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                _fail("bytes.key", "object keys must be strings")
            _reject_noncanonical_json_types(child)
        return
    if isinstance(value, list):
        for child in value:
            _reject_noncanonical_json_types(child)
        return
    if not isinstance(value, str | int | bool):
        _fail("bytes.type", f"unsupported JSON value {type(value).__name__}")


def canonical_json_bytes(value: object) -> bytes:
    _reject_noncanonical_json_types(value)
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{encoded}\n".encode()


def _read_canonical_object(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        _fail("bytes.bom", "UTF-8 BOM is forbidden")
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n"):
        _fail("bytes.terminal-lf", "exactly one terminal LF is required")
    if b"\r" in raw:
        _fail("bytes.line-ending", "CR bytes are forbidden")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        _fail("bytes.utf8", str(error))
    try:
        decoded = json.loads(text, object_pairs_hook=_object_pairs)
    except json.JSONDecodeError as error:
        _fail("bytes.json", str(error))
    _reject_noncanonical_json_types(decoded)
    if not isinstance(decoded, dict):
        _fail("bytes.root", "top-level JSON value must be an object")
    document = cast(dict[str, Any], decoded)
    if canonical_json_bytes(document) != raw:
        _fail("bytes.noncanonical", "bytes do not match the canonical reconstruction")
    return document


def _require_keys(value: Any, expected: set[str], code: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        _fail(code, f"expected keys {sorted(expected)!r}")
    return cast(dict[str, Any], value)


def _require_hash(value: Any, code: str) -> str:
    if not isinstance(value, str) or HASH_PATTERN.fullmatch(value) is None:
        _fail(code, "expected a lower-case hexadecimal SHA-256")
    return value


def _require_decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or DECIMAL_PATTERN.fullmatch(value) is None:
        _fail("scalar.decimal", f"non-canonical decimal {value!r}")
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        _fail("scalar.decimal", f"invalid decimal {value!r}")
    if parsed.is_zero() and value.startswith("-"):
        _fail("scalar.decimal", "negative zero is forbidden")
    return parsed


def _validate_parameter(record: Any, expected_identity: str) -> None:
    parameter = _require_keys(
        record,
        {
            "anchor",
            "evidence_class",
            "fixed",
            "identity",
            "lower",
            "unit",
            "upper",
            "value_kind",
        },
        "shape.parameter",
    )
    if parameter["identity"] != expected_identity:
        _fail("shape.parameter-order", f"expected {expected_identity}")
    expected_unit = EXPECTED_UNITS[expected_identity]
    if parameter["unit"] != expected_unit:
        _fail("unit.mismatch", f"{expected_identity} must use {expected_unit}")
    expected_evidence = "N" if expected_identity == "fluid.g" else "S"
    if parameter["evidence_class"] != expected_evidence:
        _fail("evidence.mismatch", f"{expected_identity} evidence class changed")

    if expected_identity in BOOLEAN_PARAMETERS:
        expected_kind = "boolean"
        values = (
            parameter["lower"],
            parameter["anchor"],
            parameter["upper"],
        )
        if any(type(value) is not bool for value in values):
            _fail("scalar.boolean", f"{expected_identity} requires booleans")
        in_bounds = values[0] == values[1] == values[2]
    elif expected_identity in INTEGER_PARAMETERS:
        expected_kind = "integer"
        values = (
            parameter["lower"],
            parameter["anchor"],
            parameter["upper"],
        )
        if any(type(value) is not int for value in values):
            _fail("scalar.integer", f"{expected_identity} requires integers")
        in_bounds = values[0] <= values[1] <= values[2]
    else:
        expected_kind = "decimal"
        lower = _require_decimal(parameter["lower"])
        anchor = _require_decimal(parameter["anchor"])
        upper = _require_decimal(parameter["upper"])
        in_bounds = lower <= anchor <= upper

    if parameter["value_kind"] != expected_kind:
        _fail("scalar.kind", f"{expected_identity} must use {expected_kind}")
    if not in_bounds:
        _fail("scalar.bounds", f"{expected_identity} anchor is outside its bounds")
    should_be_fixed = parameter["lower"] == parameter["upper"]
    if type(parameter["fixed"]) is not bool or parameter["fixed"] != should_be_fixed:
        _fail("scalar.fixed", f"{expected_identity} fixed flag disagrees with bounds")


def read_w1_declaration(raw: bytes) -> dict[str, Any]:
    declaration = _read_canonical_object(raw)
    _require_keys(
        declaration,
        {
            "authority",
            "composites",
            "disposition",
            "orderings",
            "parameters",
            "rules",
        },
        "shape.top-level",
    )
    authority = _require_keys(
        declaration["authority"],
        {
            "claim_profile_sha256",
            "declaration_schema_id",
            "evidence_rights_sha256",
            "profile_id",
            "scope",
            "w1_sha256",
        },
        "shape.authority",
    )
    expected_authority = {
        "claim_profile_sha256": AUTHORITY_HASHES[0][1],
        "declaration_schema_id": "asw-0b5.w1-member-authority.v1",
        "evidence_rights_sha256": ("8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96"),
        "profile_id": PROFILE_ID,
        "scope": "research-private",
        "w1_sha256": AUTHORITY_HASHES[1][1],
    }
    if authority != expected_authority:
        _fail("authority.mismatch", "W1 declaration authority changed")

    expected_disposition = {
        "claim_ceiling": "synthetic-v3-candidate-only",
        "current_visibility": "research-private",
        "later_visibility": "runtime-internal",
        "rights_class": "redistributable-repository-licence",
    }
    if declaration["disposition"] != expected_disposition:
        _fail("disposition.mismatch", "claim, rights, or visibility changed")
    expected_orderings = {
        "inflow": ["inflow.Q_low", "inflow.Q_nominal", "inflow.Q_assess"],
        "levels": [
            "well.h_stop",
            "well.h_start",
            "well.h_high",
            "well.h_overflow",
        ],
    }
    if declaration["orderings"] != expected_orderings:
        _fail("ordering.mismatch", "W1 ordering declaration changed")
    if declaration["composites"] != EXPECTED_COMPOSITES:
        _fail("composite.mismatch", "fixed W1 composite declaration changed")
    if declaration["rules"] != list(EXPECTED_RULES):
        _fail("rule.mismatch", "W1 rule identity list changed")

    parameters = declaration["parameters"]
    if not isinstance(parameters, list) or len(parameters) != len(PARAMETER_IDENTITIES):
        _fail("shape.parameters", "all 46 scalar parameter records are required")
    for record, expected_identity in zip(parameters, PARAMETER_IDENTITIES, strict=True):
        _validate_parameter(record, expected_identity)

    actual_sha256 = hashlib.sha256(raw).hexdigest()
    if actual_sha256 != W1_DECLARATION_SHA256:
        _fail("authority.content", "W1 declaration bytes differ from the reviewed declaration")
    return declaration


def _validate_generation_implementations(declaration: dict[str, Any]) -> None:
    generator = _require_keys(
        declaration["generator"],
        {
            "configuration_id",
            "dependency_inventory_id",
            "source_inventory_id",
        },
        "generation.generator-shape",
    )
    certifier = _require_keys(
        declaration["certifier"],
        {
            "dependency_inventory_id",
            "environment_id",
            "source_inventory_id",
        },
        "generation.certifier-shape",
    )
    for value in (*generator.values(), *certifier.values()):
        _require_hash(value, "generation.content-id")


def read_generation_declaration(raw: bytes) -> dict[str, Any]:
    declaration = _read_canonical_object(raw)
    _require_keys(
        declaration,
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
        },
        "generation.shape",
    )
    expected_authorities = [{"role": role, "sha256": sha256} for role, sha256 in AUTHORITY_HASHES]
    if declaration["authorities"] != expected_authorities:
        _fail("generation.authorities", "profile and W1-W5 authorities must match")

    cases = declaration["cases"]
    if not isinstance(cases, list) or len(cases) != len(CASE_IDS):
        _fail("generation.cases", "exact W2 case inventory is required")
    for case, expected_id in zip(cases, CASE_IDS, strict=True):
        case_record = _require_keys(
            case,
            {"case_id", "content_id"},
            "generation.case-shape",
        )
        if case_record["case_id"] != expected_id:
            _fail("generation.case-order", f"expected case {expected_id}")
        _require_hash(case_record["content_id"], "generation.content-id")

    _validate_generation_implementations(declaration)
    engine = _require_keys(
        declaration["engine"],
        {
            "commit",
            "configuration_id",
            "patch_sha256",
            "repository",
            "version",
        },
        "generation.engine-shape",
    )
    if (
        engine["repository"] != "https://github.com/USEPA/Stormwater-Management-Model.git"
        or engine["version"] != "5.2.4"
        or engine["commit"] != "7952ca837988b1c32f791812eccc9fd64547e093"
        or engine["patch_sha256"] != "522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894"
    ):
        _fail("generation.engine", "pinned SWMM identity changed")
    _require_hash(engine["configuration_id"], "generation.content-id")

    if declaration["profile_id"] != PROFILE_ID:
        _fail("generation.profile", "profile identity changed")
    if declaration["schema_id"] != "asw-0b5.generation-declaration.v1":
        _fail("generation.schema", "generation schema identity changed")
    if (
        declaration["manifest_specification_id"] != "asw-0b5.promotion-manifest-specification.v1"
        or declaration["package_profile_id"] != "asw-au-nsw-lh-syn-sps.package.v1"
    ):
        _fail("generation.package-spec", "W5 package specification changed")
    _require_hash(declaration["member_content_id"], "generation.content-id")
    _require_hash(
        declaration["w4_probe_catalogue_content_id"],
        "generation.content-id",
    )
    if declaration["receipt_profile"] != {
        "identity": "asw-0b5.research-receipts.v1",
        "kinds": list(RECEIPT_KINDS),
    }:
        _fail("generation.receipt-profile", "receipt kind profile changed")
    if declaration["replay_policy"] != {
        "ordinals": [0, 1],
        "workspace_policy": "fresh-absent-root",
    }:
        _fail("generation.replay", "two fresh ordered replays are required")
    return declaration


def world_generation_id(raw: bytes) -> str:
    read_generation_declaration(raw)
    return hashlib.sha256(b"asw-0b5.world-generation.v1\0" + raw).hexdigest()


def validate_safe_relative_path(path: str) -> None:
    if not path or path.startswith("/") or "\\" in path or ":" in path:
        _fail("path.unsafe", f"unsafe relative path {path!r}")
    if "\x00" in path or any(ord(character) < 32 for character in path):
        _fail("path.unsafe", f"control character in path {path!r}")
    if "%" in path:
        _fail("path.unsafe", f"encoded path material is forbidden in {path!r}")
    segments = path.split("/")
    if any(segment in {"", ".", ".."} or PATH_SEGMENT_PATTERN.fullmatch(segment) is None for segment in segments):
        _fail("path.unsafe", f"unsafe relative path {path!r}")


def capture_source_identity(root: Path, relative_paths: Sequence[str]) -> str:
    if root.is_symlink() or not root.is_dir():
        _fail("source.root", "source root must be a real directory")
    if not relative_paths or len(set(relative_paths)) != len(relative_paths):
        _fail("source.inventory", "source paths must be non-empty and unique")
    if tuple(relative_paths) != tuple(sorted(relative_paths)):
        _fail("source.inventory", "source paths must be in lexical order")

    inventory: list[dict[str, str]] = []
    for relative_path in relative_paths:
        validate_safe_relative_path(relative_path)
        source_path = root.joinpath(*relative_path.split("/"))
        try:
            source_stat = source_path.lstat()
        except OSError as error:
            _fail("source.file", str(error))
        if source_path.is_symlink() or not stat.S_ISREG(source_stat.st_mode):
            _fail("source.file-type", f"{relative_path} is not a regular file")
        inventory.append(
            {
                "content_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
                "path": relative_path,
            }
        )
    inventory_bytes = canonical_json_bytes({"files": inventory})
    return hashlib.sha256(b"asw-0b5.generator-source-inventory.v1\0" + inventory_bytes).hexdigest()


def capture_dependency_identity(
    dependencies: Sequence[tuple[str, str]],
) -> str:
    if not dependencies or len(set(dependencies)) != len(dependencies):
        _fail("dependency.inventory", "dependencies must be non-empty and unique")
    if tuple(dependencies) != tuple(sorted(dependencies)):
        _fail("dependency.inventory", "dependencies must be in lexical order")
    inventory: list[dict[str, str]] = []
    for name, version in dependencies:
        if PATH_SEGMENT_PATTERN.fullmatch(name) is None:
            _fail("dependency.name", f"unsafe dependency name {name!r}")
        if DEPENDENCY_VERSION_PATTERN.fullmatch(version) is None:
            _fail("dependency.version", f"unsafe dependency version {version!r}")
        inventory.append({"name": name, "version": version})
    inventory_bytes = canonical_json_bytes({"dependencies": inventory})
    return hashlib.sha256(b"asw-0b5.generator-dependency-inventory.v1\0" + inventory_bytes).hexdigest()
