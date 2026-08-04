# ABOUTME: Export routes for current experiment communication artefacts.
# ABOUTME: Keeps public and internal experiment exports behind explicit access gates.

from fastapi import APIRouter, Depends, HTTPException, Request, status

from aec_bench.communication.standalone import (
    build_internal_experiment_artifact,
    build_public_experiment_artifact,
)
from aec_bench.web.dependencies import get_web_settings, require_internal_access

router = APIRouter()


@router.get("/api/public/experiments/{experiment_id}")
def public_experiment(request: Request, experiment_id: str) -> dict[str, object]:
    settings = get_web_settings(request)
    try:
        return build_public_experiment_artifact(
            ledger_root=settings.ledger_root,
            tasks_root=settings.tasks_root,
            experiment_id=experiment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get(
    "/api/internal/experiments/{experiment_id}",
    dependencies=[Depends(require_internal_access)],
)
def internal_experiment(request: Request, experiment_id: str) -> dict[str, object]:
    settings = get_web_settings(request)
    try:
        return build_internal_experiment_artifact(
            ledger_root=settings.ledger_root,
            tasks_root=settings.tasks_root,
            experiment_id=experiment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
