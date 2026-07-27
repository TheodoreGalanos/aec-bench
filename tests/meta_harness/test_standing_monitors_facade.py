# ABOUTME: Characterizes the stable standing-monitor facade and its canonical package modules.
# ABOUTME: Guards exact public object identity under facade-first and canonical-first imports.

from __future__ import annotations

import importlib
import subprocess
import sys


def test_standing_monitor_facade_preserves_public_object_identity() -> None:
    facade = importlib.import_module("aec_bench.meta_harness.monitors")
    canonical = importlib.import_module("aec_bench.meta_harness.standing_monitors")
    models = importlib.import_module("aec_bench.meta_harness.standing_monitors.models")
    evaluation = importlib.import_module("aec_bench.meta_harness.standing_monitors.evaluation")
    replay = importlib.import_module("aec_bench.meta_harness.standing_monitors.replay")
    assertions = importlib.import_module("aec_bench.meta_harness.standing_monitors.assertions")

    expected = {
        "CanaryKind": models.CanaryKind,
        "FlowSurface": models.FlowSurface,
        "FlowAction": models.FlowAction,
        "MonitorFindingCode": models.MonitorFindingCode,
        "CycleMonitorReportStatus": models.CycleMonitorReportStatus,
        "CanaryCommitment": models.CanaryCommitment,
        "CanaryObservation": models.CanaryObservation,
        "CanaryResult": models.CanaryResult,
        "ForbiddenFlowRule": models.ForbiddenFlowRule,
        "RuntimeFlowObservation": models.RuntimeFlowObservation,
        "BasisReplayRequirement": models.BasisReplayRequirement,
        "BasisReplayObservation": models.BasisReplayObservation,
        "StandingMonitorPlan": models.StandingMonitorPlan,
        "StandingMonitorPolicy": models.StandingMonitorPolicy,
        "CycleMonitorPlan": models.CycleMonitorPlan,
        "MonitorCoverageAttestation": models.MonitorCoverageAttestation,
        "MonitorFinding": models.MonitorFinding,
        "CycleMonitorReport": models.CycleMonitorReport,
        "ProductionCycleMonitorEnvelope": models.ProductionCycleMonitorEnvelope,
        "default_forbidden_flow_rules": models.default_forbidden_flow_rules,
        "run_production_cycle_monitors": evaluation.run_production_cycle_monitors,
        "run_standing_monitors": evaluation.run_standing_monitors,
        "schedule_basis_replay": replay.schedule_basis_replay,
        "replay_scheduled_basis": replay.replay_scheduled_basis,
        "assert_current_cycle_monitor_report": assertions.assert_current_cycle_monitor_report,
        "assert_current_production_cycle_monitor_envelope": (
            assertions.assert_current_production_cycle_monitor_envelope
        ),
    }
    for name, implementation in expected.items():
        assert getattr(facade, name) is implementation
        assert getattr(canonical, name) is implementation


def test_standing_monitor_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.meta_harness.monitors as facade
import aec_bench.meta_harness.standing_monitors as canonical
assert facade.StandingMonitorPolicy is canonical.StandingMonitorPolicy
assert facade.run_production_cycle_monitors is canonical.run_production_cycle_monitors
assert facade.schedule_basis_replay is canonical.schedule_basis_replay
assert (
    facade.assert_current_production_cycle_monitor_envelope
    is canonical.assert_current_production_cycle_monitor_envelope
)
""",
        """
import aec_bench.meta_harness.standing_monitors as canonical
import aec_bench.meta_harness.monitors as facade
assert facade.StandingMonitorPolicy is canonical.StandingMonitorPolicy
assert facade.run_production_cycle_monitors is canonical.run_production_cycle_monitors
assert facade.schedule_basis_replay is canonical.schedule_basis_replay
assert (
    facade.assert_current_production_cycle_monitor_envelope
    is canonical.assert_current_production_cycle_monitor_envelope
)
""",
    )

    for program in programs:
        subprocess.run([sys.executable, "-c", program], check=True)
