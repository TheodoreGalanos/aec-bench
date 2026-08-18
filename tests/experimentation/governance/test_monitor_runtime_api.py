# ABOUTME: Pins the public monitor-runtime package surface and historical content-addressed contracts.
# ABOUTME: Protects exact serialization while the runtime is decomposed by lifecycle responsibility.

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

import aec_bench.experimentation.governance.monitor_runtime as monitor_runtime_api
from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.experimentation.governance.monitor_runtime import (
    CanaryLogicalProjectionConfiguration,
    CanaryReferenceEvent,
    CanarySurfaceActivation,
    CanarySurfaceProbeReceipt,
    FlowCollectorActivation,
    FlowCollectorKind,
    FlowCollectorProbeOutcome,
    FlowCollectorProbeReceipt,
    MonitorCanaryPlacement,
    MonitorCanarySurface,
    MonitorRuntimeCollectionEvidence,
    ProductionMonitorCheckpointKind,
    ProductionMonitorEffectPermit,
    ProductionMonitorRuntimeCheckpoint,
    ProductionMonitorRuntimeClosure,
    ProductionMonitorRuntimeManifest,
)
from aec_bench.experimentation.governance.standing_monitors import (
    CanaryCommitment,
    CanaryKind,
    CanaryObservation,
    CycleMonitorPlan,
    MonitorCoverageAttestation,
    StandingMonitorPolicy,
    default_forbidden_flow_rules,
    run_production_cycle_monitors,
)
from tests.support.evaluation_regimes import fake_regime_ref

