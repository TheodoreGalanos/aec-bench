# ABOUTME: Exposes the provider-neutral read-only run progress projection.
# ABOUTME: Requires explicit operational and portable plan roots; it never hydrates evidence attachments.

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from aec_bench.execution.operational.store import OperationalStoreError, OperationalStoreNotFound
from aec_bench.harness.run_progress import load_run_progress_surface
from aec_bench.ledger.evidence_run_store import EvidenceRunStoreError, EvidenceRunStoreIncomplete
from aec_bench.web.dependencies import get_web_settings
from aec_bench.web.schemas import RunProgressResponse

router = APIRouter()


@router.get("/api/runs/{run_id}/status", response_model=RunProgressResponse)
def run_progress_api(request: Request, run_id: str) -> RunProgressResponse:
    """Return progress for one exact run and authoritative plan."""

    settings = get_web_settings(request)
    if settings.operational_store_path is None or settings.plan_root is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="run progress requires explicit operational_store_path and plan_root",
        )
    try:
        return load_run_progress_surface(
            run_id,
            operational_store_path=settings.operational_store_path,
            plan_root=settings.plan_root,
        )
    except (EvidenceRunStoreIncomplete, OperationalStoreNotFound) as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except (EvidenceRunStoreError, OperationalStoreError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
