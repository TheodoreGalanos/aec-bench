# ABOUTME: Imports Prime hosted evaluation samples into ledger-compatible artefacts.
# ABOUTME: Bridges Prime rollout payloads to TrialRecord records for existing analysis tools.

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.jsonl import write_jsonl
from aec_bench.contracts.trial_record import (
    AgentReference,
    Completeness,
    CostRecord,
    EnvironmentSnapshot,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)
from aec_bench.ledger.writer import DuplicateTrialRecordError, write_trial_record


@dataclass(frozen=True)
class PrimeEvalImportResult:
    experiment_id: str
    records: list[TrialRecord]
    record_paths: list[Path]
    skipped_duplicates: int = 0
    artifact_paths: list[Path] = field(default_factory=list)


def fetch_prime_eval_payloads(eval_id: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    evaluation = _run_prime_json(["prime", "eval", "get", eval_id, "--plain", "-o", "json"])
    first_page = _run_prime_json(["prime", "eval", "samples", eval_id, "--plain", "-n", "100", "-o", "json"])
    samples = list(first_page.get("samples", []))
    total_pages = int(first_page.get("total_pages") or 1)
    for page in range(2, total_pages + 1):
        payload = _run_prime_json(
            [
                "prime",
                "eval",
                "samples",
                eval_id,
                "--plain",
                "-n",
                "100",
                "-p",
                str(page),
                "-o",
                "json",
            ]
        )
        samples.extend(payload.get("samples", []))
    return evaluation, samples


def import_prime_eval_samples(
    *,
    evaluation: dict[str, Any],
    samples: list[dict[str, Any]],
    ledger_root: Path,
    experiment_id: str | None = None,
    skip_duplicates: bool = True,
) -> PrimeEvalImportResult:
    eval_id = _evaluation_id(evaluation)
    resolved_experiment = experiment_id or f"prime-eval-{_slug(eval_id)}"
    imported_records: list[TrialRecord] = []
    record_paths: list[Path] = []
    artifact_paths: list[Path] = []
    skipped_duplicates = 0

    for sample in samples:
        sample_id = str(sample.get("sample_id") or f"sample-{len(imported_records) + 1}")
        trial_id = f"prime-{_slug(eval_id)}-{_slug(sample_id)}"
        record_path = ledger_root / resolved_experiment / f"{trial_id}.json"
        if skip_duplicates and record_path.exists():
            skipped_duplicates += 1
            continue
        artifact_dir = ledger_root / resolved_experiment / "_artifacts" / trial_id
        record, artifacts = _build_record(
            evaluation=evaluation,
            sample=sample,
            experiment_id=resolved_experiment,
            trial_id=trial_id,
            artifact_dir=artifact_dir,
        )
        try:
            record_path = write_trial_record(ledger_root=ledger_root, record=record)
        except DuplicateTrialRecordError:
            if not skip_duplicates:
                raise
            skipped_duplicates += 1
            continue
        imported_records.append(record)
        record_paths.append(record_path)
        artifact_paths.extend(artifacts)

    return PrimeEvalImportResult(
        experiment_id=resolved_experiment,
        records=imported_records,
        record_paths=record_paths,
        skipped_duplicates=skipped_duplicates,
        artifact_paths=artifact_paths,
    )


def _build_record(
    *,
    evaluation: dict[str, Any],
    sample: dict[str, Any],
    experiment_id: str,
    trial_id: str,
    artifact_dir: Path,
) -> tuple[TrialRecord, list[Path]]:
    info = _dict(sample.get("info"))
    metrics = _dict(info.get("metrics"))
    timing = _dict(info.get("timing"))
    token_usage = _dict(info.get("token_usage"))
    conversation = _conversation_messages(sample)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    conversation_path = artifact_dir / "conversation.jsonl"
    write_jsonl(conversation_path, conversation)

    sample_path = artifact_dir / "prime_sample.json"
    sample_path.write_text(json.dumps(sample, indent=2, sort_keys=True), encoding="utf-8")

    output_path = _write_submitted_output(artifact_dir, conversation)
    artifacts = [conversation_path, sample_path]
    if output_path is not None:
        artifacts.append(output_path)

    reward = _reward(sample, metrics)
    error = _dict(info.get("error"))
    error_name = str(error.get("error") or "")
    error_message = str(error.get("error_chain_str") or error_name)
    has_error = bool(error_name)
    status = AgentOutputStatus.COMPLETED if reward > 0.0 else AgentOutputStatus.FAILED

    agent_result = {
        "source": "prime-eval-samples",
        "prime_evaluation_id": _evaluation_id(evaluation),
        "prime_sample_id": sample.get("sample_id"),
        "example_id": sample.get("example_id"),
        "rollout_number": sample.get("rollout_number"),
        "stop_condition": info.get("stop_condition"),
        "is_completed": info.get("is_completed"),
        "error": error or None,
        **metrics,
    }

    return (
        TrialRecord(
            trial_id=trial_id,
            experiment_id=experiment_id,
            dataset_id=_dataset_id(info),
            timestamp=_timestamp(sample),
            task=TaskReference(
                task_id=_task_id(sample, info),
                task_revision=str(info.get("task_revision") or "prime-hosted"),
            ),
            agent=AgentReference(
                adapter="prime-hosted",
                model=_model_name(evaluation),
                configuration={
                    "source": "prime-eval-samples",
                    "evaluation_id": _evaluation_id(evaluation),
                    "evaluation_name": evaluation.get("name"),
                    "viewer_url": evaluation.get("viewer_url"),
                    "eval_config": evaluation.get("eval_config"),
                },
            ),
            environment=EnvironmentSnapshot(
                runtime_image="prime-hosted",
                compute_backend="prime-hosted",
            ),
            inputs=InputRecord(
                instruction=_instruction(sample, info),
                system_prompt=None,
                input_files=None,
            ),
            outputs=OutputRecord(
                agent_output=AgentOutput(
                    status=status,
                    output_path=output_path.name if output_path is not None else "output.md",
                    output_format="markdown",
                    error_message=error_message if has_error and reward == 0.0 else None,
                ),
                raw_output_path=str(output_path) if output_path is not None else None,
                conversation_path=str(conversation_path),
                trajectory_path=None,
                agent_result=agent_result,
            ),
            evaluation=EvaluationResult(
                reward=reward,
                validity=ValidityCheck(
                    output_parseable=reward > 0.0,
                    schema_valid=reward > 0.0,
                    verifier_completed=True,
                    errors=[error_message] if has_error and reward == 0.0 else [],
                ),
                breakdown=metrics,
            ),
            timing=TimingRecord(
                total_seconds=_total_seconds(sample, timing),
                agent_seconds=_seconds(timing.get("generation_ms")),
                verification_seconds=_seconds(timing.get("scoring_ms")),
            ),
            cost=CostRecord(
                tokens_in=_optional_int(token_usage.get("input_tokens")),
                tokens_out=_optional_int(token_usage.get("output_tokens")),
            ),
            completeness=Completeness.PARTIAL,
        ),
        artifacts,
    )


def _conversation_messages(sample: dict[str, Any]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for raw in [*list(sample.get("prompt") or ()), *list(sample.get("completion") or ())]:
        if not isinstance(raw, dict):
            continue
        message = {
            "role": str(raw.get("role") or ""),
            "content": raw.get("content") or "",
        }
        tool_calls = _normalise_tool_calls(raw.get("tool_calls"))
        if tool_calls:
            message["tool_calls"] = tool_calls
        tool_call_id = raw.get("tool_call_id")
        if tool_call_id:
            message["tool_call_id"] = str(tool_call_id)
        messages.append(message)
    return messages


def _normalise_tool_calls(raw_tool_calls: object) -> list[dict[str, Any]]:
    if not isinstance(raw_tool_calls, list):
        return []
    tool_calls: list[dict[str, Any]] = []
    for raw in raw_tool_calls:
        if isinstance(raw, dict):
            tool_calls.append(raw)
            continue
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                tool_calls.append(parsed)
    return tool_calls


def _write_submitted_output(
    artifact_dir: Path,
    conversation: list[dict[str, Any]],
) -> Path | None:
    for message in conversation:
        for tool_call in message.get("tool_calls", []):
            function_payload = _dict(tool_call.get("function"))
            if function_payload.get("name") != "submit_answer":
                continue
            arguments = _parse_arguments(function_payload.get("arguments"))
            content = arguments.get("content")
            if not isinstance(content, str) or not content:
                continue
            output_path = artifact_dir / str(arguments.get("path") or "output.md")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            return output_path
    return None


def _parse_arguments(raw: object) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(str(raw or "{}"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _run_prime_json(args: list[str]) -> dict[str, Any]:
    completed = subprocess.run(args, check=True, capture_output=True, text=True)
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        msg = f"Prime command returned non-object JSON: {' '.join(args)}"
        raise ValueError(msg)
    return payload


def _evaluation_id(evaluation: dict[str, Any]) -> str:
    return str(evaluation.get("evaluation_id") or evaluation.get("id") or "unknown")


def _model_name(evaluation: dict[str, Any]) -> str:
    return str(
        evaluation.get("model_name")
        or evaluation.get("inference_model")
        or _dict(evaluation.get("metadata")).get("model")
        or "unknown"
    )


def _task_id(sample: dict[str, Any], info: dict[str, Any]) -> str:
    return str(info.get("task_id") or sample.get("answer") or f"prime/{sample.get('example_id', 'unknown')}")


def _instruction(sample: dict[str, Any], info: dict[str, Any]) -> str:
    if info.get("instruction"):
        return str(info["instruction"])
    for message in sample.get("prompt") or ():
        if isinstance(message, dict) and message.get("role") == "user":
            content = str(message.get("content") or "")
            if content:
                return content
    return "Prime hosted evaluation sample"


def _dataset_id(info: dict[str, Any]) -> str | None:
    dataset = _dict(info.get("dataset"))
    name = dataset.get("name")
    version = dataset.get("version")
    if name and version:
        return f"{name}@{version}"
    return None


def _timestamp(sample: dict[str, Any]) -> datetime:
    raw = sample.get("created_at")
    if isinstance(raw, str) and raw:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    return datetime.now(UTC)


def _reward(sample: dict[str, Any], metrics: dict[str, Any]) -> float:
    value = sample.get(
        "reward",
        sample.get("aec_bench_reward", metrics.get("aec_bench_reward", 0.0)),
    )
    return float(value or 0.0)


def _total_seconds(sample: dict[str, Any], timing: dict[str, Any]) -> float:
    if sample.get("total_time") is not None:
        return float(sample["total_time"])
    if timing.get("total_ms") is not None:
        return float(timing["total_ms"]) / 1000.0
    if sample.get("latency_ms") is not None:
        return float(sample["latency_ms"]) / 1000.0
    return 0.0


def _seconds(value: object) -> float | None:
    if value is None:
        return None
    return float(value) / 1000.0


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(float(value))


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return slug or "unknown"
