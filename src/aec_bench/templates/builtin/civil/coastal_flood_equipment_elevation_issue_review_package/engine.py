# ABOUTME: Engine for the SSC-04 coastal flood equipment elevation issue package.
# ABOUTME: Derives review gold state, renders coastal source packets, and builds verifier fixtures.

from __future__ import annotations

import json

STATUS_PASS = 0.0
STATUS_FAIL = 1.0
STATUS_NOT_APPLICABLE = 2.0
STATUS_INSUFFICIENT_DATA = 3.0

READY = 0.0
READY_WITH_CARRIED_ACTIONS = 1.0
NOT_READY = 2.0

STATUS_NAMES = {
    STATUS_PASS: "pass",
    STATUS_FAIL: "fail",
    STATUS_NOT_APPLICABLE: "not_applicable",
    STATUS_INSUFFICIENT_DATA: "insufficient_data",
}

READINESS_NAMES = {
    READY: "ready_to_issue",
    READY_WITH_CARRIED_ACTIONS: "ready_with_carried_actions",
    NOT_READY: "not_ready_to_issue",
}

QUANT_STEPS = {
    "present_mean_sea_level_m_ahd": 0.01,
    "tide_amplitude_m": 0.01,
    "storm_surge_m": 0.01,
    "slr_allowance_m": 0.01,
    "wave_runup_m": 0.01,
    "required_freeboard_m": 0.01,
    "switchboard_margin_target_m": 0.01,
    "generator_margin_target_m": 0.01,
    "switchboard_deficit_m": 0.01,
    "outfall_tailwater_margin_m": 0.01,
    "required_pump_duty_m3_s": 0.01,
    "pump_duty_margin_target_m3_s": 0.01,
    "cd_to_ahd_offset_m": 0.01,
}

