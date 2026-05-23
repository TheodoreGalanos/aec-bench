# ABOUTME: Tests for the LibraryCatalogue boundary contract exposed to the aec-bench site.
# ABOUTME: Pure pydantic validation — no I/O, no projection logic.

import pytest
from pydantic import ValidationError

from aec_bench.contracts.library_catalogue import (
    InputField,
    LibraryEntryBase,
    OutputField,
    SeedEntry,
    TemplateEntry,
)


def test_input_field_name_only() -> None:
    f = InputField(name="cable_size_mm2")
    assert f.name == "cable_size_mm2"
    assert f.description is None
    assert f.unit is None
    assert f.type is None


def test_input_field_fully_specified() -> None:
    f = InputField(
        name="length_m",
        description="Cable route length",
        unit="m",
        type="float",
    )
    assert f.unit == "m"
    assert f.type == "float"


def test_input_field_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        InputField(name="x", type="complex")


def test_output_field_tolerance_optional() -> None:
    f = OutputField(name="result")
    assert f.tolerance is None


def test_output_field_with_tolerance() -> None:
    f = OutputField(name="voltage_drop_percent", tolerance=0.03, description="drop %")
    assert f.tolerance == 0.03


def test_library_entry_base_requires_core_fields() -> None:
    e = LibraryEntryBase(
        task_id="voltage-drop",
        discipline="electrical",
        category="cable-sizing",
    )
    assert e.task_id == "voltage-drop"
    assert e.category_label is None
    assert e.standards == []
    assert e.inputs == []
    assert e.outputs == []


def test_library_entry_base_rejects_unknown_discipline() -> None:
    with pytest.raises(ValidationError):
        LibraryEntryBase(
            task_id="x",
            discipline="hvac",  # not in the 5-discipline literal
            category="x",
        )


def test_field_models_reject_extra_fields() -> None:
    """All three boundary classes inherit StrictModel and reject unknown fields."""
    with pytest.raises(ValidationError):
        InputField(name="x", surprise="boom")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        OutputField(name="x", surprise="boom")  # type: ignore[call-arg]
    with pytest.raises(ValidationError):
        LibraryEntryBase(
            task_id="x",
            discipline="electrical",
            category="x",
            surprise="boom",  # type: ignore[call-arg]
        )


def test_template_entry_status_is_literal_built() -> None:
    t = TemplateEntry(
        task_id="voltage-drop",
        discipline="electrical",
        category="cable-sizing",
        task_name="Voltage Drop",
        description="Cable voltage drop calculation",
        tool_mode="with-tool",
        difficulty_tiers=["easy", "medium", "hard"],
        archetype_count=4,
    )
    assert t.status == "built"
    assert t.tool_mode == "with-tool"
    assert t.long_description is None
    assert t.tags == []


def test_template_entry_rejects_wrong_status() -> None:
    with pytest.raises(ValidationError):
        TemplateEntry(
            task_id="x",
            discipline="electrical",
            category="x",
            status="proposed",  # type: ignore[arg-type] — must be "built"
            task_name="x",
            description="x",
            tool_mode="with-tool",
            difficulty_tiers=[],
            archetype_count=0,
        )


def test_template_entry_rejects_unknown_tool_mode() -> None:
    with pytest.raises(ValidationError):
        TemplateEntry(
            task_id="x",
            discipline="electrical",
            category="x",
            task_name="x",
            description="x",
            tool_mode="maybe",  # type: ignore[arg-type]
            difficulty_tiers=[],
            archetype_count=0,
        )


def test_seed_entry_status_is_literal_proposed() -> None:
    s = SeedEntry(
        task_id="busbar-thermal",
        discipline="electrical",
        category="busbar-design",
        category_label="Busbar Design & Analysis",
        task_name="Busbar Thermal Sizing",
        description="Size busbar for continuous current",
        complexity="low",
    )
    assert s.status == "proposed"
    assert s.complexity == "low"


