# ABOUTME: Applies allowlisted Hx and px patches through the canonical repair-rule registry.
# ABOUTME: Validates exact parent structure before producing one changed candidate surface.

from __future__ import annotations

from dataclasses import dataclass

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    JoinNode,
    JoinStrategy,
    LiteralValue,
    OutputValue,
    ProgramArgument,
    ProgramLimits,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
    VerifyNode,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    HarnessBindingSpec,
    HarnessCompileRequest,
    HarnessRecipe,
)
from aec_bench.contracts.run_bundle import RunBundle
from aec_bench.evolution.repair_lifecycle import (
    CompiledRepairCandidate,
    RepairCandidate,
    RepairProgramTemplate,
)
from aec_bench.meta_harness.repair_rule_registry import (
    RepairRuleRegistration,
    RepairRuleRegistry,
)
from aec_bench.meta_harness.repair_runtime.contracts import (
    HarnessAgentCapabilityPatch,
    HarnessAgentMaxTurnsPatch,
    ProgramCoalesceTaskBatchPatch,
    ProgramMaterializeDeclaredStageGraphPatch,
    ProgramMaxTotalAttemptsPatch,
    ProgramNodeRetryPatch,
    RepairDeclaredStageGraphEvidence,
)


@dataclass(frozen=True)
class _RepairPatchContext:
    """Exact parent state made available to one registered patch rule."""

    parent: RepairCandidate
    compiled_parent: CompiledRepairCandidate | None
    iteration: int


@dataclass(frozen=True)
class _RepairPatchResult:
    """The two mutable candidate surfaces returned by one registered patch rule."""

    harness_request: HarnessCompileRequest
    program_template: RepairProgramTemplate


def _patch_agent_max_turns(
    request: HarnessCompileRequest,
    patch: HarnessAgentMaxTurnsPatch,
    *,
    iteration: int,
) -> HarnessCompileRequest:
    matches = [binding for binding in request.recipe.bindings if binding.binding_id == patch.binding_id]
    if len(matches) != 1:
        raise ValueError("harness turn patch must target exactly one agent binding")
    binding = matches[0]
    current = binding.configuration
    if not isinstance(current, AgentBindingConfig):
        raise ValueError("harness turn patch must target exactly one agent binding")
    if current.max_turns == patch.max_turns:
        raise ValueError("harness turn patch must change the owned binding")
    replacement = AgentBindingConfig(
        agent_name=current.agent_name,
        model=current.model,
        max_turns=patch.max_turns,
        timeout_seconds=current.timeout_seconds,
    )
    bindings = tuple(
        HarnessBindingSpec(
            binding_id=item.binding_id,
            capability_ref=item.capability_ref,
            depends_on=item.depends_on,
            topology_role=item.topology_role,
            contract_ids=item.contract_ids,
            configuration=replacement if item.binding_id == patch.binding_id else item.configuration,
        )
        for item in request.recipe.bindings
    )
    recipe = HarnessRecipe(
        recipe_id=request.recipe.recipe_id,
        version=request.recipe.version,
        summary=request.recipe.summary,
        contracts=request.recipe.contracts,
        budget=request.recipe.budget,
        recursion_policy=request.recipe.recursion_policy,
        bindings=bindings,
    )
    return HarnessCompileRequest(
        request_id=f"{request.request_id}.repair-{iteration}",
        kernel_ref=request.kernel_ref,
        recipe=recipe,
    )


def _patch_agent_capability(
    request: HarnessCompileRequest,
    patch: HarnessAgentCapabilityPatch,
    *,
    iteration: int,
) -> HarnessCompileRequest:
    matches = [binding for binding in request.recipe.bindings if binding.binding_id == patch.binding_id]
    if len(matches) != 1 or not isinstance(matches[0].configuration, AgentBindingConfig):
        raise ValueError("harness capability patch must target exactly one agent binding")
    target = matches[0]
    if target.capability_ref != patch.expected_capability_ref:
        raise ValueError("harness capability patch expected capability does not match the target binding")
    replacement = target.model_copy(update={"capability_ref": patch.replacement_capability_ref})
    bindings = tuple(
        replacement if binding.binding_id == patch.binding_id else binding for binding in request.recipe.bindings
    )
    recipe_payload = request.recipe.model_dump(mode="python", exclude={"content_sha256"})
    recipe_payload["bindings"] = bindings
    recipe = HarnessRecipe.model_validate(recipe_payload)
    return HarnessCompileRequest(
        request_id=f"{request.request_id}.repair-{iteration}",
        kernel_ref=request.kernel_ref,
        recipe=recipe,
    )


