# ABOUTME: Builds source scopes, allocates budgets, and lowers validated proposal graphs.
# ABOUTME: Produces deterministic execution programs under the frozen profile and harness.

from aec_bench.contracts.execution_program import (
    ActionNode,
    ExecutionProgram,
    JoinNode,
    JoinStrategy,
    OutputValue,
    ProgramArgument,
    ProgramLimits,
    ProgramOutputRef,
    StopNode,
    StopOutcome,
)
from aec_bench.contracts.harness_instance import (
    AgentBindingConfig,
    CompiledHarnessInstance,
    ContextBindingConfig,
    HarnessBudget,
    ToolBindingConfig,
)
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.proposal_execution.graph import ExecutableCandidateGraph, MonolithicIncumbentProgram
from aec_bench.contracts.proposal_execution_budget import CandidateBudgetPlan, NodeBudgetReservation
from aec_bench.contracts.proposal_execution_context import (
    CompiledNodeContextScope,
    ProposalSourceScopeManifest,
    ScopedSourceMaterialization,
)
from aec_bench.contracts.proposal_execution_profile import ProposalExecutionProfile
from aec_bench.contracts.proposal_execution_types import (
    NodeInstructionVisibility,
    ProposalCompileRejectionCode,
    ProposalExecutionSemantics,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef

from .constants import (
    _CHECK_OPERATION_ID,
    _COMPLETE_JOIN_NODE_ID,
    _FINALIZER_OPERATION_ID,
    _SEMANTIC_OPERATION_ID,
    _STOP_NODE_ID,
)
from .errors import ProposalCompilationHostError, _CandidateCompileError


def _build_source_scope_manifest(
    *,
    graph: ExecutableCandidateGraph,
    proposal_freeze: ProposalFreeze,
    task_snapshot: TaskSnapshotRef,
    source_materializations: tuple[ScopedSourceMaterialization, ...],
) -> ProposalSourceScopeManifest:
    node_scopes = [
        CompiledNodeContextScope(
            node_id=subtask.node_id,
            source_ids=subtask.source_scope.source_ids,
            upstream_handoff_ids=tuple(
                handoff.handoff_id for handoff in graph.handoffs if handoff.consumer_node_id == subtask.node_id
            ),
            instruction_visibility=NodeInstructionVisibility.OBJECTIVE_ONLY,
        )
        for subtask in graph.semantic_subtasks
    ]
    node_scopes.append(
        CompiledNodeContextScope(
            node_id=graph.finalizer.node_id,
            source_ids=graph.finalizer.source_scope.source_ids,
            upstream_handoff_ids=tuple(
                handoff.handoff_id for handoff in graph.handoffs if handoff.consumer_node_id == graph.finalizer.node_id
            ),
            instruction_visibility=NodeInstructionVisibility.PUBLIC_TASK,
        )
    )
    try:
        return ProposalSourceScopeManifest(
            proposal_graph_sha256=graph.content_sha256,
            problem_view_sha256=proposal_freeze.problem_view.content_sha256,
            task_package_sha256=task_snapshot.package_sha256,
            sources=source_materializations,
            node_scopes=tuple(node_scopes),
        )
    except ValueError as error:
        raise ProposalCompilationHostError(f"host source-scope manifest could not be sealed: {error}") from error


def _build_budget_plan(
    *,
    graph: ExecutableCandidateGraph,
    proposal_freeze: ProposalFreeze,
    fixed_harness: CompiledHarnessInstance,
    aggregate_budget: HarnessBudget,
    execution_profile: ProposalExecutionProfile,
    allocation_policy_sha256: str,
    session_overhead_seconds: int,
) -> CandidateBudgetPlan:
    node_ids = graph.node_ids
    node_count = len(node_ids)
    if aggregate_budget.max_total_attempts < node_count:
        raise _budget_infeasible("candidate requires one attempt per model-bearing node")
    agent_configurations = tuple(
        binding.configuration
        for binding in fixed_harness.bindings
        if isinstance(binding.configuration, AgentBindingConfig)
    )
    context_configurations = tuple(
        binding.configuration
        for binding in fixed_harness.bindings
        if isinstance(binding.configuration, ContextBindingConfig)
    )
    tool_configurations = tuple(
        binding.configuration
        for binding in fixed_harness.bindings
        if isinstance(binding.configuration, ToolBindingConfig)
    )
    if len(agent_configurations) != 1 or len(context_configurations) > 1 or len(tool_configurations) > 1:
        raise ProposalCompilationHostError("fixed harness has unsupported profile-bound budget cardinality")
    agent = agent_configurations[0]
    agent_turns = _partition_integer(
        min(aggregate_budget.max_agent_turns, agent.max_turns * node_count),
        node_count,
        minimum=1,
        label="agent-turn",
    )
    context_cap = (
        context_configurations[0].max_tokens if context_configurations else aggregate_budget.max_context_tokens
    )
    context_tokens = _partition_integer(
        min(aggregate_budget.max_context_tokens, context_cap * node_count),
        node_count,
        minimum=1,
        label="context",
    )
    tool_cap = tool_configurations[0].max_calls if tool_configurations else 0
    tool_calls = _partition_integer(
        min(aggregate_budget.max_tool_calls, tool_cap * node_count),
        node_count,
        minimum=0,
        label="tool-call",
    )
    remaining_runtime = aggregate_budget.max_runtime_seconds - session_overhead_seconds
    runtime_seconds = _partition_integer(
        min(remaining_runtime, agent.timeout_seconds * node_count),
        node_count,
        minimum=1,
        label="runtime",
    )
    token_reservations = _partition_optional_integer(
        aggregate_budget.max_tokens,
        node_count,
        label="token",
    )
    cost_reservations = _partition_optional_float(
        aggregate_budget.max_cost_usd,
        node_count,
    )
    reservations = tuple(
        NodeBudgetReservation(
            node_id=node_id,
            max_attempts=1,
            max_agent_turns=agent_turns[index],
            max_tool_calls=tool_calls[index],
            max_context_tokens=context_tokens[index],
            max_runtime_seconds=runtime_seconds[index],
            max_tokens=(None if token_reservations is None else token_reservations[index]),
            max_cost_usd=(None if cost_reservations is None else cost_reservations[index]),
        )
        for index, node_id in enumerate(node_ids)
    )
    try:
        return CandidateBudgetPlan(
            candidate_id=graph.candidate_id,
            proposal_graph_sha256=graph.content_sha256,
            proposal_freeze_sha256=proposal_freeze.content_sha256,
            fixed_harness_ref=fixed_harness.ref,
            allocation_policy_sha256=allocation_policy_sha256,
            aggregate_budget=aggregate_budget,
            execution_semantics=ProposalExecutionSemantics(execution_profile.scheduling.semantics.value),
            session_overhead_seconds=session_overhead_seconds,
            reservations=reservations,
        )
    except ValueError as error:
        raise _budget_infeasible(str(error)) from error


def _partition_integer(
    total: int,
    count: int,
    *,
    minimum: int,
    label: str,
) -> tuple[int, ...]:
    if total < minimum * count:
        raise _budget_infeasible(f"aggregate {label} capacity cannot reserve {count} nodes")
    base, remainder = divmod(total, count)
    return tuple(base + (1 if index < remainder else 0) for index in range(count))


def _partition_optional_integer(
    total: int | None,
    count: int,
    *,
    label: str,
) -> tuple[int, ...] | None:
    if total is None:
        return None
    return _partition_integer(total, count, minimum=1, label=label)


def _partition_optional_float(
    total: float | None,
    count: int,
) -> tuple[float, ...] | None:
    if total is None:
        return None
    share = total / count
    values = [share for _ in range(count - 1)]
    values.append(total - sum(values))
    if any(value <= 0.0 for value in values):
        raise _budget_infeasible("aggregate cost capacity cannot reserve every node")
    return tuple(values)


def _budget_infeasible(message: str) -> _CandidateCompileError:
    return _CandidateCompileError(
        ProposalCompileRejectionCode.BUDGET_ALLOCATION_INFEASIBLE,
        message,
    )


def _lower_candidate_program(
    *,
    graph: ExecutableCandidateGraph,
    fixed_harness: CompiledHarnessInstance,
    aggregate_budget: HarnessBudget,
    execution_profile: ProposalExecutionProfile,
) -> ExecutionProgram:
    if isinstance(graph, MonolithicIncumbentProgram):
        return _lower_monolithic_incumbent(
            graph=graph,
            fixed_harness=fixed_harness,
            aggregate_budget=aggregate_budget,
            execution_profile=execution_profile,
        )
    predecessors: dict[str, set[str]] = {subtask.node_id: set() for subtask in graph.semantic_subtasks}
    for handoff in graph.handoffs:
        if handoff.consumer_node_id in predecessors:
            predecessors[handoff.consumer_node_id].add(handoff.producer_node_id)

    generated_nodes: list[ActionNode | JoinNode | StopNode] = []
    generated_ids = set(graph.node_ids)
    if _STOP_NODE_ID in generated_ids:
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal node id collides with the fixed stop node",
            subject_ids=(_STOP_NODE_ID,),
        )

    for subtask in graph.semantic_subtasks:
        predecessor_checks = tuple(f"check.{node_id}" for node_id in sorted(predecessors[subtask.node_id]))
        semantic_dependencies: tuple[str, ...]
        if len(predecessor_checks) > 1:
            dependency_node_id = f"join.{subtask.node_id}.inputs"
            _claim_generated_id(dependency_node_id, generated_ids)
            generated_nodes.append(
                JoinNode(
                    node_id=dependency_node_id,
                    depends_on=predecessor_checks,
                    sources=tuple(
                        ProgramOutputRef(
                            node_id=node_id,
                            output_port="result",
                        )
                        for node_id in predecessor_checks
                    ),
                    strategy=JoinStrategy.ALL,
                )
            )
            semantic_dependencies = (dependency_node_id,)
        else:
            semantic_dependencies = predecessor_checks
        generated_nodes.append(
            ActionNode(
                node_id=subtask.node_id,
                depends_on=semantic_dependencies,
                operation_id=_SEMANTIC_OPERATION_ID,
            )
        )
        check_node_id = f"check.{subtask.node_id}"
        _claim_generated_id(check_node_id, generated_ids)
        generated_nodes.append(
            ActionNode(
                node_id=check_node_id,
                depends_on=(subtask.node_id,),
                operation_id=_CHECK_OPERATION_ID,
                arguments=(
                    ProgramArgument(
                        name="subject",
                        value=OutputValue(
                            ref=ProgramOutputRef(
                                node_id=subtask.node_id,
                                output_port="result",
                            )
                        ),
                    ),
                ),
            )
        )

    check_node_ids = tuple(f"check.{subtask.node_id}" for subtask in graph.semantic_subtasks)
    if len(check_node_ids) == 1:
        final_source_node_id = check_node_ids[0]
    else:
        _claim_generated_id(_COMPLETE_JOIN_NODE_ID, generated_ids)
        generated_nodes.append(
            JoinNode(
                node_id=_COMPLETE_JOIN_NODE_ID,
                depends_on=check_node_ids,
                sources=tuple(
                    ProgramOutputRef(
                        node_id=node_id,
                        output_port="result",
                    )
                    for node_id in check_node_ids
                ),
                strategy=JoinStrategy.ALL,
            )
        )
        final_source_node_id = _COMPLETE_JOIN_NODE_ID
    generated_nodes.append(
        ActionNode(
            node_id=graph.finalizer.node_id,
            depends_on=(final_source_node_id,),
            operation_id=_FINALIZER_OPERATION_ID,
            arguments=(
                ProgramArgument(
                    name="findings",
                    value=OutputValue(
                        ref=ProgramOutputRef(
                            node_id=final_source_node_id,
                            output_port="result",
                        )
                    ),
                ),
            ),
        )
    )
    generated_nodes.append(
        StopNode(
            node_id=_STOP_NODE_ID,
            depends_on=(graph.finalizer.node_id,),
            outcome=StopOutcome.SUCCEEDED,
            result=ProgramOutputRef(
                node_id=graph.finalizer.node_id,
                output_port="result",
            ),
        )
    )
    nodes = tuple(sorted(generated_nodes, key=lambda node: node.node_id))
    try:
        return ExecutionProgram(
            program_id=f"px.proposal.{graph.candidate_id}",
            version="1.0.0",
            harness_ref=fixed_harness.ref,
            nodes=nodes,
            limits=ProgramLimits(
                max_nodes=len(nodes),
                max_parallelism=execution_profile.scheduling.max_parallelism,
                max_total_attempts=aggregate_budget.max_total_attempts,
                max_recursion_depth=0,
                max_recursive_calls=0,
            ),
        )
    except ValueError as error:
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            f"proposal graph cannot be lowered under its execution profile: {error}",
            subject_ids=graph.node_ids,
        ) from error


