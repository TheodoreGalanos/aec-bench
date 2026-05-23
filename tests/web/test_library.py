# ABOUTME: Tests for the library API endpoints showing benchmark templates by discipline.
# ABOUTME: Verifies list view, discipline filter, detail view, and 404 handling via JSON API.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


def test_library_api_returns_json(tmp_path: Path) -> None:
    """Library API should return JSON with expected keys."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert "disciplines" in data


def test_library_shows_templates(tmp_path: Path) -> None:
    """Library API should include templates from the builtin templates."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library")
    assert resp.status_code == 200
    data = resp.json()
    # At least one builtin template should appear (e.g., voltage-drop)
    template_ids = [t["task_id"] for t in data["templates"]]
    assert any("voltage-drop" in tid for tid in template_ids)


def test_library_filter_by_discipline(tmp_path: Path) -> None:
    """Library API should filter templates by discipline."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=electrical")
    assert resp.status_code == 200
    data = resp.json()
    template_ids = [t["task_id"] for t in data["templates"]]
    assert any("voltage-drop" in tid for tid in template_ids)


def test_library_filter_excludes_other_disciplines(tmp_path: Path) -> None:
    """Filtering by electrical should only return electrical templates."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=electrical")
    assert resp.status_code == 200
    data = resp.json()
    for template in data["templates"]:
        assert template["discipline"] == "electrical"


def test_library_shows_discipline_list(tmp_path: Path) -> None:
    """Library API should return available disciplines."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library")
    assert resp.status_code == 200
    data = resp.json()
    assert "electrical" in data["disciplines"]


def test_library_shows_template_count(tmp_path: Path) -> None:
    """Library API should return a non-empty list of templates."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["templates"]) > 0


def test_library_detail_returns_json(tmp_path: Path) -> None:
    """Library detail API should return JSON with template metadata."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library/electrical/voltage-drop")
    assert resp.status_code == 200
    data = resp.json()
    assert "template" in data
    assert data["template"]["task_id"] == "voltage-drop"
    assert data["template"]["discipline"] == "electrical"


def test_library_detail_shows_description(tmp_path: Path) -> None:
    """Library detail should include the template description."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library/electrical/voltage-drop")
    assert resp.status_code == 200
    data = resp.json()
    assert "description" in data["template"]


def test_library_detail_shows_discipline(tmp_path: Path) -> None:
    """Library detail should include the discipline."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library/electrical/voltage-drop")
    assert resp.status_code == 200
    data = resp.json()
    assert data["template"]["discipline"] == "electrical"


def test_library_detail_unknown_returns_404(tmp_path: Path) -> None:
    """Library detail for non-existent template should return 404."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library/electrical/does-not-exist")
    assert resp.status_code == 404


def test_library_api_selected_discipline(tmp_path: Path) -> None:
    """API should echo back the selected discipline filter."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=electrical")
    assert resp.status_code == 200
    data = resp.json()
    assert data["selected_discipline"] == "electrical"


def test_library_empty_state_no_match(tmp_path: Path) -> None:
    """Filtering by a non-existent discipline returns empty templates list."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=nonexistent-discipline")
    assert resp.status_code == 200
    data = resp.json()
    assert data["templates"] == []
