# ABOUTME: Orchestrates fail-closed pre-effect, permit, terminal, closure, and replay transitions.
# ABOUTME: Preserves every incident and revalidates live instrumentation before effects remain authorized.

from __future__ import annotations

from aec_bench.experimentation.governance.monitor_repository import (
    MonitorRuntimeError,
    MonitorRuntimeIntegrityError,
    ProductionMonitorCheckpointKind,
    _bind_monitor_claim,
    _checkpoint_claim_path,
    _checkpoint_object_path,
    _CheckpointClaim,
    _closure_claim_path,
    _closure_object_path,
    _effect_permit_claim_path,
    _effect_permit_object_path,
    _EffectPermitClaim,
    _load_monitor_model,
    _RuntimeClosureClaim,
    _store_monitor_model,
)
from aec_bench.experimentation.governance.monitor_runtime.contracts import (
    MonitorRuntimeCollectionEvidence,
    ProductionMonitorEffectPermit,
    ProductionMonitorRuntimeCheckpoint,
    ProductionMonitorRuntimeClosure,
)
from aec_bench.experimentation.governance.monitor_runtime.coverage import (
    collection_is_complete,
    derive_coverage_attestation,
)
from aec_bench.experimentation.governance.monitor_runtime.instrumentation import (
    MonitorInstrumentationRuntime,
)
from aec_bench.experimentation.governance.standing_monitors import (
    CycleMonitorReportStatus,
    replay_scheduled_basis,
    run_production_cycle_monitors,
)


class MonitorRuntimePreEffectError(MonitorRuntimeError):
    """Raised when effects are requested without a passing pre-effect checkpoint."""


