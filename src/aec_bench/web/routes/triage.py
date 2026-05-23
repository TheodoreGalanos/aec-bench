# ABOUTME: Triage annotation API and full-width trial list page for rapid trial review.
# ABOUTME: Combines REST annotation endpoints with the primary triage workspace route.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request, status
from pydantic import BaseModel

from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.ledger.annotations import (
    TriageAnnotation,
    load_annotations,
    save_annotation,
)
from aec_bench.ledger.reader import query_trial_records, read_trial_records
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import TriageResponse, TrialRowSchema
from aec_bench.web.utils import extract_discipline, reward_css_class

router = APIRouter()


class TriageAnnotateRequest(BaseModel):
    """Request body for creating or replacing a triage annotation."""

    trial_id: str
    experiment_id: str
    verdict: Literal["pass", "fail", "defer", "note"]
    notes: str = ""


@router.post("/api/triage/annotate", status_code=status.HTTP_201_CREATED)
def post_triage_annotation(
    request: Request,
    body: TriageAnnotateRequest,
) -> dict[str, str]:
    """Create or update a triage annotation, merging verdict and notes independently.

    When saving a verdict (pass/fail/defer), existing notes are preserved.
    When saving a note, the existing verdict is preserved.
    """
    settings = get_web_settings(request)
    experiment_dir = settings.ledger_root / body.experiment_id

    # Load existing annotation to merge fields
    existing = load_annotations(experiment_dir).get(body.trial_id)

    if body.verdict == "note":
        # Saving notes only — preserve existing verdict
        verdict = existing.verdict if existing and existing.verdict != "note" else "note"
        notes = body.notes
    else:
        # Saving verdict — preserve existing notes unless new notes provided
        verdict = body.verdict
        notes = body.notes if body.notes else (existing.notes if existing else "")

    annotation = TriageAnnotation.create(verdict=verdict, notes=notes)
    save_annotation(experiment_dir, body.trial_id, annotation)
    return {
        "verdict": annotation.verdict,
        "notes": annotation.notes,
        "timestamp": annotation.timestamp,
    }


@router.get("/api/triage/annotations")
def get_triage_annotations(
    request: Request,
    experiment: str,
) -> dict[str, dict[str, str]]:
    """Return all triage annotations for an experiment as {trial_id: annotation}."""
    settings = get_web_settings(request)
    experiment_dir = settings.ledger_root / experiment
    annotations = load_annotations(experiment_dir)
    return {
        trial_id: {
            "verdict": ann.verdict,
            "notes": ann.notes,
            "timestamp": ann.timestamp,
        }
        for trial_id, ann in annotations.items()
    }


# ---------------------------------------------------------------------------
# HTML triage page
# ---------------------------------------------------------------------------


def _annotation_icon(annotation: TriageAnnotation | None) -> str:
    """Return a unicode icon representing the annotation verdict."""
    if annotation is None:
        return ""
    icons = {"pass": "\u2713", "fail": "\u2717", "defer": "?", "note": "\u270e"}
    return icons.get(annotation.verdict, "")


@dataclass(frozen=True)
class TrialRow:
    """Pre-computed view model for one trial in the triage list."""

    trial_id: str
    experiment_id: str
    task_id: str
    model: str
    adapter: str
    discipline: str
    reward: float
    reward_class: str
    annotation_icon: str
    annotation_verdict: str


def _filter_by_reward(
    records: list[TrialRecord],
    reward_filter: str,
) -> list[TrialRecord]:
    """Apply reward-band filtering to a list of trial records."""
    if reward_filter == "zero":
        return [r for r in records if r.evaluation.reward == 0.0]
    if reward_filter == "partial":
        return [r for r in records if 0.0 < r.evaluation.reward < 1.0]
    if reward_filter == "perfect":
        return [r for r in records if r.evaluation.reward >= 1.0]
    return records


def _filter_by_annotated(
    records: list[TrialRecord],
    annotated_filter: str,
    annotations: dict[str, TriageAnnotation],
) -> list[TrialRecord]:
    """Apply annotated/unannotated filtering to a list of trial records."""
    if annotated_filter == "yes":
        return [r for r in records if r.trial_id in annotations]
    if annotated_filter == "no":
        return [r for r in records if r.trial_id not in annotations]
    return records


def _filter_by_errors(
    records: list[TrialRecord],
    errors_filter: str,
    ledger_root: Path,
) -> list[TrialRecord]:
    """Apply error filtering based on trajectory exit codes."""
    if errors_filter not in ("with_errors", "clean"):
        return records

    result: list[TrialRecord] = []
    for record in records:
        has_errors = False
        traj_path_str = record.outputs.trajectory_path
        if traj_path_str:
            traj_path = Path(traj_path_str)
            if traj_path.exists():
                entries = read_trajectory(traj_path)
                has_errors = any(
                    e.exit_code is not None and e.exit_code != 0 for e in entries if e.call_type != "warmup"
                )
        if errors_filter == "with_errors" and has_errors:
            result.append(record)
        elif errors_filter == "clean" and not has_errors:
            result.append(record)
    return result


