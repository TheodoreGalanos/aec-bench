# ABOUTME: Proves Prime world trajectory metrics come only from retained machine and attributed human evidence.
# ABOUTME: Covers treatment delivery, actor efficiency, report review, and fail-closed evidence parsing.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import pytest

from aec_bench.experimentation.qualification.pump_station_prime_trajectory import (
    GUIDANCE_ID,
    PrimeTrajectoryEvidenceError,
    analyze_pump_station_prime_trial,
)

LoadState = Literal["before", "after", "failed", "absent"]


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(value) + "\n" for value in values), encoding="utf-8")


def _assistant_message(call: int, *, tool_call: dict[str, Any] | None = None, text: str = "") -> dict[str, Any]:
    content: list[dict[str, Any]] = []
    if tool_call is not None:
        content.append(tool_call)
    if text:
        content.append({"type": "text", "text": text})
    return {
        "type": "message",
        "id": f"assistant-{call}",
        "message": {
            "role": "assistant",
            "content": content,
            "usage": {
                "input": call * 100,
                "output": call * 10,
                "cacheRead": call * 2,
                "cacheWrite": call * 3,
                "totalTokens": call * 115,
            },
        },
    }


def _trial_fixture(tmp_path: Path, *, load_state: LoadState = "before") -> Path:
    trial = tmp_path / f"trial-{load_state}"
    evidence = trial / "evidence"
    evidence.mkdir(parents=True)
    guided = load_state != "absent"
    skill_call = {
        "type": "toolCall",
        "id": "load-guidance",
        "name": "ipython",
        "arguments": {
            "code": (
                "print(open('.prime-skills/pump-station-guidance/SKILL.md').read())\n"
                "print(open('references/compact-state.md').read())\n"
                "print(open('references/decision-method.md').read())"
            ),
        },
    }
    invoke_call = {
        "type": "toolCall",
        "id": "invoke-world",
        "name": "ipython",
        "arguments": {
            "code": (
                "compact = {'decision_id': 'decision-1'}\n"
                "action_ledger = []\n"
                "result = await aec_world.invoke('act', {}, decision_id='decision-1')\n"
                "action_ledger.append(result['status'])\n"
                "compact.update({'decision_id': result['next_decision_id']})\n"
                "print(result)"
            ),
        },
    }
    ordered_calls = [invoke_call]
    if load_state == "before":
        ordered_calls.insert(0, skill_call)
    elif load_state in {"after", "failed"}:
        ordered_calls.append(skill_call)
    session_events: list[dict[str, Any]] = [{"type": "session", "id": "root", "rlmDepth": 0}]
    for call_number, tool_call in enumerate(ordered_calls, start=1):
        session_events.append(_assistant_message(call_number, tool_call=tool_call))
        is_skill = tool_call["id"] == "load-guidance"
        session_events.append(
            {
                "type": "message",
                "id": f"result-{call_number}",
                "message": {
                    "role": "toolResult",
                    "toolCallId": tool_call["id"],
                    "toolName": "ipython",
                    "isError": is_skill and load_state == "failed",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "read failed"
                                if is_skill and load_state == "failed"
                                else GUIDANCE_ID
                                if is_skill
                                else '{"status": "applied", "next_observation": {}}'
                            ),
                        }
                    ],
                },
            }
        )
    final_call = len(ordered_calls) + 1
    session_events.append(_assistant_message(final_call, text="I made five world action attempts."))
    _write_jsonl(evidence / "prime-session.jsonl", session_events)
    _write_jsonl(
        evidence / "prime-acp-out.jsonl",
        [{"jsonrpc": "2.0", "method": "session/update", "params": {"_meta": {"compaction": {"count": 1}}}}],
    )
    skills = [{"order": 0, "name": "aec-world", "sha256": "generic-digest"}]
    if guided:
        skills.append({"order": 1, "name": "pump-station-guidance", "sha256": "guidance-digest"})
    _write_json(evidence / "prime-run.json", {"skills": skills, "skill_sha256": "generic-digest"})

    actor_events = [
        {"operation": "capabilities", "request": {"operation": "capabilities"}, "result": {}},
        {"operation": "observe", "request": {"operation": "observe"}, "result": {}},
        _invoke_event("request-1", "decision-1", "act", {"target": "one"}, status="applied"),
        _invoke_event("request-2", "decision-2", "act", {"target": "two"}, status="rejected"),
        _invoke_event(
            "request-3",
            "decision-2",
            "act",
            {"target": "bad"},
            error="actor-action-arguments",
        ),
        _invoke_event("request-4", "decision-2", "search", {"query": "record"}, status="NO_ACCESSIBLE_RESULT"),
        _invoke_event("request-5", "decision-2", "search", {"query": "record"}, status="NO_ACCESSIBLE_RESULT"),
    ]
    _write_jsonl(evidence / "world-actor-transport.jsonl", actor_events)

    model_calls = len(ordered_calls) + 1
    total_tokens = sum(call * 115 for call in range(1, model_calls + 1))
    _write_json(
        trial / "trial-summary.json",
        {
            "trial_id": f"trial-{load_state}",
            "condition": "Guided" if guided else "Open",
            "prime": {
                "usage": {"total_tokens": total_tokens, "model_calls": model_calls, "cost_usd": "0.9"},
                "elapsed_seconds": 12.5,
                "topology": {"child_sessions": 0},
                "refinement": {"events": 0},
                "session_state": "ended",
                "stop_reason": "end_turn",
                "limit_reason": None,
            },
            "world": {
                "benchmark_valid": True,
                "state": "active",
                "completion": "incomplete",
                "verification": {
                    "valid": True,
                    "replay_valid": True,
                    "conservation": {
                        "duty": {"unserved_capacity_seconds": 0},
                        "work": {"terminal_ids": ["work-1"], "closing_ids": ["work-1", "work-2"]},
                    },
                },
                "evaluation": {"valid": True},
            },
        },
    )
    return trial


