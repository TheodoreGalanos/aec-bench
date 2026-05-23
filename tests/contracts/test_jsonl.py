# ABOUTME: Tests for JSONL helper functions in the aec-bench contracts package.
# ABOUTME: These tests define line-oriented serialization behavior for dicts and Pydantic models.

from pathlib import Path
from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.jsonl import read_jsonl, write_jsonl
from aec_bench.contracts.payloads.audit_finding import AuditFinding, Discipline, Severity


def test_jsonl_roundtrip_for_dict_records(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    payload: list[dict[str, Any]] = [{"status": "ok"}, {"count": 2}]

    write_jsonl(path, payload)

    assert read_jsonl(path) == payload


def test_jsonl_writes_pydantic_models_as_json_objects(tmp_path: Path) -> None:
    path = tmp_path / "records.jsonl"
    payload = [
        AgentOutput(
            status=AgentOutputStatus.EMPTY,
            output_path="/workspace/output.jsonl",
            output_format="jsonl",
        )
    ]

    write_jsonl(path, payload)

    assert read_jsonl(path) == [
        {
            "status": "empty",
            "output_path": "/workspace/output.jsonl",
            "output_format": "jsonl",
            "error_message": None,
        }
    ]


def test_jsonl_creates_parent_directories(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "deep" / "records.jsonl"

    write_jsonl(path, [{"key": "value"}])

    assert read_jsonl(path) == [{"key": "value"}]


def test_jsonl_handles_empty_records_list(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"

    write_jsonl(path, [])

    assert read_jsonl(path) == []


def test_jsonl_skips_blank_lines(tmp_path: Path) -> None:
    path = tmp_path / "blanks.jsonl"
    path.write_text('{"a": 1}\n\n{"b": 2}\n\n', encoding="utf-8")

    records = read_jsonl(path)

    assert records == [{"a": 1}, {"b": 2}]


def test_jsonl_roundtrip_audit_finding_models(tmp_path: Path) -> None:
    path = tmp_path / "findings.jsonl"
    findings = [
        AuditFinding(
            title="Missing fire rating",
            severity=Severity.CRITICAL,
            discipline=Discipline.FIRE_PROTECTION,
        ),
        AuditFinding(
            title="Clearance violation",
            severity=Severity.HIGH,
            discipline=Discipline.ARCHITECTURAL,
            sheet_number="A3.2",
        ),
    ]

    write_jsonl(path, findings)
    records = read_jsonl(path)

    assert len(records) == 2
    assert records[0]["title"] == "Missing fire rating"
    assert records[1]["sheet_number"] == "A3.2"


def test_jsonl_deterministic_key_ordering(tmp_path: Path) -> None:
    path = tmp_path / "ordered.jsonl"

    write_jsonl(path, [{"zebra": 1, "alpha": 2, "mango": 3}])

    raw_line = path.read_text(encoding="utf-8").strip()
    assert raw_line.startswith('{"alpha":')


def test_jsonl_roundtrip_evaluation_result_model(tmp_path: Path) -> None:
    path = tmp_path / "evals.jsonl"
    result = EvaluationResult(
        reward=0.8,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=True,
        ),
    )

    write_jsonl(path, [result])
    records = read_jsonl(path)

    restored = EvaluationResult.model_validate(records[0])
    assert restored == result
