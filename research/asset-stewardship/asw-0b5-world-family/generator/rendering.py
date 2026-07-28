# ABOUTME: Renders canonical W2 requests into exact ASCII SWMM inputs for their authorized engine segments.
# ABOUTME: Maps only W1 hydraulics and fixed engine settings, without certifying or promoting generated consequences.

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any

from generator import curves
from repairs import solver_convergence

ALLOWED_SECTIONS = (
    "TITLE",
    "OPTIONS",
    "OUTFALLS",
    "STORAGE",
    "INFLOWS",
    "PUMPS",
    "CURVES",
    "TIMESERIES",
    "REPORT",
)
SECTION_PATTERN = re.compile(rb"^\[([A-Z]+)\]$", re.MULTILINE)
HEAD_QUANTUM = Decimal("0.000000001")
FLOW_QUANTUM = Decimal("0.000001")


class RenderingError(ValueError):
    """Raised when an authorized W2 case cannot be rendered exactly."""


@dataclass(frozen=True)
class EngineConfiguration:
    """One bounded non-promotable engine diagnostic configuration."""

    curve_segments: int = 32
    report_step_s: int = 1
    routing_step_s: int = 1
    rule_step_s: int = 1
    target_mapping: str = "base"

    def __post_init__(self) -> None:
        if self.curve_segments not in {16, 32, 64}:
            raise RenderingError("diagnostic curve segment count differs")
        if (
            self.report_step_s,
            self.routing_step_s,
            self.rule_step_s,
        ) not in {
            (1, 1, 1),
            (2, 1, 1),
            (2, 2, 2),
        }:
            raise RenderingError("diagnostic engine step differs")
        if self.target_mapping not in {
            "base",
            "outfall-order-swap",
            "outfall-target-swap",
        }:
            raise RenderingError("diagnostic target mapping differs")


DEFAULT_ENGINE_CONFIGURATION = EngineConfiguration()


@dataclass(frozen=True)
class RenderedSegment:
    """One immutable input and curve identity set for a single SWMM execution."""

    horizon_s: int
    input_bytes: bytes
    input_sha256: str
    pump_a_engine_curve_bytes: bytes
    pump_a_engine_curve_sha256: str
    pump_a_original_curve_bytes: bytes
    pump_a_original_curve_sha256: str
    pump_b_engine_curve_bytes: bytes
    pump_b_engine_curve_sha256: str
    pump_b_original_curve_bytes: bytes
    pump_b_original_curve_sha256: str
    report_step_s: int
    routing_step_s: int
    segment_id: str
    selected_pump: str


def sha256_bytes(value: bytes) -> str:
    """Return the lower-case SHA-256 of exact bytes."""
    return hashlib.sha256(value).hexdigest()


def section_names(value: bytes) -> tuple[str, ...]:
    """Return SWMM section names in rendered order."""
    return tuple(match.group(1).decode("ascii") for match in SECTION_PATTERN.finditer(value))


def _member_values(member: dict[str, Any]) -> dict[str, Decimal]:
    result: dict[str, Decimal] = {}
    for parameter in member["parameters"]:
        value = parameter["value"]
        if isinstance(value, bool):
            continue
        result[parameter["identity"]] = Decimal(value) if isinstance(value, str) else Decimal(value)
    return result


def _head(value: Decimal) -> str:
    return format(value.quantize(HEAD_QUANTUM, rounding=ROUND_HALF_EVEN), ".9f")


def _flow_lps(value_m3_s: Decimal) -> str:
    return format((value_m3_s * 1000).quantize(FLOW_QUANTUM, rounding=ROUND_HALF_EVEN), ".6f")


def _time(seconds: int) -> str:
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _engine_end_time(horizon_s: int) -> str:
    with localcontext() as context:
        context.prec = 34
        decimal_hours = (
            Decimal(horizon_s) + Decimal("0.5")
        ) / Decimal(3600)
    return format(decimal_hours, "f")


def _curve_lines(name: str, points: tuple[curves.CurvePoint, ...]) -> list[str]:
    result: list[str] = []
    for index, point in enumerate(points):
        prefix = f"{name} PUMP3" if index == 0 else name
        result.append(f"{prefix} {format(point.head_m, '.9f')} {format(point.flow_lps, '.6f')}")
    return result


def _time_series_lines(
    *,
    stimulus: str,
    horizon_s: int,
    values: dict[str, Decimal],
) -> list[str]:
    points: tuple[tuple[int, Decimal], ...]
    if stimulus == "zero":
        points = ((0, Decimal(0)), (horizon_s, Decimal(0)))
    elif stimulus == "constant-assessment":
        assessment = values["inflow.Q_assess"]
        points = ((0, assessment), (horizon_s, assessment))
    elif stimulus == "base-pattern":
        points = (
            (0, values["inflow.Q_low"]),
            (5399, values["inflow.Q_low"]),
            (5400, values["inflow.Q_nominal"]),
            (10799, values["inflow.Q_nominal"]),
            (10800, values["inflow.Q_assess"]),
            (14399, values["inflow.Q_assess"]),
            (14400, values["inflow.Q_nominal"]),
            (21599, values["inflow.Q_nominal"]),
            (21600, values["inflow.Q_low"]),
            (28800, values["inflow.Q_low"]),
        )
    else:
        raise RenderingError(f"unsupported inflow stimulus {stimulus!r}")
    return [f"TS_IN {_time(second)} {_flow_lps(flow)}" for second, flow in points]


