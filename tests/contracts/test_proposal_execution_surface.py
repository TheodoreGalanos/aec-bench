# ABOUTME: Tests coherent ownership behind the stable proposal-execution contract facade.
# ABOUTME: Proves graph, compilation, and session evidence contracts have single implementations.

from __future__ import annotations

from importlib import import_module


def test_proposal_execution_facade_reexports_contracts_from_coherent_modules() -> None:
    facade = import_module("aec_bench.contracts.proposal_execution")
    graph = import_module("aec_bench.contracts.proposal_execution.graph")
    compilation = import_module("aec_bench.contracts.proposal_execution.compilation")
    session = import_module("aec_bench.contracts.proposal_execution.session")

    expected_owners = {
        graph: (
            "FinalSynthesisSpec",
            "MonolithicIncumbentProgram",
            "NodeEvidenceContract",
            "ProposalHandoff",
            "ProposalInputPort",
            "ProposalOutputPort",
            "ProposalSourceScope",
            "ProposedDecompositionGraph",
            "SemanticSubtaskSpec",
        ),
        compilation: (
            "ProposalCompilationRejection",
            "ProposalCompilationSuccess",
            "ProposalCompileDiagnostic",
        ),
        session: (
            "ProposalContainerTransitionRef",
            "ProposalContractCheckResultRef",
            "ProposalHandoffArtifactRef",
            "ProposalNodeExecutionResultRef",
            "ProposalNodeReceipt",
            "ProposalSessionExecutionRef",
            "ProposalSessionPlan",
            "ProposalSessionReceipt",
        ),
    }

    for owner, symbol_names in expected_owners.items():
        for symbol_name in symbol_names:
            symbol = getattr(owner, symbol_name)
            assert getattr(facade, symbol_name) is symbol
            assert symbol.__module__ == owner.__name__
