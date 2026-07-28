# ABOUTME: Builds and validates path-free canonical W2 members, cases, and generator requests.
# ABOUTME: Enforces W1 authority, identity, unit, bound, cross-constraint, catalogue, and engine gates before SWMM.

from __future__ import annotations

import hashlib
import json
import re
from decimal import Decimal, localcontext
from pathlib import Path
from typing import Any, NoReturn, cast

from generator import boundary
from repairs import solver_convergence

PROFILE_ID = boundary.PROFILE_ID
CASE_IDS = boundary.CASE_IDS
GENERATOR_PROTOCOL_ID = "asw-0b5.generator-protocol.v3"
CATALOGUE_SCHEMA_ID = "asw-0b5.w2-case-catalogue.v1"
REQUEST_SCHEMA_ID = "asw-0b5.generator-request.v2"
MAPPING_REPAIR_SCHEMA_ID = "asw-0b5.engine-mapping-repair.v1"
MAPPING_REPAIR_SHA256 = (
    "862ef1f5fc70d882d156c0ef9842bb565301344725d2206edfa49c10910576ca"
)
MEMBER_DOMAIN = b"asw-0b4.member.v1\0"
CASE_DOMAIN = b"asw-0b4.case.v1\0"
REQUEST_DOMAIN = b"asw-0b5.generator-request.v2\0"
STATE_DOMAIN = b"asw-0b4.pump-state.v1\0"
ASSIGNMENT_DOMAIN = b"asw-0b4.duty-assignment.v1\0"
HASH_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
ENUM_PATTERN = re.compile(r"[a-z][a-z0-9-]*\Z")
PI = Decimal("3.141592653589793238462643383279503")

SERIES_OUTPUTS = (
    "time_s",
    "wet_well_depth_m",
    "wet_well_volume_m3",
    "wet_well_inflow_m3_s",
    "wet_well_overflow_m3_s",
    "pump_a_flow_m3_s",
    "pump_b_flow_m3_s",
    "force_main_flow_m3_s",
    "pump_a_setting",
    "pump_b_setting",
    "wet_well_head_m",
    "discharge_head_m",
)

ENGINE_KEYS = {
    "build_receipt_sha256",
    "commit",
    "executable_sha256",
    "output_library_sha256",
    "patch_sha256",
    "repository",
    "settings_id",
    "solver_library_sha256",
    "version",
}
ENGINE_EXPECTED = {
    "commit": "7952ca837988b1c32f791812eccc9fd64547e093",
    "patch_sha256": "522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894",
    "repository": "https://github.com/USEPA/Stormwater-Management-Model.git",
    "settings_id": solver_convergence.ENGINE_SETTINGS_ID,
    "version": "5.2.4",
}


class GeneratorRequestError(ValueError):
    """Fail-closed canonical W2 request error."""

    def __init__(self, family: str, detail: str) -> None:
        self.family = family
        super().__init__(f"generator-request:{family}: {detail}")


def _fail(family: str, detail: str) -> NoReturn:
    raise GeneratorRequestError(family, detail)


def canonical_json_bytes(value: object) -> bytes:
    """Return the W2 canonical JSON representation."""
    return boundary.canonical_json_bytes(value)


def _read_canonical_object(raw: bytes, family: str) -> dict[str, Any]:
    try:
        if raw.startswith(b"\xef\xbb\xbf"):
            _fail(family, "UTF-8 BOM is forbidden")
        if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
            _fail(family, "exactly one LF terminator and no CR bytes are required")
        seen_duplicate = False

        def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            nonlocal seen_duplicate
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    seen_duplicate = True
                result[key] = value
            return result

        parsed = json.loads(raw.decode("utf-8"), object_pairs_hook=object_pairs)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(family, str(error))
    if seen_duplicate:
        _fail(family, "duplicate object key")
    if not isinstance(parsed, dict):
        _fail(family, "top-level JSON value must be an object")
    value = cast(dict[str, Any], parsed)
    try:
        reconstructed = canonical_json_bytes(value)
    except boundary.GeneratorBoundaryError as error:
        _fail(family, str(error))
    if reconstructed != raw:
        _fail(family, "bytes are not canonical")
    return value


def _without(value: dict[str, Any], key: str) -> dict[str, Any]:
    return {name: child for name, child in value.items() if name != key}


def _content_id(domain: bytes, value: dict[str, Any], identity_field: str) -> str:
    return hashlib.sha256(domain + canonical_json_bytes(_without(value, identity_field))).hexdigest()


