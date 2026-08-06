# ABOUTME: Routes scored RunBundle Harbor invocations through the durable governed-attempt engine.
# ABOUTME: Owns real budget, standing-monitor, dispatch reconciliation, exact import, and replay ports.

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    TaintLabel,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
)
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.contracts.stage_execution import KernelInstructionOverride
from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.harness.execution_payload import execution_request_sha256
from aec_bench.harness.harbor_dispatch import (
    HarborCommandExecutor,
    HarborDispatchResult,
    build_harbor_entrypoint_execution_bundle,
)
from aec_bench.harness.harbor_workflow import (
    HarborDispatchOnlyResult,
    HarborWorkflowResult,
    SynchronousHarborWorkflow,
)
from aec_bench.harness.scheduler import build_trial_plan
from aec_bench.meta_harness.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerError,
    StoredBasis,
)
from aec_bench.meta_harness.governed_attempt_engine import (
    GovernedAttemptBackendReceipt,
    GovernedAttemptBudgetClosure,
    GovernedAttemptBudgetReservation,
    GovernedAttemptDispatchIntent,
    GovernedAttemptEngine,
    GovernedAttemptError,
    GovernedAttemptImportReceipt,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
    GovernedAttemptReplay,
)
from aec_bench.meta_harness.governed_attempt_engine.trial_usage import (
    GovernedTrialUsageError,
    aggregate_governed_trial_usage,
)
from aec_bench.meta_harness.harbor_lowering import (
    HarborLoweringError,
    LoweredHarborRun,
)
from aec_bench.meta_harness.harness_budget import (
    HarnessBudgetError,
    HarnessBudgetLedger,
)
from aec_bench.meta_harness.harness_contracts import HarnessContractError
from aec_bench.meta_harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.meta_harness.program_execution import (
    OperationExecutionContext,
    OperationHandlerFailure,
)
from aec_bench.meta_harness.run_bundle_evidence import (
    HarborInvocationGovernance,
    HarborInvocationReceiptArtifact,
    MetaHarnessStudyContext,
    load_harbor_invocation_receipt,
    persist_harbor_invocation_receipt,
    record_scored_import_authority,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    RunBundleScoredAttemptPlan,
    build_scored_attempt_inputs,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    ScoredAttemptInputs as _Inputs,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    has_reservation_claim as _has_reservation_claim,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    invocation_workflow as _invocation_workflow,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    lower_scored_attempt as _lower,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    safe_segment as _safe_segment,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    scored_attempt_preflight as _preflight,
)
from aec_bench.meta_harness.run_bundle_scored_plan import (
    select_scored_attempt_plan as _select_plan,
)


