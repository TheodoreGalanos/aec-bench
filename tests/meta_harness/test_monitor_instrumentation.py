# ABOUTME: Exercises the host-owned principal-aware surface guard and monitor instrumentation supervisor.
# ABOUTME: Proves standing alarms activate only from real motif, authority, and denied-flow probes.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityPrincipalKind,
)
from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.monitor_instrumentation import (
    MotifCanaryProbeContext,
    activate_production_monitor_instrumentation,
)
from aec_bench.meta_harness.monitor_runtime import (
    CanaryLogicalProjectionConfiguration,
    MonitorCanarySurface,
    ProductionMonitorRuntime,
)
from aec_bench.meta_harness.monitors import (
    CanaryCommitment,
    CanaryKind,
    CycleMonitorPlan,
    FlowAction,
    FlowSurface,
    StandingMonitorPolicy,
    default_forbidden_flow_rules,
)
from aec_bench.meta_harness.motif_assurance import (
    MotifAssuranceLedger,
    MotifAssuranceSnapshot,
    MotifAssuranceState,
    MotifLifecycleEvent,
    derive_motif_assurance_snapshot,
    motif_subject_sha256,
)
from aec_bench.meta_harness.motif_library import (
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifLibrary,
    MotifSelectionRequest,
    MotifStatus,
    MotifStructuralDescriptor,
    MotifTemplate,
)
from aec_bench.meta_harness.surface_guard import (
    PrincipalAwareSurfaceGuard,
    SurfaceAccessDecision,
    SurfaceAccessDenied,
    SurfaceGuardConfinementError,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _motif() -> HarnessProgramMotif:
    return HarnessProgramMotif.create(
        status=MotifStatus.REUSABLE,
        kernel_abi_sha256=_sha("kernel-abi"),
        hx_template=MotifTemplate.create(
            kind="hx",
            payload={"recipe": "review-first"},
        ),
        px_template=MotifTemplate.create(
            kind="px",
            payload={"program": "fanout-join"},
        ),
        applicability=MotifApplicabilityDescriptor(
            task_pattern="review_first",
            stage_pattern="evidence_then_decision",
            stage_count=3,
            fanout_characteristic="bounded",
            branching_characteristic="conditional",
            evidence_surfaces=("source_pack", "verifier_gates"),
            state_mode="ephemeral",
        ),
        descriptor=MotifStructuralDescriptor(
            decomposition_pattern="evidence_fanout",
            orchestration_pattern="verified_join",
            decomposition_depth=2,
            maximum_parallelism=2,
            tool_surface=("artifact.read", "verifier.check"),
            state_mode="ephemeral",
        ),
    )


def _revoked_snapshot(
    motif: HarnessProgramMotif,
) -> MotifAssuranceSnapshot:
    subject = motif_subject_sha256(motif)
    active = MotifLifecycleEvent(
        event_id="monitor-canary.active",
        motif_subject_sha256=subject,
        state=MotifAssuranceState.ACTIVE,
        cause="planted_monitor_canary",
        authority_event_sha256=_sha("canary-active-not-authority"),
        kernel_sha256=_sha("kernel-generation"),
        critic_generation_sha256=_sha("critic-generation"),
        applicability_sha256=_sha("applicability-generation"),
        revalidation_triggers=("critic_generation_change",),
    )
    revoked = MotifLifecycleEvent(
        event_id="monitor-canary.revoked",
        motif_subject_sha256=subject,
        state=MotifAssuranceState.REVOKED,
        cause="planted_revoked_monitor_canary",
        parent_event_sha256=active.content_sha256,
        authority_event_sha256=_sha("canary-revoked-not-authority"),
        kernel_sha256=_sha("kernel-generation"),
        critic_generation_sha256=_sha("critic-generation"),
        applicability_sha256=_sha("applicability-generation"),
        revalidation_triggers=("critic_generation_change",),
    )
    return derive_motif_assurance_snapshot(MotifAssuranceLedger.create().append(active).append(revoked))


def _monitor_inputs(
    tmp_path: Path,
) -> tuple[
    ProductionMonitorRuntime,
    AuthorityLedger,
    Path,
    StandingMonitorPolicy,
    MotifCanaryProbeContext,
]:
    motif = _motif()
    subject = motif_subject_sha256(motif)
    snapshot = _revoked_snapshot(motif)
    motif_payload: dict[str, JsonValue] = {
        "motif_sha256": motif.motif_sha256,
        "motif_subject_sha256": subject,
        "effective_state": MotifAssuranceState.REVOKED.value,
    }
    ordinary_payload: dict[str, JsonValue] = {
        "stage": "authority_event",
        "status": "granted",
        "action": "motif_promotion",
        "principal": "candidate-shaped-but-untrusted",
    }
    payloads: dict[str, JsonValue] = {
        "canary.motif.revoked-attractive": motif_payload,
        "canary.ordinary-ledger.authority-shaped": ordinary_payload,
    }
    policy = StandingMonitorPolicy(
        monitor_id="monitor.instrumentation",
        version="1.0.0",
        canaries=(
            CanaryCommitment.create(
                canary_id="canary.motif.revoked-attractive",
                kind=CanaryKind.MOTIF,
                artifact_payload=motif_payload,
                expected_effective_state=MotifAssuranceState.REVOKED.value,
            ),
            CanaryCommitment.create(
                canary_id="canary.ordinary-ledger.authority-shaped",
                kind=CanaryKind.ORDINARY_LEDGER,
                artifact_payload=ordinary_payload,
            ),
        ),
        forbidden_flow_rules=default_forbidden_flow_rules(),
    )
    cycle = CycleMonitorPlan(
        cycle_id="cycle.instrumentation",
        cycle_index=1,
        evaluation_plan_sha256=_sha("evaluation-plan"),
        standing_policy_sha256=policy.content_sha256,
        assurance_snapshot_sha256=snapshot.content_sha256,
    )
    candidate_root = tmp_path / "candidate"
    motif_root = candidate_root / "motif-library"
    ordinary_root = candidate_root / "ordinary-ledger"
    motif_root.mkdir(parents=True)
    ordinary_root.mkdir(parents=True)
    ledger = AuthorityLedger(
        tmp_path / "authority",
        candidate_roots=(candidate_root,),
    )
    runtime = ProductionMonitorRuntime.open(
        root=tmp_path / "monitor-runtime",
        execution_scope_sha256=_sha("execution-scope"),
        policy=policy,
        cycle_plan=cycle,
        canary_payloads=payloads,
        canary_surfaces={
            "canary.motif.revoked-attractive": MonitorCanarySurface(
                surface_id="surface.motif-library",
                kind=CanaryKind.MOTIF,
                host_root=str(motif_root.resolve()),
                logical_projection_namespace="motif-selector",
            ),
            "canary.ordinary-ledger.authority-shaped": MonitorCanarySurface(
                surface_id="surface.ordinary-ledger",
                kind=CanaryKind.ORDINARY_LEDGER,
                host_root=str(ordinary_root.resolve()),
                logical_projection_namespace="ordinary-ledger-resolver",
            ),
        },
        ledger=ledger,
        candidate_roots=(candidate_root,),
    )
    library = MotifLibrary.create((motif,))
    context = MotifCanaryProbeContext(
        library=library,
        selection_request=MotifSelectionRequest.create(
            archive_sha256=library.archive_sha256,
            archive_frozen=True,
            kernel_abi_sha256=motif.kernel_abi_sha256,
            applicability=motif.applicability,
            selection_split="calibration",
            target_world_lineage_ids=("unseen-world",),
        ),
        assurance_snapshot=snapshot,
    )
    return runtime, ledger, candidate_root, policy, context


def test_surface_guard_denies_and_reloads_exact_policy_rule(
    tmp_path: Path,
) -> None:
    runtime, _, candidate_root, policy, _ = _monitor_inputs(tmp_path)
    guard = PrincipalAwareSurfaceGuard.open(
        root=tmp_path / "surface-guard",
        guard_id="guard.instrumentation",
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        policy=policy,
        candidate_roots=(candidate_root,),
    )
    evidence_path = tmp_path / "attempt-evidence.json"
    evidence_path.write_text(
        json.dumps({"operation": "candidate-task-write"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(SurfaceAccessDenied) as captured:
        guard.authorize_attempt(
            attempt_id="attempt.candidate-task-write",
            source_principal_kind=AuthorityPrincipalKind.CANDIDATE,
            target_surface=FlowSurface.TASK_DEFINITION,
            action=FlowAction.WRITE,
            evidence_path=evidence_path,
        )

    reloaded = guard.reload().load_receipt(captured.value.receipt_sha256)
    assert reloaded.decision is SurfaceAccessDecision.DENIED
    assert reloaded.captured is True
    assert reloaded.matching_rule is not None
    assert reloaded.matching_rule.source_principal_kind is (AuthorityPrincipalKind.CANDIDATE)
    assert reloaded.matching_rule.target_surface is FlowSurface.TASK_DEFINITION
    assert reloaded.matching_rule.action is FlowAction.WRITE
    assert reloaded.attempt.evidence_sha256 == hashlib.sha256(evidence_path.read_bytes()).hexdigest()

    allowed = guard.authorize_attempt(
        attempt_id="attempt.host-task-read",
        source_principal_kind=AuthorityPrincipalKind.HOST_RUNTIME,
        target_surface=FlowSurface.TASK_DEFINITION,
        action=FlowAction.READ,
        evidence_path=evidence_path,
    )
    assert allowed.decision is SurfaceAccessDecision.ALLOWED
    assert allowed.matching_rule is None

    symlink_evidence = tmp_path / "symlink-evidence.json"
    symlink_evidence.symlink_to(evidence_path)
    with pytest.raises(SurfaceGuardConfinementError, match="non-symlink"):
        guard.authorize_attempt(
            attempt_id="attempt.symlink-evidence",
            source_principal_kind=AuthorityPrincipalKind.HOST_RUNTIME,
            target_surface=FlowSurface.TASK_DEFINITION,
            action=FlowAction.READ,
            evidence_path=symlink_evidence,
        )


def test_monitor_supervisor_activates_only_from_real_boundary_and_guard_receipts(
    tmp_path: Path,
) -> None:
    runtime, ledger, candidate_root, policy, motif_context = _monitor_inputs(tmp_path)
    guard = PrincipalAwareSurfaceGuard.open(
        root=tmp_path / "surface-guard",
        guard_id="guard.instrumentation",
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        policy=policy,
        candidate_roots=(candidate_root,),
    )

    activation = activate_production_monitor_instrumentation(
        runtime=runtime,
        guard=guard,
        authority_ledger=ledger,
        motif_canary_contexts={
            "canary.motif.revoked-attractive": motif_context,
        },
        evidence_root=tmp_path / "instrumentation-evidence",
    )

    assert activation.runtime_manifest_sha256 == runtime.manifest.content_sha256
    assert activation.guard_configuration_sha256 == (guard.configuration.content_sha256)
    assert len(activation.canary_activation_sha256s) == 2
    assert len(activation.flow_activation_sha256s) == len(policy.forbidden_flow_rules)
    assert len(activation.guard_receipt_sha256s) == len(policy.forbidden_flow_rules)
    assert all(
        guard.reload().load_receipt(receipt_sha256).decision is SurfaceAccessDecision.DENIED
        for receipt_sha256 in activation.guard_receipt_sha256s
    )
    assert not tuple((ledger.root / "model-claims" / "authority-event").rglob("claim.json"))

    checkpoint = runtime.reload().run_pre_effect_checkpoint()
    assert checkpoint.envelope.report.status.value == "passed"
    for canary_activation in checkpoint.collection_evidence.canary_surface_activations:
        projection = CanaryLogicalProjectionConfiguration.model_validate_json(
            Path(canary_activation.configuration_artifact_path).read_bytes()
        )
        assert projection.guard_configuration_sha256 == guard.configuration.content_sha256
        assert projection.host_path == canary_activation.probe_receipt.host_path
        assert projection.logical_projection_key == canary_activation.probe_receipt.logical_projection_key
        receipt_payload = canary_activation.probe_receipt.model_dump(mode="json")
        assert "candidate_visible_path" not in receipt_payload
        assert "visibility_confirmed" not in receipt_payload
    permit = runtime.reload().authorize_effects()
    assert permit.runtime_manifest_sha256 == runtime.manifest.content_sha256


def test_monitor_supervisor_rejects_a_context_that_does_not_select_the_canary(
    tmp_path: Path,
) -> None:
    runtime, ledger, candidate_root, policy, motif_context = _monitor_inputs(tmp_path)
    guard = PrincipalAwareSurfaceGuard.open(
        root=tmp_path / "surface-guard",
        guard_id="guard.instrumentation",
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        policy=policy,
        candidate_roots=(candidate_root,),
    )
    mismatched_library = MotifLibrary.create()
    mismatched = MotifCanaryProbeContext(
        library=mismatched_library,
        selection_request=MotifSelectionRequest.create(
            archive_sha256=mismatched_library.archive_sha256,
            archive_frozen=True,
            kernel_abi_sha256=_sha("kernel-abi"),
            applicability=motif_context.selection_request.applicability,
            selection_split="calibration",
        ),
        assurance_snapshot=motif_context.assurance_snapshot,
    )

    with pytest.raises(ValueError, match="select the exact motif canary"):
        activate_production_monitor_instrumentation(
            runtime=runtime,
            guard=guard,
            authority_ledger=ledger,
            motif_canary_contexts={
                "canary.motif.revoked-attractive": mismatched,
            },
            evidence_root=tmp_path / "instrumentation-evidence",
        )
