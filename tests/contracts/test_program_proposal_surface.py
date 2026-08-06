# ABOUTME: Tests the phase-neutral module boundaries behind the program-proposal package API.
# ABOUTME: Proves public imports remain stable while current contract owners stay separated.

from __future__ import annotations

from importlib import import_module


def test_program_proposal_facade_reexports_contracts_from_coherent_modules() -> None:
    facade = import_module("aec_bench.contracts.program_proposal")
    types = import_module("aec_bench.contracts.program_proposal.types")
    problem = import_module("aec_bench.contracts.program_proposal.problem")
    candidate = import_module("aec_bench.contracts.program_proposal.candidate")
    freeze = import_module("aec_bench.contracts.program_proposal.freeze")
    study = import_module("aec_bench.contracts.program_proposal.study")

    expected_owners = {
        types: (
            "CandidateEvidenceKind",
            "OptimizationDisposition",
            "OptimizationSplit",
            "ProgramCandidateKind",
        ),
        problem: (
            "DecompositionLeakageAudit",
            "DecompositionProblemView",
            "FixedHarnessCapabilityProjection",
            "PublicAuthorityBoundary",
            "PublicDataGapBoundary",
            "PublicSourceRef",
        ),
        candidate: (
            "CandidateGenerationCoordinate",
            "CandidateGenerationManifest",
            "ProgramCandidateRef",
        ),
        freeze: ("ProposalFreeze",),
        study: (
            "DecompositionOptimizationCycle",
            "MatchedCandidateEvidenceRef",
            "MatchedEvaluationCoordinate",
            "PairedCandidateComparison",
            "ProgramCandidateStudy",
        ),
    }

    for owner, symbol_names in expected_owners.items():
        for symbol_name in symbol_names:
            symbol = getattr(owner, symbol_name)
            assert getattr(facade, symbol_name) is symbol
            assert symbol.__module__ == owner.__name__
