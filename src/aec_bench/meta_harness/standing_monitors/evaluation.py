# ABOUTME: Evaluates standing canaries, forbidden flows, replay evidence, and host coverage.
# ABOUTME: Produces deterministic cycle reports without collecting or persisting runtime evidence.

from __future__ import annotations

from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.meta_harness.standing_monitors.models import (
    BasisReplayObservation,
    BasisReplayRequirement,
    CanaryCommitment,
    CanaryObservation,
    CanaryResult,
    CycleMonitorPlan,
    CycleMonitorReport,
    CycleMonitorReportStatus,
    ForbiddenFlowRule,
    MonitorCoverageAttestation,
    MonitorFinding,
    MonitorFindingCode,
    ProductionCycleMonitorEnvelope,
    RuntimeFlowObservation,
    StandingMonitorPlan,
    StandingMonitorPolicy,
    monitor_coverage_errors,
)


def run_production_cycle_monitors(
    *,
    policy: StandingMonitorPolicy,
    cycle_plan: CycleMonitorPlan,
    coverage_attestation: MonitorCoverageAttestation | None,
    canary_observations: tuple[CanaryObservation, ...],
    flow_observations: tuple[RuntimeFlowObservation, ...],
    basis_replay_observations: tuple[BasisReplayObservation, ...],
) -> ProductionCycleMonitorEnvelope:
    """Evaluate one production cycle against its static policy and host coverage."""
    selected_policy = StandingMonitorPolicy.model_validate(policy.model_dump(mode="python"))
    selected_cycle_plan = CycleMonitorPlan.model_validate(cycle_plan.model_dump(mode="python"))
    selected_coverage = (
        None
        if coverage_attestation is None
        else MonitorCoverageAttestation.model_validate(coverage_attestation.model_dump(mode="python"))
    )
    if selected_cycle_plan.standing_policy_sha256 != selected_policy.content_sha256:
        raise ValueError("cycle monitor plan does not bind the standing policy")

    findings: list[MonitorFinding] = []
    canary_results = _evaluate_canaries(
        selected_policy.canaries,
        canary_observations,
        findings=findings,
        aggregate_duplicate_observations=True,
    )
    _evaluate_flows(
        selected_policy.forbidden_flow_rules,
        flow_observations,
        findings=findings,
    )
    replay_results = _evaluate_basis_replays(
        selected_cycle_plan.basis_replay_requirements,
        basis_replay_observations,
        cycle_index=selected_cycle_plan.cycle_index,
        findings=findings,
    )
    coverage_errors = monitor_coverage_errors(
        policy=selected_policy,
        cycle_plan=selected_cycle_plan,
        coverage_attestation=selected_coverage,
    )
    if coverage_errors:
        evidence_sha256s = {
            selected_policy.content_sha256,
            selected_cycle_plan.content_sha256,
        }
        if selected_coverage is not None:
            evidence_sha256s.add(selected_coverage.content_sha256)
        findings.append(
            MonitorFinding(
                code=MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT,
                subject_id="monitor-coverage",
                evidence_sha256s=tuple(evidence_sha256s),
                detail="; ".join(coverage_errors),
            )
        )

    report = CycleMonitorReport(
        cycle_id=selected_cycle_plan.cycle_id,
        cycle_index=selected_cycle_plan.cycle_index,
        valid_through_cycle_index=selected_cycle_plan.cycle_index + int(selected_policy.report_validity_cycles) - 1,
        monitor_plan_sha256=selected_cycle_plan.content_sha256,
        assurance_snapshot_sha256=selected_cycle_plan.assurance_snapshot_sha256,
        status=(CycleMonitorReportStatus.INCIDENT if findings else CycleMonitorReportStatus.PASSED),
        canary_results=canary_results,
        flow_observations=flow_observations,
        basis_replay_observations=replay_results,
        findings=tuple(findings),
    )
    return ProductionCycleMonitorEnvelope(
        policy=selected_policy,
        cycle_plan=selected_cycle_plan,
        coverage_attestation=selected_coverage,
        report=report,
    )


