# ABOUTME: Materializes matched four-cell RunPlan sets from fixed-K harness and program treatments.
# ABOUTME: Enforces exact shared tasks, model, resources, seeds, repetitions, and content identities.

from __future__ import annotations

from pathlib import Path
from typing import Any, Self, TypeVar

from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_program import ExecutionProgram, ExecutionProgramRef, ProgramLimits, ProgramNode
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    ComputeBindingConfig,
    ContextBindingConfig,
    HarnessBindingConfiguration,
    HarnessBudget,
    HarnessCompileRequest,
    HarnessInstanceRef,
    HarnessSpec,
    TaskSourceBindingConfig,
    ToolBindingConfig,
)
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    KernelRef,
    canonical_json_sha256,
    kernel_abi_commitment,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.run_bundle import RunPlan
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.qualification.harness_program_study.plan import (
    HarnessProgramCandidateReference,
    HarnessProgramCandidateSet,
    HarnessProgramCell,
)
from aec_bench.harness.compilation import (
    compile_execution_program,
    compile_harness_instance,
    compile_run_plan,
)
from aec_bench.harness.kernel_catalogue import KernelRuntimeRegistry


class ProgramFactorTemplate(LegacyContentAddressedModel):
    """Harness-independent program factor rebound explicitly to each compiled Hx."""

    factor_id: NonEmptyStr
    version: NonEmptyStr
    nodes: tuple[ProgramNode, ...]
    limits: ProgramLimits = Field(default_factory=ProgramLimits)

    @model_validator(mode="after")
    def validate_program_graph(self) -> Self:
        self.bind(HarnessInstanceRef(instance_id="factor-validation"))
        return self

    def bind(self, harness_ref: HarnessInstanceRef) -> ExecutionProgram:
        """Materialize this factor as one genuine harness-bound execution program."""
        return ExecutionProgram(
            program_id=self.factor_id,
            version=self.version,
            harness_ref=harness_ref,
            nodes=self.nodes,
            limits=self.limits,
        )

    @property
    def ref(self) -> ExecutionProgramRef:
        """Return the stable program factor identity."""

        return ExecutionProgramRef(program_id=self.factor_id, version=self.version)


class HarnessProgramCandidateRequest(LegacyContentAddressedModel):
    """Explicit source factors and shared controls for one matched candidate set."""

    candidate_set_id: NonEmptyStr
    task_set_id: NonEmptyStr
    experiment_id: NonEmptyStr
    kernel_ref: KernelRef
    task_refs: tuple[NonEmptyStr, ...]
    model: NonEmptyStr
    harness_budget: HarnessBudget
    program_limits: ProgramLimits
    seeds: tuple[int, ...]
    repetitions: PositiveInt
    fixed_harness_spec: HarnessSpec
    learned_harness_spec: HarnessSpec
    fixed_program: ProgramFactorTemplate
    learned_program: ProgramFactorTemplate

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or value != tuple(sorted(set(value))):
            raise ValueError("harness-program candidate factory requires canonical exact task refs")
        return value

    @model_validator(mode="after")
    def validate_shared_factors(self) -> Self:
        _validate_candidate_seed_block(self)
        _validate_candidate_factor_differences(self)
        _validate_candidate_harness_controls(self)
        _validate_candidate_resource_controls(self)
        return self


class MaterializedHarnessProgramCandidate(FrozenStrictModel):
    """One real candidate reference paired with its executable RunPlan."""

    cell: HarnessProgramCell
    reference: HarnessProgramCandidateReference
    bundle: RunPlan

    @model_validator(mode="after")
    def validate_local_identity(self) -> Self:
        if self.reference.cell is not self.cell:
            raise ValueError("materialized candidate cell does not match its reference")
        if self.reference.kernel_ref != self.bundle.harness.kernel_ref:
            raise ValueError("materialized candidate kernel does not match its RunPlan")
        if self.reference.harness_ref != self.bundle.harness.ref:
            raise ValueError("materialized candidate harness does not match its RunPlan")
        return self


