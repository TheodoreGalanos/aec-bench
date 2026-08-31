# ABOUTME: Tests optional-dependency boundaries for the public evolution package.
# ABOUTME: Proves web imports stay provider-free while public evolution exports remain available.

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_REPOSITORY_ROOT = Path(__file__).parents[2]


def _run_probe(source: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(_REPOSITORY_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-c", source],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_evolution_package_does_not_require_evolution_dependencies() -> None:
    result = _run_probe(
        """
import importlib.abc
import sys


class BlockOptionalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "numpy" or fullname == "aec_bench.evolution.application":
            raise ModuleNotFoundError(f"blocked optional import: {fullname}")
        return None


sys.meta_path.insert(0, BlockOptionalImports())
import aec_bench.evolution

assert "numpy" not in sys.modules
assert "aec_bench.evolution.application" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_web_app_import_does_not_eagerly_load_evolution_application() -> None:
    result = _run_probe(
        """
import importlib.abc
import sys


class BlockOptionalImports(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "numpy" or fullname == "aec_bench.evolution.application":
            raise ModuleNotFoundError(f"blocked optional import: {fullname}")
        return None


sys.meta_path.insert(0, BlockOptionalImports())
from aec_bench.web.app import create_app

assert callable(create_app)
assert "numpy" not in sys.modules
assert "aec_bench.evolution.application" not in sys.modules
""",
    )

    assert result.returncode == 0, result.stderr


def test_public_evolution_exports_resolve_on_request() -> None:
    result = _run_probe(
        """
import aec_bench.evolution as evolution

expected = (
    "CandidateChecks",
    "CandidateProposal",
    "CandidateProposalRequest",
    "ProposalStatus",
    "ReportWriter",
    "build_avo",
    "build_local_checks",
    "gate_candidate",
    "next_evolution_state",
    "run_evolution",
    "run_evolution_from_config",
)
assert evolution.__all__ == expected

from aec_bench.evolution import (
    CandidateChecks,
    CandidateProposal,
    CandidateProposalRequest,
    ProposalStatus,
    ReportWriter,
    build_avo,
    build_local_checks,
    gate_candidate,
    next_evolution_state,
    run_evolution,
    run_evolution_from_config,
)

assert CandidateChecks
assert CandidateProposal
assert CandidateProposalRequest
assert ProposalStatus
assert ReportWriter
assert callable(build_avo)
assert callable(build_local_checks)
assert callable(gate_candidate)
assert callable(next_evolution_state)
assert callable(run_evolution)
assert callable(run_evolution_from_config)
""",
    )

    assert result.returncode == 0, result.stderr
