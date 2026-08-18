# ABOUTME: Defines immutable standing-monitor policies, evidence, findings, and cycle reports.
# ABOUTME: Enforces canonical monitor shapes without owning runtime collection or persistence.

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, JsonValue, PositiveInt, field_validator, model_validator

from aec_bench.contracts.authority import AuthorityPrincipal, AuthorityPrincipalKind, EvaluationPlanIdentity
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr


class CanaryKind(StrEnum):
    """Standing sentinel surfaces exercised by every governed cycle."""

    MOTIF = "motif"
    ORDINARY_LEDGER = "ordinary_ledger"


class FlowSurface(StrEnum):
    """Protected surfaces that adaptive operators cannot mutate or open."""

    TASK_DEFINITION = "task_definition"
    CRITIC_DEFINITION = "critic_definition"
    AUTHORITY_NAMESPACE = "authority_namespace"
    HOLDOUT = "holdout"
    PROMOTION = "promotion"


class FlowAction(StrEnum):
    """Runtime-observed operations used by closed forbidden-flow rules."""

    READ = "read"
    WRITE = "write"
    CITE = "cite"
    GRANT = "grant"
    PROMOTE = "promote"


class MonitorFindingCode(StrEnum):
    """Closed incident codes emitted by the standing monitor plane."""

    CANARY_MISSING = "canary_missing"
    CANARY_CHANGED = "canary_changed"
    CANARY_DUPLICATED = "canary_duplicated"
    CANARY_REFERENCED = "canary_referenced"
    FORBIDDEN_FLOW = "forbidden_flow"
    BASIS_REPLAY_OVERDUE = "basis_replay_overdue"
    BASIS_REPLAY_FAILED = "basis_replay_failed"
    MONITOR_EVIDENCE_INCONSISTENT = "monitor_evidence_inconsistent"


class CycleMonitorReportStatus(StrEnum):
    """Whether current monitor evidence permits a later integrity gate to continue."""

    PASSED = "passed"
    INCIDENT = "incident"


class CanaryCommitment(LegacyContentAddressedModel):
    """Host-side commitment to one canary without retaining its payload in the report."""

    schema_version: Literal["aecbench.canary-commitment.v1"] = "aecbench.canary-commitment.v1"
    canary_id: NonEmptyStr
    kind: CanaryKind
    artifact_sha256: str
    expected_effective_state: NonEmptyStr | None = None

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_kind_shape(self) -> Self:
        if self.kind is CanaryKind.MOTIF and self.expected_effective_state is None:
            raise ValueError("motif canaries require an expected effective state")
        if self.kind is CanaryKind.ORDINARY_LEDGER and self.expected_effective_state is not None:
            raise ValueError("ordinary-ledger canaries cannot declare motif state")
        return self

    @classmethod
    def create(
        cls,
        *,
        canary_id: str,
        kind: CanaryKind,
        artifact_payload: JsonValue,
        expected_effective_state: str | None = None,
    ) -> CanaryCommitment:
        """Commit the canonical payload while keeping its bytes outside public monitor reports."""
        return cls(
            canary_id=canary_id,
            kind=kind,
            artifact_sha256=canonical_json_sha256(artifact_payload),
            expected_effective_state=expected_effective_state,
        )


