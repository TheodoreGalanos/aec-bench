# ABOUTME: Executes compiled RunBundles through the generic px runtime and real Harbor workflow boundary.
# ABOUTME: Persists candidate manifests and injects causal meta-harness lineage before ledger import.

from __future__ import annotations

import threading
from collections.abc import Mapping
from pathlib import Path

from pydantic import JsonValue

from aec_bench.contracts.harness_instance import (
    ProgramOperationSpec,
    VerificationBindingConfig,
    prohibited_retry_safe_error_codes,
)
from aec_bench.contracts.harness_kernel import (
    canonical_json_sha256,
)
from aec_bench.contracts.run_bundle import RunBundle, TaskSnapshotRef
from aec_bench.contracts.stage_execution import KernelInstructionOverride
from aec_bench.contracts.trajectory import MetaHarnessTrajectoryContext
from aec_bench.contracts.trial_record import (
    ArtifactReference,
    Completeness,
    MetaHarnessTrialProvenance,
    TrialRecord,
)
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    CandidateManifestArtifact,
    HarborInvocationEvidence,
    HarborInvocationGovernance,
    StageExecutionEvidence,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    HarborInvocationReceipt as HarborInvocationReceipt,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    HarborInvocationReceiptArtifact as HarborInvocationReceiptArtifact,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    MetaHarnessStudyContext as MetaHarnessStudyContext,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    RunBundleExecution as RunBundleExecution,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    load_harbor_invocation_receipt as load_harbor_invocation_receipt,
)
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    write_candidate_manifest as _write_candidate_manifest,
)
from aec_bench.experimentation.qualification.run_bundle_scored_attempt import (
    RunBundleScoredAttemptError,
    ScoredInvocationMaterialization,
    execute_governed_scored_attempt,
)
from aec_bench.experimentation.qualification.run_bundle_stage_attempt import (
    RunBundleStageAttemptError,
    execute_governed_stage_attempt,
)
from aec_bench.harness.budget import (
    HarnessBudgetError,
    HarnessBudgetLedger,
)
from aec_bench.harness.contract_enforcement import (
    HarnessContractError,
    enforce_runtime_harness_contracts,
)
from aec_bench.harness.declared_stage import (
    DeclaredStageRuntimeError,
    prepare_finalization_instruction,
    prepare_stage_instruction,
    stage_receipt_reference,
)
from aec_bench.harness.declared_stage import (
    load_stage_execution_receipt as load_stage_execution_receipt,
)
from aec_bench.harness.execution_payload import RuntimeExecutionAttestation
from aec_bench.harness.governed_attempt import (
    GovernedAttemptError,
)
from aec_bench.harness.harbor_dispatch import (
    HarborCommandExecutor,
)
from aec_bench.harness.harbor_lowering import HarborLoweringError, lower_run_bundle
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import (
    KernelOperationDefinition,
    KernelOperationHandlerKey,
    KernelRuntimeRegistry,
    KernelRuntimeRegistryError,
    ProgramOperationRuntime,
    verify_kernel_implementation_identity,
)
from aec_bench.harness.program_execution import (
    OperationExecutionContext,
    OperationHandler,
    OperationHandlerFailure,
    OperationRegistration,
    OperationRegistry,
    OperationResult,
    execute_program,
)


def execute_run_bundle(
    *,
    bundle: RunBundle,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    study: MetaHarnessStudyContext,
    executor: HarborCommandExecutor | None = None,
    authority_ledger: AuthorityLedger | None = None,
) -> RunBundleExecution:
    """Execute the complete immutable px graph using only fixed-K trusted operation handlers."""
    verify_kernel_implementation_identity(registry)
    candidate = _write_candidate_manifest(
        bundle=bundle,
        artifacts_root=artifacts_root,
    )
    budget = HarnessBudgetLedger(bundle.harness.budget)
    handler = _HarborBatchHandler(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        candidate=candidate,
        budget=budget,
        executor=executor,
        authority_ledger=authority_ledger,
    )
    stage_handler = _HarborStageHandler(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        budget=budget,
        executor=executor,
    )
    finalize_handler = _HarborFinalizeHandler(
        bundle=bundle,
        tasks_root=workflow.tasks_root,
        study=study,
        scored_handler=handler,
    )
    registrations = _operation_registrations(
        bundle=bundle,
        registry=registry,
        batch_handler=handler,
        stage_handler=stage_handler,
        finalize_handler=finalize_handler,
    )
    program_result = execute_program(bundle.program, OperationRegistry(registrations))
    return RunBundleExecution(
        program=program_result,
        candidate_manifest=candidate,
        stage_executions=stage_handler.executions,
        harbor_invocations=handler.invocations,
        budget=budget.snapshot(),
    )


