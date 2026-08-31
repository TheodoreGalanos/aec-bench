# ABOUTME: Tests the CLI, TUI, and web presentations of one shared run projection.
# ABOUTME: Verifies flat status fields, explicit roots, missing-run errors, and no attachment hydration.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.execution.models import RetryPolicy
from aec_bench.execution.operational import OperationalStore
from aec_bench.execution.progress import (
    AttemptProgressCounts,
    BackendSubmissionProgressCounts,
    RunProgress,
    TrialProgressCounts,
    WorkItemProgressCounts,
)
from aec_bench.harness.run_progress import load_run_progress_surface, present_run_progress
from aec_bench.tui.progress import build_run_progress_view_model, render_run_progress
from aec_bench.web.app import create_dev_app
from aec_bench.web.dependencies import WebSettings
from aec_bench.web.routes.progress import run_progress_api
from tests.harness.test_persisted_artifact_plan import _ready_store, _spec, _task


def _progress() -> RunProgress:
    run_id = new_entity_id(EntityKind.RUN)
    plan_id = new_entity_id(EntityKind.PLAN)
    return RunProgress(
        run_id=run_id,
        plan_id=plan_id,
        status="running",
        planned=2,
        work_items=WorkItemProgressCounts(queued=1, succeeded=1),
        trials=TrialProgressCounts(queued=1, succeeded=1),
        attempts=AttemptProgressCounts(succeeded=1),
        backend_submissions=BackendSubmissionProgressCounts(completed=1),
        retries=2,
        estimated_remaining_work_count=1,
        completion_blocked_by_non_terminal=True,
        completion_blocked_by_unknown=False,
        completion_blocked=True,
    )


def test_presenter_and_tui_use_the_same_flat_counts() -> None:
    progress = _progress()
    surface = present_run_progress(progress)
    view_model = build_run_progress_view_model(progress)

    assert surface.model_dump(mode="json")["planned"] == 2
    assert surface.status == "running"
    assert surface.succeeded == progress.trials.succeeded
    assert surface.queued == progress.trials.queued
    assert surface.retries == progress.retries
    assert view_model.succeeded == surface.succeeded
    assert view_model.queued == surface.queued
    assert view_model.retries == surface.retries


def test_tui_progress_screen_renders_the_view_model_fields() -> None:
    rendered = render_run_progress(build_run_progress_view_model(_progress()))

    assert "Planned: 2" in rendered
    assert "Status: running" in rendered
    assert "Succeeded: 1" in rendered
    assert "Queued: 1" in rendered
    assert "Retries: 2" in rendered
    assert "Completion blocked: yes" in rendered