class MonitorLifecycleRuntime(MonitorInstrumentationRuntime):
    """Runtime layer that owns the mandatory monitor lifecycle state machine."""

    def run_pre_effect_checkpoint(self) -> ProductionMonitorRuntimeCheckpoint:
        """Collect and persist the mandatory checkpoint that must pass before effects."""

        return self._run_checkpoint(ProductionMonitorCheckpointKind.PRE_EFFECT)

    def authorize_effects(self) -> ProductionMonitorEffectPermit:
        """Issue a durable effect permit only from the exact passing pre-effect checkpoint."""

        self._assert_terminal_absent()
        pre_effect = self._load_checkpoint(ProductionMonitorCheckpointKind.PRE_EFFECT)
        if pre_effect.envelope.report.status is not CycleMonitorReportStatus.PASSED:
            raise MonitorRuntimePreEffectError("production effects require a passing pre-effect monitor checkpoint")
        permit = ProductionMonitorEffectPermit(
            runtime_manifest_sha256=self._manifest.content_sha256,
            pre_effect_checkpoint_sha256=pre_effect.content_sha256,
        )
        _store_monitor_model(
            self._repository,
            _effect_permit_object_path(
                self._root,
                self._manifest,
                permit.content_sha256,
            ),
            permit,
            ProductionMonitorEffectPermit,
            label="monitor effect permit",
        )
        claim = _EffectPermitClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            effect_permit_sha256=permit.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            _effect_permit_claim_path(self._root, self._manifest),
            claim,
            _EffectPermitClaim,
            label="monitor effect permit",
        )
        return self._load_effect_permit()

    def load_effect_permit(self) -> ProductionMonitorEffectPermit:
        """Read and revalidate an existing supervisor-issued permit without creating one."""

        return self._load_effect_permit()

    def close_cycle(self) -> ProductionMonitorRuntimeClosure:
        """Run the mandatory terminal checkpoint and preserve all incidents in one closure."""

        if self._claim_exists(_closure_claim_path(self._root, self._manifest)):
            return self.load_closure()
        pre_effect = self._load_checkpoint(ProductionMonitorCheckpointKind.PRE_EFFECT)
        terminal = self._run_checkpoint(ProductionMonitorCheckpointKind.TERMINAL)
        effect_permit = (
            self._load_effect_permit()
            if self._claim_exists(_effect_permit_claim_path(self._root, self._manifest))
            else None
        )
        closure = _build_closure(
            runtime_manifest_sha256=self._manifest.content_sha256,
            pre_effect=pre_effect,
            terminal=terminal,
            effect_permit=effect_permit,
        )
        _store_monitor_model(
            self._repository,
            _closure_object_path(
                self._root,
                self._manifest,
                closure.content_sha256,
            ),
            closure,
            ProductionMonitorRuntimeClosure,
            label="monitor runtime closure",
        )
        claim = _RuntimeClosureClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            closure_sha256=closure.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            _closure_claim_path(self._root, self._manifest),
            claim,
            _RuntimeClosureClaim,
            label="monitor runtime closure",
        )
        return self.load_closure()

    def load_closure(self) -> ProductionMonitorRuntimeClosure:
        """Reload and verify the immutable incident-preserving cycle closure."""

        claim = _load_monitor_model(
            self._repository,
            _closure_claim_path(self._root, self._manifest),
            _RuntimeClosureClaim,
            label="monitor runtime closure claim",
        )
        if claim.runtime_manifest_sha256 != self._manifest.content_sha256:
            raise MonitorRuntimeIntegrityError("monitor runtime closure claim differs from its manifest")
        closure = _load_monitor_model(
            self._repository,
            _closure_object_path(
                self._root,
                self._manifest,
                claim.closure_sha256,
            ),
            ProductionMonitorRuntimeClosure,
            label="monitor runtime closure",
        )
        if (
            closure.content_sha256 != claim.closure_sha256
            or closure.runtime_manifest_sha256 != self._manifest.content_sha256
        ):
            raise MonitorRuntimeIntegrityError("monitor runtime closure differs from its exact claim")
        self._assert_checkpoint_matches(
            closure.pre_effect,
            ProductionMonitorCheckpointKind.PRE_EFFECT,
        )
        self._assert_checkpoint_matches(
            closure.terminal,
            ProductionMonitorCheckpointKind.TERMINAL,
        )
        if closure.effect_permit is not None and closure.effect_permit != self._load_effect_permit():
            raise MonitorRuntimeIntegrityError("monitor runtime closure effect permit differs from durable state")
        return closure

    def _run_checkpoint(
        self,
        checkpoint: ProductionMonitorCheckpointKind,
    ) -> ProductionMonitorRuntimeCheckpoint:
        claim_path = _checkpoint_claim_path(
            self._root,
            self._manifest,
            checkpoint,
        )
        if self._claim_exists(claim_path):
            return self._load_checkpoint(checkpoint)
        self._validate_checkpoint_transition(checkpoint)

        started_at = self._clock()
        evidence = self._collect_checkpoint_evidence(checkpoint)
        coverage = derive_coverage_attestation(
            cycle_plan=self._manifest.cycle_plan,
            observed_by=evidence.observed_by,
            collection_complete=evidence.collection_complete,
            covered_canary_commitment_sha256s=tuple(
                activation.canary_commitment_sha256 for activation in evidence.canary_surface_activations
            ),
            covered_forbidden_flow_rules=tuple(activation.rule for activation in evidence.flow_collector_activations),
            evidence_sha256=evidence.content_sha256,
        )
        envelope = run_production_cycle_monitors(
            policy=self._manifest.policy,
            cycle_plan=self._manifest.cycle_plan,
            coverage_attestation=coverage,
            canary_observations=evidence.canary_observations,
            flow_observations=evidence.flow_observations,
            basis_replay_observations=evidence.basis_replay_observations,
        )
        result = ProductionMonitorRuntimeCheckpoint(
            runtime_manifest_sha256=self._manifest.content_sha256,
            checkpoint=checkpoint,
            collection_evidence=evidence,
            envelope=envelope,
            wall_time_seconds=max(0.0, self._clock() - started_at),
        )
        _store_monitor_model(
            self._repository,
            _checkpoint_object_path(
                self._root,
                self._manifest,
                result.content_sha256,
            ),
            result,
            ProductionMonitorRuntimeCheckpoint,
            label=f"{checkpoint.value} monitor checkpoint",
        )
        claim = _CheckpointClaim(
            runtime_manifest_sha256=self._manifest.content_sha256,
            checkpoint=checkpoint,
            checkpoint_sha256=result.content_sha256,
        )
        _bind_monitor_claim(
            self._repository,
            claim_path,
            claim,
            _CheckpointClaim,
            label=f"{checkpoint.value} monitor checkpoint",
        )
        return self._load_checkpoint(checkpoint)

    def _validate_checkpoint_transition(
        self,
        checkpoint: ProductionMonitorCheckpointKind,
    ) -> None:
        if checkpoint is ProductionMonitorCheckpointKind.PRE_EFFECT and self._claim_exists(
            _checkpoint_claim_path(
                self._root,
                self._manifest,
                ProductionMonitorCheckpointKind.TERMINAL,
            )
        ):
            raise MonitorRuntimeIntegrityError("terminal monitor checkpoint exists without pre-effect state")
        if checkpoint is ProductionMonitorCheckpointKind.TERMINAL:
            self._load_checkpoint(ProductionMonitorCheckpointKind.PRE_EFFECT)

    def _collect_checkpoint_evidence(
        self,
        checkpoint: ProductionMonitorCheckpointKind,
    ) -> MonitorRuntimeCollectionEvidence:
        canary_activations = self._load_canary_surface_activations()
        flow_activations = self._load_flow_collector_activations()
        reference_events = self._load_reference_events()
        canary_observations = self._collect_canary_observations(reference_events=reference_events)
        replay_observations = tuple(
            replay_scheduled_basis(
                ledger=self._ledger,
                requirement=requirement,
            )
            for requirement in self._manifest.cycle_plan.basis_replay_requirements
        )
        return MonitorRuntimeCollectionEvidence(
            runtime_manifest_sha256=self._manifest.content_sha256,
            checkpoint=checkpoint,
            observed_by=self._manifest.observed_by,
            canary_observations=canary_observations,
            flow_observations=self._load_flow_observations(),
            basis_replay_observations=replay_observations,
            canary_reference_events=reference_events,
            canary_surface_activations=canary_activations,
            flow_collector_activations=flow_activations,
            collection_complete=collection_is_complete(
                policy=self._manifest.policy,
                activated_canary_sha256s=(activation.canary_commitment_sha256 for activation in canary_activations),
                activated_rules=(activation.rule for activation in flow_activations),
            ),
        )

    def _load_checkpoint(
        self,
        checkpoint: ProductionMonitorCheckpointKind,
    ) -> ProductionMonitorRuntimeCheckpoint:
        claim = _load_monitor_model(
            self._repository,
            _checkpoint_claim_path(
                self._root,
                self._manifest,
                checkpoint,
            ),
            _CheckpointClaim,
            label=f"{checkpoint.value} monitor checkpoint claim",
        )
        if claim.runtime_manifest_sha256 != self._manifest.content_sha256 or claim.checkpoint is not checkpoint:
            raise MonitorRuntimeIntegrityError(f"{checkpoint.value} monitor checkpoint claim differs from its cycle")
        result = _load_monitor_model(
            self._repository,
            _checkpoint_object_path(
                self._root,
                self._manifest,
                claim.checkpoint_sha256,
            ),
            ProductionMonitorRuntimeCheckpoint,
            label=f"{checkpoint.value} monitor checkpoint",
        )
        self._assert_checkpoint_matches(result, checkpoint)
        if result.content_sha256 != claim.checkpoint_sha256:
            raise MonitorRuntimeIntegrityError(f"{checkpoint.value} monitor checkpoint differs from its claim")
        return result

    def _assert_checkpoint_matches(
        self,
        checkpoint: ProductionMonitorRuntimeCheckpoint,
        expected_kind: ProductionMonitorCheckpointKind,
    ) -> None:
        if (
            checkpoint.runtime_manifest_sha256 != self._manifest.content_sha256
            or checkpoint.checkpoint is not expected_kind
            or checkpoint.envelope.policy != self._manifest.policy
            or checkpoint.envelope.cycle_plan != self._manifest.cycle_plan
        ):
            raise MonitorRuntimeIntegrityError(
                f"{expected_kind.value} monitor checkpoint differs from its runtime manifest"
            )

    def _load_effect_permit(self) -> ProductionMonitorEffectPermit:
        claim = _load_monitor_model(
            self._repository,
            _effect_permit_claim_path(self._root, self._manifest),
            _EffectPermitClaim,
            label="monitor effect permit claim",
        )
        if claim.runtime_manifest_sha256 != self._manifest.content_sha256:
            raise MonitorRuntimeIntegrityError("monitor effect permit claim differs from its runtime manifest")
        permit = _load_monitor_model(
            self._repository,
            _effect_permit_object_path(
                self._root,
                self._manifest,
                claim.effect_permit_sha256,
            ),
            ProductionMonitorEffectPermit,
            label="monitor effect permit",
        )
        pre_effect = self._load_checkpoint(ProductionMonitorCheckpointKind.PRE_EFFECT)
        live_canary_activations = self._load_canary_surface_activations()
        live_flow_activations = self._load_flow_collector_activations()
        if (
            permit.content_sha256 != claim.effect_permit_sha256
            or permit.runtime_manifest_sha256 != self._manifest.content_sha256
            or permit.pre_effect_checkpoint_sha256 != pre_effect.content_sha256
            or pre_effect.envelope.report.status is not CycleMonitorReportStatus.PASSED
            or pre_effect.collection_evidence.canary_surface_activations != live_canary_activations
            or pre_effect.collection_evidence.flow_collector_activations != live_flow_activations
        ):
            raise MonitorRuntimeIntegrityError(
                "monitor effect permit is not backed by the passing pre-effect checkpoint"
            )
        return permit


def _build_closure(
    *,
    runtime_manifest_sha256: str,
    pre_effect: ProductionMonitorRuntimeCheckpoint,
    terminal: ProductionMonitorRuntimeCheckpoint,
    effect_permit: ProductionMonitorEffectPermit | None,
) -> ProductionMonitorRuntimeClosure:
    incident_finding_sha256s = tuple(
        sorted(
            {
                finding.content_sha256
                for checkpoint in (pre_effect, terminal)
                for finding in checkpoint.envelope.report.findings
            }
        )
    )
    return ProductionMonitorRuntimeClosure(
        runtime_manifest_sha256=runtime_manifest_sha256,
        pre_effect=pre_effect,
        terminal=terminal,
        effect_permit=effect_permit,
        incident_finding_sha256s=incident_finding_sha256s,
        closure_eligible=(
            effect_permit is not None
            and pre_effect.envelope.report.status is CycleMonitorReportStatus.PASSED
            and terminal.envelope.report.status is CycleMonitorReportStatus.PASSED
        ),
    )
