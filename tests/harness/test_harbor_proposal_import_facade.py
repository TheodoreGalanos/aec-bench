# ABOUTME: Characterizes the stable Harbor proposal-import facade and canonical package.
# ABOUTME: Guards exact public identity under facade-first and canonical-first imports.

from __future__ import annotations

import importlib
import subprocess
import sys


def test_harbor_proposal_import_facade_preserves_public_identity() -> None:
    facade = importlib.import_module(
        "aec_bench.harness.harbor_importing.proposal",
    )
    canonical = importlib.import_module(
        "aec_bench.harness.harbor_importing.proposal_evidence",
    )
    contracts = importlib.import_module(
        "aec_bench.harness.harbor_importing.proposal_evidence.contracts",
    )
    api = importlib.import_module(
        "aec_bench.harness.harbor_importing.proposal_evidence.api",
    )

    expected = {
        "ProposalHarborImportEvidence": contracts.ProposalHarborImportEvidence,
        "ProposalImportEvidenceExtension": api.ProposalImportEvidenceExtension,
        "PROPOSAL_IMPORT_EVIDENCE_EXTENSION": api.PROPOSAL_IMPORT_EVIDENCE_EXTENSION,
        "load_proposal_harbor_import_evidence": api.load_proposal_harbor_import_evidence,
        "load_proposal_harbor_candidate_failure_evidence": (api.load_proposal_harbor_candidate_failure_evidence),
    }
    for name, implementation in expected.items():
        assert getattr(facade, name) is implementation
        assert getattr(canonical, name) is implementation


def test_harbor_proposal_import_facade_is_stable_under_both_import_orders() -> None:
    programs = (
        """
import aec_bench.harness.harbor_importing.proposal as facade
import aec_bench.harness.harbor_importing.proposal_evidence as canonical
assert facade.ProposalHarborImportEvidence is canonical.ProposalHarborImportEvidence
assert facade.ProposalImportEvidenceExtension is canonical.ProposalImportEvidenceExtension
assert facade.PROPOSAL_IMPORT_EVIDENCE_EXTENSION is canonical.PROPOSAL_IMPORT_EVIDENCE_EXTENSION
assert facade.load_proposal_harbor_import_evidence is canonical.load_proposal_harbor_import_evidence
assert (
    facade.load_proposal_harbor_candidate_failure_evidence
    is canonical.load_proposal_harbor_candidate_failure_evidence
)
""",
        """
import aec_bench.harness.harbor_importing.proposal_evidence as canonical
import aec_bench.harness.harbor_importing.proposal as facade
assert facade.ProposalHarborImportEvidence is canonical.ProposalHarborImportEvidence
assert facade.ProposalImportEvidenceExtension is canonical.ProposalImportEvidenceExtension
assert facade.PROPOSAL_IMPORT_EVIDENCE_EXTENSION is canonical.PROPOSAL_IMPORT_EVIDENCE_EXTENSION
assert facade.load_proposal_harbor_import_evidence is canonical.load_proposal_harbor_import_evidence
assert (
    facade.load_proposal_harbor_candidate_failure_evidence
    is canonical.load_proposal_harbor_candidate_failure_evidence
)
""",
    )

    for program in programs:
        subprocess.run([sys.executable, "-c", program], check=True)