_PUBLIC_NAMES = {
    "CanaryLogicalProjectionConfiguration",
    "CanaryReferenceEvent",
    "CanarySurfaceActivation",
    "CanarySurfaceProbeReceipt",
    "FlowCollectorActivation",
    "FlowCollectorKind",
    "FlowCollectorProbeOutcome",
    "FlowCollectorProbeReceipt",
    "MonitorCanaryPlacement",
    "MonitorCanarySurface",
    "MonitorRuntimeCollectionEvidence",
    "MonitorRuntimeCollisionError",
    "MonitorRuntimeConfinementError",
    "MonitorRuntimeError",
    "MonitorRuntimeIntegrityError",
    "MonitorRuntimePreEffectError",
    "ProductionMonitorCheckpointKind",
    "ProductionMonitorEffectPermit",
    "ProductionMonitorRuntime",
    "ProductionMonitorRuntimeCheckpoint",
    "ProductionMonitorRuntimeClosure",
    "ProductionMonitorRuntimeManifest",
}


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _canonical_bytes(model: LegacyContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _historical_contracts() -> Mapping[str, LegacyContentAddressedModel]:
    observer = AuthorityPrincipal(
        principal_id="host.production-monitor-runtime",
        kind=AuthorityPrincipalKind.HOST_RUNTIME,
    )
    payloads = {
        "canary.motif.contract": {
            "effective_state": "revoked",
            "motif_subject_sha256": _sha("motif-subject"),
        },
        "canary.ordinary-ledger.contract": {
            "stage": "authority_event",
            "status": "granted",
        },
    }
    commitments = (
        CanaryCommitment.create(
            canary_id="canary.motif.contract",
            kind=CanaryKind.MOTIF,
            artifact_payload=payloads["canary.motif.contract"],
            expected_effective_state="revoked",
        ),
        CanaryCommitment.create(
            canary_id="canary.ordinary-ledger.contract",
            kind=CanaryKind.ORDINARY_LEDGER,
            artifact_payload=payloads["canary.ordinary-ledger.contract"],
        ),
    )
    policy = StandingMonitorPolicy(
        monitor_id="monitor.contract-characterization",
        version="2.0.0",
        canaries=commitments,
        forbidden_flow_rules=default_forbidden_flow_rules(),
        report_validity_cycles=1,
    )
    cycle = CycleMonitorPlan(
        cycle_id="cycle.contract-characterization",
        cycle_index=12,
        evaluation_regime=fake_regime_ref(),
        standing_policy_sha256=policy.content_sha256,
        assurance_snapshot_sha256=_sha("assurance-snapshot"),
    )
    surfaces = {
        CanaryKind.MOTIF: MonitorCanarySurface(
            surface_id="surface.motif-library",
            kind=CanaryKind.MOTIF,
            host_root="/private/tmp/aec-bench-monitor-contract/motif",
            logical_projection_namespace="motif-selector",
        ),
        CanaryKind.ORDINARY_LEDGER: MonitorCanarySurface(
            surface_id="surface.ordinary-ledger",
            kind=CanaryKind.ORDINARY_LEDGER,
            host_root="/private/tmp/aec-bench-monitor-contract/ordinary-ledger",
            logical_projection_namespace="ordinary-ledger-resolver",
        ),
    }
    placements = tuple(
        MonitorCanaryPlacement(
            canary_id=commitment.canary_id,
            commitment_sha256=commitment.content_sha256,
            kind=commitment.kind,
            surface=surfaces[commitment.kind],
            host_path=(
                f"{surfaces[commitment.kind].host_root}/.aecbench-monitor-canaries/"
                f"{commitment.kind.value}/{commitment.content_sha256}/canary.json"
            ),
            logical_projection_key=(
                f"{surfaces[commitment.kind].logical_projection_namespace}:"
                f"{commitment.kind.value}:{commitment.content_sha256}"
            ),
        )
        for commitment in commitments
    )
    manifest = ProductionMonitorRuntimeManifest(
        execution_scope_sha256=_sha("execution-scope"),
        policy=policy,
        cycle_plan=cycle,
        observed_by=observer,
        canary_placements=placements,
    )

    configurations = tuple(
        CanaryLogicalProjectionConfiguration(
            runtime_manifest_sha256=manifest.content_sha256,
            execution_scope_sha256=manifest.execution_scope_sha256,
            canary_commitment_sha256=placement.commitment_sha256,
            surface_sha256=placement.surface.content_sha256,
            host_path=placement.host_path,
            logical_projection_key=placement.logical_projection_key,
            guard_configuration_sha256=_sha(f"guard:{placement.canary_id}"),
            semantic_probe_evidence_path=(
                f"/private/tmp/aec-bench-monitor-contract/evidence/{placement.commitment_sha256}/semantic.json"
            ),
            semantic_probe_evidence_sha256=_sha(f"semantic:{placement.canary_id}"),
        )
        for placement in placements
    )
    canary_probes = tuple(
        CanarySurfaceProbeReceipt(
            probe_id=f"probe.{placement.canary_id}",
            runtime_manifest_sha256=manifest.content_sha256,
            execution_scope_sha256=manifest.execution_scope_sha256,
            canary_commitment_sha256=placement.commitment_sha256,
            host_path=placement.host_path,
            logical_projection_key=placement.logical_projection_key,
            projection_configuration_sha256=_sha(f"configuration:{placement.canary_id}"),
            observed_artifact_sha256=next(
                commitment.artifact_sha256
                for commitment in commitments
                if commitment.content_sha256 == placement.commitment_sha256
            ),
            observed_by=observer,
            host_placement_confirmed=True,
        )
        for placement in placements
    )
    canary_activations = tuple(
        CanarySurfaceActivation(
            runtime_manifest_sha256=manifest.content_sha256,
            execution_scope_sha256=manifest.execution_scope_sha256,
            canary_commitment_sha256=placement.commitment_sha256,
            configuration_artifact_path=(
                f"/private/tmp/aec-bench-monitor-contract/evidence/{placement.commitment_sha256}/configuration.json"
            ),
            configuration_artifact_sha256=probe.projection_configuration_sha256,
            probe_receipt_path=(
                f"/private/tmp/aec-bench-monitor-contract/evidence/{placement.commitment_sha256}/probe.json"
            ),
            probe_receipt=probe,
        )
        for placement, probe in zip(placements, canary_probes, strict=True)
    )
    flow_probes = tuple(
        FlowCollectorProbeReceipt(
            probe_id=f"probe.flow.{index:02d}",
            runtime_manifest_sha256=manifest.content_sha256,
            execution_scope_sha256=manifest.execution_scope_sha256,
            rule=rule,
            collector_kind=FlowCollectorKind.AUDIT_OR_DENIAL_PROBE,
            configuration_artifact_sha256=_sha(f"flow-configuration:{index}"),
            probe_evidence_sha256=_sha(f"flow-evidence:{index}"),
            outcome=FlowCollectorProbeOutcome.CAPTURED_OR_BLOCKED,
            observed_by=observer,
            collector_armed=True,
        )
        for index, rule in enumerate(policy.forbidden_flow_rules)
    )
    flow_activations = tuple(
        FlowCollectorActivation(
            runtime_manifest_sha256=manifest.content_sha256,
            execution_scope_sha256=manifest.execution_scope_sha256,
            rule=probe.rule,
            configuration_artifact_path=(
                f"/private/tmp/aec-bench-monitor-contract/evidence/flow/{index:02d}/configuration.json"
            ),
            configuration_artifact_sha256=probe.configuration_artifact_sha256,
            probe_evidence_path=(
                f"/private/tmp/aec-bench-monitor-contract/evidence/flow/{index:02d}/probe-evidence.json"
            ),
            probe_evidence_sha256=probe.probe_evidence_sha256,
            probe_receipt_path=(f"/private/tmp/aec-bench-monitor-contract/evidence/flow/{index:02d}/probe.json"),
            probe_receipt=probe,
        )
        for index, probe in enumerate(flow_probes)
    )
    observations = tuple(
        CanaryObservation.observe(
            commitment=commitment,
            observed_payload=payloads[commitment.canary_id],
            occurrence_count=1,
            observed_effective_state=(
                commitment.expected_effective_state if commitment.kind is CanaryKind.MOTIF else None
            ),
        )
        for commitment in commitments
    )
    reference = CanaryReferenceEvent(
        reference_id="reference.contract-characterization",
        canary_commitment_sha256=commitments[0].content_sha256,
        evidence_sha256=_sha("reference-evidence"),
    )

    def checkpoint(
        kind: ProductionMonitorCheckpointKind,
        wall_time_seconds: float,
    ) -> ProductionMonitorRuntimeCheckpoint:
        evidence = MonitorRuntimeCollectionEvidence(
            runtime_manifest_sha256=manifest.content_sha256,
            checkpoint=kind,
            observed_by=observer,
            canary_observations=observations,
            flow_observations=(),
            basis_replay_observations=(),
            canary_reference_events=(),
            canary_surface_activations=canary_activations,
            flow_collector_activations=flow_activations,
            collection_complete=True,
        )
        coverage = MonitorCoverageAttestation(
            cycle_monitor_plan_sha256=cycle.content_sha256,
            observed_by=observer,
            collection_complete=True,
            covered_canary_commitment_sha256s=tuple(
                activation.canary_commitment_sha256 for activation in canary_activations
            ),
            covered_forbidden_flow_rules=tuple(activation.rule for activation in flow_activations),
            covered_basis_replay_requirement_sha256s=(),
            evidence_sha256=evidence.content_sha256,
        )
        envelope = run_production_cycle_monitors(
            policy=policy,
            cycle_plan=cycle,
            coverage_attestation=coverage,
            canary_observations=evidence.canary_observations,
            flow_observations=evidence.flow_observations,
            basis_replay_observations=evidence.basis_replay_observations,
        )
        return ProductionMonitorRuntimeCheckpoint(
            runtime_manifest_sha256=manifest.content_sha256,
            checkpoint=kind,
            collection_evidence=evidence,
            envelope=envelope,
            wall_time_seconds=wall_time_seconds,
        )

    pre_effect = checkpoint(ProductionMonitorCheckpointKind.PRE_EFFECT, 0.25)
    terminal = checkpoint(ProductionMonitorCheckpointKind.TERMINAL, 0.5)
    permit = ProductionMonitorEffectPermit(
        runtime_manifest_sha256=manifest.content_sha256,
        pre_effect_checkpoint_sha256=pre_effect.content_sha256,
    )
    closure = ProductionMonitorRuntimeClosure(
        runtime_manifest_sha256=manifest.content_sha256,
        pre_effect=pre_effect,
        terminal=terminal,
        effect_permit=permit,
        incident_finding_sha256s=(),
        closure_eligible=True,
    )
    return {
        "surface": surfaces[CanaryKind.MOTIF],
        "placement": placements[0],
        "manifest": manifest,
        "configuration": configurations[0],
        "canary_probe": canary_probes[0],
        "flow_probe": flow_probes[0],
        "canary_activation": canary_activations[0],
        "flow_activation": flow_activations[0],
        "reference": reference,
        "pre_effect_evidence": pre_effect.collection_evidence,
        "pre_effect_checkpoint": pre_effect,
        "effect_permit": permit,
        "terminal_checkpoint": terminal,
        "closure": closure,
    }


def test_public_import_path_is_a_stable_package_surface() -> None:
    assert set(monitor_runtime_api.__all__) == _PUBLIC_NAMES
    assert all(getattr(monitor_runtime_api, name) is not None for name in _PUBLIC_NAMES)


def test_legacy_monitor_contract_hashes_and_bytes_are_stable() -> None:
    contracts = _historical_contracts()

    assert {name: model.content_sha256 for name, model in contracts.items()} == {
        "canary_activation": "f26d8db8ea3b1ee1a853d41d94b4432390102d8df567b6c3831ab32a0d15ec74",
        "canary_probe": "481f7d59b7170daccb6bc14289868b0909c05735c18081f142b427579327987d",
        "closure": "7dbcb5ec0834eab05006300dc0e3f15df833b34e8392db6334312a3e31883436",
        "configuration": "26a1fd490f1f16eb2670af066535b278323a525675499b8a5d88432db0b7d071",
        "effect_permit": "2605e347135110139b1702fec16adff0ec47b11a748cdf10e8630e9730556a59",
        "flow_activation": "7ff919e8036448057971faf639efd66357ce1b6060fee2dc2bb3cb39ab2e1a82",
        "flow_probe": "8962792f39f73f90e1f8dce9dfd4e70f480df0960f3e32783b48e8de52424d7d",
        "manifest": "ccdfee88a16a5d3a70a3c06b5571541467d2ed6aa29044b1efcc18b5b24c6cde",
        "placement": "803522f9090a5a11c07f12d0017160128415234ca92d2771bd8528a5dfa17673",
        "pre_effect_checkpoint": "cd30227034067743826a637e4e72459c30e921d3bade5a90c8cfd44072179402",
        "pre_effect_evidence": "a370daea778f11a792bd48f941303625aa8ca402f58e8d76e9d49d4aaac69b6e",
        "reference": "4a90fe58e0fa69c75d533e72e4affd1a9e07096772f4ff97e919e2a63625663d",
        "surface": "15b71aa7294a6dbfe562592bd2c1885a82b8a29c3b4a8dc3e62cc7b6ea6da53e",
        "terminal_checkpoint": "ca672d2ddef99d1ae01bab88785149b950a7be87ab0091463277de2203847cb3",
    }
    for model in contracts.values():
        encoded = _canonical_bytes(model)
        assert type(model).model_validate_json(encoded) == model
        assert _canonical_bytes(type(model).model_validate_json(encoded)) == encoded
