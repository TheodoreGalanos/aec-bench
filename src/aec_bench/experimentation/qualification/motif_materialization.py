# ABOUTME: Materializes frozen motif selections into target-specific Hx and px harness-program factors.
# ABOUTME: Rebinds only declared task, model, and budget slots while preserving trusted motif structure.

from __future__ import annotations

from typing import Literal, Self

from pydantic import JsonValue, PositiveInt, field_validator, model_validator

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    LiteralValue,
    ProgramArgument,
    ProgramLimits,
    ProgramNode,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    HarnessBindingSpec,
    HarnessBudget,
    HarnessRecipe,
    TaskSourceBindingConfig,
)
from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    KernelRef,
    validate_sha256,
)
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.motifs import (
    MotifLibrary,
    MotifSelectionDecision,
    MotifSelectionOutcome,
    MotifSelectionRequest,
    MotifTemplate,
    resolve_motif_selection,
)
from aec_bench.experimentation.qualification.harness_program_study.candidates import (
    HarnessProgramCandidateRequest,
    ProgramFactorTemplate,
)


class HarnessMotifTemplatePayload(FrozenStrictModel):
    """Closed payload stored inside an Hx motif template."""

    schema_version: Literal["aecbench.hx-motif-template.v1"] = "aecbench.hx-motif-template.v1"
    recipe: HarnessRecipe


class ProgramMotifTemplatePayload(FrozenStrictModel):
    """Closed payload stored inside a px motif template."""

    schema_version: Literal["aecbench.px-motif-template.v1"] = "aecbench.px-motif-template.v1"
    factor: ProgramFactorTemplate