def _pump_rows(
    *,
    control_mode: str,
    selected_pump: str,
    target_mapping: str,
    values: dict[str, Decimal],
) -> list[str]:
    rows: list[str] = []
    mappings = (
        ("L_PA", "O_HGL_A", "C_EA", "pump-a"),
        ("L_PB", "O_HGL_B", "C_EB", "pump-b"),
    )
    if target_mapping == "outfall-target-swap":
        mappings = (
            ("L_PA", "O_HGL_B", "C_EA", "pump-a"),
            ("L_PB", "O_HGL_A", "C_EB", "pump-b"),
        )
    for pump_id, outfall_id, curve_id, label in mappings:
        status = "OFF"
        startup = Decimal(0)
        shutoff = Decimal(0)
        if control_mode == "automatic" and selected_pump == label:
            startup = values["well.h_start"]
            shutoff = values["well.h_stop"]
        elif control_mode == "forced-on" and selected_pump == label:
            status = "ON"
        rows.append(
            f"{pump_id} WW_B4 {outfall_id} {curve_id} {status} "
            f"{_head(startup)} {_head(shutoff)}"
        )
    return rows


def _render_segment(
    request: dict[str, Any],
    *,
    segment_id: str,
    selected_pump: str,
    horizon_s: int,
    initial_depth: Decimal,
    pump_a_state: dict[str, str],
    pump_b_state: dict[str, str],
    configuration: EngineConfiguration,
) -> RenderedSegment:
    member = request["member"]
    case = request["case"]
    values = _member_values(member)
    pump_a_original_curve = curves.materialize(
        member,
        obstruction=pump_a_state["obstruction"],
        clearance_loss=pump_a_state["clearance-loss"],
    )
    pump_b_original_curve = curves.materialize(
        member,
        obstruction=pump_b_state["obstruction"],
        clearance_loss=pump_b_state["clearance-loss"],
    )
    pump_a_engine_curve = curves.materialize_net_head(
        member,
        obstruction=pump_a_state["obstruction"],
        clearance_loss=pump_a_state["clearance-loss"],
        segment_count=configuration.curve_segments,
    )
    pump_b_engine_curve = curves.materialize_net_head(
        member,
        obstruction=pump_b_state["obstruction"],
        clearance_loss=pump_b_state["clearance-loss"],
        segment_count=configuration.curve_segments,
    )
    end_time = _engine_end_time(horizon_s)
    control_mode = case["control_mode"]
    if control_mode == "transfer":
        control_mode = "forced-on"
    if control_mode == "forced-off":
        selected_pump = "none"
    outfall_rows = [
        f"O_HGL_A {_head(Decimal(0))} FIXED {_head(values['system.z_d'])} NO",
        f"O_HGL_B {_head(Decimal(0))} FIXED {_head(values['system.z_d'])} NO",
    ]
    if configuration.target_mapping == "outfall-order-swap":
        outfall_rows.reverse()
    sections: list[tuple[str, list[str]]] = [
        (
            "TITLE",
            [
                f"{request['authority']['profile_id']} {case['case_id']} {request['request_content_id']}",
            ],
        ),
        (
            "OPTIONS",
            [
                "FLOW_UNITS LPS",
                "FLOW_ROUTING DYNWAVE",
                "LINK_OFFSETS DEPTH",
                "FORCE_MAIN_EQUATION D-W",
                "IGNORE_RAINFALL YES",
                "SKIP_STEADY_STATE NO",
                "START_DATE 01/01/2002",
                "START_TIME 00:00:00",
                "REPORT_START_DATE 01/01/2002",
                "REPORT_START_TIME 00:00:00",
                "END_DATE 01/01/2002",
                f"END_TIME {end_time}",
                f"REPORT_STEP {_time(configuration.report_step_s)}",
                f"WET_STEP {_time(configuration.routing_step_s)}",
                f"DRY_STEP {_time(configuration.routing_step_s)}",
                f"ROUTING_STEP {_time(configuration.routing_step_s)}",
                f"RULE_STEP {_time(configuration.rule_step_s)}",
                "ALLOW_PONDING NO",
                "VARIABLE_STEP 0.00",
                (
                    "HEAD_TOLERANCE "
                    f"{solver_convergence.HEAD_TOLERANCE_M}"
                ),
                f"MAX_TRIALS {solver_convergence.MAX_TRIALS}",
                "THREADS 1",
            ],
        ),
        (
            "OUTFALLS",
            outfall_rows,
        ),
        (
            "STORAGE",
            [
                (
                    f"WW_B4 {_head(Decimal(0))} {_head(values['well.h_overflow'])} "
                    f"{_head(initial_depth)} CYLINDRICAL {_head(values['well.D_w'])} "
                    f"{_head(values['well.D_w'])} {_head(Decimal(0))} "
                    f"{_head(Decimal(0))} {_head(Decimal(0))}"
                )
            ],
        ),
        (
            "INFLOWS",
            ["WW_B4 FLOW TS_IN FLOW 1.000000000 1.000000000 0.000000"],
        ),
        (
            "PUMPS",
            _pump_rows(
                control_mode=control_mode,
                selected_pump=selected_pump,
                target_mapping=configuration.target_mapping,
                values=values,
            ),
        ),
        (
            "CURVES",
            [
                *_curve_lines("C_EA", pump_a_engine_curve),
                *_curve_lines("C_EB", pump_b_engine_curve),
            ],
        ),
        (
            "TIMESERIES",
            _time_series_lines(
                stimulus=case["inflow_stimulus"],
                horizon_s=horizon_s,
                values=values,
            ),
        ),
        (
            "REPORT",
            [
                "INPUT NO",
                "CONTROLS NO",
                "AVERAGES NO",
                "SUBCATCHMENTS NONE",
                "NODES WW_B4 O_HGL_A O_HGL_B",
                "LINKS L_PA L_PB",
            ],
        ),
    ]
    lines: list[str] = []
    for index, (section, body) in enumerate(sections):
        if index:
            lines.append("")
        lines.append(f"[{section}]")
        lines.extend(body)
    input_bytes = ("\n".join(lines) + "\n").encode("ascii")
    if section_names(input_bytes) != ALLOWED_SECTIONS:
        raise RenderingError("rendered section set or order differs")
    if b"\t" in input_bytes or b"\r" in input_bytes or input_bytes.endswith(b"\n\n"):
        raise RenderingError("rendered bytes violate the ASCII line profile")
    if any(line.endswith(b" ") for line in input_bytes.splitlines()):
        raise RenderingError("rendered line has trailing whitespace")
    return RenderedSegment(
        horizon_s=horizon_s,
        input_bytes=input_bytes,
        input_sha256=sha256_bytes(input_bytes),
        pump_a_engine_curve_bytes=curves.canonical_net_head_curve_bytes(
            pump_a_engine_curve
        ),
        pump_a_engine_curve_sha256=curves.net_head_curve_sha256(
            pump_a_engine_curve
        ),
        pump_a_original_curve_bytes=curves.canonical_curve_bytes(
            pump_a_original_curve
        ),
        pump_a_original_curve_sha256=curves.curve_sha256(
            pump_a_original_curve
        ),
        pump_b_engine_curve_bytes=curves.canonical_net_head_curve_bytes(
            pump_b_engine_curve
        ),
        pump_b_engine_curve_sha256=curves.net_head_curve_sha256(
            pump_b_engine_curve
        ),
        pump_b_original_curve_bytes=curves.canonical_curve_bytes(
            pump_b_original_curve
        ),
        pump_b_original_curve_sha256=curves.curve_sha256(
            pump_b_original_curve
        ),
        report_step_s=configuration.report_step_s,
        routing_step_s=configuration.routing_step_s,
        segment_id=segment_id,
        selected_pump=selected_pump,
    )


