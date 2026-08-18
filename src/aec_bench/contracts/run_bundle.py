# ABOUTME: Defines the immutable execution bundle that binds fixed K, compiled Hx, and compiled px.
# ABOUTME: Carries only typed Harbor lowering data and content-pinned task snapshots, never target settings.

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import (
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

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
from aec_bench.contracts.harness_kernel import FrozenStrictModel, KernelRef, validate_sha256
from aec_bench.contracts.stage_execution import DeclaredStageGraph
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.validators import NonEmptyStr


class RunTarget(StrEnum):
    """Trusted runtime lowering targets supported by a RunBundle."""

    HARBOR = "harbor"


class TaskReviewSnapshotRef(FrozenStrictModel):
    """Content-pinned identity for one task-review profile and its declared surface."""

    profile_id: NonEmptyStr
    review_profile_sha256: str
    review_sidecar_sha256: str
    declared_surface_sha256: str
    visibility: Visibility
    stage_graph: DeclaredStageGraph | None = None

    @field_validator(
        "review_profile_sha256",
        "review_sidecar_sha256",
        "declared_surface_sha256",
    )
    @classmethod
    def validate_sha256_fields(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_stage_graph(self) -> Self:
        if self.stage_graph is not None and self.stage_graph.review_sidecar_sha256 != self.review_sidecar_sha256:
            raise ValueError("declared stage graph does not match task-review sidecar bytes")
        return self

    @model_serializer(mode="wrap")
    def serialize_task_review_snapshot(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("task-review snapshot serialization must produce an object")
        if self.stage_graph is None:
            payload.pop("stage_graph", None)
        return payload


class TaskSnapshotRef(FrozenStrictModel):
    """Content-pinned task definition and complete runnable package."""

    task_id: NonEmptyStr
    definition_sha256: str
    package_sha256: str
    task_review: TaskReviewSnapshotRef | None = None

    @field_validator("definition_sha256", "package_sha256")
    @classmethod
    def validate_sha256_fields(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_task_review(self) -> Self:
        if (
            self.task_review is not None
            and self.task_review.stage_graph is not None
            and self.task_review.stage_graph.task_id != self.task_id
        ):
            raise ValueError("declared stage graph does not match task snapshot id")
        return self


class HarborRunPayload(FrozenStrictModel):
    """Closed Harbor lowering payload whose runtime choices point back into Hx."""

    experiment_id: NonEmptyStr
    task_refs: tuple[NonEmptyStr, ...]
    agent_binding_id: NonEmptyStr
    compute_binding_id: NonEmptyStr
    verification_binding_id: NonEmptyStr | None = None
    result_import_binding_id: NonEmptyStr
    repetitions: int = Field(default=1, ge=1, le=1_000)

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("Harbor run payload must include at least one task ref")
        if len(value) != len(set(value)):
            raise ValueError("Harbor run task refs must be unique")
        return value


class RunBundle(FrozenStrictModel):
    """Executable K/Hx/px package for one trusted runtime target."""

    bundle_id: NonEmptyStr
    kernel_ref: KernelRef
    harness: CompiledHarnessInstance
    program: CompiledExecutionProgram
    target: RunTarget = RunTarget.HARBOR
    task_snapshots: tuple[TaskSnapshotRef, ...]
    harbor: HarborRunPayload

    @model_validator(mode="after")
    def validate_bundle(self) -> Self:
        self._validate_contract_identity()
        invoked_operations = self._resolve_invoked_operations()
        self._validate_program_budget()
        self._validate_recursive_nodes()
        self._validate_task_snapshots()
        self._validate_invoked_task_scope(invoked_operations)
        self._validate_selected_binding_wiring(invoked_operations)
        self._validate_required_verifiers(invoked_operations)
        self._validate_harbor_binding_roles()
        return self

    def _validate_contract_identity(self) -> None:
        if self.kernel_ref != self.harness.kernel_ref:
            raise ValueError("bundle kernel_ref does not match compiled harness kernel_ref")
        if self.program.harness_ref != self.harness.ref:
            raise ValueError("program harness_ref does not match bundled harness")
        if self.program.surface_id != self.harness.program_surface.surface_id:
            raise ValueError("program surface_id does not match bundled harness program surface")

    def _resolve_invoked_operations(self) -> tuple[ProgramOperationSpec, ...]:
        invoked_operations: list[ProgramOperationSpec] = []
        for reference in self.program.operation_refs:
            operation = self.harness.program_surface.resolve_operation(reference)
            if operation is None:
                raise ValueError(
                    f"program operation ref {reference.operation_id!r} does not resolve "
                    "against the bundled harness surface"
                )
            invoked_operations.append(operation)
        return tuple(invoked_operations)

    def _validate_program_budget(self) -> None:
        if self.program.limits.max_parallelism > self.harness.budget.max_parallelism:
            raise ValueError("program parallelism limit exceeds bundled harness budget")
        if self.program.limits.max_total_attempts > self.harness.budget.max_total_attempts:
            raise ValueError("program attempt limit exceeds bundled harness budget")

    def _validate_task_snapshots(self) -> None:
        snapshot_ids = tuple(snapshot.task_id for snapshot in self.task_snapshots)
        if len(snapshot_ids) != len(set(snapshot_ids)):
            raise ValueError("task snapshot ids must be unique")
        if snapshot_ids != self.harbor.task_refs:
            raise ValueError("task snapshots must exactly match Harbor task_refs")

    def _validate_invoked_task_scope(self, invoked_operations: tuple[ProgramOperationSpec, ...]) -> None:
        invoked_task_refs = {task_ref for operation in invoked_operations for task_ref in operation.allowed_task_refs}
        outside_surface = sorted(set(self.harbor.task_refs) - invoked_task_refs)
        if outside_surface:
            raise ValueError(
                "Harbor task refs outside the harness program surface invoked by px: " + ", ".join(outside_surface)
            )

        bound_task_refs = {
            task_ref
            for binding in self.harness.bindings
            if isinstance(binding.configuration, TaskSourceBindingConfig)
            for task_ref in binding.configuration.task_refs
        }
        outside_bindings = sorted(set(self.harbor.task_refs) - bound_task_refs)
        if outside_bindings:
            raise ValueError(
                "Harbor task refs outside the harness task-source bindings: " + ", ".join(outside_bindings)
            )

    def _validate_selected_binding_wiring(
        self,
        invoked_operations: tuple[ProgramOperationSpec, ...],
    ) -> None:
        invoked_binding_ids = {binding_id for operation in invoked_operations for binding_id in operation.binding_ids}
        selected_binding_ids = {
            self.harbor.agent_binding_id,
            self.harbor.compute_binding_id,
            self.harbor.result_import_binding_id,
        }
        if self.harbor.verification_binding_id is not None:
            selected_binding_ids.add(self.harbor.verification_binding_id)
        unwired_binding_ids = sorted(selected_binding_ids - invoked_binding_ids)
        if unwired_binding_ids:
            raise ValueError(
                "selected Harbor binding ids outside invoked operations: " + ", ".join(unwired_binding_ids)
            )

    def _validate_required_verifiers(
        self,
        invoked_operations: tuple[ProgramOperationSpec, ...],
    ) -> None:
        required_verifier_ids = {
            placement.binding_id
            for operation in invoked_operations
            for placement in operation.verifier_placements
            if placement.required
        }
        selected_verifier_ids = (
            {self.harbor.verification_binding_id} if self.harbor.verification_binding_id is not None else set()
        )
        if required_verifier_ids != selected_verifier_ids and required_verifier_ids:
            raise ValueError(
                "Harbor verification binding must satisfy required invoked verifier placements: "
                + ", ".join(sorted(required_verifier_ids))
            )

    def _validate_harbor_binding_roles(self) -> None:
        self._validate_binding_role(
            field_name="agent_binding_id",
            binding_id=self.harbor.agent_binding_id,
            configuration_type=AgentBindingConfig,
            role="agent",
        )
        self._validate_binding_role(
            field_name="compute_binding_id",
            binding_id=self.harbor.compute_binding_id,
            configuration_type=ComputeBindingConfig,
            role="compute",
        )
        if self.harbor.verification_binding_id is not None:
            self._validate_binding_role(
                field_name="verification_binding_id",
                binding_id=self.harbor.verification_binding_id,
                configuration_type=VerificationBindingConfig,
                role="verification",
            )
        self._validate_binding_role(
            field_name="result_import_binding_id",
            binding_id=self.harbor.result_import_binding_id,
            configuration_type=ResultImportBindingConfig,
            role="result-import",
        )

    def _validate_recursive_nodes(self) -> None:
        recursive_nodes = [
            node
            for node in self.program.nodes
            if isinstance(node, ActionNode | FanoutNode) and node.recursion is not None
        ]
        policy = self.harness.recursion_policy
        if recursive_nodes and not policy.enabled:
            raise ValueError("recursive program nodes require enabled harness recursion")
        for recursive_node in recursive_nodes:
            assert recursive_node.recursion is not None
            if (
                recursive_node.recursion.max_depth > policy.max_depth
                or recursive_node.recursion.max_calls > policy.max_calls
            ):
                raise ValueError("program recursion exceeds bundled harness recursion policy")
            operation = self.harness.program_surface.operation(recursive_node.operation_id)
            if operation is None or not operation.supports_recursion:
                raise ValueError(f"program operation {recursive_node.operation_id!r} does not support recursion")
            if not set(operation.binding_ids).intersection(policy.allowed_binding_ids):
                raise ValueError(
                    f"program operation {recursive_node.operation_id!r} is outside the "
                    "harness recursion binding allowlist"
                )

        for candidate_node in self.program.nodes:
            if isinstance(candidate_node, ActionNode | FanoutNode | VerifyNode) and candidate_node.retry is not None:
                operation = self.harness.program_surface.operation(candidate_node.operation_id)
                if operation is None or not operation.supports_retry:
                    raise ValueError(f"program operation {candidate_node.operation_id!r} does not support retry")
                unsafe_retry_codes = tuple(
                    error_code
                    for error_code in candidate_node.retry.retry_on
                    if error_code not in operation.retry_safe_error_codes
                )
                if unsafe_retry_codes:
                    raise ValueError(
                        f"program node {candidate_node.node_id!r} retries error codes outside the "
                        "operation retry-safe error codes: " + ", ".join(unsafe_retry_codes)
                    )

    def _validate_binding_role(
        self,
        *,
        field_name: str,
        binding_id: str,
        configuration_type: type[FrozenStrictModel],
        role: str,
    ) -> None:
        binding = self.harness.binding(binding_id)
        if binding is None or not isinstance(binding.configuration, configuration_type):
            raise ValueError(f"{field_name} must reference an {role} binding")
