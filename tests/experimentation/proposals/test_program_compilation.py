# ABOUTME: Tests governed deterministic compilation of frozen proposal graphs.
# ABOUTME: Proves exact authority, source, budget, profile, and provider-free lowering boundaries.

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.contracts.execution_program import (
    ActionNode,
    FanoutNode,
    JoinNode,
    OutputValue,
)
from aec_bench.contracts.harness_instance import (
    CompiledHarnessInstance,
    ProgramOperationRef,
    ProgramOperationScope,
)
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.program_proposal.candidate import ProgramCandidateRef
from aec_bench.contracts.program_proposal.freeze import ProposalFreeze
from aec_bench.contracts.program_proposal.types import ProgramCandidateKind
from aec_bench.contracts.proposal_execution.compilation import ProposalCompilationRejection
from aec_bench.contracts.proposal_execution.graph import (
    FinalSynthesisSpec,
    MonolithicIncumbentProgram,
    NodeEvidenceContract,
    ProposalHandoff,
    ProposalInputPort,
    ProposalOutputPort,
    ProposalSourceScope,
    ProposedDecompositionGraph,
    SemanticSubtaskSpec,
)
from aec_bench.contracts.proposal_execution_context import ScopedSourceMaterialization
from aec_bench.contracts.proposal_execution_profile import (
    ProposalLoweringPolicy,
)
from aec_bench.contracts.proposal_execution_types import (
    ProposalCompileRejectionCode,
    ProposalExecutionSemantics,
    ProposalPortKind,
)
from aec_bench.experimentation.proposals.freezing import (
    GovernedProposalFreezeResult,
    IncumbentArtifact,
    ProposalArtifact,
)
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalCompilationHostError,
    ProposalRunSessionBundle,
    compile_governed_proposal,
    proposal_execution_profile,
)
from aec_bench.harness.compilation import (
    CompilationError,
    CompilationOwner,
    compile_execution_program,
)
from aec_bench.harness.compilation.task_snapshot import build_task_snapshot
from aec_bench.harness.kernel_catalogue import default_kernel_registry
from aec_bench.tasks.loader import load_task_definition
from tests.experimentation.proposals.test_freezing import (
    _execution_profile,
    _Fixture,
    _fixture,
    _issue,
)

_GRAMMAR_SHA256 = hashlib.sha256(b"phase9-pilot-grammar-v1").hexdigest()
_LOWERING_POLICY_SHA256 = hashlib.sha256(b"phase9-sequential-lowering-v1").hexdigest()
_ALLOCATION_POLICY_SHA256 = hashlib.sha256(b"phase9-equal-budget-v1").hexdigest()
_INCUMBENT_POLICY_SHA256 = hashlib.sha256(b"phase9-monolithic-incumbent-v1").hexdigest()


def test_monolithic_incumbent_compiles_as_one_budget_matched_task_resident_node(
    tmp_path: Path,
) -> None:
    fixture, governed, incumbent = _governed_incumbent_fixture(tmp_path)
    candidate_ref = governed.freeze.incumbent_candidate
    assert candidate_ref is not None

    result = compile_governed_proposal(
        **_compile_arguments(
            fixture,
            governed,
            candidate_ref=candidate_ref,
        ),
    )

    assert isinstance(result, ProposalRunSessionBundle)
    assert result.compilation.candidate_ref.kind is ProgramCandidateKind.INCUMBENT
    assert result.compilation.proposal_graph == incumbent
    assert result.session_plan.planned_node_ids == ("finalize",)
    assert result.session_plan.topological_order == ("finalize",)
    assert result.compilation.budget_plan.aggregate_budget == fixture.fixed_harness.budget
    assert result.compilation.budget_plan.reservation_node_ids == ("finalize",)
    assert result.fixed_harness == fixture.fixed_harness
    assert result.task_snapshot.task_id == fixture.problem_view.task_id
    action_nodes = tuple(node for node in result.compilation.lowered_program.nodes if isinstance(node, ActionNode))
    assert tuple(node.node_id for node in action_nodes) == ("finalize",)
    assert action_nodes[0].operation_id == "finalize_proposed_plan"
    assert action_nodes[0].depends_on == ()
    assert action_nodes[0].arguments == ()
    assert {candidate.candidate_id for candidate in governed.freeze.realized_candidates} == {
        coordinate.candidate_id for coordinate in fixture.candidate_manifest.coordinates
    }
    assert governed.basis.incumbent_artifact is not None
    assert governed.basis.incumbent_artifact.artifact_sha256 == incumbent.content_sha256


