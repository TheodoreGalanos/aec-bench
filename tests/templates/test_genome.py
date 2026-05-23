# ABOUTME: Tests for extracting task genome manifests from generation templates.
# ABOUTME: Verifies template-level sidecars avoid repeated runnable-instance noise.

from pathlib import Path

import yaml

from aec_bench.templates.genome import extract_template_genome, template_genome_to_yaml

TEMPLATES_ROOT = Path(__file__).resolve().parents[2] / "src" / "aec_bench" / "templates" / "builtin"


def test_extracts_mechanical_velocity_template_genome() -> None:
    manifest = extract_template_genome(
        TEMPLATES_ROOT / "mechanical" / "velocity_check",
        Path.cwd(),
    )

    assert manifest.task_id == "mechanical/velocity-check"
    assert manifest.domain_frame.discipline == "mechanical"
    assert manifest.domain_frame.subdomain == "pipe-hydraulics"
    assert manifest.domain_frame.standards == ["AWWA M11", "Crane TP-410"]
    assert manifest.input_bundle.quantities == [
        "flow_rate_l_s",
        "pipe_internal_diameter_mm",
        "minimum_velocity_m_s",
        "maximum_velocity_m_s",
    ]
    assert manifest.output_contract.required_fields == [
        "pipe_area_m2",
        "velocity_m_s",
        "min_margin_m_s",
        "max_margin_m_s",
        "velocity_within_range",
    ]
    assert manifest.verifier_contract.mode == "template_engine"
    assert manifest.verifier_contract.script == ("src/aec_bench/templates/builtin/mechanical/velocity_check/engine.py")
    assert manifest.verifier_contract.field_scores["velocity_within_range"] == "tolerance_0.01"
    assert any(point.id == "explicit_range_check" for point in manifest.pressure_points)


def test_template_genome_yaml_round_trips() -> None:
    manifest = extract_template_genome(
        TEMPLATES_ROOT / "mechanical" / "pump_head_calculation",
        Path.cwd(),
    )

    payload = yaml.safe_load(template_genome_to_yaml(manifest))

    assert payload["task_id"] == "mechanical/pump-head-calculation"
    assert payload["output_contract"]["required_fields"] == [
        "static_head_m",
        "pressure_head_differential_m",
        "friction_head_m",
        "total_dynamic_head_m",
        "hydraulic_power_kw",
    ]
    assert "pressure_points" in payload