class _HarborBatchHandler:
    def __init__(
        self,
        *,
        bundle: RunBundle,
        registry: KernelRuntimeRegistry,
        workflow: SynchronousHarborWorkflow,
        artifacts_root: Path,
        study: MetaHarnessStudyContext,
        candidate: CandidateManifestArtifact,
        budget: HarnessBudgetLedger,
        executor: HarborCommandExecutor | None,
        authority_ledger: AuthorityLedger | None,
    ) -> None:
        self._bundle = bundle
        self._registry = registry
        self._workflow = workflow
        self._artifacts_root = Path(artifacts_root)
        self._study = study
        self._candidate = candidate
        self._budget = budget
        self._executor = executor
        self._authority_ledger = authority_ledger
        self._invocations: list[HarborInvocationEvidence] = []
        self._lock = threading.Lock()

    @property
    def invocations(self) -> tuple[HarborInvocationEvidence, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._invocations,
                    key=lambda item: (
                        item.program_node_id,
                        item.attempt,
                        -1 if item.fanout_index is None else item.fanout_index,
                    ),
                )
            )

    def __call__(
        self,
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
    ) -> OperationResult:
        return self.execute(arguments, context)

    def execute(
        self,
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
        *,
        instruction_override: KernelInstructionOverride | None = None,
        additional_artifacts: tuple[ArtifactReference, ...] = (),
    ) -> OperationResult:
        """Run one scored batch/finalization operation through Harbor and the ledger."""

        selected_task_refs = _runtime_task_refs(arguments)
        try:
            attempt = execute_governed_scored_attempt(
                bundle=self._bundle,
                registry=self._registry,
                workflow=self._workflow,
                artifacts_root=self._artifacts_root,
                study=self._study,
                candidate=self._candidate.reference,
                budget=self._budget,
                context=context,
                task_refs=selected_task_refs,
                executor=self._executor,
                authority_ledger=self._authority_ledger,
                instruction_override=instruction_override,
                additional_artifacts=additional_artifacts,
            )
        except RunBundleScoredAttemptError as error:
            if error.materialization is not None:
                self._append_materialization(
                    context=context,
                    materialization=error.materialization,
                    governance=None,
                )
            if error.dispatch_started and not error.dispatch_accounted:
                self._budget.mark_unaccounted_dispatch()
            raise OperationHandlerFailure(error.code, str(error)) from error

        evidence = self._append_materialization(
            context=context,
            materialization=attempt.materialization,
            governance=attempt.governance,
        )
        rewards = _trial_rewards(evidence.imported_trial_paths)
        return OperationResult.succeeded(
            {
                "result": {
                    "experiment_id": evidence.experiment_id,
                    "job_dir": str(evidence.job_dir),
                    "trial_record_paths": [str(path) for path in evidence.imported_trial_paths],
                    "discovered_trials": attempt.materialization.discovered_trials,
                    "imported_trials": attempt.materialization.imported_trials,
                    "duplicate_trials": attempt.materialization.duplicate_trials,
                    "mean_reward": (sum(rewards) / len(rewards)) if rewards else None,
                },
                "trials": [str(path) for path in evidence.imported_trial_paths],
            }
        )

    def _append_materialization(
        self,
        *,
        context: OperationExecutionContext,
        materialization: ScoredInvocationMaterialization,
        governance: HarborInvocationGovernance | None,
    ) -> HarborInvocationEvidence:
        evidence = HarborInvocationEvidence(
            program_node_id=context.node_id,
            attempt=context.attempt_index,
            fanout_index=context.fanout_index,
            experiment_id=materialization.experiment_id,
            job_dir=materialization.job_dir,
            imported_trial_paths=materialization.imported_trial_paths,
            receipt=materialization.receipt,
            governance=governance,
        )
        with self._lock:
            self._invocations.append(evidence)
        return evidence


