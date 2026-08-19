# ABOUTME: Routes one unscored declared-stage Harbor effect through the governed-attempt engine.
# ABOUTME: Adapts exact stage metering and content-addressed receipt replay without opening scored import.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.stage_execution import (
    KernelInstructionOverride,
    StageContextManifest,
    StageExecutionReceipt,
)
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.harness.declared_stage import (
    StoredStageExecutionReceipt,
    load_stage_execution_receipt,
    persist_stage_execution,
    stage_receipt_reference,
)
from aec_bench.harness.governed_attempt import (
    GovernedAttemptBackendReceipt,
    GovernedAttemptBudgetClosure,
    GovernedAttemptBudgetReservation,
    GovernedAttemptDispatchIntent,
    GovernedAttemptEngine,
    GovernedAttemptImportReceipt,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
    GovernedAttemptReplay,
    GovernedAttemptUsage,
    GovernedAttemptUsageLimits,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_lowering import LoweredHarborRun
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.program_execution import OperationExecutionContext

_EXACT_CALL_ADAPTERS = frozenset({"direct", "tool_loop"})


class RunBundleStageAttemptError(ValueError):
    """Reject a stage attempt that cannot preserve exact governed evidence."""


@dataclass(frozen=True, slots=True)
class GovernedStageAttempt:
    """Exact stage receipt joined to the phase-neutral terminal replay."""

    stage_receipt: StoredStageExecutionReceipt
    replay: GovernedAttemptReplay


@dataclass(frozen=True, slots=True)
class _StageAttemptInputs:
    bundle: RunPlan
    lowered: LoweredHarborRun
    workflow: SynchronousHarborWorkflow
    artifacts_root: Path
    run_id: str
    context: OperationExecutionContext
    task_id: str
    stage_id: str
    context_manifest: StageContextManifest
    context_manifest_reference: ArtifactReference
    upstream_receipts: tuple[StageExecutionReceipt, ...]
    instruction_override: KernelInstructionOverride
    jobs_root: Path
    config_path: Path
    executor: HarborCommandExecutor | None
    maximum_wall_time_seconds: int
    on_dispatch_started: Callable[[], None]


def execute_governed_stage_attempt(
    *,
    engine_root: Path,
    bundle: RunPlan,
    lowered: LoweredHarborRun,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    run_id: str,
    context: OperationExecutionContext,
    task_id: str,
    stage_id: str,
    context_manifest: StageContextManifest,
    context_manifest_reference: ArtifactReference,
    upstream_receipts: tuple[StageExecutionReceipt, ...],
    instruction_override: KernelInstructionOverride,
    jobs_root: Path,
    config_path: Path,
    executor: HarborCommandExecutor | None,
    maximum_wall_time_seconds: int,
    on_dispatch_started: Callable[[], None],
) -> GovernedStageAttempt:
    """Execute or replay one exact declared-stage effect through the generic engine."""

    inputs = _StageAttemptInputs(
        bundle=bundle,
        lowered=lowered,
        workflow=workflow,
        artifacts_root=Path(artifacts_root).resolve(),
        run_id=run_id,
        context=context,
        task_id=task_id,
        stage_id=stage_id,
        context_manifest=context_manifest,
        context_manifest_reference=context_manifest_reference,
        upstream_receipts=upstream_receipts,
        instruction_override=instruction_override,
        jobs_root=Path(jobs_root).resolve(),
        config_path=Path(config_path).resolve(),
        executor=executor,
        maximum_wall_time_seconds=maximum_wall_time_seconds,
        on_dispatch_started=on_dispatch_started,
    )
    _validate_inputs(inputs)
    dispatch_payload_sha256 = _dispatch_payload_sha256(inputs)
    preflight = _preflight(
        inputs,
        dispatch_payload_sha256=dispatch_payload_sha256,
    )
    backend = _StageBackendPort(
        inputs=inputs,
        dispatch_payload_sha256=dispatch_payload_sha256,
    )
    engine = GovernedAttemptEngine(
        root=Path(engine_root).resolve(),
        budget=_StageBudgetPort(),
        monitor=_StageMonitorPort(),
        backend=backend,
        import_extension=_StageImportExtension(inputs=inputs),
        disjoint_roots=(
            Path(workflow.tasks_root).resolve(),
            Path(workflow.ledger_root).resolve(),
            inputs.jobs_root,
        ),
    )
    replay = engine.execute(preflight)
    stage_receipt = _resolve_stage_receipt(inputs)
    if stage_receipt is None:
        raise RunBundleStageAttemptError(
            "governed stage terminal has no replayable stage execution receipt",
        )
    expected_backend = _backend_receipt(
        inputs=inputs,
        attempt_id=replay.dispatch_intent.attempt_id,
        dispatch_key_sha256=(replay.dispatch_intent.dispatch_key_sha256),
        stage_receipt=stage_receipt,
    )
    if expected_backend != replay.dispatch_receipt:
        raise RunBundleStageAttemptError(
            "governed stage replay differs from its exact stage execution receipt",
        )
    return GovernedStageAttempt(
        stage_receipt=stage_receipt,
        replay=replay,
    )


@dataclass(slots=True)
class _StageBudgetPort:
    def reserve(
        self,
        preflight: GovernedAttemptPreflight,
    ) -> GovernedAttemptBudgetReservation:
        return GovernedAttemptBudgetReservation(
            attempt_id=preflight.attempt_id,
            reservation_id=f"run-bundle-stage-budget:{preflight.attempt_id}",
            maximum_usage=preflight.maximum_usage,
        )

    def close(
        self,
        *,
        reservation: GovernedAttemptBudgetReservation,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
    ) -> GovernedAttemptBudgetClosure:
        return GovernedAttemptBudgetClosure(
            attempt_id=reservation.attempt_id,
            reservation_id=reservation.reservation_id,
            backend_receipt_id=dispatch_receipt.backend_receipt_id,
            import_id=import_receipt.import_id,
            observed_usage=import_receipt.observed_usage,
            effect_evidence_sha256s=(import_receipt.source_effect_evidence_sha256s),
        )


@dataclass(slots=True)
class _StageMonitorPort:
    def authorize(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
    ) -> GovernedAttemptMonitorPermit:
        return GovernedAttemptMonitorPermit(
            attempt_id=preflight.attempt_id,
            reservation_id=reservation.reservation_id,
            permit_id=f"run-bundle-stage-integrity:{preflight.attempt_id}",
        )

    def close(
        self,
        *,
        permit: GovernedAttemptMonitorPermit,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
    ) -> GovernedAttemptMonitorClosure:
        return GovernedAttemptMonitorClosure(
            attempt_id=permit.attempt_id,
            permit_id=permit.permit_id,
            backend_receipt_id=dispatch_receipt.backend_receipt_id,
            import_id=import_receipt.import_id,
            observed_usage=import_receipt.observed_usage,
            effect_evidence_sha256s=(import_receipt.source_effect_evidence_sha256s),
            closure_permitted=True,
        )


@dataclass(slots=True)
class _StageBackendPort:
    inputs: _StageAttemptInputs
    dispatch_payload_sha256: str

    def dispatch(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt:
        self._validate_intent(intent)
        invocation_workflow = _invocation_workflow(self.inputs)
        self.inputs.on_dispatch_started()
        dispatched = invocation_workflow.dispatch_only(
            manifest=self.inputs.lowered.manifest,
            config_path=self.inputs.config_path,
            executor=self.inputs.executor,
            resolved_tasks=self.inputs.lowered.tasks,
        )
        stored = persist_stage_execution(
            bundle=self.inputs.bundle,
            task_id=self.inputs.task_id,
            stage_id=self.inputs.stage_id,
            run_id=self.inputs.run_id,
            context=self.inputs.context,
            context_manifest=self.inputs.context_manifest,
            context_manifest_reference=(self.inputs.context_manifest_reference),
            upstream_receipts=self.inputs.upstream_receipts,
            job_dir=dispatched.job_dir,
            artifacts_root=self.inputs.artifacts_root,
        )
        return _backend_receipt(
            inputs=self.inputs,
            attempt_id=intent.attempt_id,
            dispatch_key_sha256=intent.dispatch_key_sha256,
            stage_receipt=stored,
        )

    def reconcile(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt | None:
        self._validate_intent(intent)
        stored = _resolve_stage_receipt(self.inputs)
        if stored is None:
            return None
        return _backend_receipt(
            inputs=self.inputs,
            attempt_id=intent.attempt_id,
            dispatch_key_sha256=intent.dispatch_key_sha256,
            stage_receipt=stored,
        )

    def _validate_intent(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> None:
        if intent.dispatch_payload_sha256 != self.dispatch_payload_sha256:
            raise RunBundleStageAttemptError(
                "governed stage intent differs from the exact Harbor payload",
            )


@dataclass(slots=True)
class _StageImportExtension:
    inputs: _StageAttemptInputs

    def import_result(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        dispatch_receipt: GovernedAttemptBackendReceipt,
    ) -> GovernedAttemptImportReceipt:
        stored = _resolve_stage_receipt(self.inputs)
        if stored is None:
            raise RunBundleStageAttemptError(
                "governed stage import has no replayable stage receipt",
            )
        expected = _backend_receipt(
            inputs=self.inputs,
            attempt_id=preflight.attempt_id,
            dispatch_key_sha256=(dispatch_receipt.dispatch_key_sha256),
            stage_receipt=stored,
        )
        if expected != dispatch_receipt:
            raise RunBundleStageAttemptError(
                "governed stage import source differs from its backend receipt",
            )
        return GovernedAttemptImportReceipt(
            attempt_id=preflight.attempt_id,
            backend_receipt_id=dispatch_receipt.backend_receipt_id,
            import_id=f"run-bundle-stage-import:{stored.reference.sha256}",
            observed_usage=dispatch_receipt.observed_usage,
            source_effect_evidence_sha256s=(dispatch_receipt.effect_evidence_sha256s),
            imported_evidence_sha256s=_imported_evidence(stored.receipt),
        )


def _preflight(
    inputs: _StageAttemptInputs,
    *,
    dispatch_payload_sha256: str,
) -> GovernedAttemptPreflight:
    coordinate = {
        "bundle_id": inputs.bundle.run_manifest.run_id,
        "run_id": inputs.run_id,
        "program_node_id": inputs.context.node_id,
        "attempt": inputs.context.attempt_index,
        "fanout_index": inputs.context.fanout_index,
        "task_id": inputs.task_id,
        "stage_id": inputs.stage_id,
    }
    required_evidence = tuple(
        sorted(
            {
                dispatch_payload_sha256,
                inputs.context_manifest_reference.sha256,
                *(stage_receipt_reference(receipt).sha256 for receipt in inputs.upstream_receipts),
            }
        )
    )
    return GovernedAttemptPreflight(
        attempt_id=("run-bundle-stage." + canonical_json_sha256(coordinate)),
        workload_sha256=canonical_json_sha256(
            {
                **coordinate,
                "program_ref": inputs.bundle.execution_program.ref.model_dump(mode="json"),
                "context_manifest": inputs.context_manifest_reference.model_dump(mode="json"),
                "instruction_override": inputs.instruction_override.model_dump(mode="json"),
            }
        ),
        dispatch_payload_sha256=dispatch_payload_sha256,
        maximum_usage=GovernedAttemptUsageLimits(
            model_calls=inputs.lowered.agent_turn_capacity,
            total_tokens=inputs.bundle.harness.budget.max_tokens,
            estimated_cost_usd=(inputs.bundle.harness.budget.max_cost_usd),
            wall_time_seconds=inputs.maximum_wall_time_seconds,
        ),
        required_effect_evidence_sha256s=required_evidence,
    )


def _backend_receipt(
    *,
    inputs: _StageAttemptInputs,
    attempt_id: str,
    dispatch_key_sha256: str,
    stage_receipt: StoredStageExecutionReceipt,
) -> GovernedAttemptBackendReceipt:
    receipt = stage_receipt.receipt
    return GovernedAttemptBackendReceipt(
        attempt_id=attempt_id,
        dispatch_key_sha256=dispatch_key_sha256,
        backend_receipt_id=(f"stage-execution:{stage_receipt.reference.sha256}"),
        observed_usage=_exact_usage(
            receipt,
            adapter_kind=inputs.lowered.manifest.agents[0].adapter,
        ),
        effect_evidence_sha256s=_effect_evidence(
            inputs,
            stage_receipt,
        ),
    )


def _exact_usage(
    receipt: StageExecutionReceipt,
    *,
    adapter_kind: str,
) -> GovernedAttemptUsage:
    if adapter_kind not in _EXACT_CALL_ADAPTERS:
        raise RunBundleStageAttemptError(
            f"declared-stage governed execution does not have exact model-call accounting for adapter {adapter_kind!r}",
        )
    resources = receipt.resources
    required = {
        "tokens_in": resources.tokens_in,
        "tokens_out": resources.tokens_out,
        "cache_read_tokens": resources.cache_read_tokens,
        "cache_write_tokens": resources.cache_write_tokens,
        "estimated_cost_usd": resources.estimated_cost_usd,
        "agent_turns": resources.agent_turns,
    }
    missing = tuple(name for name, value in required.items() if value is None)
    if missing:
        raise RunBundleStageAttemptError(
            "declared-stage governed execution lacks exact usage fields: " + ", ".join(missing),
        )
    payload = _json_object(Path(receipt.agent_result.path))
    advisor_values = (
        payload.get("usage_advisor_calls"),
        payload.get("usage_advisor_input_tokens"),
        payload.get("usage_advisor_output_tokens"),
    )
    if all(value is None for value in advisor_values):
        advisor_calls = advisor_input = advisor_output = 0
    elif all(_is_nonnegative_int(value) for value in advisor_values):
        advisor_calls, advisor_input, advisor_output = cast(
            tuple[int, int, int],
            advisor_values,
        )
    else:
        raise RunBundleStageAttemptError(
            "declared-stage advisor usage must be entirely present or absent",
        )
    assert resources.tokens_in is not None
    assert resources.tokens_out is not None
    assert resources.cache_read_tokens is not None
    assert resources.cache_write_tokens is not None
    assert resources.estimated_cost_usd is not None
    assert resources.agent_turns is not None
    assert isinstance(advisor_calls, int)
    assert isinstance(advisor_input, int)
    assert isinstance(advisor_output, int)
    return GovernedAttemptUsage(
        model_calls=resources.agent_turns + advisor_calls,
        input_tokens=resources.tokens_in + advisor_input,
        output_tokens=resources.tokens_out + advisor_output,
        cache_read_tokens=resources.cache_read_tokens,
        cache_write_tokens=resources.cache_write_tokens,
        estimated_cost_usd=resources.estimated_cost_usd,
        wall_time_seconds=resources.wall_seconds,
    )


def _effect_evidence(
    inputs: _StageAttemptInputs,
    stored: StoredStageExecutionReceipt,
) -> tuple[str, ...]:
    receipt = stored.receipt
    return tuple(
        sorted(
            {
                _dispatch_payload_sha256(inputs),
                inputs.context_manifest_reference.sha256,
                stored.reference.sha256,
                receipt.raw_output.sha256,
                receipt.parsed_output.sha256,
                receipt.agent_result.sha256,
                *(item.sha256 for item in receipt.job_files),
                *(stage_receipt_reference(upstream).sha256 for upstream in inputs.upstream_receipts),
            }
        )
    )


def _imported_evidence(
    receipt: StageExecutionReceipt,
) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                receipt.context_manifest.sha256,
                receipt.raw_output.sha256,
                receipt.parsed_output.sha256,
                receipt.agent_result.sha256,
            }
        )
    )


def _resolve_stage_receipt(
    inputs: _StageAttemptInputs,
) -> StoredStageExecutionReceipt | None:
    receipts_root = (
        inputs.artifacts_root
        / _safe_segment(inputs.bundle.run_manifest.run_id)
        / "runs"
        / _safe_segment(inputs.run_id)
        / "stage-receipts"
    )
    if not receipts_root.exists():
        return None
    matches: list[StoredStageExecutionReceipt] = []
    for path in sorted(
        receipts_root.glob(
            "*/stage-execution-receipt.json",
        )
    ):
        receipt = load_stage_execution_receipt(path)
        if _matches_inputs(receipt, inputs):
            reference = stage_receipt_reference(receipt)
            matches.append(
                StoredStageExecutionReceipt(
                    path=Path(reference.path),
                    reference=reference,
                    receipt=receipt,
                )
            )
    if len(matches) > 1:
        raise RunBundleStageAttemptError(
            "governed stage coordinate resolves to multiple immutable receipts",
        )
    return matches[0] if matches else None


def _matches_inputs(
    receipt: StageExecutionReceipt,
    inputs: _StageAttemptInputs,
) -> bool:
    return (
        receipt.plan_run_id == inputs.bundle.run_manifest.run_id
        and receipt.run_id == inputs.run_id
        and receipt.program_ref == inputs.bundle.execution_program.ref
        and receipt.program_node_id == inputs.context.node_id
        and receipt.operation_ref == inputs.context.operation_ref
        and receipt.attempt == inputs.context.attempt_index
        and receipt.task_id == inputs.task_id
        and receipt.stage_id == inputs.stage_id
        and receipt.context_manifest == inputs.context_manifest_reference
        and receipt.upstream_receipts == tuple(stage_receipt_reference(item) for item in inputs.upstream_receipts)
    )


def _dispatch_payload_sha256(
    inputs: _StageAttemptInputs,
) -> str:
    return canonical_json_sha256(
        {
            "bundle_id": inputs.bundle.run_manifest.run_id,
            "run_id": inputs.run_id,
            "operation_context": {
                "node_id": inputs.context.node_id,
                "operation_ref": (inputs.context.operation_ref.model_dump(mode="json")),
                "attempt_index": inputs.context.attempt_index,
                "fanout_index": inputs.context.fanout_index,
            },
            "manifest": inputs.lowered.manifest.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in inputs.lowered.tasks],
            "harbor_job_config": inputs.lowered.harbor_job_config(
                jobs_dir=inputs.jobs_root,
            ),
            "instruction_override": (inputs.instruction_override.model_dump(mode="json")),
            "context_manifest": (inputs.context_manifest.model_dump(mode="json")),
            "context_manifest_reference": (inputs.context_manifest_reference.model_dump(mode="json")),
            "upstream_receipts": [
                stage_receipt_reference(receipt).model_dump(mode="json") for receipt in inputs.upstream_receipts
            ],
            "config_path": str(inputs.config_path),
        }
    )


