# ABOUTME: Tests for well-known task payload contracts in the aec-bench contracts package.
# ABOUTME: These tests cover audit findings and calculation-result boundary shapes.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.payloads.audit_finding import AuditFinding, Discipline, Severity
from aec_bench.contracts.payloads.calculation_result import CalculationResult

# --- AuditFinding ---


def test_audit_finding_accepts_valid_payload() -> None:
    finding = AuditFinding(
        title="Door clearance is insufficient",
        severity=Severity.HIGH,
        discipline=Discipline.ARCHITECTURAL,
        sheet_number="A3.2",
    )

    assert finding.severity is Severity.HIGH
    assert finding.discipline is Discipline.ARCHITECTURAL


def test_audit_finding_accepts_all_optional_fields() -> None:
    finding = AuditFinding(
        title="Voltage drop exceeds 5%",
        severity=Severity.CRITICAL,
        discipline=Discipline.ELECTRICAL,
        sheet_number="E2.1",
        location="Panel DB-3 to receptacle circuit",
        measured_value="6.2%",
        expected_value="<= 5%",
        standard_reference="AS/NZS 3000:2018 C6.3",
        rationale="Voltage drop exceeds allowable limit for branch circuits.",
    )

    assert finding.location is not None
    assert finding.standard_reference is not None


def test_audit_finding_rejects_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        AuditFinding.model_validate(
            {
                "title": "Bad finding",
                "severity": "urgent",
                "discipline": Discipline.ARCHITECTURAL,
                "sheet_number": "A3.2",
            }
        )


def test_audit_finding_rejects_invalid_discipline() -> None:
    with pytest.raises(ValidationError):
        AuditFinding.model_validate(
            {
                "title": "Bad finding",
                "severity": "high",
                "discipline": "Dentistry",
            }
        )


def test_audit_finding_rejects_blank_title() -> None:
    with pytest.raises(ValidationError):
        AuditFinding(
            title="   ",
            severity=Severity.LOW,
            discipline=Discipline.GENERAL,
        )


def test_audit_finding_roundtrip_serialization() -> None:
    original = AuditFinding(
        title="Missing fire rating",
        severity=Severity.CRITICAL,
        discipline=Discipline.FIRE_PROTECTION,
        sheet_number="A5.1",
        location="Door D-14",
        measured_value="FRL 0/0/0",
        expected_value="FRL -/60/30",
    )

    serialized = original.model_dump(mode="json")
    restored = AuditFinding.model_validate(serialized)

    assert restored == original


# --- CalculationResult ---


def test_calculation_result_accepts_valid_payload() -> None:
    result = CalculationResult(parameter="voltage_drop_percent", value=3.6, unit="%")

    assert result.parameter == "voltage_drop_percent"


def test_calculation_result_accepts_with_optional_fields() -> None:
    result = CalculationResult(
        parameter="heat_load_kw",
        value=45.2,
        unit="kW",
        method="ASHRAE RTS",
        inputs={"area_m2": 120, "occupancy": 40},
    )

    assert result.method == "ASHRAE RTS"
    assert result.inputs is not None
    assert result.inputs["area_m2"] == 120


def test_calculation_result_rejects_blank_parameter() -> None:
    with pytest.raises(ValidationError):
        CalculationResult(parameter="   ", value=1.0, unit="kW")


def test_calculation_result_rejects_blank_unit() -> None:
    with pytest.raises(ValidationError):
        CalculationResult(parameter="voltage_drop", value=1.0, unit="  ")


def test_calculation_result_roundtrip_serialization() -> None:
    original = CalculationResult(
        parameter="voltage_drop_percent",
        value=3.6,
        unit="%",
        method="AS/NZS 3000",
        inputs={"cable_length_m": 50},
    )

    serialized = original.model_dump(mode="json")
    restored = CalculationResult.model_validate(serialized)

    assert restored == original
