# ABOUTME: Ledger-backed trace summary exports compatible with legacy trace review tooling.
# ABOUTME: Builds per-trial trace summaries from imported TrialRecords without raw Harbor scraping.

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from aec_bench.communication.metrics import coerce_int, split_task_id
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.trace_summary import extract_trial_trace_signals


@dataclass(frozen=True)
class TraceSummaryRecord:
    trial_id: str
    model: str
    task: str
    task_type: str
    reward: float
    turns_used: int
    max_turns: int
    tokens_in: int
    tokens_out: int
    duration_sec: float
    tool_calls: int
    tool_errors: int
    used_calc_tool: bool
    wrote_output: bool
    fields_correct: int
    fields_total: int
    first_error: str | None
    trace_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def trace_summary_from_record(record: TrialRecord) -> TraceSummaryRecord:
    task_type, task_name = split_task_id(record.task.task_id)
    agent_result = record.outputs.agent_result or {}
    trace_signals = extract_trial_trace_signals(record)
    fields_correct, fields_total = _count_breakdown_fields(record.evaluation.breakdown)

    return TraceSummaryRecord(
        trial_id=record.trial_id,
        model=record.agent.model,
        task=task_name,
        task_type=task_type,
        reward=record.evaluation.reward,
        turns_used=coerce_int(agent_result.get("turns_used")),
        max_turns=coerce_int(agent_result.get("max_turns")),
        tokens_in=_token_input_total(record),
        tokens_out=coerce_int(
            agent_result.get("usage_output_tokens"),
            fallback=_cost_tokens_out(record),
        ),
        duration_sec=record.timing.agent_seconds or record.timing.total_seconds,
        tool_calls=coerce_int(trace_signals.get("tool_call_count")),
        tool_errors=coerce_int(trace_signals.get("tool_errors")),
        used_calc_tool=bool(trace_signals.get("used_calc_tool")),
        wrote_output=bool(trace_signals.get("wrote_output")),
        fields_correct=fields_correct,
        fields_total=fields_total,
        first_error=_string_or_none(trace_signals.get("first_error")),
        trace_path=record.outputs.conversation_path or "",
    )


def build_trace_summaries(records: list[TrialRecord]) -> list[TraceSummaryRecord]:
    return [trace_summary_from_record(record) for record in records]


def export_trace_summaries_json(summaries: list[TraceSummaryRecord], output_path: Path) -> Path:
    output_path.write_text(
        json.dumps([summary.to_dict() for summary in summaries], indent=2),
        encoding="utf-8",
    )
    return output_path


def _count_breakdown_fields(details: dict[str, object] | None) -> tuple[int, int]:
    if details is None:
        return 0, 0

    correct = 0
    total = 0
    for value in details.values():
        if isinstance(value, dict):
            nested_correct, nested_total = _count_breakdown_fields(value)
            correct += nested_correct
            total += nested_total
        elif isinstance(value, int | float):
            total += 1
            if float(value) == 1.0:
                correct += 1
    return correct, total


def _token_input_total(record: TrialRecord) -> int:
    if record.cost is not None and record.cost.tokens_in is not None:
        return record.cost.tokens_in
    agent_result = record.outputs.agent_result or {}
    return coerce_int(agent_result.get("usage_input_tokens"))


def _cost_tokens_out(record: TrialRecord) -> int:
    if record.cost is None or record.cost.tokens_out is None:
        return 0
    return record.cost.tokens_out


def _string_or_none(value: object) -> str | None:
    if isinstance(value, str) and value:
        return value
    return None
