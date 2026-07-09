# ABOUTME: Engine for the SSC-02 level-crossing warning issue review package.
# ABOUTME: Renders source files, derives review evidence, and builds golden fixtures.

from __future__ import annotations

import json

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

_QUANT_STEPS = {
    "maximum_train_speed_kmh": 0.1,
    "minimum_warning_time_s": 0.1,
    "warning_time_margin_s": 0.1,
    "warning_time_deficit_s": 0.1,
    "gate_lowering_time_s": 0.1,
    "gate_start_delay_s": 0.1,
    "required_gate_horizontal_before_arrival_s": 0.1,
    "controller_load_w": 1.0,
    "flashing_light_load_w": 1.0,
    "gate_mechanism_load_w": 1.0,
    "comms_switch_load_w": 1.0,
    "track_circuit_load_w": 1.0,
    "event_recorder_load_w": 1.0,
    "load_future_allowance_pct": 0.1,
    "battery_runtime_margin_h": 0.1,
    "dc_system_voltage_v": 1.0,
    "depth_of_discharge_pct": 0.1,
    "temperature_derating_factor": 0.01,
    "inverter_efficiency_pct": 0.1,
    "load_power_factor": 0.01,
    "selected_ups_rating_margin_va": 1.0,
    "voltage_drop_margin_target_percent": 0.1,
    "feeder_resistance_milliohm_per_m": 0.01,
    "max_voltage_drop_percent": 0.1,
    "fiber_length_km": 0.01,
    "fiber_attenuation_db_per_km": 0.01,
    "connector_loss_db": 0.01,
    "splice_loss_db": 0.01,
    "patch_panel_allowance_db": 0.1,
    "optical_tx_power_dbm": 0.1,
    "receiver_sensitivity_dbm": 0.1,
    "required_fiber_margin_db": 0.1,
}
_COUNT_PARAMS = {
    "flashing_light_count",
    "gate_mechanism_count",
    "fiber_connector_count",
    "fiber_splice_count",
}


def _f(params: dict, key: str) -> float:
    return float(params[key])


def _q(value: float, digits: int = 3) -> float:
    return round(value, digits)


def _snap(value: float, step: float) -> float:
    return round(round(value / step) * step, 10)


def _quantize(params: dict) -> dict:
    quantized = dict(params)
    for key, step in _QUANT_STEPS.items():
        quantized[key] = _snap(float(params[key]), step)
    for key in _COUNT_PARAMS:
        quantized[key] = int(params[key])
    quantized["required_autonomy_h"] = str(params["required_autonomy_h"])
    quantized["packet_variant"] = str(params["packet_variant"])
    return quantized


