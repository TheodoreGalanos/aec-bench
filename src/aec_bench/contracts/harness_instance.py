# ABOUTME: Defines typed harness specifications and compiled task-specific instances over a fixed kernel.
# ABOUTME: Keeps Hx immutable, directly referenced, and limited to explicit program-surface operations.

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    Field,
    PositiveInt,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)

from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelCapabilityKind,
    KernelCapabilityRef,
    KernelRef,
)
from aec_bench.contracts.validators import NonEmptyStr

PROHIBITED_RETRY_SAFE_ERROR_CODES = frozenset(
    {
        "candidate_manifest_contract_failed",
        "fanout_item_failed",
        "handler_exception",
        "harbor_workflow_failed",
        "incomplete_harbor_import",
        "incomplete_harbor_trial_plan",
        "invalid_handler_result",
        "invalid_harbor_trials",
        "no_harbor_trials",
        "node_execution_failed",
        "program_node_failed_without_code",
        "required_verifier_not_completed",
        "runtime_execution_attestation_invalid",
        "runtime_execution_attestation_mismatch",
        "runtime_execution_attestation_missing",
        "runtime_fault",
        "verified_trial_contract_failed",
    }
)
PROHIBITED_RETRY_SAFE_ERROR_PREFIXES = ("global_", "harness_")


def prohibited_retry_safe_error_codes(error_codes: tuple[str, ...]) -> tuple[str, ...]:
    """Return retry codes whose effects or consumed budgets make replay unsafe."""
    return tuple(
        sorted(
            error_code
            for error_code in error_codes
            if error_code in PROHIBITED_RETRY_SAFE_ERROR_CODES
            or error_code.startswith(PROHIBITED_RETRY_SAFE_ERROR_PREFIXES)
        )
    )


class HarnessBindingKind(StrEnum):
    """Typed task-specific roles that a kernel capability can fill in Hx."""

    TASK_SOURCE = "task_source"
    AGENT = "agent"
    COMPUTE = "compute"
    CONTEXT = "context"
    TOOL = "tool"
    VERIFICATION = "verification"
    RESULT_IMPORT = "result_import"


class HarnessTopologyRole(StrEnum):
    """Stable structural roles used to describe the Hx binding topology."""

    SOURCE = "source"
    ORCHESTRATOR = "orchestrator"
    WORKER = "worker"
    SERVICE = "service"
    GATE = "gate"
    SINK = "sink"


class ToolAccessMode(StrEnum):
    """Closed permission modes available to a bound tool provider."""

    READ_ONLY = "read_only"
    EXECUTE = "execute"
    READ_WRITE = "read_write"


class ContextSelectionStrategy(StrEnum):
    """Closed context-selection strategies exposed by the fixed kernel."""

    FIXED = "fixed"
    RETRIEVAL = "retrieval"
    ADAPTIVE = "adaptive"


class HarnessContractKind(StrEnum):
    """Data-boundary contract roles retained in harness provenance."""

    INPUT = "input"
    OUTPUT = "output"
    INVARIANT = "invariant"


class HarnessContractEnforcement(StrEnum):
    """Point at which a harness data contract must be enforced."""

    COMPILE_TIME = "compile_time"
    RUNTIME = "runtime"


class VerificationStage(StrEnum):
    """Explicit placement of a verifier relative to an operation."""

    BEFORE_OPERATION = "before_operation"
    AFTER_OPERATION = "after_operation"
    FINAL = "final"


class TaskSourceBindingConfig(FrozenStrictModel):
    """Exact task allowlist made available to a compiled harness instance."""

    kind: Literal[HarnessBindingKind.TASK_SOURCE] = HarnessBindingKind.TASK_SOURCE
    task_refs: tuple[NonEmptyStr, ...]

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("task-source binding must include at least one task ref")
        if len(value) != len(set(value)):
            raise ValueError("task-source binding task refs must be unique")
        return value


class AgentBindingConfig(FrozenStrictModel):
    """Closed agent configuration accepted by the initial fixed-kernel surface."""

    kind: Literal[HarnessBindingKind.AGENT] = HarnessBindingKind.AGENT
    agent_name: NonEmptyStr
    model: NonEmptyStr
    max_turns: int = Field(default=8, ge=1, le=1_000)
    timeout_seconds: int = Field(default=600, ge=1, le=86_400)


