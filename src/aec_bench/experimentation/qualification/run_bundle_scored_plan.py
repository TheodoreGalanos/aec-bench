# ABOUTME: Freezes scored RunBundle invocation inputs and derives exact governed preflight evidence.
# ABOUTME: Owns durable plan selection, Harbor lowering, repository paths, and payload identities.

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Self

from pydantic import (
    NonNegativeInt,
    PositiveInt,
    field_validator,
    model_validator,
)

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.contracts.stage_execution import KernelInstructionOverride
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.qualification.run_bundle_evidence import (
    MetaHarnessStudyContext,
)
from aec_bench.harness.budget import HarnessBudgetLedger
from aec_bench.harness.governed_attempt import (
    GovernedAttemptPreflight,
    GovernedAttemptUsageLimits,
)
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_lowering import (
    LoweredHarborRun,
    lower_run_bundle,
)
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry
from aec_bench.harness.program_execution import OperationExecutionContext
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class RunBundleScoredAttemptPlan(ContentAddressedModel):
    """Durable host plan that freezes lowering inputs before a governed effect."""

    schema_version: Literal["aecbench.run-bundle-scored-attempt-plan.v1"] = "aecbench.run-bundle-scored-attempt-plan.v1"
    bundle_sha256: str
    run_id: NonEmptyStr
    program_node_id: NonEmptyStr
    attempt: PositiveInt
    fanout_index: NonNegativeInt | None = None
    task_refs: tuple[NonEmptyStr, ...]
    remaining_runtime_seconds: PositiveInt
    instruction_override_sha256: str | None = None
    additional_artifact_sha256s: tuple[str, ...] = ()

    @field_validator("bundle_sha256", "instruction_override_sha256")
    @classmethod
    def validate_hash(cls, value: str | None) -> str | None:
        return None if value is None else validate_sha256(value)

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or len(value) != len(set(value)):
            raise ValueError("scored attempt plan requires unique task references")
        return value

    @field_validator("additional_artifact_sha256s")
    @classmethod
    def validate_artifact_hashes(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if value != tuple(sorted(set(value))):
            raise ValueError("scored attempt artifact hashes must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_fanout(self) -> Self:
        if self.fanout_index is not None and self.fanout_index < 0:
            raise ValueError("scored attempt fanout index must be non-negative")
        return self


@dataclass(frozen=True, slots=True)
class ScoredAttemptInputs:
    """All host-owned inputs required to derive one immutable scored attempt."""

    bundle: RunBundle
    registry: KernelRuntimeRegistry
    workflow: SynchronousHarborWorkflow
    artifacts_root: Path
    study: MetaHarnessStudyContext
    candidate: ArtifactReference
    budget: HarnessBudgetLedger
    context: OperationExecutionContext
    task_refs: tuple[str, ...]
    executor: HarborCommandExecutor | None
    authority_ledger: AuthorityLedger | None
    instruction_override: KernelInstructionOverride | None
    additional_artifacts: tuple[ArtifactReference, ...]
    invocation_root: Path
    jobs_root: Path
    config_path: Path


def build_scored_attempt_inputs(
    *,
    bundle: RunBundle,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    study: MetaHarnessStudyContext,
    candidate: ArtifactReference,
    budget: HarnessBudgetLedger,
    context: OperationExecutionContext,
    task_refs: tuple[str, ...],
    executor: HarborCommandExecutor | None,
    authority_ledger: AuthorityLedger | None,
    instruction_override: KernelInstructionOverride | None,
    additional_artifacts: tuple[ArtifactReference, ...],
) -> ScoredAttemptInputs:
    """Resolve canonical per-invocation roots once."""

    invocation_root = invocation_root_for(
        artifacts_root=artifacts_root,
        bundle=bundle,
        run_id=study.run_id,
        context=context,
    )
    return ScoredAttemptInputs(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=Path(artifacts_root).resolve(),
        study=study,
        candidate=candidate,
        budget=budget,
        context=context,
        task_refs=task_refs,
        executor=executor,
        authority_ledger=authority_ledger,
        instruction_override=instruction_override,
        additional_artifacts=additional_artifacts,
        invocation_root=invocation_root.resolve(),
        jobs_root=(invocation_root / "jobs").resolve(),
        config_path=(invocation_root / "harbor.yaml").resolve(),
    )


def select_scored_attempt_plan(
    inputs: ScoredAttemptInputs,
    *,
    observed_remaining: int,
) -> RunBundleScoredAttemptPlan:
    """Persist once or replay the exact lowering inputs and wall allowance."""

    path = inputs.invocation_root / "scored-attempt-plan.json"
    if path.is_file():
        plan = RunBundleScoredAttemptPlan.model_validate_json(path.read_bytes())
        expected = _plan(
            inputs,
            remaining_runtime_seconds=plan.remaining_runtime_seconds,
        )
        if plan != expected:
            raise ValueError("durable scored attempt plan differs from the requested invocation")
        return plan
    plan = _plan(
        inputs,
        remaining_runtime_seconds=observed_remaining,
    )
    _write_exact(path, _pretty_model_bytes(plan))
    return RunBundleScoredAttemptPlan.model_validate_json(path.read_bytes())


def lower_scored_attempt(
    inputs: ScoredAttemptInputs,
    *,
    plan: RunBundleScoredAttemptPlan,
) -> LoweredHarborRun:
    """Lower from the durable plan rather than a drifting restart clock."""

    return lower_run_bundle(
        inputs.bundle,
        registry=inputs.registry,
        tasks_root=inputs.workflow.tasks_root,
        program_node_id=inputs.context.node_id,
        attempt=inputs.context.attempt_index,
        fanout_index=inputs.context.fanout_index,
        run_id=inputs.study.run_id,
        task_refs=inputs.task_refs,
        repair_iteration=inputs.study.repair_iteration,
        execution_seed=inputs.study.execution_seed,
        motif_ids=inputs.study.motif_ids,
        remaining_runtime_seconds=plan.remaining_runtime_seconds,
        instruction_override=inputs.instruction_override,
    )


def scored_attempt_preflight(
    inputs: ScoredAttemptInputs,
    *,
    plan: RunBundleScoredAttemptPlan,
    lowered: LoweredHarborRun,
) -> GovernedAttemptPreflight:
    """Build the exact generic-engine workload, evidence set, and usage caps."""

    dispatch_sha256 = dispatch_payload_sha256(
        inputs,
        lowered=lowered,
    )
    coordinate = {
        "bundle_sha256": inputs.bundle.content_sha256,
        "run_id": inputs.study.run_id,
        "program_node_id": inputs.context.node_id,
        "attempt": inputs.context.attempt_index,
        "fanout_index": inputs.context.fanout_index,
    }
    required = {
        inputs.bundle.content_sha256,
        inputs.candidate.sha256,
        plan.content_sha256,
        dispatch_sha256,
        *(artifact.sha256 for artifact in inputs.additional_artifacts),
    }
    if inputs.instruction_override is not None:
        required.add(inputs.instruction_override.content_sha256)
    return GovernedAttemptPreflight(
        attempt_id=("run-bundle-scored." + canonical_content_sha256(coordinate)),
        workload_sha256=canonical_content_sha256(
            {
                **coordinate,
                "plan_sha256": plan.content_sha256,
                "harness_sha256": inputs.bundle.harness.content_sha256,
                "program_sha256": inputs.bundle.program.content_sha256,
            }
        ),
        dispatch_payload_sha256=dispatch_sha256,
        maximum_usage=GovernedAttemptUsageLimits(
            model_calls=lowered.agent_turn_capacity,
            total_tokens=inputs.bundle.harness.budget.max_tokens,
            estimated_cost_usd=(inputs.bundle.harness.budget.max_cost_usd),
            wall_time_seconds=plan.remaining_runtime_seconds,
        ),
        required_effect_evidence_sha256s=tuple(sorted(required)),
    )


def dispatch_payload_sha256(
    inputs: ScoredAttemptInputs,
    *,
    lowered: LoweredHarborRun,
) -> str:
    """Hash the exact concrete Harbor payload and fixed invocation coordinate."""

    return canonical_content_sha256(
        {
            "bundle_sha256": inputs.bundle.content_sha256,
            "run_id": inputs.study.run_id,
            "operation_context": {
                "node_id": inputs.context.node_id,
                "operation_ref": (inputs.context.operation_ref.model_dump(mode="json")),
                "attempt_index": inputs.context.attempt_index,
                "fanout_index": inputs.context.fanout_index,
            },
            "manifest": lowered.manifest.model_dump(mode="json"),
            "tasks": [task.model_dump(mode="json") for task in lowered.tasks],
            "harbor_job_config": lowered.harbor_job_config(
                jobs_dir=inputs.jobs_root,
            ),
            "config_path": str(inputs.config_path),
        }
    )


def invocation_workflow(
    inputs: ScoredAttemptInputs,
    *,
    lowered: LoweredHarborRun,
) -> SynchronousHarborWorkflow:
    """Build the isolated workflow that owns one exact ledger namespace."""

    return SynchronousHarborWorkflow(
        project_root=inputs.workflow.project_root,
        repo_root=inputs.workflow.repo_root,
        tasks_root=inputs.workflow.tasks_root,
        ledger_root=(inputs.workflow.ledger_root / safe_segment(lowered.ledger_namespace)),
        jobs_root=inputs.jobs_root,
    )


def has_reservation_claim(invocation_root: Path) -> bool:
    """Return whether the generic engine already made reservation durable."""

    return any(
        (invocation_root / "governed-attempt-state" / "governed-attempt" / "claims" / "budget_reservation").glob(
            "*/claim.json"
        )
    )


def invocation_root_for(
    *,
    artifacts_root: Path,
    bundle: RunBundle,
    run_id: str,
    context: OperationExecutionContext,
) -> Path:
    """Return the stable operation coordinate root."""

    return (
        Path(artifacts_root)
        / bundle.content_sha256
        / "runs"
        / safe_segment(run_id)
        / "invocations"
        / _invocation_id(context)
    )


def safe_segment(value: str) -> str:
    """Normalize one runtime identifier for a confined path component."""

    safe = "".join(character if character.isalnum() or character in "-." else "-" for character in value)
    if not safe or safe in {".", ".."}:
        raise ValueError("runtime identifier cannot be represented as a safe path segment")
    return safe


def _plan(
    inputs: ScoredAttemptInputs,
    *,
    remaining_runtime_seconds: int,
) -> RunBundleScoredAttemptPlan:
    return RunBundleScoredAttemptPlan(
        bundle_sha256=inputs.bundle.content_sha256,
        run_id=inputs.study.run_id,
        program_node_id=inputs.context.node_id,
        attempt=inputs.context.attempt_index,
        fanout_index=inputs.context.fanout_index,
        task_refs=inputs.task_refs,
        remaining_runtime_seconds=remaining_runtime_seconds,
        instruction_override_sha256=(
            None if inputs.instruction_override is None else inputs.instruction_override.content_sha256
        ),
        additional_artifact_sha256s=tuple(sorted({artifact.sha256 for artifact in inputs.additional_artifacts})),
    )


def _pretty_model_bytes(model: ContentAddressedModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _write_exact(path: Path, encoded: bytes) -> None:
    mkdir_durable(path.parent)
    if path.exists():
        if path.read_bytes() != encoded:
            raise ValueError("durable scored attempt plan contains different bytes")
        return
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.read_bytes() != encoded:
                raise ValueError("durable scored attempt plan contains different bytes") from None
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _invocation_id(context: OperationExecutionContext) -> str:
    fanout = "" if context.fanout_index is None else f"-f{context.fanout_index}"
    return f"{safe_segment(context.node_id)}-a{context.attempt_index}{fanout}"


__all__ = (
    "RunBundleScoredAttemptPlan",
    "ScoredAttemptInputs",
    "build_scored_attempt_inputs",
    "dispatch_payload_sha256",
    "has_reservation_claim",
    "invocation_root_for",
    "invocation_workflow",
    "lower_scored_attempt",
    "safe_segment",
    "scored_attempt_preflight",
    "select_scored_attempt_plan",
)
