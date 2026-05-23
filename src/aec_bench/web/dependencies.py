# ABOUTME: Shared dependency helpers for the FastAPI communication web layer.
# ABOUTME: Carries app settings and enforces explicit internal-route access control.

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from secrets import compare_digest
from typing import cast

from fastapi import HTTPException, Request, status
from starlette.responses import Response

INTERNAL_ACCESS_HEADER_NAME = "X-AEC-BENCH-Internal-Token"
INTERNAL_ACCESS_COOKIE_NAME = "aec_bench_internal_token"


@dataclass(frozen=True)
class WebSettings:
    ledger_root: Path
    tasks_root: Path
    feedback_root: Path
    datasets_root: Path
    benchmark_templates_root: Path  # benchmark template catalogue (not Jinja2 templates)
    internal_token: str | None = None
    workspaces_root: Path | None = None


def get_web_settings(request: Request) -> WebSettings:
    return cast(WebSettings, request.app.state.settings)


def set_internal_access_cookie(request: Request, response: Response) -> None:
    settings = get_web_settings(request)
    if settings.internal_token is None:
        return
    response.set_cookie(
        key=INTERNAL_ACCESS_COOKIE_NAME,
        value=settings.internal_token,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def require_internal_access(request: Request) -> None:
    settings = get_web_settings(request)
    provided_values = (
        request.headers.get(INTERNAL_ACCESS_HEADER_NAME),
        request.cookies.get(INTERNAL_ACCESS_COOKIE_NAME),
    )
    if settings.internal_token is None or not any(
        provided is not None and compare_digest(provided, settings.internal_token) for provided in provided_values
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="internal access required",
        )
