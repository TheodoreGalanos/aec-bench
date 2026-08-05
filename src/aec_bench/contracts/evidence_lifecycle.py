# ABOUTME: Current document contracts for staged evidence lifecycle packages.
# ABOUTME: Keeps lifecycle validation independent from task catalogue topology.

from __future__ import annotations

import re
from pathlib import PurePosixPath

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class LifecycleTaskMetadata(StrictModel):
    template_id: NonEmptyStr
    name: NonEmptyStr
    discipline: NonEmptyStr


class EvidenceRequestSpec(StrictModel):
    request_id: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    prerequisite_request_ids: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_request_id(self) -> EvidenceRequestSpec:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.request_id) is None:
            raise ValueError("request_id must be a safe path segment")
        if len(self.prerequisite_request_ids) != len(set(self.prerequisite_request_ids)):
            raise ValueError("evidence request prerequisites must be unique")
        if self.request_id in self.prerequisite_request_ids:
            raise ValueError("evidence request cannot depend on itself")
        return self


class ConditionalEvidenceSpec(StrictModel):
    request_budget: PositiveInt
    requests: tuple[EvidenceRequestSpec, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_request_graph(self) -> ConditionalEvidenceSpec:
        request_ids = [request.request_id for request in self.requests]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("evidence request ids must be unique per checkpoint")
        if self.request_budget > len(request_ids):
            raise ValueError("evidence request budget cannot exceed the number of requests")

        known = set(request_ids)
        prerequisites = {request.request_id: set(request.prerequisite_request_ids) for request in self.requests}
        for request_id, dependencies in prerequisites.items():
            unknown = dependencies - known
            if unknown:
                names = ", ".join(sorted(unknown))
                raise ValueError(f"evidence request prerequisites are unknown for {request_id}: {names}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(request_id: str) -> None:
            if request_id in visiting:
                raise ValueError("evidence request prerequisites must not contain cycles")
            if request_id in visited:
                return
            visiting.add(request_id)
            for dependency in prerequisites[request_id]:
                visit(dependency)
            visiting.remove(request_id)
            visited.add(request_id)

        for request_id in request_ids:
            visit(request_id)

        prerequisite_closures: dict[str, set[str]] = {}

        def prerequisite_closure(request_id: str) -> set[str]:
            cached = prerequisite_closures.get(request_id)
            if cached is not None:
                return cached
            closure: set[str] = set()
            for dependency in prerequisites[request_id]:
                closure.add(dependency)
                closure.update(prerequisite_closure(dependency))
            prerequisite_closures[request_id] = closure
            return closure

        for request_id in request_ids:
            required_budget = len(prerequisite_closure(request_id)) + 1
            if required_budget > self.request_budget:
                raise ValueError(
                    f"evidence request budget cannot satisfy prerequisites for {request_id}: "
                    f"requires {required_budget} requests"
                )
        return self


class LifecycleOperationSpec(StrictModel):
    operation_id: NonEmptyStr
    kind: NonEmptyStr
    title: NonEmptyStr
    description: NonEmptyStr
    prerequisite_operation_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("operation_id", "kind")
    @classmethod
    def validate_safe_identity(cls, value: str) -> str:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", value) is None:
            raise ValueError("operation identity must be a safe path segment")
        return value

    @model_validator(mode="after")
    def validate_prerequisites(self) -> LifecycleOperationSpec:
        if len(self.prerequisite_operation_ids) != len(set(self.prerequisite_operation_ids)):
            raise ValueError("operation prerequisites must be unique")
        if self.operation_id in self.prerequisite_operation_ids:
            raise ValueError("operation cannot depend on itself")
        return self


class ConditionalOperationSpec(StrictModel):
    operation_budget: PositiveInt
    operations: tuple[LifecycleOperationSpec, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_operation_graph(self) -> ConditionalOperationSpec:
        operation_ids = [operation.operation_id for operation in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("operation ids must be unique per checkpoint")
        if self.operation_budget > len(operation_ids):
            raise ValueError("operation budget cannot exceed the number of operations")

        known = set(operation_ids)
        prerequisites = {
            operation.operation_id: set(operation.prerequisite_operation_ids) for operation in self.operations
        }
        for operation_id, dependencies in prerequisites.items():
            unknown = dependencies - known
            if unknown:
                names = ", ".join(sorted(unknown))
                raise ValueError(f"operation prerequisites are unknown for {operation_id}: {names}")

        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(operation_id: str) -> None:
            if operation_id in visiting:
                raise ValueError("operation prerequisites must not contain cycles")
            if operation_id in visited:
                return
            visiting.add(operation_id)
            for dependency in prerequisites[operation_id]:
                visit(dependency)
            visiting.remove(operation_id)
            visited.add(operation_id)

        for operation_id in operation_ids:
            visit(operation_id)

        prerequisite_closures: dict[str, set[str]] = {}

        def prerequisite_closure(operation_id: str) -> set[str]:
            cached = prerequisite_closures.get(operation_id)
            if cached is not None:
                return cached
            closure: set[str] = set()
            for dependency in prerequisites[operation_id]:
                closure.add(dependency)
                closure.update(prerequisite_closure(dependency))
            prerequisite_closures[operation_id] = closure
            return closure

        for operation_id in operation_ids:
            required_budget = len(prerequisite_closure(operation_id)) + 1
            if required_budget > self.operation_budget:
                raise ValueError(
                    f"operation budget cannot satisfy prerequisites for {operation_id}: "
                    f"requires {required_budget} operations"
                )
        return self


class EvidenceCheckpointSpec(StrictModel):
    checkpoint_id: NonEmptyStr
    title: NonEmptyStr
    release_path: NonEmptyStr
    instruction_path: NonEmptyStr
    submission_path: NonEmptyStr
    depends_on: list[NonEmptyStr] = Field(default_factory=list)
    required_submission_fields: list[NonEmptyStr] = Field(default_factory=lambda: ["checkpoint_id"])
    allow_additional_submission_fields: bool = True
    conditional_evidence: ConditionalEvidenceSpec | None = None
    conditional_operations: ConditionalOperationSpec | None = None

    @model_validator(mode="after")
    def validate_package_paths(self) -> EvidenceCheckpointSpec:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", self.checkpoint_id) is None:
            raise ValueError("checkpoint_id must be a safe path segment")

        namespaces = {
            "release_path": "releases",
            "instruction_path": "instructions",
            "submission_path": "submissions",
        }
        for field_name, namespace in namespaces.items():
            raw_path = getattr(self, field_name)
            path = PurePosixPath(raw_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"{field_name} must stay within the lifecycle package")
            if len(path.parts) < 2 or path.parts[0] != namespace:
                raise ValueError(f"{field_name} must be under {namespace}/")
        if PurePosixPath(self.instruction_path).suffix != ".md":
            raise ValueError("instruction_path must name a Markdown file")
        if PurePosixPath(self.submission_path).suffix != ".json":
            raise ValueError("submission_path must name a JSON file")
        if len(self.required_submission_fields) != len(set(self.required_submission_fields)):
            raise ValueError("required submission fields must be unique")
        if not self.allow_additional_submission_fields and "checkpoint_id" not in self.required_submission_fields:
            raise ValueError("exact submission fields must include checkpoint_id")
        if self.conditional_evidence is not None and self.conditional_operations is not None:
            raise ValueError("checkpoint must not declare both evidence requests and lifecycle operations")
        return self


class EvidenceLifecycleSpec(StrictModel):
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    checkpoints: list[EvidenceCheckpointSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_checkpoint_graph(self) -> EvidenceLifecycleSpec:
        checkpoint_ids = [checkpoint.checkpoint_id for checkpoint in self.checkpoints]
        if len(checkpoint_ids) != len(set(checkpoint_ids)):
            raise ValueError("checkpoint ids must be unique")

        submission_paths = [checkpoint.submission_path for checkpoint in self.checkpoints]
        if len(submission_paths) != len(set(submission_paths)):
            raise ValueError("submission paths must be unique")

        previous: set[str] = set()
        for checkpoint in self.checkpoints:
            unknown = set(checkpoint.depends_on) - previous
            if unknown:
                names = ", ".join(sorted(unknown))
                raise ValueError(f"checkpoint dependencies must refer to earlier checkpoints: {names}")
            previous.add(checkpoint.checkpoint_id)
        supports_evidence = any(checkpoint.conditional_evidence is not None for checkpoint in self.checkpoints)
        supports_operations = any(checkpoint.conditional_operations is not None for checkpoint in self.checkpoints)
        if supports_evidence and supports_operations:
            raise ValueError("lifecycle must not mix evidence-request and operation protocols")
        return self
