# ABOUTME: Characterizes the stable proposal-freeze facade and canonical package ownership.
# ABOUTME: Guards public object identity under both facade-first and canonical-first imports.

from __future__ import annotations

import importlib
import subprocess
import sys


def test_proposal_freeze_facade_preserves_public_identity() -> None:
    facade = importlib.import_module("aec_bench.meta_harness.proposal_freeze")
    canonical = importlib.import_module("aec_bench.meta_harness.proposal_freezing")
    contracts = importlib.import_module(
        "aec_bench.meta_harness.proposal_freezing.contracts",
    )
    issuance = importlib.import_module(
        "aec_bench.meta_harness.proposal_freezing.issuance",
    )
    replay = importlib.import_module(
        "aec_bench.meta_harness.proposal_freezing.replay",
    )

    expected = {
        "GovernedProposalFreezeError": contracts.GovernedProposalFreezeError,
        "ProposalArtifact": contracts.ProposalArtifact,
        "IncumbentArtifact": contracts.IncumbentArtifact,
        "ProposalFreezeBasis": contracts.ProposalFreezeBasis,
        "GovernedProposalFreezeResult": contracts.GovernedProposalFreezeResult,
        "issue_governed_proposal_freeze": issuance.issue_governed_proposal_freeze,
        "assert_proposal_freeze_authority": replay.assert_proposal_freeze_authority,
    }
    for name, implementation in expected.items():
        assert getattr(facade, name) is implementation
        assert getattr(canonical, name) is implementation


def test_proposal_freeze_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.meta_harness.proposal_freeze as facade
import aec_bench.meta_harness.proposal_freezing as canonical
assert facade.ProposalFreezeBasis is canonical.ProposalFreezeBasis
assert facade.issue_governed_proposal_freeze is canonical.issue_governed_proposal_freeze
assert facade.assert_proposal_freeze_authority is canonical.assert_proposal_freeze_authority
""",
        """
import aec_bench.meta_harness.proposal_freezing as canonical
import aec_bench.meta_harness.proposal_freeze as facade
assert facade.ProposalFreezeBasis is canonical.ProposalFreezeBasis
assert facade.issue_governed_proposal_freeze is canonical.issue_governed_proposal_freeze
assert facade.assert_proposal_freeze_authority is canonical.assert_proposal_freeze_authority
""",
    )

    for program in programs:
        subprocess.run([sys.executable, "-c", program], check=True)
