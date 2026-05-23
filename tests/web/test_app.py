# ABOUTME: Tests the FastAPI communication web layer for public and internal routes.
# ABOUTME: Verifies visibility filtering, template rendering, and explicit internal gating.

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    Completeness,
    DerivationStepRecord,
)
from aec_bench.feedback.models import CalibrationStatus, ReviewerProfile, ReviewerWeighting
from aec_bench.ledger.writer import write_trial_record
from aec_bench.web.app import create_app
from tests.support.trial_record_factories import make_trial_record


def test_public_routes_render_and_exclude_holdout_records(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"}),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-002",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
        )
    )

    dashboard = client.get("/api/dashboard")
    leaderboard = client.get("/api/public/leaderboard")
    experiment = client.get("/api/public/experiments/experiment-001")

    assert dashboard.status_code == 200
    assert "experiments" in dashboard.json()
    assert leaderboard.status_code == 200
    assert leaderboard.json()["visibility_scope"] == "public"
    assert leaderboard.json()["leaderboard"]["entries"][0]["n_trials"] == 1
    assert experiment.status_code == 200
    assert len(experiment.json()["report"]["trials"]) == 1


def test_internal_routes_are_explicitly_gated(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"}),
    )

    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
            internal_token="secret-token",
        )
    )

    response = client.get("/api/internal/leaderboard")

    assert response.status_code == 403
    assert response.json()["detail"] == "internal access required"


def test_internal_routes_allow_authorized_requests_and_include_holdout(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-alpha",
            experiment_id="experiment-001",
            task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
            adaptation=_adaptation("heat-load-family", "jurisdiction=us"),
            evaluation=EvaluationResult(
                reward=0.98,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
            completeness=Completeness.COMPLETE,
        ),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-beta",
            experiment_id="experiment-001",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
            internal_token="secret-token",
        )
    )
    headers = {"X-AEC-BENCH-Internal-Token": "secret-token"}

    leaderboard = client.get("/api/internal/leaderboard", headers=headers)
    experiment = client.get("/api/internal/experiments/experiment-001", headers=headers)
    adaptation = client.get(
        "/api/internal/adaptation/heat-load-family?experiment_id=experiment-001",
        headers=headers,
    )

    assert leaderboard.status_code == 200
    assert leaderboard.json()["visibility_scope"] == "internal"
    assert leaderboard.json()["leaderboard"]["entries"][0]["n_trials"] == 2
    assert experiment.status_code == 200
    assert len(experiment.json()["report"]["trials"]) == 2
    assert adaptation.status_code == 200
    assert adaptation.json()["artifact_type"] == "adaptation_family"
    assert adaptation.json()["bundle"]["preserved_trial_count"] == 1


def test_review_routes_enforce_reviewer_holdout_access_and_persist_annotations(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-public",
            task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
        ),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-holdout",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
            feedback_root=tmp_path / "feedback",
            internal_token="secret-token",
        )
    )
    headers = {"X-AEC-BENCH-Internal-Token": "secret-token"}
    reviewer = ReviewerProfile(
        reviewer_id="reviewer-public",
        discipline="mechanical",
        calibration_status=CalibrationStatus.UNCALIBRATED,
        calibration_version=None,
        can_review_holdout=False,
        weighting=ReviewerWeighting(
            calibration_score=0.5,
            discipline_score=1.0,
            experience_score=0.4,
        ),
        created_at=datetime(2026, 3, 16, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 16, 12, 0, tzinfo=UTC),
    )

    reviewer_response = client.post(
        "/api/internal/review/reviewers",
        headers=headers,
        json=reviewer.model_dump(mode="json"),
    )
    assignments = client.get(
        "/api/internal/review/assignments?reviewer_id=reviewer-public",
        headers=headers,
    )
    forbidden_trial = client.get(
        "/api/internal/review/trials/trial-holdout?reviewer_id=reviewer-public",
        headers=headers,
    )
    annotation_response = client.post(
        "/api/internal/review/annotations",
        headers=headers,
        json={
            "annotation_id": "annotation-public",
            "trial_id": "trial-public",
            "experiment_id": "experiment-001",
            "task_id": "mechanical/heat-load/public-task",
            "task_visibility": "public",
            "reviewer_id": "reviewer-public",
            "reviewer_discipline": "mechanical",
            "judgment": "pass",
            "categories": ["verifier.output"],
            "notes": "Looks correct.",
            "created_at": "2026-03-16T12:05:00Z",
            "is_calibration": False,
            "calibration_version": None,
        },
    )
    review_bundle = client.get(
        "/api/internal/review/trials/trial-public?reviewer_id=reviewer-public",
        headers=headers,
    )

    assert reviewer_response.status_code == 201
    assert assignments.status_code == 200
    assert [assignment["trial_id"] for assignment in assignments.json()["assignments"]] == ["trial-public"]
    assert forbidden_trial.status_code == 403
    assert annotation_response.status_code == 201
    assert review_bundle.status_code == 200
    assert len(review_bundle.json()["annotations"]) == 1
    assert review_bundle.json()["handoff"]["confidence"]["annotator_count"] == 1