class ComputeBindingConfig(FrozenStrictModel):
    """Bounded compute settings for an execution-backend capability."""

    kind: Literal[HarnessBindingKind.COMPUTE] = HarnessBindingKind.COMPUTE
    max_concurrency: int = Field(default=1, ge=1, le=256)
    timeout_override_seconds: int | None = Field(default=None, ge=1, le=86_400)


class ContextBindingConfig(FrozenStrictModel):
    """Bounded context sources and selection strategy exposed to agent bindings."""

    kind: Literal[HarnessBindingKind.CONTEXT] = HarnessBindingKind.CONTEXT
    source_ids: tuple[NonEmptyStr, ...]
    selection_strategy: ContextSelectionStrategy = ContextSelectionStrategy.FIXED
    max_tokens: int = Field(default=32_000, ge=1, le=10_000_000)

    @field_validator("source_ids")
    @classmethod
    def validate_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("context binding must include at least one source id")
        if len(value) != len(set(value)):
            raise ValueError("context source ids must be unique")
        return value


class ToolBindingConfig(FrozenStrictModel):
    """Bounded tool catalogue and access mode exposed to agent bindings."""

    kind: Literal[HarnessBindingKind.TOOL] = HarnessBindingKind.TOOL
    tool_ids: tuple[NonEmptyStr, ...]
    access_mode: ToolAccessMode
    max_calls: int = Field(default=128, ge=1, le=100_000)

    @field_validator("tool_ids")
    @classmethod
    def validate_tool_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("tool binding must include at least one tool id")
        if len(value) != len(set(value)):
            raise ValueError("tool ids must be unique")
        return value


class VerificationBindingConfig(FrozenStrictModel):
    """Explicit verifier enablement and failure policy for Hx."""

    kind: Literal[HarnessBindingKind.VERIFICATION] = HarnessBindingKind.VERIFICATION
    enabled: bool = True
    required: bool = True

    @model_validator(mode="after")
    def validate_required_verification(self) -> Self:
        if self.required and not self.enabled:
            raise ValueError("required verification cannot be disabled")
        return self