class _HarborStageHandler:
    """Execute one declared stage without opening the TrialRecord importer."""

    def __init__(
        self,
        *,
        bundle: RunBundle,
        registry: KernelRuntimeRegistry,
        workflow: SynchronousHarborWorkflow,
        artifacts_root: Path,
        study: MetaHarnessStudyContext,
        budget: HarnessBudgetLedger,
        executor: HarborCommandExecutor | None,
    ) -> None:
        self._bundle = bundle
        self._registry = registry
        self._workflow = workflow
        self._artifacts_root = Path(artifacts_root)
        self._study = study
        self._budget = budget
        self._executor = executor
        self._executions: list[StageExecutionEvidence] = []
        self._lock = threading.Lock()

    @property
    def executions(self) -> tuple[StageExecutionEvidence, ...]:
        with self._lock:
            return tuple(
                sorted(
                    self._executions,
                    key=lambda item: (item.program_node_id, item.attempt),
                )
            )

    def __call__(
        self,
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
    ) -> OperationResult:
        task_id, stage_id, upstream_values = _runtime_stage_selection(arguments)
        dispatch_started = False
        dispatch_accounted = False
        try:
            override, context_manifest, context_reference, upstream_receipts = prepare_stage_instruction(
                bundle=self._bundle,
                tasks_root=self._workflow.tasks_root,
                task_id=task_id,
                stage_id=stage_id,
                upstream_values=upstream_values,
                artifacts_root=self._artifacts_root,
                run_id=self._study.run_id,
                program_node_id=context.node_id,
                attempt=context.attempt_index,
            )
            remaining_runtime_seconds = self._budget.before_dispatch()
            lowered = lower_run_bundle(
                self._bundle,
                registry=self._registry,
                tasks_root=self._workflow.tasks_root,
                program_node_id=context.node_id,
                attempt=context.attempt_index,
                fanout_index=context.fanout_index,
                run_id=self._study.run_id,
                task_refs=(task_id,),
                repair_iteration=self._study.repair_iteration,
                execution_seed=self._study.execution_seed,
                motif_ids=self._study.motif_ids,
                remaining_runtime_seconds=remaining_runtime_seconds,
                instruction_override=override,
            )
            self._budget.reserve_invocation_capacity(
                agent_turns=lowered.agent_turn_capacity,
                tool_calls=lowered.tool_call_capacity,
                context_tokens=lowered.context_token_capacity,
            )
            invocation_root = _invocation_root(
                artifacts_root=self._artifacts_root,
                bundle=self._bundle,
                run_id=self._study.run_id,
                context=context,
            )
            jobs_root = invocation_root / "jobs"
            jobs_root.mkdir(parents=True, exist_ok=True)
            config_path = invocation_root / "harbor.yaml"

            def mark_dispatch_started() -> None:
                nonlocal dispatch_started
                dispatch_started = True

            attempt = execute_governed_stage_attempt(
                engine_root=invocation_root / "governed-attempt",
                bundle=self._bundle,
                lowered=lowered,
                workflow=self._workflow,
                artifacts_root=self._artifacts_root,
                run_id=self._study.run_id,
                context=context,
                task_id=task_id,
                stage_id=stage_id,
                context_manifest=context_manifest,
                context_manifest_reference=context_reference,
                upstream_receipts=upstream_receipts,
                instruction_override=override,
                jobs_root=jobs_root,
                config_path=config_path,
                executor=self._executor,
                maximum_wall_time_seconds=remaining_runtime_seconds,
                on_dispatch_started=mark_dispatch_started,
            )
            stored = attempt.stage_receipt
            dispatch_accounted = True
            resources = stored.receipt.resources
            self._budget.record_stage_execution(
                input_tokens=resources.tokens_in,
                output_tokens=resources.tokens_out,
                estimated_cost_usd=resources.estimated_cost_usd,
                total_seconds=resources.wall_seconds,
            )
            self._budget.after_dispatch()
        except HarborLoweringError as error:
            raise OperationHandlerFailure(error.diagnostic.code, str(error)) from error
        except DeclaredStageRuntimeError as error:
            raise OperationHandlerFailure(error.code, str(error)) from error
        except (
            GovernedAttemptError,
            RunBundleStageAttemptError,
        ) as error:
            raise OperationHandlerFailure(
                "governed_stage_attempt_failed",
                str(error),
            ) from error
        except HarnessBudgetError as error:
            raise OperationHandlerFailure(error.code, str(error)) from error
        except OperationHandlerFailure:
            raise
        except Exception as error:
            message = str(error).strip() or type(error).__name__
            raise OperationHandlerFailure("harbor_stage_workflow_failed", message) from error
        finally:
            if dispatch_started and not dispatch_accounted:
                self._budget.mark_unaccounted_dispatch()

        evidence = StageExecutionEvidence(
            program_node_id=context.node_id,
            attempt=context.attempt_index,
            task_id=task_id,
            stage_id=stage_id,
            job_dir=Path(stored.receipt.job_dir),
            receipt=stored,
        )
        with self._lock:
            self._executions.append(evidence)
        return OperationResult.succeeded({"stage_receipt": stored.reference.model_dump(mode="json")})


