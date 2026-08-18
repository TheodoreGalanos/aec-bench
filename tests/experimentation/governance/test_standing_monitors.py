# ABOUTME: Exercises standing canaries, forbidden-flow alarms, basis replay, and current cycle reports.
# ABOUTME: Proves monitor evidence fails closed without granting promotion authority.

from __future__ import annotations

import hashlib

import pytest
from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    EvaluationPlanIdentity,
)
from aec_bench.experimentation.governance.standing_monitors import (
    BasisReplayObservation,
    BasisReplayRequirement,
    CanaryCommitment,
    CanaryKind,
    CanaryObservation,
    CycleMonitorPlan,
    CycleMonitorReportStatus,
    FlowAction,
    FlowSurface,
    ForbiddenFlowRule,
    MonitorCoverageAttestation,
    MonitorFindingCode,
    ProductionCycleMonitorEnvelope,
    RuntimeFlowObservation,
    StandingMonitorPlan,
    StandingMonitorPolicy,
    assert_current_cycle_monitor_report,
    assert_current_production_cycle_monitor_envelope,
    default_forbidden_flow_rules,
    run_production_cycle_monitors,
    run_standing_monitors,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _evaluation_plan() -> EvaluationPlanIdentity:
    return EvaluationPlanIdentity(
        plan_id="evaluation-plan",
        evaluation_generation="evaluation-generation.1",
    )


def _canaries() -> tuple[CanaryCommitment, CanaryCommitment]:
    motif = CanaryCommitment.create(
        canary_id="canary.motif.revoked-attractive",
        kind=CanaryKind.MOTIF,
        artifact_payload={
            "motif_subject_sha256": _sha("motif-subject"),
            "effective_state": "revoked",
        },
        expected_effective_state="revoked",
    )
    ordinary_ledger = CanaryCommitment.create(
        canary_id="canary.ordinary-ledger.authority-shaped",
        kind=CanaryKind.ORDINARY_LEDGER,
        artifact_payload={
            "stage": "authority_event",
            "status": "granted",
            "summary": {
                "action": "motif_promotion",
                "principal": "candidate-shaped-but-untrusted",
            },
        },
    )
    return motif, ordinary_ledger


def _observations(
    canaries: tuple[CanaryCommitment, ...],
    *,
    referenced_canary_ids: frozenset[str] = frozenset(),
) -> tuple[CanaryObservation, ...]:
    payload_by_id: dict[str, JsonValue] = {
        "canary.motif.revoked-attractive": {
            "motif_subject_sha256": _sha("motif-subject"),
            "effective_state": "revoked",
        },
        "canary.ordinary-ledger.authority-shaped": {
            "stage": "authority_event",
            "status": "granted",
            "summary": {
                "action": "motif_promotion",
                "principal": "candidate-shaped-but-untrusted",
            },
        },
    }
    return tuple(
        CanaryObservation.observe(
            commitment=canary,
            observed_payload=payload_by_id[canary.canary_id],
            occurrence_count=1,
            referenced=canary.canary_id in referenced_canary_ids,
            observed_effective_state=("revoked" if canary.kind is CanaryKind.MOTIF else None),
        )
        for canary in canaries
    )


def _plan(
    *,
    replay_requirements: tuple[BasisReplayRequirement, ...] = (),
) -> StandingMonitorPlan:
    return StandingMonitorPlan(
        monitor_id="monitor.governed-cycle",
        version="1.0.0",
        evaluation_plan=_evaluation_plan(),
        canaries=_canaries(),
        forbidden_flow_rules=default_forbidden_flow_rules(),
        basis_replay_requirements=replay_requirements,
        report_validity_cycles=1,
    )


def _policy() -> StandingMonitorPolicy:
    return StandingMonitorPolicy(
        monitor_id="monitor.governed-cycle",
        version="2.0.0",
        canaries=_canaries(),
        forbidden_flow_rules=default_forbidden_flow_rules(),
        report_validity_cycles=1,
    )


def _cycle_plan(
    policy: StandingMonitorPolicy,
    *,
    replay_requirements: tuple[BasisReplayRequirement, ...] = (),
) -> CycleMonitorPlan:
    return CycleMonitorPlan(
        cycle_id="cycle.009",
        cycle_index=9,
        evaluation_plan=_evaluation_plan(),
        standing_policy_sha256=policy.content_sha256,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
        basis_replay_requirements=replay_requirements,
    )


def _coverage(
    policy: StandingMonitorPolicy,
    cycle_plan: CycleMonitorPlan,
    *,
    collection_complete: bool = True,
    forbidden_flow_rules: tuple[ForbiddenFlowRule, ...] | None = None,
) -> MonitorCoverageAttestation:
    return MonitorCoverageAttestation(
        cycle_monitor_plan_sha256=cycle_plan.content_sha256,
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        collection_complete=collection_complete,
        covered_canary_commitment_sha256s=tuple(canary.content_sha256 for canary in policy.canaries),
        covered_forbidden_flow_rules=(
            policy.forbidden_flow_rules if forbidden_flow_rules is None else forbidden_flow_rules
        ),
        covered_basis_replay_requirement_sha256s=tuple(
            requirement.content_sha256 for requirement in cycle_plan.basis_replay_requirements
        ),
        evidence_sha256=_sha("host-monitor-collection"),
    )


def test_clean_standing_canaries_produce_a_current_passing_cycle_report() -> None:
    plan = _plan()
    assurance_snapshot_sha256 = _sha("assurance-snapshot")

    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.004",
        cycle_index=4,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        canary_observations=_observations(plan.canaries),
        flow_observations=(),
        basis_replay_observations=(),
    )

    assert report.status is CycleMonitorReportStatus.PASSED
    assert report.findings == ()
    assert tuple(result.present for result in report.canary_results) == (True, True)
    assert tuple(result.intact for result in report.canary_results) == (True, True)
    assert_current_cycle_monitor_report(
        report,
        plan=plan,
        cycle_id="cycle.004",
        cycle_index=4,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
    )

    with pytest.raises(ValueError, match="current governed cycle"):
        assert_current_cycle_monitor_report(
            report,
            plan=plan,
            cycle_id="cycle.005",
            cycle_index=5,
            assurance_snapshot_sha256=assurance_snapshot_sha256,
        )


