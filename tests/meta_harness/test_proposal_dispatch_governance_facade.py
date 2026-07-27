# ABOUTME: Characterizes the stable proposal-dispatch governance facade and canonical package.
# ABOUTME: Guards exact public identity under both facade-first and canonical-first imports.

from __future__ import annotations

import importlib
import subprocess
import sys


def test_proposal_dispatch_governance_facade_preserves_public_identity() -> None:
    facade = importlib.import_module(
        "aec_bench.meta_harness.proposal_dispatch_governance",
    )
    canonical = importlib.import_module("aec_bench.meta_harness.proposal_dispatch")
    contracts = importlib.import_module(
        "aec_bench.meta_harness.proposal_dispatch.contracts",
    )
    authorization = importlib.import_module(
        "aec_bench.meta_harness.proposal_dispatch.authorization",
    )
    replay = importlib.import_module(
        "aec_bench.meta_harness.proposal_dispatch.replay",
    )

    expected = {
        "ProposalDispatchGovernanceError": contracts.ProposalDispatchGovernanceError,
        "GovernedProposalDispatch": contracts.GovernedProposalDispatch,
        "GovernedProposalDispatchAuthorization": contracts.GovernedProposalDispatchAuthorization,
        "authorize_governed_proposal_dispatch": authorization.authorize_governed_proposal_dispatch,
        "replay_governed_proposal_dispatch": replay.replay_governed_proposal_dispatch,
    }
    for name, implementation in expected.items():
        assert getattr(facade, name) is implementation
        assert getattr(canonical, name) is implementation


def test_proposal_dispatch_governance_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.meta_harness.proposal_dispatch_governance as facade
import aec_bench.meta_harness.proposal_dispatch as canonical
assert facade.GovernedProposalDispatch is canonical.GovernedProposalDispatch
assert facade.authorize_governed_proposal_dispatch is canonical.authorize_governed_proposal_dispatch
assert facade.replay_governed_proposal_dispatch is canonical.replay_governed_proposal_dispatch
""",
        """
import aec_bench.meta_harness.proposal_dispatch as canonical
import aec_bench.meta_harness.proposal_dispatch_governance as facade
assert facade.GovernedProposalDispatch is canonical.GovernedProposalDispatch
assert facade.authorize_governed_proposal_dispatch is canonical.authorize_governed_proposal_dispatch
assert facade.replay_governed_proposal_dispatch is canonical.replay_governed_proposal_dispatch
""",
    )

    for program in programs:
        subprocess.run([sys.executable, "-c", program], check=True)