class MotifHarnessProgramInstantiationRequest(ContentAddressedModel):
    """Target-world controls used to instantiate one selected motif beside H0/p0."""

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
    fixed_harness_recipe: HarnessRecipe
    fixed_program: ProgramFactorTemplate

    @field_validator("task_refs")
    @classmethod
    def validate_task_refs(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value or value != tuple(sorted(set(value))):
            raise ValueError("motif instantiation requires canonical exact task refs")
        return value

    @model_validator(mode="after")
    def validate_repetitions(self) -> Self:
        if len(self.seeds) != self.repetitions or len(self.seeds) != len(set(self.seeds)):
            raise ValueError("motif instantiation requires one unique seed per repetition")
        return self


class InstantiatedMotifFactors(ContentAddressedModel):
    """Auditable selected-motif lineage plus the genuine matched candidate request it produced."""

    selected_motif_sha256: str
    selection_request_sha256: str
    selection_decision_sha256: str
    source_harness_template_sha256: str
    source_program_template_sha256: str
    harness_program_request: HarnessProgramCandidateRequest

    @field_validator(
        "selected_motif_sha256",
        "selection_request_sha256",
        "selection_decision_sha256",
        "source_harness_template_sha256",
        "source_program_template_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


def encode_harness_motif_template(recipe: HarnessRecipe) -> MotifTemplate:
    """Encode one typed source Hx recipe without permitting executable import hooks."""

    normalized = HarnessRecipe.model_validate(recipe.model_dump(mode="json"))
    payload = HarnessMotifTemplatePayload(recipe=normalized)
    return MotifTemplate.create(kind="hx", payload=payload.model_dump(mode="json"))


def encode_program_motif_template(factor: ProgramFactorTemplate) -> MotifTemplate:
    """Encode one typed harness-independent px factor."""

    normalized = ProgramFactorTemplate.model_validate(factor.model_dump(mode="json"))
    payload = ProgramMotifTemplatePayload(factor=normalized)
    return MotifTemplate.create(kind="px", payload=payload.model_dump(mode="json"))


def instantiate_selected_motif_factors(
    *,
    library: MotifLibrary,
    selection_request: MotifSelectionRequest,
    selection_decision: MotifSelectionDecision,
    request: MotifHarnessProgramInstantiationRequest,
) -> InstantiatedMotifFactors:
    """Resolve a frozen selection and rebind its typed factors to one exact target world."""

    selected = resolve_motif_selection(library, selection_request, selection_decision)
    if selected is None or selection_decision.outcome is not MotifSelectionOutcome.SELECTED:
        raise ValueError("motif selection did not select a motif")
    if selected.kernel_abi_sha256 != request.kernel_ref.content_sha256:
        raise ValueError("selected motif does not target the requested fixed-kernel ABI")

    source_recipe = _decode_harness_template(selected.hx_template)
    source_program = _decode_program_template(selected.px_template)
    rebound_program = rebind_program_task_inputs(
        source_program,
        source_task_refs=_task_source_refs(source_recipe),
        target_task_refs=request.task_refs,
    )
    learned_recipe = _rebind_harness_recipe(
        source_recipe,
        motif_sha256=selected.motif_sha256,
        task_refs=request.task_refs,
        model=request.model,
        budget=request.harness_budget,
    )
    learned_program = ProgramFactorTemplate(
        factor_id=f"{source_program.factor_id}.motif-{selected.motif_sha256[:12]}",
        version=source_program.version,
        nodes=rebound_program.nodes,
        limits=request.program_limits,
    )
    harness_program_request = HarnessProgramCandidateRequest(
        candidate_set_id=request.candidate_set_id,
        task_set_id=request.task_set_id,
        experiment_id=request.experiment_id,
        kernel_ref=request.kernel_ref,
        task_refs=request.task_refs,
        model=request.model,
        harness_budget=request.harness_budget,
        program_limits=request.program_limits,
        seeds=request.seeds,
        repetitions=request.repetitions,
        fixed_harness_recipe=request.fixed_harness_recipe,
        learned_harness_recipe=learned_recipe,
        fixed_program=request.fixed_program,
        learned_program=learned_program,
    )
    return InstantiatedMotifFactors(
        selected_motif_sha256=selected.motif_sha256,
        selection_request_sha256=selection_request.request_sha256,
        selection_decision_sha256=selection_decision.decision_sha256,
        source_harness_template_sha256=selected.hx_template.template_sha256,
        source_program_template_sha256=selected.px_template.template_sha256,
        harness_program_request=harness_program_request,
    )


def _decode_harness_template(template: MotifTemplate) -> HarnessRecipe:
    if template.kind != "hx":
        raise ValueError("selected Hx motif template has the wrong kind")
    try:
        return HarnessMotifTemplatePayload.model_validate(template.payload).recipe
    except ValueError as error:
        raise ValueError("selected Hx motif template is not a typed HarnessRecipe payload") from error


def _decode_program_template(template: MotifTemplate) -> ProgramFactorTemplate:
    if template.kind != "px":
        raise ValueError("selected px motif template has the wrong kind")
    try:
        return ProgramMotifTemplatePayload.model_validate(template.payload).factor
    except ValueError as error:
        raise ValueError("selected px motif template is not a typed ProgramFactorTemplate payload") from error


def rebind_program_task_inputs(
    source: ProgramFactorTemplate,
    *,
    source_task_refs: tuple[str, ...],
    target_task_refs: tuple[str, ...],
) -> ProgramFactorTemplate:
    """Rebind only allowlisted literal task-input ports under an exact one-to-one mapping."""

    if (
        not source_task_refs
        or not target_task_refs
        or len(source_task_refs) != len(target_task_refs)
        or len(source_task_refs) != len(set(source_task_refs))
        or len(target_task_refs) != len(set(target_task_refs))
    ):
        raise ValueError("program task rebinding requires exact one-to-one task cardinality")
    mapping = dict(zip(source_task_refs, target_task_refs, strict=True))
    nodes = tuple(_rebind_program_node_tasks(node, mapping=mapping) for node in source.nodes)
    return ProgramFactorTemplate(
        factor_id=source.factor_id,
        version=source.version,
        nodes=nodes,
        limits=source.limits,
    )


def _rebind_program_node_tasks(
    node: ProgramNode,
    *,
    mapping: dict[str, str],
) -> ProgramNode:
    if not isinstance(node, ActionNode | FanoutNode):
        return node
    task_ports = {
        "run_batch.v1": frozenset({"task_ref", "task_refs"}),
        "run_stage.v1": frozenset({"task_ref"}),
        "finalize_task.v1": frozenset({"task_ref"}),
    }.get(node.operation_id, frozenset())
    arguments = tuple(
        _rebind_program_argument(argument, mapping=mapping) if argument.name in task_ports else argument
        for argument in node.arguments
    )
    return node.model_copy(update={"arguments": arguments})


def _rebind_program_argument(
    argument: ProgramArgument,
    *,
    mapping: dict[str, str],
) -> ProgramArgument:
    value = argument.value
    if not isinstance(value, LiteralValue):
        return argument
    rebound: JsonValue
    if argument.name == "task_ref":
        if not isinstance(value.value, str) or value.value not in mapping:
            raise ValueError("program task_ref is outside the declared source task slots")
        rebound = mapping[value.value]
    elif argument.name == "task_refs":
        if not isinstance(value.value, list):
            raise ValueError("program task_refs are outside the declared source task slots")
        task_refs: list[str] = []
        for task_ref in value.value:
            if not isinstance(task_ref, str) or task_ref not in mapping:
                raise ValueError("program task_refs are outside the declared source task slots")
            task_refs.append(task_ref)
        if len(task_refs) != len(set(task_refs)):
            raise ValueError("program task_refs must be unique before rebinding")
        rebound_task_refs: list[JsonValue] = [mapping[task_ref] for task_ref in task_refs]
        rebound = rebound_task_refs
    else:  # pragma: no cover - callers admit only the closed task-input port set
        return argument
    return ProgramArgument(
        name=argument.name,
        value=LiteralValue(value=rebound),
    )


def _rebind_harness_recipe(
    source: HarnessRecipe,
    *,
    motif_sha256: str,
    task_refs: tuple[str, ...],
    model: str,
    budget: HarnessBudget,
) -> HarnessRecipe:
    bindings = tuple(_rebind_harness_binding(binding, task_refs=task_refs, model=model) for binding in source.bindings)
    return HarnessRecipe(
        recipe_id=f"{source.recipe_id}.motif-{motif_sha256[:12]}",
        version=source.version,
        summary=source.summary,
        contracts=source.contracts,
        budget=budget,
        recursion_policy=source.recursion_policy,
        bindings=bindings,
    )


def _task_source_refs(recipe: HarnessRecipe) -> tuple[str, ...]:
    sources = tuple(
        binding.configuration
        for binding in recipe.bindings
        if isinstance(binding.configuration, TaskSourceBindingConfig)
    )
    if len(sources) != 1:
        raise ValueError("motif Hx template requires exactly one typed task-source slot")
    return sources[0].task_refs


def _rebind_harness_binding(
    binding: HarnessBindingSpec,
    *,
    task_refs: tuple[str, ...],
    model: str,
) -> HarnessBindingSpec:
    configuration = binding.configuration
    if isinstance(configuration, TaskSourceBindingConfig):
        configuration = TaskSourceBindingConfig(task_refs=task_refs)
    elif isinstance(configuration, AgentBindingConfig):
        configuration = AgentBindingConfig(
            agent_name=configuration.agent_name,
            model=model,
            max_turns=configuration.max_turns,
            timeout_seconds=configuration.timeout_seconds,
        )
    return HarnessBindingSpec(
        binding_id=binding.binding_id,
        capability_ref=binding.capability_ref,
        depends_on=binding.depends_on,
        topology_role=binding.topology_role,
        contract_ids=binding.contract_ids,
        configuration=configuration,
    )
