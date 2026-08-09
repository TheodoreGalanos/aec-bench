# ABOUTME: Validates declared-stage execution programs against pinned task-review graphs.
# ABOUTME: Owns exact task coverage, receipt lineage, control dependencies, joins, and finalizers.

from collections.abc import Mapping
from dataclasses import dataclass

from aec_bench.contracts.execution_program import (
    ActionNode,
    CompiledExecutionProgram,
    FanoutNode,
    JoinNode,
    JoinStrategy,
    OutputValue,
    ProgramArgument,
    ProgramNode,
    VerifyNode,
)
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.stage_execution import DeclaredStageGraph

from .diagnostics import CompilationOwner, _fail
from .operations import _literal_string


@dataclass(frozen=True)
class _DeclaredStageIndex:
    nodes_by_coordinate: dict[tuple[str, str], ActionNode]
    coordinates_by_node: dict[str, tuple[str, str]]
    finalizers_by_task: dict[str, list[ActionNode]]


def _validate_declared_stage_program(
    *,
    program: CompiledExecutionProgram,
    snapshots: tuple[TaskSnapshotRef, ...],
) -> None:
    stage_candidates, finalize_candidates = _declared_stage_candidates(program)
    if not stage_candidates and not finalize_candidates:
        return
    _validate_declared_stage_program_shape(
        program=program,
        stage_candidates=stage_candidates,
        finalize_candidates=finalize_candidates,
    )
    graphs = _declared_stage_graphs(snapshots)
    nodes_by_id = {node.node_id: node for node in program.nodes}
    index = _index_declared_stage_nodes(
        stage_candidates=stage_candidates,
        finalize_candidates=finalize_candidates,
        graphs=graphs,
    )
    _validate_declared_stage_task_coverage(
        graphs=graphs,
        index=index,
    )
    for task_ref, graph in graphs.items():
        _validate_declared_task_stage_graph(
            task_ref=task_ref,
            graph=graph,
            index=index,
            nodes_by_id=nodes_by_id,
        )


def _declared_stage_candidates(
    program: CompiledExecutionProgram,
) -> tuple[
    tuple[ActionNode | FanoutNode | VerifyNode, ...],
    tuple[ActionNode | FanoutNode | VerifyNode, ...],
]:
    stage_candidates = tuple(
        node
        for node in program.nodes
        if isinstance(node, ActionNode | FanoutNode | VerifyNode) and node.operation_id == "run_stage.v1"
    )
    finalize_candidates = tuple(
        node
        for node in program.nodes
        if isinstance(node, ActionNode | FanoutNode | VerifyNode) and node.operation_id == "finalize_task.v1"
    )
    return stage_candidates, finalize_candidates


def _validate_declared_stage_program_shape(
    *,
    program: CompiledExecutionProgram,
    stage_candidates: tuple[ActionNode | FanoutNode | VerifyNode, ...],
    finalize_candidates: tuple[ActionNode | FanoutNode | VerifyNode, ...],
) -> None:
    run_batch_nodes = tuple(
        node.node_id
        for node in program.nodes
        if isinstance(node, ActionNode | FanoutNode | VerifyNode) and node.operation_id == "run_batch.v1"
    )
    if run_batch_nodes:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_program_mixed_with_run_batch",
            message="one px cannot mix task-level run_batch with declared-stage execution",
            subject_ids=run_batch_nodes,
        )
    non_actions = tuple(
        node.node_id for node in (*stage_candidates, *finalize_candidates) if not isinstance(node, ActionNode)
    )
    if non_actions:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_operation_node_invalid",
            message="declared-stage and finalization operations must be action nodes",
            subject_ids=non_actions,
        )