class CanaryObservation(LegacyContentAddressedModel):
    """Host-observed presence, bytes, state, and use for one committed canary."""

    schema_version: Literal["aecbench.canary-observation.v1"] = "aecbench.canary-observation.v1"
    commitment_sha256: str
    kind: CanaryKind
    occurrence_count: int = Field(ge=0)
    observed_artifact_sha256: str | None = None
    observed_effective_state: NonEmptyStr | None = None
    referenced: bool = False

    @field_validator("commitment_sha256", "observed_artifact_sha256")
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_presence_shape(self) -> Self:
        if self.occurrence_count == 0 and self.observed_artifact_sha256 is not None:
            raise ValueError("missing canary observations cannot contain observed bytes")
        if self.occurrence_count > 0 and self.observed_artifact_sha256 is None:
            raise ValueError("present canary observations require observed bytes")
        if self.kind is CanaryKind.ORDINARY_LEDGER and self.observed_effective_state is not None:
            raise ValueError("ordinary-ledger canary observations cannot declare motif state")
        return self

    @classmethod
    def observe(
        cls,
        *,
        commitment: CanaryCommitment,
        observed_payload: JsonValue | None,
        occurrence_count: int,
        referenced: bool = False,
        observed_effective_state: str | None = None,
    ) -> CanaryObservation:
        """Create an observation from bytes read by the host monitor."""
        if occurrence_count == 0 and observed_payload is not None:
            raise ValueError("missing canary observations cannot contain a payload")
        if occurrence_count > 0 and observed_payload is None:
            raise ValueError("present canary observations require a payload")
        return cls(
            commitment_sha256=commitment.content_sha256,
            kind=commitment.kind,
            occurrence_count=occurrence_count,
            observed_artifact_sha256=(None if observed_payload is None else canonical_json_sha256(observed_payload)),
            observed_effective_state=observed_effective_state,
            referenced=referenced,
        )


class CanaryResult(FrozenStrictModel):
    """Public-safe result for one opaque canary commitment."""

    commitment_sha256: str
    kind: CanaryKind
    present: bool
    intact: bool
    unique: bool
    referenced: bool
    state_matches: bool

    @field_validator("commitment_sha256")
    @classmethod
    def validate_commitment_hash(cls, value: str) -> str:
        return validate_sha256(value)


class ForbiddenFlowRule(FrozenStrictModel):
    """One exact principal, operation, and protected-surface combination."""

    source_principal_kind: AuthorityPrincipalKind
    target_surface: FlowSurface
    action: FlowAction

    def matches(self, observation: RuntimeFlowObservation) -> bool:
        """Return whether a runtime observation violates this exact rule."""
        return (
            self.source_principal_kind is observation.source_principal_kind
            and self.target_surface is observation.target_surface
            and self.action is observation.action
        )


class RuntimeFlowObservation(LegacyContentAddressedModel):
    """One host-observed runtime flow, including the physical evidence that exposed it."""

    schema_version: Literal["aecbench.runtime-flow-observation.v1"] = "aecbench.runtime-flow-observation.v1"
    flow_id: NonEmptyStr
    source_principal_kind: AuthorityPrincipalKind
    target_surface: FlowSurface
    action: FlowAction
    evidence_sha256: str

    @field_validator("evidence_sha256")
    @classmethod
    def validate_evidence_hash(cls, value: str) -> str:
        return validate_sha256(value)