def test_incumbent_compile_cannot_use_a_proposal_manifest_member_or_unfrozen_artifact(
    tmp_path: Path,
) -> None:
    fixture, governed, incumbent = _governed_incumbent_fixture(tmp_path)
    proposal = governed.freeze.realized_candidates[0]
    disguised = ProgramCandidateRef(
        candidate_id=proposal.candidate_id,
        kind=ProgramCandidateKind.INCUMBENT,
        candidate_artifact_sha256=proposal.candidate_artifact_sha256,
    )

    with pytest.raises(ProposalCompilationHostError, match="exact governed"):
        compile_governed_proposal(
            **_compile_arguments(
                fixture,
                governed,
                candidate_ref=disguised,
            ),
        )

    unfrozen = ProgramCandidateRef(
        candidate_id="candidate.incumbent.unfrozen",
        kind=ProgramCandidateKind.INCUMBENT,
        candidate_artifact_sha256=incumbent.content_sha256,
    )
    with pytest.raises(ProposalCompilationHostError, match="exact governed"):
        compile_governed_proposal(
            **_compile_arguments(
                fixture,
                governed,
                candidate_ref=unfrozen,
            ),
        )


def test_serial_graph_compiles_to_exact_sequential_k9_program_and_session_bundle(
    tmp_path: Path,
) -> None:
    fixture, governed, graph = _governed_graph_fixture(tmp_path, shape="serial")
    arguments = _compile_arguments(fixture, governed)

    result = compile_governed_proposal(
        **arguments,
    )

    assert isinstance(result, ProposalRunSessionBundle)
    compilation = result.compilation
    assert compilation.proposal_graph == graph
    assert compilation.raw_proposal_artifact_sha256 == compilation.candidate_ref.candidate_artifact_sha256
    assert compilation.kernel_ref == fixture.fixed_harness.kernel_ref
    assert compilation.fixed_harness_ref == fixture.fixed_harness.ref
    assert compilation.source_scope_manifest.problem_view_sha256 == graph.problem_view_sha256
    assert compilation.budget_plan.aggregate_budget == fixture.fixed_harness.budget
    assert compilation.budget_plan.execution_semantics is ProposalExecutionSemantics.SEQUENTIAL_DATAFLOW
    assert compilation.budget_plan.reservation_node_ids == graph.node_ids
    assert result.session_plan.compilation == compilation
    assert result.session_plan.planned_node_ids == graph.node_ids
    assert result.session_plan.topological_order == graph.topological_order
    assert result.session_operation_ref == fixture.fixed_harness.program_surface.operation("run_proposal_session").ref
    assert result.fixed_harness == fixture.fixed_harness
    assert result.task_snapshot == arguments["task_snapshot"]
    assert compilation.execution_profile == arguments["execution_profile"]

    operation_ids = {node.operation_id for node in compilation.lowered_program.nodes if isinstance(node, ActionNode)}
    assert operation_ids == {
        "check_subtask_contract",
        "finalize_proposed_plan",
        "run_semantic_subtask",
    }
    assert (
        result.fixed_harness.program_surface.operation("run_proposal_session").required_compilation_scope
        is ProgramOperationScope.PUBLIC
    )
    for internal_operation_id in operation_ids:
        assert (
            result.fixed_harness.program_surface.operation(internal_operation_id).required_compilation_scope
            is ProgramOperationScope.PROPOSAL_SESSION_INTERNAL
        )
    assert "run_proposal_session" not in operation_ids
    assert not any(isinstance(node, FanoutNode) for node in compilation.lowered_program.nodes)
    assert compilation.lowered_program.limits.max_parallelism == 1
    assert (
        compilation.lowered_program.limits.max_parallelism == compilation.execution_profile.scheduling.max_parallelism
    )
    assert compilation.lowered_program.limits.max_recursion_depth == 0
    assert compilation.lowered_program.limits.max_recursive_calls == 0
    assert all(
        node.retry is None and node.recursion is None
        for node in compilation.lowered_program.nodes
        if isinstance(node, ActionNode)
    )

    finalizer = next(
        node
        for node in compilation.lowered_program.nodes
        if isinstance(node, ActionNode) and node.node_id == graph.finalizer.node_id
    )
    findings = next(argument for argument in finalizer.arguments if argument.name == "findings")
    assert isinstance(findings.value, OutputValue)
    assert findings.value.ref.node_id == "join.finalizer.complete"
    complete_join = next(
        node
        for node in compilation.lowered_program.nodes
        if isinstance(node, JoinNode) and node.node_id == "join.finalizer.complete"
    )
    assert tuple(source.node_id for source in complete_join.sources) == (
        "check.analyse",
        "check.assess",
    )


