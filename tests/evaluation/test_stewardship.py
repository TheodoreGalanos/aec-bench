# ABOUTME: Tests evaluation-owned pump-station metrics over reloaded durable evidence.
# ABOUTME: Proves terminal liabilities remain visible without changing verifier reward.

from __future__ import annotations

from pathlib import Path

from aec_bench.evaluation.stewardship import (
    evaluate_pump_station_stewardship_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_session import (
    run_pump_station_reference_session,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_evaluator_reloads_complete_run_and_reports_terminal_liabilities(
    tmp_path: Path,
) -> None:
    exported = export_pump_station_harbor_task(
        tmp_path / "tasks" / "stewardship" / "wastewater-pump-station",
        project_root=PROJECT_ROOT,
    )
    bridge = load_pump_station_harbor_bridge(exported.task_dir / "environment")
    completed = run_pump_station_reference_session(
        bridge=bridge,
        output_dir=tmp_path / "world-session",
        session_identity="evaluation-direct",
    )

    first = evaluate_pump_station_stewardship_run(
        run_dir=completed.output_dir / "world-run",
        package_root=bridge.package_root,
        imported_artifact_sha256=("d" * 64,),
    )
    reloaded = evaluate_pump_station_stewardship_run(
        run_dir=completed.output_dir / "world-run",
        package_root=bridge.package_root,
        imported_artifact_sha256=("d" * 64,),
    )

    assert reloaded == first
    assert first.valid is True
    assert first.gates.passed is True
    assert first.metrics.decision_time_invalid_count == 0
    assert first.metrics.physical_service_review_required is False
    assert first.metrics.maintenance_intervention_count == 1
    assert first.metrics.obligation_breach_count == 0
    assert first.metrics.restriction_breach_count == 0
    assert first.metrics.evidence_integrity_gap_count == 0
    assert first.metrics.handover_count == 0
    assert first.metrics.handover_omission_count == 0
    assert first.metrics.terminal_liability.model_dump(mode="json") == {
        "review_required_physical_state": False,
        "active_restriction_count": 1,
        "overdue_calendar_seconds": 0,
        "overdue_affected_pump_runtime_seconds": 0,
        "breached_obligation_count": 0,
        "unresolved_verification_count": 0,
        "deferred_work_count": 0,
        "unavailable_pump_count": 1,
        "consumed_maintenance_resource_count": 1,
        "unresolved_evidence": False,
    }
    assert first.evidence.imported_artifact_sha256 == ("d" * 64,)