def _declared_stage_graphs(
    snapshots: tuple[TaskSnapshotRef, ...],
) -> dict[str, DeclaredStageGraph]:
    graphs: dict[str, DeclaredStageGraph] = {}
    for snapshot in snapshots:
        graph = snapshot.task_review.stage_graph if snapshot.task_review is not None else None
        if graph is None:
            _fail(
                owner=CompilationOwner.WORLD,
                code="declared_stage_graph_missing",
                message=f"staged px requires a pinned declared-stage graph for {snapshot.task_id}",
                subject_ids=(snapshot.task_id,),
            )
        graphs[snapshot.task_id] = graph
    return graphs


def _index_declared_stage_nodes(
    *,
    stage_candidates: tuple[ActionNode | FanoutNode | VerifyNode, ...],
    finalize_candidates: tuple[ActionNode | FanoutNode | VerifyNode, ...],
    graphs: dict[str, DeclaredStageGraph],
) -> _DeclaredStageIndex:
    stage_nodes: dict[tuple[str, str], ActionNode] = {}
    stage_coordinates_by_node: dict[str, tuple[str, str]] = {}
    for candidate in stage_candidates:
        assert isinstance(candidate, ActionNode)
        task_ref = _literal_string(_argument(candidate, "task_ref"))
        stage_id = _literal_string(_argument(candidate, "stage_id"))
        assert task_ref is not None and stage_id is not None
        _add_declared_stage_node(
            candidate=candidate,
            task_ref=task_ref,
            stage_id=stage_id,
            graphs=graphs,
            stage_nodes=stage_nodes,
            stage_coordinates_by_node=stage_coordinates_by_node,
        )
    finalizers_by_task = _index_declared_stage_finalizers(
        finalize_candidates=finalize_candidates,
        graphs=graphs,
    )
    return _DeclaredStageIndex(
        nodes_by_coordinate=stage_nodes,
        coordinates_by_node=stage_coordinates_by_node,
        finalizers_by_task=finalizers_by_task,
    )


def _add_declared_stage_node(
    *,
    candidate: ActionNode,
    task_ref: str,
    stage_id: str,
    graphs: dict[str, DeclaredStageGraph],
    stage_nodes: dict[tuple[str, str], ActionNode],
    stage_coordinates_by_node: dict[str, tuple[str, str]],
) -> None:
    graph = graphs.get(task_ref)
    if graph is None:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_task_outside_bundle",
            message=f"stage node targets a task outside the RunBundle: {task_ref}",
            subject_ids=(candidate.node_id, task_ref),
        )
    if graph.stage(stage_id) is None:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_unknown",
            message=f"program stage {stage_id!r} is not declared by task {task_ref!r}",
            subject_ids=(candidate.node_id, stage_id, task_ref),
        )
    coordinate = (task_ref, stage_id)
    if coordinate in stage_nodes:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_duplicate",
            message=f"program executes declared stage {stage_id!r} more than once for {task_ref!r}",
            subject_ids=(candidate.node_id, stage_nodes[coordinate].node_id, stage_id, task_ref),
        )
    stage_nodes[coordinate] = candidate
    stage_coordinates_by_node[candidate.node_id] = coordinate


def _index_declared_stage_finalizers(
    *,
    finalize_candidates: tuple[ActionNode | FanoutNode | VerifyNode, ...],
    graphs: dict[str, DeclaredStageGraph],
) -> dict[str, list[ActionNode]]:
    finalizers_by_task: dict[str, list[ActionNode]] = {}
    for candidate in finalize_candidates:
        assert isinstance(candidate, ActionNode)
        task_ref = _literal_string(_argument(candidate, "task_ref"))
        assert task_ref is not None
        if task_ref not in graphs:
            _fail(
                owner=CompilationOwner.PROGRAM,
                code="declared_stage_task_outside_bundle",
                message=f"finalizer targets a task outside the RunBundle: {task_ref}",
                subject_ids=(candidate.node_id, task_ref),
            )
        finalizers_by_task.setdefault(task_ref, []).append(candidate)
    return finalizers_by_task


