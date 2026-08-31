# ABOUTME: Assesses ordinary RunPlan executions at the governed-attempt lifecycle boundary.
# ABOUTME: Replays scored terminal evidence while preserving the historical assessment API.

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.harness_kernel import (
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.qualification.run_bundle_runtime import (
    MetaHarnessStudyContext,
    RunBundleExecution,
    execute_run_bundle,
    load_harbor_invocation_receipt,
)
from aec_bench.harness.governed_attempt import GovernedAttemptTerminal
from aec_bench.harness.governed_attempt.repository import GovernedAttemptRepository
from aec_bench.harness.harbor_dispatch import HarborCommandExecutor
from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry


class RunBundleGovernedAttemptBlocker(StrEnum):
    """Historical migration blockers retained only for schema compatibility."""

    EXACT_USAGE_UNAVAILABLE = "exact_usage_unavailable"
    LOSSLESS_IMPORT_REPLAY_UNAVAILABLE = "lossless_import_replay_unavailable"


class RunBundleGovernedAttemptBlockedError(RuntimeError):
    """Raised when a caller tries to treat the diagnostic bridge as executable."""

    def __init__(self, assessment: RunBundleGovernedAttemptAssessment) -> None:
        self.assessment = assessment
        blockers = ", ".join(item.value for item in assessment.blockers)
        super().__init__(f"RunPlan governed-attempt migration is blocked: {blockers}")


class RunBundleGovernedAttemptAssessment(ContentAddressedModel):
    """Content-bound proof that scored invocations reached governed terminals."""

    schema_version: Literal["aecbench.run-plan-governed-attempt-assessment.v3"] = (
        "aecbench.run-plan-governed-attempt-assessment.v3"
    )
    bundle_id: NonEmptyStr
    run_id: NonEmptyStr
    plan_commitment_sha256: str
    program_execution_sha256: str
    stage_receipt_sha256s: tuple[str, ...] = ()
    invocation_receipt_sha256s: tuple[str, ...] = ()
    governed_terminal_sha256s: tuple[str, ...] = ()
    ready: Literal[True] = True
    blockers: tuple[RunBundleGovernedAttemptBlocker, ...] = ()

    @field_validator(
        "plan_commitment_sha256",
        "program_execution_sha256",
    )
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "stage_receipt_sha256s",
        "invocation_receipt_sha256s",
        "governed_terminal_sha256s",
    )
    @classmethod
    def validate_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if value != tuple(sorted(set(value))):
            raise ValueError("RunPlan governed-attempt evidence hashes must be sorted and unique")
        return value

    @model_validator(mode="after")
    def validate_blockers(self) -> Self:
        if self.blockers:
            raise ValueError("ready RunPlan governed-attempt evidence cannot retain migration blockers")
        if len(self.governed_terminal_sha256s) != len(self.invocation_receipt_sha256s):
            raise ValueError("every scored RunPlan invocation requires one governed terminal")
        return self


@dataclass(frozen=True, slots=True)
class RunBundleGovernedAttemptBoundary:
    """One unchanged ordinary execution paired with its truthful migration assessment."""

    execution: RunBundleExecution
    assessment: RunBundleGovernedAttemptAssessment


def execute_run_bundle_with_governed_attempt_assessment(
    *,
    bundle: RunPlan,
    registry: KernelRuntimeRegistry,
    workflow: SynchronousHarborWorkflow,
    artifacts_root: Path,
    study: MetaHarnessStudyContext,
    executor: HarborCommandExecutor | None = None,
    authority_ledger: AuthorityLedger | None = None,
) -> RunBundleGovernedAttemptBoundary:
    """Run the ordinary entrypoint once and replay its governed scored terminals."""

    execution = execute_run_bundle(
        bundle=bundle,
        registry=registry,
        workflow=workflow,
        artifacts_root=artifacts_root,
        study=study,
        executor=executor,
        authority_ledger=authority_ledger,
    )
    return RunBundleGovernedAttemptBoundary(
        execution=execution,
        assessment=assess_run_bundle_governed_attempt(
            bundle=bundle,
            study=study,
            execution=execution,
        ),
    )


def assess_run_bundle_governed_attempt(
    *,
    bundle: RunPlan,
    study: MetaHarnessStudyContext,
    execution: RunBundleExecution,
) -> RunBundleGovernedAttemptAssessment:
    """Verify exact legacy and governed evidence before declaring parity ready."""

    if execution.program.program_ref != bundle.execution_program.ref:
        raise ValueError("RunPlan execution program differs from the assessed bundle")

    invocation_hashes: list[str] = []
    terminal_hashes: list[str] = []
    for invocation in execution.harbor_invocations:
        loaded = load_harbor_invocation_receipt(invocation.receipt.path)
        if (
            loaded != invocation.receipt.receipt
            or loaded.bundle_id != bundle.run_manifest.run_id
            or loaded.run_id != study.run_id
        ):
            raise ValueError("RunPlan invocation receipt differs from the assessed execution")
        invocation_hashes.append(invocation.receipt.reference.sha256)
        terminal = _load_governed_terminal(invocation.job_dir)
        expected_imported = {
            invocation.receipt.reference.sha256,
            *(item.sha256 for item in invocation.receipt.receipt.imported_trial_records),
        }
        if not expected_imported.issubset(terminal.imported_evidence_sha256s):
            raise ValueError("RunPlan governed terminal omits exact imported invocation evidence")
        terminal_hashes.append(canonical_json_sha256(terminal.model_dump(mode="json")))
    if len(invocation_hashes) != len(set(invocation_hashes)):
        raise ValueError("RunPlan execution contains duplicate invocation receipt evidence")

    stage_hashes = [item.receipt.reference.sha256 for item in execution.stage_executions]
    if len(stage_hashes) != len(set(stage_hashes)):
        raise ValueError("RunPlan execution contains duplicate stage receipt evidence")

    return RunBundleGovernedAttemptAssessment(
        bundle_id=bundle.run_manifest.run_id,
        run_id=study.run_id,
        plan_commitment_sha256=canonical_json_sha256(bundle.model_dump(mode="json")),
        program_execution_sha256=canonical_json_sha256(
            execution.program.model_dump(mode="json"),
        ),
        stage_receipt_sha256s=tuple(sorted(stage_hashes)),
        invocation_receipt_sha256s=tuple(sorted(invocation_hashes)),
        governed_terminal_sha256s=tuple(sorted(terminal_hashes)),
    )


def require_run_bundle_governed_attempt_ready(
    assessment: RunBundleGovernedAttemptAssessment,
) -> None:
    """Accept only the ready v2 assessment while retaining the historical call."""

    if not assessment.ready or assessment.blockers:
        raise RunBundleGovernedAttemptBlockedError(assessment)


def _load_governed_terminal(job_dir: Path) -> GovernedAttemptTerminal:
    invocation_root = Path(job_dir).resolve().parent.parent
    state_root = invocation_root / "governed-attempt-state"
    records = tuple((state_root / "governed-attempt" / "records" / "terminal").glob("*/record.json"))
    if len(records) != 1:
        raise ValueError("RunPlan scored invocation has no unique governed terminal record")
    candidate = GovernedAttemptTerminal.model_validate_json(records[0].read_bytes())
    repository = GovernedAttemptRepository(root=state_root, disjoint_roots=())
    terminal = repository.load_state(candidate.attempt_id).terminal
    if terminal is None:
        raise ValueError("RunPlan governed terminal cannot be replayed")
    return terminal
