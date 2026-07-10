# ABOUTME: Engine for the SSC-01 review-first road low-point issue review package.
# ABOUTME: Derives packet state, variant gold review statuses, source-pack files, and golden fixtures.

from __future__ import annotations

import json
import math

_G = 9.81
_GUTTER_KU_SI = 0.376
_FT_TO_M = 0.3048
_LEGIBILITY_FT_PER_IN = 40.0

STATUS_PASS = 0.0
STATUS_FAIL = 1.0
STATUS_NOT_APPLICABLE = 2.0
STATUS_INSUFFICIENT_DATA = 3.0

READY = 0.0
READY_WITH_CARRIED_ACTIONS = 1.0
NOT_READY = 2.0

_STATUS_NAMES = {
    STATUS_PASS: "pass",
    STATUS_FAIL: "fail",
    STATUS_NOT_APPLICABLE: "not_applicable",
    STATUS_INSUFFICIENT_DATA: "insufficient_data",
}

_READINESS_NAMES = {
    READY: "ready_to_issue",
    READY_WITH_CARRIED_ACTIONS: "ready_with_carried_actions",
    NOT_READY: "not_ready_to_issue",
}

# Quantization grid: every sampled float is snapped to a reporting precision before
# any derivation so the source files carry exactly the values the engine used.
_QUANT_STEPS = {
    "runoff_coefficient": 0.01,
    "rainfall_intensity_mm_h": 0.1,
    "catchment_area_ha": 0.01,
    "upstream_bypass_flow_m3_s": 0.005,
    "cross_slope_pct": 0.1,
    "longitudinal_slope_pct": 0.1,
    "gutter_mannings_n": 0.001,
    "road_low_point_level_m": 0.005,
    "allowable_spread_margin_m": 0.05,
    "inlet_efficiency": 0.01,
    "inlet_capture_capacity_m3_s": 0.005,
    "pipe_length_m": 0.5,
    "pipe_mannings_n": 0.0005,
    "pit_loss_coefficient": 0.1,
    "hgl_clearance_target_m": 0.05,
    "minimum_cabinet_freeboard_m": 0.05,
    "cabinet_freeboard_margin_m": 0.01,
    "cabinet_freeboard_deficit_m": 0.01,
    "vms_message_margin_chars_target": 0.5,
    "reading_rate_chars_s": 0.5,
    "camera_data_rate_mbps": 0.5,
    "vms_data_rate_mbps": 0.1,
    "controller_data_rate_mbps": 0.05,
    "sensor_data_rate_mbps": 0.05,
    "network_overhead_pct": 1.0,
    "future_capacity_buffer_pct": 1.0,
    "network_headroom_margin_mbps": 0.5,
    "battery_efficiency": 0.01,
    "critical_load_w": 5.0,
    "battery_runtime_margin_h": 0.1,
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid, avoiding float dust."""
    return round(round(value / step) * step, 10)


def _ceil_to(value: float, step: float) -> float:
    """Round a value up to the next step boundary."""
    return round(math.ceil(value / step - 1e-9) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with floats snapped to grid and numeric enums cast."""
    quantized = dict(params)
    for name, step in _QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    for enum_name in ("pipe_diameter_mm", "road_design_speed_kmh", "vms_character_height_in", "required_autonomy_h"):
        quantized[enum_name] = float(params[enum_name])
    quantized["camera_count"] = int(params["camera_count"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    """Compute the full packet state: true metrics, derived criteria, and claims."""
    p = _quantize(raw_params)
    variant = p["packet_variant"]

    # Drainage: rational method and HEC-22 triangular gutter spread.
    peak_runoff = p["runoff_coefficient"] * p["rainfall_intensity_mm_h"] * p["catchment_area_ha"] / 360.0
    approach_flow = peak_runoff + p["upstream_bypass_flow_m3_s"]
    sx = p["cross_slope_pct"] / 100.0
    sl = p["longitudinal_slope_pct"] / 100.0
    n_gutter = p["gutter_mannings_n"]
    spread = (approach_flow * n_gutter / (_GUTTER_KU_SI * sx ** (5.0 / 3.0) * math.sqrt(sl))) ** (3.0 / 8.0)
    curb_depth = spread * sx
    allowable_spread = _ceil_to(spread + p["allowable_spread_margin_m"], 0.25)

    # Inlet and full-pipe HGL reach.
    intercepted = min(approach_flow * p["inlet_efficiency"], p["inlet_capture_capacity_m3_s"])
    diameter_m = p["pipe_diameter_mm"] / 1000.0
    area = math.pi * diameter_m**2 / 4.0
    hydraulic_radius = diameter_m / 4.0
    velocity = intercepted / area
    n_pipe = p["pipe_mannings_n"]
    friction_slope = (velocity * n_pipe / hydraulic_radius ** (2.0 / 3.0)) ** 2
    hgl_rise = friction_slope * p["pipe_length_m"] + p["pit_loss_coefficient"] * velocity**2 / (2.0 * _G)
    low_point = p["road_low_point_level_m"]
    tailwater = _q(low_point - p["hgl_clearance_target_m"] - hgl_rise, 0.005)
    upstream_hgl = tailwater + hgl_rise
    pavement_water_level = low_point + curb_depth
    controlling_level = max(pavement_water_level, upstream_hgl)

    # Cabinet pad: derivation-controlled so clean passes and the deficient variant fails.
    min_freeboard = p["minimum_cabinet_freeboard_m"]
    if variant == "freeboard_deficient":
        pad_level = _q(controlling_level + min_freeboard - p["cabinet_freeboard_deficit_m"], 0.005)
    else:
        pad_level = _q(controlling_level + min_freeboard + p["cabinet_freeboard_margin_m"], 0.005)
    cabinet_freeboard = pad_level - controlling_level

    # VMS legibility at the corridor's true design speed.
    design_speed = p["road_design_speed_kmh"]
    legibility_m = p["vms_character_height_in"] * _LEGIBILITY_FT_PER_IN * _FT_TO_M
    reading_time = legibility_m / (design_speed / 3.6)
    readable_chars = reading_time * p["reading_rate_chars_s"]
    message_length = max(8, math.floor(readable_chars - p["vms_message_margin_chars_target"]))
    message_margin = readable_chars - message_length
    copied_speed = design_speed + 20.0
    copied_reading_time = legibility_m / (copied_speed / 3.6)

    # Network load and provisioned uplink.
    base_load = (
        p["camera_count"] * p["camera_data_rate_mbps"]
        + p["vms_data_rate_mbps"]
        + p["controller_data_rate_mbps"]
        + p["sensor_data_rate_mbps"]
    )
    required_load = (
        base_load * (1.0 + p["network_overhead_pct"] / 100.0) * (1.0 + p["future_capacity_buffer_pct"] / 100.0)
    )
    uplink = _ceil_to(required_load + p["network_headroom_margin_mbps"], 5.0)
    network_headroom = uplink - required_load

    # Battery: provision capacity so runtime clears the required autonomy.
    autonomy = p["required_autonomy_h"]
    load_kw = p["critical_load_w"] / 1000.0
    runtime_target = autonomy + p["battery_runtime_margin_h"]
    battery_capacity = _ceil_to(runtime_target * load_kw / p["battery_efficiency"], 0.1)
    battery_runtime = battery_capacity * p["battery_efficiency"] / load_kw

    # Package claims (what the drainage/equipment files assert).
    stale_tailwater = _q(tailwater - 0.3, 0.005)
    claimed_upstream_hgl = (stale_tailwater + hgl_rise) if variant == "stale_hgl_revision" else upstream_hgl
    if variant == "freeboard_deficient":
        claimed_freeboard = pad_level - low_point  # wrong method: ignores the controlling water level
    else:
        claimed_freeboard = cabinet_freeboard

    return {
        "params": p,
        "variant": variant,
        "peak_runoff": peak_runoff,
        "approach_flow": approach_flow,
        "spread": spread,
        "curb_depth": curb_depth,
        "allowable_spread": allowable_spread,
        "intercepted": intercepted,
        "velocity": velocity,
        "hgl_rise": hgl_rise,
        "tailwater": tailwater,
        "stale_tailwater": stale_tailwater,
        "upstream_hgl": upstream_hgl,
        "claimed_upstream_hgl": claimed_upstream_hgl,
        "pavement_water_level": pavement_water_level,
        "controlling_level": controlling_level,
        "pad_level": pad_level,
        "min_freeboard": min_freeboard,
        "cabinet_freeboard": cabinet_freeboard,
        "claimed_freeboard": claimed_freeboard,
        "design_speed": design_speed,
        "copied_speed": copied_speed,
        "legibility_m": legibility_m,
        "reading_time": reading_time,
        "copied_reading_time": copied_reading_time,
        "readable_chars": readable_chars,
        "message_length": message_length,
        "message_margin": message_margin,
        "base_load": base_load,
        "required_load": required_load,
        "uplink": uplink,
        "network_headroom": network_headroom,
        "autonomy": autonomy,
        "battery_capacity": battery_capacity,
        "battery_runtime": battery_runtime,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_cabinet_level": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_hgl_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "chainage_datum_mismatch": {
        "flips": {"rlr_02_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "scenario_copy_forward": {
        "flips": {"rlr_05_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "open_critical_comment": {
        "flips": {"rlr_07_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "minor_open_comment_carried": {
        "flips": {},
        "readiness": READY_WITH_CARRIED_ACTIONS,
        "findings": 0.0,
        "requests": 0.0,
        "carried": 1.0,
    },
    "freeboard_deficient": {
        "flips": {"rlr_04_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}


def compute(**params) -> dict[str, float]:
    """Return the gold review state and evidence metrics for one packet instance."""
    state = _derive(params)
    gold = _VARIANT_GOLD[state["variant"]]

    result: dict[str, float] = {}
    for index in range(1, 10):
        key = f"rlr_0{index}_status"
        result[key] = gold["flips"].get(key, STATUS_PASS)
    result["readiness_code"] = gold["readiness"]
    result["required_findings_count"] = gold["findings"]
    result["required_information_requests_count"] = gold["requests"]
    result["required_carried_actions_count"] = gold["carried"]

    result["peak_runoff_m3_s"] = state["peak_runoff"]
    result["gutter_approach_flow_m3_s"] = state["approach_flow"]
    result["spread_width_m"] = state["spread"]
    result["allowable_spread_m"] = state["allowable_spread"]
    result["controlling_water_level_m"] = state["controlling_level"]
    if state["variant"] != "missing_cabinet_level":
        result["cabinet_freeboard_m"] = state["cabinet_freeboard"]
    result["vms_message_margin_chars"] = state["message_margin"]
    result["battery_runtime_h"] = state["battery_runtime"]
    result["network_headroom_mbps"] = state["network_headroom"]
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    drainage_rev = "Rev C"  # the register always lists the current drainage revision
    return [
        ("RD-SSC01-001", "Road geometry and corridor profile", "Rev B", "Issued for review"),
        ("DRN-SSC01-DES-01", "Low-point drainage design package", drainage_rev, "Issued for review"),
        ("ITS-SSC01-LAY-01", "Field equipment layout and levels", "Rev A", "Issued for review"),
        ("PWR-SSC01-SCH-01", "Power, battery, and network schedule", "Rev A", "Issued for review"),
        ("TOPS-SSC01-CASE-01", "Traffic operations case and VMS basis", "Rev A", "Issued for review"),
        ("CRIT-SSC01-001", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the seven-file source packet for one instance."""
    s = _derive(all_params)
    p = s["params"]
    variant = s["variant"]

    register_lines = [
        "| Document ID | Title | Revision | Status |",
        "|---|---|---|---|",
    ]
    for doc_id, title, rev, status in _register_rows(variant):
        register_lines.append(f"| {doc_id} | {title} | {rev} | {status} |")
    document_register = (
        "# Document Register — DOC-REG-SSC01-01\n\n"
        "Issue package: road low-point resilience, corridor RD-SSC01-001.\n\n"
        + "\n".join(register_lines)
        + "\n\nAll levels in this package are quoted in metres AHD unless a document states otherwise.\n"
    )

    road_geometry = f"""# Road Geometry — RD-SSC01-001 (Rev B)

Corridor: RD-SSC01-001, chainage CH 0+000 to CH 2+400, levels in metres AHD.

| Item | Value |
|---|---|
| Sag low point | LP-01 at CH 1+240 |
| LP-01 pavement level | {p["road_low_point_level_m"]:.3f} m AHD |
| Pavement crossfall at LP-01 | {p["cross_slope_pct"]:.1f} % |
| Approach longitudinal slope | {p["longitudinal_slope_pct"]:.1f} % |
| Design speed | {s["design_speed"]:.0f} km/h |

The approach gutter is a triangular kerb-and-channel section (DRN-GUT-01).
"""

    drainage_rev_header = "Rev B" if variant == "stale_hgl_revision" else "Rev C"
    stale_note = ""
    if variant == "stale_hgl_revision":
        stale_note = (
            "\nTailwater basis: downstream advice TW-2024-11 "
            f"(tailwater {s['stale_tailwater']:.3f} m AHD). "
            "Note: TW-2024-11 was superseded by TW-2025-02 after this revision.\n"
        )
    else:
        stale_note = f"\nTailwater basis: downstream advice TW-2025-02 (tailwater {s['tailwater']:.3f} m AHD).\n"

    drainage_package = f"""# Drainage Design Package — DRN-SSC01-DES-01 ({drainage_rev_header})

Design storm: STORM-01 (10-year burst). Catchment DRN-CAT-01 drains to low-point inlet DRN-PIT-01 at LP-01.

## Source values

| Item | Value |
|---|---|
| Runoff coefficient C (DRN-CAT-01) | {p["runoff_coefficient"]:.2f} |
| Rainfall intensity I (STORM-01) | {p["rainfall_intensity_mm_h"]:.1f} mm/h |
| Catchment area A (DRN-CAT-01) | {p["catchment_area_ha"]:.2f} ha |
| Upstream bypass flow (DRN-BYP-01) | {p["upstream_bypass_flow_m3_s"]:.3f} m3/s |
| Gutter Manning n (DRN-GUT-01) | n = {p["gutter_mannings_n"]:.3f} |
| Inlet interception efficiency (DRN-PIT-01) | {p["inlet_efficiency"]:.2f} |
| Inlet capture capacity (DRN-PIT-01) | {p["inlet_capture_capacity_m3_s"]:.3f} m3/s |
| Pipe diameter (DRN-PIPE-01) | {p["pipe_diameter_mm"]:.0f} mm |
| Pipe length (DRN-PIPE-01) | {p["pipe_length_m"]:.1f} m |
| Pipe Manning n (DRN-PIPE-01) | n = {p["pipe_mannings_n"]:.4f} |
| Pit loss coefficient K (HGL-01) | {p["pit_loss_coefficient"]:.1f} |
{stale_note}
## Package results (as designed)

| Item | Claimed value |
|---|---|
| Peak runoff | {s["peak_runoff"]:.3f} m3/s |
| Gutter approach flow | {s["approach_flow"]:.3f} m3/s |
| Gutter spread at LP-01 | {s["spread"]:.3f} m |
| Upstream HGL at DRN-PIT-01 (HGL-01) | {s["claimed_upstream_hgl"]:.3f} m AHD |
| Controlling water level at LP-01 | {s["controlling_level"]:.3f} m AHD |
"""

    if variant == "missing_cabinet_level":
        pad_line = "| CAB-01 pad level | pending survey verification |"
        freeboard_line = "| CAB-01 flood freeboard | to be confirmed after survey |"
    else:
        pad_line = f"| CAB-01 pad level | {s['pad_level']:.3f} m AHD |"
        verdict = "adequate" if variant != "missing_cabinet_level" else ""
        freeboard_line = f"| CAB-01 assessed flood freeboard | {s['claimed_freeboard']:.3f} m — {verdict} |"

    datum_note = "Levels in this layout are quoted in metres AHD."
    if variant == "chainage_datum_mismatch":
        datum_note = (
            "Levels in this layout are quoted in site datum (site datum = AHD + 0.350 m).\n"
            "Footer note: all levels herein are AHD."
        )

    field_equipment = f"""# Field Equipment Layout — ITS-SSC01-LAY-01 (Rev A)

| Item | Value |
|---|---|
| Field cabinet | CAB-01 at CH 1+238 |
{pad_line}
{freeboard_line}
| Variable message sign | VMS-01 at CH 1+180 (approach side) |
| VMS-01 character height | {p["vms_character_height_in"]:.0f} in |
| Water-level sensor | WLS-01 at DRN-PIT-01 |

{datum_note}
"""

    power_comms = f"""# Power And Network Schedule — PWR-SSC01-SCH-01 (Rev A)

## Battery (BATT-01)

| Item | Value |
|---|---|
| Battery capacity | {s["battery_capacity"]:.1f} kWh |
| Usable-energy efficiency | {p["battery_efficiency"]:.2f} |
| CAB-01 critical load | {p["critical_load_w"]:.0f} W |

## Network operating case (ITS-NET-01)

| Item | Value |
|---|---|
| CCTV cameras | {p["camera_count"]} |
| Data rate per camera | {p["camera_data_rate_mbps"]:.1f} Mbps |
| VMS-01 data rate | {p["vms_data_rate_mbps"]:.1f} Mbps |
| Controller data rate | {p["controller_data_rate_mbps"]:.2f} Mbps |
| Water-level sensor data rate | {p["sensor_data_rate_mbps"]:.2f} Mbps |
| Protocol overhead allowance | {p["network_overhead_pct"]:.0f} % |
| Future capacity buffer | {p["future_capacity_buffer_pct"]:.0f} % |
| Provisioned uplink | {s["uplink"]:.1f} Mbps |
"""

    if variant == "scenario_copy_forward":
        speed_basis = (
            f"| Assessment speed | {s['copied_speed']:.0f} km/h (adopted from the Corridor B VMS assessment) |\n"
            f"| Claimed reading time | {s['copied_reading_time']:.2f} s |"
        )
    else:
        speed_basis = (
            f"| Assessment speed | {s['design_speed']:.0f} km/h (RD-SSC01-001 design speed) |\n"
            f"| Claimed reading time | {s['reading_time']:.2f} s |"
        )

    traffic_operations = f"""# Traffic Operations Case — TOPS-SSC01-CASE-01 (Rev A)

Operating case: water over road at LP-01, single-lane closure with VMS-01 advisory message.

| Item | Value |
|---|---|
{speed_basis}
| Driver reading rate | {p["reading_rate_chars_s"]:.1f} chars/s |
| Selected message (MSG-01) length | {s["message_length"]} characters |

Storm case for this operating scenario: STORM-01.
"""

    comments = [
        ("C-01", "Drainage", "Confirm inlet blockage allowance at DRN-PIT-01.", "Closed", "minor", "", ""),
        ("C-02", "Electrical", "Confirm BATT-01 sizing basis for CAB-01 load.", "Closed", "minor", "", ""),
        ("C-03", "Traffic", "Confirm MSG-01 legibility basis.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        comments.append(
            (
                "C-04",
                "Authority",
                "Verify flood immunity of the CAB-01 power supply for the STORM-01 event.",
                "Open",
                "critical",
                "",
                "",
            )
        )
    if variant == "minor_open_comment_carried":
        comments.append(
            (
                "C-05",
                "Documentation",
                "Update the legend on ITS-SSC01-LAY-01 to show WLS-01.",
                "Open",
                "minor",
                "ITS designer",
                "Update legend at next revision (carried action, due next issue)",
            )
        )

    comment_lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    for cid, disc, text, status, crit, owner, action in comments:
        comment_lines.append(f"| {cid} | {disc} | {text} | {status} | {crit} | {owner} | {action} |")

    criteria_comments = f"""# Criteria Memo And Review Comments — CRIT-SSC01-001 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Allowable gutter spread at LP-01 | {s["allowable_spread"]:.2f} m |
| Minimum CAB-01 flood freeboard above the controlling water level | {s["min_freeboard"]:.2f} m |
| Required CAB-01 battery autonomy | {s["autonomy"]:.0f} h |
| Network headroom on the provisioned uplink | greater than 0 Mbps |
| VMS message margin | greater than 0 characters |

## Assessment bases (source-owned methods)

- Peak runoff: Rational Method, Q = C x I x A / 360 (SI, m3/s).
- Gutter spread: HEC-22 triangular gutter relation, Q = (0.376/n) x Sx^(5/3) x SL^(1/2) x T^(8/3) (SI).
- Pipe friction: Manning full-pipe flow; friction slope Sf = (V x n / R^(2/3))^2; pit loss K x V^2 / (2g).
- Controlling water level: greater of the ponded pavement level (LP-01 plus curb depth T x Sx) and the upstream HGL.
- VMS legibility: {_LEGIBILITY_FT_PER_IN:.0f} ft per inch of character height; reading time at the assessment speed.
- Battery runtime: capacity x efficiency / critical load.
- Network demand: device loads factored by protocol overhead and future capacity buffer.

## Review comments

{chr(10).join(comment_lines)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/road-geometry.md": road_geometry,
        "sources/drainage-package.md": drainage_package,
        "sources/field-equipment.md": field_equipment,
        "sources/power-comms.md": power_comms,
        "sources/traffic-operations.md": traffic_operations,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_hgl_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "DRN-SSC01-DES-01",
        "object_id": "HGL-01",
        "consequence": (
            "The HGL and tailwater basis cite superseded advice TW-2024-11 and a stale revision, "
            "so the drainage basis is not traceable to the current package."
        ),
        "action": "Reissue DRN-SSC01-DES-01 at Rev C using tailwater advice TW-2025-02 and reconcile HGL-01.",
    },
    "chainage_datum_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "ITS-SSC01-LAY-01",
        "object_id": "CAB-01",
        "consequence": (
            "The equipment layout quotes contradictory datums (site datum AHD +0.350 m versus AHD), "
            "so the CAB-01 pad level cannot be tied to the drainage levels."
        ),
        "action": "Confirm the datum of ITS-SSC01-LAY-01 levels and reissue with a single AHD basis.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "TOPS-SSC01-CASE-01",
        "object_id": "VMS-01",
        "consequence": (
            "The VMS legibility case adopts a Corridor B assessment speed instead of the RD-SSC01-001 "
            "design speed, without a case-selection record."
        ),
        "action": "Reassess MSG-01 legibility at the RD-SSC01-001 design speed and record the case selection.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC01-001",
        "object_id": "C-04",
        "consequence": (
            "Critical authority comment C-04 on CAB-01 flood immunity is open with no owner or agreed action."
        ),
        "action": "Assign an owner and closure path for C-04 before issue.",
    },
    "freeboard_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "ITS-SSC01-LAY-01",
        "object_id": "CAB-01",
        "consequence": (
            "Recomputed freeboard from the CAB-01 pad level to the controlling water level is below the "
            "CRIT-SSC01-001 minimum; the package claim ignores the controlling water level."
        ),
        "action": "Raise the CAB-01 pad or relocate the cabinet to restore the required freeboard.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    """Build the fully correct structured review answer for this instance."""
    state = _derive(all_params)
    variant = state["variant"]

    matrix = {}
    evidence_notes = {
        "RLR-01": "All six register documents are present with IDs and revisions (DOC-REG-SSC01-01).",
        "RLR-02": "Chainage CH 1+240 (LP-01), CH 1+238 (CAB-01), and AHD datum reconcile across sources.",
        "RLR-03": "Recomputed runoff, approach flow, and spread reconcile with DRN-SSC01-DES-01 and STORM-01.",
        "RLR-04": "Recomputed CAB-01 freeboard against the controlling water level meets CRIT-SSC01-001.",
        "RLR-05": "MSG-01 legibility uses the RD-SSC01-001 design speed and clears the message margin.",
        "RLR-06": "BATT-01 runtime and ITS-NET-01 headroom are source-backed and clear the criteria.",
        "RLR-07": "All review comments in CRIT-SSC01-001 are closed or carried with owner and action.",
        "RLR-08": "The readiness decision reconciles with the matrix, findings, and action register.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        failed_item = _VARIANT_FINDINGS[variant]["item"]
        evidence_notes[failed_item] = _VARIANT_FINDINGS[variant]["consequence"]
    if variant == "missing_cabinet_level":
        evidence_notes["RLR-04"] = (
            "The CAB-01 pad level is pending survey verification, so exposure cannot be assessed."
        )

    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        code = ground_truth[f"rlr_0{index}_status"]
        matrix[item_id] = {"status": _STATUS_NAMES[code], "evidence": evidence_notes[item_id]}

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "peak_runoff_m3_s",
            "gutter_approach_flow_m3_s",
            "spread_width_m",
            "allowable_spread_m",
            "controlling_water_level_m",
            "cabinet_freeboard_m",
            "vms_message_margin_chars",
            "battery_runtime_h",
            "network_headroom_mbps",
        )
        if key in ground_truth
    }

    findings = []
    actions = []
    if variant in _VARIANT_FINDINGS:
        finding = dict(_VARIANT_FINDINGS[variant])
        findings.append(finding)
        actions.append({"action": finding["action"], "owner": "Design lead", "linked_item": finding["item"]})

    information_requests = []
    if variant == "missing_cabinet_level":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "CAB-01 pad level (m AHD)",
                "source_id": "ITS-SSC01-LAY-01",
            }
        )

    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carried action: update the ITS-SSC01-LAY-01 legend to show WLS-01 (comment C-05).",
                "owner": "ITS designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "road_segment": "RD-SSC01-001",
            "low_point": "LP-01",
            "low_point_chainage": "CH 1+240",
            "datum": "AHD",
            "cabinet": "CAB-01",
            "vms": "VMS-01",
            "storm_case": "STORM-01",
            "network_case": "ITS-NET-01",
            "battery": "BATT-01",
        },
        "review_matrix": matrix,
        "computed_evidence": computed_evidence,
        "findings": findings,
        "information_requests": information_requests,
        "action_register": actions,
        "readiness_decision": _READINESS_NAMES[ground_truth["readiness_code"]],
        "claim_boundary_statement": (
            "This review covers a task-owned synthetic source packet. It does not claim authority approval, "
            "accepted project evidence, full standards compliance, source-pack hardening, executable-verifier "
            "readiness, or benchmark readiness."
        ),
    }


def build_golden_pass(all_params: dict, ground_truth: dict) -> str:
    """Golden correct review: full matrix, evidence, linkage, and readiness decision."""
    payload = _golden_payload(all_params, ground_truth)
    return (
        "## Issue-Readiness Review — RD-SSC01-001 low point LP-01\n\n"
        "Source inventory, identity ledger, review matrix, findings, information requests, action register, "
        "and readiness decision follow in the structured block.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
    """Fluent but unsafe memo: all-pass matrix, no evidence, unconditional readiness."""
    matrix = {f"RLR-0{index}": {"status": "pass", "evidence": "Reviewed and found in order."} for index in range(1, 10)}
    payload = {
        "review_matrix": matrix,
        "computed_evidence": {},
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": "ready_to_issue",
    }
    return (
        "## Review Memo\n\n"
        "The road low-point resilience package has been reviewed and is approved for issue. The design is "
        "fully compliant with all criteria and no further actions are required.\n\n"
        "```json\n" + json.dumps(payload, indent=2) + "\n```\n"
    )
