# ABOUTME: Derives read-only Prime world trajectory metrics from retained execution evidence.
# ABOUTME: Keeps treatment and process analysis separate from canonical world evaluation.

from __future__ import annotations

import json
import math
import re
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, JsonValue, model_validator

from aec_bench.contracts.validators import StrictModel

GUIDANCE_ID = "aecbench.pump-station-guidance"
_GUIDANCE_MARKER_PATTERN = re.compile(r"aecbench\.pump-station-guidance(?:\.v\d+)?")
_GUIDANCE_SKILL_NAME = "pump-station-guidance"
_GUIDANCE_REFERENCES = ("compact-state.md", "decision-method.md")


class PrimeTrajectoryEvidenceError(ValueError):
    """Raised when retained trial evidence cannot support trajectory analysis."""


class PrimeHumanReportReview(StrictModel):
    """Attributable human comparison of one final report with canonical evidence."""

    rubric_id: Literal["aecbench.prime-world-report-review.v1"] = "aecbench.prime-world-report-review.v1"
    reviewer: str = Field(min_length=1)
    reviewed_at: datetime
    canonical_invoke_count: int = Field(ge=0)
    reported_invoke_count: int = Field(ge=0)
    matched_invoke_count: int = Field(ge=0)
    correctly_classified_invoke_count: int = Field(ge=0)
    pending_liability_claim_count: int = Field(ge=0)
    correct_pending_liability_claim_count: int = Field(ge=0)
    unsupported_claim_count: int = Field(ge=0)
    evidence_references: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_counts(self) -> PrimeHumanReportReview:
        if self.matched_invoke_count > min(self.canonical_invoke_count, self.reported_invoke_count):
            raise ValueError("matched invoke count exceeds the canonical or reported count")
        if self.correctly_classified_invoke_count > self.matched_invoke_count:
            raise ValueError("classified invoke count exceeds the matched count")
        if self.correct_pending_liability_claim_count > self.pending_liability_claim_count:
            raise ValueError("correct pending-liability count exceeds the claimed count")
        if any(not reference.strip() for reference in self.evidence_references):
            raise ValueError("report review evidence references must be non-empty")
        return self


class PrimeWorldTrajectoryAnalysis(StrictModel):
    """One deterministic study projection that does not alter benchmark evaluation."""

    schema_id: Literal["aecbench.prime-world-trajectory.v1"] = "aecbench.prime-world-trajectory.v1"
    trial_id: str
    condition: str
    treatment: Literal["open", "guided"]
    large_output_threshold_chars: int = Field(gt=0)
    usage_by_call: tuple[dict[str, JsonValue], ...]
    model_context: dict[str, JsonValue]
    notebook: dict[str, JsonValue]
    actor_transport: dict[str, JsonValue]
    efficiency: dict[str, JsonValue]
    prime_features: dict[str, JsonValue]
    treatment_integrity: dict[str, JsonValue]
    world_progress: dict[str, JsonValue]
    report_quality: dict[str, JsonValue]


