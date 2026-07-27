# ABOUTME: Tests the disposable ASW-0B3 probe declaration and its B1/B2 boundary.
# ABOUTME: Prevents research fixtures from acquiring transfer, degradation, or promotion semantics.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from asw_b3_swmm.specification import SpecificationError, load_specification

SPIKE_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = SPIKE_ROOT / "fixtures" / "spike-probes.json"


def test_fixture_is_non_promotable_and_preserves_b1_topology() -> None:
    specification = load_specification(FIXTURE_PATH)

    assert specification.authority.stage == "ASW-0B3"
    assert specification.authority.scope == "spike_only"
    assert specification.authority.promotable is False
    assert specification.authority.world_parameters_selected is False
    assert specification.components == ("PUMP_A", "PUMP_B")
    assert tuple(probe.probe_id for probe in specification.probes) == (
        "a_duty",
        "b_duty_label_probe",
    )
    assert {(probe.active_pump, probe.inactive_pump) for probe in specification.probes} == {
        ("PUMP_A", "PUMP_B"),
        ("PUMP_B", "PUMP_A"),
    }


def test_fixture_uses_only_b3_engine_diagnostics() -> None:
    raw_text = FIXTURE_PATH.read_text(encoding="utf-8").lower()

    forbidden_semantics = (
        "obstruction",
        "degradation",
        "failure_rate",
        "maintenance",
        "intervention",
        "handover",
        "obligation",
        "transfer_time",
        "transfer_trigger",
        "load_sharing",
    )
    assert all(term not in raw_text for term in forbidden_semantics)


def test_loader_rejects_authority_expansion(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["authority"]["promotable"] = True
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SpecificationError, match="must remain non-promotable"):
        load_specification(invalid_path)


def test_loader_rejects_non_mirror_probe_pair(tmp_path: Path) -> None:
    raw = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    raw["probes"][1]["active_pump"] = "PUMP_A"
    raw["probes"][1]["inactive_pump"] = "PUMP_B"
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(SpecificationError, match="exactly one mirrored probe"):
        load_specification(invalid_path)