def member_content_id(member: dict[str, Any]) -> str:
    """Return the member identity without trusting its declared identity."""
    return _content_id(MEMBER_DOMAIN, member, "member_content_id")


def case_content_id(case: dict[str, Any]) -> str:
    """Return the case identity without trusting its declared identity."""
    return _content_id(CASE_DOMAIN, case, "case_content_id")


def request_content_id(request: dict[str, Any]) -> str:
    """Return the request identity without trusting its declared identity."""
    return _content_id(REQUEST_DOMAIN, request, "request_content_id")


def _state_content_id(state: dict[str, str]) -> str:
    return hashlib.sha256(STATE_DOMAIN + canonical_json_bytes(state)).hexdigest()


def _assignment_content_id(assignment: str) -> str:
    return hashlib.sha256(ASSIGNMENT_DOMAIN + assignment.encode("ascii")).hexdigest()


def _default_authority_path() -> Path:
    return Path(__file__).resolve().parents[1] / "declarations" / "w1-member-authority.json"


def _default_catalogue_path() -> Path:
    return Path(__file__).resolve().parents[1] / "declarations" / "w2-case-catalogue.json"


def _default_mapping_repair_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "declarations"
        / "w2-w4-engine-mapping-repair.json"
    )


def _default_solver_convergence_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "declarations"
        / "solver-convergence-amendment.json"
    )


def read_mapping_repair(raw: bytes) -> dict[str, Any]:
    """Read the exact approved repair that supersedes the W2-W4 engine mapping."""
    repair = _read_canonical_object(raw, "mapping-repair")
    if hashlib.sha256(raw).hexdigest() != MAPPING_REPAIR_SHA256:
        _fail("mapping-repair", "declaration identity differs")
    if set(repair) != {
        "authority",
        "engine_mapping",
        "formula",
        "semantic",
        "sensitivity",
        "status",
    }:
        _fail("mapping-repair", "declaration shape differs")
    authority = repair["authority"]
    expected_authority = {
        "certifier_protocol_predecessor_sha256": dict(boundary.AUTHORITY_HASHES)["w3"],
        "generator_protocol_id": GENERATOR_PROTOCOL_ID,
        "generator_protocol_predecessor_sha256": dict(boundary.AUTHORITY_HASHES)["w2"],
        "profile_id": PROFILE_ID,
        "repair_schema_id": MAPPING_REPAIR_SCHEMA_ID,
        "scope": "research-private",
        "sensitivity_protocol_predecessor_sha256": dict(boundary.AUTHORITY_HASHES)["w4"],
    }
    if authority != expected_authority or repair["status"] != "approved-repair":
        _fail("mapping-repair", "declaration authority differs")
    return repair


def anchor_member(authority_bytes: bytes) -> dict[str, Any]:
    """Construct the complete anchor member from the reviewed machine authority."""
    try:
        authority = boundary.read_w1_declaration(authority_bytes)
    except boundary.GeneratorBoundaryError as error:
        _fail("authority", str(error))
    parameters = [
        {
            "identity": parameter["identity"],
            "unit": parameter["unit"],
            "value": parameter["anchor"],
        }
        for parameter in authority["parameters"]
    ]
    member: dict[str, Any] = {
        "composites": authority["composites"],
        "member_content_id": "",
        "parameters": parameters,
    }
    member["member_content_id"] = member_content_id(member)
    return member


def read_case_catalogue(raw: bytes) -> dict[str, Any]:
    """Read the exact executable W2 case declaration."""
    catalogue = _read_canonical_object(raw, "case-authorization")
    if set(catalogue) != {"authority", "cases", "outputs", "schema_id"}:
        _fail("case-authorization", "catalogue has unexpected top-level keys")
    if catalogue["schema_id"] != CATALOGUE_SCHEMA_ID:
        _fail("case-authorization", "catalogue schema identity differs")
    authority = catalogue["authority"]
    expected_authority = {
        "profile_id": PROFILE_ID,
        "protocol_id": GENERATOR_PROTOCOL_ID,
        "repair_declaration_sha256": MAPPING_REPAIR_SHA256,
        "w1_declaration_sha256": boundary.W1_DECLARATION_SHA256,
        "w1_sha256": dict(boundary.AUTHORITY_HASHES)["w1"],
    }
    if authority != expected_authority:
        _fail("case-authorization", "catalogue authority differs")
    cases = catalogue["cases"]
    actual_case_ids = [
        case.get("case_id") for case in cases if isinstance(case, dict)
    ] if isinstance(cases, list) else []
    if not isinstance(cases, list) or actual_case_ids != list(CASE_IDS):
        _fail("case-authorization", "catalogue case IDs or order differ")
    if catalogue["outputs"] != list(SERIES_OUTPUTS):
        _fail("case-authorization", "catalogue output allowlist differs")
    for case in cases:
        _validate_catalogue_case(case)
    return catalogue