def run_standing_monitors(
    *,
    plan: StandingMonitorPlan,
    cycle_id: str,
    cycle_index: int,
    assurance_snapshot_sha256: str,
    canary_observations: tuple[CanaryObservation, ...],
    flow_observations: tuple[RuntimeFlowObservation, ...],
    basis_replay_observations: tuple[BasisReplayObservation, ...],
) -> CycleMonitorReport:
    """Evaluate all standing safeguards and emit one deterministic current-cycle report."""
    selected_plan = StandingMonitorPlan.model_validate(plan.model_dump(mode="python"))
    validate_sha256(assurance_snapshot_sha256)
    findings: list[MonitorFinding] = []
    canary_results = _evaluate_canaries(
        selected_plan.canaries,
        canary_observations,
        findings=findings,
    )
    _evaluate_flows(
        selected_plan.forbidden_flow_rules,
        flow_observations,
        findings=findings,
    )
    replay_results = _evaluate_basis_replays(
        selected_plan.basis_replay_requirements,
        basis_replay_observations,
        cycle_index=cycle_index,
        findings=findings,
    )
    return CycleMonitorReport(
        cycle_id=cycle_id,
        cycle_index=cycle_index,
        valid_through_cycle_index=cycle_index + int(selected_plan.report_validity_cycles) - 1,
        monitor_plan_sha256=selected_plan.content_sha256,
        assurance_snapshot_sha256=assurance_snapshot_sha256,
        status=(CycleMonitorReportStatus.INCIDENT if findings else CycleMonitorReportStatus.PASSED),
        canary_results=canary_results,
        flow_observations=flow_observations,
        basis_replay_observations=replay_results,
        findings=tuple(findings),
    )


def _evaluate_canaries(
    commitments: tuple[CanaryCommitment, ...],
    observations: tuple[CanaryObservation, ...],
    *,
    findings: list[MonitorFinding],
    aggregate_duplicate_observations: bool = False,
) -> tuple[CanaryResult, ...]:
    by_commitment: dict[str, list[CanaryObservation]] = {}
    for observation in observations:
        by_commitment.setdefault(observation.commitment_sha256, []).append(observation)
    expected = {commitment.content_sha256 for commitment in commitments}
    for unexpected in sorted(set(by_commitment) - expected):
        findings.append(
            _finding(
                MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT,
                subject_id=f"canary-commitment:{unexpected}",
                evidence_sha256s=tuple(item.content_sha256 for item in by_commitment[unexpected]),
            )
        )

    results: list[CanaryResult] = []
    for commitment in commitments:
        matches = by_commitment.get(commitment.content_sha256, [])
        if not matches:
            results.append(
                CanaryResult(
                    commitment_sha256=commitment.content_sha256,
                    kind=commitment.kind,
                    present=False,
                    intact=False,
                    unique=False,
                    referenced=False,
                    state_matches=False,
                )
            )
            findings.append(
                _finding(
                    MonitorFindingCode.CANARY_MISSING,
                    subject_id=commitment.canary_id,
                    evidence_sha256s=(commitment.content_sha256,),
                )
            )
            continue

        observation = matches[0]
        if aggregate_duplicate_observations:
            present_observations = tuple(item for item in matches if item.occurrence_count > 0)
            total_occurrences = sum(item.occurrence_count for item in matches)
            present = total_occurrences > 0
            unique = len(matches) == 1 and total_occurrences == 1
            intact = present and all(
                item.kind is commitment.kind and item.observed_artifact_sha256 == commitment.artifact_sha256
                for item in present_observations
            )
            state_matches = commitment.expected_effective_state is None or (
                bool(present_observations)
                and all(
                    item.observed_effective_state == commitment.expected_effective_state
                    for item in present_observations
                )
            )
            referenced = any(item.referenced for item in matches)
            evidence = tuple(sorted({item.content_sha256 for item in matches}))
        else:
            present = observation.occurrence_count > 0
            unique = len(matches) == 1 and observation.occurrence_count == 1
            intact = (
                present
                and observation.kind is commitment.kind
                and observation.observed_artifact_sha256 == commitment.artifact_sha256
            )
            state_matches = (
                commitment.expected_effective_state is None
                or observation.observed_effective_state == commitment.expected_effective_state
            )
            referenced = observation.referenced
            evidence = tuple(item.content_sha256 for item in matches)
        results.append(
            CanaryResult(
                commitment_sha256=commitment.content_sha256,
                kind=commitment.kind,
                present=present,
                intact=intact,
                unique=unique,
                referenced=referenced,
                state_matches=state_matches,
            )
        )
        if not present:
            findings.append(
                _finding(
                    MonitorFindingCode.CANARY_MISSING,
                    subject_id=commitment.canary_id,
                    evidence_sha256s=evidence,
                )
            )
        if not unique:
            findings.append(
                _finding(
                    MonitorFindingCode.CANARY_DUPLICATED,
                    subject_id=commitment.canary_id,
                    evidence_sha256s=evidence,
                )
            )
        if present and (not intact or not state_matches):
            findings.append(
                _finding(
                    MonitorFindingCode.CANARY_CHANGED,
                    subject_id=commitment.canary_id,
                    evidence_sha256s=evidence,
                )
            )
        if referenced:
            findings.append(
                _finding(
                    MonitorFindingCode.CANARY_REFERENCED,
                    subject_id=commitment.canary_id,
                    evidence_sha256s=evidence,
                )
            )
    return tuple(results)


