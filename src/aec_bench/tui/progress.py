# ABOUTME: Builds the TUI view model for the shared read-only run progress projection.
# ABOUTME: Keeps TUI rendering separate from progress counting and evidence loading.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from aec_bench.execution.progress import RunProgress
from aec_bench.harness.run_progress import RunProgressSurface, load_run_progress, present_run_progress


@dataclass(frozen=True, slots=True)
class RunProgressViewModel:
    """Compact TUI values copied from one validated RunProgress."""

    run_id: str
    plan_id: str
    status: str
    planned: int
    succeeded: int
    failed: int
    running: int
    queued: int
    unknown: int
    cancelled: int
    retries: int
    completion_blocked: bool


def render_run_progress(view_model: RunProgressViewModel) -> str:
    """Render values already calculated by the shared projection."""

    return "\n".join(
        (
            f"Run: {view_model.run_id}",
            f"Plan: {view_model.plan_id}",
            f"Status: {view_model.status}",
            f"Planned: {view_model.planned}",
            f"Succeeded: {view_model.succeeded}",
            f"Failed: {view_model.failed}",
            f"Running: {view_model.running}",
            f"Queued: {view_model.queued}",
            f"Unknown: {view_model.unknown}",
            f"Cancelled: {view_model.cancelled}",
            f"Retries: {view_model.retries}",
            f"Completion blocked: {'yes' if view_model.completion_blocked else 'no'}",
        )
    )


def build_run_progress_view_model(progress: RunProgress | RunProgressSurface) -> RunProgressViewModel:
    """Build a display model without recalculating any progress metric."""

    surface = progress if isinstance(progress, RunProgressSurface) else present_run_progress(progress)
    return RunProgressViewModel(
        run_id=str(surface.run_id),
        plan_id=str(surface.plan_id),
        status=surface.status,
        planned=surface.planned,
        succeeded=surface.succeeded,
        failed=surface.failed,
        running=surface.running,
        queued=surface.queued,
        unknown=surface.unknown,
        cancelled=surface.cancelled,
        retries=surface.retries,
        completion_blocked=surface.completion_blocked,
    )


def load_run_progress_view_model(
    run_id: str,
    *,
    operational_store_path: Path,
    plan_root: Path,
) -> RunProgressViewModel:
    """Load one projection from explicit roots for TUI callers."""

    return build_run_progress_view_model(
        load_run_progress(
            run_id,
            operational_store_path=operational_store_path,
            plan_root=plan_root,
        )
    )
