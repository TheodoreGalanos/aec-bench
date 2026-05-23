# ABOUTME: Tests for the /api/library, /api/search, and /api/review JSON endpoints.
# ABOUTME: Verifies JSON structure, filtering, and empty/error states.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.web.app import create_app


def _make_client(tmp_path: Path) -> TestClient:
    """Create a test client with empty ledger and tasks directories."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    return TestClient(create_app(ledger_root=ledger, tasks_root=tasks))


# ---------------------------------------------------------------------------
# Library API
# ---------------------------------------------------------------------------


def test_library_api_list(tmp_path: Path) -> None:
    """GET /api/library should return JSON with expected keys."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library")
    assert resp.status_code == 200
    data = resp.json()
    assert "templates" in data
    assert "disciplines" in data
    assert "selected_discipline" in data


def test_library_api_list_has_templates(tmp_path: Path) -> None:
    """Library API should include builtin templates."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["templates"]) > 0
    # Should include at least one electrical template
    names = [t["task_id"] for t in data["templates"]]
    assert any("voltage-drop" in n for n in names)


def test_library_api_filter_by_discipline(tmp_path: Path) -> None:
    """Library API should filter templates by discipline."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=electrical")
    assert resp.status_code == 200
    data = resp.json()
    for template in data["templates"]:
        assert template["discipline"] == "electrical"


def test_library_api_template_has_required_fields(tmp_path: Path) -> None:
    """Each template in the list should have all required schema fields."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=electrical")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["templates"]) > 0
    t = data["templates"][0]
    assert "task_id" in t
    assert "discipline" in t
    assert "description" in t
    assert "inputs" in t
    assert "outputs" in t
    assert "param_count" in t


def test_library_api_detail(tmp_path: Path) -> None:
    """GET /api/library/{discipline}/{template_id} should return a single template."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library?discipline=electrical")
    data = resp.json()
    first = data["templates"][0]
    discipline = first["discipline"]
    template_id = first["task_id"]

    detail_resp = client.get(f"/api/library/{discipline}/{template_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert "template" in detail
    assert detail["template"]["task_id"] == template_id


def test_library_api_detail_not_found(tmp_path: Path) -> None:
    """Detail endpoint should return 404 for an unknown template."""
    client = _make_client(tmp_path)
    resp = client.get("/api/library/electrical/no-such-template")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Search API
# ---------------------------------------------------------------------------


def test_search_api(tmp_path: Path) -> None:
    """GET /api/search should return JSON with expected keys."""
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=voltage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "voltage"
    assert "total_results" in data
    assert "template_results" in data
    assert "dataset_results" in data


def test_search_api_empty_query(tmp_path: Path) -> None:
    """Empty query should return empty results with zero total."""
    client = _make_client(tmp_path)
    resp = client.get("/api/search")
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == ""
    assert data["total_results"] == 0


def test_search_api_finds_templates(tmp_path: Path) -> None:
    """Search for 'voltage' should find voltage-drop templates."""
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=voltage")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] > 0
    names = [t["name"] for t in data["template_results"]]
    assert any("voltage" in n for n in names)


def test_search_api_no_results(tmp_path: Path) -> None:
    """Query matching nothing should return zero results."""
    client = _make_client(tmp_path)
    resp = client.get("/api/search?q=xyznonexistent999")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_results"] == 0
