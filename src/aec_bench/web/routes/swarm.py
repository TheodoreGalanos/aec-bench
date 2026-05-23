# ABOUTME: Swarm Mission Control API routes for state snapshots, event logs, and SSE streams.
# ABOUTME: Serves live and completed swarm run data to the frontend dashboard.

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    SwarmAgentSchema,
    SwarmBudgetSchema,
    SwarmCentroidSchema,
    SwarmConsolidationSchema,
    SwarmEventSchema,
    SwarmEventsResponse,
    SwarmLineageNodeSchema,
    SwarmNoteSchema,
    SwarmRunsResponse,
    SwarmRunSummarySchema,
    SwarmStateResponse,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _find_swarm_dirs(workspaces_root: Path) -> list[Path]:
    """Scan workspaces_root for directories containing _swarm_runs/events.jsonl."""
    swarm_dirs = []
    if not workspaces_root.exists():
        return swarm_dirs
    for candidate in workspaces_root.iterdir():
        if not candidate.is_dir():
            continue
        swarm_dir = candidate / "_swarm_runs"
        if (swarm_dir / "events.jsonl").exists():
            swarm_dirs.append(swarm_dir)
    return swarm_dirs


def _read_summary(swarm_dir: Path) -> dict[str, Any] | None:
    """Read summary.json from a swarm run directory. Returns None if absent."""
    summary_path = swarm_dir / "summary.json"
    if not summary_path.exists():
        return None
    return json.loads(summary_path.read_text(encoding="utf-8"))


def _read_events(swarm_dir: Path, after: int = -1) -> list[dict[str, Any]]:
    """Read events from events.jsonl, filtering by sequence_number > after."""
    events_path = swarm_dir / "events.jsonl"
    if not events_path.exists():
        return []
    events: list[dict[str, Any]] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        event = json.loads(line)
        if event.get("sequence_number", 0) > after:
            events.append(event)
    return events


def _resolve_swarm_dir(request: Request, workspace: str) -> tuple[Path, Path]:
    """Validate workspace name and return (workspace_path, swarm_dir).

    Raises HTTP 404 if workspaces_root is not configured, the workspace
    directory does not exist, or the _swarm_runs directory is absent.
    """
    settings = get_web_settings(request)
    if settings.workspaces_root is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workspaces root configured",
        )
    ws_path = settings.workspaces_root / workspace
    if not ws_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace}' not found",
        )
    swarm_dir = ws_path / "_swarm_runs"
    if not swarm_dir.is_dir() or not (swarm_dir / "events.jsonl").exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No swarm run data for workspace '{workspace}'",
        )
    return ws_path, swarm_dir


def _build_agent_map_from_lineage(lineage_path: Path) -> dict[str, str]:
    """Build a version → agent_id mapping from lineage.json.

    Handles both list-of-records and {"records": [...]} formats.
    """
    if not lineage_path.exists():
        return {}
    raw = json.loads(lineage_path.read_text(encoding="utf-8"))
    # Normalise to list
    if isinstance(raw, dict):
        records = raw.get("records", [])
    else:
        records = raw

    agent_map: dict[str, str] = {}
    for item in records:
        # Each item may be {"record": {...}, "narrative": {...}} or a flat record
        record = item.get("record", item)
        version = record.get("entry_version")
        agent_id = record.get("source_agent_id")
        if version and agent_id:
            agent_map[version] = agent_id
    return agent_map


def _derive_swarm_status(summary: dict[str, Any] | None) -> str:
    """Derive run status string from summary data."""
    if summary is None:
        return "active"
    if summary.get("elapsed_seconds") is not None:
        return "completed"
    return "active"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/api/evolution/swarm/runs")
def swarm_runs(request: Request) -> SwarmRunsResponse:
    """List all swarm runs across workspaces."""
    settings = get_web_settings(request)
    if settings.workspaces_root is None:
        return SwarmRunsResponse(runs=[])

    swarm_dirs = _find_swarm_dirs(settings.workspaces_root)
    runs: list[SwarmRunSummarySchema] = []

    for swarm_dir in swarm_dirs:
        workspace_name = swarm_dir.parent.name
        summary = _read_summary(swarm_dir)

        # Derive run_id from summary or swarm_started event
        run_id = ""
        if summary:
            run_id = summary.get("run_id", "")
        if not run_id:
            events = _read_events(swarm_dir)
            for event in events:
                if event.get("event_type") == "swarm_started":
                    run_id = event.get("payload", {}).get("run_id", "")
                    break

        # Strategy from workspace evolution.yaml
        strategy = "qd"
        evo_yaml = swarm_dir.parent / "evolution.yaml"
        if evo_yaml.exists():
            for line in evo_yaml.read_text(encoding="utf-8").splitlines():
                if line.startswith("strategy:"):
                    strategy = line.split(":", 1)[1].strip()
                    break

        run_summary = SwarmRunSummarySchema(
            run_id=run_id,
            workspace=workspace_name,
            status=_derive_swarm_status(summary),
            agent_count=summary.get("agent_count", 0) if summary else 0,
            total_evals=summary.get("total_evals", 0) if summary else 0,
            best_score=summary.get("best_score", 0.0) if summary else 0.0,
            total_cost_usd=summary.get("total_cost_usd", 0.0) if summary else 0.0,
            elapsed_seconds=summary.get("elapsed_seconds", 0.0) if summary else 0.0,
            strategy=strategy,
        )
        runs.append(run_summary)

    return SwarmRunsResponse(runs=runs)


