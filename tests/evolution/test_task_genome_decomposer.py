# ABOUTME: Tests for LLM-driven task genome decomposition orchestration.
# ABOUTME: Verifies prompt construction and validated manifest output without real model calls.

from pathlib import Path

from aec_bench.contracts.task_genome import PressurePoint, ProvenanceRef
from aec_bench.evolution.task_genome_decomposer import (
    build_decomposition_prompt,
    decompose_task_genome,
)
from aec_bench.tasks.genome import build_task_genome_evidence

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def test_build_decomposition_prompt_includes_schema_and_evidence() -> None:
    packet = build_task_genome_evidence(TASKS_ROOT / "electrical" / "voltage-drop", TASKS_ROOT)

    prompt = build_decomposition_prompt(packet)

    assert "TaskGenomeManifest" in prompt
    assert "electrical/voltage-drop" in prompt
    assert "Evidence packet" in prompt
    assert "pressure_points" in prompt


def test_decompose_task_genome_accepts_injected_lite_reviewer() -> None:
    packet = build_task_genome_evidence(TASKS_ROOT / "electrical" / "voltage-drop", TASKS_ROOT)

    def reviewer(prompt: str) -> dict:
        assert "Evidence packet" in prompt
        payload = packet.deterministic_manifest.model_dump(mode="json")
        payload["status"] = "needs_review"
        payload["pressure_points"].append(
            PressurePoint(
                id="three_phase_impedance_formula",
                type="formula_selection",
                description="Solver must apply the three-phase impedance voltage-drop formula.",
                provenance=[
                    ProvenanceRef(
                        file="instruction.md",
                        section="Problem",
                        signal="three-phase cable circuit",
                    )
                ],
                confidence="medium",
                reviewed_by="lite_reviewer",
            ).model_dump(mode="json")
        )
        payload["extraction"]["reasoning_review_fields"] = []
        payload["extraction"]["deterministic_fields"].append("llm_pressure_points")
        return payload

    manifest = decompose_task_genome(packet, model_name="lite-test", reviewer=reviewer)

    assert manifest.status == "needs_review"
    assert manifest.pressure_points[-1].id == "three_phase_impedance_formula"
    assert manifest.pressure_points[-1].reviewed_by == "lite_reviewer"
