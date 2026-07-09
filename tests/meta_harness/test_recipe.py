# ABOUTME: Tests scriptable meta-harness candidate-vs-baseline recipe helpers.
# ABOUTME: Covers recipe materialization and deterministic comparison outputs.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.meta_harness.recipe import (
    materialize_harness_comparison_recipe,
    run_harness_comparison_from_files,
)


def test_materialize_harness_comparison_recipe_writes_scripts(tmp_path: Path) -> None:
    output_dir = tmp_path / "recipe"

    result = materialize_harness_comparison_recipe(
        output_dir=output_dir,
        task_text="Create a diagnostic calculation task.",
        process_id="process.recipe",
        baseline_world=Path("baseline-world.json"),
        baseline_run=Path("baseline-run.json"),
        candidate_world=Path("candidate-world.json"),
        candidate_run=Path("candidate-run.json"),
        command_prefix="uv run aec-bench",
    )
    recipe = json.loads((output_dir / "recipe.json").read_text(encoding="utf-8"))

    assert result["status"] == "materialized"
    assert (output_dir / "task.md").read_text(encoding="utf-8").startswith("Create a diagnostic")
    assert (output_dir / "run_recipe.sh").exists()
    assert (output_dir / "compare_candidate.py").exists()
    assert recipe["steps"][-1]["id"] == "compare"
    assert recipe["paths"]["baseline_world"] == "baseline-world.json"


def test_run_harness_comparison_from_files_writes_json_and_markdown(tmp_path: Path) -> None:
    brief = tmp_path / "brief.json"
    baseline_world = tmp_path / "baseline-world.json"
    candidate_world = tmp_path / "candidate-world.json"
    baseline_run = tmp_path / "baseline-run.json"
    candidate_run = tmp_path / "candidate-run.json"
    output_dir = tmp_path / "comparison"
    _write_json(brief, _brief())
    _write_json(baseline_world, _world("world.baseline"))
    _write_json(candidate_world, _world("world.candidate"))
    _write_json(baseline_run, _task_run("run.baseline", reward=0.5))
    _write_json(candidate_run, _task_run("run.candidate", reward=1.0))

    comparison = run_harness_comparison_from_files(
        brief_path=brief,
        baseline_world_path=baseline_world,
        candidate_world_path=candidate_world,
        baseline_run_path=baseline_run,
        candidate_run_path=candidate_run,
        output_dir=output_dir,
    )

    assert comparison["status"] == "complete"
    assert comparison["deltas"]["reward"] == 0.5
    assert comparison["recommendation"]["status"] == "candidate_improved"
    assert (output_dir / "comparison.json").exists()
    assert "candidate_improved" in (output_dir / "comparison.md").read_text(encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _brief() -> dict:
    return {
        "brief_id": "brief.recipe",
        "objective": "Compare a candidate harness against a baseline.",
        "task_request": "Create a diagnostic calculation task.",
        "evidence_requirements": ["verifier reward", "artifact evidence"],
    }


def _world(world_id: str) -> dict:
    return {
        "world_id": world_id,
        "task_unit": "Complete a calculation.",
        "logic_profile": {
            "closure_gates": [{"id": "verifier_passed", "evidence_key": "score.passed", "expected": True}],
            "construction_gates": [{"id": "artifact_witnessed", "construction_required": ["artifacts.report.path"]}],
            "containment_gates": [],
            "agentic_review": {"required": True, "review_modes": ["verifier_result"]},
        },
    }


def _task_run(run_id: str, *, reward: float) -> dict:
    return {
        "run_id": run_id,
        "evidence": {
            "score": {"passed": True, "reward": reward},
            "artifacts": {"report": {"path": "logs/verifier/artifacts/report.json"}},
            "agentic_review": {"status": "complete", "reviewed_modes": ["verifier_result"], "findings": []},
        },
    }
