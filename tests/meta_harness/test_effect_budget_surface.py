# ABOUTME: Pins the generic effect-accounting surface and dependency direction.
# ABOUTME: Prevents phase-specific schemas, readers, and facades from entering fixed code.

from __future__ import annotations

import importlib.util
from pathlib import Path

from aec_bench.meta_harness import effect_budget


def test_core_effect_budget_has_no_calibration_run_surface() -> None:
    assert effect_budget.__all__ == [
        "EffectBudgetCollisionError",
        "EffectBudgetConfinementError",
        "EffectBudgetError",
        "EffectBudgetExceededError",
        "EffectBudgetIncompleteError",
        "EffectBudgetIntegrityError",
        "EffectBudgetLedger",
        "EffectOperationState",
    ]
    for module_name in (
        "aec_bench.meta_harness.effect_budget.phase91a_contracts",
        "aec_bench.meta_harness.effect_budget.phase91a_ledger",
        "aec_bench.meta_harness.effect_budget.phase91a_policy",
    ):
        assert importlib.util.find_spec(module_name) is None

    source_root = Path(__file__).parents[2] / "src" / "aec_bench" / "meta_harness" / "effect_budget"
    source = "\n".join(path.read_text(encoding="utf-8") for path in source_root.glob("*.py"))
    assert "Phase91a" not in source
    assert "phase91a" not in source
    assert "provider_calibration" not in source


def test_fixed_source_does_not_depend_on_provider_calibration_experiment() -> None:
    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    offenders = tuple(
        path.relative_to(source_root).as_posix()
        for path in sorted(source_root.rglob("*.py"))
        if "experiments" not in path.relative_to(source_root).parts
        and "aec_bench.experiments.provider_calibration_v1"
        in path.read_text(
            encoding="utf-8",
        )
    )

    assert offenders == ()


def test_no_provider_calibration_budget_compatibility_reader_remains() -> None:
    source_root = Path(__file__).parents[2] / "src" / "aec_bench"
    compatibility_root = source_root / "meta_harness" / "compatibility" / "provider_calibration_v1"
    assert tuple(compatibility_root.rglob("*.py")) == ()

    references = tuple(
        path.relative_to(source_root).as_posix()
        for path in sorted(source_root.rglob("*.py"))
        if "meta_harness.compatibility.provider_calibration_v1" in path.read_text(encoding="utf-8")
    )
    assert references == ()


def test_removed_phase_and_cli_facades_do_not_return() -> None:
    removed_modules = (
        "aec_bench.meta_harness.phase_nine_protocol",
        "aec_bench.meta_harness.compatibility.phase_nine_protocol_v1",
    )

    for module_name in removed_modules:
        assert importlib.util.find_spec(module_name) is None


def test_effect_budget_facade_declares_only_its_generic_public_surface() -> None:
    assert effect_budget.__all__ == [
        "EffectBudgetCollisionError",
        "EffectBudgetConfinementError",
        "EffectBudgetError",
        "EffectBudgetExceededError",
        "EffectBudgetIncompleteError",
        "EffectBudgetIntegrityError",
        "EffectBudgetLedger",
        "EffectOperationState",
    ]