def _validate_catalogue_case(case: object) -> None:
    if not isinstance(case, dict):
        _fail("case-authorization", "catalogue cases must be objects")
    case = cast(dict[str, Any], case)
    template = case.get("template")
    if not isinstance(template, str) or ENUM_PATTERN.fullmatch(template) is None:
        _fail("case-authorization", "case template must be a lower-case token")
    expected_keys_by_template = {
        "zero-static": {"case_id", "template"},
        "automatic-clean-base": {"case_id", "selected_pump", "template"},
        "forced-assessment": {
            "case_id",
            "clearance_loss",
            "obstruction",
            "template",
        },
        "forced-intervention": {
            "after_clearance_loss",
            "after_obstruction",
            "before_clearance_loss",
            "before_obstruction",
            "case_id",
            "effect_kind",
            "template",
        },
        "transfer-a-to-b": {"case_id", "template"},
        "progression-checkpoints": {"case_id", "checkpoints", "template"},
    }
    expected = expected_keys_by_template.get(template)
    if expected is None or set(case) != expected:
        _fail("case-authorization", f"unexpected catalogue shape for {case.get('case_id')!r}")


def _clean_state() -> dict[str, str]:
    return {"clearance-loss": "0", "obstruction": "0"}


def _exposure(runtime_s: int = 0, starts: int = 0) -> dict[str, int]:
    return {"calendar_s": runtime_s, "completed_starts": starts, "runtime_s": runtime_s}


