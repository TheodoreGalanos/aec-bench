# ABOUTME: Tests for LLM-driven task genome decomposition orchestration.
# ABOUTME: Verifies prompt construction and validated manifest output without real model calls.

from pathlib import Path

from aec_bench.contracts.task_genome import PressurePoint, TaskGenomeReview
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.evolution.task_genome_decomposer import (
    build_decomposition_prompt,
    decompose_task_genome,
)
from aec_bench.harness.compilation.task_snapshot import build_task_snapshot
from aec_bench.tasks.genome import build_task_genome_review
from aec_bench.tasks.loader import load_task_definition

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def test_build_decomposition_prompt_includes_schema_and_evidence() -> None:
    task_dir = TASKS_ROOT / "electrical" / "voltage-drop"
    review, snapshot = _build_review(task_dir)

    prompt = build_decomposition_prompt(review, task_dir=task_dir, current_task=snapshot)

    assert "TaskGenomeManifest" in prompt
    assert "electrical/voltage-drop" in prompt
    assert "Snapshot-resolved evidence excerpts" in prompt
    assert "pressure_points" in prompt


def test_decompose_task_genome_accepts_injected_lite_reviewer() -> None:
    task_dir = TASKS_ROOT / "electrical" / "voltage-drop"
    review, snapshot = _build_review(task_dir)

    def reviewer(prompt: str) -> dict:
        assert "Snapshot-resolved evidence excerpts" in prompt
        payload = review.genome.model_dump(mode="json")
        payload["pressure_points"].append(
            PressurePoint(
                id="three_phase_impedance_formula",
                type="formula_selection",
                description="Solver must apply the three-phase impedance voltage-drop formula.",
                confidence="medium",
            ).model_dump(mode="json")
        )
        payload["extraction"]["reasoning_review_fields"] = []
        payload["extraction"]["deterministic_fields"].append("llm_pressure_points")
        return payload

    updated = decompose_task_genome(
        review,
        task_dir=task_dir,
        current_task=snapshot,
        model_name="lite-test",
        reviewer=reviewer,
    )

    assert updated.status == "needs_review"
    assert updated.reviewer == "lite-test"
    assert updated.extractor == review.extractor
    assert updated.task == review.task
    assert updated.genome.pressure_points[-1].id == "three_phase_impedance_formula"


def _build_review(task_dir: Path) -> tuple[TaskGenomeReview, TaskSnapshotRef]:
    snapshot = build_task_snapshot(
        task=load_task_definition(task_dir, TASKS_ROOT),
        tasks_root=TASKS_ROOT,
    )
    return build_task_genome_review(task_dir, TASKS_ROOT, task=snapshot), snapshot
