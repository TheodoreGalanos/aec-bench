# ABOUTME: Defines content-addressed declared-stage graphs and intermediate execution receipts.
# ABOUTME: Binds deterministic artifact routing, parsed outputs, resource usage, and physical evidence.

from __future__ import annotations

from collections import defaultdict
from typing import Any, Literal, Self

from pydantic import Field, JsonValue, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr


class DeclaredStage(FrozenStrictModel):
    """One reward-blind stage declared by a task-world package."""

    stage_id: NonEmptyStr
    title: NonEmptyStr | None = None
    discipline: NonEmptyStr | None = None
    consumes: tuple[NonEmptyStr, ...] = ()
    produces: tuple[NonEmptyStr, ...] = ()
    branch_decision_ids: tuple[NonEmptyStr, ...] = ()
    verifier_gate_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("consumes", "produces", "branch_decision_ids", "verifier_gate_ids")
    @classmethod
    def validate_unique_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("declared stage artifact and decision ids must be unique")
        return value


class DeclaredHandoff(FrozenStrictModel):
    """One explicit stage-to-stage artifact route declared by a task world."""

    handoff_id: NonEmptyStr
    producer_stage_id: NonEmptyStr
    consumer_stage_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("consumer_stage_ids")
    @classmethod
    def validate_consumers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("declared handoff consumers must be unique")
        return value


class DeclaredStageRoute(FrozenStrictModel):
    """Derived internal route between two declared stages."""

    producer_stage_id: NonEmptyStr
    consumer_stage_id: NonEmptyStr
    artifact_ids: tuple[NonEmptyStr, ...]

    @field_validator("artifact_ids")
    @classmethod
    def validate_artifact_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("declared stage route must include at least one artifact id")
        if len(value) != len(set(value)):
            raise ValueError("declared stage route artifact ids must be unique")
        if value != tuple(sorted(value)):
            raise ValueError("declared stage route artifact ids must be sorted")
        return value


