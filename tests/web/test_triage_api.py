# ABOUTME: Tests for the lightweight triage annotation API endpoints.
# ABOUTME: Covers POST annotate, GET annotations, and error cases.

from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def _make_client(tmp_path: Path) -> tuple[TestClient, Path]:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    app = create_app(ledger_root=ledger, tasks_root=tasks)
    return TestClient(app), ledger


def _seed_trial(ledger: Path, experiment_id: str = "exp-01", trial_id: str = "trial-01") -> None:
    record = make_trial_record(experiment_id=experiment_id, trial_id=trial_id)
    write_trial_record(ledger_root=ledger, record=record)


def test_post_annotation(tmp_path: Path) -> None:
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger)
    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "pass",
            "notes": "looks good",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["verdict"] == "pass"
    assert body["notes"] == "looks good"
    assert "timestamp" in body


def test_post_annotation_replaces_existing(tmp_path: Path) -> None:
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger)
    client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "pass",
        },
    )
    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "fail",
            "notes": "wrong",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "fail"


def test_get_annotations(tmp_path: Path) -> None:
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger, trial_id="t1")
    _seed_trial(ledger, trial_id="t2")
    client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "t1",
            "experiment_id": "exp-01",
            "verdict": "pass",
        },
    )
    client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "t2",
            "experiment_id": "exp-01",
            "verdict": "fail",
        },
    )
    resp = client.get("/api/triage/annotations?experiment=exp-01")
    assert resp.status_code == 200
    annotations = resp.json()
    assert len(annotations) == 2
    assert annotations["t1"]["verdict"] == "pass"
    assert annotations["t2"]["verdict"] == "fail"


def test_post_annotation_invalid_verdict(tmp_path: Path) -> None:
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger)
    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "banana",
        },
    )
    assert resp.status_code == 422


def test_get_annotations_empty_experiment(tmp_path: Path) -> None:
    client, _ledger = _make_client(tmp_path)
    resp = client.get("/api/triage/annotations?experiment=nonexistent")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_note_preserves_existing_verdict(tmp_path: Path) -> None:
    """Adding a note should keep the existing pass/fail/defer verdict."""
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger)
    client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "fail",
        },
    )
    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "note",
            "notes": "used wrong formula",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "fail"
    assert resp.json()["notes"] == "used wrong formula"


def test_verdict_preserves_existing_notes(tmp_path: Path) -> None:
    """Changing verdict should keep existing notes."""
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger)
    client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "fail",
            "notes": "wrong calculation",
        },
    )
    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "pass",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "pass"
    assert resp.json()["notes"] == "wrong calculation"


def test_verdict_with_new_notes_replaces_notes(tmp_path: Path) -> None:
    """Providing notes alongside a verdict replaces existing notes."""
    client, ledger = _make_client(tmp_path)
    _seed_trial(ledger)
    client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "fail",
            "notes": "old note",
        },
    )
    resp = client.post(
        "/api/triage/annotate",
        json={
            "trial_id": "trial-01",
            "experiment_id": "exp-01",
            "verdict": "pass",
            "notes": "actually correct",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["verdict"] == "pass"
    assert resp.json()["notes"] == "actually correct"