def _evaluate_flows(
    rules: tuple[ForbiddenFlowRule, ...],
    observations: tuple[RuntimeFlowObservation, ...],
    *,
    findings: list[MonitorFinding],
) -> None:
    for observation in observations:
        if any(rule.matches(observation) for rule in rules):
            findings.append(
                _finding(
                    MonitorFindingCode.FORBIDDEN_FLOW,
                    subject_id=observation.flow_id,
                    evidence_sha256s=(
                        observation.evidence_sha256,
                        observation.content_sha256,
                    ),
                )
            )


def _evaluate_basis_replays(
    requirements: tuple[BasisReplayRequirement, ...],
    observations: tuple[BasisReplayObservation, ...],
    *,
    cycle_index: int,
    findings: list[MonitorFinding],
) -> tuple[BasisReplayObservation, ...]:
    by_requirement: dict[str, list[BasisReplayObservation]] = {}
    for observation in observations:
        by_requirement.setdefault(observation.requirement_sha256, []).append(observation)
    expected = {requirement.content_sha256 for requirement in requirements}
    for unexpected in sorted(set(by_requirement) - expected):
        findings.append(
            _finding(
                MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT,
                subject_id=f"basis-replay:{unexpected}",
                evidence_sha256s=tuple(item.content_sha256 for item in by_requirement[unexpected]),
            )
        )

    selected: list[BasisReplayObservation] = []
    for requirement in requirements:
        matches = by_requirement.get(requirement.content_sha256, [])
        if len(matches) > 1:
            findings.append(
                _finding(
                    MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT,
                    subject_id=requirement.replay_id,
                    evidence_sha256s=tuple(item.content_sha256 for item in matches),
                )
            )
        selected_observation = matches[0] if matches else None
        if selected_observation is not None:
            selected.append(selected_observation)
        if cycle_index < requirement.due_cycle_index:
            continue
        if selected_observation is None or not selected_observation.replayed:
            findings.append(
                _finding(
                    MonitorFindingCode.BASIS_REPLAY_OVERDUE,
                    subject_id=requirement.replay_id,
                    evidence_sha256s=(requirement.content_sha256,),
                )
            )
            continue
        if (
            not selected_observation.closure_complete
            or selected_observation.observed_basis_closure_sha256 != requirement.basis_closure_sha256
        ):
            findings.append(
                _finding(
                    MonitorFindingCode.BASIS_REPLAY_FAILED,
                    subject_id=requirement.replay_id,
                    evidence_sha256s=(
                        requirement.content_sha256,
                        selected_observation.content_sha256,
                    ),
                )
            )
    return tuple(selected)


def _finding(
    code: MonitorFindingCode,
    *,
    subject_id: str,
    evidence_sha256s: tuple[str, ...],
) -> MonitorFinding:
    return MonitorFinding(
        code=code,
        subject_id=subject_id,
        evidence_sha256s=evidence_sha256s,
        detail=code.value,
    )