@router.get("/api/evolution/swarm/{workspace}/state")
def swarm_state(request: Request, workspace: str) -> SwarmStateResponse:
    """Full state snapshot for the swarm Mission Control dashboard.

    Reconstructs agent states by replaying events, loads the QD archive,
    lineage, notes, and consolidation data.
    """
    ws_path, swarm_dir = _resolve_swarm_dir(request, workspace)

    events_raw = _read_events(swarm_dir)
    summary = _read_summary(swarm_dir)

    # Derive basic run metadata from summary or swarm_started event
    run_id = summary.get("run_id", "") if summary else ""
    max_cost_usd = 5.0
    total_cost_usd = summary.get("total_cost_usd", 0.0) if summary else 0.0
    best_score_overall = summary.get("best_score", 0.0) if summary else 0.0
    elapsed_seconds = summary.get("elapsed_seconds", 0.0) if summary else 0.0
    total_evals_summary = summary.get("total_evals", 0) if summary else 0

    for event in events_raw:
        if event.get("event_type") == "swarm_started":
            payload = event.get("payload", {})
            if not run_id:
                run_id = payload.get("run_id", "")
            max_cost_usd = payload.get("max_cost_usd", max_cost_usd)
            break

    # Reconstruct agent states by replaying events
    agents: dict[str, dict[str, Any]] = {}
    total_cost_from_events = 0.0
    eval_count_total = 0

    for event in events_raw:
        event_type = event.get("event_type", "")
        agent_id = event.get("agent_id")
        payload = event.get("payload", {})

        if event_type == "agent_spawned" and agent_id:
            agents[agent_id] = {
                "agent_id": agent_id,
                "model": payload.get("model", ""),
                "status": "active",
                "eval_count": 0,
                "best_score": 0.0,
                "budget_consumed_usd": 0.0,
                "restart_count": 0,
                "nudge": payload.get("nudge") or "",
            }

        elif event_type == "eval_completed" and agent_id and agent_id in agents:
            score = payload.get("score", 0.0)
            agents[agent_id]["eval_count"] += 1
            eval_count_total += 1
            if score > agents[agent_id]["best_score"]:
                agents[agent_id]["best_score"] = score

        elif event_type == "budget_spent" and agent_id and agent_id in agents:
            amount = payload.get("amount_usd", 0.0)
            agents[agent_id]["budget_consumed_usd"] += amount
            total_cost_from_events += amount

        elif event_type in ("agent_retired", "agent_pivoting") and agent_id and agent_id in agents:
            agents[agent_id]["status"] = event_type.replace("agent_", "")

        elif event_type == "agent_restarted" and agent_id and agent_id in agents:
            agents[agent_id]["status"] = "active"
            agents[agent_id]["restart_count"] = agents[agent_id].get("restart_count", 0) + 1

    agent_schemas = [SwarmAgentSchema(**a) for a in agents.values()]

    # Compute budget spend percentage
    effective_spent = total_cost_usd or total_cost_from_events
    spend_pct = (effective_spent / max_cost_usd) if max_cost_usd > 0 else 0.0
    if spend_pct >= 0.9:
        phase = "winding_down"
    elif spend_pct >= 0.5:
        phase = "mid"
    else:
        phase = "early"

    budget = SwarmBudgetSchema(
        max_cost_usd=max_cost_usd,
        total_spent_usd=effective_spent,
        spend_percentage=spend_pct,
        phase=phase,
    )

    # Load QD archive with centroid projections
    centroids: list[SwarmCentroidSchema] = []
    archive_path = swarm_dir / "archive.json"
    if archive_path.exists():
        try:
            from aec_bench.evolution.archive import QDArchive

            agent_map = _build_agent_map_from_lineage(swarm_dir / "lineage.json")
            archive = QDArchive.load(archive_path)
            raw_centroids = archive.project_2d_with_centroids(agent_map=agent_map)
            centroids = [SwarmCentroidSchema(**c) for c in raw_centroids]
        except Exception:
            pass

    # Load lineage nodes
    lineage: list[SwarmLineageNodeSchema] = []
    lineage_path = swarm_dir / "lineage.json"
    if lineage_path.exists():
        raw = json.loads(lineage_path.read_text(encoding="utf-8"))
        records = raw if isinstance(raw, list) else raw.get("records", [])
        for item in records:
            record = item.get("record", item)
            narrative = item.get("narrative", {}) if isinstance(item, dict) else {}
            lineage.append(
                SwarmLineageNodeSchema(
                    version=record.get("entry_version", ""),
                    parent_version=record.get("parent_version"),
                    agent_id=record.get("source_agent_id", ""),
                    cross_agent=record.get("cross_agent", False),
                    surprise=record.get("surprise", False),
                    mutation_type=record.get("mutation_type", ""),
                    narrative=(narrative.get("agent_reasoning", "") if isinstance(narrative, dict) else ""),
                )
            )

    # Load notes
    notes: list[SwarmNoteSchema] = []
    notes_path = swarm_dir / "notes.json"
    if notes_path.exists():
        raw_notes = json.loads(notes_path.read_text(encoding="utf-8"))
        for n in raw_notes if isinstance(raw_notes, list) else []:
            notes.append(
                SwarmNoteSchema(
                    note_id=n.get("note_id", ""),
                    agent_id=n.get("agent_id", ""),
                    timestamp=n.get("timestamp", ""),
                    title=n.get("title", ""),
                    content=n.get("content", ""),
                    tags=n.get("tags", []),
                )
            )

    # Load consolidation reports
    consolidation_reports: list[SwarmConsolidationSchema] = []
    consolidation_path = swarm_dir / "consolidation.json"
    if consolidation_path.exists():
        raw_cons = json.loads(consolidation_path.read_text(encoding="utf-8"))
        # May be a single dict or a list
        if isinstance(raw_cons, dict):
            raw_cons = [raw_cons]
        for c in raw_cons:
            consolidation_reports.append(
                SwarmConsolidationSchema(
                    report_id=c.get("report_id", ""),
                    timestamp=c.get("timestamp", ""),
                    archive_coverage_pct=c.get("archive_coverage_pct", 0.0),
                    total_evals=c.get("total_evals", 0),
                    cross_agent_patterns=c.get("cross_agent_patterns", []),
                    strategy_recommendations=c.get("strategy_recommendations", []),
                    counterintuitive_findings=c.get("counterintuitive_findings", []),
                    lineage_insights=c.get("lineage_insights", ""),
                )
            )

    event_schemas = [
        SwarmEventSchema(
            event_type=e.get("event_type", ""),
            timestamp=e.get("timestamp", ""),
            agent_id=e.get("agent_id"),
            payload=e.get("payload", {}),
            sequence_number=e.get("sequence_number", 0),
        )
        for e in events_raw
    ]

    effective_evals = total_evals_summary or eval_count_total

    return SwarmStateResponse(
        run_id=run_id,
        workspace=workspace,
        status=_derive_swarm_status(summary),
        agents=agent_schemas,
        budget=budget,
        centroids=centroids,
        lineage=lineage,
        notes=notes,
        consolidation_reports=consolidation_reports,
        events=event_schemas,
        total_evals=effective_evals,
        best_score=best_score_overall,
        elapsed_seconds=elapsed_seconds,
    )


