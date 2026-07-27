# ABOUTME: Defines immutable public contracts for production monitor placement, evidence, permits, and closure.
# ABOUTME: Enforces canonical ordering and fail-closed joins independently from runtime orchestration.

from __future__ import annotations

import math
import re
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.meta_harness.monitor_repository import (
    ProductionMonitorCheckpointKind,
    _flow_rule_identity,
)
from aec_bench.meta_harness.monitor_runtime.coverage import (
    collection_is_complete,
    derive_coverage_attestation,
)
from aec_bench.meta_harness.monitors import (
    BasisReplayObservation,
    CanaryKind,
    CanaryObservation,
    CycleMonitorPlan,
    CycleMonitorReportStatus,
    ForbiddenFlowRule,
    ProductionCycleMonitorEnvelope,
    RuntimeFlowObservation,
    StandingMonitorPolicy,
    run_production_cycle_monitors,
)


class FlowCollectorKind(StrEnum):
    """Closed host instrumentation modes admitted by the monitor runtime."""

    AUDIT_OR_DENIAL_PROBE = "audit_or_denial_probe"
    OUTPUT_SCAN = "output_scan"
    MOUNT_POLICY = "mount_policy"


class FlowCollectorProbeOutcome(StrEnum):
    """Active probe outcomes that demonstrate a collector can see or deny its rule."""

    CAPTURED_OR_BLOCKED = "captured_or_blocked"


