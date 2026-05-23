# ABOUTME: Tests for SeedTask contract mirroring seeds/seed_schema.json.
# ABOUTME: Validates source fields, input/output shape variants, and enum enforcement.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.seed_task import SeedSource, SeedTask, StructuredSeedField


def test_seed_task_plain_string_inputs() -> None:
    seed = SeedTask(
        status="proposed",
        seed_origin="ngnbench",
        source=SeedSource(
            discipline="electrical",
            task_id="busbar-thermal",
            task_name="Busbar Thermal Sizing",
            description="Size busbar for continuous current",
            inputs=["Continuous current (A)", "Material (copper/aluminum)"],
            outputs=["Required cross-section (mm²)"],
            standards=["IEEE 605"],
            complexity="low",
            category_id="busbar-design",
            category_name="Busbar Design & Analysis",
        ),
    )
    assert seed.source.discipline == "electrical"
    assert seed.source.inputs == ["Continuous current (A)", "Material (copper/aluminum)"]
    assert seed.source.category_id == "busbar-design"


def test_seed_task_structured_inputs() -> None:
    seed = SeedTask(
        status="proposed",
        seed_origin="expert",
        source=SeedSource(
            discipline="civil",
            task_id="rational-method",
            task_name="Rational Method Peak Flow",
            description="Compute peak runoff",
            inputs=[
                StructuredSeedField(name="catchment_area", type="float", unit="ha"),
                StructuredSeedField(name="runoff_coefficient", type="float"),
            ],
            outputs=[StructuredSeedField(name="peak_flow", type="float", unit="m3/s")],
            standards=["AR&R 2019"],
            complexity="medium",
        ),
    )
    assert seed.source.inputs[0].name == "catchment_area"
    assert seed.source.inputs[0].unit == "ha"


def test_seed_task_rejects_unknown_discipline() -> None:
    with pytest.raises(ValidationError):
        SeedSource(
            discipline="hvac",  # not in the 5-discipline enum
            task_id="x",
            task_name="x",
            description="x",
            inputs=["i"],
            outputs=["o"],
            standards=["s"],
            complexity="low",
        )


def test_seed_task_rejects_unknown_complexity() -> None:
    with pytest.raises(ValidationError):
        SeedSource(
            discipline="civil",
            task_id="x",
            task_name="x",
            description="x",
            inputs=["i"],
            outputs=["o"],
            standards=["s"],
            complexity="extreme",  # not low|medium|high
        )


def test_seed_task_optional_fields_default_none() -> None:
    seed = SeedTask(
        status="proposed",
        seed_origin="expert",
        source=SeedSource(
            discipline="ground",
            task_id="bearing-capacity",
            task_name="Shallow Foundation Bearing Capacity",
            description="Compute ultimate bearing capacity",
            inputs=["c", "phi"],
            outputs=["qu"],
            standards=["AS 5100.3"],
            complexity="medium",
        ),
    )
    assert seed.source.category_id is None
    assert seed.source.category_name is None
    assert seed.source.community is None


def test_structured_seed_field_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        StructuredSeedField(name="x", type="complex")  # only float/int/categorical


def test_seed_task_validates_from_dict_with_structured_field_dicts() -> None:
    """The real consumer path: SeedTask.model_validate on a dict from json.load.

    Structured input fields will be dict-shaped, not pre-constructed StructuredSeedField
    instances. Pydantic must coerce the dicts into the correct branch of the union.
    """
    raw = {
        "status": "proposed",
        "seed_origin": "expert",
        "source": {
            "discipline": "civil",
            "task_id": "rational-method",
            "task_name": "Rational Method",
            "description": "d",
            "inputs": [
                {"name": "area", "type": "float", "unit": "ha"},
                {"name": "type", "type": "categorical", "values": ["urban", "rural"]},
            ],
            "outputs": [{"name": "peak_flow", "type": "float", "unit": "m3/s"}],
            "standards": ["AR&R"],
            "complexity": "medium",
        },
    }
    seed = SeedTask.model_validate(raw)
    assert isinstance(seed.source.inputs[0], StructuredSeedField)
    assert seed.source.inputs[0].name == "area"
    assert seed.source.inputs[0].type == "float"
    assert seed.source.inputs[1].values == ["urban", "rural"]
    assert seed.source.outputs[0].unit == "m3/s"


def test_seed_task_ignores_unknown_optional_schema_fields() -> None:
    """Real seed files carry optional schema fields (keyword_hits, source_file, etc)
    that aren't modelled here. They must be silently ignored, not rejected."""
    raw = {
        "status": "proposed",
        "seed_origin": "ngnbench",
        "created_by": "someone",  # top-level extra (in the JSON schema, not in our model)
        "source": {
            "discipline": "electrical",
            "task_id": "x",
            "task_name": "x",
            "description": "x",
            "inputs": ["i"],
            "outputs": ["o"],
            "standards": ["s"],
            "complexity": "low",
            "keyword_hits": ["a", "b"],  # source-level extra
            "source_file": "data/x.json",  # source-level extra
            "suggested_relative_path": "x/y",  # source-level extra
        },
    }
    seed = SeedTask.model_validate(raw)
    assert seed.source.task_id == "x"
    # Ensure the unknown fields were truly dropped — extra="ignore" doesn't keep them.
    assert not hasattr(seed.source, "keyword_hits")
    assert not hasattr(seed, "created_by")