class _HarborFinalizeHandler:
    """Consume the exact declared stage set and delegate one scored Harbor finalization."""

    def __init__(
        self,
        *,
        bundle: RunBundle,
        tasks_root: Path,
        study: MetaHarnessStudyContext,
        scored_handler: _HarborBatchHandler,
    ) -> None:
        self._bundle = bundle
        self._tasks_root = Path(tasks_root)
        self._study = study
        self._scored_handler = scored_handler

    def __call__(
        self,
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
    ) -> OperationResult:
        task_id, stage_receipt_values = _runtime_finalization_selection(arguments)
        try:
            override, receipts = prepare_finalization_instruction(
                bundle=self._bundle,
                tasks_root=self._tasks_root,
                task_id=task_id,
                stage_receipt_values=stage_receipt_values,
                run_id=self._study.run_id,
            )
            references = tuple(stage_receipt_reference(receipt) for receipt in receipts)
        except DeclaredStageRuntimeError as error:
            raise OperationHandlerFailure(error.code, str(error)) from error
        except ValueError as error:
            raise OperationHandlerFailure("stage_finalization_evidence_invalid", str(error)) from error
        return self._scored_handler.execute(
            {"task_ref": task_id},
            context,
            instruction_override=override,
            additional_artifacts=references,
        )