def _patch_program_retry(
    template: RepairProgramTemplate,
    patch: ProgramNodeRetryPatch,
) -> RepairProgramTemplate:
    matches = [node for node in template.nodes if node.node_id == patch.node_id]
    if len(matches) != 1 or not isinstance(matches[0], ActionNode | FanoutNode | VerifyNode):
        raise ValueError("program retry patch must target exactly one executable node")
    target = matches[0]
    current_attempts = target.retry.max_attempts if target.retry is not None else 1
    if patch.retry.max_attempts <= current_attempts:
        raise ValueError("program retry patch must strictly increase effective attempts")
    nodes = tuple(
        node.model_copy(update={"retry": patch.retry}) if node.node_id == patch.node_id else node
        for node in template.nodes
    )
    return RepairProgramTemplate(
        program_id=template.program_id,
        version=template.version,
        nodes=nodes,
        limits=template.limits,
    )


def _patch_program_max_total_attempts(
    template: RepairProgramTemplate,
    patch: ProgramMaxTotalAttemptsPatch,
) -> RepairProgramTemplate:
    if patch.max_total_attempts <= template.limits.max_total_attempts:
        raise ValueError("program attempt-limit patch must strictly increase the owned limit")
    limits = template.limits.model_copy(update={"max_total_attempts": patch.max_total_attempts})
    return RepairProgramTemplate(
        program_id=template.program_id,
        version=template.version,
        nodes=template.nodes,
        limits=limits,
    )


def validate_program_declared_stage_graph_source(
    template: RepairProgramTemplate,
    *,
    task_refs: tuple[str, ...],
) -> None:
    """Reject anything except one exact monolithic run_batch followed by a clean stop."""
    if len(template.nodes) != 2:
        raise ValueError("declared-stage materialization requires an exact monolithic run_batch source")
    run, stop = template.nodes
    if not isinstance(run, ActionNode) or not isinstance(stop, StopNode):
        raise ValueError("declared-stage materialization requires an exact monolithic run_batch source")
    accepted_arguments: tuple[tuple[ProgramArgument, ...], ...] = ((),)
    if len(task_refs) == 1:
        accepted_arguments += (
            (
                ProgramArgument(
                    name="task_ref",
                    value=LiteralValue(value=task_refs[0]),
                ),
            ),
        )
    accepted_arguments += (
        (
            ProgramArgument(
                name="task_refs",
                value=LiteralValue(value=list(task_refs)),
            ),
        ),
    )
    if (
        run.depends_on
        or run.operation_id != "run_batch.v1"
        or run.arguments not in accepted_arguments
        or run.retry is not None
        or run.recursion is not None
        or stop.depends_on != (run.node_id,)
        or stop.outcome is not StopOutcome.SUCCEEDED
        or stop.result is not None
        or stop.message is not None
    ):
        raise ValueError("declared-stage materialization requires an exact monolithic run_batch source")


def materialize_program_declared_stage_graph(
    template: RepairProgramTemplate,
    patch: ProgramMaterializeDeclaredStageGraphPatch,
) -> RepairProgramTemplate:
    """Build the deterministic staged px after enforcing exact source and fixed limits."""
    task_refs = tuple(item.task_id for item in patch.task_graphs)
    validate_program_declared_stage_graph_source(template, task_refs=task_refs)
    if not _declared_stage_materialization_fits_limits(patch.task_graphs, template.limits):
        raise ValueError("declared-stage materialization exceeds the fixed px or Hx budget")
    return RepairProgramTemplate(
        program_id=template.program_id,
        version=template.version,
        nodes=_declared_stage_materialization_nodes(patch.task_graphs),
        limits=template.limits,
    )


