# ABOUTME: Exercises the durable host-owned production monitor runtime over real filesystem evidence.
# ABOUTME: Proves pre-effect gating, terminal incident preservation, replay, confinement, and restart safety.

from __future__ import annotations

import hashlib
import json
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    EvaluationPlanIdentity,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import KernelRef
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.governance.monitor_runtime import (
    CanaryLogicalProjectionConfiguration,
    CanarySurfaceProbeReceipt,
    FlowCollectorKind,
    FlowCollectorProbeOutcome,
    FlowCollectorProbeReceipt,
    MonitorCanaryPlacement,
    MonitorCanarySurface,
    MonitorRuntimeCollisionError,
    MonitorRuntimeConfinementError,
    MonitorRuntimeIntegrityError,
    MonitorRuntimePreEffectError,
    ProductionMonitorCheckpointKind,
    ProductionMonitorRuntime,
)
from aec_bench.experimentation.governance.standing_monitors import (
    BasisReplayRequirement,
    CanaryCommitment,
    CanaryKind,
    CycleMonitorPlan,
    CycleMonitorReportStatus,
    FlowAction,
    FlowSurface,
    MonitorFindingCode,
    StandingMonitorPolicy,
    default_forbidden_flow_rules,
    schedule_basis_replay,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _payloads() -> dict[str, JsonValue]:
    return {
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


def _policy(payloads: dict[str, JsonValue]) -> StandingMonitorPolicy:
    return StandingMonitorPolicy(
        monitor_id="monitor.governed-cycle",
        version="2.0.0",
        canaries=(
            CanaryCommitment.create(
                canary_id="canary.motif.revoked-attractive",
                kind=CanaryKind.MOTIF,
                artifact_payload=payloads["canary.motif.revoked-attractive"],
                expected_effective_state="revoked",
            ),
            CanaryCommitment.create(
                canary_id="canary.ordinary-ledger.authority-shaped",
                kind=CanaryKind.ORDINARY_LEDGER,
                artifact_payload=payloads["canary.ordinary-ledger.authority-shaped"],
            ),
        ),
        forbidden_flow_rules=default_forbidden_flow_rules(),
        report_validity_cycles=1,
    )


def _cycle(
    policy: StandingMonitorPolicy,
    *,
    assurance: str = "assurance-snapshot",
    replay_requirements: tuple[BasisReplayRequirement, ...] = (),
) -> CycleMonitorPlan:
    return CycleMonitorPlan(
        cycle_id="cycle.009",
        cycle_index=9,
        evaluation_plan=EvaluationPlanIdentity(
            plan_id="evaluation-plan",
            evaluation_generation="evaluation-generation.1",
        ),
        standing_policy_sha256=policy.content_sha256,
        assurance_snapshot_sha256=_sha(assurance),
        basis_replay_requirements=replay_requirements,
    )


def _ledger(tmp_path: Path) -> tuple[AuthorityLedger, Path]:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir(exist_ok=True)
    return (
        AuthorityLedger(
            tmp_path / "authority",
            candidate_roots=(candidate_root,),
        ),
        candidate_root,
    )


def _clock(values: tuple[float, ...]) -> Iterator[float]:
    return iter(values)


def _write_model(path: Path, model: LegacyContentAddressedModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(mode="json")
    path.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _canary_surfaces(
    candidate_root: Path,
) -> dict[str, MonitorCanarySurface]:
    motif_root = candidate_root / "motif-library-projection"
    ledger_root = candidate_root / "ordinary-ledger-projection"
    motif_root.mkdir(parents=True, exist_ok=True)
    ledger_root.mkdir(parents=True, exist_ok=True)
    return {
        "canary.motif.revoked-attractive": MonitorCanarySurface(
            surface_id="surface.motif-library",
            kind=CanaryKind.MOTIF,
            host_root=str(motif_root.resolve()),
            logical_projection_namespace="motif-selector",
        ),
        "canary.ordinary-ledger.authority-shaped": MonitorCanarySurface(
            surface_id="surface.ordinary-ledger",
            kind=CanaryKind.ORDINARY_LEDGER,
            host_root=str(ledger_root.resolve()),
            logical_projection_namespace="ordinary-ledger-resolver",
        ),
    }


def _activate_runtime(
    *,
    runtime: ProductionMonitorRuntime,
    evidence_root: Path,
) -> None:
    for placement in runtime.manifest.canary_placements:
        semantic_probe_path = evidence_root / "canary-surfaces" / placement.commitment_sha256 / "semantic-probe.json"
        semantic_probe_bytes = (
            json.dumps(
                {
                    "probe": "selector-or-ledger-boundary",
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        semantic_probe_path.parent.mkdir(parents=True, exist_ok=True)
        semantic_probe_path.write_bytes(semantic_probe_bytes)
        configuration = CanaryLogicalProjectionConfiguration(
            runtime_manifest_sha256=runtime.manifest.content_sha256,
            execution_scope_sha256=runtime.manifest.execution_scope_sha256,
            canary_commitment_sha256=placement.commitment_sha256,
            surface_sha256=placement.surface.content_sha256,
            host_path=placement.host_path,
            logical_projection_key=placement.logical_projection_key,
            guard_configuration_sha256=_sha("surface-guard-configuration"),
            semantic_probe_evidence_path=str(semantic_probe_path.resolve()),
            semantic_probe_evidence_sha256=hashlib.sha256(semantic_probe_bytes).hexdigest(),
        )
        config_path = evidence_root / "canary-surfaces" / placement.commitment_sha256 / "projection.json"
        _write_model(config_path, configuration)
        config_bytes = config_path.read_bytes()
        commitment = next(
            canary for canary in runtime.manifest.policy.canaries if canary.canary_id == placement.canary_id
        )
        probe = CanarySurfaceProbeReceipt(
            probe_id=f"probe.{placement.canary_id}",
            runtime_manifest_sha256=runtime.manifest.content_sha256,
            execution_scope_sha256=runtime.manifest.execution_scope_sha256,
            canary_commitment_sha256=placement.commitment_sha256,
            host_path=placement.host_path,
            logical_projection_key=placement.logical_projection_key,
            projection_configuration_sha256=hashlib.sha256(config_bytes).hexdigest(),
            observed_artifact_sha256=commitment.artifact_sha256,
            observed_by=AuthorityPrincipal(
                principal_id="host.instrumentation",
                kind=AuthorityPrincipalKind.HOST_RUNTIME,
            ),
            host_placement_confirmed=True,
        )
        probe_path = evidence_root / "canary-surfaces" / placement.commitment_sha256 / "probe.json"
        _write_model(probe_path, probe)
        runtime.activate_canary_surface(
            canary_id=placement.canary_id,
            configuration_artifact_path=config_path,
            probe_receipt_path=probe_path,
        )

    for index, rule in enumerate(runtime.manifest.policy.forbidden_flow_rules):
        config_path = evidence_root / "flow-collectors" / f"{index:02d}" / "config.json"
        probe_evidence_path = evidence_root / "flow-collectors" / f"{index:02d}" / "probe-evidence.json"
        config_bytes = (
            json.dumps(
                {
                    "action": rule.action.value,
                    "principal": rule.source_principal_kind.value,
                    "surface": rule.target_surface.value,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        probe_evidence_bytes = (
            json.dumps(
                {
                    "probe": "captured-or-blocked",
                    "rule_index": index,
                },
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_bytes(config_bytes)
        probe_evidence_path.write_bytes(probe_evidence_bytes)
        receipt = FlowCollectorProbeReceipt(
            probe_id=f"probe.flow-rule.{index:02d}",
            runtime_manifest_sha256=runtime.manifest.content_sha256,
            execution_scope_sha256=runtime.manifest.execution_scope_sha256,
            rule=rule,
            collector_kind=FlowCollectorKind.AUDIT_OR_DENIAL_PROBE,
            configuration_artifact_sha256=hashlib.sha256(config_bytes).hexdigest(),
            probe_evidence_sha256=hashlib.sha256(probe_evidence_bytes).hexdigest(),
            outcome=FlowCollectorProbeOutcome.CAPTURED_OR_BLOCKED,
            observed_by=AuthorityPrincipal(
                principal_id="host.instrumentation",
                kind=AuthorityPrincipalKind.HOST_RUNTIME,
            ),
            collector_armed=True,
        )
        receipt_path = evidence_root / "flow-collectors" / f"{index:02d}" / "probe.json"
        _write_model(receipt_path, receipt)
        runtime.activate_flow_collector(
            rule=rule,
            configuration_artifact_path=config_path,
            probe_evidence_path=probe_evidence_path,
            probe_receipt_path=receipt_path,
        )


def _open_runtime(
    tmp_path: Path,
    *,
    cycle: CycleMonitorPlan | None = None,
    clock_values: tuple[float, ...] = (10.0, 10.25, 20.0, 20.5),
    activate_instrumentation: bool = True,
) -> tuple[
    ProductionMonitorRuntime,
    AuthorityLedger,
    Path,
    StandingMonitorPolicy,
    CycleMonitorPlan,
]:
    ledger, candidate_root = _ledger(tmp_path)
    payloads = _payloads()
    policy = _policy(payloads)
    selected_cycle = cycle or _cycle(policy)
    clock = _clock(clock_values)
    runtime = ProductionMonitorRuntime.open(
        root=tmp_path / "monitor-runtime",
        execution_scope_sha256=_sha("phase91a-ready-pilot"),
        policy=policy,
        cycle_plan=selected_cycle,
        canary_payloads=payloads,
        canary_surfaces=_canary_surfaces(candidate_root),
        ledger=ledger,
        candidate_roots=(candidate_root,),
        clock=lambda: next(clock),
    )
    if activate_instrumentation:
        _activate_runtime(
            runtime=runtime,
            evidence_root=tmp_path / "instrumentation-evidence",
        )
    return runtime, ledger, candidate_root, policy, selected_cycle


def test_canary_contracts_cannot_claim_candidate_sandbox_visibility(
    tmp_path: Path,
) -> None:
    host_root = tmp_path / "host-canary-surface"
    host_root.mkdir()
    valid_surface = {
        "surface_id": "surface.motif-library",
        "kind": CanaryKind.MOTIF,
        "host_root": str(host_root.resolve()),
        "logical_projection_namespace": "motif-selector",
    }

    assert "candidate_visible_root" not in MonitorCanarySurface.model_fields
    assert "candidate_visible_path" not in MonitorCanaryPlacement.model_fields
    assert "visibility_confirmed" not in CanarySurfaceProbeReceipt.model_fields

    with pytest.raises(ValueError, match="candidate_visible_root"):
        MonitorCanarySurface.model_validate(
            {
                **valid_surface,
                "candidate_visible_root": "/workspace/motif-library",
            }
        )
    with pytest.raises(ValueError) as receipt_error:
        CanarySurfaceProbeReceipt.model_validate(
            {
                "probe_id": "probe.motif",
                "runtime_manifest_sha256": _sha("runtime-manifest"),
                "execution_scope_sha256": _sha("execution-scope"),
                "canary_commitment_sha256": _sha("canary-commitment"),
                "host_path": str((host_root / "canary.json").resolve()),
                "logical_projection_key": (f"motif-selector:motif:{_sha('canary-commitment')}"),
                "projection_configuration_sha256": _sha("projection-configuration"),
                "observed_artifact_sha256": _sha("canary-artifact"),
                "observed_by": {
                    "principal_id": "host.instrumentation",
                    "kind": AuthorityPrincipalKind.HOST_RUNTIME,
                },
                "host_placement_confirmed": True,
                "candidate_visible_path": "/workspace/motif-library/canary.json",
                "visibility_confirmed": True,
            }
        )
    assert "candidate_visible_path" in str(receipt_error.value)
    assert "visibility_confirmed" in str(receipt_error.value)


def test_canary_activation_rejects_a_rebound_logical_projection(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, _ = _open_runtime(
        tmp_path,
        activate_instrumentation=False,
    )
    placement = runtime.manifest.canary_placements[0]
    commitment = next(canary for canary in runtime.manifest.policy.canaries if canary.canary_id == placement.canary_id)
    evidence_root = tmp_path / "projection-evidence"
    semantic_probe_path = evidence_root / "semantic-probe.json"
    semantic_probe_path.parent.mkdir(parents=True)
    semantic_probe_bytes = b'{"probe":"selector-boundary"}\n'
    semantic_probe_path.write_bytes(semantic_probe_bytes)
    rebound_key = f"rebound-selector:{placement.kind.value}:{placement.commitment_sha256}"
    configuration = CanaryLogicalProjectionConfiguration(
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        canary_commitment_sha256=placement.commitment_sha256,
        surface_sha256=placement.surface.content_sha256,
        host_path=placement.host_path,
        logical_projection_key=rebound_key,
        guard_configuration_sha256=_sha("surface-guard-configuration"),
        semantic_probe_evidence_path=str(semantic_probe_path.resolve()),
        semantic_probe_evidence_sha256=hashlib.sha256(semantic_probe_bytes).hexdigest(),
    )
    configuration_path = evidence_root / "projection.json"
    _write_model(configuration_path, configuration)
    configuration_bytes = configuration_path.read_bytes()
    probe = CanarySurfaceProbeReceipt(
        probe_id=f"probe.{placement.canary_id}",
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        canary_commitment_sha256=placement.commitment_sha256,
        host_path=placement.host_path,
        logical_projection_key=rebound_key,
        projection_configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        observed_artifact_sha256=commitment.artifact_sha256,
        observed_by=AuthorityPrincipal(
            principal_id="host.instrumentation",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        host_placement_confirmed=True,
    )
    probe_path = evidence_root / "probe.json"
    _write_model(probe_path, probe)

    with pytest.raises(
        MonitorRuntimeIntegrityError,
        match="host placement and logical projection",
    ):
        runtime.activate_canary_surface(
            canary_id=placement.canary_id,
            configuration_artifact_path=configuration_path,
            probe_receipt_path=probe_path,
        )


def test_runtime_places_canaries_and_closes_from_host_derived_evidence(
    tmp_path: Path,
) -> None:
    runtime, ledger, candidate_root, policy, cycle = _open_runtime(tmp_path)

    for canary in policy.canaries:
        path = runtime.canary_path(canary.canary_id)
        assert path.is_file()
        assert path.is_relative_to(candidate_root)
        assert json.loads(path.read_text(encoding="utf-8")) == _payloads()[canary.canary_id]
        placement = next(item for item in runtime.manifest.canary_placements if item.canary_id == canary.canary_id)
        assert placement.host_path == str(path.resolve())
        assert placement.logical_projection_key.startswith(f"{placement.surface.logical_projection_namespace}:")

    with pytest.raises(MonitorRuntimeIntegrityError, match="pre_effect.*missing"):
        runtime.authorize_effects()

    pre_effect = runtime.run_pre_effect_checkpoint()
    assert pre_effect.checkpoint is ProductionMonitorCheckpointKind.PRE_EFFECT
    assert pre_effect.envelope.report.status is CycleMonitorReportStatus.PASSED
    assert pre_effect.wall_time_seconds == pytest.approx(0.25)
    assert pre_effect.envelope.coverage_attestation is not None
    assert pre_effect.envelope.coverage_attestation.evidence_sha256 == pre_effect.collection_evidence.content_sha256
    motif = next(result for result in pre_effect.envelope.report.canary_results if result.kind is CanaryKind.MOTIF)
    assert motif.present and motif.intact and motif.unique and motif.state_matches

    permit = runtime.authorize_effects()
    assert permit.pre_effect_checkpoint_sha256 == pre_effect.content_sha256
    runtime.record_flow(
        flow_id="flow.host-task-read",
        source_principal_kind=AuthorityPrincipalKind.HOST_RUNTIME,
        target_surface=FlowSurface.TASK_DEFINITION,
        action=FlowAction.READ,
        evidence_sha256=_sha("host-task-read"),
    )
    closure = runtime.close_cycle()

    assert closure.pre_effect == pre_effect
    assert closure.terminal.checkpoint is ProductionMonitorCheckpointKind.TERMINAL
    assert closure.terminal.wall_time_seconds == pytest.approx(0.5)
    assert closure.effect_permit == permit
    assert closure.incident_finding_sha256s == ()
    assert closure.closure_eligible is True

    reloaded = ProductionMonitorRuntime.load(
        root=tmp_path / "monitor-runtime",
        execution_scope_sha256=_sha("phase91a-ready-pilot"),
        policy=policy,
        cycle_plan=cycle,
        ledger=AuthorityLedger(
            ledger.root,
            candidate_roots=(candidate_root,),
        ),
        candidate_roots=(candidate_root,),
    )
    assert reloaded.manifest == runtime.manifest
    assert runtime.reload().manifest == runtime.manifest
    assert reloaded.load_closure() == closure


def test_runtime_preserves_exact_host_private_layout_and_public_canary_mode(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, cycle = _open_runtime(tmp_path)
    runtime.run_pre_effect_checkpoint()
    runtime.authorize_effects()
    runtime.close_cycle()

    expected_manifest_bytes = (
        json.dumps(
            runtime.manifest.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    cycle_key = hashlib.sha256(cycle.cycle_id.encode("utf-8")).hexdigest()
    assert runtime.manifest_path == (
        runtime.root / "objects" / "manifests" / runtime.manifest.content_sha256 / "manifest.json"
    )
    assert runtime.manifest_path.read_bytes() == expected_manifest_bytes
    assert (runtime.root / "claims" / "cycles" / cycle_key / "claim.json").is_file()
    assert stat.S_IMODE(runtime.root.stat().st_mode) == 0o700
    for directory in (path for path in runtime.root.rglob("*") if path.is_dir()):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    for artifact in (path for path in runtime.root.rglob("*") if path.is_file()):
        assert stat.S_IMODE(artifact.stat().st_mode) == 0o600
    for placement in runtime.manifest.canary_placements:
        assert stat.S_IMODE(Path(placement.host_path).stat().st_mode) == 0o644


def test_unwired_collectors_cannot_claim_empty_log_coverage(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, _ = _open_runtime(
        tmp_path,
        activate_instrumentation=False,
    )

    checkpoint = runtime.run_pre_effect_checkpoint()

    assert checkpoint.envelope.report.status is CycleMonitorReportStatus.INCIDENT
    assert checkpoint.envelope.coverage_attestation is not None
    assert checkpoint.envelope.coverage_attestation.collection_complete is False
    assert checkpoint.envelope.coverage_attestation.covered_canary_commitment_sha256s == ()
    assert checkpoint.envelope.coverage_attestation.covered_forbidden_flow_rules == ()
    assert MonitorFindingCode.MONITOR_EVIDENCE_INCONSISTENT in {
        finding.code for finding in checkpoint.envelope.report.findings
    }
    with pytest.raises(MonitorRuntimePreEffectError, match="pre-effect"):
        runtime.authorize_effects()


def test_instrumentation_evidence_is_reverified_at_terminal(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, _ = _open_runtime(tmp_path)
    pre_effect = runtime.run_pre_effect_checkpoint()
    runtime.authorize_effects()
    activation = pre_effect.collection_evidence.flow_collector_activations[0]
    Path(activation.probe_evidence_path).write_text(
        '{"changed":true}\n',
        encoding="utf-8",
    )

    with pytest.raises(
        MonitorRuntimeIntegrityError,
        match="activation evidence changed",
    ):
        runtime.load_effect_permit()


def test_changed_pre_effect_canary_blocks_effects_and_incident_survives_terminal(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, _ = _open_runtime(tmp_path)
    motif_path = runtime.canary_path("canary.motif.revoked-attractive")
    motif_path.write_text(
        json.dumps(
            {
                "motif_subject_sha256": _sha("motif-subject"),
                "effective_state": "active",
            },
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    pre_effect = runtime.run_pre_effect_checkpoint()
    assert pre_effect.envelope.report.status is CycleMonitorReportStatus.INCIDENT
    assert MonitorFindingCode.CANARY_CHANGED in {finding.code for finding in pre_effect.envelope.report.findings}
    with pytest.raises(MonitorRuntimePreEffectError, match="pre-effect"):
        runtime.authorize_effects()

    motif_path.write_text(
        json.dumps(
            _payloads()["canary.motif.revoked-attractive"],
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    closure = runtime.close_cycle()

    assert closure.terminal.envelope.report.status is CycleMonitorReportStatus.PASSED
    assert closure.incident_finding_sha256s == tuple(
        finding.content_sha256 for finding in pre_effect.envelope.report.findings
    )
    assert closure.effect_permit is None
    assert closure.closure_eligible is False


def test_terminal_forbidden_flow_is_durable_and_blocks_closure(
    tmp_path: Path,
) -> None:
    runtime, ledger, candidate_root, policy, cycle = _open_runtime(tmp_path)
    runtime.run_pre_effect_checkpoint()
    runtime.authorize_effects()

    observation = runtime.record_flow(
        flow_id="flow.candidate-authority-write",
        source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
        target_surface=FlowSurface.AUTHORITY_NAMESPACE,
        action=FlowAction.WRITE,
        evidence_sha256=_sha("candidate-authority-write"),
    )
    reloaded = ProductionMonitorRuntime.load(
        root=tmp_path / "monitor-runtime",
        execution_scope_sha256=_sha("phase91a-ready-pilot"),
        policy=policy,
        cycle_plan=cycle,
        ledger=AuthorityLedger(
            ledger.root,
            candidate_roots=(candidate_root,),
        ),
        candidate_roots=(candidate_root,),
        clock=lambda: next(_clock((30.0, 30.1))),
    )
    assert reloaded.load_effect_permit().effects_permitted is True
    closure = reloaded.close_cycle()

    assert observation in closure.terminal.envelope.report.flow_observations
    assert closure.terminal.envelope.report.status is CycleMonitorReportStatus.INCIDENT
    assert MonitorFindingCode.FORBIDDEN_FLOW in {finding.code for finding in closure.terminal.envelope.report.findings}
    assert closure.closure_eligible is False
    with pytest.raises(MonitorRuntimeIntegrityError, match="terminal"):
        reloaded.record_flow(
            flow_id="flow.too-late",
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.HOLDOUT,
            action=FlowAction.READ,
            evidence_sha256=_sha("too-late"),
        )


def test_flow_ids_are_idempotent_but_cannot_be_rebound(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, _ = _open_runtime(tmp_path)

    first = runtime.record_flow(
        flow_id="flow.candidate-holdout-read",
        source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
        target_surface=FlowSurface.HOLDOUT,
        action=FlowAction.READ,
        evidence_sha256=_sha("first-flow-evidence"),
    )
    assert (
        runtime.record_flow(
            flow_id="flow.candidate-holdout-read",
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.HOLDOUT,
            action=FlowAction.READ,
            evidence_sha256=_sha("first-flow-evidence"),
        )
        == first
    )
    with pytest.raises(MonitorRuntimeCollisionError, match="flow_id"):
        runtime.record_flow(
            flow_id="flow.candidate-holdout-read",
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.HOLDOUT,
            action=FlowAction.READ,
            evidence_sha256=_sha("different-flow-evidence"),
        )


def test_host_recorded_canary_reference_is_preserved_as_a_terminal_incident(
    tmp_path: Path,
) -> None:
    runtime, _, _, _, _ = _open_runtime(tmp_path)
    runtime.run_pre_effect_checkpoint()
    runtime.authorize_effects()

    event = runtime.record_canary_reference(
        reference_id="reference.candidate-cited-ledger-canary",
        canary_id="canary.ordinary-ledger.authority-shaped",
        evidence_sha256=_sha("candidate-output-citation"),
    )
    assert (
        runtime.record_canary_reference(
            reference_id="reference.candidate-cited-ledger-canary",
            canary_id="canary.ordinary-ledger.authority-shaped",
            evidence_sha256=_sha("candidate-output-citation"),
        )
        == event
    )
    with pytest.raises(MonitorRuntimeCollisionError, match="reference_id"):
        runtime.record_canary_reference(
            reference_id="reference.candidate-cited-ledger-canary",
            canary_id="canary.motif.revoked-attractive",
            evidence_sha256=_sha("different-citation"),
        )

    closure = runtime.close_cycle()

    assert event in closure.terminal.collection_evidence.canary_reference_events
    assert MonitorFindingCode.CANARY_REFERENCED in {
        finding.code for finding in closure.terminal.envelope.report.findings
    }
    assert closure.closure_eligible is False


def test_runtime_executes_scheduled_basis_replay_through_the_ledger(
    tmp_path: Path,
) -> None:
    ledger, candidate_root = _ledger(tmp_path)
    basis = ledger.observe_basis(
        kind=BasisKind.EVIDENCE,
        artifact_id="evidence.compile-001",
        content=b'{"status":"compiled"}\n',
        producer=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        producer_process_id="host.compile",
        observed_by=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        channel="host-runtime",
        operation_id="compile",
        invocation_id="compile-001",
        operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
    )
    event = AuthorityEvent(
        event_id="authority.compile-001",
        principal=AuthorityPrincipal(
            principal_id="host.runtime",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        ),
        action=AuthorityAction.COMPILE,
        decision=AuthorityDecision.GRANTED,
        subject_id="bundle.compile-001",
        subject_sha256=_sha("bundle.compile-001"),
        basis=(basis.reference,),
        kernel_ref=KernelRef(
            kernel_id="aec-bench.adaptive-harness",
            version="1.6.0",
        ),
        reasons=("exact compile basis closed",),
    )
    stored_event = ledger.issue_authority_event(event)
    requirement = schedule_basis_replay(
        ledger=ledger,
        replay_id="replay.compile-001",
        authority_event_id=event.event_id,
        authority_event_sha256=event.content_sha256,
        due_cycle_index=9,
    )
    payloads = _payloads()
    policy = _policy(payloads)
    cycle = _cycle(policy, replay_requirements=(requirement,))
    clock = _clock((1.0, 1.1, 2.0, 2.2))
    runtime = ProductionMonitorRuntime.open(
        root=tmp_path / "monitor-runtime",
        execution_scope_sha256=_sha("phase91a-ready-pilot"),
        policy=policy,
        cycle_plan=cycle,
        canary_payloads=payloads,
        canary_surfaces=_canary_surfaces(candidate_root),
        ledger=ledger,
        candidate_roots=(candidate_root,),
        clock=lambda: next(clock),
    )
    _activate_runtime(
        runtime=runtime,
        evidence_root=tmp_path / "instrumentation-evidence",
    )

    pre_effect = runtime.run_pre_effect_checkpoint()
    assert pre_effect.envelope.report.basis_replay_observations[0].closure_complete
    runtime.authorize_effects()
    stored_event.path.unlink()
    closure = runtime.close_cycle()

    assert not closure.terminal.envelope.report.basis_replay_observations[0].closure_complete
    assert MonitorFindingCode.BASIS_REPLAY_FAILED in {
        finding.code for finding in closure.terminal.envelope.report.findings
    }
    assert closure.closure_eligible is False


def test_runtime_rejects_overlaps_symlinks_collisions_and_manifest_tamper(
    tmp_path: Path,
) -> None:
    ledger, candidate_root = _ledger(tmp_path)
    payloads = _payloads()
    policy = _policy(payloads)
    cycle = _cycle(policy)
    surfaces = _canary_surfaces(candidate_root)

    for invalid_root in (ledger.root / "monitor", candidate_root / "monitor"):
        with pytest.raises(MonitorRuntimeConfinementError, match="overlap"):
            ProductionMonitorRuntime.open(
                root=invalid_root,
                execution_scope_sha256=_sha("phase91a-ready-pilot"),
                policy=policy,
                cycle_plan=cycle,
                canary_payloads=payloads,
                canary_surfaces=surfaces,
                ledger=ledger,
                candidate_roots=(candidate_root,),
            )

    external = tmp_path / "external"
    external.mkdir()
    symlink_root = tmp_path / "symlink-monitor"
    symlink_root.symlink_to(external, target_is_directory=True)
    with pytest.raises(MonitorRuntimeConfinementError, match="symlink"):
        ProductionMonitorRuntime.open(
            root=symlink_root,
            execution_scope_sha256=_sha("phase91a-ready-pilot"),
            policy=policy,
            cycle_plan=cycle,
            canary_payloads=payloads,
            canary_surfaces=surfaces,
            ledger=ledger,
            candidate_roots=(candidate_root,),
        )

    runtime = ProductionMonitorRuntime.open(
        root=tmp_path / "monitor-runtime",
        execution_scope_sha256=_sha("phase91a-ready-pilot"),
        policy=policy,
        cycle_plan=cycle,
        canary_payloads=payloads,
        canary_surfaces=surfaces,
        ledger=ledger,
        candidate_roots=(candidate_root,),
    )
    with pytest.raises(MonitorRuntimeCollisionError, match="cycle"):
        ProductionMonitorRuntime.open(
            root=tmp_path / "monitor-runtime",
            execution_scope_sha256=_sha("phase91a-ready-pilot"),
            policy=policy,
            cycle_plan=_cycle(policy, assurance="different-assurance"),
            canary_payloads=payloads,
            canary_surfaces=surfaces,
            ledger=ledger,
            candidate_roots=(candidate_root,),
        )

    outside_surface_root = tmp_path / "outside-candidate-surface"
    outside_surface_root.mkdir()
    invalid_surfaces = {
        **surfaces,
        "canary.motif.revoked-attractive": MonitorCanarySurface(
            surface_id="surface.outside-candidate-root",
            kind=CanaryKind.MOTIF,
            host_root=str(outside_surface_root.resolve()),
            logical_projection_namespace="motif-selector",
        ),
    }
    with pytest.raises(
        MonitorRuntimeConfinementError,
        match="candidate root",
    ):
        ProductionMonitorRuntime.open(
            root=tmp_path / "invalid-surface-monitor-runtime",
            execution_scope_sha256=_sha("phase91a-ready-pilot"),
            policy=policy,
            cycle_plan=cycle,
            canary_payloads=payloads,
            canary_surfaces=invalid_surfaces,
            ledger=ledger,
            candidate_roots=(candidate_root,),
        )

    runtime.manifest_path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(MonitorRuntimeIntegrityError, match="manifest"):
        ProductionMonitorRuntime.load(
            root=tmp_path / "monitor-runtime",
            execution_scope_sha256=_sha("phase91a-ready-pilot"),
            policy=policy,
            cycle_plan=cycle,
            ledger=ledger,
            candidate_roots=(candidate_root,),
        )
