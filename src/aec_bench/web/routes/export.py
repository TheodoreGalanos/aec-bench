# ABOUTME: Export routes for internal communication artefacts in the Phase 7 web layer.
# ABOUTME: Keeps adaptation-family and experiment exports behind explicit access gates.

from fastapi import APIRouter, Depends, HTTPException, Request, status

from aec_bench.communication.standalone import (
    build_adaptation_family_artifact,
    build_internal_experiment_artifact,
    build_public_experiment_artifact,
)
from aec_bench.web.dependencies import get_web_settings, require_internal_access

router = APIRouter()


@router.get("/api/internal/adaptation/{family_id}", dependencies=[Depends(require_internal_access)])
def internal_adaptation_export(
    request: Request,
    family_id: str,
    experiment_id: str | None = None,
) -> dict[str, object]:
    settings = get_web_settings(request)
    try:
        return build_adaptation_family_artifact(
            ledger_root=settings.ledger_root,
            family_id=family_id,
            experiment_id=experiment_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


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
