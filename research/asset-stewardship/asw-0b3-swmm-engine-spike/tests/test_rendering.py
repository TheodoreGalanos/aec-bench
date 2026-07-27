# ABOUTME: Tests deterministic SWMM input rendering for the two isolated duty probes.
# ABOUTME: Ensures the renderer exercises engine semantics without encoding a duty transfer or shared operation.

from __future__ import annotations

from pathlib import Path

from asw_b3_swmm.rendering import render_probe
from asw_b3_swmm.specification import load_specification

SPIKE_ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = load_specification(SPIKE_ROOT / "fixtures" / "spike-probes.json")


def test_a_duty_render_has_one_active_pump_and_no_controls() -> None:
    rendered = render_probe(SPECIFICATION, "a_duty")

    assert "PUMP_A          WET_WELL    DISCHARGE  PUMP_CURVE  ON" in rendered
    assert "PUMP_B          WET_WELL    DISCHARGE  PUMP_CURVE  OFF" in rendered
    assert "[CONTROLS]" not in rendered
    assert "TRANSFER" not in rendered.upper()


def test_b_label_probe_mirrors_status_without_changing_hydraulic_fixture() -> None:
    a_duty = render_probe(SPECIFICATION, "a_duty")
    b_duty = render_probe(SPECIFICATION, "b_duty_label_probe")

    assert "PUMP_A          WET_WELL    DISCHARGE  PUMP_CURVE  OFF" in b_duty
    assert "PUMP_B          WET_WELL    DISCHARGE  PUMP_CURVE  ON" in b_duty
    assert a_duty.replace(";; Probe: a_duty", ";; Probe: MIRROR").replace(
        "PUMP_A          WET_WELL    DISCHARGE  PUMP_CURVE  ON",
        "PUMP_A          WET_WELL    DISCHARGE  PUMP_CURVE  OFF",
    ).replace(
        "PUMP_B          WET_WELL    DISCHARGE  PUMP_CURVE  OFF",
        "PUMP_B          WET_WELL    DISCHARGE  PUMP_CURVE  ON",
    ) == b_duty.replace(";; Probe: b_duty_label_probe", ";; Probe: MIRROR")


def test_render_exercises_required_swmm_semantics() -> None:
    rendered = render_probe(SPECIFICATION, "a_duty")

    assert "FLOW_ROUTING            DYNWAVE" in rendered
    assert "FORCE_MAIN_EQUATION     D-W" in rendered
    assert "THREADS                 1" in rendered
    assert "WET_WELL        0.0        3.0       1.5        CYLINDRICAL" in rendered
    assert "FORCE_MAIN      FORCE_MAIN" in rendered
    assert "PUMP_CURVE      PUMP3" in rendered
    assert rendered.endswith("\n")