def test_cli_run_status_is_structured_and_does_not_read_attachments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    progress = _progress()
    monkeypatch.setattr("aec_bench.harness.run_progress.load_run_progress", lambda *args, **kwargs: progress)
    monkeypatch.setattr(
        "aec_bench.ledger.reader.read_trial_records",
        lambda *args, **kwargs: pytest.fail("run status must not hydrate trial attachments"),
    )

    result = CliRunner().invoke(
        app,
        [
            "--json",
            "run",
            "status",
            str(progress.run_id),
            "--operational-store",
            str(tmp_path / "operational.sqlite3"),
            "--plan-root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["status"] == "success"
    assert payload["data"]["planned"] == 2
    assert payload["data"]["status"] == "running"
    assert payload["data"]["succeeded"] == 1
    assert payload["data"]["queued"] == 1
    assert payload["data"]["retries"] == 2


def test_cli_run_status_requires_explicit_roots() -> None:
    result = CliRunner().invoke(app, ["--json", "run", "status", str(new_entity_id(EntityKind.RUN))])

    assert result.exit_code == 1
    assert "--operational-store and --plan-root" in result.stdout


def test_cli_run_status_reports_missing_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec_bench.ledger.evidence_run_store import EvidenceRunStoreIncomplete

    def fail(*args: object, **kwargs: object) -> object:
        raise EvidenceRunStoreIncomplete("no evidence run matches selector")

    monkeypatch.setattr("aec_bench.harness.run_progress.load_run_progress", fail)
    result = CliRunner().invoke(
        app,
        [
            "--json",
            "run",
            "status",
            str(new_entity_id(EntityKind.RUN)),
            "--operational-store",
            str(tmp_path / "operational.sqlite3"),
            "--plan-root",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 1
    assert "no evidence run" in result.stdout


def test_cli_run_cancel_accounts_queued_work(tmp_path: Path) -> None:
    run_id = new_entity_id(EntityKind.RUN)
    plan_id = new_entity_id(EntityKind.PLAN)
    trial_id = new_entity_id(EntityKind.TRIAL)
    now = datetime.now(UTC)
    store = OperationalStore(tmp_path / "operational.sqlite3")
    store.create_run(run_id, spec_ref="run/resolved-run-spec.json", now=now)
    store.put_plan(plan_id, run_id=run_id, plan_ref="run/run-plan.json", now=now)
    store.put_planned_trial(trial_id, plan_id=plan_id, run_id=run_id, ordinal=1, now=now)
    store.create_work_item(
        new_entity_id(EntityKind.WORK_ITEM),
        work_key="work-1",
        run_id=run_id,
        trial_id=trial_id,
        plan_id=plan_id,
        ordinal=1,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="default",
        resource_class="default",
        retry_policy=RetryPolicy(),
        available_at=now,
        now=now,
    )

    result = CliRunner().invoke(
        app,
        ["--json", "run", "cancel", str(run_id), "--operational-store", str(store.path)],
    )

    assert result.exit_code == 0, result.stdout
    assert json.loads(result.stdout)["data"]["queued_cancelled"] == 1
    assert store.list_work_items(run_id)[0].state == "cancelled"


def test_cli_run_cancel_human_output_reports_pending_states(tmp_path: Path) -> None:
    run_id = new_entity_id(EntityKind.RUN)
    store = OperationalStore(tmp_path / "operational.sqlite3")
    store.create_run(run_id, spec_ref="run/resolved-run-spec.json")

    result = CliRunner().invoke(
        app,
        ["--text", "run", "cancel", str(run_id), "--operational-store", str(store.path)],
    )

    assert result.exit_code == 0, result.stdout
    assert "queued_cancelled: 0" in result.stdout
    assert "backend_cancellation_pending: 0" in result.stdout
    assert "unknown_reconciliation: 0" in result.stdout


def test_cli_run_cancel_does_not_create_a_missing_store(tmp_path: Path) -> None:
    path = tmp_path / "missing.sqlite3"

    result = CliRunner().invoke(
        app,
        ["--json", "run", "cancel", str(new_entity_id(EntityKind.RUN)), "--operational-store", str(path)],
    )

    assert result.exit_code == 1
    assert "must already be a regular file" in result.stdout
    assert not path.exists()


def test_loader_joins_authoritative_plan_and_operational_store_without_evidence_hydration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    task = _task(tmp_path)
    evidence_store, plan = _ready_store(tmp_path, _spec(task))
    operational = OperationalStore(tmp_path / "operational.sqlite3")
    operational.create_run(plan.run_id, spec_ref="run/resolved-run-spec.json")
    operational.put_plan(plan.plan_id, run_id=plan.run_id, plan_ref="run/run-plan.json")
    trial = plan.trials[0]
    operational.put_planned_trial(
        trial.trial_id,
        plan_id=plan.plan_id,
        run_id=plan.run_id,
        ordinal=trial.ordinal,
        state="succeeded",
    )
    created_at = datetime.now(UTC)
    work = operational.create_work_item(
        new_entity_id(EntityKind.WORK_ITEM),
        work_key="work-1",
        run_id=plan.run_id,
        trial_id=trial.trial_id,
        plan_id=plan.plan_id,
        ordinal=trial.ordinal,
        execution_family="artifact",
        backend="local",
        provider_route="default",
        model_route="default",
        resource_class="default",
        retry_policy=RetryPolicy(),
        available_at=created_at,
        now=created_at,
    )
    operational.update_work_item(work.work_id, state="succeeded")
    monkeypatch.setattr(
        "aec_bench.ledger.reader.read_trial_records",
        lambda *args, **kwargs: pytest.fail("progress loader must not hydrate evidence attachments"),
    )

    surface = load_run_progress_surface(
        str(plan.run_id),
        operational_store_path=operational.path,
        plan_root=evidence_store.root,
    )

    assert surface.run_id == plan.run_id
    assert surface.status == "created"
    assert surface.planned == 1
    assert surface.succeeded == 1
    assert not surface.completion_blocked


def test_web_run_status_uses_the_same_projection_and_requires_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    progress = _progress()
    monkeypatch.setattr(
        "aec_bench.web.routes.progress.load_run_progress_surface",
        lambda *args, **kwargs: present_run_progress(progress),
    )

    def request(settings: WebSettings) -> SimpleNamespace:
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings)))

    missing_request = request(
        WebSettings(
            ledger_root=tmp_path,
            tasks_root=tmp_path,
            feedback_root=tmp_path,
            datasets_root=tmp_path,
            benchmark_templates_root=tmp_path,
        )
    )
    configured_request = request(
        WebSettings(
            ledger_root=tmp_path,
            tasks_root=tmp_path,
            feedback_root=tmp_path,
            datasets_root=tmp_path,
            benchmark_templates_root=tmp_path,
            operational_store_path=tmp_path / "operational.sqlite3",
            plan_root=tmp_path / "runs",
        )
    )

    with pytest.raises(HTTPException) as missing:
        run_progress_api(missing_request, str(progress.run_id))
    configured = run_progress_api(configured_request, str(progress.run_id))

    assert missing.value.status_code == 503
    assert configured.planned == 2
    assert configured.status == "running"
    assert configured.succeeded == 1
    assert configured.retries == 2


def test_web_run_status_reports_missing_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec_bench.ledger.evidence_run_store import EvidenceRunStoreIncomplete

    def fail(*args: object, **kwargs: object) -> object:
        raise EvidenceRunStoreIncomplete("no evidence run matches selector")

    monkeypatch.setattr("aec_bench.web.routes.progress.load_run_progress_surface", fail)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=WebSettings(
                    ledger_root=tmp_path,
                    tasks_root=tmp_path,
                    feedback_root=tmp_path,
                    datasets_root=tmp_path,
                    benchmark_templates_root=tmp_path,
                    operational_store_path=tmp_path / "operational.sqlite3",
                    plan_root=tmp_path / "runs",
                )
            )
        )
    )

    with pytest.raises(HTTPException) as response:
        run_progress_api(request, str(new_entity_id(EntityKind.RUN)))

    assert response.value.status_code == 404
    assert "no evidence run" in response.value.detail