def analyze_prime_world_trial(
    trial_directory: Path,
    *,
    large_output_threshold_chars: int = 10_000,
    human_review_file: Path | None = None,
) -> PrimeWorldTrajectoryAnalysis:
    """Read one retained trial without invoking or re-evaluating its world."""
    if large_output_threshold_chars < 1:
        raise ValueError("large output threshold must be positive")
    trial_directory = trial_directory.resolve()
    evidence_directory = trial_directory / "evidence"
    summary = _read_json_object(trial_directory / "trial-summary.json")
    prime_run = _read_json_object(evidence_directory / "prime-run.json")
    session_events = _read_session_events(evidence_directory)
    actor_events = _read_jsonl(evidence_directory / "world-actor-transport.jsonl")

    messages = [
        _required_mapping(event.get("message"), "Prime message")
        for event in session_events
        if event.get("type") == "message"
    ]
    assistant_messages = [message for message in messages if message.get("role") == "assistant"]
    tool_result_messages = [message for message in messages if message.get("role") == "toolResult"]
    usage_by_call = _usage_by_call(assistant_messages)
    tool_calls, code_cells = _tool_calls(assistant_messages)
    invoke_cells = [code for code in code_cells if "aec_world.invoke(" in code]
    tool_results = _tool_results(tool_result_messages, tool_calls)
    actor = _actor_metrics(actor_events)
    treatment_integrity = _treatment_integrity(prime_run, tool_calls, tool_results)

    condition = _required_string(summary.get("condition"), "trial condition")
    treatment: Literal["open", "guided"] = (
        "guided" if treatment_integrity["guidance_available"] or "guided" in condition.lower() else "open"
    )
    prime_summary = _required_mapping(summary.get("prime"), "trial Prime summary")
    total_tokens = _required_int(
        _required_mapping(prime_summary.get("usage"), "trial Prime usage").get("total_tokens"),
        "total_tokens",
    )
    model_calls = _required_int(
        _required_mapping(prime_summary.get("usage"), "trial Prime usage").get("model_calls"),
        "model_calls",
    )
    elapsed_seconds = _required_float(prime_summary.get("elapsed_seconds"), "elapsed_seconds")
    cost_usd = _required_float(
        _required_mapping(prime_summary.get("usage"), "trial Prime usage").get("cost_usd"),
        "cost_usd",
    )
    applied = int(actor["invoke_statuses"].get("applied", 0))
    invoke_attempts = int(actor["operations"].get("invoke", 0))
    session_state = _required_string(prime_summary.get("session_state"), "Prime session state")
    stop_reason = _optional_string(prime_summary.get("stop_reason"), "Prime stop reason")
    limit_reason = _optional_string(prime_summary.get("limit_reason"), "Prime limit reason")

    input_values = [int(item["input_tokens"]) for item in usage_by_call]
    tool_lengths = [int(result["chars"]) for result in tool_results]
    final_text = (
        _final_assistant_text(assistant_messages) if session_state == "ended" and stop_reason == "end_turn" else ""
    )
    first_invoke_call = min(
        (
            int(call["ordinal"])
            for call in tool_calls
            if call["name"] == "ipython" and "aec_world.invoke(" in str(call["code"])
        ),
        default=None,
    )
    last_invoke_call = max(
        (
            int(call["ordinal"])
            for call in tool_calls
            if call["name"] == "ipython" and "aec_world.invoke(" in str(call["code"])
        ),
        default=None,
    )
    review_path = human_review_file or trial_directory / "report-review.json"
    report_quality = _report_quality(review_path, canonical_invoke_count=invoke_attempts, final_text=final_text)

    return PrimeWorldTrajectoryAnalysis(
        trial_id=_required_string(summary.get("trial_id"), "trial ID"),
        condition=condition,
        treatment=treatment,
        large_output_threshold_chars=large_output_threshold_chars,
        usage_by_call=tuple(usage_by_call),
        model_context={
            "reported_input_tokens_sum": sum(input_values),
            "input_tokens_median": _median(input_values),
            "input_tokens_p90": _percentile(input_values, 0.9),
            "input_tokens_max": max(input_values, default=0),
            "output_tokens_sum": sum(int(item["output_tokens"]) for item in usage_by_call),
            "cache_read_tokens_sum": sum(int(item["cache_read_tokens"]) for item in usage_by_call),
            "cache_write_tokens_sum": sum(int(item["cache_write_tokens"]) for item in usage_by_call),
            "reported_total_tokens_sum": sum(int(item["total_tokens"]) for item in usage_by_call),
        },
        notebook={
            "tool_calls": len(tool_calls),
            "tool_call_names": dict(Counter(str(call["name"]) for call in tool_calls)),
            "ipython_cells": len(code_cells),
            "full_object_output_cells": sum(1 for code in code_cells if _prints_full_object(code)),
            "compact_state_cells": sum(1 for code in code_cells if _uses_compact_state(code)),
            "compact_state_update_cells": sum(1 for code in code_cells if _updates_compact_state(code)),
            "action_ledger_cells": sum(1 for code in code_cells if _uses_action_ledger(code)),
            "action_ledger_append_cells": sum(1 for code in code_cells if _appends_action_ledger(code)),
            "invoke_cells": len(invoke_cells),
            "invoke_and_ledger_append_cells": sum(1 for code in invoke_cells if _appends_action_ledger(code)),
            "invoke_and_compact_state_update_cells": sum(1 for code in invoke_cells if _updates_compact_state(code)),
            "invoke_and_print_cells": sum(1 for code in invoke_cells if "print(" in code),
            "invoke_ledger_colocation_rate": _ratio(
                sum(1 for code in invoke_cells if _appends_action_ledger(code)), len(invoke_cells)
            ),
            "invoke_compact_state_colocation_rate": _ratio(
                sum(1 for code in invoke_cells if _updates_compact_state(code)), len(invoke_cells)
            ),
            "first_invoke_model_call": first_invoke_call,
            "last_invoke_model_call": last_invoke_call,
            "model_calls_before_first_invoke": None if first_invoke_call is None else first_invoke_call - 1,
            "tool_result_count": len(tool_results),
            "tool_result_error_count": sum(1 for result in tool_results if result["is_error"]),
            "tool_result_chars_total": sum(tool_lengths),
            "tool_result_chars_median": _median(tool_lengths),
            "tool_result_chars_p90": _percentile(tool_lengths, 0.9),
            "tool_result_chars_max": max(tool_lengths, default=0),
            "large_tool_result_count": sum(1 for length in tool_lengths if length >= large_output_threshold_chars),
            "largest_tool_result": max(tool_results, key=lambda result: int(result["chars"]), default=None),
            "final_assistant_text_chars": len(final_text),
        },
        actor_transport=actor,
        efficiency={
            "total_tokens": total_tokens,
            "model_calls": model_calls,
            "cost_usd": cost_usd,
            "elapsed_seconds": elapsed_seconds,
            "applied_transitions": applied,
            "tokens_per_applied_transition": _ratio(total_tokens, applied),
            "model_calls_per_applied_transition": _ratio(model_calls, applied),
            "cost_per_applied_transition": _ratio(cost_usd, applied),
            "actions_per_model_call": _ratio(invoke_attempts, model_calls),
            "applied_invoke_rate": _ratio(applied, invoke_attempts),
        },
        prime_features={
            "child_sessions": _nested_int(prime_summary, "topology", "child_sessions"),
            "refinement_events": _nested_int(prime_summary, "refinement", "events"),
            "explicit_compaction_events": _compaction_event_count(evidence_directory, session_events),
            "session_state": session_state,
            "stop_reason": stop_reason,
            "limit_reason": limit_reason,
        },
        treatment_integrity=treatment_integrity,
        world_progress=_world_progress(summary),
        report_quality=report_quality,
    )


