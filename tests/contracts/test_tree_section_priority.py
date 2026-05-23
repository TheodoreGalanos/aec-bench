# ABOUTME: Tests TreeSection.source_priority field for per-source numeric authority priority.
# ABOUTME: Lower integer = higher authority. Keyed by the "source:field" string used in input_mapping.

import dataclasses

import pytest

from aec_bench.contracts.repl import OutputField, TreeSection


def _make_section(**overrides):
    defaults = dict(
        id="test",
        title="Test",
        fields={"body": OutputField(name="body", dtype="str", description="")},
        depends_on=(),
        generation_mode="prose",
        per_discipline=False,
        writing_guidance=(),
        input_mapping=(),
    )
    defaults.update(overrides)
    return TreeSection(**defaults)


def test_source_priority_defaults_to_empty_mapping():
    section = _make_section()
    assert section.source_priority == {}


def test_source_priority_accepts_integer_map_keyed_by_source_field():
    section = _make_section(
        input_mapping=("design_report:d", "project_brief:p"),
        source_priority={"design_report:d": 1, "project_brief:p": 4},
    )
    assert section.source_priority["design_report:d"] == 1
    assert section.source_priority["project_brief:p"] == 4


def test_source_priority_is_frozen():
    section = _make_section(source_priority={"src:field": 1})
    with pytest.raises(dataclasses.FrozenInstanceError):
        section.source_priority = {"src:field": 2}  # type: ignore[misc]


def test_source_priority_accepts_any_tier_count():
    """Priority is just an integer — 2 tiers, 5 tiers, 10 tiers all work."""
    section = _make_section(
        source_priority={
            "a:x": 1,
            "b:x": 2,
            "c:x": 3,
            "d:x": 4,
            "e:x": 5,
        },
    )
    assert len(section.source_priority) == 5
    assert min(section.source_priority.values()) == 1
    assert max(section.source_priority.values()) == 5
