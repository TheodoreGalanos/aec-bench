# ABOUTME: Constructs and checks W4 bound-selected members independently of generator and certifier code.
# ABOUTME: Retains invalid probes as deterministic precondition rejections instead of clamping or replacing them.

from __future__ import annotations

import hashlib
import json
from decimal import Decimal, localcontext
from typing import Any, NoReturn, cast

from sensitivity import catalogue

W1_DECLARATION_SHA256 = "4470e8af16bb6238a11045847199ffad95f1a7f57f64e85978a009bdda30ded9"
MEMBER_DOMAIN = b"asw-0b4.member.v1\0"
PROBE_RESULT_DOMAIN = b"asw-0b5.sensitivity-member.v1\0"
PI = Decimal("3.141592653589793238462643383279503")


class MemberProbeError(ValueError):
    """Fail-closed W4 member construction error."""


class MemberPreconditionError(ValueError):
    """Expected W1 cross-constraint rejection for a constructed probe."""


def _fail(detail: str) -> NoReturn:
    raise MemberProbeError(f"w4-member: {detail}")


def _canonical_object(raw: bytes) -> dict[str, Any]:
    if not raw.endswith(b"\n") or raw.endswith(b"\n\n") or b"\r" in raw:
        _fail("authority requires exactly one terminal LF")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        _fail(str(error))
    if not isinstance(value, dict):
        _fail("authority root is not an object")
    parsed = cast(dict[str, Any], value)
    if catalogue.canonical_json_bytes(parsed) != raw:
        _fail("authority bytes are not canonical")
    return parsed


def read_w1_authority(raw: bytes) -> dict[str, Any]:
    """Read the exact reviewed W1 member declaration."""
    authority = _canonical_object(raw)
    if hashlib.sha256(raw).hexdigest() != W1_DECLARATION_SHA256:
        _fail("W1 authority content identity differs")
    return authority


def member_content_id(member: dict[str, Any]) -> str:
    """Recompute the W1 member identity without trusting its declared value."""
    payload = {key: child for key, child in member.items() if key != "member_content_id"}
    return hashlib.sha256(MEMBER_DOMAIN + catalogue.canonical_json_bytes(payload)).hexdigest()


def member_values(member: dict[str, Any]) -> dict[str, Decimal]:
    """Return exact non-boolean member values."""
    values: dict[str, Decimal] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if not isinstance(value, bool):
            values[parameter["identity"]] = Decimal(str(value))
    return values


def build_member(
    authority: dict[str, Any],
    selections: dict[str, str],
) -> dict[str, Any]:
    """Build one exact anchor-or-bound member from W1 declarations."""
    declarations = {parameter["identity"]: parameter for parameter in authority["parameters"]}
    for identity, bound in selections.items():
        if identity not in declarations:
            _fail(f"unknown parameter {identity!r}")
        if declarations[identity]["fixed"]:
            _fail(f"fixed parameter {identity!r} cannot be selected")
        if bound not in {"lower", "anchor", "upper"}:
            _fail(f"unknown bound {bound!r}")
    parameters: list[dict[str, Any]] = []
    for declared in authority["parameters"]:
        identity = declared["identity"]
        selected = selections.get(identity, "anchor")
        parameters.append(
            {
                "identity": identity,
                "unit": declared["unit"],
                "value": declared[selected],
            }
        )
    member: dict[str, Any] = {
        "composites": authority["composites"],
        "member_content_id": "",
        "parameters": parameters,
    }
    member["member_content_id"] = member_content_id(member)
    return member


def _pump_head(
    values: dict[str, Decimal],
    flow: Decimal,
    obstruction: Decimal,
    clearance: Decimal,
) -> Decimal:
    ratio = flow / values["pump.Q_0"]
    return values["pump.H_0"] * (
        Decimal(1)
        - values["mechanism.a_o"] * obstruction
        - values["mechanism.a_c"] * clearance
        - (Decimal(1) + values["mechanism.b_o"] * obstruction + values["mechanism.b_c"] * clearance) * ratio * ratio
    )


