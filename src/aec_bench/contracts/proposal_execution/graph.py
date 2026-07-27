# ABOUTME: Defines candidate-authored semantic graphs and the monolithic incumbent control.
# ABOUTME: Keeps typed ports, source scopes, handoffs, and graph invariants independent of execution evidence.

from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.proposal_execution._canonical import (
    canonical_unique_models,
    canonical_unique_strings,
)
from aec_bench.contracts.proposal_execution_types import ProposalPortKind
from aec_bench.contracts.validators import NonEmptyStr


class ProposalInputPort(FrozenStrictModel):
    """Typed input expected by one proposal-owned node."""

    input_id: NonEmptyStr
    kind: ProposalPortKind


class ProposalOutputPort(FrozenStrictModel):
    """Typed output emitted by one semantic subtask."""

    output_id: NonEmptyStr
    kind: ProposalPortKind


class ProposalSourceScope(FrozenStrictModel):
    """Opaque public source IDs visible to one proposal-owned node."""

    source_ids: tuple[NonEmptyStr, ...] = ()

    @field_validator("source_ids")
    @classmethod
    def canonicalize_source_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="proposal source ids")


class NodeEvidenceContract(ContentAddressedModel):
    """Structural completeness policy checked without opening task quality evidence."""

    schema_version: Literal["aecbench.node-evidence-contract.v1"] = "aecbench.node-evidence-contract.v1"
    required_output_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    require_provenance: Literal[True]
    allow_explicit_data_gap: bool

    @field_validator("required_output_ids")
    @classmethod
    def canonicalize_required_outputs(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        return canonical_unique_strings(value, label="required output ids")


class SemanticSubtaskSpec(FrozenStrictModel):
    """Candidate-authored semantic objective with typed inputs, outputs, and sources."""

    node_id: NonEmptyStr
    objective: NonEmptyStr
    source_scope: ProposalSourceScope
    input_ports: tuple[ProposalInputPort, ...] = ()
    output_ports: tuple[ProposalOutputPort, ...] = Field(min_length=1)
    evidence_contract: NodeEvidenceContract

    @field_validator("input_ports")
    @classmethod
    def canonicalize_input_ports(
        cls,
        value: tuple[ProposalInputPort, ...],
    ) -> tuple[ProposalInputPort, ...]:
        return canonical_unique_models(
            value,
            identity="input_id",
            label="subtask input ports",
        )

    @field_validator("output_ports")
    @classmethod
    def canonicalize_output_ports(
        cls,
        value: tuple[ProposalOutputPort, ...],
    ) -> tuple[ProposalOutputPort, ...]:
        return canonical_unique_models(
            value,
            identity="output_id",
            label="subtask output ports",
        )

    @model_validator(mode="after")
    def validate_evidence_contract(self) -> Self:
        output_ids = tuple(output.output_id for output in self.output_ports)
        if self.evidence_contract.required_output_ids != output_ids:
            raise ValueError("node evidence contract must require every typed output exactly once")
        if not self.source_scope.source_ids and not self.input_ports:
            raise ValueError("semantic subtask requires a public source or an upstream input")
        return self


class FinalSynthesisSpec(FrozenStrictModel):
    """Sole final task-artifact synthesis boundary in a proposal graph."""

    node_id: NonEmptyStr
    objective: NonEmptyStr
    source_scope: ProposalSourceScope
    input_ports: tuple[ProposalInputPort, ...] = ()
    output_completion_contract_sha256: str

    @field_validator("input_ports")
    @classmethod
    def canonicalize_input_ports(
        cls,
        value: tuple[ProposalInputPort, ...],
    ) -> tuple[ProposalInputPort, ...]:
        return canonical_unique_models(
            value,
            identity="input_id",
            label="finalizer input ports",
        )

    @field_validator("output_completion_contract_sha256")
    @classmethod
    def validate_output_contract_hash(cls, value: str) -> str:
        return validate_sha256(value)


class ProposalHandoff(FrozenStrictModel):
    """Typed route from one semantic output to one downstream input."""

    handoff_id: NonEmptyStr
    producer_node_id: NonEmptyStr
    producer_output_id: NonEmptyStr
    consumer_node_id: NonEmptyStr
    consumer_input_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_distinct_nodes(self) -> Self:
        if self.producer_node_id == self.consumer_node_id:
            raise ValueError("proposal handoff cannot route a node to itself")
        return self


class ProposedDecompositionGraph(ContentAddressedModel):
    """Canonical decomposition plan generated from one public problem view."""

    schema_version: Literal["aecbench.proposed-decomposition-graph.v1"] = "aecbench.proposed-decomposition-graph.v1"
    candidate_id: NonEmptyStr
    generation_coordinate_id: NonEmptyStr
    problem_view_sha256: str
    proposal_policy_sha256: str
    policy_checkpoint_sha256: str
    proposal_grammar_sha256: str
    semantic_subtasks: tuple[SemanticSubtaskSpec, ...] = Field(min_length=1)
    finalizer: FinalSynthesisSpec
    handoffs: tuple[ProposalHandoff, ...]

    @field_validator(
        "problem_view_sha256",
        "proposal_policy_sha256",
        "policy_checkpoint_sha256",
        "proposal_grammar_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("semantic_subtasks")
    @classmethod
    def canonicalize_subtasks(
        cls,
        value: tuple[SemanticSubtaskSpec, ...],
    ) -> tuple[SemanticSubtaskSpec, ...]:
        return canonical_unique_models(
            value,
            identity="node_id",
            label="semantic subtasks",
        )

    @field_validator("handoffs")
    @classmethod
    def canonicalize_handoffs(
        cls,
        value: tuple[ProposalHandoff, ...],
    ) -> tuple[ProposalHandoff, ...]:
        return canonical_unique_models(
            value,
            identity="handoff_id",
            label="proposal handoffs",
        )

    @model_validator(mode="after")
    def validate_graph(self) -> Self:
        from aec_bench.contracts.proposal_graph_verifier import (
            verify_proposed_decomposition_graph,
        )

        verify_proposed_decomposition_graph(self)
        return self

    @property
    def node_ids(self) -> tuple[str, ...]:
        """Return the canonical model-bearing node set."""
        return tuple(
            sorted(
                (
                    *(subtask.node_id for subtask in self.semantic_subtasks),
                    self.finalizer.node_id,
                )
            )
        )

    @property
    def topological_order(self) -> tuple[str, ...]:
        """Return a deterministic dependency order for model-bearing nodes."""
        from aec_bench.contracts.proposal_graph_verifier import (
            verify_proposed_decomposition_graph,
        )

        return verify_proposed_decomposition_graph(self).topological_order


class MonolithicIncumbentProgram(ContentAddressedModel):
    """Host-owned one-call control bound only to the graph-hidden public task view."""

    schema_version: Literal["aecbench.monolithic-incumbent-program.v1"] = "aecbench.monolithic-incumbent-program.v1"
    candidate_id: NonEmptyStr
    problem_view_sha256: str
    incumbent_policy_sha256: str
    finalizer: FinalSynthesisSpec
    execution_semantics: Literal["monolithic"] = "monolithic"

    @field_validator(
        "problem_view_sha256",
        "incumbent_policy_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_monolithic_shape(self) -> Self:
        if self.finalizer.input_ports:
            raise ValueError("monolithic incumbent cannot depend on decomposed inputs")
        if not self.finalizer.source_scope.source_ids:
            raise ValueError("monolithic incumbent requires at least one public source")
        return self

    @property
    def generation_coordinate_id(self) -> None:
        """Return the absent proposer coordinate for the host-owned incumbent."""
        return None

    @property
    def proposal_policy_sha256(self) -> str:
        """Expose the incumbent policy through the legacy session-lineage field."""
        return self.incumbent_policy_sha256

    @property
    def semantic_subtasks(self) -> tuple[()]:
        """Return the empty decomposition owned by the monolithic control."""
        return ()

    @property
    def handoffs(self) -> tuple[()]:
        """Return the empty dataflow edge set owned by the monolithic control."""
        return ()

    @property
    def node_ids(self) -> tuple[str]:
        """Return the sole model-bearing task node."""
        return (self.finalizer.node_id,)

    @property
    def topological_order(self) -> tuple[str]:
        """Return the sole task node in deterministic execution order."""
        return self.node_ids


ExecutableCandidateGraph = ProposedDecompositionGraph | MonolithicIncumbentProgram
