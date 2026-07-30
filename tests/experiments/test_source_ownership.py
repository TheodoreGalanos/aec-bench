# ABOUTME: Enforces the narrow set of experiment helpers shipped with aec-bench.
# ABOUTME: Keeps concrete adaptive campaigns, critic studies, and calibration runs out of the wheel.

from __future__ import annotations

import ast
from pathlib import Path

SOURCE_EXPERIMENTS = Path(__file__).parents[2] / "src" / "aec_bench" / "experiments"
EXPECTED_LIBRARY_EXPERIMENTS = {
    "__init__.py",
    "stewardship_continuity/__init__.py",
    "stewardship_continuity/analysis.py",
    "stewardship_continuity/artifacts.py",
    "stewardship_continuity/contracts.py",
    "stewardship_continuity/fixtures.py",
    "stewardship_continuity/planning.py",
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


def test_stewardship_continuity_helpers_do_not_import_provider_code() -> None:
    continuity_root = SOURCE_EXPERIMENTS / "stewardship_continuity"
    forbidden_roots = {
        "aec_bench.adapters",
        "aec_bench.providers",
    }

    imports = {
        alias.name
        for path in continuity_root.glob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in (node.names if isinstance(node, ast.Import) else [ast.alias(name=node.module or "")])
    }

    assert all(
        not any(import_name == root or import_name.startswith(f"{root}.") for root in forbidden_roots)
        for import_name in imports
    )
