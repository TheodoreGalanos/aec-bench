# ABOUTME: Derives standing-monitor coverage solely from host-collected activation evidence.
# ABOUTME: Keeps completeness fail-closed unless every exact canary and forbidden-flow rule is active.

from __future__ import annotations

from collections.abc import Iterable

from aec_bench.contracts.authority import AuthorityPrincipal
from aec_bench.meta_harness.monitor_repository import _flow_rule_identity
from aec_bench.meta_harness.standing_monitors import (
    CycleMonitorPlan,
    ForbiddenFlowRule,
    MonitorCoverageAttestation,
    StandingMonitorPolicy,
)


def collection_is_complete(
    *,
    policy: StandingMonitorPolicy,
    activated_canary_sha256s: Iterable[str],
    activated_rules: Iterable[ForbiddenFlowRule],
) -> bool:
    """Return whether activation evidence covers the exact standing policy."""

    expected_canaries = {canary.content_sha256 for canary in policy.canaries}
    observed_canaries = set(activated_canary_sha256s)
    expected_rules = {_flow_rule_identity(rule) for rule in policy.forbidden_flow_rules}
    observed_rules = {_flow_rule_identity(rule) for rule in activated_rules}
    return observed_canaries == expected_canaries and observed_rules == expected_rules


def derive_coverage_attestation(
    *,
    cycle_plan: CycleMonitorPlan,
    observed_by: AuthorityPrincipal,
    collection_complete: bool,
    covered_canary_commitment_sha256s: tuple[str, ...],
    covered_forbidden_flow_rules: tuple[ForbiddenFlowRule, ...],
    evidence_sha256: str,
) -> MonitorCoverageAttestation:
    """Bind exact host activation evidence into one canonical coverage attestation."""

    return MonitorCoverageAttestation(
        cycle_monitor_plan_sha256=cycle_plan.content_sha256,
        observed_by=observed_by,
        collection_complete=collection_complete,
        covered_canary_commitment_sha256s=covered_canary_commitment_sha256s,
        covered_forbidden_flow_rules=covered_forbidden_flow_rules,
        covered_basis_replay_requirement_sha256s=tuple(
            requirement.content_sha256 for requirement in cycle_plan.basis_replay_requirements
        ),
        evidence_sha256=evidence_sha256,
    )