class MaterializedHarnessProgramCandidateSet(LegacyContentAddressedModel):
    """Integrity-checked four-cell references, source factors, and executable bundles."""

    request: HarnessProgramCandidateRequest
    references: HarnessProgramCandidateSet
    candidates: tuple[MaterializedHarnessProgramCandidate, ...]

    @field_validator("candidates")
    @classmethod
    def canonicalize_candidates(
        cls,
        value: tuple[MaterializedHarnessProgramCandidate, ...],
    ) -> tuple[MaterializedHarnessProgramCandidate, ...]:
        order = {cell: index for index, cell in enumerate(HarnessProgramCell)}
        return tuple(sorted(value, key=lambda candidate: order[candidate.cell]))

    @model_validator(mode="after")
    def validate_materialized_integrity(self) -> Self:
        by_cell = {candidate.cell: candidate for candidate in self.candidates}
        _validate_materialized_candidate_members(self, by_cell=by_cell)
        snapshots = self.candidates[0].bundle.task_snapshots
        task_set_sha256 = _task_set_sha256(snapshots)
        policy_sha256 = _policy_sha256(self.request)
        resource_sha256 = _resource_sha256(self.request)
        abi_sha256 = kernel_abi_commitment(self.request.kernel_ref)
        for cell, candidate in by_cell.items():
            harness_spec = _harness_spec(self.request, cell)
            program_factor = _program_factor(self.request, cell)
            _validate_candidate_bundle_identity(
                request=self.request,
                cell=cell,
                bundle=candidate.bundle,
                snapshots=snapshots,
            )
            _validate_candidate_bundle_factors(
                request=self.request,
                bundle=candidate.bundle,
                harness_spec=harness_spec,
                program_factor=program_factor,
            )
            _validate_candidate_reference(
                request=self.request,
                candidate=candidate,
                program_factor=program_factor,
                task_set_sha256=task_set_sha256,
                policy_sha256=policy_sha256,
                resource_sha256=resource_sha256,
                abi_sha256=abi_sha256,
            )
        _validate_materialized_harness_program_cross(by_cell)
        return self


def _validate_candidate_seed_block(request: HarnessProgramCandidateRequest) -> None:
    if len(request.seeds) != request.repetitions or len(request.seeds) != len(set(request.seeds)):
        raise ValueError("harness-program candidate factory requires one unique seed per repetition")


def _validate_candidate_factor_differences(
    request: HarnessProgramCandidateRequest,
) -> None:
    if request.fixed_harness_spec == request.learned_harness_spec:
        raise ValueError("learned harness spec must differ from the fixed harness spec")
    if request.fixed_program == request.learned_program:
        raise ValueError("learned program factor must differ from the fixed program factor")
    if request.fixed_program.ref == request.learned_program.ref:
        raise ValueError("learned program factor must use a distinct stable reference")
    if harness_runtime_semantics(request.fixed_harness_spec) == harness_runtime_semantics(request.learned_harness_spec):
        raise ValueError("learned harness must contain a runtime-effective harness difference")
    if program_runtime_semantics(request.fixed_program) == program_runtime_semantics(request.learned_program):
        raise ValueError("learned program must contain a runtime-effective program difference")


def _validate_candidate_harness_controls(
    request: HarnessProgramCandidateRequest,
) -> None:
    for spec in (request.fixed_harness_spec, request.learned_harness_spec):
        task_configuration = _single_spec_configuration(spec, TaskSourceBindingConfig, role="task source")
        if task_configuration.task_refs != request.task_refs:
            raise ValueError("harness-program harness specs must use the exact task refs")
        agent_configuration = _single_spec_configuration(spec, AgentBindingConfig, role="agent")
        if agent_configuration.model != request.model:
            raise ValueError("harness-program harness specs must use one shared model")
        if spec.budget != request.harness_budget:
            raise ValueError("harness-program harness specs must use one shared harness budget")


