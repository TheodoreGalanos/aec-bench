# ABOUTME: Tests template genome decomposition into recombinable task parts.
# ABOUTME: Verifies decomposition sidecars expose crossover-facing structure.

from pathlib import Path

from aec_bench.templates.decomposition import (
    build_template_decomposition,
    task_decomposition_to_yaml,
)
from aec_bench.templates.genome import extract_template_genome

TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "templates" / "builtin"


def test_builds_velocity_check_template_decomposition() -> None:
    manifest = extract_template_genome(
        TEMPLATES_ROOT / "mechanical" / "velocity_check",
        Path.cwd(),
    )

    decomposition = build_template_decomposition(
        manifest,
        source_genome_path="src/aec_bench/templates/builtin/mechanical/velocity_check",
    )

    part_ids = [part.id for part in decomposition.parts]
    assert decomposition.task_id == "mechanical/velocity-check"
    assert "threshold_decision" in part_ids
    assert "verifier_contract" in part_ids
    assert any("velocity_m_s" in part.summary for part in decomposition.parts)
    assert any("explicit_range_check" in note for note in decomposition.crossover_notes)


def test_template_decomposition_yaml_round_trips() -> None:
    manifest = extract_template_genome(
        TEMPLATES_ROOT / "electrical" / "voltage_drop",
        Path.cwd(),
    )

    decomposition = build_template_decomposition(
        manifest,
        source_genome_path="src/aec_bench/templates/builtin/electrical/voltage_drop",
    )

    assert "task_id: electrical/voltage-drop" in task_decomposition_to_yaml(decomposition)
