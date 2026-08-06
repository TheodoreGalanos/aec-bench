# ABOUTME: Resolves and validates exact frozen proposal candidate artifacts.
# ABOUTME: Classifies candidate-owned grammar failures separately from host-owned integrity faults.

from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import ValidationError

from aec_bench.contracts.authority import BasisReference
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.proposal_execution.graph import (
    ExecutableCandidateGraph,
    MonolithicIncumbentProgram,
    ProposedDecompositionGraph,
)
from aec_bench.contracts.proposal_execution_profile import ProposalExecutionProfile
from aec_bench.contracts.proposal_execution_types import ProposalCompileRejectionCode
from aec_bench.meta_harness.authority_ledger import AuthorityLedger, AuthorityLedgerError
from aec_bench.meta_harness.proposal_freezing import GovernedProposalFreezeResult

from .errors import ProposalCompilationHostError, _CandidateCompileError


def _parse_candidate_graph(
    *,
    candidate_ref: ProgramCandidateRef,
    candidate_bytes: bytes,
) -> ExecutableCandidateGraph:
    try:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            return MonolithicIncumbentProgram.model_validate_json(candidate_bytes)
        return ProposedDecompositionGraph.model_validate_json(candidate_bytes)
    except ValidationError as error:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            raise ProposalCompilationHostError(
                "frozen monolithic incumbent does not satisfy its host-owned contract"
            ) from error
        raise _candidate_error_from_validation(error) from error


def _resolve_exact_candidate_bytes(
    *,
    ledger: AuthorityLedger,
    governed_freeze: GovernedProposalFreezeResult,
    candidate_ref: ProgramCandidateRef,
    candidate_artifact_root: Path,
) -> bytes:
    reference = _candidate_basis_reference(
        governed_freeze=governed_freeze,
        candidate_ref=candidate_ref,
    )
    resolved_root = _resolve_candidate_artifact_root(
        ledger=ledger,
        candidate_artifact_root=candidate_artifact_root,
    )
    content = _read_candidate_basis_bytes(
        ledger=ledger,
        reference=reference,
        resolved_root=resolved_root,
    )
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if observed_sha256 != candidate_ref.candidate_artifact_sha256:
        raise ProposalCompilationHostError("candidate bytes changed after authority replay")
    return content


def _candidate_basis_reference(
    *,
    governed_freeze: GovernedProposalFreezeResult,
    candidate_ref: ProgramCandidateRef,
) -> BasisReference:
    scope = f"proposal-freeze.{governed_freeze.freeze.freeze_id}"
    expected_artifact_id = (
        f"{scope}.incumbent-artifact.{candidate_ref.candidate_id}"
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT
        else f"{scope}.proposal-artifact.{candidate_ref.candidate_id}"
    )
    references: tuple[BasisReference, ...] = (
        () if governed_freeze.basis.incumbent_artifact is None else (governed_freeze.basis.incumbent_artifact,)
    )
    if candidate_ref.kind is ProgramCandidateKind.PROPOSAL:
        references = governed_freeze.basis.proposal_artifacts
    matches = tuple(reference for reference in references if reference.artifact_id == expected_artifact_id)
    if len(matches) != 1:
        raise ProposalCompilationHostError("governed freeze basis does not contain exactly one candidate artifact")
    reference = matches[0]
    if reference.artifact_sha256 != candidate_ref.candidate_artifact_sha256:
        raise ProposalCompilationHostError("candidate basis digest differs from its exact frozen reference")
    return reference


def _resolve_candidate_artifact_root(
    *,
    ledger: AuthorityLedger,
    candidate_artifact_root: Path,
) -> Path:
    expected_root = (ledger.root / "basis-objects").resolve(strict=True)
    supplied_root = Path(candidate_artifact_root)
    if supplied_root.is_symlink():
        raise ProposalCompilationHostError("frozen candidate artifact root must not be a symlink")
    try:
        resolved_root = supplied_root.resolve(strict=True)
    except OSError as error:
        raise ProposalCompilationHostError(f"frozen candidate artifact root cannot be resolved: {error}") from error
    if resolved_root != expected_root:
        raise ProposalCompilationHostError("candidate artifact root differs from the authority ledger basis root")
    return resolved_root