def test_review_routes_support_holdout_reviewer_adjudication_and_internal_pages(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-holdout",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
            feedback_root=tmp_path / "feedback",
            internal_token="secret-token",
        )
    )
    headers = {"X-AEC-BENCH-Internal-Token": "secret-token"}
    for reviewer_id in ["reviewer-holdout", "reviewer-second"]:
        reviewer = ReviewerProfile(
            reviewer_id=reviewer_id,
            discipline="mechanical",
            calibration_status=CalibrationStatus.CALIBRATED,
            calibration_version="v1",
            can_review_holdout=True,
            weighting=ReviewerWeighting(
                calibration_score=0.9,
                discipline_score=1.0,
                experience_score=0.8,
            ),
            created_at=datetime(2026, 3, 16, 13, 0, tzinfo=UTC),
            updated_at=datetime(2026, 3, 16, 13, 0, tzinfo=UTC),
        )
        response = client.post(
            "/api/internal/review/reviewers",
            headers=headers,
            json=reviewer.model_dump(mode="json"),
        )
        assert response.status_code == 201

    first_annotation = client.post(
        "/api/internal/review/annotations",
        headers=headers,
        json={
            "annotation_id": "annotation-1",
            "trial_id": "trial-holdout",
            "experiment_id": "experiment-001",
            "task_id": "mechanical/heat-load/holdout-task",
            "task_visibility": "holdout",
            "reviewer_id": "reviewer-holdout",
            "reviewer_discipline": "mechanical",
            "judgment": "pass",
            "categories": ["instruction.clarity"],
            "notes": "Looks acceptable.",
            "created_at": "2026-03-16T13:05:00Z",
            "is_calibration": False,
            "calibration_version": None,
        },
    )
    second_annotation = client.post(
        "/api/internal/review/annotations",
        headers=headers,
        json={
            "annotation_id": "annotation-2",
            "trial_id": "trial-holdout",
            "experiment_id": "experiment-001",
            "task_id": "mechanical/heat-load/holdout-task",
            "task_visibility": "holdout",
            "reviewer_id": "reviewer-second",
            "reviewer_discipline": "mechanical",
            "judgment": "fail",
            "categories": ["verifier.output"],
            "notes": "Verifier evidence disagrees.",
            "created_at": "2026-03-16T13:06:00Z",
            "is_calibration": False,
            "calibration_version": None,
        },
    )
    adjudication = client.post(
        "/api/internal/review/adjudications",
        headers=headers,
        json={
            "decision_id": "decision-1",
            "trial_id": "trial-holdout",
            "final_judgment": "fail",
            "decided_by": "reviewer-holdout",
            "rationale": "Failure is better supported by the transcript.",
        },
    )
    queue_api = client.get(
        "/api/review/queue?reviewer_id=reviewer-holdout",
        headers=headers,
    )
    review_bundle = client.get(
        "/api/internal/review/trials/trial-holdout?reviewer_id=reviewer-holdout",
        headers=headers,
    )

    assert first_annotation.status_code == 201
    assert second_annotation.status_code == 201
    assert adjudication.status_code == 201
    assert queue_api.status_code == 200
    # Queue should have no remaining assignments (trial is fully adjudicated)
    assert isinstance(queue_api.json()["assignments"]["assignments"], list)
    assert review_bundle.status_code == 200
    assert review_bundle.json()["adjudication"]["status"] == "adjudicated"
    assert review_bundle.json()["handoff"]["confidence"]["confidence_method"] == "adjudicated_human_review"
    # Verify annotation content is accessible via API
    assert any(a["notes"] == "Verifier evidence disagrees." for a in review_bundle.json()["annotations"])
    assert any("instruction.clarity" in a["categories"] for a in review_bundle.json()["annotations"])


