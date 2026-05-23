# ABOUTME: Well-known audit finding payload contract for review-style benchmark tasks in aec-bench.
# ABOUTME: Defines standardized severity and discipline values for structured findings output.

from enum import StrEnum

from pydantic import field_validator

from aec_bench.contracts.validators import StrictModel, ensure_non_empty_string


class Severity(StrEnum):
    COSMETIC = "cosmetic"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Discipline(StrEnum):
    GENERAL = "General"
    HAZARDOUS_MATERIALS = "Hazardous materials"
    SURVEY_MAPPING = "Survey/Mapping"
    GEOTECHNICAL = "Geotechnical"
    CIVIL = "Civil"
    LANDSCAPE = "Landscape"
    STRUCTURAL = "Structural"
    ARCHITECTURAL = "Architectural"
    INTERIORS = "Interiors"
    FIRE_PROTECTION = "Fire protection"
    PLUMBING = "Plumbing"
    MECHANICAL = "Mechanical"
    ELECTRICAL = "Electrical"
    TELECOMMUNICATIONS = "Telecommunications"
    RESOURCE = "Resource"
    OTHER_DISCIPLINES = "Other disciplines"
    OPERATIONS = "Operations"


class AuditFinding(StrictModel):
    title: str
    severity: Severity
    discipline: Discipline
    sheet_number: str | None = None
    location: str | None = None
    measured_value: str | None = None
    expected_value: str | None = None
    standard_reference: str | None = None
    rationale: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return ensure_non_empty_string(value)
