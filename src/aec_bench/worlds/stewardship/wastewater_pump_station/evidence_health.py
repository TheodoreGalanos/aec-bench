# ABOUTME: Defines the evidence-quality values used by the current coupled pump world.
# ABOUTME: Contains no host treatment command, schedule, or historical runtime contract.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

PUMP_STATION_EVIDENCE_STALE_AFTER_SECONDS = 28_800


class PumpStationEvidenceQuality(StrEnum):
    """Permitted actor-visible quality of an observation or evidence item."""

    CURRENT = "current"
    SUSPECT = "suspect"
    UNAVAILABLE = "unavailable"


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
    """Complete provenance and base quality for one current evidence item."""

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
        for field_name in ("observed_at_seconds", "produced_at_seconds", "available_at_seconds"):
            _require_non_negative(getattr(self, field_name), field_name)
        if not (self.observed_at_seconds <= self.produced_at_seconds <= self.available_at_seconds):
            raise ValueError("observation, production, and availability times must be ordered")
        for field_name in ("source_id", "baseline_id", "operating_regime_id"):
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
        for field_name in ("contradicts_evidence_id", "supersedes_evidence_id"):
            value = getattr(self, field_name)
            if value is not None:
                _require_text(value, field_name)
