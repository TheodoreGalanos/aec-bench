# ABOUTME: Tests the evidence-quality values used by the current coupled pump runtime.
# ABOUTME: Excludes the removed evidence-treatment command and session contracts.

from __future__ import annotations

import pytest

from aec_bench.worlds.stewardship.wastewater_pump_station.evidence_health import (
    PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS,
    PumpStationEvidenceHealth,
    PumpStationEvidenceQuality,
    evidence_quality_at,
)


def test_current_evidence_becomes_suspect_only_after_the_stale_threshold() -> None:
    observed_at_seconds = 10_000

    assert (
        evidence_quality_at(
            PumpStationEvidenceQuality.CURRENT,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds + PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS,
        )
        is PumpStationEvidenceQuality.CURRENT
    )
    assert (
        evidence_quality_at(
            PumpStationEvidenceQuality.CURRENT,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds + PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS + 1,
        )
        is PumpStationEvidenceQuality.SUSPECT
    )
    with pytest.raises(ValueError, match="before observation time"):
        evidence_quality_at(
            PumpStationEvidenceQuality.CURRENT,
            observed_at_seconds=observed_at_seconds,
            now_seconds=observed_at_seconds - 1,
        )


def test_current_evidence_health_requires_ordered_provenance_times() -> None:
    health = PumpStationEvidenceHealth(
        observed_at_seconds=7_200,
        produced_at_seconds=7_260,
        available_at_seconds=7_320,
        source_id="station-condition-sensor",
        component_scope=("pump-a",),
        baseline_id="pump-a-post-maintenance-baseline",
        operating_regime_id="pump-a-standby",
        accepted=True,
        quality=PumpStationEvidenceQuality.CURRENT,
    )

    assert health.accepted is True
    with pytest.raises(ValueError, match="observation, production, and availability"):
        PumpStationEvidenceHealth(
            observed_at_seconds=7_200,
            produced_at_seconds=7_100,
            available_at_seconds=7_320,
            source_id="station-condition-sensor",
            component_scope=("pump-a",),
            baseline_id="baseline",
            operating_regime_id="standby",
            accepted=True,
            quality=PumpStationEvidenceQuality.CURRENT,
        )