def _invoke_event(
    request_id: str,
    decision_id: str,
    action_name: str,
    arguments: dict[str, Any],
    *,
    status: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    return {
        "operation": "invoke",
        "request": {
            "operation": "invoke",
            "request_id": request_id,
            "decision_id": decision_id,
            "action_name": action_name,
            "arguments": arguments,
        },
        "result": None if status is None else {"status": status},
        "error": None if error is None else {"code": error, "detail": "fixture error"},
    }


def test_derives_guided_trajectory_and_leaves_report_quality_incomplete_without_review(tmp_path: Path) -> None:
    trial = _trial_fixture(tmp_path)

    analysis = analyze_pump_station_prime_trial(trial, large_output_threshold_chars=20)

    assert analysis.treatment == "guided"
    assert analysis.model_context == {
        "reported_input_tokens_sum": 600,
        "input_tokens_median": 200.0,
        "input_tokens_p90": 280.0,
        "input_tokens_max": 300,
        "output_tokens_sum": 60,
        "cache_read_tokens_sum": 12,
        "cache_write_tokens_sum": 18,
        "reported_total_tokens_sum": 690,
    }
    assert analysis.notebook["ipython_cells"] == 2
    assert analysis.notebook["full_object_output_cells"] == 1
    assert analysis.notebook["compact_state_cells"] == 1
    assert analysis.notebook["compact_state_update_cells"] == 1
    assert analysis.notebook["action_ledger_cells"] == 1
    assert analysis.notebook["action_ledger_append_cells"] == 1
    assert analysis.notebook["invoke_cells"] == 1
    assert analysis.notebook["invoke_and_ledger_append_cells"] == 1
    assert analysis.notebook["invoke_and_compact_state_update_cells"] == 1
    assert analysis.notebook["invoke_and_print_cells"] == 1
    assert analysis.notebook["invoke_ledger_colocation_rate"] == 1.0
    assert analysis.notebook["invoke_compact_state_colocation_rate"] == 1.0
    assert analysis.notebook["first_invoke_model_call"] == 2
    assert analysis.notebook["last_invoke_model_call"] == 2
    assert analysis.notebook["model_calls_before_first_invoke"] == 1
    assert analysis.actor_transport["operations"] == {"capabilities": 1, "observe": 1, "invoke": 5}
    assert analysis.actor_transport["invoke_statuses"] == {
        "applied": 1,
        "rejected": 1,
        "actor-action-arguments": 1,
        "NO_ACCESSIBLE_RESULT": 2,
    }
    assert analysis.actor_transport["repeated_equivalent_requests_in_unchanged_state"] == 1
    assert analysis.efficiency["tokens_per_applied_transition"] == 690.0
    assert analysis.efficiency["model_calls_per_applied_transition"] == 3.0
    assert analysis.efficiency["actions_per_model_call"] == pytest.approx(5 / 3)
    assert analysis.efficiency["elapsed_seconds"] == 12.5
    assert analysis.prime_features["explicit_compaction_events"] == 1
    assert analysis.treatment_integrity == {
        "guidance_available": True,
        "guidance_loaded": True,
        "guidance_loaded_before_first_invoke": True,
        "guidance_id": GUIDANCE_ID,
        "reference_loads": ["compact-state.md", "decision-method.md"],
    }
    assert analysis.world_progress["unserved_capacity_seconds"] == 0
    assert analysis.world_progress["terminal_work_count"] == 1
    assert analysis.report_quality["status"] == "incomplete"
    assert analysis.report_quality["action_ledger_recall"] is None


@pytest.mark.parametrize(
    ("load_state", "available", "loaded", "before"),
    [
        ("before", True, True, True),
        ("after", True, True, False),
        ("failed", True, False, False),
        ("absent", False, False, False),
    ],
)
def test_distinguishes_treatment_availability_and_delivery(
    tmp_path: Path,
    load_state: LoadState,
    available: bool,
    loaded: bool,
    before: bool,
) -> None:
    analysis = analyze_pump_station_prime_trial(_trial_fixture(tmp_path, load_state=load_state))

    assert analysis.treatment_integrity["guidance_available"] is available
    assert analysis.treatment_integrity["guidance_loaded"] is loaded
    assert analysis.treatment_integrity["guidance_loaded_before_first_invoke"] is before


def test_recognizes_a_legacy_versioned_guidance_marker(tmp_path: Path) -> None:
    trial = _trial_fixture(tmp_path)
    session_file = trial / "evidence" / "prime-session.jsonl"
    session_file.write_text(
        session_file.read_text(encoding="utf-8").replace(
            GUIDANCE_ID,
            "aecbench.pump-station-guidance.v1",
        ),
        encoding="utf-8",
    )

    analysis = analyze_pump_station_prime_trial(trial)

    assert analysis.treatment_integrity["guidance_loaded"] is True
    assert analysis.treatment_integrity["guidance_id"] == GUIDANCE_ID


def test_uses_attributed_human_review_for_final_report_metrics(tmp_path: Path) -> None:
    trial = _trial_fixture(tmp_path)
    review = {
        "rubric_id": "aecbench.prime-world-report-review.v1",
        "reviewer": "reviewer@example.test",
        "reviewed_at": datetime(2026, 8, 7, tzinfo=UTC).isoformat(),
        "canonical_invoke_count": 5,
        "reported_invoke_count": 4,
        "matched_invoke_count": 4,
        "correctly_classified_invoke_count": 4,
        "pending_liability_claim_count": 2,
        "correct_pending_liability_claim_count": 1,
        "unsupported_claim_count": 1,
        "evidence_references": ["evidence/world-actor-transport.jsonl", "evidence/prime-session.jsonl"],
    }
    _write_json(trial / "report-review.json", review)

    report = analyze_pump_station_prime_trial(trial).report_quality

    assert report["status"] == "complete"
    assert report["rubric_id"] == "aecbench.prime-world-report-review.v1"
    assert report["action_ledger_recall"] == 0.8
    assert report["action_outcome_classification_accuracy"] == 0.8
    assert report["pending_liability_accuracy"] == 0.5
    assert report["unsupported_claim_count"] == 1

    review["canonical_invoke_count"] = 4
    _write_json(trial / "report-review.json", review)
    with pytest.raises(PrimeTrajectoryEvidenceError, match="canonical invoke count"):
        analyze_pump_station_prime_trial(trial)


def test_cancelled_session_does_not_treat_planning_text_as_a_final_report(tmp_path: Path) -> None:
    trial = _trial_fixture(tmp_path)
    summary = json.loads((trial / "trial-summary.json").read_text(encoding="utf-8"))
    summary["prime"]["session_state"] = "cancelled"
    summary["prime"]["stop_reason"] = "cancelled"
    summary["prime"]["limit_reason"] = "max_model_calls"
    _write_json(trial / "trial-summary.json", summary)

    analysis = analyze_pump_station_prime_trial(trial)

    assert analysis.notebook["final_assistant_text_chars"] == 0
    assert analysis.report_quality["final_report_present"] is False
