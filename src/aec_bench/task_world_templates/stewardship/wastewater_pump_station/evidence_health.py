# ABOUTME: Defines task-owned evidence-health records and deterministic treatment contracts.
# ABOUTME: Keeps ASW-6A quality, timing, provenance, and host-private control rules local.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_models import (
    PumpStationObservation,
)

PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS = 28_800
PUMP_STATION_EVIDENCE_DELAY_SECONDS = 28_800
PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1 = "pump-station-evidence-treatment.v1"
PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1 = "actor-effect-only.v1"


class PumpStationEvidenceQuality(StrEnum):
    """Permitted actor-visible quality of an observation or evidence item."""

    CURRENT = "current"
    SUSPECT = "suspect"
    UNAVAILABLE = "unavailable"


class PumpStationEvidenceTreatmentClass(StrEnum):
    """Closed ASW-6A treatment catalogue."""

    CALIBRATION_LAPSE = "calibration_lapse"
    EVIDENCE_DELAY = "evidence_delay"
    STALE_SAMPLE = "stale_sample"
    CONTRADICTORY_REPORT = "contradictory_report"
    OBSERVATION_LOSS = "observation_loss"
    BASELINE_CHANGE = "baseline_change"


class PumpStationEvidenceTreatmentStatus(StrEnum):
    """Private lifecycle state of one scheduled treatment."""

    SCHEDULED = "scheduled"
    ACTIVE = "active"
    APPLIED = "applied"


def _require_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty")


def _require_non_negative(value: object, field_name: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def evidence_quality_at(
    source_quality: PumpStationEvidenceQuality,
    *,
    observed_at_seconds: int,
    now_seconds: int,
) -> PumpStationEvidenceQuality:
    """Return public quality with age computed at projection time."""
    if not isinstance(source_quality, PumpStationEvidenceQuality):
        raise ValueError("source_quality must be a permitted evidence quality")
    _require_non_negative(observed_at_seconds, "observed_at_seconds")
    _require_non_negative(now_seconds, "now_seconds")
    if now_seconds < observed_at_seconds:
        raise ValueError("current time is before observation time")
    if source_quality is PumpStationEvidenceQuality.UNAVAILABLE:
        return source_quality
    if now_seconds - observed_at_seconds > PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS:
        return PumpStationEvidenceQuality.SUSPECT
    return source_quality


@dataclass(frozen=True, slots=True)
class PumpStationEvidenceHealth:
    """Complete provenance and base quality for one evidence item."""

    observed_at_seconds: int
    produced_at_seconds: int
    available_at_seconds: int
    source_id: str
    component_scope: tuple[str, ...]
    baseline_id: str
    operating_regime_id: str
    accepted: bool
    quality: PumpStationEvidenceQuality
    contradicts_evidence_id: str | None = None
    supersedes_evidence_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in (
            "observed_at_seconds",
            "produced_at_seconds",
            "available_at_seconds",
        ):
            _require_non_negative(getattr(self, field_name), field_name)
        if not (self.observed_at_seconds <= self.produced_at_seconds <= self.available_at_seconds):
            raise ValueError("observation, production, and availability times must be ordered")
        for field_name in (
            "source_id",
            "baseline_id",
            "operating_regime_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        if not self.component_scope:
            raise ValueError("component_scope must not be empty")
        for component_id in self.component_scope:
            _require_text(component_id, "component_scope")
        if len(set(self.component_scope)) != len(self.component_scope):
            raise ValueError("component_scope must not contain duplicates")
        if type(self.accepted) is not bool:
            raise ValueError("accepted must be a boolean")
        if not isinstance(self.quality, PumpStationEvidenceQuality):
            raise ValueError("quality must be a permitted evidence quality")
        for field_name in (
            "contradicts_evidence_id",
            "supersedes_evidence_id",
        ):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)


@dataclass(frozen=True, slots=True)
class PumpStationEvidenceTreatmentRequest:
    """Exact host-private request to schedule one deterministic treatment."""

    request_id: str
    run_id: str
    episode_id: str
    world_branch_id: str
    base_state_id: str
    base_commit_id: str
    based_on_sequence: int
    treatment_class: PumpStationEvidenceTreatmentClass
    treatment_version: str
    target_source_id: str
    effective_decision_point_seconds: int
    visibility_policy: str

    def __post_init__(self) -> None:
        for field_name in (
            "request_id",
            "run_id",
            "episode_id",
            "world_branch_id",
            "base_state_id",
            "base_commit_id",
            "target_source_id",
        ):
            _require_text(getattr(self, field_name), field_name)
        _require_non_negative(self.based_on_sequence, "based_on_sequence")
        _require_non_negative(
            self.effective_decision_point_seconds,
            "effective_decision_point_seconds",
        )
        if not isinstance(self.treatment_class, PumpStationEvidenceTreatmentClass):
            raise ValueError("treatment_class must be one of the approved six classes")
        if self.treatment_version != PUMP_STATION_EVIDENCE_TREATMENT_VERSION_V1:
            raise ValueError("unsupported treatment version")
        if self.visibility_policy != PUMP_STATION_EVIDENCE_VISIBILITY_POLICY_V1:
            raise ValueError("unsupported visibility policy")


@dataclass(frozen=True, slots=True)
class PumpStationObservationSource:
    """Private sensor source state used to produce one permitted public view."""

    source_id: str
    component_scope: tuple[str, ...]
    baseline_id: str
    operating_regime_id: str
    observation: PumpStationObservation
    observed_at_seconds: int
    produced_at_seconds: int
    available_at_seconds: int
    quality: PumpStationEvidenceQuality
    refresh_enabled: bool = True
    reading_available: bool = True

    def __post_init__(self) -> None:
        health = PumpStationEvidenceHealth(
            observed_at_seconds=self.observed_at_seconds,
            produced_at_seconds=self.produced_at_seconds,
            available_at_seconds=self.available_at_seconds,
            source_id=self.source_id,
            component_scope=self.component_scope,
            baseline_id=self.baseline_id,
            operating_regime_id=self.operating_regime_id,
            accepted=True,
            quality=self.quality,
        )
        if self.observation.sample_time_seconds != health.observed_at_seconds:
            raise ValueError("source observation time differs from its sample time")
        if type(self.refresh_enabled) is not bool or type(self.reading_available) is not bool:
            raise ValueError("source control fields must be boolean")


@dataclass(frozen=True, slots=True)
class PumpStationEvidenceTreatment:
    """Host-private manifest for one immutable deterministic treatment."""

    treatment_id: str
    request: PumpStationEvidenceTreatmentRequest
    status: PumpStationEvidenceTreatmentStatus
    scheduled_sequence: int
    activated_sequence: int | None = None
    activated_at_seconds: int | None = None

    def __post_init__(self) -> None:
        _require_text(self.treatment_id, "treatment_id")
        _require_non_negative(self.scheduled_sequence, "scheduled_sequence")
        if not isinstance(self.status, PumpStationEvidenceTreatmentStatus):
            raise ValueError("status must be a permitted treatment status")
        activation_values = (self.activated_sequence, self.activated_at_seconds)
        if self.status is PumpStationEvidenceTreatmentStatus.SCHEDULED:
            if activation_values != (None, None):
                raise ValueError("scheduled treatment cannot contain activation facts")
            return
        if any(value is None for value in activation_values):
            raise ValueError("active treatment requires complete activation facts")
        _require_non_negative(self.activated_sequence, "activated_sequence")
        _require_non_negative(self.activated_at_seconds, "activated_at_seconds")