def _derive(raw_params: dict) -> dict:
    p = _quantize(raw_params)
    variant = str(p["packet_variant"])

    speed_m_s = _f(p, "maximum_train_speed_kmh") / 3.6
    if variant == "warning_time_deficient":
        provided_warning_time_s = _f(p, "minimum_warning_time_s") - _f(p, "warning_time_deficit_s")
    else:
        provided_warning_time_s = _f(p, "minimum_warning_time_s") + _f(p, "warning_time_margin_s")
    strike_in_distance_m = speed_m_s * provided_warning_time_s
    warning_time_margin_s = provided_warning_time_s - _f(p, "minimum_warning_time_s")
    gate_horizontal_margin_s = (
        provided_warning_time_s
        - _f(p, "gate_start_delay_s")
        - _f(p, "gate_lowering_time_s")
        - _f(p, "required_gate_horizontal_before_arrival_s")
    )

    connected_load_w = (
        _f(p, "controller_load_w")
        + _f(p, "flashing_light_load_w") * _f(p, "flashing_light_count")
        + _f(p, "gate_mechanism_load_w") * _f(p, "gate_mechanism_count")
        + _f(p, "comms_switch_load_w")
        + _f(p, "track_circuit_load_w")
        + _f(p, "event_recorder_load_w")
    )
    design_signal_load_w = connected_load_w * (1.0 + _f(p, "load_future_allowance_pct") / 100.0)
    required_autonomy_h = float(p["required_autonomy_h"])
    usable_fraction = (
        _f(p, "depth_of_discharge_pct")
        / 100.0
        * _f(p, "temperature_derating_factor")
        * _f(p, "inverter_efficiency_pct")
        / 100.0
    )
    required_battery_capacity_ah = (
        design_signal_load_w * required_autonomy_h / (_f(p, "dc_system_voltage_v") * usable_fraction)
    )
    installed_battery_capacity_ah = (
        design_signal_load_w
        * (required_autonomy_h + _f(p, "battery_runtime_margin_h"))
        / (_f(p, "dc_system_voltage_v") * usable_fraction)
    )
    battery_runtime_h = (
        installed_battery_capacity_ah * _f(p, "dc_system_voltage_v") * usable_fraction / design_signal_load_w
    )
    battery_runtime_margin_h = battery_runtime_h - required_autonomy_h
    required_ups_rating_va = design_signal_load_w / _f(p, "load_power_factor")
    selected_ups_rating_va = required_ups_rating_va + _f(p, "selected_ups_rating_margin_va")

    dc_feeder_current_a = design_signal_load_w / _f(p, "dc_system_voltage_v")
    target_voltage_drop_percent = _f(p, "max_voltage_drop_percent") - _f(p, "voltage_drop_margin_target_percent")
    feeder_length_m = _snap(
        target_voltage_drop_percent
        / 100.0
        * _f(p, "dc_system_voltage_v")
        * 1000.0
        / (2.0 * dc_feeder_current_a * _f(p, "feeder_resistance_milliohm_per_m")),
        0.1,
    )
    dc_feeder_voltage_drop_v = (
        2.0 * dc_feeder_current_a * feeder_length_m * _f(p, "feeder_resistance_milliohm_per_m") / 1000.0
    )
    dc_feeder_voltage_drop_percent = dc_feeder_voltage_drop_v / _f(p, "dc_system_voltage_v") * 100.0
    dc_voltage_drop_margin_percent = _f(p, "max_voltage_drop_percent") - dc_feeder_voltage_drop_percent

    fiber_total_loss_db = (
        _f(p, "fiber_length_km") * _f(p, "fiber_attenuation_db_per_km")
        + _f(p, "fiber_connector_count") * _f(p, "connector_loss_db")
        + _f(p, "fiber_splice_count") * _f(p, "splice_loss_db")
        + _f(p, "patch_panel_allowance_db")
    )
    fiber_receive_power_dbm = _f(p, "optical_tx_power_dbm") - fiber_total_loss_db
    fiber_link_margin_db = fiber_receive_power_dbm - _f(p, "receiver_sensitivity_dbm")
    fiber_excess_margin_db = fiber_link_margin_db - _f(p, "required_fiber_margin_db")

    return {
        "params": p,
        "variant": variant,
        "speed_m_s": speed_m_s,
        "provided_warning_time_s": provided_warning_time_s,
        "strike_in_distance_m": strike_in_distance_m,
        "warning_time_margin_s": warning_time_margin_s,
        "gate_horizontal_margin_s": gate_horizontal_margin_s,
        "connected_load_w": connected_load_w,
        "design_signal_load_w": design_signal_load_w,
        "required_autonomy_h": required_autonomy_h,
        "required_battery_capacity_ah": required_battery_capacity_ah,
        "installed_battery_capacity_ah": installed_battery_capacity_ah,
        "battery_runtime_h": battery_runtime_h,
        "battery_runtime_margin_h": battery_runtime_margin_h,
        "required_ups_rating_va": required_ups_rating_va,
        "selected_ups_rating_va": selected_ups_rating_va,
        "dc_feeder_current_a": dc_feeder_current_a,
        "feeder_length_m": feeder_length_m,
        "dc_feeder_voltage_drop_v": dc_feeder_voltage_drop_v,
        "dc_feeder_voltage_drop_percent": dc_feeder_voltage_drop_percent,
        "dc_voltage_drop_margin_percent": dc_voltage_drop_margin_percent,
        "fiber_total_loss_db": fiber_total_loss_db,
        "fiber_receive_power_dbm": fiber_receive_power_dbm,
        "fiber_link_margin_db": fiber_link_margin_db,
        "fiber_excess_margin_db": fiber_excess_margin_db,
    }


_VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_battery_capacity": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_warning_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "chainage_sighting_mismatch": {
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
    "warning_time_deficient": {
        "flips": {"rlr_04_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}


def compute(**params) -> dict[str, float]:
    """Return gold review statuses and recomputed evidence for one issue packet."""
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

    evidence = {
        "maximum_train_speed_m_s": state["speed_m_s"],
        "provided_warning_time_s": state["provided_warning_time_s"],
        "strike_in_distance_m": state["strike_in_distance_m"],
        "warning_time_margin_s": state["warning_time_margin_s"],
        "gate_horizontal_margin_s": state["gate_horizontal_margin_s"],
        "design_signal_load_w": state["design_signal_load_w"],
        "required_battery_capacity_ah": state["required_battery_capacity_ah"],
        "installed_battery_capacity_ah": state["installed_battery_capacity_ah"],
        "battery_runtime_h": state["battery_runtime_h"],
        "battery_runtime_margin_h": state["battery_runtime_margin_h"],
        "dc_voltage_drop_margin_percent": state["dc_voltage_drop_margin_percent"],
        "fiber_link_margin_db": state["fiber_link_margin_db"],
    }
    if state["variant"] == "missing_battery_capacity":
        for key in ("installed_battery_capacity_ah", "battery_runtime_h", "battery_runtime_margin_h"):
            evidence.pop(key, None)
    for key, value in evidence.items():
        result[key] = _q(value)
    return result


def _register_rows(variant: str) -> list[tuple[str, str, str, str]]:
    return [
        ("ROUTE-SSC02-LX-01", "Route profile and crossing location", "Rev C", "Issued for review"),
        ("SIGHT-SSC02-LX-01", "Sighting and warning time worksheet", "Rev B", "Issued for review"),
        ("LAYOUT-SSC02-LX-01", "Crossing control layout", "Rev B", "Issued for review"),
        ("BACKUP-SSC02-LX-01", "Backup power and communications schedule", "Rev B", "Issued for review"),
        ("OPS-SSC02-LX-01", "Degraded-mode operations note", "Rev A", "Current"),
        ("CRIT-SSC02-LX-01", "Criteria memo and review comments", "Rev A", "Current"),
    ]


def _comments_table(variant: str) -> str:
    rows = [
        (
            "C-01",
            "Rail",
            "Confirm warning time and sighting basis refer to the same crossing approach.",
            "Closed",
            "minor",
            "",
            "",
        ),
        (
            "C-02",
            "Electrical",
            "Confirm backup-power schedule supports the degraded-mode case.",
            "Closed",
            "minor",
            "",
            "",
        ),
        ("C-03", "Comms", "Confirm fiber-link budget is source backed.", "Closed", "minor", "", ""),
    ]
    if variant == "open_critical_comment":
        rows.append(
            (
                "C-04",
                "Operator",
                "Resolve critical warning-time issue comment before package issue.",
                "Open",
                "critical",
                "",
                "",
            )
        )
    if variant == "minor_open_comment_carried":
        rows.append(
            (
                "C-05",
                "Documentation",
                "Update the crossing equipment label on the next issue.",
                "Open",
                "minor",
                "Signalling designer",
                "Carry label update to next package issue.",
            )
        )
    lines = [
        "| ID | Discipline | Comment | Status | Criticality | Owner | Agreed action |",
        "|---|---|---|---|---|---|---|",
    ]
    lines.extend(f"| {row[0]} | {row[1]} | {row[2]} | {row[3]} | {row[4]} | {row[5]} | {row[6]} |" for row in rows)
    return "\n".join(lines)


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the source packet for one level-crossing issue review instance."""
    state = _derive(all_params)
    p = state["params"]
    variant = state["variant"]

    register_lines = ["| Document ID | Title | Revision | Status |", "|---|---|---|---|"]
    register_lines.extend(
        f"| {doc_id} | {title} | {rev} | {status} |" for doc_id, title, rev, status in _register_rows(variant)
    )
    document_register = (
        "# Document Register - DOC-REG-SSC02-LX\n\n"
        "Issue package: LX-SSC02-014 warning, controls, backup-power, and communications review.\n\n"
        + "\n".join(register_lines)
        + "\n"
    )

    route_crossing = "LX-SSC02-041" if variant == "chainage_sighting_mismatch" else "LX-SSC02-014"
    route_profile = f"""# Route Profile - ROUTE-SSC02-LX-01 (Rev C)

Route case: SSC-02 North approach. Crossing ID: {route_crossing}.

| Item | Value |
|---|---|
| Crossing ID | {route_crossing} |
| Approach track | North main |
| Maximum train speed | {_f(p, "maximum_train_speed_kmh"):.3f} km/h |
| Crossing chainage | Ch 42+180 |
| Track direction | Up approach |

Package claim: ROUTE-SSC02-LX-01 is the route and speed basis for the warning-time review.
"""

    warning_revision = "Rev A" if variant == "stale_warning_revision" else "Rev B"
    sighting_warning_time = f"""# Sighting And Warning Time Worksheet - SIGHT-SSC02-LX-01 ({warning_revision})

Crossing ID: LX-SSC02-014. Route source: ROUTE-SSC02-LX-01.

| Item | Value |
|---|---|
| Maximum train speed | {_f(p, "maximum_train_speed_kmh"):.3f} km/h |
| Strike-in distance | {state["strike_in_distance_m"]:.3f} m |
| Minimum warning time | {_f(p, "minimum_warning_time_s"):.3f} s |
| Provided warning time | {state["provided_warning_time_s"]:.3f} s |
| Warning-time margin | {state["warning_time_margin_s"]:.3f} s |
| Gate start delay | {_f(p, "gate_start_delay_s"):.3f} s |
| Gate lowering time | {_f(p, "gate_lowering_time_s"):.3f} s |
| Required gates-horizontal time before arrival | {_f(p, "required_gate_horizontal_before_arrival_s"):.3f} s |
| Gates-horizontal margin | {state["gate_horizontal_margin_s"]:.3f} s |

Package claim: the strike-in distance provides the warning time for LX-SSC02-014.
"""

    crossing_control_layout = f"""# Crossing Control Layout - LAYOUT-SSC02-LX-01 (Rev B)

Crossing ID: LX-SSC02-014. Controller cabinet: CAB-LX-014.

| Item | Value |
|---|---|
| Controller load | {_f(p, "controller_load_w"):.1f} W |
| Flashing-light load | {_f(p, "flashing_light_load_w"):.1f} W |
| Flashing-light count | {int(_f(p, "flashing_light_count"))} |
| Gate mechanism load | {_f(p, "gate_mechanism_load_w"):.1f} W |
| Gate mechanism count | {int(_f(p, "gate_mechanism_count"))} |
| Track circuit load | {_f(p, "track_circuit_load_w"):.1f} W |
| Event recorder load | {_f(p, "event_recorder_load_w"):.1f} W |
| Claimed design signal load | {state["design_signal_load_w"]:.3f} W |
"""

    battery_capacity_line = (
        "| Installed battery capacity | pending battery capacity confirmation |"
        if variant == "missing_battery_capacity"
        else f"| Installed battery capacity | {state['installed_battery_capacity_ah']:.3f} Ah |"
    )
    runtime_line = (
        "| Claimed battery runtime | pending battery runtime confirmation |"
        if variant == "missing_battery_capacity"
        else f"| Claimed battery runtime | {state['battery_runtime_h']:.3f} h |"
    )
    backup_power_comms = f"""# Backup Power And Communications Schedule - BACKUP-SSC02-LX-01 (Rev B)

Crossing ID: LX-SSC02-014. Degraded-mode source: OPS-SSC02-LX-01.

| Item | Value |
|---|---|
| Communications switch load | {_f(p, "comms_switch_load_w"):.1f} W |
| Load future allowance | {_f(p, "load_future_allowance_pct"):.1f} % |
| Required autonomy | {state["required_autonomy_h"]:.1f} h |
| DC system voltage | {_f(p, "dc_system_voltage_v"):.1f} V |
| Depth of discharge | {_f(p, "depth_of_discharge_pct"):.1f} % |
| Temperature derating factor | {_f(p, "temperature_derating_factor"):.3f} |
| Inverter efficiency | {_f(p, "inverter_efficiency_pct"):.1f} % |
| Required battery capacity | {state["required_battery_capacity_ah"]:.3f} Ah |
{battery_capacity_line}
{runtime_line}
| Required UPS rating | {state["required_ups_rating_va"]:.3f} VA |
| Selected UPS rating | {state["selected_ups_rating_va"]:.3f} VA |
| Feeder length | {state["feeder_length_m"]:.1f} m |
| Feeder resistance | {_f(p, "feeder_resistance_milliohm_per_m"):.3f} milliohm/m |
| Maximum voltage drop | {_f(p, "max_voltage_drop_percent"):.1f} % |
| DC voltage-drop margin | {state["dc_voltage_drop_margin_percent"]:.3f} % |
| Fiber length | {_f(p, "fiber_length_km"):.3f} km |
| Fiber attenuation | {_f(p, "fiber_attenuation_db_per_km"):.3f} dB/km |
| Fiber connector count | {int(_f(p, "fiber_connector_count"))} |
| Connector loss | {_f(p, "connector_loss_db"):.3f} dB |
| Fiber splice count | {int(_f(p, "fiber_splice_count"))} |
| Splice loss | {_f(p, "splice_loss_db"):.3f} dB |
| Patch panel allowance | {_f(p, "patch_panel_allowance_db"):.3f} dB |
| Optical TX power | {_f(p, "optical_tx_power_dbm"):.3f} dBm |
| Receiver sensitivity | {_f(p, "receiver_sensitivity_dbm"):.3f} dBm |
| Required fiber margin | {_f(p, "required_fiber_margin_db"):.3f} dB |
| Fiber link margin | {state["fiber_link_margin_db"]:.3f} dB |
"""

    scenario_note = "LX-SSC02-014 degraded-mode case for the North approach."
    if variant == "scenario_copy_forward":
        scenario_note = (
            "LX-SSC02-014 degraded-mode table was copied forward from LX-SSC02-099; confirm the warning, backup, "
            "and communications assumptions belong to LX-SSC02-014."
        )
    degraded_mode_operations = f"""# Degraded-Mode Operations Note - OPS-SSC02-LX-01 (Rev A)

Scenario note: {scenario_note}

Issue-readiness rule: unresolved warning-time, backup-power, communications, or critical comment findings block issue.
"""

    criteria_comments = f"""# Criteria Memo And Review Comments - CRIT-SSC02-LX-01 (Rev A)

## Acceptance criteria

| Criterion | Value |
|---|---|
| Warning-time margin | must be greater than or equal to 0 s |
| Gate-horizontal margin | must be greater than or equal to 0 s |
| Battery runtime margin | must be greater than or equal to 0 h |
| DC voltage-drop margin | must be greater than or equal to 0 percent |
| Fiber link margin | must be greater than or equal to the required margin in BACKUP-SSC02-LX-01 |

## Assessment bases

- Provided warning time: strike-in distance divided by maximum train speed.
- Warning-time margin: provided warning time minus minimum warning time.
- Gates-horizontal margin: provided warning time minus gate start delay, gate lowering time, and required gate time.
- Design signal load: connected signal load plus future allowance.
- Battery runtime: installed battery capacity times DC voltage and usable fraction divided by design signal load.
- DC feeder voltage drop: two-way feeder current drop divided by DC voltage.
- Fiber link margin: receive power minus receiver sensitivity.

## Review comments

{_comments_table(variant)}
"""

    return {
        "sources/document-register.md": document_register,
        "sources/route-profile.md": route_profile,
        "sources/sighting-warning-time.md": sighting_warning_time,
        "sources/crossing-control-layout.md": crossing_control_layout,
        "sources/backup-power-comms.md": backup_power_comms,
        "sources/degraded-mode-operations.md": degraded_mode_operations,
        "sources/criteria-comments.md": criteria_comments,
    }


_VARIANT_FINDINGS = {
    "stale_warning_revision": {
        "item": "RLR-03",
        "severity": "critical",
        "source_id": "SIGHT-SSC02-LX-01",
        "object_id": "SIGHT-SSC02-LX-01",
        "consequence": "The warning-time worksheet is stale against the document register.",
        "action": "Replace the stale warning-time worksheet with the current revision before issue.",
    },
    "chainage_sighting_mismatch": {
        "item": "RLR-02",
        "severity": "critical",
        "source_id": "ROUTE-SSC02-LX-01",
        "object_id": "LX-SSC02-041",
        "consequence": "The route table and sighting worksheet do not identify the same crossing.",
        "action": "Reconcile the crossing ID and chainage across route and sighting sources before issue.",
    },
    "scenario_copy_forward": {
        "item": "RLR-05",
        "severity": "critical",
        "source_id": "OPS-SSC02-LX-01",
        "object_id": "LX-SSC02-014",
        "consequence": "The degraded-mode scenario is copied from another crossing.",
        "action": "Reissue the degraded-mode note for LX-SSC02-014 before issue.",
    },
    "open_critical_comment": {
        "item": "RLR-07",
        "severity": "critical",
        "source_id": "CRIT-SSC02-LX-01",
        "object_id": "C-04",
        "consequence": "A critical warning-time comment remains open.",
        "action": "Close comment C-04 before issue.",
    },
    "warning_time_deficient": {
        "item": "RLR-04",
        "severity": "critical",
        "source_id": "SIGHT-SSC02-LX-01",
        "object_id": "LX-SSC02-014",
        "consequence": "The recomputed warning-time margin is negative.",
        "action": "Revise strike-in distance, speed case, or warning controls before issue.",
    },
}


def _golden_payload(all_params: dict, ground_truth: dict) -> dict:
    variant = str(all_params["packet_variant"])
    evidence_notes = {
        "RLR-01": "All required level-crossing source files are present with IDs and revisions.",
        "RLR-02": "The route, sighting, layout, backup, degraded-mode, and criteria sources identify LX-SSC02-014.",
        "RLR-03": "Warning-time, backup-power, feeder, and fiber bases are traceable and recomputable.",
        "RLR-04": "Warning-time and backup-power adequacy clear the source-owned criteria.",
        "RLR-05": "The same degraded-mode scenario is used across warning, backup, feeder, and fiber sources.",
        "RLR-06": "Feeder voltage-drop and fiber-link evidence are source-backed and internally consistent.",
        "RLR-07": "All critical comments are closed and carried minor comments have owners.",
        "RLR-08": "The readiness decision reconciles with the matrix and registers.",
        "RLR-09": "This review makes no approval, compliance, or benchmark-readiness claims.",
    }
    if variant in _VARIANT_FINDINGS:
        finding = _VARIANT_FINDINGS[variant]
        evidence_notes[finding["item"]] = finding["consequence"]
    if variant == "missing_battery_capacity":
        evidence_notes["RLR-04"] = "BACKUP-SSC02-LX-01 marks installed battery capacity as pending confirmation."

    matrix = {}
    for index in range(1, 10):
        item_id = f"RLR-0{index}"
        matrix[item_id] = {
            "status": _STATUS_NAMES[ground_truth[f"rlr_0{index}_status"]],
            "evidence": evidence_notes[item_id],
        }

    computed_evidence = {
        key: ground_truth[key]
        for key in (
            "maximum_train_speed_m_s",
            "provided_warning_time_s",
            "strike_in_distance_m",
            "warning_time_margin_s",
            "gate_horizontal_margin_s",
            "design_signal_load_w",
            "required_battery_capacity_ah",
            "installed_battery_capacity_ah",
            "battery_runtime_h",
            "battery_runtime_margin_h",
            "dc_voltage_drop_margin_percent",
            "fiber_link_margin_db",
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
    if variant == "missing_battery_capacity":
        information_requests.append(
            {
                "item": "RLR-04",
                "missing_field": "Installed battery capacity for BACKUP-SSC02-LX-01",
                "source_id": "BACKUP-SSC02-LX-01",
            }
        )
    if variant == "minor_open_comment_carried":
        actions.append(
            {
                "action": "Carry the crossing equipment label update to the next package issue.",
                "owner": "Signalling designer",
                "linked_item": "RLR-07",
            }
        )

    return {
        "source_inventory": [
            {"doc_id": doc_id, "revision": rev, "status": status}
            for doc_id, _title, rev, status in _register_rows(variant)
        ],
        "identity_ledger": {
            "route_profile": "ROUTE-SSC02-LX-01",
            "sighting_warning_time": "SIGHT-SSC02-LX-01",
            "crossing_layout": "LAYOUT-SSC02-LX-01",
            "backup_power_comms": "BACKUP-SSC02-LX-01",
            "degraded_mode": "OPS-SSC02-LX-01",
            "criteria_comments": "CRIT-SSC02-LX-01",
            "crossing_id": "LX-SSC02-014",
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
    payload = _golden_payload(all_params, ground_truth)
    return (
        "## Issue-Readiness Review - SSC-02 level crossing package\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```\n"
    )


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
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
        "## Review Memo\n\nApproved for issue with no further actions.\n\n```json\n"
        + json.dumps(payload, indent=2)
        + "\n```\n"
    )
