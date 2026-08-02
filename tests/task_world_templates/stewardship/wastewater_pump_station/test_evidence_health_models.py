# ABOUTME: Defines the frozen evidence-health and treatment contracts through tests.
# ABOUTME: Checks exact time limits, quality rules, provenance fields, and host-private bindings.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evidence_health import (
    PUMP_STATION_EVIDENCE_DELAY_SECONDS,
    PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS,
    PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
    PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    PumpStationEvidenceHealth,
    PumpStationEvidenceQuality,
    PumpStationEvidenceTreatmentClass,
    PumpStationEvidenceTreatmentRequest,
    evidence_quality_at,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_control import (
    PumpStationEvidenceControlRequest,
)


def _treatment_request(
    **changes: object,
) -> PumpStationEvidenceTreatmentRequest:
    values: dict[str, object] = {
        "request_id": "treatment-request-001",
        "run_id": "run-evidence-health",
        "episode_id": "episode-evidence-health",
        "world_branch_id": "branch-evidence-health",
        "base_state_id": "state-before-treatment",
        "base_commit_id": "commit-before-treatment",
        "based_on_sequence": 4,
        "treatment_class": PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE,
        "treatment_version": PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1,
        "target_source_id": "station-condition-sensor",
        "effective_decision_point_seconds": 86_400,
        "visibility_policy": PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1,
    }
    values.update(changes)
    return PumpStationEvidenceTreatmentRequest(**values)  # type: ignore[arg-type]


def test_frozen_evidence_health_values_are_exact() -> None:
    assert PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS == 28_800
    assert PUMP_STATION_EVIDENCE_DELAY_SECONDS == 28_800
    assert PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1 == "pump-station-evidence-treatment.v1"
    assert PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1 == "actor-effect-only.v1"
    assert tuple(PumpStationEvidenceQuality) == (
        PumpStationEvidenceQuality.CURRENT,
        PumpStationEvidenceQuality.SUSPECT,
        PumpStationEvidenceQuality.UNAVAILABLE,
    )
    assert {item.value for item in PumpStationEvidenceTreatmentClass} == {
        "calibration_lapse",
        "evidence_delay",
        "stale_sample",
        "contradictory_report",
        "observation_loss",
        "baseline_change",
    }


def test_staleness_starts_only_after_the_exact_threshold() -> None:
    observed_at_seconds = 10_000

    assert (
        evidence_quality_at(
            PumpStationEvidenceQuality.CURRENT,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds + 28_800,
        )
        is PumpStationEvidenceQuality.CURRENT
    )
    assert (
        evidence_quality_at(
            PumpStationEvidenceQuality.CURRENT,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds + 28_801,
        )
        is PumpStationEvidenceQuality.SUSPECT
    )
    assert (
        evidence_quality_at(
            PumpStationEvidenceQuality.UNAVAILABLE,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds + 28_801,
        )
        is PumpStationEvidenceQuality.UNAVAILABLE
    )
    with pytest.raises(ValueError, match="before observation time"):
        evidence_quality_at(
            PumpStationEvidenceQuality.CURRENT,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds - 1,
        )


def test_health_record_requires_complete_ordered_provenance() -> None:
    health = PumpStationEvidenceHealth(
        observed_at_seconds=7_200,
        produced_at_seconds=7_260,
        available_at_seconds=7_320,
        source_id="station-condition-sensor",
        component_scope=("pump-a",),
        baseline_id="pump-a-post-maintenance-baseline.v1",
        operating_regime_id="pump-a-standby.v1",
        accepted=True,
        quality=PumpStationEvidenceQuality.CURRENT,
        contradicts_evidence_id="evidence-0001",
        supersedes_evidence_id="evidence-0000",
    )

    assert health.observed_at_seconds == 7_200
    assert health.component_scope == ("pump-a",)
    assert health.accepted is True

    with pytest.raises(ValueError, match="observation, production, and availability"):
        PumpStationEvidenceHealth(
            observed_at_seconds=7_200,
            produced_at_seconds=7_100,
            available_at_seconds=7_320,
            source_id="station-condition-sensor",
            component_scope=("pump-a",),
            baseline_id="baseline.v1",
            operating_regime_id="standby.v1",
            accepted=True,
            quality=PumpStationEvidenceQuality.CURRENT,
        )
    with pytest.raises(ValueError, match="component_scope"):
        PumpStationEvidenceHealth(
            observed_at_seconds=7_200,
            produced_at_seconds=7_260,
            available_at_seconds=7_320,
            source_id="station-condition-sensor",
            component_scope=(),
            baseline_id="baseline.v1",
            operating_regime_id="standby.v1",
            accepted=True,
            quality=PumpStationEvidenceQuality.CURRENT,
        )


def test_treatment_request_binds_the_complete_private_control_intent() -> None:
    request = _treatment_request()

    assert request.treatment_class is PumpStationEvidenceTreatmentClass.CALIBRATION_LAPSE
    assert request.based_on_sequence == 4
    assert request.effective_decision_point_seconds == 86_400

    with pytest.raises(ValueError, match="treatment version"):
        _treatment_request(treatment_version="pump-station-evidence-treatment.v2")
    with pytest.raises(ValueError, match="visibility policy"):
        _treatment_request(visibility_policy="show-treatment-identity")
    with pytest.raises(ValueError, match="based_on_sequence"):
        _treatment_request(based_on_sequence=-1)
    with pytest.raises(ValueError, match="treatment_class"):
        _treatment_request(treatment_class="arbitrary_evidence_insertion")


def test_evidence_control_rejects_unknown_operations_and_raw_state() -> None:
    base = {
        "request_id": "treatment-request-001",
        "operation": "schedule_evidence_treatment",
        "task_world_id": "wastewater-pump-station",
        "authority_id": "host-evidence",
        "treatment_request": _treatment_request(),
    }

    with pytest.raises(ValidationError, match="Input should be"):
        PumpStationEvidenceControlRequest.model_validate({**base, "operation": "replace_state"})
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PumpStationEvidenceControlRequest.model_validate({**base, "state": {"quality": "current"}})