def _validate_candidate_resource_controls(
    request: HarnessProgramCandidateRequest,
) -> None:
    if (
        request.fixed_program.limits != request.program_limits
        or request.learned_program.limits != request.program_limits
    ):
        raise ValueError("harness-program program factors must use one shared program limits budget")
    if _runtime_budget_payload(request.fixed_harness_spec) != _runtime_budget_payload(request.learned_harness_spec):
        raise ValueError("harness-program HarnessSpec values must use one shared runtime resource budget")


def _validate_materialized_candidate_members(
    candidate_set: MaterializedHarnessProgramCandidateSet,
    *,
    by_cell: dict[HarnessProgramCell, MaterializedHarnessProgramCandidate],
) -> None:
    if len(candidate_set.candidates) != len(HarnessProgramCell) or set(by_cell) != set(HarnessProgramCell):
        raise ValueError("materialized candidate set requires exactly one bundle for each harness-program cell")
    if candidate_set.references.task_set_id != candidate_set.request.task_set_id:
        raise ValueError("materialized candidate references do not match the requested task set")
    if candidate_set.references.candidates != tuple(candidate.reference for candidate in candidate_set.candidates):
        raise ValueError("materialized candidate references do not match the executable candidates")


def _validate_candidate_bundle_identity(
    *,
    request: HarnessProgramCandidateRequest,
    cell: HarnessProgramCell,
    bundle: RunPlan,
    snapshots: tuple[TaskSnapshotRef, ...],
) -> None:
    if bundle.run_manifest.run_id != f"{request.candidate_set_id}.{cell.value}":
        raise ValueError("candidate bundle id does not match its harness-program cell")
    if bundle.harness.kernel_ref != request.kernel_ref:
        raise ValueError("candidate bundle does not use the requested fixed kernel")
    if (
        bundle.task_snapshots != snapshots
        or tuple(snapshot.task_id for snapshot in bundle.task_snapshots) != request.task_refs
    ):
        raise ValueError("candidate bundles must use identical exact task snapshots")
    if bundle.run_manifest.experiment_id != request.experiment_id:
        raise ValueError("candidate bundles must use one shared experiment identity")


def _validate_candidate_bundle_factors(
    *,
    request: HarnessProgramCandidateRequest,
    bundle: RunPlan,
    harness_spec: HarnessSpec,
    program_factor: ProgramFactorTemplate,
) -> None:
    if bundle.harness.source_spec != harness_spec:
        raise ValueError("candidate harness does not match its harness factor")
    if bundle.harness.budget != request.harness_budget:
        raise ValueError("candidate bundles must use one shared harness budget")
    agent = _single_compiled_configuration(bundle, AgentBindingConfig, role="agent")
    if agent.model != request.model:
        raise ValueError("candidate bundles must use one shared model")
    expected_program = program_factor.bind(bundle.harness.ref)
    if bundle.execution_program.source_program_ref != expected_program.ref:
        raise ValueError("candidate compiled program does not match its program factor")
    if bundle.execution_program.limits != request.program_limits:
        raise ValueError("candidate bundles must use one shared program limits budget")


def _validate_candidate_reference(
    *,
    request: HarnessProgramCandidateRequest,
    candidate: MaterializedHarnessProgramCandidate,
    program_factor: ProgramFactorTemplate,
    task_set_sha256: str,
    policy_sha256: str,
    resource_sha256: str,
    abi_sha256: str,
) -> None:
    reference = candidate.reference
    if reference.task_set_id != request.task_set_id or reference.task_set_sha256 != task_set_sha256:
        raise ValueError("candidate reference does not bind the exact task and task-review snapshots")
    if reference.policy_sha256 != policy_sha256:
        raise ValueError("candidate reference does not bind the shared model, seeds, and repetitions")
    if reference.resource_sha256 != resource_sha256:
        raise ValueError("candidate reference does not bind the shared resource budget")
    if reference.program_ref != candidate.bundle.execution_program.source_program_ref:
        raise ValueError("candidate reference does not bind its harness-independent program factor")
    abi_identities = (
        reference.kernel_abi_sha256,
        reference.harness_abi_sha256,
        reference.program_abi_sha256,
    )
    if any(identity != abi_sha256 for identity in abi_identities):
        raise ValueError("candidate reference does not bind the fixed-kernel ABI")


