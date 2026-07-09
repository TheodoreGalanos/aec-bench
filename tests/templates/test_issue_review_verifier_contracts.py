# ABOUTME: Checks domain-neutral verifier behavior shared by every issue-review template.
# ABOUTME: Prevents claim-boundary wording equivalence from drifting across copied verifiers.

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "templates" / "builtin"
ISSUE_REVIEW_DIRS = sorted(TEMPLATE_ROOT.glob("*/*_issue_review_package"))

SUPPORTED_BOUNDARIES = [
    (
        "This review covers a task-owned synthetic source packet and does not claim authority approval, "
        "accepted project evidence, full standards compliance, source-pack hardening, executable-verifier "
        "readiness, or benchmark readiness."
    ),
    (
        "This review covers a task-owned synthetic source packet only. It does not claim or imply regulatory "
        "approval, acceptance as project evidence, compliance with any named standard, hardening of the source "
        "pack, readiness for use in an executable verifier, or benchmark certification."
    ),
    (
        "This review covers a task-owned synthetic source packet and does not constitute authority acceptance, "
        "project-of-record evidence, certification of standards compliance, validation or hardening of the source "
        "packet, readiness for executable verification, or benchmark compliance."
    ),
    (
        "This review covers a task-owned synthetic source packet and does not constitute authority (AHJ) approval, "
        "accepted project evidence, a finding of full standards compliance, source-pack hardening, "
        "executable-verifier readiness, or benchmark readiness."
    ),
    (
        "This review covers a task-owned synthetic source packet and does not constitute authority approval of any "
        "project document, acceptance of any project evidence, demonstration of full standards compliance, "
        "source-pack hardening, executable-verifier readiness, or benchmark readiness."
    ),
]


def _load_verifier(template_dir: Path):
    path = template_dir / "verify.py"
    spec = importlib.util.spec_from_file_location(f"{template_dir.name}_verify", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("template_dir", ISSUE_REVIEW_DIRS, ids=lambda path: path.name)
@pytest.mark.parametrize("statement", SUPPORTED_BOUNDARIES)
def test_issue_review_verifier_accepts_equivalent_claim_boundaries(template_dir: Path, statement: str) -> None:
    verifier = _load_verifier(template_dir)

    _score, details = verifier.score_identity_claims({"identity_ledger": {}, "claim_boundary_statement": statement})

    assert details["checks"]["claim_boundary"] == 1.0


@pytest.mark.parametrize("template_dir", ISSUE_REVIEW_DIRS, ids=lambda path: path.name)
def test_issue_review_verifier_rejects_missing_claim_boundary_category(template_dir: Path) -> None:
    verifier = _load_verifier(template_dir)
    incomplete = (
        "This review covers a task-owned synthetic source packet and does not claim authority approval, "
        "accepted project evidence, full standards compliance, source-pack hardening, or benchmark readiness."
    )

    _score, details = verifier.score_identity_claims({"identity_ledger": {}, "claim_boundary_statement": incomplete})

    assert details["checks"]["claim_boundary"] == 0.0