def _declared_stage_materialization_fits_limits(
    task_graphs: tuple[RepairDeclaredStageGraphEvidence, ...],
    limits: ProgramLimits,
) -> bool:
    nodes = _declared_stage_materialization_nodes(task_graphs)
    required_attempts = sum(len(item.stage_graph.stages) + 1 for item in task_graphs)
    return len(nodes) <= limits.max_nodes and required_attempts <= limits.max_total_attempts


def _declared_stage_materialization_nodes(
    task_graphs: tuple[RepairDeclaredStageGraphEvidence, ...],
) -> tuple[ActionNode | JoinNode | StopNode, ...]:
    nodes: list[ActionNode | JoinNode | StopNode] = []
    finalizer_ids: list[str] = []
    for task_index, task_graph in enumerate(task_graphs, start=1):
        prefix = f"task-{task_index:03d}"
        graph = task_graph.stage_graph
        stage_node_ids = {
            stage_id: f"{prefix}.stage-{stage_index:03d}"
            for stage_index, stage_id in enumerate(graph.topological_order, start=1)
        }
        task_argument = ProgramArgument(
            name="task_ref",
            value=LiteralValue(value=task_graph.task_id),
        )
        for stage_id in graph.topological_order:
            predecessors = graph.predecessor_stage_ids(stage_id)
            dependencies: tuple[str, ...] = ()
            arguments: list[ProgramArgument] = [
                task_argument,
                ProgramArgument(
                    name="stage_id",
                    value=LiteralValue(value=stage_id),
                ),
            ]
            if len(predecessors) == 1:
                source_id = stage_node_ids[predecessors[0]]
                dependencies = (source_id,)
                arguments.append(
                    ProgramArgument(
                        name="upstream_receipts",
                        value=OutputValue(
                            ref=ProgramOutputRef(
                                node_id=source_id,
                                output_port="stage_receipt",
                            )
                        ),
                    )
                )
            elif len(predecessors) > 1:
                join_id = f"{stage_node_ids[stage_id]}.inputs"
                predecessor_node_ids = tuple(stage_node_ids[item] for item in predecessors)
                nodes.append(
                    JoinNode(
                        node_id=join_id,
                        depends_on=predecessor_node_ids,
                        sources=tuple(
                            ProgramOutputRef(
                                node_id=node_id,
                                output_port="stage_receipt",
                            )
                            for node_id in predecessor_node_ids
                        ),
                        strategy=JoinStrategy.ALL,
                    )
                )
                dependencies = (join_id,)
                arguments.append(
                    ProgramArgument(
                        name="upstream_receipts",
                        value=OutputValue(
                            ref=ProgramOutputRef(
                                node_id=join_id,
                                output_port="result",
                            )
                        ),
                    )
                )
            nodes.append(
                ActionNode(
                    node_id=stage_node_ids[stage_id],
                    depends_on=dependencies,
                    operation_id="run_stage.v1",
                    arguments=tuple(arguments),
                )
            )

        all_stage_node_ids = tuple(stage_node_ids[stage_id] for stage_id in graph.topological_order)
        all_stages_join_id = f"{prefix}.all-stages"
        nodes.append(
            JoinNode(
                node_id=all_stages_join_id,
                depends_on=all_stage_node_ids,
                sources=tuple(
                    ProgramOutputRef(
                        node_id=node_id,
                        output_port="stage_receipt",
                    )
                    for node_id in all_stage_node_ids
                ),
                strategy=JoinStrategy.ALL,
            )
        )
        finalizer_id = f"{prefix}.finalize"
        nodes.append(
            ActionNode(
                node_id=finalizer_id,
                depends_on=(all_stages_join_id,),
                operation_id="finalize_task.v1",
                arguments=(
                    task_argument,
                    ProgramArgument(
                        name="stage_receipts",
                        value=OutputValue(
                            ref=ProgramOutputRef(
                                node_id=all_stages_join_id,
                                output_port="result",
                            )
                        ),
                    ),
                ),
            )
        )
        finalizer_ids.append(finalizer_id)
    nodes.append(
        StopNode(
            node_id="stop",
            depends_on=tuple(finalizer_ids),
            outcome=StopOutcome.SUCCEEDED,
        )
    )
    return tuple(nodes)


