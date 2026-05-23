# ABOUTME: FastAPI app factory for the Phase 7 communication web layer.
# ABOUTME: Wires public and internal routes to shared standalone communication builders.

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from aec_bench.web.dependencies import WebSettings, set_internal_access_cookie
from aec_bench.web.routes.analyze import router as analyze_router
from aec_bench.web.routes.dashboard import router as dashboard_router
from aec_bench.web.routes.datasets import router as datasets_router
from aec_bench.web.routes.evolution import router as evolution_router
from aec_bench.web.routes.export import router as export_router
from aec_bench.web.routes.leaderboard import router as leaderboard_router
from aec_bench.web.routes.library import router as library_router
from aec_bench.web.routes.review import router as review_router
from aec_bench.web.routes.search import router as search_router
from aec_bench.web.routes.swarm import router as swarm_router
from aec_bench.web.routes.triage import router as triage_router
from aec_bench.web.routes.viewer import router as viewer_router


def create_app(
    *,
    ledger_root: Path,
    tasks_root: Path,
    feedback_root: Path | None = None,
    datasets_root: Path | None = None,
    internal_token: str | None = None,
    benchmark_templates_root: Path | None = None,
    frontend_dist: Path | None = None,
    workspaces_root: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="aec-bench communication and feedback")
    resolved_benchmark = benchmark_templates_root or (Path(__file__).resolve().parents[1] / "templates" / "builtin")
    app.state.settings = WebSettings(
        ledger_root=ledger_root,
        tasks_root=tasks_root,
        feedback_root=feedback_root or (ledger_root.parent / "feedback"),
        datasets_root=datasets_root or (ledger_root.parent / "datasets"),
        benchmark_templates_root=resolved_benchmark,
        internal_token=internal_token,
        workspaces_root=workspaces_root,
    )

    app.include_router(analyze_router)
    app.include_router(dashboard_router)
    app.include_router(datasets_router)
    app.include_router(swarm_router)
    app.include_router(evolution_router)
    app.include_router(leaderboard_router)
    app.include_router(library_router)
    app.include_router(export_router)
    app.include_router(review_router)
    app.include_router(search_router)
    app.include_router(triage_router)
    app.include_router(viewer_router)

    # Serve Svelte SPA if frontend dist directory exists
    resolved_frontend_dist = frontend_dist
    if resolved_frontend_dist is None:
        candidate = Path(__file__).resolve().parent / "frontend" / "dist"
        if candidate.exists():
            resolved_frontend_dist = candidate

    index_html = resolved_frontend_dist / "index.html" if resolved_frontend_dist else None
    if resolved_frontend_dist and resolved_frontend_dist.exists() and index_html and index_html.exists():
        # Mount built assets (JS, CSS) at /assets
        assets_dir = resolved_frontend_dist / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        # SPA catch-all — MUST be registered LAST so /api/* routes take precedence
        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str, request: Request) -> HTMLResponse:
            response = HTMLResponse(content=index_html.read_text(encoding="utf-8"))
            set_internal_access_cookie(request, response)
            return response

    return app
