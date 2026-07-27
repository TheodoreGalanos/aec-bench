# ABOUTME: Enforces the narrow set of experiment helpers shipped with aec-bench.
# ABOUTME: Keeps concrete adaptive campaigns, critic studies, and calibration runs out of the wheel.

from __future__ import annotations

from pathlib import Path

SOURCE_EXPERIMENTS = Path(__file__).parents[2] / "src" / "aec_bench" / "experiments"
EXPECTED_LIBRARY_EXPERIMENTS = {
    "__init__.py",
    "task_ecology_baseline.py",
    "task_ecology_benchmark.py",
}


def test_library_contains_only_reusable_experiment_helpers() -> None:
    actual = {
        path.relative_to(SOURCE_EXPERIMENTS).as_posix()
        for path in SOURCE_EXPERIMENTS.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    }

    assert actual == EXPECTED_LIBRARY_EXPERIMENTS
