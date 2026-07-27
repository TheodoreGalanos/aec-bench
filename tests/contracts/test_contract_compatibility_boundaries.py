# ABOUTME: Tests that historical research contracts stay at explicit experiment or compatibility boundaries.
# ABOUTME: Proves ordinary contract imports do not eagerly load provider-calibration wire schemas.

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import aec_bench.contracts as contracts
from aec_bench.contracts.compatibility.provider_calibration_v1 import (
    ProviderCalibrationTask as CompatibilityProviderCalibrationTask,
)
from aec_bench.contracts.evaluation_generation import (
    GovernedBatchExecutionClosure,
    GovernedBatchTerminalEvidence,
)
from aec_bench.contracts.provider_calibration import ProviderCalibrationTask


def test_provider_calibration_contract_path_is_an_identity_preserving_adapter() -> None:
    assert ProviderCalibrationTask is CompatibilityProviderCalibrationTask


def test_historical_pilot_contract_paths_are_owned_by_the_experiment() -> None:
    assert importlib.util.find_spec("aec_bench.contracts.phase_nine_calibration") is None
    assert importlib.util.find_spec("aec_bench.contracts.compatibility.phase91a_v1") is None


def test_historical_experiment_contracts_are_not_general_package_exports() -> None:
    exported = set(contracts.__all__)

    assert "Phase91aPilotPlan" not in exported
    assert "ProviderCalibrationPilotPlan" not in exported
    assert "ProviderCalibrationTask" not in exported
    assert "ProviderCalibrationTaskManifest" not in exported


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
                "'aec_bench.contracts.provider_calibration', "
                "'aec_bench.contracts.compatibility.phase91a_v1', "
                "'aec_bench.contracts.compatibility.provider_calibration_v1'"
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


def test_trajectory_contract_does_not_import_trial_record_contracts() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; "
                "import aec_bench.contracts.trajectory; "
                "assert 'aec_bench.contracts.trial_record' not in sys.modules"
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
    assert (
        importlib.util.find_spec(
            "aec_bench.meta_harness.compatibility.phase91a_accounting_v1",
        )
        is None
    )
    assert (
        importlib.util.find_spec(
            "aec_bench.meta_harness.phase_nine_calibration_accounting",
        )
        is None
    )


def test_governed_batch_has_no_unreleased_phase_specific_execution_surface() -> None:
    for module_name in (
        "aec_bench.meta_harness.phase91a_governed_pilot",
        "aec_bench.meta_harness.phase91a_governed_pilot_adapter",
        "aec_bench.meta_harness.governed_pilot_execution",
    ):
        assert importlib.util.find_spec(module_name) is None

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
        assert importlib.util.find_spec(module_name) is None

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