def test_seed_entry_rejects_wrong_status() -> None:
    with pytest.raises(ValidationError):
        SeedEntry(
            task_id="x",
            discipline="electrical",
            category="x",
            status="built",  # type: ignore[arg-type] — must be "proposed"
            task_name="x",
            description="x",
        )


def test_seed_entry_complexity_is_optional() -> None:
    s = SeedEntry(
        task_id="x",
        discipline="electrical",
        category="x",
        task_name="x",
        description="x",
    )
    assert s.complexity is None


def test_catalogue_counts_basic() -> None:
    from aec_bench.contracts.library_catalogue import CatalogueCounts

    c = CatalogueCounts(
        total_templates=79,
        total_seeds=393,
        by_discipline={
            "electrical": {"templates": 14, "seeds": 75},
            "civil": {"templates": 72, "seeds": 88},
        },
    )
    assert c.total_templates == 79
    assert c.by_discipline["electrical"]["templates"] == 14


def test_library_catalogue_schema_version_is_pinned_to_1() -> None:
    from datetime import UTC, datetime

    from aec_bench.contracts.library_catalogue import CatalogueCounts, LibraryCatalogue

    with pytest.raises(ValidationError):
        LibraryCatalogue(
            schema_version=2,  # type: ignore[arg-type] — pinned to 1
            generated_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
            library_version="0.1.0",
            templates=[],
            seeds=[],
            counts=CatalogueCounts(total_templates=0, total_seeds=0, by_discipline={}),
        )


def test_library_catalogue_round_trip() -> None:
    from datetime import UTC, datetime

    from aec_bench.contracts.library_catalogue import CatalogueCounts, LibraryCatalogue

    cat = LibraryCatalogue(
        generated_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
        library_version="0.1.0",
        library_commit="abc1234",
        templates=[
            TemplateEntry(
                task_id="voltage-drop",
                discipline="electrical",
                category="cable-sizing",
                task_name="Voltage Drop",
                description="Cable voltage drop",
                tool_mode="with-tool",
                difficulty_tiers=["easy", "medium", "hard"],
                archetype_count=4,
            )
        ],
        seeds=[],
        counts=CatalogueCounts(
            total_templates=1,
            total_seeds=0,
            by_discipline={"electrical": {"templates": 1, "seeds": 0}},
        ),
    )
    # Round-trip through JSON — the site consumes this shape.
    serialised = cat.model_dump_json()
    reparsed = LibraryCatalogue.model_validate_json(serialised)
    assert reparsed == cat


def test_library_catalogue_library_commit_optional() -> None:
    from datetime import UTC, datetime

    from aec_bench.contracts.library_catalogue import CatalogueCounts, LibraryCatalogue

    cat = LibraryCatalogue(
        generated_at=datetime(2026, 4, 19, 12, 0, tzinfo=UTC),
        library_version="0.1.0",
        templates=[],
        seeds=[],
        counts=CatalogueCounts(total_templates=0, total_seeds=0, by_discipline={}),
    )
    assert cat.library_commit is None
    assert cat.schema_version == 1


def test_golden_fixture_parses_cleanly() -> None:
    """Lock the public shape — if this breaks, the site repo contract has changed."""
    from datetime import datetime
    from pathlib import Path

    from aec_bench.contracts.library_catalogue import LibraryCatalogue

    fixture_path = Path(__file__).parent / "fixtures" / "library_catalogue_golden.json"
    raw = fixture_path.read_text(encoding="utf-8")
    cat = LibraryCatalogue.model_validate_json(raw)
    # Smoke-check every top-level field the site depends on.
    assert cat.schema_version == 1
    assert cat.library_version
    assert isinstance(cat.generated_at, datetime)
    assert len(cat.templates) >= 1
    assert len(cat.seeds) >= 1
    assert cat.counts.total_templates == len(cat.templates)
    assert cat.counts.total_seeds == len(cat.seeds)
