# ABOUTME: Tests that obsolete research contracts are absent from current package boundaries.
# ABOUTME: Proves ordinary contract imports do not eagerly load deleted experiment schemas.

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from aec_bench.contracts.evaluation_generation.lifecycle import (
    GovernedBatchExecutionClosure,
    GovernedBatchTerminalEvidence,
)


def _module_exists(module_name: str) -> bool:
    """Return whether an optional module exists, including when its parent is absent."""
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def test_historical_pilot_contract_paths_are_owned_by_the_experiment() -> None:
    assert not _module_exists("aec_bench.contracts.phase_nine_calibration")
    assert not _module_exists("aec_bench.contracts.compatibility.phase91a_v1")


def test_importing_one_contract_does_not_load_historical_experiment_contracts() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import aec_bench.contracts.harness_kernel; "
                "blocked = {"
                "'aec_bench.contracts.phase_nine_calibration', "
                "'aec_bench.contracts.compatibility.phase91a_v1'"
                "}; "
                "loaded = sorted(blocked.intersection(sys.modules)); "
                "assert not loaded, loaded"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_trajectory_contract_does_not_import_run_accounting_contract() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import aec_bench.contracts.trajectory; "
                "assert 'aec_bench.contracts.run_accounting' not in sys.modules"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_completed_batch_has_one_execution_accounting_surface() -> None:
    assert "accounting_evidence" not in GovernedBatchExecutionClosure.model_fields
    assert "accounting_evidence" not in GovernedBatchTerminalEvidence.model_fields
    assert "accounting_assignments" not in GovernedBatchTerminalEvidence.model_fields
    assert not _module_exists("aec_bench.meta_harness.compatibility.phase91a_accounting_v1")
    assert not _module_exists("aec_bench.meta_harness.phase_nine_calibration_accounting")


def test_governed_batch_has_no_unreleased_phase_specific_execution_surface() -> None:
    for module_name in (
        "aec_bench.meta_harness.phase91a_governed_pilot",
        "aec_bench.meta_harness.phase91a_governed_pilot_adapter",
        "aec_bench.meta_harness.governed_pilot_execution",
    ):
        assert not _module_exists(module_name)

    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    governed_pilot_schemas = tuple(
        path for path in source_root.rglob("*.py") if "aecbench.governed-pilot-" in path.read_text(encoding="utf-8")
    )
    assert governed_pilot_schemas == ()


def test_execution_preflight_has_no_unreleased_phase_specific_surface() -> None:
    for module_name in (
        "aec_bench.meta_harness.phase91a_preflight",
        "aec_bench.meta_harness.phase_nine_calibration_controller",
    ):
        assert not _module_exists(module_name)

    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    obsolete_schemas = {
        "aecbench.phase91a-proposal-invocation-ref.v1",
        "aecbench.phase91a-proposal-closure.v1",
        "aecbench.phase91a-verified-schedule.v1",
        "aecbench.phase91a-schedule-closure.v1",
        "aecbench.phase91a-compilation-result-ref.v1",
        "aecbench.phase91a-compilation-closure.v1",
        "aecbench.phase91a-monitor-closure.v1",
        "aecbench.phase91a-authorized-dispatch-ref.v1",
        "aecbench.phase91a-ready-pilot.v1",
        "aecbench.phase91a-execution-gate.v1",
    }
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in source_root.rglob("*.py"))
    assert all(schema not in source_text for schema in obsolete_schemas)
