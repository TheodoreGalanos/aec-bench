# ABOUTME: Verifies and records host-owned canary surfaces, flow collectors, and runtime observations.
# ABOUTME: Closes instrumentation before pre-effect and refuses identity rebinding or unverified evidence.

from __future__ import annotations

import hashlib
from pathlib import Path

from aec_bench.contracts.authority import AuthorityPrincipalKind
from aec_bench.meta_harness.monitor_repository import (
    MonitorRuntimeIntegrityError,
    _bind_monitor_claim,
    _canary_activation_claim_path,
    _canary_activation_object_path,
    _CanaryReferenceClaim,
    _CanarySurfaceActivationClaim,
    _flow_activation_claim_path,
    _flow_activation_object_path,
    _flow_claim_path,
    _flow_object_path,
    _FlowCollectorActivationClaim,
    _reference_claim_path,
    _reference_object_path,
    _RuntimeFlowClaim,
    _store_monitor_model,
)
from aec_bench.meta_harness.monitor_runtime.contracts import (
    CanaryLogicalProjectionConfiguration,
    CanaryReferenceEvent,
    CanarySurfaceActivation,
    CanarySurfaceProbeReceipt,
    FlowCollectorActivation,
    FlowCollectorProbeOutcome,
    FlowCollectorProbeReceipt,
)
from aec_bench.meta_harness.monitor_runtime.evidence import MonitorEvidenceRuntime
from aec_bench.meta_harness.monitor_runtime.surface_io import (
    canonical_json_bytes,
    canonical_model_bytes,
    load_external_model,
    read_external_file,
    read_surface_canonical_json,
)
from aec_bench.meta_harness.monitors import (
    FlowAction,
    FlowSurface,
    ForbiddenFlowRule,
    RuntimeFlowObservation,
)


