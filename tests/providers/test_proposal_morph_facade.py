# ABOUTME: Guards the stable Morph Harbor facade while its implementation lives in a focused package.
# ABOUTME: Proves import order, public object identity, and the historical Harbor import path remain exact.

from __future__ import annotations

import subprocess
import sys

import pytest

_PUBLIC_NAMES = (
    "MORPH_MIN_DISK_SIZE_MB",
    "PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH",
    "REMOTE_LOGS_DIR",
    "REMOTE_TESTS_DIR",
    "REMOTE_WORKSPACE_DIR",
    "ProposalCandidateInvocationTransition",
    "ProposalMorphBoundaryError",
    "ProposalMorphCleanupReceipt",
    "ProposalMorphHarborEnvironment",
    "ProposalMorphHarborOperations",
    "load_completed_proposal_morph_cleanup_receipt",
)


@pytest.mark.parametrize(
    ("first_module", "second_module"),
    (
        (
            "aec_bench.providers.proposal_morph_harbor",
            "aec_bench.providers.proposal_morph",
        ),
        (
            "aec_bench.providers.proposal_morph",
            "aec_bench.providers.proposal_morph_harbor",
        ),
    ),
)
def test_facade_and_canonical_package_share_public_objects_in_either_import_order(
    first_module: str,
    second_module: str,
) -> None:
    names = repr(_PUBLIC_NAMES)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib;"
                f"first=importlib.import_module({first_module!r});"
                f"second=importlib.import_module({second_module!r});"
                f"names={names};"
                "assert all(getattr(first,name) is getattr(second,name) for name in names);"
                "assert first.PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH =="
                "'aec_bench.providers.proposal_morph_harbor:ProposalMorphHarborEnvironment';"
                "module_name,class_name=first.PROPOSAL_MORPH_HARBOR_ENVIRONMENT_IMPORT_PATH.split(':',1);"
                "resolved=getattr(importlib.import_module(module_name),class_name);"
                "assert resolved is first.ProposalMorphHarborEnvironment"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert probe.returncode == 0, probe.stderr