def _validate_materialized_harness_program_cross(
    by_cell: dict[HarnessProgramCell, MaterializedHarnessProgramCandidate],
) -> None:
    h0_p0 = by_cell[HarnessProgramCell.H0_P0]
    hx_p0 = by_cell[HarnessProgramCell.HX_P0]
    h0_px = by_cell[HarnessProgramCell.H0_PX]
    hx_px = by_cell[HarnessProgramCell.HX_PX]
    if h0_p0.bundle.harness != h0_px.bundle.harness or hx_p0.bundle.harness != hx_px.bundle.harness:
        raise ValueError("harness-program cells do not preserve their exact compiled harness factor")
    if (
        h0_p0.bundle.execution_program == hx_p0.bundle.execution_program
        or h0_px.bundle.execution_program == hx_px.bundle.execution_program
    ):
        raise ValueError("program factors must compile separately against each harness")


def materialize_harness_program_candidates(
    request: HarnessProgramCandidateRequest,
    *,
    registry: KernelRuntimeRegistry,
    tasks_root: Path,
) -> MaterializedHarnessProgramCandidateSet:
    """Compile both program factors against both harness factors and bind exact task bytes."""
    source = HarnessProgramCandidateRequest.model_validate(request.model_dump(mode="python"))
    if source.kernel_ref != registry.manifest.ref:
        raise ValueError("harness-program candidate request does not target the installed fixed kernel")

    harnesses = {
        False: compile_harness_instance(
            HarnessCompileRequest(
                request_id=f"{source.candidate_set_id}.compile-h0",
                kernel_ref=source.kernel_ref,
                spec=source.fixed_harness_spec,
            ),
            registry=registry,
        ),
        True: compile_harness_instance(
            HarnessCompileRequest(
                request_id=f"{source.candidate_set_id}.compile-hx",
                kernel_ref=source.kernel_ref,
                spec=source.learned_harness_spec,
            ),
            registry=registry,
        ),
    }
    bundles: dict[HarnessProgramCell, RunPlan] = {}
    for cell in HarnessProgramCell:
        harness = harnesses[_learned_harness(cell)]
        program_factor = _program_factor(source, cell)
        compiled_program = compile_execution_program(
            program_factor.bind(harness.ref),
            harness=harness,
            registry=registry,
        )
        bundles[cell] = compile_run_plan(
            run_id=f"{source.candidate_set_id}.{cell.value}",
            harness=harness,
            execution_program=compiled_program,
            registry=registry,
            tasks_root=Path(tasks_root),
            experiment_id=source.experiment_id,
        )

    snapshots = bundles[HarnessProgramCell.H0_P0].task_snapshots
    if any(bundle.task_snapshots != snapshots for bundle in bundles.values()):
        raise ValueError("task package bytes changed while materializing the matched candidate set")
    candidates = tuple(
        MaterializedHarnessProgramCandidate(
            cell=cell,
            reference=build_harness_program_candidate_reference(
                request=source,
                cell=cell,
                bundle=bundles[cell],
            ),
            bundle=bundles[cell],
        )
        for cell in HarnessProgramCell
    )
    references = HarnessProgramCandidateSet(
        task_set_id=source.task_set_id,
        candidates=tuple(candidate.reference for candidate in candidates),
    )
    return MaterializedHarnessProgramCandidateSet(
        request=source,
        references=references,
        candidates=candidates,
    )


