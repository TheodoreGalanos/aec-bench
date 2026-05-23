# ABOUTME: Tests that the seed JSON schema validates correct seeds and rejects invalid ones.
# ABOUTME: Ensures the skill-to-skill seed contract is enforced.

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "seeds" / "seed_schema.json"


@pytest.fixture()
def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists() -> None:
    assert SCHEMA_PATH.exists(), f"seed schema not found at {SCHEMA_PATH}"


def test_schema_validates_expert_seed(schema: dict) -> None:
    seed = {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "discipline": "electrical",
            "task_id": "cable-sizing-long-runs",
            "task_name": "Cable Sizing for Long Runs",
            "description": "Calculate minimum conductor cross-section for long cable runs",
            "inputs": [
                {"name": "Cable length", "type": "float", "unit": "m"},
                {"name": "Load current", "type": "float", "unit": "A"},
            ],
            "outputs": [
                {"name": "Cross-section", "type": "float", "unit": "mm²"},
            ],
            "standards": ["AS/NZS 3008.1.1"],
            "complexity": "medium",
        },
    }
    jsonschema.validate(seed, schema)


def test_schema_validates_ngnbench_seed(schema: dict) -> None:
    """Old-style seeds with flat string inputs/outputs must also validate."""
    seed = {
        "status": "proposed",
        "seed_origin": "ngnbench",
        "source": {
            "discipline": "civil",
            "task_id": "gravel-road-thickness",
            "task_name": "Gravel Road Pavement Thickness",
            "description": "Calculate required pavement thickness",
            "inputs": ["Subgrade CBR (%)", "Design traffic (ESAs)"],
            "outputs": ["Required base course thickness (mm)"],
            "standards": ["Austroads Guides"],
            "complexity": "low",
        },
    }
    jsonschema.validate(seed, schema)


def test_schema_validates_real_ngnbench_seed_with_all_optional_fields(
    schema: dict,
) -> None:
    """Mirrors the exact structure of a real on-disk seed (e.g., gravel-road-thickness)."""
    seed = {
        "status": "proposed",
        "seed_origin": "ngnbench",
        "source": {
            "discipline": "civil",
            "community": "civil_energy",
            "category_id": "access-roads",
            "category_name": "Access Road Design",
            "task_id": "gravel-road-thickness",
            "task_name": "Gravel Road Pavement Thickness",
            "description": "Calculate required pavement thickness for light-duty gravel access road",
            "complexity": "low",
            "standards": ["Austroads Guides"],
            "inputs": [
                "Subgrade CBR (%)",
                "Design traffic (ESAs)",
                "Gravel material properties",
            ],
            "outputs": [
                "Required base course thickness (mm)",
                "Compaction standard",
                "Crossfall (%)",
            ],
            "keyword_hits": ["calculate"],
            "source_file": "data/tasks/civil/civil_energy.json",
            "suggested_relative_path": "civil/access-roads/gravel-road-thickness",
        },
    }
    jsonschema.validate(seed, schema)


def test_schema_validates_full_expert_seed_with_all_optional_fields(
    schema: dict,
) -> None:
    seed = {
        "status": "proposed",
        "seed_origin": "expert",
        "created_by": "theo",
        "source": {
            "discipline": "electrical",
            "task_id": "cable-sizing-long-runs",
            "task_name": "Cable Sizing for Long Runs",
            "description": "Calculate minimum conductor cross-section for long cable runs",
            "inputs": [
                {"name": "Cable length", "type": "float", "unit": "m"},
            ],
            "outputs": [
                {"name": "Cross-section", "type": "float", "unit": "mm²"},
            ],
            "standards": ["AS/NZS 3008.1.1"],
            "reference_details": [
                "AS3008.1.1 Table 3 Column 4",
            ],
            "complexity": "medium",
            "worked_examples": [
                {
                    "description": "200m buried cable at 100A",
                    "inputs": {"cable_length": 200, "load_current": 100},
                    "outputs": {"cross_section": 95},
                },
            ],
            "edge_cases": [
                "Derating applies when more than 3 cables grouped",
            ],
            "community": "electrical_power",
            "category_id": "cable-sizing",
            "category_name": "Cable Sizing",
            "keyword_hits": ["calculate", "sizing"],
            "source_file": "data/tasks/electrical/electrical_power.json",
            "suggested_relative_path": "electrical/cable-sizing/cable-sizing-long-runs",
        },
        "feasibility": {
            "parameterisable": True,
            "criteria": {
                "closed_form": True,
                "deterministic": True,
                "parameterisable_inputs": True,
                "numeric_outputs": True,
                "single_compute": True,
            },
            "notes": "",
        },
    }
    jsonschema.validate(seed, schema)


def test_schema_rejects_missing_discipline(schema: dict) -> None:
    seed = {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "task_id": "cable-sizing",
            "task_name": "Cable Sizing",
            "description": "Calculate cable size",
            "inputs": [{"name": "Length", "type": "float", "unit": "m"}],
            "outputs": [{"name": "Size", "type": "float", "unit": "mm²"}],
            "standards": ["AS3008"],
            "complexity": "low",
        },
    }
    with pytest.raises(jsonschema.ValidationError, match="discipline"):
        jsonschema.validate(seed, schema)


def test_schema_rejects_invalid_discipline(schema: dict) -> None:
    seed = {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "discipline": "plumbing",
            "task_id": "pipe-sizing",
            "task_name": "Pipe Sizing",
            "description": "Size a pipe",
            "inputs": [{"name": "Flow", "type": "float", "unit": "L/s"}],
            "outputs": [{"name": "Diameter", "type": "float", "unit": "mm"}],
            "standards": ["AS3500"],
            "complexity": "low",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(seed, schema)


def test_schema_rejects_invalid_complexity(schema: dict) -> None:
    seed = {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "discipline": "civil",
            "task_id": "test",
            "task_name": "Test",
            "description": "Test task",
            "inputs": ["x"],
            "outputs": ["y"],
            "standards": ["std"],
            "complexity": "extreme",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(seed, schema)


def test_schema_rejects_empty_inputs(schema: dict) -> None:
    seed = {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "discipline": "civil",
            "task_id": "test",
            "task_name": "Test",
            "description": "Test task",
            "inputs": [],
            "outputs": ["y"],
            "standards": ["std"],
            "complexity": "low",
        },
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(seed, schema)