class _TrialLineageTransform:
    def __init__(
        self,
        *,
        bundle: RunBundle,
        study: MetaHarnessStudyContext,
        candidate: ArtifactReference,
        required_artifact_kinds: tuple[str, ...],
        expected_adapter_kind: str,
        expected_model: str,
        expected_context: MetaHarnessTrajectoryContext,
        expected_execution_request_sha256_by_task_id: Mapping[str, str],
        additional_artifacts: tuple[ArtifactReference, ...] = (),
    ) -> None:
        self._bundle = bundle
        self._study = study
        self._candidate = candidate
        self._required_artifact_kinds = required_artifact_kinds
        self._expected_adapter_kind = expected_adapter_kind
        self._expected_model = expected_model
        self._expected_context = expected_context
        self._expected_execution_request_sha256_by_task_id = dict(expected_execution_request_sha256_by_task_id)
        self._additional_artifacts = additional_artifacts
        self._repetitions: dict[str, int] = {}
        self._snapshots = {snapshot.task_id: snapshot for snapshot in bundle.task_snapshots}

    def __call__(self, record: TrialRecord) -> TrialRecord:
        self._validate_runtime_attestation(record)
        self._validate_required_verifier(record)
        snapshot = self._snapshots.get(record.task.task_id)
        if snapshot is None:
            raise ValueError(f"trial task is absent from RunBundle snapshots: {record.task.task_id}")
        repetition = self._repetitions.get(record.task.task_id, 0) + 1
        if repetition > self._bundle.harbor.repetitions:
            raise ValueError(f"too many repetitions imported for task: {record.task.task_id}")
        self._repetitions[record.task.task_id] = repetition
        review_sidecar_sha256, declared_surface_sha256 = _review_lineage(snapshot)
        artifacts = _merge_artifacts(
            record.outputs.artifacts or [],
            self._candidate,
            self._study.harness_program_plan,
            self._study.repair_decision,
            *self._additional_artifacts,
        )
        missing = tuple(
            required
            for required in self._required_artifact_kinds
            if not any(_artifact_matches(artifact, required) for artifact in artifacts)
        )
        if missing:
            raise ValueError("required result artifacts are missing: " + ", ".join(missing))
        provenance = MetaHarnessTrialProvenance(
            run_id=self._study.run_id,
            policy_id=self._study.policy_id,
            kernel_id=self._bundle.kernel_ref.kernel_id,
            kernel_sha256=canonical_json_sha256(self._bundle.kernel_ref.model_dump(mode="json")),
            harness_id=self._bundle.harness.instance_id,
            harness_sha256=canonical_json_sha256(self._bundle.harness.model_dump(mode="json")),
            program_id=self._bundle.program.program_id,
            program_sha256=canonical_json_sha256(self._bundle.program.model_dump(mode="json")),
            bundle_id=self._bundle.bundle_id,
            bundle_sha256=canonical_json_sha256(self._bundle.model_dump(mode="json")),
            parent_bundle_id=self._study.parent_bundle_id,
            review_sidecar_sha256=review_sidecar_sha256,
            declared_surface_sha256=declared_surface_sha256,
            harness_generator_sha256=self._study.harness_generator_sha256,
            program_generator_sha256=self._study.program_generator_sha256,
            split=self._study.split,
            repetition=repetition,
            execution_seed=self._study.execution_seed,
            harness_program_cell=self._study.harness_program_cell,
            paired_block_id=self._study.paired_block_id,
            repair_attempt_id=self._study.repair_attempt_id,
            repair_iteration=self._study.repair_iteration,
            candidate_manifest=self._candidate,
            harness_program_plan=self._study.harness_program_plan,
            repair_decision=self._study.repair_decision,
            motif_ids=self._study.motif_ids,
            evaluation_plan_ref=self._study.evaluation_plan_ref,
        )
        transformed = record.model_copy(
            update={
                "environment": record.environment.model_copy(
                    update={"tool_versions": _bound_runtime_versions(self._bundle, snapshot, record)}
                ),
                "outputs": record.outputs.model_copy(update={"artifacts": artifacts}),
                "meta_harness_provenance": provenance,
                "completeness": Completeness.COMPLETE,
            }
        )
        validated = TrialRecord.model_validate(transformed.model_dump(mode="python"))
        enforce_runtime_harness_contracts(
            contracts=self._bundle.harness.contracts,
            record=validated,
            candidate_manifest=self._candidate,
        )
        return validated

    def _validate_runtime_attestation(self, record: TrialRecord) -> None:
        result = record.outputs.agent_result
        payload = result.get("runtime_execution_attestation") if isinstance(result, dict) else None
        if not isinstance(payload, dict):
            raise HarnessContractError(
                "runtime_execution_attestation_missing",
                f"trial {record.trial_id!r} lacks kernel-owned runtime execution evidence",
                subject_ids=(record.trial_id,),
            )
        try:
            attestation = RuntimeExecutionAttestation.model_validate(payload)
        except ValueError as error:
            raise HarnessContractError(
                "runtime_execution_attestation_invalid",
                f"trial {record.trial_id!r} has invalid runtime execution evidence: {error}",
                subject_ids=(record.trial_id,),
            ) from error
        mismatches: list[str] = []
        if attestation.adapter_kind != self._expected_adapter_kind:
            mismatches.append("adapter_kind")
        if attestation.requested_model != self._expected_model:
            mismatches.append("requested_model")
        if attestation.resolved_model != record.agent.model:
            mismatches.append("resolved_model")
        if attestation.meta_harness_context != self._expected_context:
            mismatches.append("meta_harness_context")
        expected_request_sha256 = self._expected_execution_request_sha256_by_task_id.get(record.task.task_id)
        if attestation.execution_request_sha256 != expected_request_sha256:
            mismatches.append("execution_request_sha256")
        if mismatches:
            raise HarnessContractError(
                "runtime_execution_attestation_mismatch",
                f"trial {record.trial_id!r} runtime evidence differs from compiled dispatch: " + ", ".join(mismatches),
                subject_ids=tuple(sorted((record.trial_id, *mismatches))),
            )

    def _validate_required_verifier(self, record: TrialRecord) -> None:
        required = any(
            isinstance(binding.configuration, VerificationBindingConfig)
            and binding.configuration.enabled
            and binding.configuration.required
            for binding in self._bundle.harness.bindings
        )
        if required and not record.evaluation.validity.verifier_completed:
            raise HarnessContractError(
                "required_verifier_not_completed",
                f"trial {record.trial_id!r} did not complete the required Hx verifier",
                subject_ids=(record.trial_id,),
            )

    def validate_complete(self, *, task_ids: tuple[str, ...]) -> None:
        """Require exact coverage of every task/repetition in this Harbor invocation."""
        expected = self._bundle.harbor.repetitions
        missing = tuple(
            sorted(
                f"{task_id}:{self._repetitions.get(task_id, 0)}/{expected}"
                for task_id in task_ids
                if self._repetitions.get(task_id, 0) != expected
            )
        )
        unexpected = tuple(sorted(set(self._repetitions) - set(task_ids)))
        if missing or unexpected:
            raise HarnessContractError(
                "incomplete_harbor_trial_plan",
                "Harbor results do not cover the exact compiled task/repetition plan",
                subject_ids=tuple(sorted((*missing, *unexpected))),
            )