class ResultImportBindingConfig(FrozenStrictModel):
    """Typed result-import destination exposed by the compiled harness."""

    kind: Literal[HarnessBindingKind.RESULT_IMPORT] = HarnessBindingKind.RESULT_IMPORT
    ledger_namespace: NonEmptyStr
    required_artifacts: tuple[NonEmptyStr, ...] = ()

    @field_validator("required_artifacts")
    @classmethod
    def validate_required_artifacts(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("result-import required artifacts must be unique")
        return value


HarnessBindingConfiguration = Annotated[
    TaskSourceBindingConfig
    | AgentBindingConfig
    | ComputeBindingConfig
    | ContextBindingConfig
    | ToolBindingConfig
    | VerificationBindingConfig
    | ResultImportBindingConfig,
    Field(discriminator="kind"),
]


class HarnessBudget(FrozenStrictModel):
    """Closed resource envelope constraining every program compiled for Hx."""

    max_parallelism: int = Field(default=32, ge=1, le=256)
    max_total_attempts: int = Field(default=256, ge=1, le=10_000)
    max_agent_turns: int = Field(default=1_000, ge=1, le=100_000)
    max_tool_calls: int = Field(default=1_024, ge=1, le=100_000)
    max_context_tokens: int = Field(default=1_000_000, ge=1, le=10_000_000)
    max_runtime_seconds: int = Field(default=86_400, ge=1, le=604_800)
    max_tokens: int | None = Field(default=None, ge=1, le=100_000_000)
    max_cost_usd: float | None = Field(default=None, gt=0.0, le=1_000_000.0)


class HarnessRecursionPolicy(FrozenStrictModel):
    """Harness-level upper bound and allowlist for recursive orchestration."""

    enabled: bool = False
    max_depth: int = Field(default=0, ge=0, le=32)
    max_calls: int = Field(default=0, ge=0, le=1_024)
    allowed_binding_ids: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_recursion(self) -> Self:
        if len(self.allowed_binding_ids) != len(set(self.allowed_binding_ids)):
            raise ValueError("recursive binding ids must be unique")
        if self.enabled:
            if self.max_depth == 0 or self.max_calls == 0 or not self.allowed_binding_ids:
                raise ValueError("enabled harness recursion requires positive bounds and allowed bindings")
        elif self.max_depth != 0 or self.max_calls != 0 or self.allowed_binding_ids:
            raise ValueError("disabled harness recursion cannot carry bounds or allowed bindings")
        return self


class HarnessContractSpec(FrozenStrictModel):
    """Schema contract enforced across an Hx boundary."""

    contract_id: NonEmptyStr
    kind: HarnessContractKind
    schema_ref: NonEmptyStr
    enforcement: HarnessContractEnforcement
    summary: NonEmptyStr


class HarnessBindingSpec(FrozenStrictModel):
    """One proposed spec binding from a trusted capability to a typed Hx role."""

    binding_id: NonEmptyStr
    capability_ref: KernelCapabilityRef
    depends_on: tuple[NonEmptyStr, ...] = ()
    topology_role: HarnessTopologyRole
    contract_ids: tuple[NonEmptyStr, ...] = ()
    configuration: HarnessBindingConfiguration

    @model_validator(mode="after")
    def validate_dependencies(self) -> Self:
        _validate_local_dependencies(self.binding_id, self.depends_on)
        _validate_unique_ids(self.contract_ids, label=f"binding {self.binding_id!r} contract ids")
        _validate_topology_role(self)
        return self


class HarnessSpec(FrozenStrictModel):
    """Declarative capability, binding, contract, and budget input for a harness."""

    summary: NonEmptyStr
    contracts: tuple[HarnessContractSpec, ...] = ()
    budget: HarnessBudget = Field(default_factory=HarnessBudget)
    recursion_policy: HarnessRecursionPolicy = Field(default_factory=HarnessRecursionPolicy)
    bindings: tuple[HarnessBindingSpec, ...]

    @model_validator(mode="after")
    def validate_binding_graph(self) -> Self:
        _validate_binding_graph(self.bindings)
        _validate_contract_references(self.bindings, self.contracts)
        _validate_budget_compatibility(self.bindings, self.budget)
        _validate_recursion_bindings(self.bindings, self.recursion_policy)
        return self

    def binding(self, binding_id: str) -> HarnessBindingSpec | None:
        """Return a harness binding by id without exposing a mutable index."""
        return next((binding for binding in self.bindings if binding.binding_id == binding_id), None)


class HarnessCompileRequest(FrozenStrictModel):
    """Closed compile request that pairs one complete harness specification with one fixed K."""

    request_id: NonEmptyStr
    kernel_ref: KernelRef
    spec: HarnessSpec


class CompiledHarnessBinding(FrozenStrictModel):
    """Kernel-resolved binding retained as immutable Hx provenance."""

    binding_id: NonEmptyStr
    capability_ref: KernelCapabilityRef
    capability_kind: KernelCapabilityKind
    depends_on: tuple[NonEmptyStr, ...] = ()
    topology_role: HarnessTopologyRole
    contract_ids: tuple[NonEmptyStr, ...] = ()
    configuration: HarnessBindingConfiguration

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        _validate_local_dependencies(self.binding_id, self.depends_on)
        _validate_unique_ids(self.contract_ids, label=f"binding {self.binding_id!r} contract ids")
        _validate_topology_role(self)
        expected_kind = _CAPABILITY_KIND_BY_BINDING_KIND[self.configuration.kind]
        if self.capability_kind is not expected_kind:
            raise ValueError(
                f"binding {self.binding_id!r} requires capability kind {expected_kind.value}, "
                f"found {self.capability_kind.value}"
            )
        return self


class VerificationPlacement(FrozenStrictModel):
    """Verifier binding and stage attached to one exported operation."""

    binding_id: NonEmptyStr
    stage: VerificationStage
    required: bool = True


class ProgramOperationScope(StrEnum):
    """Compilation authority required to invoke one exported operation."""

    PUBLIC = "public"
    PROPOSAL_SESSION_INTERNAL = "proposal_session_internal"


class ProgramOperationRef(FrozenStrictModel):
    """Stable reference used to resolve one exported Hx operation."""

    operation_id: NonEmptyStr


class ProgramOperationSpec(FrozenStrictModel):
    """One typed operation exported by Hx for px compilation."""

    operation_id: NonEmptyStr
    capability_ref: KernelCapabilityRef
    input_schema_ref: NonEmptyStr
    output_schema_ref: NonEmptyStr
    binding_ids: tuple[NonEmptyStr, ...]
    contract_ids: tuple[NonEmptyStr, ...] = ()
    allowed_task_refs: tuple[NonEmptyStr, ...] = ()
    max_parallelism: PositiveInt = 1
    supports_retry: bool = False
    retry_safe_error_codes: tuple[NonEmptyStr, ...] = ()
    supports_recursion: bool = False
    verifier_placements: tuple[VerificationPlacement, ...] = ()
    required_compilation_scope: ProgramOperationScope = ProgramOperationScope.PUBLIC

    @model_serializer(mode="wrap")
    def serialize_with_legacy_public_scope(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, object]:
        """Keep legacy public-operation identities while hashing internal scope."""
        payload = handler(self)
        if not isinstance(payload, dict):
            raise TypeError("program operation serialization must produce an object")
        if self.required_compilation_scope is ProgramOperationScope.PUBLIC:
            payload.pop("required_compilation_scope", None)
        return payload

    @field_validator("binding_ids")
    @classmethod
    def validate_binding_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("program operation must retain at least one binding id")
        _validate_unique_ids(value, label="program operation binding ids")
        return value

    @field_validator("contract_ids")
    @classmethod
    def validate_contract_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        _validate_unique_ids(value, label="program operation contract ids")
        return value

    @field_validator("allowed_task_refs")
    @classmethod
    def validate_allowed_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("program operation allowed task refs must be unique")
        return value

    @field_validator("retry_safe_error_codes")
    @classmethod
    def validate_retry_safe_error_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("retry-safe error codes must be unique")
        if "*" in value:
            raise ValueError("wildcard retry-safe error codes are not permitted")
        prohibited = prohibited_retry_safe_error_codes(value)
        if prohibited:
            raise ValueError("prohibited retry-safe error codes: " + ", ".join(prohibited))
        return value

    @field_validator("verifier_placements")
    @classmethod
    def validate_verifier_placements(
        cls,
        value: tuple[VerificationPlacement, ...],
    ) -> tuple[VerificationPlacement, ...]:
        placements = [(placement.binding_id, placement.stage) for placement in value]
        if len(placements) != len(set(placements)):
            raise ValueError("program operation verifier placements must be unique")
        return value

    @field_validator("max_parallelism")
    @classmethod
    def validate_max_parallelism(cls, value: int) -> int:
        if value > 256:
            raise ValueError("program operation max_parallelism must not exceed 256")
        return value

    @model_validator(mode="after")
    def validate_operation_provenance(self) -> Self:
        if self.supports_retry and not self.retry_safe_error_codes:
            raise ValueError("retry support requires explicit safe error codes")
        if self.retry_safe_error_codes and not self.supports_retry:
            raise ValueError("retry-safe error codes require retry support")
        outside = sorted(
            placement.binding_id
            for placement in self.verifier_placements
            if placement.binding_id not in self.binding_ids
        )
        if outside:
            raise ValueError("verifier placements must reference operation binding ids: " + ", ".join(outside))
        return self

    @property
    def ref(self) -> ProgramOperationRef:
        return ProgramOperationRef(operation_id=self.operation_id)


class ProgramSurface(FrozenStrictModel):
    """Named operation surface against which execution programs compile."""

    surface_id: NonEmptyStr
    operations: tuple[ProgramOperationSpec, ...]

    @model_validator(mode="after")
    def validate_operations(self) -> Self:
        if not self.operations:
            raise ValueError("program surface must expose at least one operation")
        operation_ids = [operation.operation_id for operation in self.operations]
        if len(operation_ids) != len(set(operation_ids)):
            raise ValueError("program surface operation ids must be unique")
        return self

    @property
    def operation_refs(self) -> tuple[ProgramOperationRef, ...]:
        return tuple(operation.ref for operation in self.operations)

    def operation(self, operation_id: str) -> ProgramOperationSpec | None:
        """Return one operation by its surface-unique id."""
        return next((operation for operation in self.operations if operation.operation_id == operation_id), None)

    def resolve_operation(self, reference: ProgramOperationRef) -> ProgramOperationSpec | None:
        """Resolve an operation from the directly validated embedded surface."""

        return self.operation(reference.operation_id)


class HarnessInstanceRef(FrozenStrictModel):
    """Stable reference to one compiled task-specific harness instance."""

    instance_id: NonEmptyStr


class CompiledHarnessInstance(FrozenStrictModel):
    """Immutable Hx produced by deterministic compilation against one fixed K."""

    instance_id: NonEmptyStr
    kernel_ref: KernelRef
    source_spec: HarnessSpec
    contracts: tuple[HarnessContractSpec, ...] = ()
    budget: HarnessBudget = Field(default_factory=HarnessBudget)
    recursion_policy: HarnessRecursionPolicy = Field(default_factory=HarnessRecursionPolicy)
    bindings: tuple[CompiledHarnessBinding, ...]
    program_surface: ProgramSurface
    compatibility_notes: tuple[NonEmptyStr, ...] = ()

    @model_validator(mode="after")
    def validate_instance(self) -> Self:
        _validate_binding_graph(self.bindings)
        _validate_contract_references(self.bindings, self.contracts)
        _validate_budget_compatibility(self.bindings, self.budget)
        _validate_recursion_bindings(self.bindings, self.recursion_policy)
        task_refs = {
            task_ref
            for binding in self.bindings
            if isinstance(binding.configuration, TaskSourceBindingConfig)
            for task_ref in binding.configuration.task_refs
        }
        exported_task_refs = {
            task_ref for operation in self.program_surface.operations for task_ref in operation.allowed_task_refs
        }
        outside = sorted(exported_task_refs - task_refs)
        if outside:
            raise ValueError(
                "program surface exports task refs outside the compiled task-source bindings: " + ", ".join(outside)
            )
        binding_ids = {binding.binding_id for binding in self.bindings}
        bindings_by_id = {binding.binding_id: binding for binding in self.bindings}
        contract_ids = {contract.contract_id for contract in self.contracts}
        for operation in self.program_surface.operations:
            unknown_bindings = sorted(set(operation.binding_ids) - binding_ids)
            if unknown_bindings:
                raise ValueError(
                    f"operation {operation.operation_id!r} has unknown binding ids: " + ", ".join(unknown_bindings)
                )
            named_task_refs: set[str] = set()
            for binding_id in operation.binding_ids:
                configuration = bindings_by_id[binding_id].configuration
                if isinstance(configuration, TaskSourceBindingConfig):
                    named_task_refs.update(configuration.task_refs)
            unbacked_task_refs = sorted(set(operation.allowed_task_refs) - named_task_refs)
            if unbacked_task_refs:
                raise ValueError(
                    f"operation {operation.operation_id!r} allowed task refs are not backed by "
                    "named task-source bindings: " + ", ".join(unbacked_task_refs)
                )
            unknown_contracts = sorted(set(operation.contract_ids) - contract_ids)
            if unknown_contracts:
                raise ValueError(
                    f"operation {operation.operation_id!r} has unknown contract ids: " + ", ".join(unknown_contracts)
                )
            for placement in operation.verifier_placements:
                binding = self.binding(placement.binding_id)
                if binding is None or not isinstance(binding.configuration, VerificationBindingConfig):
                    raise ValueError(
                        f"operation {operation.operation_id!r} verifier placement "
                        f"{placement.binding_id!r} must reference a verification binding"
                    )
        return self

    @property
    def ref(self) -> HarnessInstanceRef:
        return HarnessInstanceRef(instance_id=self.instance_id)

    def binding(self, binding_id: str) -> CompiledHarnessBinding | None:
        """Return a compiled binding by id without exposing a mutable index."""
        return next((binding for binding in self.bindings if binding.binding_id == binding_id), None)


_CAPABILITY_KIND_BY_BINDING_KIND: dict[HarnessBindingKind, KernelCapabilityKind] = {
    HarnessBindingKind.TASK_SOURCE: KernelCapabilityKind.TASK_SOURCE,
    HarnessBindingKind.AGENT: KernelCapabilityKind.AGENT_ADAPTER,
    HarnessBindingKind.COMPUTE: KernelCapabilityKind.EXECUTION_BACKEND,
    HarnessBindingKind.CONTEXT: KernelCapabilityKind.CONTEXT_PROVIDER,
    HarnessBindingKind.TOOL: KernelCapabilityKind.TOOL_PROVIDER,
    HarnessBindingKind.VERIFICATION: KernelCapabilityKind.VERIFIER,
    HarnessBindingKind.RESULT_IMPORT: KernelCapabilityKind.RESULT_IMPORTER,
}

_TOPOLOGY_ROLES_BY_BINDING_KIND: dict[HarnessBindingKind, frozenset[HarnessTopologyRole]] = {
    HarnessBindingKind.TASK_SOURCE: frozenset({HarnessTopologyRole.SOURCE}),
    HarnessBindingKind.AGENT: frozenset({HarnessTopologyRole.ORCHESTRATOR, HarnessTopologyRole.WORKER}),
    HarnessBindingKind.COMPUTE: frozenset({HarnessTopologyRole.SERVICE}),
    HarnessBindingKind.CONTEXT: frozenset({HarnessTopologyRole.SOURCE, HarnessTopologyRole.SERVICE}),
    HarnessBindingKind.TOOL: frozenset({HarnessTopologyRole.SERVICE}),
    HarnessBindingKind.VERIFICATION: frozenset({HarnessTopologyRole.GATE}),
    HarnessBindingKind.RESULT_IMPORT: frozenset({HarnessTopologyRole.SINK}),
}


def _validate_local_dependencies(binding_id: str, depends_on: tuple[str, ...]) -> None:
    if len(depends_on) != len(set(depends_on)):
        raise ValueError(f"binding {binding_id!r} dependencies must be unique")
    if binding_id in depends_on:
        raise ValueError(f"binding {binding_id!r} cannot depend on itself")


def _validate_unique_ids(values: tuple[str, ...], *, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_topology_role(binding: HarnessBindingSpec | CompiledHarnessBinding) -> None:
    allowed_roles = _TOPOLOGY_ROLES_BY_BINDING_KIND[binding.configuration.kind]
    if binding.topology_role not in allowed_roles:
        allowed = ", ".join(sorted(role.value for role in allowed_roles))
        raise ValueError(
            f"binding {binding.binding_id!r} topology role must be one of {allowed} "
            f"for {binding.configuration.kind.value} configuration"
        )


def _validate_binding_graph(bindings: tuple[HarnessBindingSpec, ...] | tuple[CompiledHarnessBinding, ...]) -> None:
    if not bindings:
        raise ValueError("harness binding graph must include at least one binding")
    binding_ids = [binding.binding_id for binding in bindings]
    if len(binding_ids) != len(set(binding_ids)):
        raise ValueError("harness binding ids must be unique")

    known_ids = set(binding_ids)
    dependencies = {binding.binding_id: set(binding.depends_on) for binding in bindings}
    for binding_id, binding_dependencies in dependencies.items():
        unknown = sorted(binding_dependencies - known_ids)
        if unknown:
            raise ValueError(f"binding {binding_id!r} has unknown dependencies: {', '.join(unknown)}")

    remaining = {binding_id: set(binding_dependencies) for binding_id, binding_dependencies in dependencies.items()}
    while remaining:
        ready = {binding_id for binding_id, binding_dependencies in remaining.items() if not binding_dependencies}
        if not ready:
            raise ValueError("harness binding graph must be acyclic")
        for binding_id in ready:
            del remaining[binding_id]
        for binding_dependencies in remaining.values():
            binding_dependencies.difference_update(ready)


def _validate_contract_references(
    bindings: tuple[HarnessBindingSpec, ...] | tuple[CompiledHarnessBinding, ...],
    contracts: tuple[HarnessContractSpec, ...],
) -> None:
    contract_ids = [contract.contract_id for contract in contracts]
    if len(contract_ids) != len(set(contract_ids)):
        raise ValueError("harness contract ids must be unique")
    known_contract_ids = set(contract_ids)
    for binding in bindings:
        unknown = sorted(set(binding.contract_ids) - known_contract_ids)
        if unknown:
            raise ValueError(f"binding {binding.binding_id!r} has unknown contract ids: " + ", ".join(unknown))


def _validate_budget_compatibility(
    bindings: tuple[HarnessBindingSpec, ...] | tuple[CompiledHarnessBinding, ...],
    budget: HarnessBudget,
) -> None:
    for binding in bindings:
        configuration = binding.configuration
        if isinstance(configuration, AgentBindingConfig) and configuration.max_turns > budget.max_agent_turns:
            raise ValueError(f"binding {binding.binding_id!r} max_turns exceeds harness budget")
        if isinstance(configuration, ComputeBindingConfig) and configuration.max_concurrency > budget.max_parallelism:
            raise ValueError(f"binding {binding.binding_id!r} max_concurrency exceeds harness budget")
        if isinstance(configuration, ContextBindingConfig) and configuration.max_tokens > budget.max_context_tokens:
            raise ValueError(f"binding {binding.binding_id!r} context tokens exceed harness budget")
        if isinstance(configuration, ToolBindingConfig) and configuration.max_calls > budget.max_tool_calls:
            raise ValueError(f"binding {binding.binding_id!r} tool calls exceed harness budget")


def _validate_recursion_bindings(
    bindings: tuple[HarnessBindingSpec, ...] | tuple[CompiledHarnessBinding, ...],
    policy: HarnessRecursionPolicy,
) -> None:
    known_ids = {binding.binding_id for binding in bindings}
    unknown = sorted(set(policy.allowed_binding_ids) - known_ids)
    if unknown:
        raise ValueError("harness recursion policy has unknown binding ids: " + ", ".join(unknown))