def _lower_monolithic_incumbent(
    *,
    graph: MonolithicIncumbentProgram,
    fixed_harness: CompiledHarnessInstance,
    aggregate_budget: HarnessBudget,
    execution_profile: ProposalExecutionProfile,
) -> ExecutionProgram:
    if graph.finalizer.node_id == _STOP_NODE_ID:
        raise ProposalCompilationHostError("monolithic incumbent node id collides with the fixed stop node")
    try:
        return ExecutionProgram(
            program_id=f"p0.incumbent.{graph.candidate_id}",
            version="1.0.0",
            harness_ref=fixed_harness.ref,
            nodes=(
                ActionNode(
                    node_id=graph.finalizer.node_id,
                    operation_id=_FINALIZER_OPERATION_ID,
                ),
                StopNode(
                    node_id=_STOP_NODE_ID,
                    depends_on=(graph.finalizer.node_id,),
                    outcome=StopOutcome.SUCCEEDED,
                    result=ProgramOutputRef(
                        node_id=graph.finalizer.node_id,
                        output_port="result",
                    ),
                ),
            ),
            limits=ProgramLimits(
                max_nodes=2,
                max_parallelism=execution_profile.scheduling.max_parallelism,
                max_total_attempts=aggregate_budget.max_total_attempts,
                max_recursion_depth=0,
                max_recursive_calls=0,
            ),
        )
    except ValueError as error:
        raise ProposalCompilationHostError(
            f"host-owned monolithic incumbent cannot be lowered safely: {error}"
        ) from error


def _claim_generated_id(node_id: str, claimed: set[str]) -> None:
    if node_id in claimed:
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal node id collides with compiler-owned orchestration",
            subject_ids=(node_id,),
        )
    claimed.add(node_id)