class BasisReplayRequirement(LegacyContentAddressedModel):
    """Accepted authority basis that must close again no later than one cycle."""

    schema_version: Literal["aecbench.basis-replay-requirement.v1"] = "aecbench.basis-replay-requirement.v1"
    replay_id: NonEmptyStr
    authority_event_id: NonEmptyStr
    authority_event_sha256: str
    basis_closure_sha256: str
    due_cycle_index: int = Field(ge=0)

    @field_validator("authority_event_sha256", "basis_closure_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class BasisReplayObservation(LegacyContentAddressedModel):
    """Result of resolving one scheduled accepted basis chain through the trusted store."""

    schema_version: Literal["aecbench.basis-replay-observation.v1"] = "aecbench.basis-replay-observation.v1"
    requirement_sha256: str
    replayed: bool
    closure_complete: bool
    observed_basis_closure_sha256: str | None = None
    evidence_sha256: str | None = None

    @field_validator(
        "requirement_sha256",
        "observed_basis_closure_sha256",
        "evidence_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @model_validator(mode="after")
    def validate_replay_shape(self) -> Self:
        if self.closure_complete and not self.replayed:
            raise ValueError("complete basis closure requires an attempted replay")
        if self.closure_complete and (self.observed_basis_closure_sha256 is None or self.evidence_sha256 is None):
            raise ValueError("complete basis replay requires closure and evidence identities")
        return self


class StandingMonitorPlan(LegacyContentAddressedModel):
    """Host-side standing alarms and replay schedule for every governed cycle."""

    schema_version: Literal["aecbench.standing-monitor-plan.v1"] = "aecbench.standing-monitor-plan.v1"
    monitor_id: NonEmptyStr
    version: NonEmptyStr
    evaluation_plan: EvaluationPlanIdentity
    canaries: tuple[CanaryCommitment, ...] = Field(min_length=1)
    forbidden_flow_rules: tuple[ForbiddenFlowRule, ...] = ()
    basis_replay_requirements: tuple[BasisReplayRequirement, ...] = ()
    report_validity_cycles: PositiveInt = 1

    @field_validator("canaries")
    @classmethod
    def canonicalize_canaries(
        cls,
        value: tuple[CanaryCommitment, ...],
    ) -> tuple[CanaryCommitment, ...]:
        identities = tuple(canary.content_sha256 for canary in value)
        if len(identities) != len(set(identities)):
            raise ValueError("standing monitor canaries must be unique")
        return tuple(sorted(value, key=lambda canary: canary.content_sha256))

    @field_validator("forbidden_flow_rules")
    @classmethod
    def canonicalize_rules(
        cls,
        value: tuple[ForbiddenFlowRule, ...],
    ) -> tuple[ForbiddenFlowRule, ...]:
        identities = tuple(
            (rule.source_principal_kind.value, rule.target_surface.value, rule.action.value) for rule in value
        )
        if len(identities) != len(set(identities)):
            raise ValueError("forbidden flow rules must be unique")
        return tuple(
            sorted(
                value,
                key=lambda rule: (
                    rule.source_principal_kind.value,
                    rule.target_surface.value,
                    rule.action.value,
                ),
            )
        )

    @field_validator("basis_replay_requirements")
    @classmethod
    def canonicalize_replays(
        cls,
        value: tuple[BasisReplayRequirement, ...],
    ) -> tuple[BasisReplayRequirement, ...]:
        identities = tuple(requirement.content_sha256 for requirement in value)
        if len(identities) != len(set(identities)):
            raise ValueError("basis replay requirements must be unique")
        return tuple(sorted(value, key=lambda requirement: requirement.content_sha256))


class StandingMonitorPolicy(LegacyContentAddressedModel):
    """Static production monitor surface pinned by an evaluation plan."""

    schema_version: Literal["aecbench.standing-monitor-policy.v2"] = "aecbench.standing-monitor-policy.v2"
    monitor_id: NonEmptyStr
    version: NonEmptyStr
    canaries: tuple[CanaryCommitment, ...]
    forbidden_flow_rules: tuple[ForbiddenFlowRule, ...] = Field(min_length=1)
    report_validity_cycles: PositiveInt = 1

    @field_validator("canaries")
    @classmethod
    def canonicalize_canaries(
        cls,
        value: tuple[CanaryCommitment, ...],
    ) -> tuple[CanaryCommitment, ...]:
        identities = tuple(canary.content_sha256 for canary in value)
        if len(identities) != len(set(identities)):
            raise ValueError("standing monitor canaries must be unique")
        return tuple(sorted(value, key=lambda canary: canary.content_sha256))

    @field_validator("forbidden_flow_rules")
    @classmethod
    def canonicalize_rules(
        cls,
        value: tuple[ForbiddenFlowRule, ...],
    ) -> tuple[ForbiddenFlowRule, ...]:
        identities = tuple(_flow_rule_identity(rule) for rule in value)
        if len(identities) != len(set(identities)):
            raise ValueError("forbidden flow rules must be unique")
        return tuple(sorted(value, key=_flow_rule_identity))

    @model_validator(mode="after")
    def validate_required_standing_alarms(self) -> Self:
        kinds = {canary.kind for canary in self.canaries}
        if kinds != {CanaryKind.MOTIF, CanaryKind.ORDINARY_LEDGER}:
            raise ValueError("standing monitor policy requires both motif and ordinary-ledger canaries")
        configured = {_flow_rule_identity(rule) for rule in self.forbidden_flow_rules}
        baseline = {_flow_rule_identity(rule) for rule in default_forbidden_flow_rules()}
        if not baseline.issubset(configured):
            raise ValueError("standing monitor policy must include every baseline forbidden-flow rule")
        return self


class CycleMonitorPlan(LegacyContentAddressedModel):
    """Dynamic cycle selection bound to one static monitor policy and assurance state."""

    schema_version: Literal["aecbench.cycle-monitor-plan.v2"] = "aecbench.cycle-monitor-plan.v2"
    cycle_id: NonEmptyStr
    cycle_index: int = Field(ge=0)
    evaluation_plan: EvaluationPlanIdentity
    standing_policy_sha256: str
    assurance_snapshot_sha256: str
    basis_replay_requirements: tuple[BasisReplayRequirement, ...] = ()

    @field_validator(
        "standing_policy_sha256",
        "assurance_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("basis_replay_requirements")
    @classmethod
    def canonicalize_replays(
        cls,
        value: tuple[BasisReplayRequirement, ...],
    ) -> tuple[BasisReplayRequirement, ...]:
        identities = tuple(requirement.content_sha256 for requirement in value)
        if len(identities) != len(set(identities)):
            raise ValueError("basis replay requirements must be unique")
        return tuple(sorted(value, key=lambda requirement: requirement.content_sha256))


class MonitorCoverageAttestation(LegacyContentAddressedModel):
    """Host attestation that every static and cycle-specific monitor was collected."""

    schema_version: Literal["aecbench.monitor-coverage-attestation.v2"] = "aecbench.monitor-coverage-attestation.v2"
    cycle_monitor_plan_sha256: str
    observed_by: AuthorityPrincipal
    collection_complete: bool
    covered_canary_commitment_sha256s: tuple[str, ...] = ()
    covered_forbidden_flow_rules: tuple[ForbiddenFlowRule, ...] = ()
    covered_basis_replay_requirement_sha256s: tuple[str, ...] = ()
    evidence_sha256: str

    @field_validator("cycle_monitor_plan_sha256", "evidence_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "covered_canary_commitment_sha256s",
        "covered_basis_replay_requirement_sha256s",
    )
    @classmethod
    def canonicalize_covered_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("monitor coverage references must be unique")
        return tuple(sorted(value))

    @field_validator("covered_forbidden_flow_rules")
    @classmethod
    def canonicalize_covered_rules(
        cls,
        value: tuple[ForbiddenFlowRule, ...],
    ) -> tuple[ForbiddenFlowRule, ...]:
        identities = tuple(_flow_rule_identity(rule) for rule in value)
        if len(identities) != len(set(identities)):
            raise ValueError("covered forbidden-flow rules must be unique")
        return tuple(sorted(value, key=_flow_rule_identity))

    @model_validator(mode="after")
    def validate_host_observer(self) -> Self:
        if self.observed_by.kind not in {
            AuthorityPrincipalKind.HOST_RUNTIME,
            AuthorityPrincipalKind.HOST_POLICY,
        }:
            raise ValueError("monitor coverage must be attested by a host principal")
        return self


class MonitorFinding(LegacyContentAddressedModel):
    """Detection-only incident over one opaque subject and its supporting evidence."""

    schema_version: Literal["aecbench.monitor-finding.v1"] = "aecbench.monitor-finding.v1"
    code: MonitorFindingCode
    subject_id: NonEmptyStr
    evidence_sha256s: tuple[str, ...] = ()
    detail: NonEmptyStr

    @field_validator("evidence_sha256s")
    @classmethod
    def canonicalize_evidence_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("monitor finding evidence references must be unique")
        return tuple(sorted(value))


class CycleMonitorReport(LegacyContentAddressedModel):
    """Current-cycle monitor evidence consumed by, but never authoritative over, promotion."""

    schema_version: Literal["aecbench.cycle-monitor-report.v1"] = "aecbench.cycle-monitor-report.v1"
    cycle_id: NonEmptyStr
    cycle_index: int = Field(ge=0)
    valid_through_cycle_index: int = Field(ge=0)
    monitor_plan_sha256: str
    assurance_snapshot_sha256: str
    status: CycleMonitorReportStatus
    canary_results: tuple[CanaryResult, ...]
    flow_observations: tuple[RuntimeFlowObservation, ...] = ()
    basis_replay_observations: tuple[BasisReplayObservation, ...] = ()
    findings: tuple[MonitorFinding, ...] = ()

    @field_validator("monitor_plan_sha256", "assurance_snapshot_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("canary_results")
    @classmethod
    def canonicalize_canary_results(
        cls,
        value: tuple[CanaryResult, ...],
    ) -> tuple[CanaryResult, ...]:
        identities = tuple(result.commitment_sha256 for result in value)
        if len(identities) != len(set(identities)):
            raise ValueError("cycle monitor canary results must be unique")
        return tuple(sorted(value, key=lambda result: result.commitment_sha256))

    @field_validator("flow_observations")
    @classmethod
    def canonicalize_flows(
        cls,
        value: tuple[RuntimeFlowObservation, ...],
    ) -> tuple[RuntimeFlowObservation, ...]:
        identities = tuple(observation.content_sha256 for observation in value)
        if len(identities) != len(set(identities)):
            raise ValueError("cycle monitor flow observations must be unique")
        return tuple(sorted(value, key=lambda observation: observation.content_sha256))

    @field_validator("basis_replay_observations")
    @classmethod
    def canonicalize_replay_observations(
        cls,
        value: tuple[BasisReplayObservation, ...],
    ) -> tuple[BasisReplayObservation, ...]:
        identities = tuple(observation.requirement_sha256 for observation in value)
        if len(identities) != len(set(identities)):
            raise ValueError("cycle monitor basis replay observations must be unique by requirement")
        return tuple(sorted(value, key=lambda observation: observation.requirement_sha256))

    @field_validator("findings")
    @classmethod
    def canonicalize_findings(
        cls,
        value: tuple[MonitorFinding, ...],
    ) -> tuple[MonitorFinding, ...]:
        identities = tuple(finding.content_sha256 for finding in value)
        if len(identities) != len(set(identities)):
            raise ValueError("cycle monitor findings must be unique")
        return tuple(
            sorted(
                value,
                key=lambda finding: (
                    finding.code.value,
                    finding.subject_id,
                    finding.content_sha256,
                ),
            )
        )

    @model_validator(mode="after")
    def validate_report_status(self) -> Self:
        if self.valid_through_cycle_index < self.cycle_index:
            raise ValueError("cycle monitor report cannot expire before its source cycle")
        expected = CycleMonitorReportStatus.INCIDENT if self.findings else CycleMonitorReportStatus.PASSED
        if self.status is not expected:
            raise ValueError("cycle monitor report status must reflect its findings")
        return self


class ProductionCycleMonitorEnvelope(LegacyContentAddressedModel):
    """Complete production monitor evidence joining static policy and cycle collection."""

    schema_version: Literal["aecbench.production-cycle-monitor-envelope.v2"] = (
        "aecbench.production-cycle-monitor-envelope.v2"
    )
    policy: StandingMonitorPolicy
    cycle_plan: CycleMonitorPlan
    coverage_attestation: MonitorCoverageAttestation | None
    report: CycleMonitorReport

    @model_validator(mode="after")
    def validate_envelope_bindings(self) -> Self:
        if self.cycle_plan.standing_policy_sha256 != self.policy.content_sha256:
            raise ValueError("production cycle plan does not bind the enclosed standing policy")
        if (
            self.report.monitor_plan_sha256 != self.cycle_plan.content_sha256
            or self.report.cycle_id != self.cycle_plan.cycle_id
            or self.report.cycle_index != self.cycle_plan.cycle_index
            or self.report.assurance_snapshot_sha256 != self.cycle_plan.assurance_snapshot_sha256
            or self.report.valid_through_cycle_index
            != self.cycle_plan.cycle_index + int(self.policy.report_validity_cycles) - 1
        ):
            raise ValueError("production monitor report does not bind the enclosed cycle plan")
        expected_canaries = {(canary.content_sha256, canary.kind) for canary in self.policy.canaries}
        observed_canaries = {(result.commitment_sha256, result.kind) for result in self.report.canary_results}
        if observed_canaries != expected_canaries:
            raise ValueError("production monitor report does not cover every policy canary")
        coverage_errors = monitor_coverage_errors(
            policy=self.policy,
            cycle_plan=self.cycle_plan,
            coverage_attestation=self.coverage_attestation,
        )
        has_coverage_finding = any(
            finding.code is MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT
            and finding.subject_id == "monitor-coverage"
            for finding in self.report.findings
        )
        if bool(coverage_errors) is not has_coverage_finding:
            raise ValueError("production monitor report does not reflect host coverage state")
        return self


def default_forbidden_flow_rules() -> tuple[ForbiddenFlowRule, ...]:
    """Return the initial closed rules from the approved evaluation-governance plan."""
    rules = (
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.TASK_DEFINITION,
            action=FlowAction.WRITE,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.CRITIC_DEFINITION,
            action=FlowAction.READ,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.CRITIC_DEFINITION,
            action=FlowAction.WRITE,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.AUTHORITY_NAMESPACE,
            action=FlowAction.WRITE,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.AUTHORITY_NAMESPACE,
            action=FlowAction.CITE,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.AUTHORITY_NAMESPACE,
            action=FlowAction.GRANT,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.HOLDOUT,
            action=FlowAction.READ,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.HOLDOUT,
            action=FlowAction.WRITE,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.RED_TEAM,
            target_surface=FlowSurface.PROMOTION,
            action=FlowAction.CITE,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.RED_TEAM,
            target_surface=FlowSurface.PROMOTION,
            action=FlowAction.GRANT,
        ),
        ForbiddenFlowRule(
            source_principal_kind=AuthorityPrincipalKind.RED_TEAM,
            target_surface=FlowSurface.PROMOTION,
            action=FlowAction.PROMOTE,
        ),
    )
    return tuple(
        sorted(
            rules,
            key=lambda rule: (
                rule.source_principal_kind.value,
                rule.target_surface.value,
                rule.action.value,
            ),
        )
    )


def monitor_coverage_errors(
    *,
    policy: StandingMonitorPolicy,
    cycle_plan: CycleMonitorPlan,
    coverage_attestation: MonitorCoverageAttestation | None,
) -> tuple[str, ...]:
    if coverage_attestation is None:
        return ("host monitor coverage attestation is absent",)

    errors: list[str] = []
    if coverage_attestation.cycle_monitor_plan_sha256 != cycle_plan.content_sha256:
        errors.append("coverage attestation does not bind the cycle monitor plan")
    if not coverage_attestation.collection_complete:
        errors.append("host monitor collection is incomplete")
    expected_canaries = {canary.content_sha256 for canary in policy.canaries}
    if set(coverage_attestation.covered_canary_commitment_sha256s) != expected_canaries:
        errors.append("host collection does not cover every policy canary")
    expected_rules = {_flow_rule_identity(rule) for rule in policy.forbidden_flow_rules}
    covered_rules = {_flow_rule_identity(rule) for rule in coverage_attestation.covered_forbidden_flow_rules}
    if covered_rules != expected_rules:
        errors.append("host collection does not cover every forbidden-flow rule")
    expected_replays = {requirement.content_sha256 for requirement in cycle_plan.basis_replay_requirements}
    if set(coverage_attestation.covered_basis_replay_requirement_sha256s) != expected_replays:
        errors.append("host collection does not cover every scheduled basis replay")
    return tuple(errors)


def _flow_rule_identity(
    rule: ForbiddenFlowRule,
) -> tuple[str, str, str]:
    return (
        rule.source_principal_kind.value,
        rule.target_surface.value,
        rule.action.value,
    )