def test_execution_profile_limits_are_enforced_as_candidate_policy(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    arguments = _compile_arguments(fixture, governed)
    profile = arguments["execution_profile"]
    assert hasattr(profile, "model_dump")
    payload = profile.model_dump(  # type: ignore[union-attr]
        mode="python",
        exclude={"content_sha256", "lowering"},
    )
    payload["lowering"] = ProposalLoweringPolicy(
        max_semantic_subtasks=1,
        max_fan_in=2,
        max_fan_out=2,
        allow_retry=False,
        allow_recursion=False,
    )
    limited_profile = type(profile).model_validate(payload)
    governed = _issue(
        fixture,
        execution_profile=limited_profile,
        freeze_id="freeze.phase9.dev.limited-profile",
        event_id="authority.freeze.phase9.dev.limited-profile",
        replay_id="replay.freeze.phase9.dev.limited-profile",
    )
    arguments = _compile_arguments(fixture, governed)
    arguments["execution_profile"] = limited_profile

    result = compile_governed_proposal(**arguments)

    assert isinstance(result, ProposalCompilationRejection)
    assert result.execution_profile == arguments["execution_profile"]
    assert result.diagnostic.code is ProposalCompileRejectionCode.NODE_LIMIT_EXCEEDED


def test_execution_profile_rejects_kernel_and_operation_definition_drift(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    arguments = _compile_arguments(fixture, governed)
    profile = arguments["execution_profile"]
    assert hasattr(profile, "model_dump")
    payload = profile.model_dump(mode="python", exclude={"content_sha256"})  # type: ignore[union-attr]
    payload["required_kernel_version"] = "9.9.9"
    arguments["execution_profile"] = type(profile).model_validate(payload)

    with pytest.raises(
        ProposalCompilationHostError,
        match="differs from the exact governed",
    ):
        compile_governed_proposal(**arguments)

    arguments = _compile_arguments(fixture, governed)
    profile = arguments["execution_profile"]
    assert hasattr(profile, "model_dump")
    payload = profile.model_dump(mode="python", exclude={"content_sha256"})  # type: ignore[union-attr]
    constraints = list(payload["operation_constraints"])
    constraint = dict(constraints[0])
    constraint["operation_definition_sha256"] = "0" * 64
    constraints[0] = constraint
    payload["operation_constraints"] = tuple(constraints)
    drifted_profile = type(profile).model_validate(payload)
    governed = _issue(
        fixture,
        execution_profile=drifted_profile,
        freeze_id="freeze.phase9.dev.operation-drift",
        event_id="authority.freeze.phase9.dev.operation-drift",
        replay_id="replay.freeze.phase9.dev.operation-drift",
    )
    arguments = _compile_arguments(fixture, governed)
    arguments["execution_profile"] = drifted_profile

    with pytest.raises(ProposalCompilationHostError, match="operation definition"):
        compile_governed_proposal(**arguments)


def test_session_bundle_rejects_reconstructed_harness_or_task_identity(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    result = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    assert isinstance(result, ProposalRunSessionBundle)

    harness_payload = fixture.fixed_harness.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    harness_payload["instance_id"] = "hx.reconstructed"
    wrong_harness = CompiledHarnessInstance.model_validate(harness_payload)
    with pytest.raises(ValueError, match="exact frozen harness"):
        ProposalRunSessionBundle(
            bundle_id=result.bundle_id,
            compilation=result.compilation,
            session_plan=result.session_plan,
            fixed_harness=wrong_harness,
            task_snapshot=result.task_snapshot,
            session_operation_ref=result.session_operation_ref,
        )

    wrong_task = result.task_snapshot.model_copy(update={"task_id": "task.reconstructed"})
    with pytest.raises(ValueError, match="task identity key"):
        ProposalRunSessionBundle(
            bundle_id=result.bundle_id,
            compilation=result.compilation,
            session_plan=result.session_plan,
            fixed_harness=result.fixed_harness,
            task_snapshot=wrong_task,
            session_operation_ref=result.session_operation_ref,
        )

    with pytest.raises(ValueError, match="profiled session operation"):
        ProposalRunSessionBundle(
            bundle_id=result.bundle_id,
            compilation=result.compilation,
            session_plan=result.session_plan,
            fixed_harness=result.fixed_harness,
            task_snapshot=result.task_snapshot,
            session_operation_ref=ProgramOperationRef(
                operation_id="unknown_proposal_session.v1",
            ),
        )


def test_ordinary_program_compilation_cannot_invoke_proposal_session_internals(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    result = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    assert isinstance(result, ProposalRunSessionBundle)

    with pytest.raises(CompilationError) as captured:
        compile_execution_program(
            result.compilation.lowered_program,
            harness=result.fixed_harness,
            registry=default_kernel_registry(),
        )

    assert captured.value.diagnostic.owner is CompilationOwner.PROGRAM
    assert captured.value.diagnostic.code == "proposal_session_scope_required"


def test_fork_join_lowering_and_content_identity_are_permutation_stable(
    tmp_path: Path,
) -> None:
    fixture, governed, graph = _governed_graph_fixture(tmp_path, shape="fork_join")
    permuted = _proposal_graph(
        fixture,
        candidate_id=graph.candidate_id,
        coordinate_id=graph.generation_coordinate_id,
        shape="fork_join",
        reverse=True,
    )
    assert permuted == graph
    assert permuted.content_sha256 == graph.content_sha256

    first = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )
    second = compile_governed_proposal(
        **_compile_arguments(
            fixture,
            governed,
            source_materializations=tuple(reversed(_source_materializations(fixture))),
        ),
    )

    assert isinstance(first, ProposalRunSessionBundle)
    assert isinstance(second, ProposalRunSessionBundle)
    assert first == second
    assert first.content_sha256 == second.content_sha256
    assert first.compilation.lowered_program == second.compilation.lowered_program
    assert first.compilation.compiled_program.topological_order == (
        "analyse",
        "check.analyse",
        "assess-a",
        "assess-b",
        "check.assess-a",
        "check.assess-b",
        "join.finalizer.complete",
        "finalize",
        "stop.v1",
    )
    complete_join = next(
        node
        for node in first.compilation.lowered_program.nodes
        if isinstance(node, JoinNode) and node.node_id == "join.finalizer.complete"
    )
    assert tuple(source.node_id for source in complete_join.sources) == (
        "check.analyse",
        "check.assess-a",
        "check.assess-b",
    )


def test_malformed_frozen_artifact_returns_typed_zero_dispatch_rejection(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    governed = _issue(fixture, execution_profile=_execution_profile(fixture))

    result = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )

    assert isinstance(result, ProposalCompilationRejection)
    assert result.diagnostic.code is ProposalCompileRejectionCode.GRAMMAR_INVALID
    assert result.raw_proposal_artifact_sha256 == result.candidate_ref.candidate_artifact_sha256
    assert result.run_bundle_permitted is False
    assert result.trial_record_permitted is False


def test_compile_rejects_freeze_without_execution_profile(
    tmp_path: Path,
) -> None:
    fixture = _fixture(tmp_path)
    governed = _issue(fixture)

    with pytest.raises(
        ProposalCompilationHostError,
        match="does not bind an execution profile",
    ):
        compile_governed_proposal(
            **_compile_arguments(fixture, governed),
        )


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    (
        ("unknown_source", ProposalCompileRejectionCode.PUBLIC_SOURCE_UNKNOWN),
        ("output_contract", ProposalCompileRejectionCode.OUTPUT_CONTRACT_MISMATCH),
    ),
)
def test_candidate_binding_failures_return_typed_rejections(
    tmp_path: Path,
    mutation: str,
    expected_code: ProposalCompileRejectionCode,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(
        tmp_path,
        shape="serial",
        unknown_source=mutation == "unknown_source",
        output_contract_sha256=(
            hashlib.sha256(b"wrong-output-contract").hexdigest() if mutation == "output_contract" else None
        ),
    )

    result = compile_governed_proposal(
        **_compile_arguments(fixture, governed),
    )

    assert isinstance(result, ProposalCompilationRejection)
    assert result.diagnostic.code is expected_code
    assert result.run_bundle_permitted is False


def test_infeasible_shared_budget_returns_typed_candidate_rejection(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")

    result = compile_governed_proposal(
        **_compile_arguments(
            fixture,
            governed,
            session_overhead_seconds=fixture.fixed_harness.budget.max_runtime_seconds,
        ),
    )

    assert isinstance(result, ProposalCompilationRejection)
    assert result.diagnostic.code is ProposalCompileRejectionCode.BUDGET_ALLOCATION_INFEASIBLE
    assert result.run_bundle_permitted is False


def test_mutated_freeze_fails_as_a_host_authority_error_before_candidate_compilation(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    payload = governed.freeze.model_dump(mode="json", exclude={"content_sha256"})
    payload["freeze_id"] = "freeze.phase9.mutated"
    mutated = ProposalFreeze.model_validate(payload)

    with pytest.raises(ProposalCompilationHostError, match="authority"):
        compile_governed_proposal(
            **_compile_arguments(
                fixture,
                governed,
                proposal_freeze=mutated,
            ),
        )


def test_candidate_basis_tamper_fails_as_a_host_error_not_candidate_utility(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    candidate = governed.freeze.realized_candidates[0]
    reference = next(
        item for item in governed.basis.proposal_artifacts if item.artifact_id.endswith(f".{candidate.candidate_id}")
    )
    stored = fixture.ledger.resolve_basis(reference)
    stored.content_path.write_bytes(b'{"candidate_id":"tampered"}')

    with pytest.raises(ProposalCompilationHostError, match="authority"):
        compile_governed_proposal(
            **_compile_arguments(fixture, governed),
        )


def test_compilation_rejects_non_exact_h0_before_building_candidate_utility(
    tmp_path: Path,
) -> None:
    fixture, governed, _ = _governed_graph_fixture(tmp_path, shape="serial")
    harness_payload = fixture.fixed_harness.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    harness_payload["instance_id"] = "hx.not-the-frozen-h0"
    wrong_harness = fixture.fixed_harness.model_validate(harness_payload)

    with pytest.raises(ProposalCompilationHostError, match="fixed harness"):
        compile_governed_proposal(
            **_compile_arguments(
                fixture,
                governed,
                fixed_harness=wrong_harness,
            ),
        )


def _governed_graph_fixture(
    tmp_path: Path,
    *,
    shape: str,
    unknown_source: bool = False,
    output_contract_sha256: str | None = None,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    include_tool_binding: bool = True,
) -> tuple[_Fixture, GovernedProposalFreezeResult, ProposedDecompositionGraph]:
    fixture = _fixture(
        tmp_path,
        agent_capability_id=agent_capability_id,
        include_tool_binding=include_tool_binding,
    )
    graphs = tuple(
        _proposal_graph(
            fixture,
            candidate_id=coordinate.candidate_id,
            coordinate_id=coordinate.coordinate_id,
            shape=shape if index == 0 else "serial",
            unknown_source=unknown_source if index == 0 else False,
            output_contract_sha256=output_contract_sha256 if index == 0 else None,
        )
        for index, coordinate in enumerate(fixture.candidate_manifest.coordinates)
    )
    artifacts = tuple(
        _proposal_artifact(graph, template)
        for graph, template in zip(
            graphs,
            fixture.proposal_artifacts,
            strict=True,
        )
    )
    fixture = replace(fixture, proposal_artifacts=artifacts)
    return (
        fixture,
        _issue(fixture, execution_profile=_execution_profile(fixture)),
        graphs[0],
    )


def _governed_incumbent_fixture(
    tmp_path: Path,
    *,
    agent_capability_id: str = "aecbench.adapter.tool-loop",
    include_tool_binding: bool = True,
) -> tuple[_Fixture, GovernedProposalFreezeResult, MonolithicIncumbentProgram]:
    fixture = _fixture(
        tmp_path,
        agent_capability_id=agent_capability_id,
        include_tool_binding=include_tool_binding,
    )
    incumbent = MonolithicIncumbentProgram(
        candidate_id="candidate.incumbent",
        problem_view_sha256=fixture.problem_view.content_sha256,
        incumbent_policy_sha256=_INCUMBENT_POLICY_SHA256,
        finalizer=FinalSynthesisSpec(
            node_id="finalize",
            objective="Complete the public task directly under the fixed harness.",
            source_scope=ProposalSourceScope(
                source_ids=tuple(source.source_id for source in fixture.problem_view.public_sources),
            ),
            input_ports=(),
            output_completion_contract_sha256=canonical_json_sha256(
                fixture.problem_view.output_contract.model_dump(mode="json"),
            ),
        ),
    )
    content = json.dumps(
        incumbent.model_dump(mode="json", exclude={"content_sha256"}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert hashlib.sha256(content).hexdigest() == incumbent.content_sha256
    artifact = IncumbentArtifact(
        reference=ProgramCandidateRef(
            candidate_id=incumbent.candidate_id,
            kind=ProgramCandidateKind.INCUMBENT,
            candidate_artifact_sha256=incumbent.content_sha256,
        ),
        content=content,
        producer=fixture.host_policy,
        producer_process_id="aecbench.monolithic-incumbent",
        invocation_id="incumbent.phase9.1a",
    )
    return (
        fixture,
        _issue(
            fixture,
            incumbent_artifact=artifact,
            execution_profile=_execution_profile(fixture),
        ),
        incumbent,
    )


def _proposal_graph(
    fixture: _Fixture,
    *,
    candidate_id: str,
    coordinate_id: str,
    shape: str,
    reverse: bool = False,
    unknown_source: bool = False,
    output_contract_sha256: str | None = None,
) -> ProposedDecompositionGraph:
    source_id = "unknown-source" if unknown_source else "rainfall-input"
    analyse = SemanticSubtaskSpec(
        node_id="analyse",
        objective="Extract the public rainfall evidence.",
        source_scope=ProposalSourceScope(source_ids=(source_id,)),
        output_ports=(
            ProposalOutputPort(
                output_id="facts",
                kind=ProposalPortKind.FACT_SET,
            ),
        ),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=("facts",),
            require_provenance=True,
            allow_explicit_data_gap=True,
        ),
    )
    if shape == "serial":
        assess = _assessment_subtask(
            node_id="assess",
            input_id="facts",
            output_id="findings",
        )
        finalizer = _finalizer(
            fixture,
            input_ids=("findings",),
            output_contract_sha256=output_contract_sha256,
        )
        subtasks = (analyse, assess)
        handoffs = (
            ProposalHandoff(
                handoff_id="handoff.facts",
                producer_node_id="analyse",
                producer_output_id="facts",
                consumer_node_id="assess",
                consumer_input_id="facts",
            ),
            ProposalHandoff(
                handoff_id="handoff.findings",
                producer_node_id="assess",
                producer_output_id="findings",
                consumer_node_id="finalize",
                consumer_input_id="findings",
            ),
        )
    elif shape == "fork_join":
        assess_a = _assessment_subtask(
            node_id="assess-a",
            input_id="facts-a",
            output_id="findings-a",
        )
        assess_b = _assessment_subtask(
            node_id="assess-b",
            input_id="facts-b",
            output_id="findings-b",
        )
        finalizer = _finalizer(
            fixture,
            input_ids=("findings-a", "findings-b"),
            output_contract_sha256=output_contract_sha256,
        )
        subtasks = (analyse, assess_a, assess_b)
        handoffs = (
            ProposalHandoff(
                handoff_id="handoff.facts-a",
                producer_node_id="analyse",
                producer_output_id="facts",
                consumer_node_id="assess-a",
                consumer_input_id="facts-a",
            ),
            ProposalHandoff(
                handoff_id="handoff.facts-b",
                producer_node_id="analyse",
                producer_output_id="facts",
                consumer_node_id="assess-b",
                consumer_input_id="facts-b",
            ),
            ProposalHandoff(
                handoff_id="handoff.findings-a",
                producer_node_id="assess-a",
                producer_output_id="findings-a",
                consumer_node_id="finalize",
                consumer_input_id="findings-a",
            ),
            ProposalHandoff(
                handoff_id="handoff.findings-b",
                producer_node_id="assess-b",
                producer_output_id="findings-b",
                consumer_node_id="finalize",
                consumer_input_id="findings-b",
            ),
        )
    else:
        raise AssertionError(f"unsupported test graph shape: {shape}")
    if reverse:
        subtasks = tuple(reversed(subtasks))
        handoffs = tuple(reversed(handoffs))
    return ProposedDecompositionGraph(
        candidate_id=candidate_id,
        generation_coordinate_id=coordinate_id,
        problem_view_sha256=fixture.problem_view.content_sha256,
        proposal_policy_sha256=fixture.candidate_manifest.proposal_policy_sha256,
        policy_checkpoint_sha256=fixture.candidate_manifest.policy_checkpoint_sha256,
        proposal_grammar_sha256=_GRAMMAR_SHA256,
        semantic_subtasks=subtasks,
        finalizer=finalizer,
        handoffs=handoffs,
    )


def _assessment_subtask(
    *,
    node_id: str,
    input_id: str,
    output_id: str,
) -> SemanticSubtaskSpec:
    return SemanticSubtaskSpec(
        node_id=node_id,
        objective=f"Assess {input_id} and emit {output_id}.",
        source_scope=ProposalSourceScope(),
        input_ports=(
            ProposalInputPort(
                input_id=input_id,
                kind=ProposalPortKind.FACT_SET,
            ),
        ),
        output_ports=(
            ProposalOutputPort(
                output_id=output_id,
                kind=ProposalPortKind.FINDING_SET,
            ),
        ),
        evidence_contract=NodeEvidenceContract(
            required_output_ids=(output_id,),
            require_provenance=True,
            allow_explicit_data_gap=True,
        ),
    )


def _finalizer(
    fixture: _Fixture,
    *,
    input_ids: tuple[str, ...],
    output_contract_sha256: str | None,
) -> FinalSynthesisSpec:
    expected = canonical_json_sha256(fixture.problem_view.output_contract.model_dump(mode="json"))
    return FinalSynthesisSpec(
        node_id="finalize",
        objective="Synthesize the public task response from every checked subtask.",
        source_scope=ProposalSourceScope(),
        input_ports=tuple(
            ProposalInputPort(
                input_id=input_id,
                kind=ProposalPortKind.FINDING_SET,
            )
            for input_id in input_ids
        ),
        output_completion_contract_sha256=output_contract_sha256 or expected,
    )


def _proposal_artifact(
    graph: ProposedDecompositionGraph,
    template: ProposalArtifact,
) -> ProposalArtifact:
    content = json.dumps(
        graph.model_dump(mode="json", exclude={"content_sha256"}),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    assert hashlib.sha256(content).hexdigest() == graph.content_sha256
    reference_payload = template.reference.model_dump(
        mode="json",
        exclude={"content_sha256"},
    )
    reference_payload["candidate_artifact_sha256"] = graph.content_sha256
    return ProposalArtifact(
        reference=ProgramCandidateRef.model_validate(reference_payload),
        content=content,
        producer=template.producer,
        producer_process_id=template.producer_process_id,
        invocation_id=template.invocation_id,
    )


def _source_materializations(
    fixture: _Fixture,
) -> tuple[ScopedSourceMaterialization, ...]:
    source = fixture.problem_view.public_sources[0]
    return (
        ScopedSourceMaterialization(
            source_id=source.source_id,
            source_sha256=source.source_sha256,
            byte_size=source.byte_size,
            task_relative_path="source/rainfall.txt",
        ),
    )


def _compile_arguments(
    fixture: _Fixture,
    governed: GovernedProposalFreezeResult,
    *,
    proposal_freeze: ProposalFreeze | None = None,
    fixed_harness: CompiledHarnessInstance | None = None,
    candidate_ref: ProgramCandidateRef | None = None,
    source_materializations: tuple[ScopedSourceMaterialization, ...] | None = None,
    session_overhead_seconds: int = 0,
) -> dict[str, object]:
    tasks_root = fixture.ledger.root.parent / "tasks"
    task_dir = tasks_root / fixture.problem_view.task_id
    task = load_task_definition(task_dir, tasks_root)
    task_snapshot = build_task_snapshot(task=task, tasks_root=tasks_root)
    frozen = governed.freeze
    selected_candidate = candidate_ref or frozen.realized_candidates[0]
    registry = default_kernel_registry()
    resolved_harness = fixed_harness or fixture.fixed_harness
    return {
        "compilation_id": f"compile.{selected_candidate.candidate_id}",
        "bundle_id": f"proposal-bundle.{selected_candidate.candidate_id}",
        "session_plan_id": f"session-plan.{selected_candidate.candidate_id}",
        "ledger": fixture.ledger,
        "governed_freeze": governed,
        "proposal_freeze": proposal_freeze or frozen,
        "candidate_ref": selected_candidate,
        "candidate_artifact_root": fixture.ledger.root / "basis-objects",
        "registry": registry,
        "fixed_harness": resolved_harness,
        "execution_profile": proposal_execution_profile(
            registry=registry,
            fixed_harness=resolved_harness,
            provider_broker_required=False,
        ),
        "task_snapshot": task_snapshot,
        "source_materializations": (
            source_materializations if source_materializations is not None else _source_materializations(fixture)
        ),
        "output_contract_sha256": canonical_json_sha256(fixture.problem_view.output_contract.model_dump(mode="json")),
        "aggregate_budget": fixture.fixed_harness.budget,
        "proposal_grammar_sha256": _GRAMMAR_SHA256,
        "lowering_policy_sha256": _LOWERING_POLICY_SHA256,
        "allocation_policy_sha256": _ALLOCATION_POLICY_SHA256,
        "session_overhead_seconds": session_overhead_seconds,
    }
