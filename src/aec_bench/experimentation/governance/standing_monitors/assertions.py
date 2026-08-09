# ABOUTME: Enforces current-cycle monitor bindings at governance consumption boundaries.
# ABOUTME: Fails closed on incidents, stale cycles, mismatched assurance, or incomplete coverage.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.experimentation.governance.standing_monitors.models import (
    CycleMonitorReport,
    CycleMonitorReportStatus,
    ProductionCycleMonitorEnvelope,
    StandingMonitorPlan,
    StandingMonitorPolicy,
    monitor_coverage_errors,
)


def assert_current_cycle_monitor_report(
    report: CycleMonitorReport,
    *,
    plan: StandingMonitorPlan,
    cycle_id: str,
    cycle_index: int,
    assurance_snapshot_sha256: str,
) -> None:
    """Fail closed unless a passing report binds the exact current plan, cycle, and assurance."""
    selected = CycleMonitorReport.model_validate(report.model_dump(mode="python"))
    selected_plan = StandingMonitorPlan.model_validate(plan.model_dump(mode="python"))
    if selected.status is not CycleMonitorReportStatus.PASSED:
        raise ValueError("cycle monitor report is not passing")
    if (
        selected.monitor_plan_sha256 != selected_plan.content_sha256
        or selected.cycle_id != cycle_id
        or selected.cycle_index != cycle_index
        or selected.valid_through_cycle_index < cycle_index
        or selected.assurance_snapshot_sha256 != assurance_snapshot_sha256
    ):
        raise ValueError("cycle monitor report does not cover the current governed cycle")


def assert_current_production_cycle_monitor_envelope(
    envelope: ProductionCycleMonitorEnvelope,
    *,
    policy: StandingMonitorPolicy,
    evaluation_plan_sha256: str,
    cycle_id: str,
    cycle_index: int,
    assurance_snapshot_sha256: str,
) -> None:
    """Fail closed unless a complete production envelope covers the current cycle."""
    selected = ProductionCycleMonitorEnvelope.model_validate(envelope.model_dump(mode="python"))
    selected_policy = StandingMonitorPolicy.model_validate(policy.model_dump(mode="python"))
    validate_sha256(evaluation_plan_sha256)
    validate_sha256(assurance_snapshot_sha256)
    if selected.report.status is not CycleMonitorReportStatus.PASSED:
        raise ValueError("production cycle monitor report is not passing")
    if (
        selected.policy.content_sha256 != selected_policy.content_sha256
        or selected.cycle_plan.evaluation_plan_sha256 != evaluation_plan_sha256
        or selected.cycle_plan.cycle_id != cycle_id
        or selected.cycle_plan.cycle_index != cycle_index
        or selected.cycle_plan.assurance_snapshot_sha256 != assurance_snapshot_sha256
        or selected.report.valid_through_cycle_index < cycle_index
    ):
        raise ValueError("production monitor envelope does not cover the current governed cycle")
    if monitor_coverage_errors(
        policy=selected_policy,
        cycle_plan=selected.cycle_plan,
        coverage_attestation=selected.coverage_attestation,
    ):
        raise ValueError("production monitor collection coverage is incomplete")