class MonitorCanarySurface(ContentAddressedModel):
    """Host placement root and logical monitor projection for one canary kind."""

    schema_version: Literal["aecbench.monitor-canary-surface.v2"] = "aecbench.monitor-canary-surface.v2"
    surface_id: NonEmptyStr
    kind: CanaryKind
    host_root: NonEmptyStr
    logical_projection_namespace: NonEmptyStr

    @field_validator("host_root")
    @classmethod
    def validate_host_root(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("monitor canary surface host root must be absolute")
        return value

    @field_validator("logical_projection_namespace")
    @classmethod
    def validate_logical_projection_namespace(cls, value: str) -> str:
        if re.fullmatch(r"[a-z][a-z0-9.-]*", value) is None:
            raise ValueError("canary logical projection namespace must be a canonical lowercase identifier")
        return value


class MonitorCanaryPlacement(ContentAddressedModel):
    """One committed canary and its cycle-local physical placement."""

    schema_version: Literal["aecbench.monitor-canary-placement.v2"] = "aecbench.monitor-canary-placement.v2"
    canary_id: NonEmptyStr
    commitment_sha256: str
    kind: CanaryKind
    surface: MonitorCanarySurface
    host_path: NonEmptyStr
    logical_projection_key: NonEmptyStr

    @field_validator("commitment_sha256")
    @classmethod
    def validate_commitment_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("host_path")
    @classmethod
    def validate_host_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("physical canary host path must be absolute")
        return value

    @field_validator("logical_projection_key")
    @classmethod
    def validate_logical_projection_key(cls, value: str) -> str:
        if (
            re.fullmatch(
                r"[a-z][a-z0-9.-]*:(?:motif|ordinary_ledger):[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise ValueError("canary logical projection key must bind a namespace, kind, and commitment")
        return value

    @model_validator(mode="after")
    def validate_surface_binding(self) -> Self:
        host_root = Path(self.surface.host_root)
        host_path = Path(self.host_path)
        expected_projection_key = ":".join(
            (
                self.surface.logical_projection_namespace,
                self.kind.value,
                self.commitment_sha256,
            )
        )
        if (
            self.kind is not self.surface.kind
            or not host_path.is_relative_to(host_root)
            or self.logical_projection_key != expected_projection_key
        ):
            raise ValueError("canary placement must remain on its exact kind-matched monitored surface")
        return self


class ProductionMonitorRuntimeManifest(ContentAddressedModel):
    """Frozen monitor policy, cycle, collectors, and physical canary slots."""

    schema_version: Literal["aecbench.production-monitor-runtime-manifest.v2"] = (
        "aecbench.production-monitor-runtime-manifest.v2"
    )
    execution_scope_sha256: str
    policy: StandingMonitorPolicy
    cycle_plan: CycleMonitorPlan
    observed_by: AuthorityPrincipal
    canary_placements: tuple[MonitorCanaryPlacement, ...]

    @field_validator("execution_scope_sha256")
    @classmethod
    def validate_execution_scope_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("canary_placements")
    @classmethod
    def canonicalize_placements(
        cls,
        value: tuple[MonitorCanaryPlacement, ...],
    ) -> tuple[MonitorCanaryPlacement, ...]:
        identities = tuple(item.commitment_sha256 for item in value)
        canary_ids = tuple(item.canary_id for item in value)
        paths = tuple(item.host_path for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("monitor canary placements must be unique by commitment")
        if len(canary_ids) != len(set(canary_ids)):
            raise ValueError("monitor canary placements must be unique by canary id")
        if len(paths) != len(set(paths)):
            raise ValueError("monitor canary placement paths must be unique")
        return tuple(sorted(value, key=lambda item: item.commitment_sha256))

    @model_validator(mode="after")
    def validate_runtime_surface(self) -> Self:
        if self.observed_by.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
            raise ValueError("production monitor runtime requires a host-runtime observer")
        if self.cycle_plan.standing_policy_sha256 != self.policy.content_sha256:
            raise ValueError("production monitor runtime cycle does not bind its policy")
        expected = {(canary.canary_id, canary.content_sha256, canary.kind) for canary in self.policy.canaries}
        placed = {
            (placement.canary_id, placement.commitment_sha256, placement.kind) for placement in self.canary_placements
        }
        if placed != expected:
            raise ValueError("production monitor runtime must place every exact policy canary")
        return self


class CanaryLogicalProjectionConfiguration(ContentAddressedModel):
    """Exact host placement, logical projection, guard, and semantic probe wiring."""

    schema_version: Literal["aecbench.canary-logical-projection-configuration.v1"] = (
        "aecbench.canary-logical-projection-configuration.v1"
    )
    runtime_manifest_sha256: str
    execution_scope_sha256: str
    canary_commitment_sha256: str
    surface_sha256: str
    host_path: NonEmptyStr
    logical_projection_key: NonEmptyStr
    guard_configuration_sha256: str
    semantic_probe_evidence_path: NonEmptyStr
    semantic_probe_evidence_sha256: str

    @field_validator(
        "runtime_manifest_sha256",
        "execution_scope_sha256",
        "canary_commitment_sha256",
        "surface_sha256",
        "guard_configuration_sha256",
        "semantic_probe_evidence_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("host_path", "semantic_probe_evidence_path")
    @classmethod
    def validate_host_paths(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("canary logical projection configuration paths must be absolute")
        return value

    @field_validator("logical_projection_key")
    @classmethod
    def validate_logical_projection_key(cls, value: str) -> str:
        if (
            re.fullmatch(
                r"[a-z][a-z0-9.-]*:(?:motif|ordinary_ledger):[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise ValueError("canary logical projection configuration requires a canonical key")
        return value


class CanarySurfaceProbeReceipt(ContentAddressedModel):
    """Host probe of an exact physical canary and guarded logical projection."""

    schema_version: Literal["aecbench.canary-surface-probe-receipt.v2"] = "aecbench.canary-surface-probe-receipt.v2"
    probe_id: NonEmptyStr
    runtime_manifest_sha256: str
    execution_scope_sha256: str
    canary_commitment_sha256: str
    host_path: NonEmptyStr
    logical_projection_key: NonEmptyStr
    projection_configuration_sha256: str
    observed_artifact_sha256: str
    observed_by: AuthorityPrincipal
    host_placement_confirmed: Literal[True]

    @field_validator(
        "runtime_manifest_sha256",
        "execution_scope_sha256",
        "canary_commitment_sha256",
        "projection_configuration_sha256",
        "observed_artifact_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("host_path")
    @classmethod
    def validate_probe_host_path(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("canary surface probe host path must be absolute")
        return value

    @field_validator("logical_projection_key")
    @classmethod
    def validate_probe_logical_projection_key(cls, value: str) -> str:
        if (
            re.fullmatch(
                r"[a-z][a-z0-9.-]*:(?:motif|ordinary_ledger):[0-9a-f]{64}",
                value,
            )
            is None
        ):
            raise ValueError("canary surface probe requires a canonical logical key")
        return value

    @model_validator(mode="after")
    def validate_host_probe(self) -> Self:
        if self.observed_by.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
            raise ValueError("canary surface probe requires a host-runtime observer")
        return self


class FlowCollectorProbeReceipt(ContentAddressedModel):
    """Host active-probe receipt for one exact forbidden-flow collector."""

    schema_version: Literal["aecbench.flow-collector-probe-receipt.v1"] = "aecbench.flow-collector-probe-receipt.v1"
    probe_id: NonEmptyStr
    runtime_manifest_sha256: str
    execution_scope_sha256: str
    rule: ForbiddenFlowRule
    collector_kind: FlowCollectorKind
    configuration_artifact_sha256: str
    probe_evidence_sha256: str
    outcome: FlowCollectorProbeOutcome
    observed_by: AuthorityPrincipal
    collector_armed: Literal[True]

    @field_validator(
        "runtime_manifest_sha256",
        "execution_scope_sha256",
        "configuration_artifact_sha256",
        "probe_evidence_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_host_probe(self) -> Self:
        if self.observed_by.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
            raise ValueError("flow collector probe requires a host-runtime observer")
        return self


class CanarySurfaceActivation(ContentAddressedModel):
    """Verified host placement and guarded logical projection for one canary."""

    schema_version: Literal["aecbench.canary-surface-activation.v2"] = "aecbench.canary-surface-activation.v2"
    runtime_manifest_sha256: str
    execution_scope_sha256: str
    canary_commitment_sha256: str
    configuration_artifact_path: NonEmptyStr
    configuration_artifact_sha256: str
    probe_receipt_path: NonEmptyStr
    probe_receipt: CanarySurfaceProbeReceipt

    @field_validator(
        "runtime_manifest_sha256",
        "execution_scope_sha256",
        "canary_commitment_sha256",
        "configuration_artifact_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("configuration_artifact_path", "probe_receipt_path")
    @classmethod
    def validate_absolute_paths(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("canary surface activation evidence paths must be absolute")
        return value

    @model_validator(mode="after")
    def validate_probe_binding(self) -> Self:
        probe = self.probe_receipt
        if (
            probe.runtime_manifest_sha256 != self.runtime_manifest_sha256
            or probe.execution_scope_sha256 != self.execution_scope_sha256
            or probe.canary_commitment_sha256 != self.canary_commitment_sha256
            or probe.projection_configuration_sha256 != self.configuration_artifact_sha256
        ):
            raise ValueError("canary surface activation does not bind its exact probe and configuration")
        return self


class FlowCollectorActivation(ContentAddressedModel):
    """Verified collector configuration and active probe for one forbidden-flow rule."""

    schema_version: Literal["aecbench.flow-collector-activation.v1"] = "aecbench.flow-collector-activation.v1"
    runtime_manifest_sha256: str
    execution_scope_sha256: str
    rule: ForbiddenFlowRule
    configuration_artifact_path: NonEmptyStr
    configuration_artifact_sha256: str
    probe_evidence_path: NonEmptyStr
    probe_evidence_sha256: str
    probe_receipt_path: NonEmptyStr
    probe_receipt: FlowCollectorProbeReceipt

    @field_validator(
        "runtime_manifest_sha256",
        "execution_scope_sha256",
        "configuration_artifact_sha256",
        "probe_evidence_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "configuration_artifact_path",
        "probe_evidence_path",
        "probe_receipt_path",
    )
    @classmethod
    def validate_absolute_paths(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("flow collector activation evidence paths must be absolute")
        return value

    @model_validator(mode="after")
    def validate_probe_binding(self) -> Self:
        probe = self.probe_receipt
        if (
            probe.runtime_manifest_sha256 != self.runtime_manifest_sha256
            or probe.execution_scope_sha256 != self.execution_scope_sha256
            or probe.rule != self.rule
            or probe.configuration_artifact_sha256 != self.configuration_artifact_sha256
            or probe.probe_evidence_sha256 != self.probe_evidence_sha256
            or probe.outcome is not FlowCollectorProbeOutcome.CAPTURED_OR_BLOCKED
        ):
            raise ValueError("flow collector activation does not bind its exact probe and evidence")
        return self


class CanaryReferenceEvent(ContentAddressedModel):
    """One host-recorded use of a canary by an effect-bearing runtime."""

    schema_version: Literal["aecbench.canary-reference-event.v1"] = "aecbench.canary-reference-event.v1"
    reference_id: NonEmptyStr
    canary_commitment_sha256: str
    evidence_sha256: str

    @field_validator("canary_commitment_sha256", "evidence_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class MonitorRuntimeCollectionEvidence(ContentAddressedModel):
    """Exact host-collected observations consumed by one monitor checkpoint."""

    schema_version: Literal["aecbench.monitor-runtime-collection-evidence.v1"] = (
        "aecbench.monitor-runtime-collection-evidence.v1"
    )
    runtime_manifest_sha256: str
    checkpoint: ProductionMonitorCheckpointKind
    observed_by: AuthorityPrincipal
    canary_observations: tuple[CanaryObservation, ...]
    flow_observations: tuple[RuntimeFlowObservation, ...]
    basis_replay_observations: tuple[BasisReplayObservation, ...]
    canary_reference_events: tuple[CanaryReferenceEvent, ...]
    canary_surface_activations: tuple[CanarySurfaceActivation, ...]
    flow_collector_activations: tuple[FlowCollectorActivation, ...]
    collection_complete: bool

    @field_validator("runtime_manifest_sha256")
    @classmethod
    def validate_manifest_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("canary_observations")
    @classmethod
    def canonicalize_canary_observations(
        cls,
        value: tuple[CanaryObservation, ...],
    ) -> tuple[CanaryObservation, ...]:
        return tuple(
            sorted(
                value,
                key=lambda item: (
                    item.commitment_sha256,
                    item.observed_artifact_sha256 or "",
                    item.observed_effective_state or "",
                    item.content_sha256,
                ),
            )
        )

    @field_validator("flow_observations")
    @classmethod
    def canonicalize_flow_observations(
        cls,
        value: tuple[RuntimeFlowObservation, ...],
    ) -> tuple[RuntimeFlowObservation, ...]:
        identities = tuple(item.flow_id for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("runtime flow evidence must be unique by flow_id")
        return tuple(sorted(value, key=lambda item: item.flow_id))

    @field_validator("basis_replay_observations")
    @classmethod
    def canonicalize_replay_observations(
        cls,
        value: tuple[BasisReplayObservation, ...],
    ) -> tuple[BasisReplayObservation, ...]:
        identities = tuple(item.requirement_sha256 for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("runtime basis replay evidence must be unique by requirement")
        return tuple(sorted(value, key=lambda item: item.requirement_sha256))

    @field_validator("canary_reference_events")
    @classmethod
    def canonicalize_reference_events(
        cls,
        value: tuple[CanaryReferenceEvent, ...],
    ) -> tuple[CanaryReferenceEvent, ...]:
        identities = tuple(item.reference_id for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("canary reference evidence must be unique by reference_id")
        return tuple(sorted(value, key=lambda item: item.reference_id))

    @field_validator("canary_surface_activations")
    @classmethod
    def canonicalize_canary_activations(
        cls,
        value: tuple[CanarySurfaceActivation, ...],
    ) -> tuple[CanarySurfaceActivation, ...]:
        identities = tuple(item.canary_commitment_sha256 for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("canary surface activations must be unique by commitment")
        return tuple(sorted(value, key=lambda item: item.canary_commitment_sha256))

    @field_validator("flow_collector_activations")
    @classmethod
    def canonicalize_flow_activations(
        cls,
        value: tuple[FlowCollectorActivation, ...],
    ) -> tuple[FlowCollectorActivation, ...]:
        identities = tuple(_flow_rule_identity(item.rule) for item in value)
        if len(identities) != len(set(identities)):
            raise ValueError("flow collector activations must be unique by forbidden-flow rule")
        return tuple(sorted(value, key=lambda item: _flow_rule_identity(item.rule)))

    @model_validator(mode="after")
    def validate_host_collection(self) -> Self:
        if self.observed_by.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
            raise ValueError("monitor evidence must be collected by the host runtime")
        return self


class ProductionMonitorRuntimeCheckpoint(ContentAddressedModel):
    """One persisted, host-derived production monitor checkpoint."""

    schema_version: Literal["aecbench.production-monitor-runtime-checkpoint.v1"] = (
        "aecbench.production-monitor-runtime-checkpoint.v1"
    )
    runtime_manifest_sha256: str
    checkpoint: ProductionMonitorCheckpointKind
    collection_evidence: MonitorRuntimeCollectionEvidence
    envelope: ProductionCycleMonitorEnvelope
    wall_time_seconds: float = Field(ge=0.0)

    @field_validator("runtime_manifest_sha256")
    @classmethod
    def validate_manifest_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("wall_time_seconds")
    @classmethod
    def validate_finite_wall_time(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("monitor checkpoint wall time must be finite")
        return value

    @model_validator(mode="after")
    def validate_derived_envelope(self) -> Self:
        evidence = self.collection_evidence
        if (
            evidence.runtime_manifest_sha256 != self.runtime_manifest_sha256
            or evidence.checkpoint is not self.checkpoint
        ):
            raise ValueError("monitor checkpoint does not bind its collection evidence")
        expected_coverage = derive_coverage_attestation(
            cycle_plan=self.envelope.cycle_plan,
            observed_by=evidence.observed_by,
            collection_complete=evidence.collection_complete,
            covered_canary_commitment_sha256s=tuple(
                activation.canary_commitment_sha256 for activation in evidence.canary_surface_activations
            ),
            covered_forbidden_flow_rules=tuple(activation.rule for activation in evidence.flow_collector_activations),
            evidence_sha256=evidence.content_sha256,
        )
        if self.envelope.coverage_attestation != expected_coverage:
            raise ValueError("monitor checkpoint coverage was not derived from its collection evidence")
        expected_envelope = run_production_cycle_monitors(
            policy=self.envelope.policy,
            cycle_plan=self.envelope.cycle_plan,
            coverage_attestation=expected_coverage,
            canary_observations=evidence.canary_observations,
            flow_observations=evidence.flow_observations,
            basis_replay_observations=evidence.basis_replay_observations,
        )
        if self.envelope != expected_envelope:
            raise ValueError("monitor checkpoint report was not derived from its collection evidence")
        expected_canaries = {canary.content_sha256 for canary in self.envelope.policy.canaries}
        observed_canaries = {observation.commitment_sha256 for observation in evidence.canary_observations}
        if observed_canaries != expected_canaries:
            raise ValueError("monitor checkpoint did not physically inspect every exact policy canary")
        expected_complete = collection_is_complete(
            policy=self.envelope.policy,
            activated_canary_sha256s=(
                activation.canary_commitment_sha256 for activation in evidence.canary_surface_activations
            ),
            activated_rules=(activation.rule for activation in evidence.flow_collector_activations),
        )
        if evidence.collection_complete is not expected_complete:
            raise ValueError("monitor collection completeness must reflect exact surface and collector activations")
        expected_referenced = {event.canary_commitment_sha256 for event in evidence.canary_reference_events}
        observed_by_commitment: dict[str, set[bool]] = {}
        for observation in evidence.canary_observations:
            observed_by_commitment.setdefault(
                observation.commitment_sha256,
                set(),
            ).add(observation.referenced)
        if any(
            states != {commitment_sha256 in expected_referenced}
            for commitment_sha256, states in observed_by_commitment.items()
        ):
            raise ValueError("canary reference state was not derived from recorded reference events")
        return self


class ProductionMonitorEffectPermit(ContentAddressedModel):
    """Durable proof that the exact cycle passed its pre-effect checkpoint."""

    schema_version: Literal["aecbench.production-monitor-effect-permit.v1"] = (
        "aecbench.production-monitor-effect-permit.v1"
    )
    runtime_manifest_sha256: str
    pre_effect_checkpoint_sha256: str
    effects_permitted: Literal[True] = True

    @field_validator(
        "runtime_manifest_sha256",
        "pre_effect_checkpoint_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class ProductionMonitorRuntimeClosure(ContentAddressedModel):
    """Incident-preserving join over mandatory pre-effect and terminal checkpoints."""

    schema_version: Literal["aecbench.production-monitor-runtime-closure.v1"] = (
        "aecbench.production-monitor-runtime-closure.v1"
    )
    runtime_manifest_sha256: str
    pre_effect: ProductionMonitorRuntimeCheckpoint
    terminal: ProductionMonitorRuntimeCheckpoint
    effect_permit: ProductionMonitorEffectPermit | None
    incident_finding_sha256s: tuple[str, ...]
    closure_eligible: bool

    @field_validator("runtime_manifest_sha256")
    @classmethod
    def validate_manifest_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("incident_finding_sha256s")
    @classmethod
    def canonicalize_incidents(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("monitor closure incident references must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_lifecycle_join(self) -> Self:
        if (
            self.pre_effect.runtime_manifest_sha256 != self.runtime_manifest_sha256
            or self.terminal.runtime_manifest_sha256 != self.runtime_manifest_sha256
            or self.pre_effect.checkpoint is not ProductionMonitorCheckpointKind.PRE_EFFECT
            or self.terminal.checkpoint is not ProductionMonitorCheckpointKind.TERMINAL
        ):
            raise ValueError("monitor closure does not join the exact mandatory checkpoints")
        if self.effect_permit is not None and (
            self.effect_permit.runtime_manifest_sha256 != self.runtime_manifest_sha256
            or self.effect_permit.pre_effect_checkpoint_sha256 != self.pre_effect.content_sha256
        ):
            raise ValueError("monitor closure effect permit does not bind its pre-effect checkpoint")
        expected_incidents = tuple(
            sorted(
                {
                    finding.content_sha256
                    for checkpoint in (self.pre_effect, self.terminal)
                    for finding in checkpoint.envelope.report.findings
                }
            )
        )
        if self.incident_finding_sha256s != expected_incidents:
            raise ValueError("monitor closure must preserve every checkpoint incident")
        expected_eligibility = (
            self.effect_permit is not None
            and self.pre_effect.envelope.report.status is CycleMonitorReportStatus.PASSED
            and self.terminal.envelope.report.status is CycleMonitorReportStatus.PASSED
        )
        if self.closure_eligible is not expected_eligibility:
            raise ValueError("monitor closure eligibility must reflect both checkpoints and the effect permit")
        return self