def _system_head(
    values: dict[str, Decimal],
    flow: Decimal,
    depth: Decimal,
) -> Decimal:
    if flow == 0:
        return values["system.z_d"] - depth
    velocity = Decimal(4) * flow / (PI * values["system.D"] ** 2)
    reynolds = values["fluid.rho"] * velocity * values["system.D"] / values["fluid.mu"]
    friction = (
        Decimal("0.25")
        / (
            values["system.epsilon"] / (Decimal("3.7") * values["system.D"])
            + Decimal("5.74") / reynolds ** Decimal("0.9")
        ).log10()
        ** 2
    )
    velocity_head = velocity * velocity / (Decimal(2) * values["fluid.g"])
    return (
        values["system.z_d"]
        - depth
        + (friction * values["system.L"] / values["system.D"] + values["system.K_minor"]) * velocity_head
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
        return _pump_head(
            values,
            flow,
            obstruction,
            clearance,
        ) - _system_head(values, flow, depth)

    if residual(lower) <= 0 or residual(upper) >= 0:
        raise MemberPreconditionError("operating-point root is not strictly internal")
    for _ in range(160):
        midpoint = (lower + upper) / 2
        if residual(midpoint) > 0:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2


def validate_preconditions(member: dict[str, Any]) -> None:
    """Apply W1 ordering, root, Reynolds, capability, and witness constraints."""
    with localcontext() as context:
        context.prec = 34
        values = member_values(member)
        levels = [values[f"well.{name}"] for name in ("h_stop", "h_start", "h_high", "h_overflow")]
        inflows = [values[f"inflow.{name}"] for name in ("Q_low", "Q_nominal", "Q_assess")]
        if not Decimal(0) < levels[0] < levels[1] < levels[2] < levels[3]:
            raise MemberPreconditionError("level ordering fails")
        if not Decimal(0) <= inflows[0] < inflows[1] < inflows[2]:
            raise MemberPreconditionError("inflow ordering fails")
        if values["pump.H_0"] <= values["system.z_d"] - levels[0]:
            raise MemberPreconditionError("clean shutoff head is insufficient")
        clean_points = [_operating_point(values, depth) for depth in levels]
        for flow in clean_points:
            velocity = Decimal(4) * flow / (PI * values["system.D"] ** 2)
            reynolds = values["fluid.rho"] * velocity * values["system.D"] / values["fluid.mu"]
            if not Decimal(0) < flow < values["pump.Q_0"]:
                raise MemberPreconditionError("clean flow leaves pump support")
            if reynolds < values["system.Re_min"]:
                raise MemberPreconditionError("clean flow leaves Reynolds envelope")
        clean_assessment = clean_points[1]
        if clean_assessment <= values["inflow.Q_assess"]:
            raise MemberPreconditionError("clean assessment has no positive net flow")
        area = PI * values["well.D_w"] ** 2 / 4
        working_volume = area * (levels[1] - levels[0])
        drawdown = working_volume / (clean_assessment - values["inflow.Q_assess"])
        if drawdown > values["capability.t_draw_limit"]:
            raise MemberPreconditionError("clean drawdown exceeds capability limit")
        degraded = _operating_point(
            values,
            levels[1],
            Decimal(1),
            Decimal(1),
        )
        degraded_net = degraded - values["inflow.Q_assess"]
        if degraded_net > 0 and working_volume / degraded_net <= values["capability.t_draw_limit"]:
            raise MemberPreconditionError("bounded degraded state remains capable")
        target_flow = _operating_point(
            values,
            levels[1],
            Decimal("0.65"),
            Decimal("0.10"),
        )
        ratio_squared = (target_flow / values["pump.Q_0"]) ** 2
        target_factor = (
            Decimal(1)
            - values["mechanism.a_o"] * Decimal("0.65")
            - values["mechanism.a_c"] * Decimal("0.10")
            - (Decimal(1) + values["mechanism.b_o"] * Decimal("0.65") + values["mechanism.b_c"] * Decimal("0.10"))
            * ratio_squared
        )
        matched_clearance = (
            Decimal(1)
            - values["mechanism.a_o"] * Decimal("0.25")
            - (Decimal(1) + values["mechanism.b_o"] * Decimal("0.25")) * ratio_squared
            - target_factor
        ) / (values["mechanism.a_c"] + values["mechanism.b_c"] * ratio_squared)
        if not Decimal(0) <= matched_clearance <= Decimal(1):
            raise MemberPreconditionError("ambiguity witness leaves bounds")
        if values["resource.kit_lead"] <= 0 or values["resource.access_duration"] <= 0:
            raise MemberPreconditionError("resource constraint is immediate")


def _result_content_id(result: dict[str, Any]) -> str:
    payload = {key: child for key, child in result.items() if key != "result_content_id"}
    return hashlib.sha256(PROBE_RESULT_DOMAIN + catalogue.canonical_json_bytes(payload)).hexdigest()


def _probe_result(
    *,
    authority: dict[str, Any],
    case_ids: list[str],
    probe_id: str,
    selections: dict[str, str],
) -> dict[str, Any]:
    member = build_member(authority, selections)
    terminal_state = "probe-pass"
    first_failure = "none"
    try:
        validate_preconditions(member)
    except MemberPreconditionError as error:
        terminal_state = "probe-precondition-reject"
        first_failure = str(error)
    result: dict[str, Any] = {
        "case_ids": case_ids,
        "first_failure": first_failure,
        "member": member,
        "probe_id": probe_id,
        "promotable": False,
        "result_content_id": "",
        "terminal_state": terminal_state,
    }
    result["result_content_id"] = _result_content_id(result)
    return result


def build_oat_results(
    authority: dict[str, Any],
    probes: dict[str, Any],
) -> list[dict[str, Any]]:
    """Construct every lexical OAT member and retain its precondition outcome."""
    results: list[dict[str, Any]] = []
    for probe_id in probes["oat_probe_ids"]:
        stem, bound = probe_id.rsplit(".", 1)
        identity = stem.removeprefix("OAT.")
        results.append(
            _probe_result(
                authority=authority,
                case_ids=[],
                probe_id=probe_id,
                selections={identity: bound},
            )
        )
    return results


def build_interaction_results(
    authority: dict[str, Any],
    probes: dict[str, Any],
) -> list[dict[str, Any]]:
    """Construct every fixed interaction member in declared execution order."""
    return [
        _probe_result(
            authority=authority,
            case_ids=list(interaction["case_ids"]),
            probe_id=interaction["probe_id"],
            selections=dict(interaction["selections"]),
        )
        for interaction in probes["interactions"]
    ]