def render_case(
    request: dict[str, Any],
    *,
    carried_depth_m: str | None = None,
    configuration: EngineConfiguration = DEFAULT_ENGINE_CONFIGURATION,
) -> tuple[RenderedSegment, ...]:
    """Expand one authorized case into its exact independent SWMM segments."""
    case = request["case"]
    values = _member_values(request["member"])
    initial = (
        values["well.h_stop"]
        if case["initial_depth_source"] == "well.h_stop"
        else values["well.h_start"]
    )
    pump_a_state = case["mechanism_state"]["pump-a"]
    pump_b_state = case["mechanism_state"]["pump-b"]
    if case["family"] == "transfer-sequence":
        segment_a = _render_segment(
            request,
            segment_id="segment-a",
            selected_pump="pump-a",
            horizon_s=60,
            initial_depth=initial,
            pump_a_state=pump_a_state,
            pump_b_state=pump_b_state,
            configuration=configuration,
        )
        if carried_depth_m is None:
            return (segment_a,)
        return (
            segment_a,
            _render_segment(
                request,
                segment_id="segment-b",
                selected_pump="pump-b",
                horizon_s=60,
                initial_depth=Decimal(carried_depth_m),
                pump_a_state=pump_a_state,
                pump_b_state=pump_b_state,
                configuration=configuration,
            ),
        )
    if case["family"] == "progression-checkpoints":
        return tuple(
            _render_segment(
                request,
                segment_id=f"checkpoint-{checkpoint['checkpoint_index']}",
                selected_pump="pump-a",
                horizon_s=case["horizon_s"],
                initial_depth=initial,
                pump_a_state=checkpoint["mechanism_state"],
                pump_b_state=pump_b_state,
                configuration=configuration,
            )
            for checkpoint in case["checkpoints"]
        )
    return (
        _render_segment(
            request,
            segment_id="single",
            selected_pump=case["selected_pump"],
            horizon_s=case["horizon_s"],
            initial_depth=initial,
            pump_a_state=pump_a_state,
            pump_b_state=pump_b_state,
            configuration=configuration,
        ),
    )