class _EnumerateTaskRefsHandler:
    def __init__(self, task_refs: tuple[str, ...]) -> None:
        self._task_refs = task_refs

    def __call__(
        self,
        arguments: Mapping[str, JsonValue],
        context: OperationExecutionContext,
    ) -> OperationResult:
        del context
        if arguments:
            raise OperationHandlerFailure(
                "unsupported_task_enumeration_arguments",
                "the fixed-K task enumerator accepts no runtime arguments",
            )
        return OperationResult.succeeded({"tasks": list(self._task_refs)})


def _operation_registrations(
    *,
    bundle: RunBundle,
    registry: KernelRuntimeRegistry,
    batch_handler: _HarborBatchHandler,
    stage_handler: _HarborStageHandler,
    finalize_handler: _HarborFinalizeHandler,
) -> tuple[OperationRegistration, ...]:
    operation_runtimes: dict[str, ProgramOperationRuntime] = {}
    for surface_operation in bundle.harness.program_surface.operations:
        try:
            primitive = registry.resolve(surface_operation.capability_ref)
        except KernelRuntimeRegistryError as error:
            raise ValueError(str(error)) from error
        if not isinstance(primitive.runtime, ProgramOperationRuntime):
            raise ValueError(f"operation has no trusted program runtime: {surface_operation.operation_id}")
        prohibited = prohibited_retry_safe_error_codes(primitive.runtime.retry_safe_error_codes)
        if prohibited:
            raise ValueError(
                "installed fixed-K primitive declares prohibited retry-safe error codes: " + ", ".join(prohibited)
            )
        if (
            surface_operation.retry_safe_error_codes != primitive.runtime.retry_safe_error_codes
            or surface_operation.supports_retry is not bool(primitive.runtime.retry_safe_error_codes)
        ):
            raise ValueError(
                "operation retry taxonomy differs from the installed fixed-K primitive: "
                + surface_operation.operation_id
            )
        operation_runtimes[surface_operation.operation_id] = primitive.runtime

    registrations: list[OperationRegistration] = []
    for reference in bundle.program.operation_refs:
        operation = bundle.harness.program_surface.resolve_operation(reference)
        if operation is None:
            raise ValueError(f"compiled operation no longer resolves against Hx: {reference.operation_id}")
        runtime = operation_runtimes[operation.operation_id]
        operation_handler: OperationHandler
        definition = _operation_definition_for_dispatch(
            registry=registry,
            operation=operation,
        )
        if definition is not None:
            operation_handler = _definition_operation_handler(
                definition=definition,
                operation=operation,
                batch_handler=batch_handler,
                stage_handler=stage_handler,
                finalize_handler=finalize_handler,
            )
        else:
            if not registry.is_legacy_definition_free:
                raise ValueError("fixed-K operation lacks its phase-neutral definition: " + operation.operation_id)
            operation_handler = _legacy_operation_handler(
                runtime=runtime,
                operation=operation,
                batch_handler=batch_handler,
                stage_handler=stage_handler,
                finalize_handler=finalize_handler,
            )
        registrations.append(
            OperationRegistration(
                reference=reference,
                binding_ids=operation.binding_ids,
                handler=operation_handler,
                max_parallelism=operation.max_parallelism,
            )
        )
    return tuple(registrations)