def _decimal_text(value: Decimal) -> str:
    rendered = format(value, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return "0" if rendered in {"", "-0"} else rendered


def _progressed_state(member: dict[str, Any], runtime_s: int, starts: int) -> dict[str, str]:
    values = _parameter_values(member)
    obstruction = min(
        Decimal(1),
        values["mechanism.r_o_runtime"] * runtime_s + values["mechanism.r_o_start"] * starts,
    )
    clearance = min(Decimal(1), values["mechanism.r_c_runtime"] * runtime_s)
    return {
        "clearance-loss": _decimal_text(clearance),
        "obstruction": _decimal_text(obstruction),
    }


def _materialize_case(case_declaration: dict[str, Any], member: dict[str, Any]) -> dict[str, Any]:
    case_id = cast(str, case_declaration["case_id"])
    template = case_declaration["template"]
    pump_a_state = _clean_state()
    pump_b_state = _clean_state()
    base: dict[str, Any] = {
        "case_content_id": "",
        "case_id": case_id,
        "checkpoints": [],
        "control_mode": "forced-on",
        "exposure_state": {
            "pump-a": _exposure(),
            "pump-b": _exposure(),
        },
        "family": "hydraulic-diagnostic",
        "history_retained": True,
        "horizon_s": 120,
        "inflow_stimulus": "constant-assessment",
        "initial_depth_source": "well.h_start",
        "mechanism_state": {
            "pump-a": pump_a_state,
            "pump-b": pump_b_state,
        },
        "non_promotable_boundary": False,
        "physical_transitions": [],
        "segments": [],
        "selected_pump": "pump-a",
    }
    if template == "zero-static":
        base.update(
            {
                "control_mode": "forced-off",
                "family": "static-boundary",
                "horizon_s": 3600,
                "inflow_stimulus": "zero",
                "non_promotable_boundary": True,
                "selected_pump": "none",
            }
        )
    elif template == "automatic-clean-base":
        selected = case_declaration["selected_pump"]
        base.update(
            {
                "control_mode": "automatic",
                "family": "automatic-base",
                "horizon_s": 28800,
                "inflow_stimulus": "base-pattern",
                "initial_depth_source": "well.h_stop",
                "selected_pump": selected,
            }
        )
    elif template == "forced-assessment":
        pump_a_state.update(
            {
                "clearance-loss": case_declaration["clearance_loss"],
                "obstruction": case_declaration["obstruction"],
            }
        )
    elif template == "forced-intervention":
        before = {
            "clearance-loss": case_declaration["before_clearance_loss"],
            "obstruction": case_declaration["before_obstruction"],
        }
        after = {
            "clearance-loss": case_declaration["after_clearance_loss"],
            "obstruction": case_declaration["after_obstruction"],
        }
        base["mechanism_state"]["pump-a"] = after
        base["physical_transitions"] = [
            {
                "after_state_content_id": _state_content_id(after),
                "before_state_content_id": _state_content_id(before),
                "effect_kind": case_declaration["effect_kind"],
                "effective_second": 0,
                "rule_identity": (
                    "asw-0b4.rule.obstruction-clearing.v1"
                    if case_declaration["effect_kind"] == "obstruction-clearing"
                    else "asw-0b4.rule.clearance-repair.v1"
                ),
                "target_pump": "pump-a",
            }
        ]
    elif template == "transfer-a-to-b":
        pump_a_state["obstruction"] = "0.75"
        base.update(
            {
                "control_mode": "transfer",
                "family": "transfer-sequence",
                "segments": [
                    {
                        "horizon_s": 60,
                        "local_end_s": 60,
                        "local_start_s": 1,
                        "selected_pump": "pump-a",
                    },
                    {
                        "horizon_s": 60,
                        "local_end_s": 60,
                        "local_start_s": 1,
                        "selected_pump": "pump-b",
                    },
                ],
                "physical_transitions": [
                    {
                        "after_state_content_id": _assignment_content_id("pump-b"),
                        "before_state_content_id": _assignment_content_id("pump-a"),
                        "effect_kind": "duty-transfer",
                        "effective_second": 60,
                        "rule_identity": "asw-0b4.rule.transfer.v1",
                        "target_pump": "pump-a-to-pump-b",
                    }
                ],
                "selected_pump": "pump-a-to-pump-b",
            }
        )
    elif template == "progression-checkpoints":
        checkpoints: list[dict[str, Any]] = []
        for checkpoint in case_declaration["checkpoints"]:
            runtime_s = checkpoint["runtime_s"]
            starts = checkpoint["completed_starts"]
            state = _progressed_state(member, runtime_s, starts)
            checkpoints.append(
                {
                    "checkpoint_index": checkpoint["checkpoint_index"],
                    "exposure": _exposure(runtime_s, starts),
                    "mechanism_state": state,
                }
            )
        base.update(
            {
                "checkpoints": checkpoints,
                "family": "progression-checkpoints",
            }
        )
    else:
        _fail("case-authorization", f"unsupported template {template!r}")
    base["case_content_id"] = case_content_id(base)
    return base


def _parameter_values(member: dict[str, Any]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if isinstance(value, bool):
            continue
        values[parameter["identity"]] = Decimal(value) if isinstance(value, str) else Decimal(value)
    return values


def _engine_identity(value: object) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != ENGINE_KEYS:
        _fail("request-shape", "engine identity has unexpected keys")
    engine = cast(dict[str, Any], value)
    for key, expected in ENGINE_EXPECTED.items():
        if engine[key] != expected:
            _fail("engine-settings", f"engine {key} differs")
    for key in (
        "build_receipt_sha256",
        "executable_sha256",
        "solver_library_sha256",
        "output_library_sha256",
        "patch_sha256",
    ):
        if not isinstance(engine[key], str) or HASH_PATTERN.fullmatch(engine[key]) is None:
            _fail("engine-build", f"engine {key} is not a SHA-256")
    return engine


def build_member_request(
    *,
    authority_bytes: bytes,
    catalogue_bytes: bytes,
    case_id: str,
    engine_identity: dict[str, Any],
    member: dict[str, Any],
    repair_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> bytes:
    """Build one complete request for a validated W1 family member."""
    authority_declaration = boundary.read_w1_declaration(authority_bytes)
    read_mapping_repair(repair_bytes)
    solver_convergence.read_amendment(solver_convergence_bytes)
    catalogue = read_case_catalogue(catalogue_bytes)
    selected = next((case for case in catalogue["cases"] if case["case_id"] == case_id), None)
    if selected is None:
        _fail("case-authorization", f"unknown case {case_id!r}")
    if (
        not isinstance(member, dict)
        or set(member)
        != {"composites", "member_content_id", "parameters"}
        or member.get("member_content_id") != member_content_id(member)
    ):
        _fail("content-identity", "member content identity differs")
    _validate_units_and_bounds(member, authority_declaration)
    _validate_cross_constraints(member)
    case = _materialize_case(selected, member)
    request: dict[str, Any] = {
        "authority": {
            "profile_id": PROFILE_ID,
            "promotable": False,
            "protocol_id": GENERATOR_PROTOCOL_ID,
            "repair_declaration_sha256": MAPPING_REPAIR_SHA256,
            "scope": "research-only",
            "solver_convergence_amendment_sha256": (
                solver_convergence.AMENDMENT_SHA256
            ),
            "w1_declaration_sha256": boundary.W1_DECLARATION_SHA256,
            "w1_sha256": authority_declaration["authority"]["w1_sha256"],
        },
        "case": case,
        "engine": _engine_identity(engine_identity),
        "member": member,
        "outputs": catalogue["outputs"],
        "request_content_id": "",
        "schema_id": REQUEST_SCHEMA_ID,
    }
    request["request_content_id"] = request_content_id(request)
    return canonical_json_bytes(request)


def build_anchor_request(
    *,
    authority_bytes: bytes,
    catalogue_bytes: bytes,
    case_id: str,
    engine_identity: dict[str, Any],
    repair_bytes: bytes,
    solver_convergence_bytes: bytes,
) -> bytes:
    """Build one complete anchor request for an exact catalogue case."""
    return build_member_request(
        authority_bytes=authority_bytes,
        catalogue_bytes=catalogue_bytes,
        case_id=case_id,
        engine_identity=engine_identity,
        member=anchor_member(authority_bytes),
        repair_bytes=repair_bytes,
        solver_convergence_bytes=solver_convergence_bytes,
    )


def _require_request_shape(value: dict[str, Any]) -> None:
    if set(value) != {
        "authority",
        "case",
        "engine",
        "member",
        "outputs",
        "request_content_id",
        "schema_id",
    }:
        _fail("request-shape", "request top-level keys differ")
    if value["schema_id"] != REQUEST_SCHEMA_ID:
        _fail("request-shape", "request schema differs")
    if not isinstance(value["member"], dict) or set(value["member"]) != {
        "composites",
        "member_content_id",
        "parameters",
    }:
        _fail("request-shape", "member shape differs")
    if not isinstance(value["case"], dict):
        _fail("request-shape", "case must be an object")
    _engine_identity(value["engine"])


def _validate_authority(value: object) -> None:
    expected = {
        "profile_id": PROFILE_ID,
        "promotable": False,
        "protocol_id": GENERATOR_PROTOCOL_ID,
        "repair_declaration_sha256": MAPPING_REPAIR_SHA256,
        "scope": "research-only",
        "solver_convergence_amendment_sha256": (
            solver_convergence.AMENDMENT_SHA256
        ),
        "w1_declaration_sha256": boundary.W1_DECLARATION_SHA256,
        "w1_sha256": dict(boundary.AUTHORITY_HASHES)["w1"],
    }
    if value != expected:
        _fail("authority", "request authority differs")


def _validate_identities(value: dict[str, Any]) -> None:
    member = cast(dict[str, Any], value["member"])
    case = cast(dict[str, Any], value["case"])
    if member.get("member_content_id") != member_content_id(member):
        _fail("content-identity", "member content identity differs")
    if case.get("case_content_id") != case_content_id(case):
        _fail("content-identity", "case content identity differs")
    if value.get("request_content_id") != request_content_id(value):
        _fail("content-identity", "request content identity differs")


def _validate_units_and_bounds(member: dict[str, Any], authority: dict[str, Any]) -> None:
    parameters = member["parameters"]
    declarations = authority["parameters"]
    if not isinstance(parameters, list) or len(parameters) != len(declarations):
        _fail("member-bounds", "member parameter inventory is incomplete")
    for supplied, declared in zip(parameters, declarations, strict=True):
        if not isinstance(supplied, dict) or set(supplied) != {"identity", "unit", "value"}:
            _fail("request-shape", "member parameter shape differs")
        if supplied["identity"] != declared["identity"]:
            _fail("member-bounds", "member parameter order or identity differs")
        if supplied["unit"] != declared["unit"]:
            _fail("units", f"unit differs for {declared['identity']}")
        value = supplied["value"]
        kind = declared["value_kind"]
        if kind == "boolean":
            if not isinstance(value, bool):
                _fail("member-bounds", f"{declared['identity']} must be boolean")
            if value != declared["anchor"]:
                _fail("member-bounds", f"{declared['identity']} fixed value differs")
            continue
        if kind == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                _fail("member-bounds", f"{declared['identity']} must be integer")
            lower = Decimal(declared["lower"])
            upper = Decimal(declared["upper"])
            candidate = Decimal(value)
        else:
            try:
                candidate = boundary._require_decimal(value)
                lower = boundary._require_decimal(declared["lower"])
                upper = boundary._require_decimal(declared["upper"])
            except boundary.GeneratorBoundaryError as error:
                _fail("member-bounds", str(error))
        if not lower <= candidate <= upper:
            _fail("member-bounds", f"{declared['identity']} is outside inclusive bounds")
        if declared["fixed"] and candidate != Decimal(declared["anchor"]):
            _fail("member-bounds", f"{declared['identity']} fixed value differs")
    if member["composites"] != authority["composites"]:
        _fail("member-bounds", "fixed composite inventory differs")


def _pump_head(values: dict[str, Decimal], flow: Decimal, obstruction: Decimal, clearance: Decimal) -> Decimal:
    ratio = flow / values["pump.Q_0"]
    return values["pump.H_0"] * (
        Decimal(1)
        - values["mechanism.a_o"] * obstruction
        - values["mechanism.a_c"] * clearance
        - (
            Decimal(1)
            + values["mechanism.b_o"] * obstruction
            + values["mechanism.b_c"] * clearance
        )
        * ratio
        * ratio
    )


def _system_head(values: dict[str, Decimal], flow: Decimal, depth: Decimal) -> Decimal:
    if flow == 0:
        return values["system.z_d"] - depth
    velocity = Decimal(4) * flow / (PI * values["system.D"] * values["system.D"])
    reynolds = values["fluid.rho"] * velocity * values["system.D"] / values["fluid.mu"]
    relative = values["system.epsilon"] / (Decimal("3.7") * values["system.D"])
    friction = Decimal("0.25") / (
        relative + Decimal("5.74") / (reynolds ** Decimal("0.9"))
    ).log10() ** 2
    velocity_head = velocity * velocity / (Decimal(2) * values["fluid.g"])
    return (
        values["system.z_d"]
        - depth
        + friction * (values["system.L"] / values["system.D"]) * velocity_head
        + values["system.K_minor"] * velocity_head
    )


def _operating_point(
    values: dict[str, Decimal],
    depth: Decimal,
    obstruction: Decimal = Decimal(0),
    clearance: Decimal = Decimal(0),
) -> Decimal:
    lower = Decimal(0)
    upper = values["pump.Q_0"]

    def residual(flow: Decimal) -> Decimal:
        return _pump_head(values, flow, obstruction, clearance) - _system_head(values, flow, depth)

    low_residual = residual(lower)
    high_residual = residual(upper)
    if low_residual <= 0 or high_residual >= 0:
        _fail("member-cross-constraint", "operating-point root is not strictly internal")
    for _ in range(160):
        midpoint = (lower + upper) / 2
        if residual(midpoint) > 0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2


def _validate_cross_constraints(member: dict[str, Any]) -> None:
    with localcontext() as context:
        context.prec = 34
        values = _parameter_values(member)
        levels = [values[f"well.{name}"] for name in ("h_stop", "h_start", "h_high", "h_overflow")]
        inflows = [values[f"inflow.{name}"] for name in ("Q_low", "Q_nominal", "Q_assess")]
        if not Decimal(0) < levels[0] < levels[1] < levels[2] < levels[3]:
            _fail("member-cross-constraint", "level ordering fails")
        if not Decimal(0) <= inflows[0] < inflows[1] < inflows[2]:
            _fail("member-cross-constraint", "inflow ordering fails")
        if values["pump.H_0"] <= values["system.z_d"] - values["well.h_stop"]:
            _fail("member-cross-constraint", "clean shutoff head does not exceed static head")
        clean_points = [_operating_point(values, depth) for depth in levels]
        for flow in clean_points:
            velocity = Decimal(4) * flow / (PI * values["system.D"] ** 2)
            reynolds = values["fluid.rho"] * velocity * values["system.D"] / values["fluid.mu"]
            if not Decimal(0) < flow < values["pump.Q_0"] or reynolds < values["system.Re_min"]:
                _fail("member-cross-constraint", "clean operating point leaves the accepted envelope")
        clean_assess = clean_points[1]
        if clean_assess <= values["inflow.Q_assess"]:
            _fail("member-cross-constraint", "clean assessment flow does not exceed inflow")
        area = PI * values["well.D_w"] ** 2 / 4
        working_volume = area * (values["well.h_start"] - values["well.h_stop"])
        drawdown = working_volume / (clean_assess - values["inflow.Q_assess"])
        if drawdown > values["capability.t_draw_limit"]:
            _fail("member-cross-constraint", "clean drawdown exceeds the capability limit")
        degraded = _operating_point(values, values["well.h_start"], Decimal(1), Decimal(1))
        degraded_net = degraded - values["inflow.Q_assess"]
        if degraded_net > 0 and working_volume / degraded_net <= values["capability.t_draw_limit"]:
            _fail("member-cross-constraint", "bounded degraded state does not cross the capability predicate")
        target_a = (Decimal("0.65"), Decimal("0.10"))
        target_flow = _operating_point(
            values,
            values["well.h_start"],
            target_a[0],
            target_a[1],
        )
        flow_ratio_squared = (target_flow / values["pump.Q_0"]) ** 2
        target_head_factor = (
            Decimal(1)
            - values["mechanism.a_o"] * target_a[0]
            - values["mechanism.a_c"] * target_a[1]
            - (
                Decimal(1)
                + values["mechanism.b_o"] * target_a[0]
                + values["mechanism.b_c"] * target_a[1]
            )
            * flow_ratio_squared
        )
        matched_clearance = (
            Decimal(1)
            - values["mechanism.a_o"] * Decimal("0.25")
            - (Decimal(1) + values["mechanism.b_o"] * Decimal("0.25")) * flow_ratio_squared
            - target_head_factor
        ) / (
            values["mechanism.a_c"]
            + values["mechanism.b_c"] * flow_ratio_squared
        )
        if not Decimal(0) <= matched_clearance <= Decimal(1):
            _fail("member-cross-constraint", "same-reading different-history witness leaves severity bounds")
        if values["resource.kit_lead"] <= 0 or values["resource.access_duration"] <= 0:
            _fail("member-cross-constraint", "resource constraint is not consequential")


def _validate_case(case: dict[str, Any], member: dict[str, Any], catalogue: dict[str, Any]) -> None:
    case_id = case.get("case_id")
    declaration = next((item for item in catalogue["cases"] if item["case_id"] == case_id), None)
    if declaration is None:
        _fail("case-authorization", f"case {case_id!r} is not allowlisted")
    expected = _materialize_case(declaration, member)
    if case != expected:
        _fail("case-authorization", f"case {case_id!r} differs from its exact catalogue declaration")


def read_request(
    raw: bytes,
    *,
    authority_bytes: bytes | None = None,
    catalogue_bytes: bytes | None = None,
    repair_bytes: bytes | None = None,
    solver_convergence_bytes: bytes | None = None,
) -> dict[str, Any]:
    """Validate a complete W2 request in the protocol's fail-closed order."""
    value = _read_canonical_object(raw, "request-bytes")
    _require_request_shape(value)
    _validate_authority(value["authority"])
    _validate_identities(value)
    authority_raw = _default_authority_path().read_bytes() if authority_bytes is None else authority_bytes
    catalogue_raw = _default_catalogue_path().read_bytes() if catalogue_bytes is None else catalogue_bytes
    repair_raw = (
        _default_mapping_repair_path().read_bytes()
        if repair_bytes is None
        else repair_bytes
    )
    solver_convergence_raw = (
        _default_solver_convergence_path().read_bytes()
        if solver_convergence_bytes is None
        else solver_convergence_bytes
    )
    try:
        authority = boundary.read_w1_declaration(authority_raw)
    except boundary.GeneratorBoundaryError as error:
        _fail("authority", str(error))
    read_mapping_repair(repair_raw)
    solver_convergence.read_amendment(solver_convergence_raw)
    member = cast(dict[str, Any], value["member"])
    _validate_units_and_bounds(member, authority)
    _validate_cross_constraints(member)
    catalogue = read_case_catalogue(catalogue_raw)
    _validate_case(cast(dict[str, Any], value["case"]), member, catalogue)
    if value["outputs"] != list(SERIES_OUTPUTS):
        _fail("case-authorization", "requested output allowlist differs")
    _engine_identity(value["engine"])
    return value