class RunBundleScoredAttemptError(RuntimeError):
    """Stable operation failure with any complete materialized invocation attached."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        materialization: ScoredInvocationMaterialization | None,
        dispatch_started: bool,
        dispatch_accounted: bool,
    ) -> None:
        self.code = code
        self.materialization = materialization
        self.dispatch_started = dispatch_started
        self.dispatch_accounted = dispatch_accounted
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ScoredInvocationMaterialization:
    """Exact legacy invocation evidence materialized behind one backend effect."""

    experiment_id: str
    job_dir: Path
    imported_trial_paths: tuple[Path, ...]
    receipt: HarborInvocationReceiptArtifact
    records: tuple[TrialRecord, ...]
    discovered_trials: int
    imported_trials: int
    duplicate_trials: int


@dataclass(frozen=True, slots=True)
class GovernedScoredAttempt:
    """Complete governed replay joined to the preserved RunBundle evidence."""

    replay: GovernedAttemptReplay
    materialization: ScoredInvocationMaterialization
    governance: HarborInvocationGovernance | None


def execute_governed_scored_attempt(
    *,
    bundle: RunBundle,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    study: MetaHarnessStudyContext,
    candidate: ArtifactReference,
    budget: HarnessBudgetLedger,
    context: OperationExecutionContext,
    task_refs: tuple[str, ...] | None,
    executor: HarborCommandExecutor | None,
    authority_ledger: AuthorityLedger | None,
    instruction_override: KernelInstructionOverride | None = None,
    additional_artifacts: tuple[ArtifactReference, ...] = (),
) -> GovernedScoredAttempt:
    """Execute or replay one scored invocation without ambiguous redispatch."""

    selected_task_refs = task_refs or bundle.harbor.task_refs
    inputs = build_scored_attempt_inputs(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        candidate=candidate,
        budget=budget,
        context=context,
        task_refs=selected_task_refs,
        executor=executor,
        authority_ledger=authority_ledger,
        instruction_override=instruction_override,
        additional_artifacts=additional_artifacts,
    )
    dispatch_started = False
    budget_port: _ScoredBudgetPort | None = None
    backend: _ScoredBackendPort | None = None
    try:
        observed_remaining = budget.before_dispatch()
        plan = _select_plan(
            inputs,
            observed_remaining=observed_remaining,
        )
        lowered = _lower(inputs, plan=plan)
        preflight = _preflight(inputs, plan=plan, lowered=lowered)
        budget_port = _ScoredBudgetPort(
            ledger=budget,
            lowered=lowered,
        )
        if _has_reservation_claim(inputs.invocation_root):
            budget_port.ensure_reserved()
        monitor = _ScoredMonitorPort(
            root=inputs.invocation_root / "standing-monitor",
            bundle=bundle,
            jobs_root=inputs.jobs_root,
        )

        def mark_dispatch_started() -> None:
            nonlocal dispatch_started
            dispatch_started = True

        backend = _ScoredBackendPort(
            inputs=inputs,
            plan=plan,
            lowered=lowered,
            preflight=preflight,
            budget=budget_port,
            monitor=monitor,
            on_dispatch_started=mark_dispatch_started,
        )
        importer = _ScoredImportExtension(
            inputs=inputs,
            backend=backend,
        )
        engine = GovernedAttemptEngine(
            root=inputs.invocation_root / "governed-attempt-state",
            budget=budget_port,
            monitor=monitor,
            backend=backend,
            import_extension=importer,
            disjoint_roots=(
                workflow.tasks_root.resolve(),
                (workflow.ledger_root / _safe_segment(lowered.ledger_namespace)).resolve(),
                inputs.jobs_root,
            ),
        )
        replay = engine.execute(preflight)
        materialization = backend.materialization or _resolve_materialization(inputs, lowered=lowered)
        if materialization is None:
            raise ValueError("governed terminal has no replayable Harbor invocation receipt")
        _verify_terminal_materialization(
            backend=backend,
            replay=replay,
            materialization=materialization,
        )
        budget_port.account_replay(materialization)
        monitor.verify_replay(
            permit=replay.monitor_permit,
            dispatch_receipt=replay.dispatch_receipt,
            import_receipt=replay.import_receipt,
            budget_closure=replay.budget_closure,
        )
        governance = importer.governance
        if governance is None and authority_ledger is not None:
            governance = _record_external_governance(
                inputs,
                materialization=materialization,
            )
        return GovernedScoredAttempt(
            replay=replay,
            materialization=materialization,
            governance=governance,
        )
    except Exception as error:
        materialization = None if backend is None else backend.materialization
        budget_error: HarnessBudgetError | None = None
        if budget_port is not None and materialization is not None:
            try:
                budget_port.account_replay(materialization)
            except HarnessBudgetError as candidate:
                budget_error = candidate
        selected_error: BaseException = budget_error or error
        code, reported_error = _classified_error(selected_error)
        raise RunBundleScoredAttemptError(
            code,
            str(reported_error).strip() or type(reported_error).__name__,
            materialization=materialization,
            dispatch_started=dispatch_started,
            dispatch_accounted=materialization is not None,
        ) from error


@dataclass(slots=True)
class _ScoredBudgetPort:
    ledger: HarnessBudgetLedger
    lowered: LoweredHarborRun
    _reserved: bool = False
    _accounted: bool = False
    materialization: ScoredInvocationMaterialization | None = None

    def ensure_reserved(self) -> None:
        if self._reserved:
            return
        self.ledger.reserve_invocation_capacity(
            agent_turns=self.lowered.agent_turn_capacity,
            tool_calls=self.lowered.tool_call_capacity,
            context_tokens=self.lowered.context_token_capacity,
        )
        self._reserved = True

    def reserve(
        self,
        preflight: GovernedAttemptPreflight,
    ) -> GovernedAttemptBudgetReservation:
        self.ensure_reserved()
        return GovernedAttemptBudgetReservation(
            attempt_id=preflight.attempt_id,
            preflight_sha256=preflight.content_sha256,
            reservation_id=f"run-bundle-budget:{preflight.content_sha256}",
            maximum_usage=preflight.maximum_usage,
        )

    def close(
        self,
        *,
        reservation: GovernedAttemptBudgetReservation,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
    ) -> GovernedAttemptBudgetClosure:
        if self.materialization is None:
            raise ValueError("budget closure has no exact materialized TrialRecords")
        self._account(self.materialization.records)
        return GovernedAttemptBudgetClosure(
            attempt_id=reservation.attempt_id,
            reservation_sha256=reservation.content_sha256,
            dispatch_receipt_sha256=dispatch_receipt.content_sha256,
            import_receipt_sha256=import_receipt.content_sha256,
            observed_usage=dispatch_receipt.observed_usage,
            effect_evidence_sha256s=dispatch_receipt.effect_evidence_sha256s,
        )

    def account_replay(
        self,
        materialization: ScoredInvocationMaterialization,
    ) -> None:
        self.ensure_reserved()
        self._account(materialization.records)

    def _account(self, records: tuple[TrialRecord, ...]) -> None:
        if self._accounted:
            return
        self._accounted = True
        for record in records:
            self.ledger.record_trial(record)
        self.ledger.after_dispatch()


@dataclass(slots=True)
class _ScoredMonitorPort:
    root: Path
    bundle: RunBundle
    jobs_root: Path
    _ledger: AuthorityLedger = field(init=False)
    _host: AuthorityPrincipal = field(init=False)

    def __post_init__(self) -> None:
        self._ledger = AuthorityLedger(
            self.root,
            candidate_roots=(self.jobs_root,),
        )
        self._host = AuthorityPrincipal(
            principal_id="host.run-bundle-standing-monitor",
            kind=AuthorityPrincipalKind.HOST_RUNTIME,
        )

    def authorize(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
    ) -> GovernedAttemptMonitorPermit:
        preflight_basis = self._observe(
            artifact_id=f"{preflight.attempt_id}.preflight",
            content=_canonical_model_bytes(preflight),
            operation_id="governed-preflight",
        )
        reservation_basis = self._observe(
            artifact_id=f"{preflight.attempt_id}.budget-reservation",
            content=_canonical_model_bytes(reservation),
            operation_id="governed-budget-reservation",
            parent_origins=(preflight_basis.origin.content_sha256,),
        )
        event = AuthorityEvent(
            event_id=f"authority.provider-dispatch.{preflight.attempt_id}",
            principal=self._host,
            action=AuthorityAction.PROVIDER_DISPATCH,
            decision=AuthorityDecision.GRANTED,
            subject_id=f"run-bundle-dispatch.{preflight.attempt_id}",
            subject_sha256=preflight.dispatch_payload_sha256,
            basis=(
                preflight_basis.reference,
                reservation_basis.reference,
            ),
            kernel_sha256=self.bundle.kernel_ref.content_sha256,
            reasons=("exact preflight and real Hx budget reservation passed",),
            revalidation_triggers=("governed_attempt_replay",),
        )
        stored = self._ledger.issue_authority_event(event)
        return GovernedAttemptMonitorPermit(
            attempt_id=preflight.attempt_id,
            preflight_sha256=preflight.content_sha256,
            reservation_sha256=reservation.content_sha256,
            permit_id=stored.event.event_id,
        )

    def close(
        self,
        *,
        permit: GovernedAttemptMonitorPermit,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
    ) -> GovernedAttemptMonitorClosure:
        self._verify_permit(
            permit,
            dispatch_payload_sha256=None,
        )
        report = _monitor_report_bytes(
            permit=permit,
            dispatch_receipt=dispatch_receipt,
            import_receipt=import_receipt,
            budget_closure=budget_closure,
        )
        self._observe(
            artifact_id=f"{permit.attempt_id}.terminal-monitor-report",
            content=report,
            operation_id="governed-terminal-monitor",
        )
        return GovernedAttemptMonitorClosure(
            attempt_id=permit.attempt_id,
            permit_sha256=permit.content_sha256,
            dispatch_receipt_sha256=dispatch_receipt.content_sha256,
            import_receipt_sha256=import_receipt.content_sha256,
            budget_closure_sha256=budget_closure.content_sha256,
            observed_usage=dispatch_receipt.observed_usage,
            effect_evidence_sha256s=dispatch_receipt.effect_evidence_sha256s,
            closure_permitted=True,
        )

    def verify_intent(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        intent: GovernedAttemptDispatchIntent,
    ) -> None:
        event = self._resolve_dispatch_event()
        if event.subject_sha256 != preflight.dispatch_payload_sha256:
            raise AuthorityLedgerError(
                "standing monitor permit differs from the exact Harbor payload",
            )

    def verify_replay(
        self,
        *,
        permit: GovernedAttemptMonitorPermit,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
    ) -> None:
        self._verify_permit(
            permit,
            dispatch_payload_sha256=None,
        )
        stored = self._ledger.basis_for_id(
            kind=BasisKind.EVIDENCE,
            artifact_id=f"{permit.attempt_id}.terminal-monitor-report",
        )
        expected = _monitor_report_bytes(
            permit=permit,
            dispatch_receipt=dispatch_receipt,
            import_receipt=import_receipt,
            budget_closure=budget_closure,
        )
        if stored is None or stored.content_path.read_bytes() != expected:
            raise AuthorityLedgerError(
                "standing monitor terminal report is missing or changed",
            )

    def _verify_permit(
        self,
        permit: GovernedAttemptMonitorPermit,
        *,
        dispatch_payload_sha256: str | None,
    ) -> AuthorityEvent:
        stored = self._ledger.authority_event_for_id(permit.permit_id)
        if (
            stored is None
            or stored.event.action is not AuthorityAction.PROVIDER_DISPATCH
            or stored.event.decision is not AuthorityDecision.GRANTED
            or stored.event.kernel_sha256 != self.bundle.kernel_ref.content_sha256
            or (dispatch_payload_sha256 is not None and stored.event.subject_sha256 != dispatch_payload_sha256)
        ):
            raise AuthorityLedgerError(
                "standing monitor provider-dispatch permit is invalid",
            )
        return stored.event

    def _resolve_dispatch_event(self) -> AuthorityEvent:
        event_root = self.root / "model-objects" / "authority-event"
        matches: list[AuthorityEvent] = []
        if event_root.is_dir():
            for path in sorted(event_root.glob("*/artifact.json")):
                event = AuthorityEvent.model_validate_json(path.read_bytes())
                if event.action is AuthorityAction.PROVIDER_DISPATCH:
                    matches.append(event)
        if len(matches) != 1:
            raise AuthorityLedgerError("standing monitor permit cannot be resolved uniquely")
        return self._ledger.resolve_authority_event(
            event_id=matches[0].event_id,
            content_sha256=matches[0].content_sha256,
        ).event

    def _observe(
        self,
        *,
        artifact_id: str,
        content: bytes,
        operation_id: str,
        parent_origins: tuple[str, ...] = (),
    ) -> StoredBasis:
        return self._ledger.observe_basis(
            kind=BasisKind.EVIDENCE,
            artifact_id=artifact_id,
            content=content,
            producer=self._host,
            producer_process_id="aecbench.run-bundle-standing-monitor",
            observed_by=self._host,
            channel="run-bundle-governed-attempt",
            operation_id=operation_id,
            invocation_id=artifact_id,
            parent_origin_sha256s=parent_origins,
            operation_taint=(TaintLabel.RUNTIME_OBSERVED,),
        )


@dataclass(slots=True)
class _ScoredBackendPort:
    inputs: _Inputs
    plan: RunBundleScoredAttemptPlan
    lowered: LoweredHarborRun
    preflight: GovernedAttemptPreflight
    budget: _ScoredBudgetPort
    monitor: _ScoredMonitorPort
    on_dispatch_started: Callable[[], None]
    materialization: ScoredInvocationMaterialization | None = None

    def dispatch(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt:
        self._validate_intent(intent)
        invocation_workflow = _invocation_workflow(self.inputs, lowered=self.lowered)
        self.on_dispatch_started()
        dispatched = invocation_workflow.dispatch_only(
            manifest=self.lowered.manifest,
            config_path=self.inputs.config_path,
            executor=self.inputs.executor,
            resolved_tasks=self.lowered.tasks,
        )
        return self._materialize_receipt(
            intent=intent,
            dispatched=dispatched,
        )

    def reconcile(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt | None:
        self._validate_intent(intent)
        existing = _resolve_materialization(
            self.inputs,
            lowered=self.lowered,
        )
        if existing is not None:
            self.materialization = existing
            self.budget.materialization = existing
            return self._backend_receipt(intent, existing)
        dispatched = _reconcile_dispatch(self.inputs, lowered=self.lowered)
        if dispatched is None:
            return None
        return self._materialize_receipt(
            intent=intent,
            dispatched=dispatched,
        )

    def _materialize_receipt(
        self,
        *,
        intent: GovernedAttemptDispatchIntent,
        dispatched: HarborDispatchOnlyResult,
    ) -> GovernedAttemptBackendReceipt:
        from aec_bench.meta_harness.run_bundle_runtime import (
            _TrialLineageTransform,
        )

        transform = _TrialLineageTransform(
            bundle=self.inputs.bundle,
            study=self.inputs.study,
            candidate=self.inputs.candidate,
            required_artifact_kinds=self.lowered.required_artifact_kinds,
            expected_adapter_kind=self.lowered.manifest.agents[0].adapter,
            expected_model=self.lowered.manifest.agents[0].model,
            expected_context=self.lowered.meta_harness_context,
            expected_execution_request_sha256_by_task_id={
                task.task_id: execution_request_sha256(
                    build_harbor_entrypoint_execution_bundle(
                        agent=self.lowered.manifest.agents[0],
                        instruction=self.lowered.effective_instruction_by_task_id[task.task_id],
                    )
                )
                for task in self.lowered.tasks
            },
            additional_artifacts=self.inputs.additional_artifacts,
        )
        workflow_result = _invocation_workflow(
            self.inputs,
            lowered=self.lowered,
        ).import_dispatched(
            manifest=self.lowered.manifest,
            dispatched=dispatched,
            record_transform=transform,
        )
        transform.validate_complete(
            task_ids=tuple(task.task_id for task in self.lowered.tasks),
        )
        _validate_import(workflow_result)
        receipt = persist_harbor_invocation_receipt(
            artifacts_root=self.inputs.artifacts_root,
            bundle=self.inputs.bundle,
            study=self.inputs.study,
            context=self.inputs.context,
            experiment_id=self.lowered.manifest.experiment_id,
            harbor_config_path=self.inputs.config_path,
            job_dir=workflow_result.job_dir,
            imported_trial_paths=tuple(workflow_result.import_result.ledger_paths),
        )
        records = _load_records(
            tuple(workflow_result.import_result.ledger_paths),
        )
        self.materialization = ScoredInvocationMaterialization(
            experiment_id=self.lowered.manifest.experiment_id,
            job_dir=workflow_result.job_dir.resolve(),
            imported_trial_paths=tuple(path.resolve() for path in workflow_result.import_result.ledger_paths),
            receipt=receipt,
            records=records,
            discovered_trials=workflow_result.import_result.discovered_trials,
            imported_trials=workflow_result.import_result.imported_trials,
            duplicate_trials=workflow_result.import_result.duplicate_trials,
        )
        self.budget.materialization = self.materialization
        return self._backend_receipt(intent, self.materialization)

    def _backend_receipt(
        self,
        intent: GovernedAttemptDispatchIntent,
        materialization: ScoredInvocationMaterialization,
    ) -> GovernedAttemptBackendReceipt:
        return GovernedAttemptBackendReceipt(
            attempt_id=intent.attempt_id,
            dispatch_intent_sha256=intent.content_sha256,
            dispatch_key_sha256=intent.dispatch_key_sha256,
            backend_receipt_id=f"harbor-invocation:{materialization.receipt.reference.sha256}",
            observed_usage=aggregate_governed_trial_usage(
                materialization.records,
                wall_time_seconds=math.fsum(float(record.timing.total_seconds) for record in materialization.records),
            ),
            effect_evidence_sha256s=_effect_evidence(
                preflight=self.preflight,
                materialization=materialization,
            ),
        )

    def _validate_intent(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> None:
        if intent.dispatch_payload_sha256 != self.preflight.dispatch_payload_sha256:
            raise ValueError("governed scored intent differs from the exact Harbor payload")
        self.monitor.verify_intent(
            preflight=self.preflight,
            intent=intent,
        )


@dataclass(slots=True)
class _ScoredImportExtension:
    inputs: _Inputs
    backend: _ScoredBackendPort
    governance: HarborInvocationGovernance | None = None

    def import_result(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        dispatch_receipt: GovernedAttemptBackendReceipt,
    ) -> GovernedAttemptImportReceipt:
        materialization = self.backend.materialization
        if materialization is None:
            raise ValueError("governed scored import has no materialized Harbor evidence")
        self.governance = _record_external_governance(
            self.inputs,
            materialization=materialization,
        )
        return GovernedAttemptImportReceipt(
            attempt_id=preflight.attempt_id,
            dispatch_receipt_sha256=dispatch_receipt.content_sha256,
            import_id=f"run-bundle-import:{materialization.receipt.reference.sha256}",
            observed_usage=dispatch_receipt.observed_usage,
            source_effect_evidence_sha256s=dispatch_receipt.effect_evidence_sha256s,
            imported_evidence_sha256s=tuple(
                sorted(
                    {
                        materialization.receipt.reference.sha256,
                        *(reference.sha256 for reference in materialization.receipt.receipt.imported_trial_records),
                    }
                )
            ),
        )


def _reconcile_dispatch(
    inputs: _Inputs,
    *,
    lowered: LoweredHarborRun,
) -> HarborDispatchOnlyResult | None:
    if not inputs.config_path.is_file() or not inputs.jobs_root.is_dir():
        return None
    try:
        stored_config = yaml.safe_load(
            inputs.config_path.read_text(encoding="utf-8"),
        )
    except (OSError, yaml.YAMLError):
        return None
    if stored_config != lowered.harbor_job_config(jobs_dir=inputs.jobs_root):
        raise ValueError("durable Harbor config differs from the frozen dispatch payload")
    jobs = tuple(sorted(path.resolve() for path in inputs.jobs_root.iterdir() if path.is_dir()))
    if len(jobs) != 1:
        return None
    return HarborDispatchOnlyResult(
        dispatch=HarborDispatchResult(
            config_path=inputs.config_path,
            command=["uv", "run", "harbor", "run", "-c", str(inputs.config_path)],
            selected_task_count=len(lowered.tasks),
            planned_trial_count=len(build_trial_plan(lowered.manifest, list(lowered.tasks))),
            exit_code=0,
        ),
        job_dir=jobs[0],
        resolved_tasks=lowered.tasks,
    )


def _resolve_materialization(
    inputs: _Inputs,
    *,
    lowered: LoweredHarborRun,
) -> ScoredInvocationMaterialization | None:
    receipts_root = (
        inputs.artifacts_root / inputs.bundle.content_sha256 / "runs" / _safe_segment(inputs.study.run_id) / "receipts"
    )
    if not receipts_root.is_dir():
        return None
    matches: list[HarborInvocationReceiptArtifact] = []
    for path in sorted(receipts_root.glob("*/harbor-invocation-receipt.json")):
        receipt = load_harbor_invocation_receipt(path)
        if (
            receipt.bundle_sha256 == inputs.bundle.content_sha256
            and receipt.run_id == inputs.study.run_id
            and receipt.program_node_id == inputs.context.node_id
            and receipt.attempt == inputs.context.attempt_index
            and receipt.fanout_index == inputs.context.fanout_index
            and receipt.experiment_id == lowered.manifest.experiment_id
        ):
            reference = ArtifactReference(
                kind="harbor-invocation-receipt",
                path=str(path.resolve()),
                sha256=path.parent.name,
                media_type="application/json",
            )
            matches.append(
                HarborInvocationReceiptArtifact(
                    path=path.resolve(),
                    reference=reference,
                    receipt=receipt,
                )
            )
    if len(matches) > 1:
        raise ValueError("scored invocation coordinate resolves to multiple immutable receipts")
    if not matches:
        return None
    stored = matches[0]
    paths = tuple(Path(reference.path).resolve() for reference in stored.receipt.imported_trial_records)
    return ScoredInvocationMaterialization(
        experiment_id=stored.receipt.experiment_id,
        job_dir=Path(stored.receipt.job_dir).resolve(),
        imported_trial_paths=paths,
        receipt=stored,
        records=_load_records(paths),
        discovered_trials=len(paths),
        imported_trials=0,
        duplicate_trials=len(paths),
    )


def _verify_terminal_materialization(
    *,
    backend: _ScoredBackendPort,
    replay: GovernedAttemptReplay,
    materialization: ScoredInvocationMaterialization,
) -> None:
    expected = backend._backend_receipt(
        replay.dispatch_intent,
        materialization,
    )
    if expected != replay.dispatch_receipt:
        raise ValueError("governed terminal differs from the exact Harbor invocation receipt")


def _effect_evidence(
    *,
    preflight: GovernedAttemptPreflight,
    materialization: ScoredInvocationMaterialization,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                *preflight.required_effect_evidence_sha256s,
                materialization.receipt.reference.sha256,
                materialization.receipt.receipt.harbor_config.sha256,
                *(item.sha256 for item in materialization.receipt.receipt.job_files),
                *(item.sha256 for item in materialization.receipt.receipt.imported_trial_records),
            }
        )
    )


def _record_external_governance(
    inputs: _Inputs,
    *,
    materialization: ScoredInvocationMaterialization,
) -> HarborInvocationGovernance | None:
    if inputs.authority_ledger is None:
        return None
    return record_scored_import_authority(
        ledger=inputs.authority_ledger,
        bundle=inputs.bundle,
        study=inputs.study,
        receipt=materialization.receipt,
        imported_trial_paths=materialization.imported_trial_paths,
    )


def _validate_import(workflow_result: HarborWorkflowResult) -> None:
    imported = workflow_result.import_result
    if imported.discovered_trials <= 0:
        raise OperationHandlerFailure(
            "no_harbor_trials",
            "Harbor completed without producing any importable trials",
        )
    if imported.invalid_trials:
        raise OperationHandlerFailure(
            "invalid_harbor_trials",
            f"Harbor import reported {imported.invalid_trials} invalid trials",
        )
    if imported.imported_trials + imported.duplicate_trials != imported.discovered_trials:
        raise OperationHandlerFailure(
            "incomplete_harbor_import",
            "not every discovered Harbor trial reached the append-only ledger",
        )


def _load_records(paths: tuple[Path, ...]) -> tuple[TrialRecord, ...]:
    return tuple(TrialRecord.model_validate_json(path.read_bytes()) for path in paths)


def _monitor_report_bytes(
    *,
    permit: GovernedAttemptMonitorPermit,
    dispatch_receipt: GovernedAttemptBackendReceipt,
    import_receipt: GovernedAttemptImportReceipt,
    budget_closure: GovernedAttemptBudgetClosure,
) -> bytes:
    return (
        json.dumps(
            {
                "schema_version": "aecbench.run-bundle-standing-monitor-report.v1",
                "attempt_id": permit.attempt_id,
                "permit_sha256": permit.content_sha256,
                "dispatch_receipt_sha256": dispatch_receipt.content_sha256,
                "import_receipt_sha256": import_receipt.content_sha256,
                "budget_closure_sha256": budget_closure.content_sha256,
                "effect_evidence_sha256s": dispatch_receipt.effect_evidence_sha256s,
                "observed_usage": dispatch_receipt.observed_usage.model_dump(mode="json"),
                "status": "passed",
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _canonical_model_bytes(model: ContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _classified_error(
    error: BaseException,
) -> tuple[str, BaseException]:
    for item in _cause_chain(error):
        if isinstance(item, HarnessBudgetError):
            return item.code, item
        if isinstance(item, OperationHandlerFailure):
            return item.code, item
        if isinstance(item, HarnessContractError):
            return item.code, item
        if isinstance(item, GovernedTrialUsageError):
            return "governed_usage_evidence_missing", item
        if isinstance(item, AuthorityLedgerError):
            return "scored_import_authority_failed", item
        if isinstance(item, HarborLoweringError):
            return item.diagnostic.code, item
    if isinstance(error, ValueError) and (
        "receipt" in str(error).lower() or "trialrecord" in str(error).lower() or "terminal" in str(error).lower()
    ):
        return "governed_import_integrity_failed", error
    if isinstance(error, GovernedAttemptError):
        return "harbor_workflow_failed", error
    return "harbor_workflow_failed", error


def _cause_chain(error: BaseException) -> tuple[BaseException, ...]:
    result: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in result:
        result.append(current)
        current = current.__cause__ or current.__context__
    return tuple(result)


__all__ = (
    "GovernedScoredAttempt",
    "RunBundleScoredAttemptError",
    "RunBundleScoredAttemptPlan",
    "ScoredInvocationMaterialization",
    "execute_governed_scored_attempt",
)