def _validate_declared_stage_task_coverage(
    *,
    graphs: dict[str, DeclaredStageGraph],
    index: _DeclaredStageIndex,
) -> None:
    expected_task_ids = set(graphs)
    stage_task_ids = {task_ref for task_ref, _ in index.nodes_by_coordinate}
    finalizer_task_ids = set(index.finalizers_by_task)
    if stage_task_ids != expected_task_ids or finalizer_task_ids != expected_task_ids:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_task_coverage_mismatch",
            message="staged px must execute and finalize every task bound into the RunBundle",
            subject_ids=tuple(sorted(expected_task_ids | stage_task_ids | finalizer_task_ids)),
        )


def _validate_declared_task_stage_graph(
    *,
    task_ref: str,
    graph: DeclaredStageGraph,
    index: _DeclaredStageIndex,
    nodes_by_id: dict[str, ProgramNode],
) -> None:
    expected_stage_ids = {stage.stage_id for stage in graph.stages}
    actual_stage_ids = {
        stage_id for candidate_task, stage_id in index.nodes_by_coordinate if candidate_task == task_ref
    }
    if actual_stage_ids != expected_stage_ids:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_coverage_mismatch",
            message=f"program stages do not exactly cover the declared graph for {task_ref!r}",
            subject_ids=tuple(sorted(expected_stage_ids | actual_stage_ids | {task_ref})),
        )
    finalizers = index.finalizers_by_task[task_ref]
    if len(finalizers) != 1:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_finalizer_cardinality",
            message=f"staged px requires exactly one finalizer for {task_ref!r}",
            subject_ids=tuple(sorted((task_ref, *(node.node_id for node in finalizers)))),
        )
    for stage_id in graph.topological_order:
        _validate_declared_stage_predecessors(
            task_ref=task_ref,
            stage_id=stage_id,
            graph=graph,
            index=index,
            nodes_by_id=nodes_by_id,
        )
    _validate_declared_stage_finalizer(
        task_ref=task_ref,
        expected_stage_ids=expected_stage_ids,
        finalizer=finalizers[0],
        index=index,
        nodes_by_id=nodes_by_id,
    )


def _validate_declared_stage_predecessors(
    *,
    task_ref: str,
    stage_id: str,
    graph: DeclaredStageGraph,
    index: _DeclaredStageIndex,
    nodes_by_id: dict[str, ProgramNode],
) -> None:
    node = index.nodes_by_coordinate[(task_ref, stage_id)]
    upstream_argument = _argument(node, "upstream_receipts")
    actual_predecessors, source_node_id = _stage_receipt_sources(
        argument=upstream_argument,
        task_ref=task_ref,
        nodes_by_id=nodes_by_id,
        stage_coordinates_by_node=index.coordinates_by_node,
        consumer_node_id=node.node_id,
    )
    expected_predecessors = set(graph.predecessor_stage_ids(stage_id))
    if set(actual_predecessors) != expected_predecessors:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_predecessor_mismatch",
            message=f"stage node {node.node_id!r} receipts do not match declared predecessors for {stage_id!r}",
            subject_ids=tuple(
                sorted(
                    {
                        node.node_id,
                        stage_id,
                        *expected_predecessors,
                        *actual_predecessors,
                    }
                )
            ),
        )
    expected_dependencies = {source_node_id} if source_node_id is not None else set()
    if set(node.depends_on) != expected_dependencies:
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_control_dependency_mismatch",
            message=f"stage node {node.node_id!r} must depend only on its receipt source",
            subject_ids=tuple(sorted({node.node_id, *node.depends_on, *expected_dependencies})),
        )