VARIANT_GOLD = {
    "clean": {"flips": {}, "readiness": READY, "findings": 0.0, "requests": 0.0, "carried": 0.0},
    "missing_switchboard_survey_level": {
        "flips": {"rlr_04_status": STATUS_INSUFFICIENT_DATA},
        "readiness": NOT_READY,
        "findings": 0.0,
        "requests": 1.0,
        "carried": 0.0,
    },
    "stale_water_level_basis_revision": {
        "flips": {"rlr_03_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
    "asset_survey_chart_datum_labelled_ahd": {
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
    "switchboard_below_design_level": {
        "flips": {"rlr_04_status": STATUS_FAIL},
        "readiness": NOT_READY,
        "findings": 1.0,
        "requests": 0.0,
        "carried": 0.0,
    },
}


def _q(value: float, step: float) -> float:
    """Snap a value to its reporting grid."""
    return round(round(value / step) * step, 10)


def _quantize(params: dict) -> dict:
    """Return params with source-facing values snapped to stable grids."""
    quantized = dict(params)
    quantized["packet_variant"] = str(params["packet_variant"])
    for name, step in QUANT_STEPS.items():
        quantized[name] = _q(float(params[name]), step)
    return quantized


def _derive(params: dict) -> dict:
    """Derive source truth, package claims, and review-state values."""
    p = _quantize(params)
    variant = p["packet_variant"]
    design_flood = (
        p["present_mean_sea_level_m_ahd"]
        + p["tide_amplitude_m"]
        + p["slr_allowance_m"]
        + p["storm_surge_m"]
        + p["wave_runup_m"]
    )
    switchboard_margin = (
        -p["switchboard_deficit_m"] if variant == "switchboard_below_design_level" else p["switchboard_margin_target_m"]
    )
    switchboard_elevation = design_flood + p["required_freeboard_m"] + switchboard_margin
    generator_elevation = design_flood + p["required_freeboard_m"] + p["generator_margin_target_m"]
    design_tailwater = p["present_mean_sea_level_m_ahd"] + p["tide_amplitude_m"] + p["slr_allowance_m"]
    outfall_allowable_tailwater = design_tailwater + p["outfall_tailwater_margin_m"]
    selected_pump_duty = p["required_pump_duty_m3_s"] + p["pump_duty_margin_target_m3_s"]

    return {
        "params": p,
        "variant": variant,
        "design_flood": design_flood,
        "switchboard_elevation": switchboard_elevation,
        "generator_elevation": generator_elevation,
        "switchboard_freeboard": switchboard_elevation - design_flood,
        "switchboard_margin": switchboard_margin,
        "generator_margin": generator_elevation - design_flood - p["required_freeboard_m"],
        "design_tailwater": design_tailwater,
        "outfall_allowable_tailwater": outfall_allowable_tailwater,
        "outfall_margin": outfall_allowable_tailwater - design_tailwater,
        "selected_pump_duty": selected_pump_duty,
        "pump_margin": selected_pump_duty - p["required_pump_duty_m3_s"],
    }


def compute(**params) -> dict[str, float]:
    """Compute gold review statuses and recomputed evidence for an SSC-04 instance."""
    state = _derive(params)
    variant = state["variant"]
    spec = VARIANT_GOLD[variant]

    truth = {f"rlr_0{i}_status": STATUS_PASS for i in range(1, 10)}
    truth.update(spec["flips"])
    truth.update(
        {
            "design_flood_level_m_ahd": round(state["design_flood"], 3),
            "wave_runup_m": round(state["params"]["wave_runup_m"], 3),
            "generator_freeboard_margin_m": round(state["generator_margin"], 3),
            "outfall_submergence_margin_m": round(state["outfall_margin"], 3),
            "pump_duty_margin": round(state["pump_margin"], 3),
            "readiness_code": spec["readiness"],
            "required_findings_count": spec["findings"],
            "required_information_requests_count": spec["requests"],
            "required_carried_actions_count": spec["carried"],
        }
    )
    if variant != "missing_switchboard_survey_level":
        truth["switchboard_freeboard_m"] = round(state["switchboard_freeboard"], 3)
        truth["switchboard_freeboard_margin_m"] = round(state["switchboard_margin"], 3)
    return truth


def build_sources(all_params: dict) -> dict[str, str]:
    """Render the seven-file source packet for one instance."""
    state = _derive(all_params)
    p = state["params"]
    variant = state["variant"]

    water_revision = "Rev C" if variant == "stale_water_level_basis_revision" else "Rev D"
    if variant == "scenario_copy_forward":
        slr_asset_class = "car park asset class copied from SLR-04-YARD"
    else:
        slr_asset_class = "pump station critical equipment"

    register = """# Document Register

| Document ID | Title | Revision | Status |
|---|---|---|---|
| TIDE-04-BASIS-01 | Tide and water-level basis | Rev D | current |
| SLR-04-SCEN-01 | SLR planning horizon | Rev C | current |
| RUNUP-04-WAVE-01 | Wave and runup basis | Rev C | current |
| SURV-04-ASSET-01 | Asset survey | Rev D | current |
| PUMP-04-OUTFALL-01 | Pump and outfall schedule | Rev C | current |
| CRIT-SSC04-001 | Criteria and review comments | Rev C | current |
"""

    water = f"""# Tide And Water-Level Basis

Source ID: TIDE-04-BASIS-01 ({water_revision})
Site: SITE-04
Datum: DATUM-04
Water-level basis: TIDE-04

| Field | Value |
|---|---|
| Present mean sea level | {p["present_mean_sea_level_m_ahd"]:.2f} m AHD |
| Tide amplitude | {p["tide_amplitude_m"]:.2f} m |
| Storm surge | {p["storm_surge_m"]:.2f} m |
| Controlling datum | AHD |
"""

    slr = f"""# SLR Planning Horizon

Source ID: SLR-04-SCEN-01
Site: SITE-04
SLR scenario: SLR-04

| Field | Value |
|---|---|
| SLR allowance | {p["slr_allowance_m"]:.2f} m |
| Planning horizon | 2100 |
| Asset class | {slr_asset_class} |
"""

    runup = f"""# Wave And Runup Basis

Source ID: RUNUP-04-WAVE-01
Site: SITE-04
Runup case: RUNUP-04

| Field | Value |
|---|---|
| Wave runup | {p["wave_runup_m"]:.2f} m |
| Runup basis | exposed coastal pump station frontage |
"""

    if variant == "missing_switchboard_survey_level":
        switchboard_row = "| Switchboard surveyed elevation | survey to follow |"
    else:
        switchboard_row = f"| Switchboard surveyed elevation | {state['switchboard_elevation']:.2f} m AHD |"
    datum_note = "Survey elevations are in AHD."
    if variant == "asset_survey_chart_datum_labelled_ahd":
        datum_note = "Survey levels are chart datum values labelled AHD; chart datum conversion was not applied."
    survey = f"""# Asset Survey

Source ID: SURV-04-ASSET-01
Site: SITE-04
Switchboard: SWBD-04
Generator: GEN-04

{datum_note}

| Field | Value |
|---|---|
{switchboard_row}
| Generator surveyed elevation | {state["generator_elevation"]:.2f} m AHD |
"""

    pump = f"""# Pump And Outfall Schedule

Source ID: PUMP-04-OUTFALL-01
Site: SITE-04
Outfall: OUTFALL-04
Pump duty: PUMP-04

| Field | Value |
|---|---|
| Design tailwater | {state["design_tailwater"]:.2f} m AHD |
| Required pump duty | {p["required_pump_duty_m3_s"]:.2f} m3/s |
| Selected pump duty | {state["selected_pump_duty"]:.2f} m3/s |
"""

    comment_status = "All review comments closed."
    if variant == "open_critical_comment":
        comment_status = "Critical comment CRIT-04-C03 remains open: confirm switchboard flood elevation before issue."
    elif variant == "minor_open_comment_carried":
        comment_status = (
            "Minor comment CRIT-04-M01 may be carried with owner coastal lead and action to update figure title."
        )

    criteria = f"""# Criteria And Review Comments

Source ID: CRIT-SSC04-001
Site: SITE-04

## Assessment bases (source-owned methods)

Controlling datum: AHD.
Chart datum to AHD offset: {p["cd_to_ahd_offset_m"]:.2f} m.
Design flood level = present mean sea level + tide amplitude + SLR allowance + storm surge + wave runup.
Required equipment freeboard: {p["required_freeboard_m"]:.2f} m.
Outfall allowable tailwater: {state["outfall_allowable_tailwater"]:.2f} m AHD.
Pump duty margin = selected pump duty minus required pump duty.

## Comments

{comment_status}
"""

    return {
        "sources/document-register.md": register,
        "sources/tide-water-level-basis.md": water,
        "sources/slr-planning-horizon.md": slr,
        "sources/wave-runup-basis.md": runup,
        "sources/asset-survey.md": survey,
        "sources/pump-outfall-schedule.md": pump,
        "sources/criteria-comments.md": criteria,
    }


def _status_entry(status: float, evidence: str) -> dict[str, str]:
    """Build one review-matrix entry."""
    return {"status": STATUS_NAMES[status], "evidence": evidence}


def _base_payload(ground_truth: dict) -> dict:
    """Create a gold review payload from ground-truth status codes."""
    source_inventory = [
        {"doc_id": "TIDE-04-BASIS-01", "revision": "Rev D", "status": "current"},
        {"doc_id": "SLR-04-SCEN-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "RUNUP-04-WAVE-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "SURV-04-ASSET-01", "revision": "Rev D", "status": "current"},
        {"doc_id": "PUMP-04-OUTFALL-01", "revision": "Rev C", "status": "current"},
        {"doc_id": "CRIT-SSC04-001", "revision": "Rev C", "status": "current"},
    ]
    ledger = {
        "site": "SITE-04",
        "datum": "DATUM-04 AHD",
        "water_level_basis": "TIDE-04-BASIS-01",
        "slr_scenario": "SLR-04",
        "runup_case": "RUNUP-04",
        "switchboard": "SWBD-04",
        "generator": "GEN-04",
        "outfall": "OUTFALL-04",
        "pump_duty": "PUMP-04",
        "criteria_memo": "CRIT-SSC04-001",
    }
    evidence_text = {
        "RLR-01": "Required source files are inventoried with IDs and revisions.",
        "RLR-02": "SITE-04, DATUM-04, SWBD-04, GEN-04, OUTFALL-04, PUMP-04, and CRIT-SSC04-001 stay consistent.",
        "RLR-03": "Coastal boundary basis is traceable and recomputed from source-owned criteria.",
        "RLR-04": "Equipment elevations clear the source-owned design flood level and required freeboard.",
        "RLR-05": "Same planning horizon and asset class are used through the packet.",
        "RLR-06": "Outfall tailwater and pump duty margins are source-backed.",
        "RLR-07": "Review comments are closed or carried with owner and action.",
        "RLR-08": "Readiness decision reconciles with matrix and registers.",
        "RLR-09": "Review remains inside the task-owned synthetic claim boundary.",
    }
    matrix = {
        item: _status_entry(ground_truth[f"rlr_0{item[-1]}_status"], evidence_text[item])
        for item in [f"RLR-0{i}" for i in range(1, 10)]
    }
    computed = {
        key: ground_truth[key]
        for key in (
            "design_flood_level_m_ahd",
            "wave_runup_m",
            "switchboard_freeboard_m",
            "switchboard_freeboard_margin_m",
            "generator_freeboard_margin_m",
            "outfall_submergence_margin_m",
            "pump_duty_margin",
        )
        if key in ground_truth
    }
    return {
        "source_inventory": source_inventory,
        "identity_ledger": ledger,
        "review_matrix": matrix,
        "computed_evidence": computed,
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": READINESS_NAMES[ground_truth["readiness_code"]],
        "claim_boundary_statement": (
            "This review covers a task-owned synthetic source packet. It does not claim authority approval, "
            "accepted project evidence, full standards compliance, source-pack hardening, executable-verifier "
            "readiness, or benchmark readiness."
        ),
    }


def build_golden_pass(all_params: dict, ground_truth: dict) -> str:
    """Build a full-credit review response fixture."""
    variant = str(all_params["packet_variant"])
    payload = _base_payload(ground_truth)

    if variant == "missing_switchboard_survey_level":
        payload["review_matrix"]["RLR-04"]["evidence"] = (
            "Switchboard surveyed elevation is missing, so switchboard freeboard cannot be completed."
        )
        payload["information_requests"].append(
            {
                "item": "RLR-04",
                "missing_field": "switchboard surveyed elevation",
                "source_id": "SURV-04-ASSET-01",
            }
        )
    elif variant in {
        "stale_water_level_basis_revision",
        "asset_survey_chart_datum_labelled_ahd",
        "scenario_copy_forward",
        "open_critical_comment",
        "switchboard_below_design_level",
    }:
        item = {
            "stale_water_level_basis_revision": "RLR-03",
            "asset_survey_chart_datum_labelled_ahd": "RLR-02",
            "scenario_copy_forward": "RLR-05",
            "open_critical_comment": "RLR-07",
            "switchboard_below_design_level": "RLR-04",
        }[variant]
        payload["findings"].append(
            {
                "item": item,
                "severity": "critical",
                "source_id": {
                    "stale_water_level_basis_revision": "TIDE-04-BASIS-01",
                    "asset_survey_chart_datum_labelled_ahd": "SURV-04-ASSET-01",
                    "scenario_copy_forward": "SLR-04-SCEN-01",
                    "open_critical_comment": "CRIT-SSC04-001",
                    "switchboard_below_design_level": "SURV-04-ASSET-01",
                }[variant],
                "object_id": {
                    "stale_water_level_basis_revision": "TIDE-04",
                    "asset_survey_chart_datum_labelled_ahd": "DATUM-04",
                    "scenario_copy_forward": "SLR-04",
                    "open_critical_comment": "CRIT-04-C03",
                    "switchboard_below_design_level": "SWBD-04",
                }[variant],
                "consequence": "The package cannot be issued until the blocker is resolved.",
                "action": "Revise the affected source and re-issue the review packet.",
            }
        )
    elif variant == "minor_open_comment_carried":
        payload["action_register"].append(
            {
                "action": "Carry figure-title update to next issue",
                "owner": "coastal lead",
                "linked_item": "RLR-07",
            }
        )

    json_block = json.dumps(payload, indent=2)
    return f"""## Review

The source packet has been inventoried, recomputed where applicable, and assessed against the review matrix.

```json
{json_block}
```
"""


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
    """Build a fluent unsafe fixture that approves the packet without evidence."""
    payload = {
        "source_inventory": [],
        "identity_ledger": {},
        "review_matrix": {f"RLR-0{i}": {"status": "pass", "evidence": "Looks acceptable."} for i in range(1, 10)},
        "computed_evidence": {},
        "findings": [],
        "information_requests": [],
        "action_register": [],
        "readiness_decision": "ready_to_issue",
        "claim_boundary_statement": "Approved for issue.",
    }
    json_block = json.dumps(payload, indent=2)
    return f"""## Review

The package appears acceptable for issue.

```json
{json_block}
```
"""