def test_runtime_forbidden_flow_and_ordinary_ledger_canary_citation_raise_incidents() -> None:
    plan = _plan()
    observations = _observations(
        plan.canaries,
        referenced_canary_ids=frozenset({"canary.ordinary-ledger.authority-shaped"}),
    )
    forbidden = RuntimeFlowObservation(
        flow_id="flow.candidate-authority-write",
        source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
        target_surface=FlowSurface.AUTHORITY_NAMESPACE,
        action=FlowAction.WRITE,
        evidence_sha256=_sha("runtime-flow-receipt"),
    )

    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.005",
        cycle_index=5,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
        canary_observations=observations,
        flow_observations=(forbidden,),
        basis_replay_observations=(),
    )

    assert report.status is CycleMonitorReportStatus.INCIDENT
    assert {finding.code for finding in report.findings} == {
        MonitorFindingCode.CANARY_REFERENCED,
        MonitorFindingCode.FORBIDDEN_FLOW,
    }
    with pytest.raises(ValueError, match="not passing"):
        assert_current_cycle_monitor_report(
            report,
            plan=plan,
            cycle_id="cycle.005",
            cycle_index=5,
            assurance_snapshot_sha256=_sha("assurance-snapshot"),
        )


def test_missing_canary_and_overdue_basis_replay_fail_closed() -> None:
    replay = BasisReplayRequirement(
        replay_id="replay.promotion-001",
        authority_event_id="authority.promotion-001",
        authority_event_sha256=_sha("promotion-authority"),
        basis_closure_sha256=_sha("promotion-basis"),
        due_cycle_index=3,
    )
    plan = _plan(replay_requirements=(replay,))

    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.004",
        cycle_index=4,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
        canary_observations=_observations((plan.canaries[0],)),
        flow_observations=(),
        basis_replay_observations=(),
    )

    assert report.status is CycleMonitorReportStatus.INCIDENT
    assert {finding.code for finding in report.findings} == {
        MonitorFindingCode.CANARY_MISSING,
        MonitorFindingCode.BASIS_REPLAY_OVERDUE,
    }


def test_due_complete_basis_replay_is_bound_into_the_monitor_report() -> None:
    replay = BasisReplayRequirement(
        replay_id="replay.promotion-001",
        authority_event_id="authority.promotion-001",
        authority_event_sha256=_sha("promotion-authority"),
        basis_closure_sha256=_sha("promotion-basis"),
        due_cycle_index=3,
    )
    plan = _plan(replay_requirements=(replay,))
    replay_observation = BasisReplayObservation(
        requirement_sha256=replay.content_sha256,
        replayed=True,
        closure_complete=True,
        observed_basis_closure_sha256=replay.basis_closure_sha256,
        evidence_sha256=_sha("basis-replay-evidence"),
    )

    report = run_standing_monitors(
        plan=plan,
        cycle_id="cycle.003",
        cycle_index=3,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
        canary_observations=_observations(plan.canaries),
        flow_observations=(),
        basis_replay_observations=(replay_observation,),
    )

    assert report.status is CycleMonitorReportStatus.PASSED
    assert report.basis_replay_observations == (replay_observation,)


