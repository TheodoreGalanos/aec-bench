# ABOUTME: Replays and revalidates durable monitor observations, references, and instrumentation evidence.
# ABOUTME: Refuses stale, rebound, non-canonical, or changed host evidence at every checkpoint and permit load.

from __future__ import annotations

import hashlib
from pathlib import Path

from aec_bench.meta_harness.monitor_repository import (
    MonitorRuntimeConfinementError,
    MonitorRuntimeIntegrityError,
    _canary_activation_claim_path,
    _canary_activation_object_path,
    _CanaryReferenceClaim,
    _CanarySurfaceActivationClaim,
    _cycle_root,
    _flow_activation_claim_path,
    _flow_activation_object_path,
    _flow_claim_path,
    _flow_object_path,
    _flow_rule_identity,
    _FlowCollectorActivationClaim,
    _load_monitor_model,
    _monitor_claim_files,
    _reference_claim_path,
    _reference_object_path,
    _RuntimeFlowClaim,
)
from aec_bench.meta_harness.monitor_runtime.contracts import (
    CanaryLogicalProjectionConfiguration,
    CanaryReferenceEvent,
    CanarySurfaceActivation,
    CanarySurfaceProbeReceipt,
    FlowCollectorActivation,
    FlowCollectorProbeReceipt,
)
from aec_bench.meta_harness.monitor_runtime.state import MonitorRuntimeState
from aec_bench.meta_harness.monitor_runtime.surface_io import (
    canonical_model_bytes,
    guard_surface_path,
    load_external_model,
    motif_effective_state,
    read_external_file,
    read_surface_canonical_json,
)
from aec_bench.meta_harness.monitors import (
    CanaryKind,
    CanaryObservation,
    ForbiddenFlowRule,
    RuntimeFlowObservation,
)


