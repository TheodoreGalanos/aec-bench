# ABOUTME: Locks the proposal-session compatibility facade to its canonical runtime package.
# ABOUTME: Prevents the fixed-K decomposition from duplicating public classes or callables.

from __future__ import annotations

import importlib


def test_proposal_session_facade_preserves_canonical_runtime_objects() -> None:
    facade = importlib.import_module(
        "aec_bench.harness.proposal_session",
    )
    canonical = importlib.import_module(
        "aec_bench.harness.proposal_session_runtime",
    )

    public_names = (
        "PreparedProposalNodeInvocation",
        "ProposalBackend",
        "ProposalSessionEnvironment",
        "ProposalSessionEnvironmentPool",
        "ProposalSessionExecResult",
        "ProposalSessionRuntimeError",
        "build_proposal_session_execution_ref",
        "prepare_proposal_node_invocation",
        "run_proposal_session",
    )
    compatibility_names = (
        "_operation_definition_for_proposal_runtime",
        "_validate_provider_broker_call_budgets",
    )
    for name in (*public_names, *compatibility_names):
        assert getattr(facade, name) is getattr(canonical, name)

    assert facade.__all__ == public_names
    assert canonical.__all__ == public_names


def test_proposal_session_runtime_uses_cohesive_canonical_modules() -> None:
    canonical = importlib.import_module(
        "aec_bench.harness.proposal_session_runtime",
    )

    assert canonical.run_proposal_session.__module__ == ("aec_bench.harness.proposal_session_runtime.session")
    assert canonical.prepare_proposal_node_invocation.__module__ == (
        "aec_bench.harness.proposal_session_runtime.preparation"
    )
    assert canonical.build_proposal_session_execution_ref.__module__ == (
        "aec_bench.harness.proposal_session_runtime.receipts"
    )
    assert canonical.ProposalSessionRuntimeError.__module__ == ("aec_bench.harness.proposal_session_runtime.contracts")