def _sort_trials(records: list[TrialRecord], sort_key: str) -> list[TrialRecord]:
    """Sort trial records by the given key."""
    if sort_key == "reward_asc":
        return sorted(records, key=lambda r: r.evaluation.reward)
    if sort_key == "reward_desc":
        return sorted(records, key=lambda r: r.evaluation.reward, reverse=True)
    if sort_key == "model":
        return sorted(records, key=lambda r: r.agent.model)
    if sort_key == "task":
        return sorted(records, key=lambda r: r.task.task_id)
    return list(records)


def _build_filter_query(
    filters: dict[str, str],
    *,
    override_key: str | None = None,
    override_value: str | None = None,
) -> str:
    """Build a URL query string from filter dict, optionally overriding one key."""
    merged = dict(filters)
    if override_key is not None:
        if override_value:
            merged[override_key] = override_value
        else:
            merged.pop(override_key, None)
    parts = [f"{k}={v}" for k, v in sorted(merged.items()) if v]
    return "&".join(parts)


@router.get("/api/triage")
def get_triage_api(
    request: Request,
    experiment: str | None = None,
    model: str | None = None,
    adapter: str | None = None,
    task_type: str | None = None,
    reward: str | None = None,
    errors: str | None = None,
    annotated: str | None = None,
    sort: str | None = None,
) -> TriageResponse:
    """Return triage trial list as JSON with all filter params supported."""
    settings = get_web_settings(request)
    sort_key = sort or "reward_asc"

    # Load trial records — optionally scoped to experiment and model
    if experiment:
        records = query_trial_records(
            settings.ledger_root,
            experiment_id=experiment,
            model=model,
        )
    elif model:
        records = query_trial_records(settings.ledger_root, model=model)
    else:
        records = read_trial_records(settings.ledger_root)

    # Load annotations for all relevant experiments
    annotations: dict[str, TriageAnnotation] = {}
    for exp_id in {r.experiment_id for r in records}:
        exp_dir = settings.ledger_root / exp_id
        annotations.update(load_annotations(exp_dir))

    # Apply adapter filter
    if adapter:
        records = [r for r in records if r.agent.adapter == adapter]

    # Apply task_type filter (second segment of task_id)
    if task_type:
        records = [
            r for r in records if len(r.task.task_id.split("/")) > 1 and r.task.task_id.split("/")[1] == task_type
        ]

    # Apply post-read filters
    if reward:
        records = _filter_by_reward(records, reward)
    if annotated:
        records = _filter_by_annotated(records, annotated, annotations)
    if errors:
        records = _filter_by_errors(records, errors, settings.ledger_root)

    # Sort
    records = _sort_trials(records, sort_key)

    # Discover available experiments and models for dropdowns
    all_records = read_trial_records(settings.ledger_root)
    experiments_list = sorted({r.experiment_id for r in all_records})
    models_list = sorted({r.agent.model for r in all_records})

    # Build current filter state
    filters: dict[str, str] = {}
    if experiment:
        filters["experiment"] = experiment
    if model:
        filters["model"] = model
    if adapter:
        filters["adapter"] = adapter
    if task_type:
        filters["task_type"] = task_type
    if reward:
        filters["reward"] = reward
    if errors:
        filters["errors"] = errors
    if annotated:
        filters["annotated"] = annotated
    if sort:
        filters["sort"] = sort

    # Build trial rows
    trial_rows: list[TrialRowSchema] = []
    for record in records:
        ann = annotations.get(record.trial_id)
        trial_rows.append(
            TrialRowSchema(
                trial_id=record.trial_id,
                experiment_id=record.experiment_id,
                task_id=record.task.task_id,
                model=record.agent.model,
                adapter=record.agent.adapter,
                discipline=extract_discipline(record.task.task_id),
                reward=record.evaluation.reward,
                reward_class=reward_css_class(record.evaluation.reward),
                annotation_icon=_annotation_icon(ann),
                annotation_verdict=ann.verdict if ann else "",
            )
        )

    return TriageResponse(
        trials=trial_rows,
        trial_count=len(trial_rows),
        annotations={tid: {"verdict": ann.verdict, "icon": _annotation_icon(ann)} for tid, ann in annotations.items()},
        filters=filters,
        experiments=experiments_list,
        models=models_list,
    )