class DeclaredStageGraph(ContentAddressedModel):
    """Content-pinned executable projection of a task world's declared stage graph."""

    schema_version: Literal["aecbench.declared-stage-graph.v1"] = "aecbench.declared-stage-graph.v1"
    task_id: NonEmptyStr
    world_package_sha256: str
    stages: tuple[DeclaredStage, ...] = Field(min_length=1)
    handoffs: tuple[DeclaredHandoff, ...] = ()

    @field_validator("world_package_sha256")
    @classmethod
    def validate_world_package_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        stage_ids = tuple(stage.stage_id for stage in self.stages)
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("declared stage ids must be unique")
        handoff_ids = tuple(handoff.handoff_id for handoff in self.handoffs)
        if len(handoff_ids) != len(set(handoff_ids)):
            raise ValueError("declared handoff ids must be unique")

        known_stage_ids = set(stage_ids)
        for handoff in self.handoffs:
            if handoff.producer_stage_id not in known_stage_ids:
                raise ValueError("declared handoff producer references an unknown stage")
            unknown_consumers = set(handoff.consumer_stage_ids) - known_stage_ids
            if unknown_consumers:
                raise ValueError("declared handoff consumer references an unknown stage")
            if handoff.producer_stage_id in handoff.consumer_stage_ids:
                raise ValueError("declared handoff cannot route an artifact to its producer")

        self._artifact_producers()
        self._derive_topological_order()
        return self

    @property
    def routes(self) -> tuple[DeclaredStageRoute, ...]:
        """Return the deterministic union of consumes-based and explicit handoff routes."""
        producers = self._artifact_producers()
        routed: dict[tuple[str, str], set[str]] = defaultdict(set)
        for consumer in self.stages:
            for artifact_id in consumer.consumes:
                producer = producers.get(artifact_id)
                if producer is not None and producer != consumer.stage_id:
                    routed[(producer, consumer.stage_id)].add(artifact_id)
        for handoff in self.handoffs:
            for consumer_stage_id in handoff.consumer_stage_ids:
                routed[(handoff.producer_stage_id, consumer_stage_id)].add(handoff.handoff_id)
        return tuple(
            DeclaredStageRoute(
                producer_stage_id=producer,
                consumer_stage_id=consumer,
                artifact_ids=tuple(sorted(artifact_ids)),
            )
            for (producer, consumer), artifact_ids in sorted(routed.items())
        )

    @property
    def topological_order(self) -> tuple[str, ...]:
        """Return a stable stage order, preserving declaration order between ready stages."""
        return self._derive_topological_order()

    def stage(self, stage_id: str) -> DeclaredStage | None:
        """Resolve one declared stage by id."""
        return next((stage for stage in self.stages if stage.stage_id == stage_id), None)

    def predecessor_stage_ids(self, stage_id: str) -> tuple[str, ...]:
        """Return all internal producers required by one declared stage."""
        if self.stage(stage_id) is None:
            raise ValueError(f"unknown declared stage: {stage_id}")
        predecessors = {route.producer_stage_id for route in self.routes if route.consumer_stage_id == stage_id}
        return tuple(candidate for candidate in self.topological_order if candidate in predecessors)

    def routed_artifact_ids(self, producer_stage_id: str, consumer_stage_id: str) -> tuple[str, ...]:
        """Return exact artifact ids routed across one internal stage edge."""
        route = next(
            (
                candidate
                for candidate in self.routes
                if candidate.producer_stage_id == producer_stage_id and candidate.consumer_stage_id == consumer_stage_id
            ),
            None,
        )
        return route.artifact_ids if route is not None else ()

    def required_output_ids(self, stage_id: str) -> tuple[str, ...]:
        """Return all outputs a stage receipt must bind before it can be consumed."""
        stage = self.stage(stage_id)
        if stage is None:
            raise ValueError(f"unknown declared stage: {stage_id}")
        handoff_ids = {handoff.handoff_id for handoff in self.handoffs if handoff.producer_stage_id == stage_id}
        return tuple(sorted(set(stage.produces) | handoff_ids))

    def _artifact_producers(self) -> dict[str, str]:
        producers: dict[str, str] = {}
        for stage in self.stages:
            for artifact_id in stage.produces:
                existing = producers.get(artifact_id)
                if existing is not None and existing != stage.stage_id:
                    raise ValueError("declared stage outputs must have one producer")
                producers[artifact_id] = stage.stage_id
        for handoff in self.handoffs:
            existing = producers.get(handoff.handoff_id)
            if existing is not None and existing != handoff.producer_stage_id:
                raise ValueError("declared stage outputs must have one producer")
            producers[handoff.handoff_id] = handoff.producer_stage_id
        return producers

    def _derive_topological_order(self) -> tuple[str, ...]:
        stage_order = tuple(stage.stage_id for stage in self.stages)
        dependencies: dict[str, set[str]] = {stage_id: set() for stage_id in stage_order}
        for route in self.routes:
            dependencies[route.consumer_stage_id].add(route.producer_stage_id)

        remaining = {stage_id: set(values) for stage_id, values in dependencies.items()}
        order: list[str] = []
        while remaining:
            ready = tuple(stage_id for stage_id in stage_order if stage_id in remaining and not remaining[stage_id])
            if not ready:
                raise ValueError("declared stage graph must be acyclic")
            order.extend(ready)
            for stage_id in ready:
                del remaining[stage_id]
            for values in remaining.values():
                values.difference_update(ready)
        return tuple(order)


class KernelInstructionOverride(ContentAddressedModel):
    """Kernel-owned effective request bound to the original task instruction bytes."""

    schema_version: Literal["aecbench.kernel-instruction-override.v1"] = "aecbench.kernel-instruction-override.v1"
    mode: Literal["declared_stage", "task_finalization"]
    task_id: NonEmptyStr
    original_instruction_sha256: str
    effective_instruction: NonEmptyStr
    stage_id: NonEmptyStr | None = None
    context_manifest_sha256: str | None = None

    @field_validator("original_instruction_sha256", "context_manifest_sha256")
    @classmethod
    def validate_sha256_fields(cls, value: str | None) -> str | None:
        return validate_sha256(value) if value is not None else None

    @model_validator(mode="after")
    def validate_mode_shape(self) -> Self:
        if self.mode == "declared_stage":
            if self.stage_id is None or self.context_manifest_sha256 is None:
                raise ValueError("declared-stage override requires stage_id and context_manifest_sha256")
        elif self.stage_id is not None or self.context_manifest_sha256 is not None:
            raise ValueError("task-finalization override cannot carry stage_id or context_manifest_sha256")
        return self