def _read_candidate_basis_bytes(
    *,
    ledger: AuthorityLedger,
    reference: BasisReference,
    resolved_root: Path,
) -> bytes:
    try:
        stored = ledger.resolve_basis(reference)
        path = stored.content_path.resolve(strict=True)
        if not path.is_relative_to(resolved_root):
            raise ProposalCompilationHostError("resolved candidate artifact escapes the frozen candidate root")
        content = path.read_bytes()
    except AuthorityLedgerError as error:
        raise ProposalCompilationHostError(f"exact candidate basis cannot be resolved: {error}") from error
    except OSError as error:
        raise ProposalCompilationHostError(f"exact candidate bytes cannot be read: {error}") from error
    return content


def _validate_candidate_program(
    *,
    graph: ExecutableCandidateGraph,
    candidate_ref: ProgramCandidateRef,
    proposal_freeze: ProposalFreeze,
    proposal_grammar_sha256: str,
    output_contract_sha256: str,
    execution_profile: ProposalExecutionProfile,
) -> None:
    _validate_candidate_artifact_identity(
        graph=graph,
        candidate_ref=candidate_ref,
    )
    _validate_candidate_problem_binding(
        graph=graph,
        candidate_ref=candidate_ref,
        proposal_freeze=proposal_freeze,
    )
    if isinstance(graph, ProposedDecompositionGraph):
        _validate_proposal_policy_and_profile(
            graph=graph,
            proposal_freeze=proposal_freeze,
            proposal_grammar_sha256=proposal_grammar_sha256,
            execution_profile=execution_profile,
        )
    _validate_candidate_source_scope(
        graph=graph,
        candidate_ref=candidate_ref,
        proposal_freeze=proposal_freeze,
    )
    _validate_candidate_output_contract(
        graph=graph,
        candidate_ref=candidate_ref,
        output_contract_sha256=output_contract_sha256,
    )


def _validate_candidate_artifact_identity(
    *,
    graph: ExecutableCandidateGraph,
    candidate_ref: ProgramCandidateRef,
) -> None:
    if graph.content_sha256 != candidate_ref.candidate_artifact_sha256:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            raise ProposalCompilationHostError(
                "monolithic incumbent artifact is not the exact canonical frozen program"
            )
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal artifact is not the canonical content-addressed graph",
            subject_ids=(candidate_ref.candidate_id,),
        )
    if graph.candidate_id != candidate_ref.candidate_id:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            raise ProposalCompilationHostError("monolithic incumbent identity differs from its frozen reference")
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal graph identity differs from its frozen candidate coordinate",
            subject_ids=(candidate_ref.candidate_id, graph.candidate_id),
        )
    if isinstance(graph, ProposedDecompositionGraph):
        _validate_proposal_coordinate(
            graph=graph,
            candidate_ref=candidate_ref,
        )
    elif candidate_ref.kind is not ProgramCandidateKind.INCUMBENT:
        raise ProposalCompilationHostError("monolithic program cannot compile as a proposal candidate")


def _validate_proposal_coordinate(
    *,
    graph: ProposedDecompositionGraph,
    candidate_ref: ProgramCandidateRef,
) -> None:
    if (
        candidate_ref.kind is not ProgramCandidateKind.PROPOSAL
        or graph.generation_coordinate_id != candidate_ref.generation_coordinate_id
    ):
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal graph identity differs from its frozen candidate coordinate",
            subject_ids=(candidate_ref.candidate_id, graph.candidate_id),
        )


def _validate_candidate_problem_binding(
    *,
    graph: ExecutableCandidateGraph,
    candidate_ref: ProgramCandidateRef,
    proposal_freeze: ProposalFreeze,
) -> None:
    if graph.problem_view_sha256 != proposal_freeze.problem_view.content_sha256:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            raise ProposalCompilationHostError("monolithic incumbent does not bind the governed public problem view")
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal graph does not bind the governed problem view",
            subject_ids=(graph.candidate_id,),
        )


def _validate_proposal_policy_and_profile(
    *,
    graph: ProposedDecompositionGraph,
    proposal_freeze: ProposalFreeze,
    proposal_grammar_sha256: str,
    execution_profile: ProposalExecutionProfile,
) -> None:
    if (
        graph.proposal_policy_sha256 != proposal_freeze.proposal_policy_sha256
        or graph.policy_checkpoint_sha256 != proposal_freeze.policy_checkpoint_sha256
        or graph.proposal_grammar_sha256 != proposal_grammar_sha256
    ):
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "proposal graph does not bind the frozen policy and grammar",
            subject_ids=(graph.candidate_id,),
        )
    _validate_candidate_graph_profile(
        graph,
        execution_profile=execution_profile,
    )


