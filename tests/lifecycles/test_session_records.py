# ABOUTME: Tests strict parsing of durable lifecycle agent session status values.
# ABOUTME: Prevents missing or unknown raw status from becoming a valid failed session.

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

import pytest

from aec_bench.contracts.trial_record import LifecycleSessionRecord
from aec_bench.lifecycles.session_records import parse_lifecycle_session_records

_MISSING = object()


def _parse_session(
    tmp_path: Path,
    *,
    raw_status: object,
    attempt_status: Literal["submitted", "failed"] = "failed",
    execution_status: Literal["completed", "failed", "partial"] = "failed",
    payload_updates: Mapping[str, object] | None = None,
    missing_fields: tuple[str, ...] = (),
) -> list[LifecycleSessionRecord]:
    relative = Path("sessions/session-001/agent_result.json")
    result_path = tmp_path / relative
    result_path.parent.mkdir(parents=True)
    payload: dict[str, object] = {
        "session_id": "session-001",
        "checkpoint_ids": ["checkpoint-1"],
        "model": "test-model",
        "resolved_model": "test-model",
        "adapter": "tool_loop",
        "adapter_name": "tool_loop",
        "session_mode": "persistent",
        "memory_visibility_policy": "persistent_context",
        "max_turns": 5,
        "configuration_record": {"model": "test-model", "max_turns": 5},
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }
    if raw_status is not _MISSING:
        payload["status"] = raw_status
    payload.update(payload_updates or {})
    for field in missing_fields:
        payload.pop(field, None)
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    completed = execution_status == "completed"
    return parse_lifecycle_session_records(
        run_dir=tmp_path,
        artifact_references=(),
        state={
            "status": "complete" if completed else "running",
            "checkpoint_runs": [
                {
                    "checkpoint_id": "checkpoint-1",
                    "status": "submitted" if attempt_status == "submitted" else "active",
                    "attempts": [
                        {
                            "session_id": "session-001",
                            "status": attempt_status,
                            "execution_mode": "persistent_context",
                        }
                    ],
                }
            ],
        },
        declared_run_artifacts={relative.as_posix(): "0" * 64},
        requested_model="test-model",
        requested_adapter="tool_loop",
        execution_mode="persistent_context",
        memory_visibility_policy="persistent_context",
        max_turns_per_session=5,
        execution_status=execution_status,
        verification={
            "overall": "complete" if completed else "incomplete",
            "reward": 1.0 if completed else 0.0,
        },
    )


@pytest.mark.parametrize("raw_status", [_MISSING, "forged", "ok"])
def test_session_parser_rejects_missing_or_unknown_status(tmp_path: Path, raw_status: object) -> None:
    with pytest.raises(ValueError, match="lifecycle session status is invalid"):
        _parse_session(tmp_path, raw_status=raw_status)


@pytest.mark.parametrize(
    ("raw_status", "attempt_status", "execution_status", "expected"),
    [
        ("completed", "submitted", "completed", "completed"),
        ("failed", "failed", "failed", "failed"),
        ("partial", "failed", "failed", "partial"),
    ],
)
def test_session_parser_preserves_supported_status_values(
    tmp_path: Path,
    raw_status: str,
    attempt_status: Literal["submitted", "failed"],
    execution_status: Literal["completed", "failed", "partial"],
    expected: Literal["completed", "failed", "partial"],
) -> None:
    sessions = _parse_session(
        tmp_path,
        raw_status=raw_status,
        attempt_status=attempt_status,
        execution_status=execution_status,
    )

    assert [session.status for session in sessions] == [expected]


@pytest.mark.parametrize("raw_value", [_MISSING, "", "   "])
def test_session_parser_rejects_missing_or_blank_resolved_model(tmp_path: Path, raw_value: object) -> None:
    updates = {} if raw_value is _MISSING else {"resolved_model": raw_value}
    missing = ("resolved_model",) if raw_value is _MISSING else ()

    with pytest.raises(ValueError, match="lifecycle session resolved model is invalid"):
        _parse_session(
            tmp_path,
            raw_status="failed",
            payload_updates=updates,
            missing_fields=missing,
        )


@pytest.mark.parametrize("field", ["model", "adapter", "adapter_name", "resolved_model"])
@pytest.mark.parametrize("raw_value", [_MISSING, 7])
def test_session_parser_rejects_missing_or_non_string_identity(
    tmp_path: Path,
    field: str,
    raw_value: object,
) -> None:
    updates = {} if raw_value is _MISSING else {field: raw_value}
    missing = (field,) if raw_value is _MISSING else ()

    with pytest.raises(ValueError, match="lifecycle session .* is invalid"):
        _parse_session(
            tmp_path,
            raw_status="failed",
            payload_updates=updates,
            missing_fields=missing,
        )


@pytest.mark.parametrize(
    ("raw_value", "message"),
    [
        (_MISSING, "lifecycle session max_turns is invalid"),
        (True, "lifecycle session max_turns is invalid"),
        (1.0, "lifecycle session max_turns is invalid"),
        ("1", "lifecycle session max_turns is invalid"),
        ("5", "lifecycle session max_turns is invalid"),
        (0, "lifecycle session max_turns is invalid"),
        (-1, "lifecycle session max_turns is invalid"),
        (6, "lifecycle session max_turns does not match invocation"),
    ],
)
def test_session_parser_rejects_invalid_or_mismatched_max_turns(
    tmp_path: Path,
    raw_value: object,
    message: str,
) -> None:
    updates = {} if raw_value is _MISSING else {"max_turns": raw_value}
    missing = ("max_turns",) if raw_value is _MISSING else ()

    with pytest.raises(ValueError, match=message):
        _parse_session(
            tmp_path,
            raw_status="failed",
            payload_updates=updates,
            missing_fields=missing,
        )


@pytest.mark.parametrize(
    "field",
    ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens"],
)
@pytest.mark.parametrize("raw_value", [_MISSING, True, 1.0, "1", "0", -1])
def test_session_parser_rejects_missing_or_invalid_token_count(
    tmp_path: Path,
    field: str,
    raw_value: object,
) -> None:
    updates = {} if raw_value is _MISSING else {field: raw_value}
    missing = (field,) if raw_value is _MISSING else ()

    with pytest.raises(ValueError, match=rf"lifecycle session {field} is invalid"):
        _parse_session(
            tmp_path,
            raw_status="failed",
            payload_updates=updates,
            missing_fields=missing,
        )