def build_harness_program_candidate_reference(
    *,
    request: HarnessProgramCandidateRequest,
    cell: HarnessProgramCell,
    bundle: RunPlan,
) -> HarnessProgramCandidateReference:
    """Derive one candidate identity from its exact source factors and compiled bundle."""
    source = HarnessProgramCandidateRequest.model_validate(request.model_dump(mode="python"))
    compiled = RunPlan.model_validate(bundle.model_dump(mode="python"))
    factor = _program_factor(source, cell)
    expected_spec = source.learned_harness_spec if _learned_harness(cell) else source.fixed_harness_spec
    if compiled.harness.kernel_ref != source.kernel_ref:
        raise ValueError("harness-program candidate bundle does not use the requested fixed kernel")
    if compiled.harness.source_spec != expected_spec:
        raise ValueError("harness-program candidate bundle does not use the requested harness factor")
    if compiled.execution_program.source_program_ref != factor.bind(compiled.harness.ref).ref:
        raise ValueError("harness-program candidate bundle does not use the requested program factor")
    if tuple(snapshot.task_id for snapshot in compiled.task_snapshots) != source.task_refs:
        raise ValueError("harness-program candidate bundle does not use the requested task surface")
    abi_sha256 = kernel_abi_commitment(source.kernel_ref)
    return HarnessProgramCandidateReference.create(
        cell=cell,
        kernel_ref=source.kernel_ref,
        kernel_abi_sha256=abi_sha256,
        policy_sha256=_policy_sha256(source),
        task_set_id=source.task_set_id,
        task_set_sha256=_task_set_sha256(compiled.task_snapshots),
        harness_ref=compiled.harness.ref,
        harness_abi_sha256=abi_sha256,
        program_ref=compiled.execution_program.source_program_ref,
        program_abi_sha256=abi_sha256,
        resource_sha256=_resource_sha256(source),
    )


def harness_runtime_semantics(spec: HarnessSpec) -> dict[str, Any]:
    """Return only Hx fields that can change compilation, execution, verification, or evidence."""
    source = HarnessSpec.model_validate(spec.model_dump(mode="python"))
    contract_semantics = {
        contract.contract_id: {
            "kind": contract.kind.value,
            "schema_ref": contract.schema_ref,
            "enforcement": contract.enforcement.value,
        }
        for contract in source.contracts
    }
    bindings: list[dict[str, Any]] = []
    for binding in source.bindings:
        configuration = binding.configuration.model_dump(mode="json")
        if configuration["kind"] == "agent":
            configuration.pop("agent_name", None)
        elif configuration["kind"] == "result_import":
            configuration.pop("ledger_namespace", None)
        bindings.append(
            {
                "capability_ref": binding.capability_ref.model_dump(mode="json"),
                "contracts": sorted(
                    (contract_semantics[contract_id] for contract_id in binding.contract_ids),
                    key=canonical_json_sha256,
                ),
                "configuration": configuration,
            }
        )
    return {
        "contracts": sorted(contract_semantics.values(), key=canonical_json_sha256),
        "budget": source.budget.model_dump(mode="json"),
        "recursion_policy": source.recursion_policy.model_dump(mode="json"),
        "bindings": sorted(bindings, key=canonical_json_sha256),
    }


def program_runtime_semantics(program: ProgramFactorTemplate) -> dict[str, Any]:
    """Return px behavior after removing factor identity and alpha-renaming node ids."""
    source = ProgramFactorTemplate.model_validate(program.model_dump(mode="python"))
    node_ids = {node.node_id: f"node-{index}" for index, node in enumerate(source.nodes)}
    nodes = [_rewrite_program_node_ids(node.model_dump(mode="json"), node_ids) for node in source.nodes]
    return {
        "nodes": nodes,
        "limits": source.limits.model_dump(mode="json"),
    }