def _validate_candidate_source_scope(
    *,
    graph: ExecutableCandidateGraph,
    candidate_ref: ProgramCandidateRef,
    proposal_freeze: ProposalFreeze,
) -> None:
    public_source_ids = {source.source_id for source in proposal_freeze.problem_view.public_sources}
    requested_source_ids = {
        source_id for subtask in graph.semantic_subtasks for source_id in subtask.source_scope.source_ids
    }
    requested_source_ids.update(graph.finalizer.source_scope.source_ids)
    unknown_source_ids = tuple(sorted(requested_source_ids - public_source_ids))
    if unknown_source_ids:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            raise ProposalCompilationHostError(
                "monolithic incumbent requests sources outside the governed public allowlist"
            )
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.PUBLIC_SOURCE_UNKNOWN,
            "proposal graph requests sources outside the governed public allowlist",
            subject_ids=unknown_source_ids,
        )
    if isinstance(graph, MonolithicIncumbentProgram) and (
        set(graph.finalizer.source_scope.source_ids) != public_source_ids
    ):
        raise ProposalCompilationHostError("monolithic incumbent must receive the exact complete public source set")


def _validate_candidate_output_contract(
    *,
    graph: ExecutableCandidateGraph,
    candidate_ref: ProgramCandidateRef,
    output_contract_sha256: str,
) -> None:
    if graph.finalizer.output_completion_contract_sha256 != output_contract_sha256:
        if candidate_ref.kind is ProgramCandidateKind.INCUMBENT:
            raise ProposalCompilationHostError(
                "monolithic incumbent finalizer does not bind the governed output contract"
            )
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.OUTPUT_CONTRACT_MISMATCH,
            "proposal finalizer does not bind the governed output contract",
            subject_ids=(graph.finalizer.node_id,),
        )


def _validate_candidate_graph_profile(
    graph: ProposedDecompositionGraph,
    *,
    execution_profile: ProposalExecutionProfile,
) -> None:
    lowering = execution_profile.lowering
    if len(graph.semantic_subtasks) > lowering.max_semantic_subtasks:
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.NODE_LIMIT_EXCEEDED,
            "proposal graph semantic-subtask count exceeds its execution profile",
            subject_ids=tuple(subtask.node_id for subtask in graph.semantic_subtasks),
        )
    fan_in = {node_id: 0 for node_id in graph.node_ids}
    fan_out = {node_id: 0 for node_id in graph.node_ids}
    for handoff in graph.handoffs:
        fan_in[handoff.consumer_node_id] += 1
        fan_out[handoff.producer_node_id] += 1
    excessive_fan_in = tuple(sorted(node_id for node_id, count in fan_in.items() if count > lowering.max_fan_in))
    if excessive_fan_in:
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.FAN_IN_LIMIT_EXCEEDED,
            "proposal graph fan-in exceeds its execution profile",
            subject_ids=excessive_fan_in,
        )
    excessive_fan_out = tuple(sorted(node_id for node_id, count in fan_out.items() if count > lowering.max_fan_out))
    if excessive_fan_out:
        raise _CandidateCompileError(
            ProposalCompileRejectionCode.FAN_OUT_LIMIT_EXCEEDED,
            "proposal graph fan-out exceeds its execution profile",
            subject_ids=excessive_fan_out,
        )


def _candidate_error_from_validation(
    error: ValidationError,
) -> _CandidateCompileError:
    if any(item["type"] == "missing" for item in error.errors()):
        return _CandidateCompileError(
            ProposalCompileRejectionCode.GRAMMAR_INVALID,
            "frozen proposal artifact does not satisfy the proposal graph grammar",
        )
    message = str(error)
    normalized = message.casefold()
    if "acyclic" in normalized:
        code = ProposalCompileRejectionCode.GRAPH_CYCLIC
    elif "reach the finalizer" in normalized:
        code = ProposalCompileRejectionCode.GRAPH_DISCONNECTED
    elif "port kind" in normalized:
        code = ProposalCompileRejectionCode.PORT_CONTRACT_INVALID
    elif "handoff" in normalized or "input port" in normalized:
        code = ProposalCompileRejectionCode.HANDOFF_CONTRACT_INVALID
    else:
        code = ProposalCompileRejectionCode.GRAMMAR_INVALID
    return _CandidateCompileError(
        code,
        "frozen proposal artifact does not satisfy the proposal graph grammar",
    )
