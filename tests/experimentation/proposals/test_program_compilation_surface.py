# ABOUTME: Characterizes the stable public facade of the proposal-compilation package.
# ABOUTME: Proves facade exports alias their single implementations in cohesive submodules.

from importlib import import_module


def test_program_proposal_compilation_facade_reexports_single_implementations() -> None:
    facade = import_module("aec_bench.experimentation.proposals.program_compilation")
    compilation = import_module("aec_bench.experimentation.proposals.program_compilation.compilation")
    contracts = import_module("aec_bench.experimentation.proposals.program_compilation.contracts")
    errors = import_module("aec_bench.experimentation.proposals.program_compilation.errors")
    profile = import_module("aec_bench.experimentation.proposals.program_compilation.profile")

    assert facade.compile_governed_proposal is compilation.compile_governed_proposal
    assert facade.ProposalRunSessionBundle is contracts.ProposalRunSessionBundle
    assert facade.ProposalCompilationHostError is errors.ProposalCompilationHostError
    assert facade.proposal_execution_profile is profile.proposal_execution_profile
    assert facade.__all__ == (
        "ProposalCompilationHostError",
        "ProposalRunSessionBundle",
        "compile_governed_proposal",
        "proposal_execution_profile",
    )
