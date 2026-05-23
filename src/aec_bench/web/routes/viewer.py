# ABOUTME: Full-page trial viewer route with trajectory, artefacts, and info tabs.
# ABOUTME: Breakout page from triage — shows detailed step-by-step agent execution.

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.contracts.trajectory import TrajectoryEntry, read_trajectory
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.trajectory_reader import (
    compute_step_status,
    detect_adapter_type,
    group_by_step,
)
from aec_bench.ledger.annotations import load_annotations
from aec_bench.ledger.reader import read_trial_records
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    AnnotationSchema,
    StepSummarySchema,
    ViewerMetaResponse,
    ViewerStateResponse,
    ViewerStepResponse,
)
from aec_bench.web.utils import reward_css_class

router = APIRouter()


@dataclass(frozen=True)
class StepSummary:
    """Lightweight view of one trajectory step for the step list sidebar."""

    step: int
    status: str
    description: str
    tool_name: str
    duration_ms: int | None
    error_count: int
    metadata: dict[str, Any] | None = None  # RLM step metadata
    call_type: str | None = None  # warmup, main, or subagent
    output_summary: str | None = None  # truncated preview of tool stdout


def _build_viewer_step_summaries(
    messages_by_step: dict[int, list[TrajectoryEntry]],
) -> list[StepSummary]:
    """Convert grouped trajectory entries to step summaries for the sidebar."""
    summaries: list[StepSummary] = []
    for step_num, entries in messages_by_step.items():
        first_tool = next((e.tool_name for e in entries if e.tool_name), "")
        first_role = entries[0].role if entries else ""
        description = first_tool or first_role
        error_count = sum(1 for e in entries if e.exit_code is not None and e.exit_code != 0)
        total_duration = None
        durations = [e.duration_ms for e in entries if e.duration_ms is not None]
        if durations:
            total_duration = sum(durations)

        # Extract metadata from the tool_result entry (if present)
        step_metadata = next(
            (e.metadata for e in entries if e.role == "tool_result" and e.metadata),
            None,
        )

        # Extract call_type from the first entry that carries one
        call_type = next(
            (e.call_type for e in entries if e.call_type is not None),
            None,
        )

        # Extract output_summary from the first tool_result that has one
        output_summary = next(
            (e.output_summary for e in entries if e.role == "tool_result" and e.output_summary),
            None,
        )

        summaries.append(
            StepSummary(
                step=step_num,
                status=compute_step_status(entries),
                description=description,
                tool_name=first_tool,
                duration_ms=total_duration,
                error_count=error_count,
                metadata=step_metadata,
                call_type=call_type,
                output_summary=output_summary,
            )
        )
    return summaries


def _discover_artefacts(record: TrialRecord) -> list[str]:
    """Discover image artefact files from the trial output directory."""
    raw_path = record.outputs.raw_output_path
    if not raw_path:
        return []
    output_dir = Path(raw_path).parent
    if not output_dir.is_dir():
        return []
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".pdf"}
    return sorted(str(p) for p in output_dir.iterdir() if p.suffix.lower() in image_exts)


def _load_conversation_fallback(path_str: str | None) -> list[dict[str, Any]]:
    """Try to load conversation messages from a JSONL file as fallback."""
    if not path_str:
        return []
    path = Path(path_str)
    if not path.exists():
        return []
    messages: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def _build_back_url(from_page: str | None, query_params: dict[str, str]) -> str:
    """Reconstruct a back URL from the origin page and filter query params."""
    if not from_page:
        return "/"
    base = f"/{from_page}"
    # Carry forward filter params (exclude 'from' itself)
    parts = [f"{k}={v}" for k, v in sorted(query_params.items()) if k != "from" and v]
    if parts:
        return f"{base}?{'&'.join(parts)}"
    return base