def validate_program_batch_coalescing_source(
    template: RepairProgramTemplate,
    *,
    source_node_ids: tuple[str, str],
    replacement_node_id: str,
    task_refs: tuple[str, str],
) -> None:
    """Reject anything except the preregistered serial two-task source fragment."""
    _program_batch_coalescing_stop(
        template,
        source_node_ids=source_node_ids,
        replacement_node_id=replacement_node_id,
        task_refs=task_refs,
    )


def _patch_program_coalesce_task_batch(
    template: RepairProgramTemplate,
    patch: ProgramCoalesceTaskBatchPatch,
) -> RepairProgramTemplate:
    stop = _program_batch_coalescing_stop(
        template,
        source_node_ids=patch.source_node_ids,
        replacement_node_id=patch.replacement_node_id,
        task_refs=patch.task_refs,
    )
    replacement = ActionNode(
        node_id=patch.replacement_node_id,
        operation_id="run_batch.v1",
        arguments=(
            ProgramArgument(
                name="task_refs",
                value=LiteralValue(value=list(patch.task_refs)),
            ),
        ),
    )
    rebound_stop = stop.model_copy(update={"depends_on": (patch.replacement_node_id,)})
    return RepairProgramTemplate(
        program_id=template.program_id,
        version=template.version,
        nodes=(replacement, rebound_stop),
        limits=template.limits,
    )


def _apply_harness_max_turns_rule(
    context: _RepairPatchContext,
    patch: HarnessAgentMaxTurnsPatch,
) -> _RepairPatchResult:
    return _RepairPatchResult(
        harness_request=_patch_agent_max_turns(
            context.parent.harness_request,
            patch,
            iteration=context.iteration,
        ),
        program_template=context.parent.program_template,
    )


def _apply_harness_capability_rule(
    context: _RepairPatchContext,
    patch: HarnessAgentCapabilityPatch,
) -> _RepairPatchResult:
    return _RepairPatchResult(
        harness_request=_patch_agent_capability(
            context.parent.harness_request,
            patch,
            iteration=context.iteration,
        ),
        program_template=context.parent.program_template,
    )


def _apply_program_retry_rule(
    context: _RepairPatchContext,
    patch: ProgramNodeRetryPatch,
) -> _RepairPatchResult:
    return _RepairPatchResult(
        harness_request=context.parent.harness_request,
        program_template=_patch_program_retry(
            context.parent.program_template,
            patch,
        ),
    )


def _apply_program_attempt_limit_rule(
    context: _RepairPatchContext,
    patch: ProgramMaxTotalAttemptsPatch,
) -> _RepairPatchResult:
    return _RepairPatchResult(
        harness_request=context.parent.harness_request,
        program_template=_patch_program_max_total_attempts(
            context.parent.program_template,
            patch,
        ),
    )


def _apply_program_batch_coalescing_rule(
    context: _RepairPatchContext,
    patch: ProgramCoalesceTaskBatchPatch,
) -> _RepairPatchResult:
    compiled_parent = context.compiled_parent
    if compiled_parent is None:
        raise ValueError("program batch-coalescing patch requires the exact compiled parent")
    if compiled_parent.program.content_sha256 != patch.expected_program_sha256:
        raise ValueError("program batch-coalescing patch expected program hash does not match the parent")
    return _RepairPatchResult(
        harness_request=context.parent.harness_request,
        program_template=_patch_program_coalesce_task_batch(
            context.parent.program_template,
            patch,
        ),
    )


def _apply_declared_stage_graph_rule(
    context: _RepairPatchContext,
    patch: ProgramMaterializeDeclaredStageGraphPatch,
) -> _RepairPatchResult:
    compiled_parent = context.compiled_parent
    if compiled_parent is None:
        raise ValueError("declared-stage graph patch requires the exact compiled parent")
    if compiled_parent.program.content_sha256 != patch.expected_program_sha256:
        raise ValueError("declared-stage graph patch expected program hash does not match the parent")
    expected_graphs = _declared_stage_graph_evidence(compiled_parent.bundle)
    if patch.task_graphs != expected_graphs:
        raise ValueError("declared-stage graph patch task/world graph evidence does not match the parent")
    return _RepairPatchResult(
        harness_request=context.parent.harness_request,
        program_template=materialize_program_declared_stage_graph(
            context.parent.program_template,
            patch,
        ),
    )


