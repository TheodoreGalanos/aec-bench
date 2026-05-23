# ABOUTME: Tests for WebSettings configuration and app creation.
# ABOUTME: Verifies settings structure and app factory behaviour.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


def _make_app(tmp_path: Path) -> TestClient:
    ledger_root = tmp_path / "ledger"
    ledger_root.mkdir()
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()
    app = create_app(ledger_root=ledger_root, tasks_root=tasks_root)
    return TestClient(app)


def test_web_settings_has_benchmark_templates_root(tmp_path: Path) -> None:
    """WebSettings should carry the benchmark templates root path."""
    from aec_bench.web.dependencies import WebSettings

    settings = WebSettings(
        ledger_root=tmp_path / "ledger",
        tasks_root=tmp_path / "tasks",
        feedback_root=tmp_path / "feedback",
        datasets_root=tmp_path / "datasets",
        benchmark_templates_root=tmp_path / "benchmark",
    )
    assert settings.benchmark_templates_root == tmp_path / "benchmark"


def test_api_dashboard_serves_json(tmp_path: Path) -> None:
    """App should serve JSON from /api/dashboard."""
    client = _make_app(tmp_path)
    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "experiments" in data