@router.get("/api/evolution/swarm/{workspace}/events")
def swarm_events(
    request: Request,
    workspace: str,
    after: int = -1,
) -> SwarmEventsResponse:
    """Return swarm events with sequence_number greater than `after`."""
    _ws_path, swarm_dir = _resolve_swarm_dir(request, workspace)

    raw_events = _read_events(swarm_dir, after=after)
    events = [
        SwarmEventSchema(
            event_type=e.get("event_type", ""),
            timestamp=e.get("timestamp", ""),
            agent_id=e.get("agent_id"),
            payload=e.get("payload", {}),
            sequence_number=e.get("sequence_number", 0),
        )
        for e in raw_events
    ]
    return SwarmEventsResponse(events=events)


@router.get("/api/evolution/swarm/{workspace}/events/stream")
async def swarm_events_stream(request: Request, workspace: str) -> StreamingResponse:
    """SSE endpoint for live swarm events.

    For completed runs (summary.json has elapsed_seconds), returns 204.
    For active runs, tails events.jsonl and yields SSE-formatted lines.
    """
    _ws_path, swarm_dir = _resolve_swarm_dir(request, workspace)

    summary = _read_summary(swarm_dir)
    if summary and summary.get("elapsed_seconds") is not None:
        return StreamingResponse(
            content=iter([]),
            status_code=204,
            media_type="text/event-stream",
        )

    def event_generator() -> Generator[str]:
        last_seq = -1
        while True:
            raw_events = _read_events(swarm_dir, after=last_seq)
            for event in raw_events:
                seq = event.get("sequence_number", 0)
                last_seq = max(last_seq, seq)
                yield f"data: {json.dumps(event)}\n\n"
            # Check if still active
            current_summary = _read_summary(swarm_dir)
            if current_summary and current_summary.get("elapsed_seconds") is not None:
                yield "event: done\ndata: {}\n\n"
                break

    return StreamingResponse(
        content=event_generator(),
        media_type="text/event-stream",
    )