class MonitorEvidenceRuntime(MonitorRuntimeState):
    """Runtime layer that replays exact durable collection evidence."""

    def _load_flow_claim(self, flow_id: str) -> RuntimeFlowObservation:
        claim = _load_monitor_model(
            self._repository,
            _flow_claim_path(self._root, self._manifest, flow_id),
            _RuntimeFlowClaim,
            label="runtime flow claim",
        )
        if claim.runtime_manifest_sha256 != self._manifest.content_sha256 or claim.flow_id != flow_id:
            raise MonitorRuntimeIntegrityError("runtime flow claim differs from its lookup identity")
        observation = _load_monitor_model(
            self._repository,
            _flow_object_path(
                self._root,
                self._manifest,
                claim.flow_observation_sha256,
            ),
            RuntimeFlowObservation,
            label="runtime flow observation",
        )
        if observation.content_sha256 != claim.flow_observation_sha256 or observation.flow_id != claim.flow_id:
            raise MonitorRuntimeIntegrityError("runtime flow observation differs from its claim")
        return observation

    def _load_flow_observations(self) -> tuple[RuntimeFlowObservation, ...]:
        claims_root = (
            _cycle_root(
                self._root,
                self._manifest,
            )
            / "flows"
            / "claims"
        )
        return tuple(
            sorted(
                (
                    self._load_flow_claim(
                        _load_monitor_model(
                            self._repository,
                            claim_path,
                            _RuntimeFlowClaim,
                            label="runtime flow claim",
                        ).flow_id
                    )
                    for claim_path in _monitor_claim_files(
                        self._repository,
                        claims_root,
                    )
                ),
                key=lambda item: item.flow_id,
            )
        )

    def _load_reference_claim(
        self,
        reference_id: str,
    ) -> CanaryReferenceEvent:
        claim = _load_monitor_model(
            self._repository,
            _reference_claim_path(
                self._root,
                self._manifest,
                reference_id,
            ),
            _CanaryReferenceClaim,
            label="canary reference claim",
        )
        if claim.runtime_manifest_sha256 != self._manifest.content_sha256 or claim.reference_id != reference_id:
            raise MonitorRuntimeIntegrityError("canary reference claim differs from its lookup identity")
        event = _load_monitor_model(
            self._repository,
            _reference_object_path(
                self._root,
                self._manifest,
                claim.reference_event_sha256,
            ),
            CanaryReferenceEvent,
            label="canary reference event",
        )
        if event.content_sha256 != claim.reference_event_sha256 or event.reference_id != claim.reference_id:
            raise MonitorRuntimeIntegrityError("canary reference event differs from its claim")
        expected_commitments = {canary.content_sha256 for canary in self._manifest.policy.canaries}
        if event.canary_commitment_sha256 not in expected_commitments:
            raise MonitorRuntimeIntegrityError("canary reference event names an unknown canary commitment")
        return event

    def _load_reference_events(self) -> tuple[CanaryReferenceEvent, ...]:
        claims_root = (
            _cycle_root(
                self._root,
                self._manifest,
            )
            / "references"
            / "claims"
        )
        return tuple(
            sorted(
                (
                    self._load_reference_claim(
                        _load_monitor_model(
                            self._repository,
                            claim_path,
                            _CanaryReferenceClaim,
                            label="canary reference claim",
                        ).reference_id
                    )
                    for claim_path in _monitor_claim_files(
                        self._repository,
                        claims_root,
                    )
                ),
                key=lambda item: item.reference_id,
            )
        )

    def _load_canary_surface_activation(
        self,
        canary_commitment_sha256: str,
    ) -> CanarySurfaceActivation:
        claim = _load_monitor_model(
            self._repository,
            _canary_activation_claim_path(
                self._root,
                self._manifest,
                canary_commitment_sha256,
            ),
            _CanarySurfaceActivationClaim,
            label="canary surface activation claim",
        )
        if (
            claim.runtime_manifest_sha256 != self._manifest.content_sha256
            or claim.canary_commitment_sha256 != canary_commitment_sha256
        ):
            raise MonitorRuntimeIntegrityError("canary surface activation claim differs from its lookup identity")
        activation = _load_monitor_model(
            self._repository,
            _canary_activation_object_path(
                self._root,
                self._manifest,
                claim.activation_sha256,
            ),
            CanarySurfaceActivation,
            label="canary surface activation",
        )
        if (
            activation.content_sha256 != claim.activation_sha256
            or activation.runtime_manifest_sha256 != self._manifest.content_sha256
            or activation.execution_scope_sha256 != self._manifest.execution_scope_sha256
            or activation.canary_commitment_sha256 != canary_commitment_sha256
        ):
            raise MonitorRuntimeIntegrityError("canary surface activation differs from its exact claim")
        self._revalidate_canary_activation_evidence(activation)
        return activation

    def _revalidate_canary_activation_evidence(
        self,
        activation: CanarySurfaceActivation,
    ) -> None:
        config_path = self._host_evidence_path(
            Path(activation.configuration_artifact_path),
            label="canary surface configuration",
        )
        receipt_path = self._host_evidence_path(
            Path(activation.probe_receipt_path),
            label="canary surface probe receipt",
        )
        configuration = load_external_model(
            config_path,
            CanaryLogicalProjectionConfiguration,
            label="canary logical projection configuration",
        )
        semantic_probe_path = self._host_evidence_path(
            Path(configuration.semantic_probe_evidence_path),
            label="canary semantic probe evidence",
        )
        if (
            hashlib.sha256(canonical_model_bytes(configuration)).hexdigest() != activation.configuration_artifact_sha256
            or hashlib.sha256(
                read_external_file(
                    semantic_probe_path,
                    label="canary semantic probe evidence",
                )
            ).hexdigest()
            != configuration.semantic_probe_evidence_sha256
            or load_external_model(
                receipt_path,
                CanarySurfaceProbeReceipt,
                label="canary surface probe receipt",
            )
            != activation.probe_receipt
        ):
            raise MonitorRuntimeIntegrityError("canary surface activation evidence changed after verification")

    def _load_canary_surface_activations(
        self,
    ) -> tuple[CanarySurfaceActivation, ...]:
        claims_root = _cycle_root(self._root, self._manifest) / "instrumentation" / "canary-surfaces" / "claims"
        return tuple(
            sorted(
                (
                    self._load_canary_surface_activation(
                        _load_monitor_model(
                            self._repository,
                            claim_path,
                            _CanarySurfaceActivationClaim,
                            label="canary surface activation claim",
                        ).canary_commitment_sha256
                    )
                    for claim_path in _monitor_claim_files(
                        self._repository,
                        claims_root,
                    )
                ),
                key=lambda item: item.canary_commitment_sha256,
            )
        )

    def _load_flow_collector_activation(
        self,
        rule: ForbiddenFlowRule,
    ) -> FlowCollectorActivation:
        claim = _load_monitor_model(
            self._repository,
            _flow_activation_claim_path(
                self._root,
                self._manifest,
                rule,
            ),
            _FlowCollectorActivationClaim,
            label="flow collector activation claim",
        )
        if claim.runtime_manifest_sha256 != self._manifest.content_sha256 or claim.rule != rule:
            raise MonitorRuntimeIntegrityError("flow collector activation claim differs from its lookup rule")
        activation = _load_monitor_model(
            self._repository,
            _flow_activation_object_path(
                self._root,
                self._manifest,
                claim.activation_sha256,
            ),
            FlowCollectorActivation,
            label="flow collector activation",
        )
        if (
            activation.content_sha256 != claim.activation_sha256
            or activation.runtime_manifest_sha256 != self._manifest.content_sha256
            or activation.execution_scope_sha256 != self._manifest.execution_scope_sha256
            or activation.rule != rule
        ):
            raise MonitorRuntimeIntegrityError("flow collector activation differs from its exact claim")
        self._revalidate_flow_activation_evidence(activation)
        return activation

    def _revalidate_flow_activation_evidence(
        self,
        activation: FlowCollectorActivation,
    ) -> None:
        config_path = self._host_evidence_path(
            Path(activation.configuration_artifact_path),
            label="flow collector configuration",
        )
        evidence_path = self._host_evidence_path(
            Path(activation.probe_evidence_path),
            label="flow collector probe evidence",
        )
        receipt_path = self._host_evidence_path(
            Path(activation.probe_receipt_path),
            label="flow collector probe receipt",
        )
        if (
            hashlib.sha256(
                read_external_file(
                    config_path,
                    label="flow collector configuration",
                )
            ).hexdigest()
            != activation.configuration_artifact_sha256
            or hashlib.sha256(
                read_external_file(
                    evidence_path,
                    label="flow collector probe evidence",
                )
            ).hexdigest()
            != activation.probe_evidence_sha256
            or load_external_model(
                receipt_path,
                FlowCollectorProbeReceipt,
                label="flow collector probe receipt",
            )
            != activation.probe_receipt
        ):
            raise MonitorRuntimeIntegrityError("flow collector activation evidence changed after verification")

    def _load_flow_collector_activations(
        self,
    ) -> tuple[FlowCollectorActivation, ...]:
        claims_root = _cycle_root(self._root, self._manifest) / "instrumentation" / "flow-collectors" / "claims"
        return tuple(
            sorted(
                (
                    self._load_flow_collector_activation(
                        _load_monitor_model(
                            self._repository,
                            claim_path,
                            _FlowCollectorActivationClaim,
                            label="flow collector activation claim",
                        ).rule
                    )
                    for claim_path in _monitor_claim_files(
                        self._repository,
                        claims_root,
                    )
                ),
                key=lambda item: _flow_rule_identity(item.rule),
            )
        )

    def _collect_canary_observations(
        self,
        *,
        reference_events: tuple[CanaryReferenceEvent, ...],
    ) -> tuple[CanaryObservation, ...]:
        referenced = {event.canary_commitment_sha256 for event in reference_events}
        observations: list[CanaryObservation] = []
        for placement in self._manifest.canary_placements:
            commitment = self._canary_commitment(placement.canary_id)
            surface_root = Path(placement.surface.host_root)
            placement_root = Path(placement.host_path).parent
            guard_surface_path(surface_root, placement_root)
            if not placement_root.exists():
                observations.append(
                    CanaryObservation.observe(
                        commitment=commitment,
                        observed_payload=None,
                        occurrence_count=0,
                        referenced=(commitment.content_sha256 in referenced),
                    )
                )
                continue
            if placement_root.is_symlink() or not placement_root.is_dir():
                raise MonitorRuntimeConfinementError("canary placement root must be a regular non-symlink directory")
            paths = tuple(sorted(placement_root.iterdir(), key=lambda path: path.name))
            if not paths:
                observations.append(
                    CanaryObservation.observe(
                        commitment=commitment,
                        observed_payload=None,
                        occurrence_count=0,
                        referenced=(commitment.content_sha256 in referenced),
                    )
                )
                continue
            for path in paths:
                payload = read_surface_canonical_json(
                    surface_root=surface_root,
                    path=path,
                    label="physical canary payload",
                )
                observations.append(
                    CanaryObservation.observe(
                        commitment=commitment,
                        observed_payload=payload,
                        occurrence_count=1,
                        referenced=(commitment.content_sha256 in referenced),
                        observed_effective_state=(
                            motif_effective_state(payload) if commitment.kind is CanaryKind.MOTIF else None
                        ),
                    )
                )
        return tuple(observations)
