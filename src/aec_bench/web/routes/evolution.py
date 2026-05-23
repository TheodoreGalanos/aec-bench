# ABOUTME: Evolution API routes for workspace discovery, cycle data, file trees, and diffs.
# ABOUTME: Serves git-backed evolution history to the frontend explorer.

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.evolution.report_data import (
    build_evolution_report_data,
    discover_workspaces,
    get_file_at_version,
    get_file_diff_at_version,
    get_file_tree_at_version,
)
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import (
    EvolutionCycleSchema,
    EvolutionDataResponse,
    EvolutionDiffResponse,
    EvolutionFileResponse,
    EvolutionRunSchema,
    EvolutionRunsResponse,
    EvolutionTreeResponse,
    EvolutionWorkspacesResponse,
    EvolutionWorkspaceSummarySchema,
    FileTreeNodeSchema,
    GraveyardEntrySchema,
    GraveyardResponse,
)

router = APIRouter()


def _read_workspace_strategy(ws_path: Path) -> str:
    """Read strategy from workspace evolution config."""
    from aec_bench.evolution.report_data import _read_strategy

    return _read_strategy(ws_path)


def _resolve_workspace(request: Request, workspace: str) -> Path:
    """Validate and return the filesystem path for a workspace name.

    Raises 404 if workspaces_root is not configured, the workspace
    directory does not exist, or it is missing required config files.
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

    manifest = ws_path / "manifest.yaml"
    evolution = ws_path / "evolution.yaml"
    if not manifest.exists() or not evolution.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace '{workspace}' is missing manifest.yaml or evolution.yaml",
        )

    return ws_path


def _dict_to_tree_node(raw: dict) -> FileTreeNodeSchema:
    """Recursively convert a raw tree dict to a FileTreeNodeSchema."""
    children = None
    if raw.get("children") is not None:
        children = [_dict_to_tree_node(c) for c in raw["children"]]
    return FileTreeNodeSchema(
        name=raw["name"],
        type=raw["type"],
        status=raw.get("status", "unchanged"),
        size=raw.get("size"),
        children=children,
    )


@router.get("/api/evolution/workspaces")
def evolution_workspaces(request: Request) -> EvolutionWorkspacesResponse:
    """List all discovered evolution workspaces."""
    settings = get_web_settings(request)
    if settings.workspaces_root is None or not settings.workspaces_root.exists():
        return EvolutionWorkspacesResponse(workspaces=[])

    raw_workspaces = discover_workspaces(settings.workspaces_root)
    workspaces = [
        EvolutionWorkspaceSummarySchema(
            name=ws["name"],
            path=ws["path"],
            run_id=ws.get("run_id", ""),
            strategy=ws.get("strategy", "unknown"),
            cycles=ws["cycles"],
            best_score=ws["best_score"],
            final_score=ws["final_score"],
            model=ws["model"],
            has_swarm=(settings.workspaces_root / ws["path"] / "_swarm_runs" / "events.jsonl").exists(),
        )
        for ws in raw_workspaces
    ]
    return EvolutionWorkspacesResponse(workspaces=workspaces)


@router.get("/api/evolution/{workspace}")
def evolution_detail(
    request: Request,
    workspace: str,
    run_id: str | None = None,
) -> EvolutionDataResponse:
    """Return full evolution report data for a single workspace."""
    ws_path = _resolve_workspace(request, workspace)
    report = build_evolution_report_data(ws_path, run_id=run_id)

    cycles = [
        EvolutionCycleSchema(
            cycle=c.cycle,
            version_tag=c.version_tag,
            score=c.score,
            prompt_diff=c.prompt_diff,
            skills_added=c.skills_added,
            skills_modified=c.skills_modified,
            skills_removed=c.skills_removed,
            skill_diffs=c.skill_diffs,
            evolver_reasoning=c.evolver_reasoning,
        )
        for c in report.cycles
    ]

    return EvolutionDataResponse(
        workspace_name=report.workspace_name,
        model=report.model,
        strategy=_read_workspace_strategy(ws_path),
        total_cycles=report.total_cycles,
        converged=report.converged,
        best_score=report.best_score,
        final_score=report.final_score,
        cycles=cycles,
    )


@router.get("/api/evolution/{workspace}/runs")
def evolution_runs(request: Request, workspace: str) -> EvolutionRunsResponse:
    """List all evolution runs in a workspace, grouped by run_id."""
    ws_path = _resolve_workspace(request, workspace)

    from aec_bench.evolution.report_data import list_runs

    raw_runs = list_runs(ws_path)
    runs = [
        EvolutionRunSchema(
            run_id=r["run_id"],
            strategy=r["strategy"],
            cycles=r["cycles"],
            best_score=r["best_score"],
            final_score=r["final_score"],
        )
        for r in raw_runs
    ]
    return EvolutionRunsResponse(runs=runs)


@router.get("/api/evolution/{workspace}/graveyard")
def evolution_graveyard(request: Request, workspace: str) -> GraveyardResponse:
    """Return enriched graveyard entries for a workspace."""
    settings = get_web_settings(request)
    if settings.workspaces_root is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No workspaces root",
        )

    ws_path = settings.workspaces_root / workspace
    graveyard_path = ws_path / "graveyard.json"

    if not graveyard_path.exists():
        return GraveyardResponse(entries=[], total=0)

    from aec_bench.evolution.graveyard import MutationGraveyard

    graveyard = MutationGraveyard.load(graveyard_path)
    all_entries = graveyard.browse(limit=50)

    entries = [
        GraveyardEntrySchema(
            cycle=e.cycle,
            strategy=e.strategy,
            mutation_description=e.mutation_description,
            score_before=e.score_before,
            score_after=e.score_after,
            failure_reason=e.failure_reason,
            field_failures=e.field_failures,
            detected_patterns=e.detected_patterns,
            mutation_actions=e.mutation_actions,
            investigation_summary=e.investigation_summary,
        )
        for e in all_entries
    ]
    return GraveyardResponse(entries=entries, total=graveyard.size)


@router.get("/api/evolution/{workspace}/tree/{version}")
def evolution_tree(
    request: Request,
    workspace: str,
    version: str,
) -> EvolutionTreeResponse:
    """Return the file tree at a specific evo-N version."""
    ws_path = _resolve_workspace(request, workspace)
    raw_tree = get_file_tree_at_version(ws_path, version)

    # raw_tree is the root node dict — return its children as the top-level list
    children = raw_tree.get("children", [])
    tree_nodes = [_dict_to_tree_node(c) for c in children]

    return EvolutionTreeResponse(version=version, tree=tree_nodes)


@router.get("/api/evolution/{workspace}/file/{version}/{path:path}")
def evolution_file(
    request: Request,
    workspace: str,
    version: str,
    path: str,
) -> EvolutionFileResponse:
    """Return file content at a specific version."""
    ws_path = _resolve_workspace(request, workspace)
    data = get_file_at_version(ws_path, version, path)
    return EvolutionFileResponse(
        path=data["path"],
        version=data["version"],
        content=data["content"],
        language=data["language"],
    )


@router.get("/api/evolution/{workspace}/archive")
async def get_archive(workspace: str, request: Request) -> dict:
    """Return the QD archive data for a workspace: 2D projection + summary."""
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
            detail=f"Workspace not found: {workspace}",
        )

    archive_path = ws_path / "archive.json"
    if not archive_path.exists():
        return {
            "summary": {"size": 0, "coverage": 0.0, "n_centroids": 200},
            "points_2d": [],
        }

    from aec_bench.evolution.archive import QDArchive

    archive = QDArchive.load(archive_path)
    return {
        "summary": archive.to_summary(),
        "points_2d": archive.project_2d(),
    }


@router.get("/api/evolution/{workspace}/diff/{version}/{path:path}")
def evolution_diff(
    request: Request,
    workspace: str,
    version: str,
    path: str,
) -> EvolutionDiffResponse:
    """Return the unified diff of a file between the previous version and this one."""
    ws_path = _resolve_workspace(request, workspace)
    data = get_file_diff_at_version(ws_path, version, path)
    return EvolutionDiffResponse(
        path=data["path"],
        from_version=data["from_version"] or "",
        to_version=data["to_version"],
        diff=data["diff"],
    )