_REPAIR_RULE_REGISTRY = RepairRuleRegistry[_RepairPatchContext, _RepairPatchResult](
    (
        RepairRuleRegistration(
            rule_id="harness_agent_max_turns",
            patch_type=HarnessAgentMaxTurnsPatch,
            apply=_apply_harness_max_turns_rule,
        ),
        RepairRuleRegistration(
            rule_id="harness_agent_capability",
            patch_type=HarnessAgentCapabilityPatch,
            apply=_apply_harness_capability_rule,
        ),
        RepairRuleRegistration(
            rule_id="program_node_retry",
            patch_type=ProgramNodeRetryPatch,
            apply=_apply_program_retry_rule,
        ),
        RepairRuleRegistration(
            rule_id="program_max_total_attempts",
            patch_type=ProgramMaxTotalAttemptsPatch,
            apply=_apply_program_attempt_limit_rule,
        ),
        RepairRuleRegistration(
            rule_id="program_coalesce_task_batch",
            patch_type=ProgramCoalesceTaskBatchPatch,
            apply=_apply_program_batch_coalescing_rule,
        ),
        RepairRuleRegistration(
            rule_id="program_materialize_declared_stage_graph",
            patch_type=ProgramMaterializeDeclaredStageGraphPatch,
            apply=_apply_declared_stage_graph_rule,
        ),
    )
)


def _program_batch_coalescing_stop(
    template: RepairProgramTemplate,
    *,
    source_node_ids: tuple[str, str],
    replacement_node_id: str,
    task_refs: tuple[str, str],
) -> StopNode:
    if template.limits.max_total_attempts != 1:
        raise ValueError("program batch-coalescing requires max_total_attempts to remain one")
    if replacement_node_id in {node.node_id for node in template.nodes}:
        raise ValueError("program batch-coalescing replacement node already exists")
    if len(template.nodes) != 3:
        raise ValueError("program batch-coalescing requires the exact serial batch source")
    nodes = {node.node_id: node for node in template.nodes}
    primary = nodes.get(source_node_ids[0])
    secondary = nodes.get(source_node_ids[1])
    stop_nodes = tuple(node for node in template.nodes if isinstance(node, StopNode))
    if (
        not _is_exact_single_task_batch_action(
            primary,
            depends_on=(),
            task_ref=task_refs[0],
        )
        or not _is_exact_single_task_batch_action(
            secondary,
            depends_on=(source_node_ids[0],),
            task_ref=task_refs[1],
        )
        or len(stop_nodes) != 1
    ):
        raise ValueError("program batch-coalescing requires the exact serial batch source")
    stop = stop_nodes[0]
    if (
        tuple(node.node_id for node in template.nodes) != (*source_node_ids, stop.node_id)
        or stop.depends_on != (source_node_ids[1],)
        or stop.outcome is not StopOutcome.SUCCEEDED
        or stop.result is not None
        or stop.message is not None
    ):
        raise ValueError("program batch-coalescing requires the exact serial batch source")
    return stop


def _is_exact_single_task_batch_action(
    node: object,
    *,
    depends_on: tuple[str, ...],
    task_ref: str,
) -> bool:
    if not isinstance(node, ActionNode):
        return False
    return (
        node.depends_on == depends_on
        and node.operation_id == "run_batch.v1"
        and node.retry is None
        and node.recursion is None
        and node.arguments
        == (
            ProgramArgument(
                name="task_ref",
                value=LiteralValue(value=task_ref),
            ),
        )
    )


def _declared_stage_graph_evidence(
    bundle: RunBundle,
) -> tuple[RepairDeclaredStageGraphEvidence, ...]:
    evidence: list[RepairDeclaredStageGraphEvidence] = []
    for snapshot in bundle.task_snapshots:
        world = snapshot.world
        graph = world.stage_graph if world is not None else None
        if world is None or graph is None:
            return ()
        evidence.append(
            RepairDeclaredStageGraphEvidence(
                task_id=snapshot.task_id,
                task_package_sha256=snapshot.package_sha256,
                world_package_sha256=world.world_package_sha256,
                stage_graph=graph,
            )
        )
    return tuple(evidence)