def test_web_run_status_reports_store_configuration_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from aec_bench.execution.operational import OperationalStoreError

    def fail(*args: object, **kwargs: object) -> object:
        raise OperationalStoreError("operational database does not contain the current schema")

    monkeypatch.setattr("aec_bench.web.routes.progress.load_run_progress_surface", fail)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                settings=WebSettings(
                    ledger_root=tmp_path,
                    tasks_root=tmp_path,
                    feedback_root=tmp_path,
                    datasets_root=tmp_path,
                    benchmark_templates_root=tmp_path,
                    operational_store_path=tmp_path / "operational.sqlite3",
                    plan_root=tmp_path / "runs",
                )
            )
        )
    )

    with pytest.raises(HTTPException) as response:
        run_progress_api(request, str(new_entity_id(EntityKind.RUN)))

    assert response.value.status_code == 503


def test_development_web_factory_receives_explicit_progress_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "AEC_BENCH_WEB_LEDGER_ROOT",
        "AEC_BENCH_WEB_TASKS_ROOT",
        "AEC_BENCH_WEB_FEEDBACK_ROOT",
        "AEC_BENCH_WEB_DATASETS_ROOT",
    ):
        monkeypatch.setenv(name, str(tmp_path / name.lower()))
    operational_path = tmp_path / "operational.sqlite3"
    plan_root = tmp_path / "runs"
    monkeypatch.setenv("AEC_BENCH_OPERATIONAL_STORE", str(operational_path))
    monkeypatch.setenv("AEC_BENCH_PLAN_ROOT", str(plan_root))

    configured = create_dev_app().state.settings

    assert configured.operational_store_path == operational_path
    assert configured.plan_root == plan_root