def _validate_inputs(inputs: _StageAttemptInputs) -> None:
    if inputs.lowered.operation_runtime != "harbor_run_stage":
        raise RunBundleStageAttemptError(
            "governed stage adapter accepts only harbor_run_stage lowering",
        )
    if len(inputs.lowered.tasks) != 1:
        raise RunBundleStageAttemptError(
            "governed stage adapter requires one exact task",
        )
    if inputs.lowered.tasks[0].task_id != inputs.task_id:
        raise RunBundleStageAttemptError(
            "governed stage task differs from its lowered Harbor payload",
        )
    if inputs.instruction_override.mode != "declared_stage":
        raise RunBundleStageAttemptError(
            "governed stage requires a declared-stage instruction override",
        )
    if (
        inputs.instruction_override.task_id != inputs.task_id
        or inputs.instruction_override.stage_id != inputs.stage_id
        or inputs.instruction_override.context_manifest != inputs.context_manifest_reference
        or inputs.context_manifest_reference.sha256 != _file_sha256(Path(inputs.context_manifest_reference.path))
    ):
        raise RunBundleStageAttemptError(
            "governed stage input identities do not form one exact request",
        )
    if inputs.maximum_wall_time_seconds < 1:
        raise RunBundleStageAttemptError(
            "governed stage wall-time limit must be positive",
        )
    parameters = inputs.lowered.manifest.agents[0].parameters
    if any("advisor" in key for key in parameters):
        raise RunBundleStageAttemptError(
            "governed stage adapter cannot bound an advisor-enabled payload",
        )


def _invocation_workflow(
    inputs: _StageAttemptInputs,
) -> SynchronousHarborWorkflow:
    return SynchronousHarborWorkflow(
        project_root=inputs.workflow.project_root,
        repo_root=inputs.workflow.repo_root,
        tasks_root=inputs.workflow.tasks_root,
        ledger_root=inputs.workflow.ledger_root / "__intermediate-stage-no-import__",
        jobs_root=inputs.jobs_root,
    )


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RunBundleStageAttemptError(
            f"declared-stage usage evidence is invalid: {error}",
        ) from error
    if not isinstance(value, dict):
        raise RunBundleStageAttemptError(
            "declared-stage usage evidence must be a JSON object",
        )
    return value


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise RunBundleStageAttemptError(
            f"governed stage evidence is missing: {path}",
        )
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_nonnegative_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _safe_segment(value: str) -> str:
    safe = "".join(character if character.isalnum() or character in "-." else "-" for character in value)
    if not safe or safe in {".", ".."}:
        raise RunBundleStageAttemptError(
            "run id cannot be represented as a safe stage path",
        )
    return safe