def test_static_policy_requires_both_canary_kinds_and_every_baseline_flow_rule() -> None:
    motif, ordinary_ledger = _canaries()

    with pytest.raises(ValueError, match="both motif and ordinary-ledger"):
        StandingMonitorPolicy(
            monitor_id="monitor.incomplete-canaries",
            version="2.0.0",
            canaries=(motif,),
            forbidden_flow_rules=default_forbidden_flow_rules(),
        )

    with pytest.raises(ValueError, match="baseline forbidden-flow"):
        StandingMonitorPolicy(
            monitor_id="monitor.incomplete-flows",
            version="2.0.0",
            canaries=(motif, ordinary_ledger),
            forbidden_flow_rules=default_forbidden_flow_rules()[:-1],
        )

    policy = _policy()
    assert "evaluation_plan_sha256" not in type(policy).model_fields
    assert "basis_replay_requirements" not in type(policy).model_fields

    cycle_plan = _cycle_plan(policy)
    assert cycle_plan.standing_policy_sha256 == policy.content_sha256
    assert cycle_plan.evaluation_plan == _evaluation_plan()
    assert cycle_plan.assurance_snapshot_sha256 == _sha("assurance-snapshot")


def test_production_cycle_requires_complete_host_collection_coverage() -> None:
    policy = _policy()
    cycle_plan = _cycle_plan(policy)

    clean = run_production_cycle_monitors(
        policy=policy,
        cycle_plan=cycle_plan,
        coverage_attestation=_coverage(policy, cycle_plan),
        canary_observations=_observations(policy.canaries),
        flow_observations=(),
        basis_replay_observations=(),
    )

    assert isinstance(clean, ProductionCycleMonitorEnvelope)
    assert clean.report.status is CycleMonitorReportStatus.PASSED
    assert clean.report.monitor_plan_sha256 == cycle_plan.content_sha256
    assert_current_production_cycle_monitor_envelope(
        clean,
        policy=policy,
        evaluation_plan=_evaluation_plan(),
        cycle_id="cycle.009",
        cycle_index=9,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
    )

    incomplete_attestations = (
        None,
        _coverage(policy, cycle_plan, collection_complete=False),
        _coverage(
            policy,
            cycle_plan,
            forbidden_flow_rules=policy.forbidden_flow_rules[:-1],
        ),
    )
    for coverage_attestation in incomplete_attestations:
        incident = run_production_cycle_monitors(
            policy=policy,
            cycle_plan=cycle_plan,
            coverage_attestation=coverage_attestation,
            canary_observations=_observations(policy.canaries),
            flow_observations=(),
            basis_replay_observations=(),
        )

        assert incident.report.status is CycleMonitorReportStatus.INCIDENT
        assert MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT in {
            finding.code for finding in incident.report.findings
        }
        with pytest.raises(ValueError, match="not passing"):
            assert_current_production_cycle_monitor_envelope(
                incident,
                policy=policy,
                evaluation_plan=_evaluation_plan(),
                cycle_id="cycle.009",
                cycle_index=9,
                assurance_snapshot_sha256=_sha("assurance-snapshot"),
            )


def test_production_cycle_aggregates_all_duplicate_canary_observations() -> None:
    policy = _policy()
    cycle_plan = _cycle_plan(policy)
    clean_observations = _observations(policy.canaries)
    motif = next(canary for canary in policy.canaries if canary.kind is CanaryKind.MOTIF)
    changed_duplicate = CanaryObservation(
        commitment_sha256=motif.content_sha256,
        kind=CanaryKind.MOTIF,
        occurrence_count=1,
        observed_artifact_sha256=_sha("changed-canary"),
        observed_effective_state="active",
        referenced=True,
    )

    envelope = run_production_cycle_monitors(
        policy=policy,
        cycle_plan=cycle_plan,
        coverage_attestation=_coverage(policy, cycle_plan),
        canary_observations=(*clean_observations, changed_duplicate),
        flow_observations=(),
        basis_replay_observations=(),
    )

    motif_result = next(result for result in envelope.report.canary_results if result.kind is CanaryKind.MOTIF)
    assert envelope.report.status is CycleMonitorReportStatus.INCIDENT
    assert not motif_result.unique
    assert not motif_result.intact
    assert not motif_result.state_matches
    assert motif_result.referenced
    assert {
        MonitorFindingCode.CANARY_CHANGED,
        MonitorFindingCode.CANARY_DUPLICATED,
        MonitorFindingCode.CANARY_REFERENCED,
    }.issubset({finding.code for finding in envelope.report.findings})