class MonitorInstrumentationRuntime(MonitorEvidenceRuntime):
    """Runtime layer that admits only actively verified host instrumentation."""

    def activate_canary_surface(
        self,
        *,
        canary_id: str,
        configuration_artifact_path: Path,
        probe_receipt_path: Path,
    ) -> CanarySurfaceActivation:
        """Verify one physical canary and its guarded logical projection."""

        self._assert_instrumentation_open()
        commitment = self._canary_commitment(canary_id)
        placement = self._canary_placement(canary_id)
        config_path = self._host_evidence_path(
            configuration_artifact_path,
            label="canary surface configuration",
        )
        receipt_path = self._host_evidence_path(
            probe_receipt_path,
            label="canary surface probe receipt",
        )
        configuration = load_external_model(
            config_path,
            CanaryLogicalProjectionConfiguration,
            label="canary logical projection configuration",
        )
        configuration_sha256 = hashlib.sha256(canonical_model_bytes(configuration)).hexdigest()
        semantic_probe_path = self._host_evidence_path(
            Path(configuration.semantic_probe_evidence_path),
            label="canary semantic probe evidence",
        )
        probe = load_external_model(
            receipt_path,
            CanarySurfaceProbeReceipt,
            label="canary surface probe receipt",
        )
        observed_payload = read_surface_canonical_json(
            surface_root=Path(placement.surface.host_root),
            path=Path(placement.host_path),
            label="physical canary payload",
        )
        if not _canary_probe_matches(
            runtime_manifest_sha256=self._manifest.content_sha256,
            execution_scope_sha256=self._manifest.execution_scope_sha256,
            commitment_sha256=commitment.content_sha256,
            artifact_sha256=commitment.artifact_sha256,
            placement_host_path=placement.host_path,
            placement_projection_key=placement.logical_projection_key,
            placement_surface_sha256=placement.surface.content_sha256,
            configuration=configuration,
            configuration_sha256=configuration_sha256,
            semantic_probe_sha256=hashlib.sha256(
                read_external_file(
                    semantic_probe_path,
                    label="canary semantic probe evidence",
                )
            ).hexdigest(),
            observed_artifact_sha256=hashlib.sha256(canonical_json_bytes(observed_payload)[:-1]).hexdigest(),
            probe=probe,
        ):
            raise MonitorRuntimeIntegrityError(
                "canary surface probe does not verify the exact host placement and logical projection"
            )
        activation = CanarySurfaceActivation(
            runtime_manifest_sha256=self._manifest.content_sha256,
            execution_scope_sha256=self._manifest.execution_scope_sha256,
            canary_commitment_sha256=commitment.content_sha256,
            configuration_artifact_path=str(config_path),
            configuration_artifact_sha256=configuration_sha256,
            probe_receipt_path=str(receipt_path),
            probe_receipt=probe,
        )
        _store_monitor_model(
            self._repository,
            _canary_activation_object_path(
                self._root,
                self._manifest,
                activation.content_sha256,
            ),
            activation,
            CanarySurfaceActivation,
            label="canary surface activation",
        )
        claim = _CanarySurfaceActivationClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            canary_commitment_sha256=commitment.content_sha256,
            activation_sha256=activation.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            _canary_activation_claim_path(
                self._root,
                self._manifest,
                commitment.content_sha256,
            ),
            claim,
            _CanarySurfaceActivationClaim,
            label="canary surface activation",
        )
        return self._load_canary_surface_activation(commitment.content_sha256)

    def activate_flow_collector(
        self,
        *,
        rule: ForbiddenFlowRule,
        configuration_artifact_path: Path,
        probe_evidence_path: Path,
        probe_receipt_path: Path,
    ) -> FlowCollectorActivation:
        """Verify and persist an active collector probe for one exact forbidden-flow rule."""

        self._assert_instrumentation_open()
        selected_rule = ForbiddenFlowRule.model_validate(rule.model_dump(mode="python"))
        if selected_rule not in self._manifest.policy.forbidden_flow_rules:
            raise MonitorRuntimeIntegrityError("flow collector activation names a rule outside the standing policy")
        config_path = self._host_evidence_path(
            configuration_artifact_path,
            label="flow collector configuration",
        )
        evidence_path = self._host_evidence_path(
            probe_evidence_path,
            label="flow collector probe evidence",
        )
        receipt_path = self._host_evidence_path(
            probe_receipt_path,
            label="flow collector probe receipt",
        )
        configuration_sha256 = hashlib.sha256(
            read_external_file(
                config_path,
                label="flow collector configuration",
            )
        ).hexdigest()
        probe_evidence_sha256 = hashlib.sha256(
            read_external_file(
                evidence_path,
                label="flow collector probe evidence",
            )
        ).hexdigest()
        probe = load_external_model(
            receipt_path,
            FlowCollectorProbeReceipt,
            label="flow collector probe receipt",
        )
        if not _flow_probe_matches(
            probe=probe,
            runtime_manifest_sha256=self._manifest.content_sha256,
            execution_scope_sha256=self._manifest.execution_scope_sha256,
            rule=selected_rule,
            configuration_sha256=configuration_sha256,
            evidence_sha256=probe_evidence_sha256,
        ):
            raise MonitorRuntimeIntegrityError(
                "flow collector probe does not verify the exact configured rule instrumentation"
            )
        activation = FlowCollectorActivation(
            runtime_manifest_sha256=self._manifest.content_sha256,
            execution_scope_sha256=self._manifest.execution_scope_sha256,
            rule=selected_rule,
            configuration_artifact_path=str(config_path),
            configuration_artifact_sha256=configuration_sha256,
            probe_evidence_path=str(evidence_path),
            probe_evidence_sha256=probe_evidence_sha256,
            probe_receipt_path=str(receipt_path),
            probe_receipt=probe,
        )
        _store_monitor_model(
            self._repository,
            _flow_activation_object_path(
                self._root,
                self._manifest,
                activation.content_sha256,
            ),
            activation,
            FlowCollectorActivation,
            label="flow collector activation",
        )
        claim = _FlowCollectorActivationClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            rule=selected_rule,
            activation_sha256=activation.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            _flow_activation_claim_path(
                self._root,
                self._manifest,
                selected_rule,
            ),
            claim,
            _FlowCollectorActivationClaim,
            label="flow collector rule",
        )
        return self._load_flow_collector_activation(selected_rule)

    def record_flow(
        self,
        *,
        flow_id: str,
        source_principal_kind: AuthorityPrincipalKind,
        target_surface: FlowSurface,
        action: FlowAction,
        evidence_sha256: str,
    ) -> RuntimeFlowObservation:
        """Durably record one flow before terminal closure, with exclusive flow_id use."""

        self._assert_terminal_absent()
        observation = RuntimeFlowObservation(
            flow_id=flow_id,
            source_principal_kind=source_principal_kind,
            target_surface=target_surface,
            action=action,
            evidence_sha256=evidence_sha256,
        )
        _store_monitor_model(
            self._repository,
            _flow_object_path(
                self._root,
                self._manifest,
                observation.content_sha256,
            ),
            observation,
            RuntimeFlowObservation,
            label="runtime flow observation",
        )
        claim = _RuntimeFlowClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            flow_id=observation.flow_id,
            flow_observation_sha256=observation.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            _flow_claim_path(
                self._root,
                self._manifest,
                observation.flow_id,
            ),
            claim,
            _RuntimeFlowClaim,
            label="runtime flow_id",
        )
        return self._load_flow_claim(observation.flow_id)

    def record_or_replay_flow(
        self,
        *,
        flow_id: str,
        source_principal_kind: AuthorityPrincipalKind,
        target_surface: FlowSurface,
        action: FlowAction,
        evidence_sha256: str,
    ) -> RuntimeFlowObservation:
        """Record one flow or replay its exact existing logical claim."""

        expected = RuntimeFlowObservation(
            flow_id=flow_id,
            source_principal_kind=source_principal_kind,
            target_surface=target_surface,
            action=action,
            evidence_sha256=evidence_sha256,
        )
        claim_path = _flow_claim_path(
            self._root,
            self._manifest,
            flow_id,
        )
        if not self._claim_exists(claim_path):
            return self.record_flow(
                flow_id=flow_id,
                source_principal_kind=source_principal_kind,
                target_surface=target_surface,
                action=action,
                evidence_sha256=evidence_sha256,
            )
        replayed = self._load_flow_claim(flow_id)
        if replayed != expected:
            raise MonitorRuntimeIntegrityError(
                "runtime flow replay differs from its existing claim",
            )
        return replayed

    def record_canary_reference(
        self,
        *,
        reference_id: str,
        canary_id: str,
        evidence_sha256: str,
    ) -> CanaryReferenceEvent:
        """Durably record one canary use before terminal closure."""

        self._assert_terminal_absent()
        commitment = self._canary_commitment(canary_id)
        event = CanaryReferenceEvent(
            reference_id=reference_id,
            canary_commitment_sha256=commitment.content_sha256,
            evidence_sha256=evidence_sha256,
        )
        _store_monitor_model(
            self._repository,
            _reference_object_path(
                self._root,
                self._manifest,
                event.content_sha256,
            ),
            event,
            CanaryReferenceEvent,
            label="canary reference event",
        )
        claim = _CanaryReferenceClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            reference_id=event.reference_id,
            reference_event_sha256=event.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            _reference_claim_path(
                self._root,
                self._manifest,
                event.reference_id,
            ),
            claim,
            _CanaryReferenceClaim,
            label="canary reference_id",
        )
        return self._load_reference_claim(event.reference_id)

    def record_or_replay_canary_reference(
        self,
        *,
        reference_id: str,
        canary_id: str,
        evidence_sha256: str,
    ) -> CanaryReferenceEvent:
        """Record one canary reference or replay its exact existing claim."""

        commitment = self._canary_commitment(canary_id)
        expected = CanaryReferenceEvent(
            reference_id=reference_id,
            canary_commitment_sha256=commitment.content_sha256,
            evidence_sha256=evidence_sha256,
        )
        claim_path = _reference_claim_path(
            self._root,
            self._manifest,
            reference_id,
        )
        if not self._claim_exists(claim_path):
            return self.record_canary_reference(
                reference_id=reference_id,
                canary_id=canary_id,
                evidence_sha256=evidence_sha256,
            )
        replayed = self._load_reference_claim(reference_id)
        if replayed != expected:
            raise MonitorRuntimeIntegrityError(
                "canary reference replay differs from its existing claim",
            )
        return replayed