class StageContextRoute(FrozenStrictModel):
    """One upstream receipt selected to satisfy a declared consumer input."""

    input_id: NonEmptyStr
    producer_stage_id: NonEmptyStr
    producer_receipt: ArtifactReference

    @model_validator(mode="after")
    def validate_receipt_kind(self) -> Self:
        if self.producer_receipt.kind != "stage-execution-receipt":
            raise ValueError("stage context routes require stage-execution receipts")
        return self


class StageContextManifest(ContentAddressedModel):
    """Deterministic rendered context and exact upstream lineage for one stage call."""

    schema_version: Literal["aecbench.stage-context-manifest.v1"] = "aecbench.stage-context-manifest.v1"
    task_id: NonEmptyStr
    stage_graph_sha256: str
    consumer_stage_id: NonEmptyStr
    base_context_sha256: str
    routes: tuple[StageContextRoute, ...] = ()
    rendered_context: ArtifactReference

    @field_validator("stage_graph_sha256", "base_context_sha256")
    @classmethod
    def validate_sha256_fields(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_routes_and_artifacts(self) -> Self:
        route_ids = tuple((route.input_id, route.producer_stage_id) for route in self.routes)
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("stage context routes must be unique")
        if self.rendered_context.kind != "stage-context":
            raise ValueError("rendered stage context must use stage-context artifact kind")
        return self


class StageOutput(ContentAddressedModel):
    """Parsed terminal payload emitted by one declared stage."""

    schema_version: Literal["aecbench.stage-output.v1"] = "aecbench.stage-output.v1"
    task_id: NonEmptyStr
    stage_id: NonEmptyStr
    outputs: dict[NonEmptyStr, JsonValue]

    @field_validator("outputs")
    @classmethod
    def validate_outputs(cls, value: dict[str, JsonValue]) -> dict[str, JsonValue]:
        if not value:
            raise ValueError("stage output must include at least one declared output")
        return value


class StageJobFileDigest(FrozenStrictModel):
    """Physical file evidence copied from one isolated stage job."""

    relative_path: NonEmptyStr
    sha256: str
    size_bytes: int = Field(ge=0)

    @field_validator("sha256")
    @classmethod
    def validate_file_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("relative_path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("stage job evidence paths must be contained relative paths")
        return value


class StageResourceEvidence(FrozenStrictModel):
    """Measured usage from an intermediate dispatch that does not emit a TrialRecord."""

    wall_seconds: float = Field(ge=0.0)
    tokens_in: int | None = Field(default=None, ge=0)
    tokens_out: int | None = Field(default=None, ge=0)
    cache_read_tokens: int | None = Field(default=None, ge=0)
    cache_write_tokens: int | None = Field(default=None, ge=0)
    estimated_cost_usd: float | None = Field(default=None, ge=0.0)
    agent_turns: int | None = Field(default=None, ge=0)
    tool_calls: int | None = Field(default=None, ge=0)


class StageExecutionReceipt(ContentAddressedModel):
    """Tamper-evident intermediate execution result kept outside the TrialRecord ledger."""

    schema_version: Literal["aecbench.stage-execution-receipt.v1"] = "aecbench.stage-execution-receipt.v1"
    bundle_id: NonEmptyStr
    bundle_sha256: str
    run_id: NonEmptyStr
    program_sha256: str
    program_node_id: NonEmptyStr
    operation_sha256: str
    attempt: int = Field(ge=1)
    task_id: NonEmptyStr
    task_package_sha256: str
    world_package_sha256: str
    stage_graph_sha256: str
    stage_id: NonEmptyStr
    context_manifest: ArtifactReference
    upstream_receipts: tuple[ArtifactReference, ...] = ()
    raw_output: ArtifactReference
    parsed_output: ArtifactReference
    agent_result: ArtifactReference
    job_dir: NonEmptyStr
    job_files: tuple[StageJobFileDigest, ...]
    resources: StageResourceEvidence

    @field_validator(
        "bundle_sha256",
        "program_sha256",
        "operation_sha256",
        "task_package_sha256",
        "world_package_sha256",
        "stage_graph_sha256",
    )
    @classmethod
    def validate_sha256_fields(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_artifacts_and_files(self) -> Self:
        expected_kinds = (
            (self.context_manifest, "stage-context-manifest"),
            (self.raw_output, "stage-output-raw"),
            (self.parsed_output, "stage-output"),
            (self.agent_result, "stage-agent-result"),
        )
        for artifact, expected_kind in expected_kinds:
            if artifact.kind != expected_kind:
                raise ValueError(f"stage receipt artifact must use {expected_kind} kind")
        if any(receipt.kind != "stage-execution-receipt" for receipt in self.upstream_receipts):
            raise ValueError("upstream stage artifacts must be stage-execution receipts")
        receipt_ids = tuple((receipt.path, receipt.sha256) for receipt in self.upstream_receipts)
        if len(receipt_ids) != len(set(receipt_ids)):
            raise ValueError("upstream stage receipts must be unique")
        file_paths = tuple(file.relative_path for file in self.job_files)
        if len(file_paths) != len(set(file_paths)):
            raise ValueError("stage receipt job file paths must be unique")
        if file_paths != tuple(sorted(file_paths)):
            raise ValueError("stage receipt job files must be sorted by relative path")
        return self


def declared_stage_graph_from_payload(
    *,
    task_id: str,
    world_package_sha256: str,
    payload: dict[str, Any],
) -> DeclaredStageGraph | None:
    """Build the closed stage graph projection from an already parsed world sidecar."""
    raw_stages = payload.get("stages")
    if raw_stages is None:
        return None

    return DeclaredStageGraph(
        task_id=task_id,
        world_package_sha256=world_package_sha256,
        stages=_declared_stages_from_payload(raw_stages),
        handoffs=_declared_handoffs_from_payload(payload.get("handoffs", ())),
    )


def _declared_stages_from_payload(value: object) -> tuple[DeclaredStage, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError("declared task-world stages must be a non-empty list")
    return tuple(_declared_stage_from_payload(item) for item in value)


def _declared_stage_from_payload(value: object) -> DeclaredStage:
    if not isinstance(value, dict):
        raise ValueError("declared task-world stage must be a mapping")
    stage_id = value.get("id")
    if not isinstance(stage_id, str) or not stage_id.strip():
        raise ValueError("declared task-world stage requires a non-empty id")
    return DeclaredStage(
        stage_id=stage_id,
        title=_optional_text(value.get("title")),
        discipline=_optional_text(value.get("discipline")),
        consumes=_string_tuple(value.get("consumes", ()), label="stage consumes"),
        produces=_string_tuple(value.get("produces", ()), label="stage produces"),
        branch_decision_ids=_string_tuple(
            value.get("branch_decisions", ()),
            label="stage branch decisions",
        ),
        verifier_gate_ids=_string_tuple(
            value.get("verifier_gates", ()),
            label="stage verifier gates",
        ),
    )


def _declared_handoffs_from_payload(value: object) -> tuple[DeclaredHandoff, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError("declared task-world handoffs must be a list")
    return tuple(_declared_handoff_from_payload(item) for item in value)


def _declared_handoff_from_payload(value: object) -> DeclaredHandoff:
    if not isinstance(value, dict):
        raise ValueError("declared task-world handoff must be a mapping")
    handoff_id = value.get("id")
    producer = value.get("producer_stage")
    if not isinstance(handoff_id, str) or not handoff_id.strip():
        raise ValueError("declared task-world handoff requires a non-empty id")
    if not isinstance(producer, str) or not producer.strip():
        raise ValueError("declared task-world handoff requires a producer stage")
    return DeclaredHandoff(
        handoff_id=handoff_id,
        producer_stage_id=producer,
        consumer_stage_ids=_string_tuple(
            value.get("consumer_stages", ()),
            label="handoff consumers",
        ),
    )


def _string_tuple(value: object, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        raise ValueError(f"{label} must be a list")
    if any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{label} must contain non-empty strings")
    return tuple(value)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError("declared stage text must be non-empty when supplied")
    return value
