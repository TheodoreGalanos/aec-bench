# ABOUTME: Verifies proposal-owned semantic graphs independently of their persisted models.
# ABOUTME: Returns typed topology evidence while enforcing exact ports, handoffs, and reachability.

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aec_bench.contracts.proposal_execution.graph import (
        FinalSynthesisSpec,
        ProposalHandoff,
        ProposalInputPort,
        ProposalOutputPort,
        ProposedDecompositionGraph,
        SemanticSubtaskSpec,
    )


@dataclass(frozen=True, slots=True)
class ProposedGraphVerification:
    """Derived topology evidence for one valid proposed decomposition graph."""

    node_ids: tuple[str, ...]
    topological_order: tuple[str, ...]
    handoff_ids: tuple[str, ...]
    finalizer_reachable_node_ids: tuple[str, ...]


def verify_proposed_decomposition_graph(
    graph: ProposedDecompositionGraph,
) -> ProposedGraphVerification:
    """Recompute and validate graph topology from the persisted semantic surface."""

    if not graph.finalizer.input_ports:
        raise ValueError("proposal finalizer requires at least one semantic input")
    subtasks, input_ports, output_ports = _graph_port_indexes(graph)
    dependencies, outgoing, bound_inputs = _bind_graph_handoffs(
        graph,
        input_ports=input_ports,
        output_ports=output_ports,
    )
    expected_inputs = {(node_id, input_id) for node_id, ports in input_ports.items() for input_id in ports}
    if set(bound_inputs) != expected_inputs:
        raise ValueError("every input port exactly once must be bound by a handoff")
    topological_order = _topological_order(dependencies)
    reachable = _nodes_reaching_finalizer(
        outgoing,
        finalizer_id=graph.finalizer.node_id,
    )
    if not set(subtasks) <= reachable:
        raise ValueError("every semantic subtask must reach the finalizer")
    return ProposedGraphVerification(
        node_ids=tuple(sorted(input_ports)),
        topological_order=topological_order,
        handoff_ids=tuple(sorted(handoff.handoff_id for handoff in graph.handoffs)),
        finalizer_reachable_node_ids=tuple(sorted(reachable)),
    )


def _graph_port_indexes(
    graph: ProposedDecompositionGraph,
) -> tuple[
    dict[str, SemanticSubtaskSpec],
    dict[str, dict[str, ProposalInputPort]],
    dict[str, dict[str, ProposalOutputPort]],
]:
    subtasks = {subtask.node_id: subtask for subtask in graph.semantic_subtasks}
    if graph.finalizer.node_id in subtasks:
        raise ValueError("finalizer node id must be distinct from semantic subtasks")
    nodes: dict[str, SemanticSubtaskSpec | FinalSynthesisSpec] = {
        **subtasks,
        graph.finalizer.node_id: graph.finalizer,
    }
    input_ports = {node_id: {port.input_id: port for port in node.input_ports} for node_id, node in nodes.items()}
    output_ports = {
        node_id: {port.output_id: port for port in subtask.output_ports} for node_id, subtask in subtasks.items()
    }
    return subtasks, input_ports, output_ports


def _bind_graph_handoffs(
    graph: ProposedDecompositionGraph,
    *,
    input_ports: dict[str, dict[str, ProposalInputPort]],
    output_ports: dict[str, dict[str, ProposalOutputPort]],
) -> tuple[
    dict[str, set[str]],
    dict[str, set[str]],
    dict[tuple[str, str], str],
]:
    dependencies: dict[str, set[str]] = {node_id: set() for node_id in input_ports}
    outgoing: dict[str, set[str]] = {node_id: set() for node_id in input_ports}
    bound_inputs: dict[tuple[str, str], str] = {}
    for handoff in graph.handoffs:
        input_identity = _validate_graph_handoff(
            graph,
            handoff=handoff,
            input_ports=input_ports,
            output_ports=output_ports,
        )
        if input_identity in bound_inputs:
            raise ValueError("every input port must have exactly one handoff")
        bound_inputs[input_identity] = handoff.handoff_id
        dependencies[handoff.consumer_node_id].add(handoff.producer_node_id)
        outgoing[handoff.producer_node_id].add(handoff.consumer_node_id)
    return dependencies, outgoing, bound_inputs


def _validate_graph_handoff(
    graph: ProposedDecompositionGraph,
    *,
    handoff: ProposalHandoff,
    input_ports: dict[str, dict[str, ProposalInputPort]],
    output_ports: dict[str, dict[str, ProposalOutputPort]],
) -> tuple[str, str]:
    if handoff.producer_node_id == graph.finalizer.node_id:
        raise ValueError("finalizer cannot produce handoffs")
    producer_outputs = output_ports.get(handoff.producer_node_id)
    if producer_outputs is None:
        raise ValueError("proposal handoff references an unknown producer node")
    producer_port = producer_outputs.get(handoff.producer_output_id)
    if producer_port is None:
        raise ValueError("proposal handoff references an unknown producer output")
    consumer_inputs = input_ports.get(handoff.consumer_node_id)
    if consumer_inputs is None:
        raise ValueError("proposal handoff references an unknown consumer node")
    consumer_port = consumer_inputs.get(handoff.consumer_input_id)
    if consumer_port is None:
        raise ValueError("proposal handoff references an unknown consumer input")
    if producer_port.kind is not consumer_port.kind:
        raise ValueError("proposal handoff port kinds must match")
    return handoff.consumer_node_id, handoff.consumer_input_id


def _topological_order(
    dependencies: dict[str, set[str]],
) -> tuple[str, ...]:
    remaining = {node_id: set(node_dependencies) for node_id, node_dependencies in dependencies.items()}
    order: list[str] = []
    while remaining:
        ready = tuple(sorted(node_id for node_id, node_dependencies in remaining.items() if not node_dependencies))
        if not ready:
            raise ValueError("proposed decomposition graph must be acyclic")
        order.extend(ready)
        for node_id in ready:
            del remaining[node_id]
        for node_dependencies in remaining.values():
            node_dependencies.difference_update(ready)
    return tuple(order)


def _nodes_reaching_finalizer(
    outgoing: dict[str, set[str]],
    *,
    finalizer_id: str,
) -> set[str]:
    reverse: dict[str, set[str]] = {node_id: set() for node_id in outgoing}
    for producer, consumers in outgoing.items():
        for consumer in consumers:
            reverse[consumer].add(producer)
    reachable = {finalizer_id}
    frontier = [finalizer_id]
    while frontier:
        current = frontier.pop()
        for predecessor in reverse[current]:
            if predecessor not in reachable:
                reachable.add(predecessor)
                frontier.append(predecessor)
    return reachable