def _load_symbolic_state(traj_path_str: str | None) -> dict[str, Any]:
    """Load symbolic_state.json from the same directory as the trajectory file."""
    if not traj_path_str:
        return {}
    ss_path = Path(traj_path_str).parent / "symbolic_state.json"
    if not ss_path.exists():
        return {}
    try:
        return json.loads(ss_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_scratchpad(traj_path_str: str | None) -> dict[str, Any]:
    """Load .scratchpad.json from the same directory as the trajectory file."""
    if not traj_path_str:
        return {}
    sp_path = Path(traj_path_str).parent / ".scratchpad.json"
    if not sp_path.exists():
        return {}
    try:
        return json.loads(sp_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _load_plan_state(traj_path_str: str | None) -> dict[str, Any] | None:
    """Extract plan_state from the last trajectory entry that carries one."""
    if not traj_path_str:
        return None
    traj_path = Path(traj_path_str)
    if not traj_path.exists():
        return None
    entries = read_trajectory(traj_path)
    plan_state = None
    for entry in entries:
        if entry.metadata and "plan_state" in entry.metadata:
            plan_state = entry.metadata["plan_state"]
    return plan_state


def _load_trial(
    settings_ledger_root: Path,
    experiment_id: str,
    trial_id: str,
) -> tuple[TrialRecord, list[TrialRecord]]:
    """Load a trial record and all siblings for the experiment, or raise 404."""
    records = read_trial_records(settings_ledger_root, experiment_id=experiment_id)
    matching = [r for r in records if r.trial_id == trial_id]
    if not matching:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Trial {trial_id} not found in experiment {experiment_id}",
        )
    return matching[0], records


@router.get("/api/viewer/{experiment_id}/{trial_id}")
def viewer_api_meta(
    request: Request,
    experiment_id: str,
    trial_id: str,
) -> ViewerMetaResponse:
    """Return trial metadata and step summaries for lazy-loading the viewer."""
    settings = get_web_settings(request)
    record, all_records = _load_trial(settings.ledger_root, experiment_id, trial_id)

    siblings = sorted(r.trial_id for r in all_records)
    try:
        idx = siblings.index(trial_id)
    except ValueError:
        idx = 0
    prev_trial = siblings[idx - 1] if idx > 0 else None
    next_trial = siblings[idx + 1] if idx < len(siblings) - 1 else None

    # Parse trajectory
    entries: list[TrajectoryEntry] = []
    has_trajectory = False
    traj_path_str = record.outputs.trajectory_path
    if traj_path_str:
        traj_path = Path(traj_path_str)
        if traj_path.exists():
            entries = read_trajectory(traj_path)
            if entries:
                has_trajectory = True

    messages_by_step = group_by_step(entries) if has_trajectory else {}
    raw_steps = _build_viewer_step_summaries(messages_by_step) if has_trajectory else []
    steps = [
        StepSummarySchema(
            step=s.step,
            status=s.status,
            description=s.description,
            tool_name=s.tool_name,
            duration_ms=s.duration_ms,
            error_count=s.error_count,
            metadata=s.metadata,
            call_type=s.call_type,
            output_summary=s.output_summary,
        )
        for s in raw_steps
    ]
    adapter_type = detect_adapter_type(entries) if has_trajectory else "other"
    is_rlm_trial = adapter_type in ("rlm", "lambda-rlm")
    artefacts = _discover_artefacts(record)

    # Load annotation
    experiment_dir = settings.ledger_root / experiment_id
    annotations = load_annotations(experiment_dir)
    raw_annotation = annotations.get(trial_id)
    annotation: AnnotationSchema | None = None
    if raw_annotation is not None:
        annotation = AnnotationSchema(
            verdict=raw_annotation.verdict,
            notes=raw_annotation.notes,
            timestamp=raw_annotation.timestamp,
        )

    # Token stats
    total_errors = sum(s.error_count for s in raw_steps)
    tokens_in = record.cost.tokens_in if record.cost else None
    tokens_out = record.cost.tokens_out if record.cost else None
    total_tokens: int | None = None
    if tokens_in is not None and tokens_out is not None:
        total_tokens = tokens_in + tokens_out
    cost_usd = record.cost.estimated_cost_usd if record.cost else None

    # Back URL (API callers may omit query params — use empty defaults)
    query_params: dict[str, str] = {k: v for k, v in request.query_params.items()}
    back_url = _build_back_url(query_params.get("from"), query_params)

    return ViewerMetaResponse(
        trial_id=record.trial_id,
        experiment_id=record.experiment_id,
        dataset_id=record.dataset_id,
        task_id=record.task.task_id,
        model=record.agent.model,
        adapter=record.agent.adapter,
        reward=record.evaluation.reward,
        reward_class=reward_css_class(record.evaluation.reward),
        steps=steps,
        is_rlm_trial=is_rlm_trial,
        adapter_type=adapter_type,
        artefacts=artefacts,
        annotation=annotation,
        total_errors=total_errors,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        siblings=siblings,
        prev_trial=prev_trial,
        next_trial=next_trial,
        back_url=back_url,
        has_trajectory=has_trajectory,
    )


@router.get("/api/viewer/{experiment_id}/{trial_id}/steps/{step_num}")
def viewer_api_step(
    request: Request,
    experiment_id: str,
    trial_id: str,
    step_num: int,
) -> ViewerStepResponse:
    """Return all messages for a single trajectory step, loaded on demand."""
    settings = get_web_settings(request)
    record, _ = _load_trial(settings.ledger_root, experiment_id, trial_id)

    entries: list[TrajectoryEntry] = []
    traj_path_str = record.outputs.trajectory_path
    if traj_path_str:
        traj_path = Path(traj_path_str)
        if traj_path.exists():
            entries = read_trajectory(traj_path)

    messages_by_step = group_by_step(entries)
    step_entries = messages_by_step.get(step_num, [])
    messages = [e.model_dump(mode="json", exclude_none=True) for e in step_entries]

    return ViewerStepResponse(step_num=step_num, messages=messages)


@router.get("/api/viewer/{experiment_id}/{trial_id}/state")
def viewer_api_state(
    request: Request,
    experiment_id: str,
    trial_id: str,
) -> ViewerStateResponse:
    """Return symbolic state and scratchpad for an RLM trial."""
    settings = get_web_settings(request)
    record, _ = _load_trial(settings.ledger_root, experiment_id, trial_id)

    traj_path_str = record.outputs.trajectory_path
    symbolic_state = _load_symbolic_state(traj_path_str)
    scratchpad_data = _load_scratchpad(traj_path_str)
    plan_state = _load_plan_state(traj_path_str)

    return ViewerStateResponse(
        symbolic_state=symbolic_state,
        scratchpad_data=scratchpad_data,
        plan_state=plan_state,
    )