def _validate_declared_stage_finalizer(
    *,
    task_ref: str,
    expected_stage_ids: set[str],
    finalizer: ActionNode,
    index: _DeclaredStageIndex,
    nodes_by_id: dict[str, ProgramNode],
) -> None:
    receipt_argument = _argument(finalizer, "stage_receipts")
    final_stage_ids, final_source_node_id = _stage_receipt_sources(
        argument=receipt_argument,
        task_ref=task_ref,
        nodes_by_id=nodes_by_id,
        stage_coordinates_by_node=index.coordinates_by_node,
        consumer_node_id=finalizer.node_id,
    )
    source_node = nodes_by_id.get(final_source_node_id) if final_source_node_id is not None else None
    requires_join = len(expected_stage_ids) > 1
    if (
        set(final_stage_ids) != expected_stage_ids
        or final_source_node_id is None
        or (requires_join and not isinstance(source_node, JoinNode))
        or set(finalizer.depends_on) != {final_source_node_id}
    ):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_finalizer_receipt_mismatch",
            message=f"finalizer does not consume exactly one receipt for every stage of {task_ref!r}",
            subject_ids=tuple(
                sorted(
                    {
                        finalizer.node_id,
                        task_ref,
                        *expected_stage_ids,
                        *final_stage_ids,
                    }
                )
            ),
        )


def _stage_receipt_sources(
    *,
    argument: ProgramArgument | None,
    task_ref: str,
    nodes_by_id: Mapping[str, object],
    stage_coordinates_by_node: dict[str, tuple[str, str]],
    consumer_node_id: str,
) -> tuple[tuple[str, ...], str | None]:
    if argument is None:
        return (), None
    if not isinstance(argument.value, OutputValue):
        _fail(
            owner=CompilationOwner.PROGRAM,
            code="declared_stage_receipt_source_invalid",
            message=f"receipt argument for {consumer_node_id!r} is not output-derived",
            subject_ids=(consumer_node_id,),
        )
    reference = argument.value.ref
    source = nodes_by_id.get(reference.node_id)
    if isinstance(source, ActionNode) and source.operation_id == "run_stage.v1":
        coordinate = stage_coordinates_by_node.get(source.node_id)
        if reference.output_port != "stage_receipt" or coordinate is None or coordinate[0] != task_ref:
            _fail(
                owner=CompilationOwner.PROGRAM,
                code="declared_stage_receipt_source_invalid",
                message=f"receipt source for {consumer_node_id!r} is not a matching stage receipt",
                subject_ids=(consumer_node_id, reference.node_id),
            )
        return (coordinate[1],), source.node_id
    if isinstance(source, JoinNode):
        joined_node_ids = tuple(item.node_id for item in source.sources)
        if (
            reference.output_port != "result"
            or source.strategy is not JoinStrategy.ALL
            or set(source.depends_on) != set(joined_node_ids)
            or any(item.output_port != "stage_receipt" for item in source.sources)
        ):
            _fail(
                owner=CompilationOwner.PROGRAM,
                code="declared_stage_receipt_source_invalid",
                message=f"receipt join for {consumer_node_id!r} is not an exact all-stage join",
                subject_ids=(consumer_node_id, source.node_id),
            )
        coordinates = tuple(stage_coordinates_by_node.get(node_id) for node_id in joined_node_ids)
        if any(coordinate is None or coordinate[0] != task_ref for coordinate in coordinates):
            _fail(
                owner=CompilationOwner.PROGRAM,
                code="declared_stage_receipt_source_invalid",
                message=f"receipt join for {consumer_node_id!r} crosses task boundaries",
                subject_ids=(consumer_node_id, source.node_id, *joined_node_ids),
            )
        return tuple(coordinate[1] for coordinate in coordinates if coordinate is not None), source.node_id
    _fail(
        owner=CompilationOwner.PROGRAM,
        code="declared_stage_receipt_source_invalid",
        message=f"receipt source for {consumer_node_id!r} is not a stage action or join",
        subject_ids=(consumer_node_id, reference.node_id),
    )


def _argument(node: ActionNode, name: str) -> ProgramArgument | None:
    return next((argument for argument in node.arguments if argument.name == name), None)