def _legacy_operation_handler(
    *,
    runtime: ProgramOperationRuntime,
    operation: ProgramOperationSpec,
    batch_handler: _HarborBatchHandler,
    stage_handler: _HarborStageHandler,
    finalize_handler: _HarborFinalizeHandler,
) -> OperationHandler:
    """Resolve historical runtime strings only for a definition-free registry."""
    if runtime.operation == "harbor_run_batch":
        return batch_handler
    if runtime.operation == "harbor_run_stage":
        return stage_handler
    if runtime.operation == "harbor_finalize_task":
        return finalize_handler
    if runtime.operation == "enumerate_task_refs":
        return _EnumerateTaskRefsHandler(operation.allowed_task_refs)
    raise ValueError(f"unsupported legacy fixed-K operation runtime: {runtime.operation}")


def _operation_definition_for_dispatch(
    *,
    registry: KernelRuntimeRegistry,
    operation: ProgramOperationSpec,
) -> KernelOperationDefinition | None:
    """Resolve migrated dispatch metadata from the same exact registry capability."""
    definition = registry.operation_definition(operation.operation_id)
    if definition is None:
        if not registry.is_legacy_definition_free:
            raise ValueError("fixed-K operation lacks its phase-neutral definition: " + operation.operation_id)
        return None
    primitive = registry.resolve(operation.capability_ref)
    if definition.capability.ref != operation.capability_ref or definition.primitive != primitive:
        raise ValueError("compiled operation differs from its installed kernel definition: " + operation.operation_id)
    return definition


def _definition_operation_handler(
    *,
    definition: KernelOperationDefinition,
    operation: ProgramOperationSpec,
    batch_handler: _HarborBatchHandler,
    stage_handler: _HarborStageHandler,
    finalize_handler: _HarborFinalizeHandler,
) -> OperationHandler:
    if definition.handler_key is KernelOperationHandlerKey.ENUMERATE_TASK_REFS:
        return _EnumerateTaskRefsHandler(operation.allowed_task_refs)
    if definition.handler_key is KernelOperationHandlerKey.RUN_BATCH:
        return batch_handler
    if definition.handler_key is KernelOperationHandlerKey.RUN_STAGE:
        return stage_handler
    if definition.handler_key is KernelOperationHandlerKey.FINALIZE_TASK:
        return finalize_handler
    raise ValueError(f"unsupported kernel operation definition handler: {definition.handler_key}")


def _invocation_root(
    *,
    artifacts_root: Path,
    bundle: RunBundle,
    run_id: str,
    context: OperationExecutionContext,
) -> Path:
    return (
        Path(artifacts_root)
        / _safe_segment(bundle.bundle_id)
        / "runs"
        / _safe_segment(run_id)
        / "invocations"
        / _invocation_id(context)
    )


def _runtime_task_refs(arguments: Mapping[str, JsonValue]) -> tuple[str, ...] | None:
    if not arguments:
        return None
    if set(arguments) == {"task_ref"}:
        task_ref = arguments["task_ref"]
        if isinstance(task_ref, str) and task_ref.strip():
            return (task_ref,)
    elif set(arguments) == {"task_refs"}:
        task_refs = arguments["task_refs"]
        if isinstance(task_refs, list) and task_refs:
            selected: list[str] = []
            for task_ref in task_refs:
                if not isinstance(task_ref, str) or not task_ref.strip():
                    break
                selected.append(task_ref)
            if len(selected) == len(task_refs) and len(selected) == len(set(selected)):
                return tuple(selected)
    raise OperationHandlerFailure(
        "invalid_harbor_task_selection",
        "harbor_run_batch accepts only one non-blank task_ref or a unique non-empty task_refs list",
    )