def _read_session_events(evidence_directory: Path) -> list[dict[str, Any]]:
    paths = sorted(evidence_directory.glob("prime-session*.jsonl"))
    if not paths:
        raise PrimeTrajectoryEvidenceError("trial has no retained Prime session JSONL")
    return [event for path in paths for event in _read_jsonl(path)]


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PrimeTrajectoryEvidenceError(f"cannot read JSON evidence: {path.name}") from exc
    if not isinstance(value, dict):
        raise PrimeTrajectoryEvidenceError(f"JSON evidence must be an object: {path.name}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PrimeTrajectoryEvidenceError(f"cannot read JSONL evidence: {path.name}") from exc
    if text and not text.endswith("\n"):
        raise PrimeTrajectoryEvidenceError(f"JSONL evidence has an incomplete final frame: {path.name}")
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise PrimeTrajectoryEvidenceError(f"JSONL evidence has a blank frame: {path.name}:{line_number}")
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PrimeTrajectoryEvidenceError(f"JSONL evidence is malformed: {path.name}:{line_number}") from exc
        if not isinstance(value, dict):
            raise PrimeTrajectoryEvidenceError(f"JSONL evidence frame must be an object: {path.name}:{line_number}")
        events.append(value)
    return events


def _usage_by_call(assistant_messages: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for message in assistant_messages:
        usage = message.get("usage")
        if not isinstance(usage, dict):
            raise PrimeTrajectoryEvidenceError("Prime assistant message has no usage evidence")
        result.append(
            {
                "call": len(result) + 1,
                "input_tokens": _required_int(usage.get("input"), "usage.input"),
                "output_tokens": _required_int(usage.get("output"), "usage.output"),
                "cache_read_tokens": _required_int(usage.get("cacheRead"), "usage.cacheRead"),
                "cache_write_tokens": _required_int(usage.get("cacheWrite"), "usage.cacheWrite"),
                "total_tokens": _required_int(usage.get("totalTokens"), "usage.totalTokens"),
            }
        )
    return result


def _tool_calls(
    assistant_messages: Sequence[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    calls: list[dict[str, Any]] = []
    code_cells: list[str] = []
    ordinal = 0
    for message in assistant_messages:
        ordinal += 1
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "toolCall":
                continue
            call_id = item.get("id")
            name = item.get("name")
            if not isinstance(call_id, str) or not isinstance(name, str):
                raise PrimeTrajectoryEvidenceError("Prime tool call has no identity or name")
            arguments = item.get("arguments")
            code = arguments.get("code", "") if isinstance(arguments, dict) else ""
            if not isinstance(code, str):
                code = ""
            calls.append({"id": call_id, "name": name, "code": code, "ordinal": ordinal})
            if name == "ipython":
                code_cells.append(code)
    return calls, code_cells


def _tool_results(
    tool_result_messages: Sequence[dict[str, Any]],
    tool_calls: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    calls = {str(call["id"]): call for call in tool_calls}
    results: list[dict[str, Any]] = []
    for ordinal, message in enumerate(tool_result_messages, start=1):
        call_id = message.get("toolCallId")
        if not isinstance(call_id, str):
            raise PrimeTrajectoryEvidenceError("Prime tool result has no tool call identity")
        call = calls.get(call_id)
        text = _content_text(message.get("content"))
        results.append(
            {
                "tool_call_id": call_id,
                "name": str(message.get("toolName", "")),
                "chars": len(text),
                "is_error": bool(message.get("isError")),
                "guidance_marker_present": _guidance_marker_present(text),
                "code_preview": " ".join(str(call["code"]).split())[:240] if call is not None else "",
                "result_ordinal": ordinal,
            }
        )
    return results


def _actor_metrics(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    operations = Counter(str(event.get("operation")) for event in events if event.get("operation") is not None)
    invokes = [event for event in events if event.get("operation") == "invoke"]
    statuses: Counter[str] = Counter()
    repeated = 0
    seen: dict[tuple[str, str, str], str] = {}
    for event in invokes:
        result = event.get("result")
        error = event.get("error")
        status = result.get("status") if isinstance(result, dict) else None
        if not isinstance(status, str) and isinstance(error, dict):
            status = error.get("code")
        statuses[str(status or "unknown")] += 1
        request = event.get("request")
        if not isinstance(request, dict):
            continue
        decision_id = request.get("decision_id")
        action_name = request.get("action_name")
        request_id = request.get("request_id")
        arguments = request.get("arguments")
        if not isinstance(decision_id, str) or not isinstance(action_name, str) or not isinstance(request_id, str):
            continue
        key = (decision_id, action_name, json.dumps(arguments, sort_keys=True, separators=(",", ":")))
        previous_request_id = seen.setdefault(key, request_id)
        if previous_request_id != request_id:
            repeated += 1
    invalid_codes = {"actor-request-invalid", "actor-action-arguments"}
    return {
        "operations": dict(operations),
        "invoke_statuses": dict(statuses),
        "repeated_equivalent_requests_in_unchanged_state": repeated,
        "invalid_invoke_count": sum(statuses[code] for code in invalid_codes),
        "stale_decision_count": statuses["decision-stale"],
        "no_accessible_result_count": statuses["NO_ACCESSIBLE_RESULT"],
    }


def _treatment_integrity(
    prime_run: Mapping[str, Any],
    tool_calls: Sequence[dict[str, Any]],
    tool_results: Sequence[dict[str, Any]],
) -> dict[str, Any]:
    raw_skills = prime_run.get("skills")
    selected_skills = [skill for skill in raw_skills if isinstance(skill, dict)] if isinstance(raw_skills, list) else []
    guidance_available = any(
        skill.get("name") == _GUIDANCE_SKILL_NAME and isinstance(skill.get("sha256"), str) and bool(skill["sha256"])
        for skill in selected_skills
    )
    calls = {str(call["id"]): call for call in tool_calls}
    load_calls: dict[str, int] = {}
    reference_loads: list[str] = []
    for result in tool_results:
        if result["is_error"]:
            continue
        call = calls.get(str(result["tool_call_id"]))
        if call is None:
            continue
        code = str(call["code"])
        if _GUIDANCE_SKILL_NAME in code and "SKILL.md" in code:
            load_calls[str(call["id"])] = int(call["ordinal"])
        for reference in _GUIDANCE_REFERENCES:
            if reference in code and reference not in reference_loads:
                reference_loads.append(reference)
    completed_load_call_ids = {
        str(result["tool_call_id"])
        for result in tool_results
        if not result["is_error"] and result["guidance_marker_present"]
    }.intersection(load_calls)
    guidance_loaded = bool(completed_load_call_ids)
    first_invoke_ordinal = min(
        (
            int(call["ordinal"])
            for call in tool_calls
            if call["name"] == "ipython" and "aec_world.invoke(" in str(call["code"])
        ),
        default=None,
    )
    loaded_before_first_invoke = bool(
        guidance_loaded
        and first_invoke_ordinal is not None
        and min(load_calls[call_id] for call_id in completed_load_call_ids) < first_invoke_ordinal
    )
    return {
        "guidance_available": guidance_available,
        "guidance_loaded": guidance_loaded,
        "guidance_loaded_before_first_invoke": loaded_before_first_invoke,
        "guidance_id": GUIDANCE_ID if guidance_loaded else None,
        "reference_loads": reference_loads,
    }


def _guidance_marker_present(text: str) -> bool:
    return _GUIDANCE_MARKER_PATTERN.search(text) is not None


def _report_quality(path: Path, *, canonical_invoke_count: int, final_text: str) -> dict[str, Any]:
    if not path.is_file():
        return {
            "status": "incomplete",
            "reason": "human report review is missing",
            "final_report_present": bool(final_text.strip()),
            "action_ledger_recall": None,
            "action_outcome_classification_accuracy": None,
            "pending_liability_accuracy": None,
            "unsupported_claim_count": None,
        }
    try:
        review = PrimeHumanReportReview.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise PrimeTrajectoryEvidenceError("human report review is invalid") from exc
    if review.canonical_invoke_count != canonical_invoke_count:
        raise PrimeTrajectoryEvidenceError("human report review canonical invoke count does not match transport")
    return {
        "status": "complete",
        "rubric_id": review.rubric_id,
        "reviewer": review.reviewer,
        "reviewed_at": review.reviewed_at.isoformat(),
        "evidence_references": list(review.evidence_references),
        "final_report_present": bool(final_text.strip()),
        "reported_invoke_count": review.reported_invoke_count,
        "action_ledger_recall": _ratio(review.matched_invoke_count, canonical_invoke_count),
        "action_outcome_classification_accuracy": _ratio(
            review.correctly_classified_invoke_count, canonical_invoke_count
        ),
        "pending_liability_accuracy": _ratio(
            review.correct_pending_liability_claim_count, review.pending_liability_claim_count
        ),
        "unsupported_claim_count": review.unsupported_claim_count,
    }


def _world_progress(summary: Mapping[str, Any]) -> dict[str, Any]:
    world = _required_mapping(summary.get("world"), "trial world summary")
    verification = _required_mapping(world.get("verification"), "world verification")
    conservation = _required_mapping(verification.get("conservation"), "world conservation")
    duty = _required_mapping(conservation.get("duty"), "world duty conservation")
    work = _required_mapping(conservation.get("work"), "world work conservation")
    evaluation = _required_mapping(world.get("evaluation"), "world evaluation")
    return {
        "benchmark_valid": _required_bool(world.get("benchmark_valid"), "world benchmark_valid"),
        "verification_valid": _required_bool(verification.get("valid"), "world verification valid"),
        "replay_valid": _required_bool(verification.get("replay_valid"), "world replay valid"),
        "evaluation_valid": _required_bool(evaluation.get("valid"), "world evaluation valid"),
        "unserved_capacity_seconds": _required_int(duty.get("unserved_capacity_seconds"), "unserved_capacity_seconds"),
        "terminal_work_count": len(_required_list(work.get("terminal_ids"), "terminal work IDs")),
        "closing_work_count": len(_required_list(work.get("closing_ids"), "closing work IDs")),
        "world_state": _required_string(world.get("state"), "world state"),
        "completion": _required_string(world.get("completion"), "world completion"),
    }


def _compaction_event_count(evidence_directory: Path, session_events: Sequence[dict[str, Any]]) -> int:
    acp_file = evidence_directory / "prime-acp-out.jsonl"
    events = _read_jsonl(acp_file) if acp_file.is_file() else list(session_events)
    return sum(_contains_structured_key(event, "compaction") for event in events)


def _contains_structured_key(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(
            _contains_structured_key(item, key) for item in value.values() if not isinstance(item, str)
        )
    if isinstance(value, list):
        return any(_contains_structured_key(item, key) for item in value)
    return False


def _prints_full_object(code: str) -> bool:
    normalized = re.sub(r"\s+", " ", code)
    return ("json.dumps(" in code and re.search(r"indent\s*=", code) is not None) or bool(
        re.search(r"print\([^)]*\b(observation|catalogue|caps|result(?:_?[A-Za-z0-9]+)?)\s*\)", normalized)
    )


def _uses_compact_state(code: str) -> bool:
    return "state.json" in code or bool(re.search(r"\bcompact(?:_state)?\s*(?:=|\[|\.)", code))


def _updates_compact_state(code: str) -> bool:
    return bool(re.search(r"\bcompact(?:_state)?\.update\(", code)) or bool(
        re.search(r"\bcompact(?:_state)?\[[^]]+\]\s*=", code)
    )


def _uses_action_ledger(code: str) -> bool:
    return "action_ledger" in code or bool(re.search(r"\bledger\s*=|\bledger\.append\(", code))


def _appends_action_ledger(code: str) -> bool:
    return "action_ledger.append(" in code or "ledger.append(" in code


def _final_assistant_text(assistant_messages: Sequence[dict[str, Any]]) -> str:
    final = ""
    for message in assistant_messages:
        content = message.get("content")
        if not isinstance(content, list):
            continue
        text = "".join(
            str(item.get("text", "")) for item in content if isinstance(item, dict) and item.get("type") == "text"
        )
        if text:
            final = text
    return final


def _content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "".join(str(item.get(key, "")) for item in content if isinstance(item, dict) for key in ("text", "thinking"))


def _median(values: Sequence[int]) -> float:
    return float(statistics.median(values)) if values else 0.0


def _percentile(values: Sequence[int], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return float(ordered[lower] * (1 - weight) + ordered[upper] * weight)


def _ratio(numerator: int | float, denominator: int) -> float | None:
    return None if denominator == 0 else float(numerator / denominator)


def _required_mapping(value: object, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PrimeTrajectoryEvidenceError(f"{name} must be an object")
    return value


def _required_list(value: object, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise PrimeTrajectoryEvidenceError(f"{name} must be a list")
    return value


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value:
        raise PrimeTrajectoryEvidenceError(f"{name} must be a non-empty string")
    return value


def _optional_string(value: object, name: str) -> str | None:
    if value is None:
        return None
    return _required_string(value, name)


def _required_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise PrimeTrajectoryEvidenceError(f"{name} must be a non-negative integer")
    return value


def _required_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        raise PrimeTrajectoryEvidenceError(f"{name} must be numeric")
    try:
        result = float(value)
    except ValueError as exc:
        raise PrimeTrajectoryEvidenceError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result < 0:
        raise PrimeTrajectoryEvidenceError(f"{name} must be non-negative")
    return result


def _required_bool(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise PrimeTrajectoryEvidenceError(f"{name} must be a boolean")
    return value


def _nested_int(value: Mapping[str, Any], parent: str, child: str) -> int:
    return _required_int(_required_mapping(value.get(parent), parent).get(child), f"{parent}.{child}")