def _rewrite_program_node_ids(value: Any, node_ids: dict[str, str], *, field_name: str | None = None) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_program_node_ids(item, node_ids, field_name=key) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_program_node_ids(item, node_ids, field_name=field_name) for item in value]
    if isinstance(value, str) and field_name in {
        "node_id",
        "depends_on",
        "true_node_id",
        "false_node_id",
    }:
        return node_ids.get(value, value)
    return value


ConfigurationT = TypeVar("ConfigurationT", bound=HarnessBindingConfiguration)


def _single_spec_configuration(
    spec: HarnessSpec,
    configuration_type: type[ConfigurationT],
    *,
    role: str,
) -> ConfigurationT:
    configurations = [
        binding.configuration for binding in spec.bindings if isinstance(binding.configuration, configuration_type)
    ]
    if len(configurations) != 1:
        raise ValueError(f"harness-program harness spec requires exactly one {role} binding")
    return configurations[0]


def _single_compiled_configuration(
    bundle: RunPlan,
    configuration_type: type[ConfigurationT],
    *,
    role: str,
) -> ConfigurationT:
    configurations = [
        binding.configuration
        for binding in bundle.harness.bindings
        if isinstance(binding.configuration, configuration_type)
    ]
    if len(configurations) != 1:
        raise ValueError(f"harness-program candidate requires exactly one compiled {role} binding")
    return configurations[0]


def _runtime_budget_payload(spec: HarnessSpec) -> dict[str, Any]:
    agent = _single_spec_configuration(spec, AgentBindingConfig, role="agent")
    compute = _single_spec_configuration(spec, ComputeBindingConfig, role="compute")
    contexts = sorted(
        configuration.max_tokens
        for configuration in (binding.configuration for binding in spec.bindings)
        if isinstance(configuration, ContextBindingConfig)
    )
    tools = sorted(
        configuration.max_calls
        for configuration in (binding.configuration for binding in spec.bindings)
        if isinstance(configuration, ToolBindingConfig)
    )
    return {
        "agent": {"max_turns": agent.max_turns, "timeout_seconds": agent.timeout_seconds},
        "compute": {
            "max_concurrency": compute.max_concurrency,
            "timeout_override_seconds": compute.timeout_override_seconds,
        },
        "context_max_tokens": contexts,
        "tool_max_calls": tools,
        "recursion_policy": spec.recursion_policy.model_dump(mode="json"),
    }


def _harness_spec(request: HarnessProgramCandidateRequest, cell: HarnessProgramCell) -> HarnessSpec:
    return request.learned_harness_spec if _learned_harness(cell) else request.fixed_harness_spec


def _program_factor(request: HarnessProgramCandidateRequest, cell: HarnessProgramCell) -> ProgramFactorTemplate:
    return (
        request.learned_program
        if cell in {HarnessProgramCell.H0_PX, HarnessProgramCell.HX_PX}
        else request.fixed_program
    )


def _learned_harness(cell: HarnessProgramCell) -> bool:
    return cell in {HarnessProgramCell.HX_P0, HarnessProgramCell.HX_PX}


def _task_set_sha256(snapshots: tuple[TaskSnapshotRef, ...]) -> str:
    return canonical_json_sha256(
        {
            "schema_version": "1",
            "task_snapshots": [snapshot.model_dump(mode="json") for snapshot in snapshots],
        }
    )


def _policy_sha256(request: HarnessProgramCandidateRequest) -> str:
    return canonical_json_sha256(
        {
            "schema_version": "1",
            "model": request.model,
            "seeds": list(request.seeds),
            "repetitions": request.repetitions,
        }
    )


def _resource_sha256(request: HarnessProgramCandidateRequest) -> str:
    return canonical_json_sha256(
        {
            "schema_version": "1",
            "harness_budget": request.harness_budget.model_dump(mode="json"),
            "program_limits": request.program_limits.model_dump(mode="json"),
            "runtime_budget": _runtime_budget_payload(request.fixed_harness_spec),
        }
    )