def _runtime_stage_selection(
    arguments: Mapping[str, JsonValue],
) -> tuple[str, str, JsonValue | None]:
    allowed = {"task_ref", "stage_id", "upstream_receipts"}
    if not {"task_ref", "stage_id"}.issubset(arguments) or not set(arguments).issubset(allowed):
        raise OperationHandlerFailure(
            "invalid_stage_selection",
            "run_stage.v1 requires task_ref/stage_id and optional output-derived upstream_receipts",
        )
    task_ref = arguments["task_ref"]
    stage_id = arguments["stage_id"]
    if not isinstance(task_ref, str) or not task_ref.strip() or not isinstance(stage_id, str) or not stage_id.strip():
        raise OperationHandlerFailure(
            "invalid_stage_selection",
            "run_stage.v1 task_ref and stage_id must be non-blank strings",
        )
    return task_ref, stage_id, arguments.get("upstream_receipts")


def _runtime_finalization_selection(
    arguments: Mapping[str, JsonValue],
) -> tuple[str, JsonValue]:
    if set(arguments) != {"task_ref", "stage_receipts"}:
        raise OperationHandlerFailure(
            "invalid_finalization_selection",
            "finalize_task.v1 requires task_ref and output-derived stage_receipts",
        )
    task_ref = arguments["task_ref"]
    if not isinstance(task_ref, str) or not task_ref.strip():
        raise OperationHandlerFailure(
            "invalid_finalization_selection",
            "finalize_task.v1 task_ref must be a non-blank string",
        )
    return task_ref, arguments["stage_receipts"]


def _review_lineage(snapshot: TaskSnapshotRef) -> tuple[str, str]:
    if snapshot.task_review is not None:
        return snapshot.task_review.review_sidecar_sha256, snapshot.task_review.declared_surface_sha256
    return (
        snapshot.package_sha256,
        canonical_json_sha256(
            {
                "kind": "atomic-task",
                "task_id": snapshot.task_id,
                "task_package_sha256": snapshot.package_sha256,
            }
        ),
    )


def _bound_runtime_versions(
    bundle: RunBundle,
    snapshot: TaskSnapshotRef,
    record: TrialRecord,
) -> dict[str, str]:
    """Bind every selected kernel primitive and the exact task package into execution provenance."""
    versions = dict(record.environment.tool_versions or {})
    expected = {
        **{
            f"kernel:{binding.capability_ref.capability_id}": binding.capability_ref.version
            for binding in bundle.harness.bindings
        },
        "task-package": f"sha256:{snapshot.package_sha256}",
    }
    for name, version in expected.items():
        existing = versions.get(name)
        if existing is not None and existing != version:
            raise ValueError(f"Harbor environment version conflicts with compiled runtime: {name}")
        versions[name] = version
    return dict(sorted(versions.items()))


def _merge_artifacts(
    existing: list[ArtifactReference],
    *required: ArtifactReference | None,
) -> list[ArtifactReference]:
    result = list(existing)
    identities = {(item.kind, item.path, item.sha256) for item in result}
    for artifact in required:
        if artifact is None:
            continue
        identity = (artifact.kind, artifact.path, artifact.sha256)
        if identity not in identities:
            result.append(artifact)
            identities.add(identity)
    return result


def _artifact_matches(artifact: ArtifactReference, requirement: str) -> bool:
    return artifact.kind == requirement or artifact.path.endswith(requirement)


def _invocation_id(context: OperationExecutionContext) -> str:
    fanout = "" if context.fanout_index is None else f"-f{context.fanout_index}"
    return f"{_safe_segment(context.node_id)}-a{context.attempt_index}{fanout}"


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-." else "-" for character in value)
    if not safe or safe in {".", ".."}:
        raise ValueError("runtime identifier cannot be represented as a safe path segment")
    return safe


def _trial_rewards(paths: tuple[Path, ...]) -> list[float]:
    rewards: list[float] = []
    for path in paths:
        record = TrialRecord.model_validate_json(path.read_text(encoding="utf-8"))
        if record.evaluation.reward is not None:
            rewards.append(float(record.evaluation.reward))
    return rewards
