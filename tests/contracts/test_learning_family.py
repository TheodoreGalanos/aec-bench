# ABOUTME: Tests strict learning-family contracts and semantic dimension validation.
# ABOUTME: Proves overlays describe authored task relations without changing adaptation contracts.

from copy import deepcopy

import pytest
from pydantic import ValidationError

from aec_bench.contracts.learning_family import LearningFamilySpec


def _family_data() -> dict[str, object]:
    return {
        "family_id": "calculation-family",
        "title": "Calculation family",
        "description": "A small valid family",
        "dimensions": (
            {"dimension_id": "method", "kind": "causal", "description": "Governing method"},
            {"dimension_id": "value_band", "kind": "parameter", "description": "Input band"},
        ),
        "members": (
            {
                "member_id": "a",
                "task_id": "civil/example/a",
                "dimension_values": {"method": "m", "value_band": "small"},
            },
            {
                "member_id": "b",
                "task_id": "civil/example/b",
                "probe_only": True,
                "dimension_values": {"method": "m", "value_band": "large"},
            },
        ),
        "relations": (
            {
                "relation_id": "a-to-b",
                "purpose": "transfer",
                "source_member_ids": ("a",),
                "target_member_id": "b",
                "invariant_dimensions": ("method",),
                "invariant_claims": ("Method m remains valid.",),
                "changed_dimensions": ("value_band",),
                "rationale": "Tests a parameter change.",
            },
        ),
    }


def test_learning_family_round_trips_with_frozen_nested_values() -> None:
    family = LearningFamilySpec.model_validate(_family_data())

    restored = LearningFamilySpec.model_validate_json(family.model_dump_json(round_trip=True))

    assert restored == family
    with pytest.raises(TypeError, match="immutable"):
        restored.members[0].dimension_values["method"] = "other"


@pytest.mark.parametrize(
    ("edit", "message"),
    (
        (
            lambda data: data["members"][1]["dimension_values"].update(value_band="small"),
            "changed dimension does not differ",
        ),
        (
            lambda data: data["members"][1]["dimension_values"].update(method="n"),
            "invariant dimension differs",
        ),
        (
            lambda data: data["relations"][0].update(changed_dimensions=("unknown",)),
            "unknown dimensions",
        ),
        (
            lambda data: data["members"][1].update(task_id="civil/example/a"),
            "member task ids must be unique",
        ),
    ),
)
def test_learning_family_rejects_inconsistent_authored_dimensions(edit, message: str) -> None:  # noqa: ANN001
    data = deepcopy(_family_data())
    edit(data)

    with pytest.raises(ValidationError, match=message):
        LearningFamilySpec.model_validate(data)


def test_learning_family_rejects_unknown_fields() -> None:
    data = _family_data()
    data["registry_id"] = "not-supported"

    with pytest.raises(ValidationError, match="registry_id"):
        LearningFamilySpec.model_validate(data)
