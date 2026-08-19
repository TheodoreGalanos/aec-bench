# ABOUTME: Defines plain internal run plans and their single published package envelope.
# ABOUTME: Embeds run-owned configuration while task, review, trial, and authority evidence keep distinct owners.

from __future__ import annotations

from typing import Literal, Self

from pydantic import model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.execution_program import (
    ActionNode,
    CompiledExecutionProgram,
    FanoutNode,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ComputeBindingConfig,
    ProgramOperationSpec,
    ResultImportBindingConfig,
    TaskSourceBindingConfig,
    VerificationBindingConfig,
)
from aec_bench.contracts.task_review_snapshot import ReviewSnapshot
from aec_bench.contracts.task_snapshot import TaskSnapshotRef, task_snapshot_id
from aec_bench.contracts.trial_record import RunManifest
from aec_bench.contracts.validators import FrozenStrictModel


class RunPlan(FrozenStrictModel):
    """One internal execution plan with no self-digest or parallel package identity."""

    run_manifest: RunManifest
    task_snapshots: tuple[TaskSnapshotRef, ...]
    harness: CompiledHarnessInstance
    execution_program: CompiledExecutionProgram
    review: ReviewSnapshot | ArtifactRef | None = None

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        invoked_operations = self._resolve_invoked_operations()
        self._validate_contract_relationships()
        self._validate_program_budget()
        self._validate_recursive_nodes()
        self._validate_task_snapshots()
        self._validate_invoked_task_scope(invoked_operations)
        self._validate_binding_wiring(invoked_operations)
        self._validate_required_verifiers(invoked_operations)
        self._validate_provider_composition()
        self._validate_review()
        return self

    def _validate_contract_relationships(self) -> None:
        if self.execution_program.harness_ref != self.harness.ref:
            raise ValueError("execution program does not target the embedded harness")
        if self.execution_program.surface_id != self.harness.program_surface.surface_id:
            raise ValueError("execution program surface does not match the embedded harness surface")

    def _resolve_invoked_operations(self) -> tuple[ProgramOperationSpec, ...]:
        invoked_operations: list[ProgramOperationSpec] = []
        for reference in self.execution_program.operation_refs:
            operation = self.harness.program_surface.resolve_operation(reference)
            if operation is None:
                raise ValueError(
                    f"execution program operation {reference.operation_id!r} does not resolve "
                    "against the embedded harness surface"
                )
            invoked_operations.append(operation)
        return tuple(invoked_operations)

    def _validate_program_budget(self) -> None:
        if self.execution_program.limits.max_parallelism > self.harness.budget.max_parallelism:
            raise ValueError("execution program parallelism exceeds the harness budget")
        if self.execution_program.limits.max_total_attempts > self.harness.budget.max_total_attempts:
            raise ValueError("execution program attempts exceed the harness budget")

    def _validate_task_snapshots(self) -> None:
        snapshot_ids = tuple(task_snapshot_id(snapshot) for snapshot in self.task_snapshots)
        if not snapshot_ids:
            raise ValueError("run plan must include at least one task snapshot")
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("task snapshot ids must be unique")
        bound_task_ids = tuple(
            task_ref
            for binding in self.harness.bindings
            if isinstance(binding.configuration, TaskSourceBindingConfig)
            for task_ref in binding.configuration.task_refs
        )
        if snapshot_ids != bound_task_ids:
            raise ValueError("task snapshots must exactly match the harness task-source bindings")

    def _validate_invoked_task_scope(self, invoked_operations: tuple[ProgramOperationSpec, ...]) -> None:
        task_ids = {task_snapshot_id(snapshot) for snapshot in self.task_snapshots}
        invoked_task_ids = {task_ref for operation in invoked_operations for task_ref in operation.allowed_task_refs}
        outside_surface = sorted(task_ids - invoked_task_ids)
        if outside_surface:
            raise ValueError(
                "run plan tasks are outside the invoked harness program surface: " + ", ".join(outside_surface)
            )

    def _validate_binding_wiring(self, invoked_operations: tuple[ProgramOperationSpec, ...]) -> None:
        invoked_binding_ids = {binding_id for operation in invoked_operations for binding_id in operation.binding_ids}
        required_binding_ids = {
            binding.binding_id
            for binding in self.harness.bindings
            if isinstance(
                binding.configuration,
                AgentBindingConfig | ComputeBindingConfig | ResultImportBindingConfig,
            )
        }
        unwired = sorted(required_binding_ids - invoked_binding_ids)
        if unwired:
            raise ValueError("required harness bindings are outside invoked operations: " + ", ".join(unwired))

    def _validate_required_verifiers(self, invoked_operations: tuple[ProgramOperationSpec, ...]) -> None:
        required_verifier_ids = {
            placement.binding_id
            for operation in invoked_operations
            for placement in operation.verifier_placements
            if placement.required
        }
        available_verifier_ids = {
            binding.binding_id
            for binding in self.harness.bindings
            if isinstance(binding.configuration, VerificationBindingConfig) and binding.configuration.enabled
        }
        missing = sorted(required_verifier_ids - available_verifier_ids)
        if missing:
            raise ValueError("required verifier placements are unavailable: " + ", ".join(missing))

    def _validate_provider_composition(self) -> None:
        agent_bindings = tuple(
            binding for binding in self.harness.bindings if isinstance(binding.configuration, AgentBindingConfig)
        )
        compute_bindings = tuple(
            binding for binding in self.harness.bindings if isinstance(binding.configuration, ComputeBindingConfig)
        )
        if len(agent_bindings) != 1 or len(compute_bindings) != 1:
            raise ValueError("run plan requires one agent binding and one compute binding")
        agent = agent_bindings[0]
        assert isinstance(agent.configuration, AgentBindingConfig)
        compute = compute_bindings[0]
        if self.run_manifest.agent.adapter not in {
            agent.configuration.agent_name,
            agent.capability_ref.capability_id,
        }:
            raise ValueError("run manifest agent adapter is incompatible with the harness agent binding")
        if self.run_manifest.agent.model != agent.configuration.model:
            raise ValueError("run manifest model does not match the harness agent binding")
        if self.run_manifest.provider_route.route != compute.capability_ref.capability_id:
            raise ValueError("run manifest provider route is incompatible with the harness compute binding")

    def _validate_review(self) -> None:
        if not isinstance(self.review, ReviewSnapshot):
            return
        snapshot_ids = {task_snapshot_id(snapshot) for snapshot in self.task_snapshots}
        review_ids = {review.task_id for review in self.review.tasks}
        outside = sorted(review_ids - snapshot_ids)
        if outside:
            raise ValueError("review snapshot contains tasks outside the run plan: " + ", ".join(outside))

    def _validate_recursive_nodes(self) -> None:
        recursive_nodes = [
            node
            for node in self.execution_program.nodes
            if isinstance(node, ActionNode | FanoutNode) and node.recursion is not None
        ]
        policy = self.harness.recursion_policy
        if recursive_nodes and not policy.enabled:
            raise ValueError("recursive execution program nodes require enabled harness recursion")
        for recursive_node in recursive_nodes:
            assert recursive_node.recursion is not None
            if (
                recursive_node.recursion.max_depth > policy.max_depth
                or recursive_node.recursion.max_calls > policy.max_calls
            ):
                raise ValueError("execution program recursion exceeds the harness policy")
            operation = self.harness.program_surface.operation(recursive_node.operation_id)
            if operation is None or not operation.supports_recursion:
                raise ValueError(f"execution program operation {recursive_node.operation_id!r} cannot recurse")
            if not set(operation.binding_ids).intersection(policy.allowed_binding_ids):
                raise ValueError(
                    f"execution program operation {recursive_node.operation_id!r} is outside the "
                    "harness recursion binding allowlist"
                )

        for candidate_node in self.execution_program.nodes:
            if isinstance(candidate_node, ActionNode | FanoutNode | VerifyNode) and candidate_node.retry is not None:
                operation = self.harness.program_surface.operation(candidate_node.operation_id)
                if operation is None or not operation.supports_retry:
                    raise ValueError(f"execution program operation {candidate_node.operation_id!r} cannot retry")
                unsafe_retry_codes = tuple(
                    error_code
                    for error_code in candidate_node.retry.retry_on
                    if error_code not in operation.retry_safe_error_codes
                )
                if unsafe_retry_codes:
                    raise ValueError(
                        f"execution program node {candidate_node.node_id!r} retries unsafe error codes: "
                        + ", ".join(unsafe_retry_codes)
                    )


class PublishedRunPackage(FrozenStrictModel):
    """One versioned run plan and its exact retained trial records."""

    schema_version: Literal[1] = 1
    run_plan: RunPlan
    trial_refs: tuple[ArtifactRef, ...] = ()

    @model_validator(mode="after")
    def validate_trials(self) -> PublishedRunPackage:
        trial_ids = tuple((reference.sha256, reference.size_bytes) for reference in self.trial_refs)
        if len(trial_ids) != len(set(trial_ids)):
            raise ValueError("published run package trial references must be unique")
        return self


__all__ = (
    "PublishedRunPackage",
    "RunPlan",
)
