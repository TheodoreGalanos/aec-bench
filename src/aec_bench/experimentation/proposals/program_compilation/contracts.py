# ABOUTME: Defines the content-addressed proposal session bundle emitted by compilation.
# ABOUTME: Validates exact profile, harness, task, operation, and scheduling bindings.

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from aec_bench.contracts.harness_instance import CompiledHarnessInstance, ProgramOperationRef
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationSuccess
from aec_bench.contracts.proposal_execution.session import ProposalSessionPlan
from aec_bench.contracts.proposal_execution_types import ProposalExecutionSemantics
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.harness.compilation.task_snapshot import (
    TaskSnapshotError,
    graph_hidden_task_snapshot_sha256,
)

from .constants import _SESSION_OPERATION_ID


class ProposalRunSessionBundle(LegacyContentAddressedModel):
    """Provider-free wrapper binding compilation evidence to the fixed session operation."""

    schema_version: Literal["aecbench.proposal-run-session-bundle.v1"] = "aecbench.proposal-run-session-bundle.v1"
    bundle_id: NonEmptyStr
    compilation: ProposalCompilationSuccess
    session_plan: ProposalSessionPlan
    fixed_harness: CompiledHarnessInstance
    task_snapshot: TaskSnapshotRef
    session_operation_ref: ProgramOperationRef
    execution_semantics: ProposalExecutionSemantics = ProposalExecutionSemantics.SEQUENTIAL_DATAFLOW

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        execution_profile = self.compilation.execution_profile
        if execution_profile is None:
            raise ValueError("proposal session execution requires a profile-bound compilation")
        if self.session_plan.compilation != self.compilation:
            raise ValueError("proposal session plan does not bind the exact compilation")
        if self.fixed_harness.ref != self.compilation.fixed_harness_ref:
            raise ValueError("proposal session bundle does not carry the exact frozen harness")
        try:
            task_snapshot_sha256 = graph_hidden_task_snapshot_sha256(self.task_snapshot)
        except TaskSnapshotError as error:
            raise ValueError(f"proposal session bundle carries an invalid task snapshot: {error}") from error
        if task_snapshot_sha256 != self.compilation.task_snapshot_sha256:
            raise ValueError("proposal session bundle task snapshot differs from the compilation")
        problem_view = self.compilation.proposal_freeze.problem_view
        source_manifest = self.compilation.source_scope_manifest
        if (
            self.task_snapshot.task_id != problem_view.task_id
            or self.task_snapshot.definition_sha256 != problem_view.task_revision
            or self.task_snapshot.package_sha256 != source_manifest.task_package_sha256
        ):
            raise ValueError("proposal session bundle task snapshot differs from the frozen task identity")
        session_constraint = execution_profile.operation(_SESSION_OPERATION_ID)
        if session_constraint is None or self.session_operation_ref.operation_id != session_constraint.operation_id:
            raise ValueError("proposal session bundle requires its profiled session operation")
        session_operation = self.fixed_harness.program_surface.operation(self.session_operation_ref.operation_id)
        if (
            session_operation is None
            or session_operation.ref != self.session_operation_ref
            or session_operation.capability_ref != session_constraint.capability_ref
            or session_operation.max_parallelism != session_constraint.max_parallelism
            or session_operation.supports_retry is not session_constraint.supports_retry
            or session_operation.retry_safe_error_codes != session_constraint.retry_safe_error_codes
            or session_operation.supports_recursion is not session_constraint.supports_recursion
            or session_operation.required_compilation_scope is not session_constraint.required_scope
        ):
            raise ValueError("proposal session operation does not resolve on the exact frozen harness surface")
        if (
            self.compilation.budget_plan.execution_semantics is not self.execution_semantics
            or self.execution_semantics.value != execution_profile.scheduling.semantics.value
        ):
            raise ValueError("proposal session semantics do not match the candidate budget plan")
        return self