def test_internal_review_api_queue_and_trial_bundle_accessible(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-public",
            task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
        ),
    )

    client = TestClient(
        create_app(
            ledger_root=tmp_path / "ledger",
            tasks_root=tasks_root,
            feedback_root=tmp_path / "feedback",
            internal_token="secret-token",
        )
    )
    headers = {"X-AEC-BENCH-Internal-Token": "secret-token"}
    reviewer = ReviewerProfile(
        reviewer_id="reviewer-public",
        discipline="mechanical",
        calibration_status=CalibrationStatus.UNCALIBRATED,
        calibration_version=None,
        can_review_holdout=False,
        weighting=ReviewerWeighting(
            calibration_score=0.5,
            discipline_score=1.0,
            experience_score=0.4,
        ),
        created_at=datetime(2026, 3, 16, 14, 0, tzinfo=UTC),
        updated_at=datetime(2026, 3, 16, 14, 0, tzinfo=UTC),
    )
    reviewer_response = client.post(
        "/api/internal/review/reviewers",
        headers=headers,
        json=reviewer.model_dump(mode="json"),
    )
    assert reviewer_response.status_code == 201

    queue_api = client.get(
        "/api/review/queue?reviewer_id=reviewer-public",
        headers=headers,
    )
    trial_bundle = client.get(
        "/api/review/trial/trial-public?reviewer_id=reviewer-public",
        headers=headers,
    )
    annotation_response = client.post(
        "/api/internal/review/annotations",
        headers=headers,
        json={
            "annotation_id": "annotation-browser",
            "trial_id": "trial-public",
            "experiment_id": "experiment-001",
            "task_id": "mechanical/heat-load/public-task",
            "task_visibility": "public",
            "reviewer_id": "reviewer-public",
            "reviewer_discipline": "mechanical",
            "judgment": "pass",
            "categories": ["verifier.output"],
            "notes": "Browser session reuse works.",
            "created_at": "2026-03-16T14:05:00Z",
            "is_calibration": False,
            "calibration_version": None,
        },
    )
    assignments = client.get(
        "/api/internal/review/assignments?reviewer_id=reviewer-public",
        headers=headers,
    )

    assert queue_api.status_code == 200
    assert isinstance(queue_api.json()["assignments"]["assignments"], list)
    assert trial_bundle.status_code == 200
    assert trial_bundle.json()["bundle"]["trial"]["trial_id"] == "trial-public"
    assert annotation_response.status_code == 201
    assert assignments.status_code == 200
    assert assignments.json()["assignments"] == []


def test_spa_fallback_serves_index_html(tmp_path: Path) -> None:
    """When frontend dist exists, non-API paths serve index.html."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")

    app = create_app(ledger_root=ledger, tasks_root=tasks, frontend_dist=dist_dir)
    client = TestClient(app)

    resp = client.get("/some-unknown-path")
    assert resp.status_code == 200
    assert "SPA" in resp.text


def test_spa_fallback_sets_internal_access_cookie_when_token_configured(tmp_path: Path) -> None:
    """SPA loads should seed the internal review cookie for browser API calls."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")

    app = create_app(
        ledger_root=ledger,
        tasks_root=tasks,
        frontend_dist=dist_dir,
        internal_token="secret-token",
    )
    client = TestClient(app)

    resp = client.get("/review/queue")

    assert resp.status_code == 200
    assert resp.cookies["aec_bench_internal_token"] == "secret-token"


def test_api_routes_not_caught_by_spa_fallback(tmp_path: Path) -> None:
    """API routes should return JSON, not the SPA."""
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    (dist_dir / "index.html").write_text("<html><body>SPA</body></html>", encoding="utf-8")

    app = create_app(ledger_root=ledger, tasks_root=tasks, frontend_dist=dist_dir)
    client = TestClient(app)

    resp = client.get("/api/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "experiments" in data


def _write_task_instance(*, tasks_root: Path, relative_path: str, visibility: Visibility) -> None:
    instance_dir = tasks_root / relative_path
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )


def _adaptation(family_id: str, variation_key: str) -> AdaptationProvenance:
    variation_value = variation_key.split("=", maxsplit=1)[1]
    return AdaptationProvenance(
        family_id=family_id,
        seed_task_id="mechanical/heat-load/au-office",
        variation_key=variation_key,
        variation={"jurisdiction": variation_value},
        derivation_lineage=[
            DerivationStepRecord(
                axis="jurisdiction",
                parent_value="au",
                value=variation_value,
            )
        ],
    )