def _canary_probe_matches(
    *,
    runtime_manifest_sha256: str,
    execution_scope_sha256: str,
    commitment_sha256: str,
    artifact_sha256: str,
    placement_host_path: str,
    placement_projection_key: str,
    placement_surface_sha256: str,
    configuration: CanaryLogicalProjectionConfiguration,
    configuration_sha256: str,
    semantic_probe_sha256: str,
    observed_artifact_sha256: str,
    probe: CanarySurfaceProbeReceipt,
) -> bool:
    return (
        probe.runtime_manifest_sha256 == runtime_manifest_sha256
        and probe.execution_scope_sha256 == execution_scope_sha256
        and probe.canary_commitment_sha256 == commitment_sha256
        and probe.host_path == placement_host_path
        and probe.logical_projection_key == placement_projection_key
        and probe.projection_configuration_sha256 == configuration_sha256
        and probe.observed_artifact_sha256 == artifact_sha256
        and configuration.runtime_manifest_sha256 == runtime_manifest_sha256
        and configuration.execution_scope_sha256 == execution_scope_sha256
        and configuration.canary_commitment_sha256 == commitment_sha256
        and configuration.surface_sha256 == placement_surface_sha256
        and configuration.host_path == placement_host_path
        and configuration.logical_projection_key == placement_projection_key
        and semantic_probe_sha256 == configuration.semantic_probe_evidence_sha256
        and observed_artifact_sha256 == probe.observed_artifact_sha256
    )


def _flow_probe_matches(
    *,
    probe: FlowCollectorProbeReceipt,
    runtime_manifest_sha256: str,
    execution_scope_sha256: str,
    rule: ForbiddenFlowRule,
    configuration_sha256: str,
    evidence_sha256: str,
) -> bool:
    return (
        probe.runtime_manifest_sha256 == runtime_manifest_sha256
        and probe.execution_scope_sha256 == execution_scope_sha256
        and probe.rule == rule
        and probe.configuration_artifact_sha256 == configuration_sha256
        and probe.probe_evidence_sha256 == evidence_sha256
        and probe.outcome is FlowCollectorProbeOutcome.CAPTURED_OR_BLOCKED
    )
