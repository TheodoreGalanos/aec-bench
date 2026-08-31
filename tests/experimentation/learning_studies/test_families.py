# ABOUTME: Tests TOML learning-family loading and exact task resolution.
# ABOUTME: Proves real overlays remain host-selected and do not modify ordinary task definitions.

from pathlib import Path

import pytest

from aec_bench.experimentation.learning_studies.families import load_learning_family
from aec_bench.experimentation.learning_studies.protocol_collection import BUILTIN_LEARNING_STUDY_PROTOCOLS
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition
from tests.experimentation.learning_studies.support import resolve_learning_task_dir

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_PROTOCOL_ROOT = BUILTIN_LEARNING_STUDY_PROTOCOLS


def _resolve_task(task_id: str):  # noqa: ANN202
    instance_dir = resolve_learning_task_dir(_TASKS_ROOT, task_id)
    return resolve_instance_paths(load_task_definition(instance_dir, _TASKS_ROOT), instance_dir)


@pytest.mark.parametrize(
    ("protocol_id", "member_count"),
    (
        ("a01-artifact-structural-transfer", 2),
        ("a02-artifact-applicability-boundary", 2),
        ("a03-artifact-retention-interference", 4),
        ("a04-artifact-composition", 3),
    ),
)
def test_real_learning_families_name_exact_existing_tasks(protocol_id: str, member_count: int) -> None:
    family = load_learning_family(_PROTOCOL_ROOT / protocol_id / "family.toml")

    resolved = tuple(_resolve_task(member.task_id) for member in family.members)

    assert len(resolved) == member_count
    assert all(
        task.task.task_id == member.task_id.lower() for task, member in zip(resolved, family.members, strict=True)
    )


def test_transfer_relation_names_non_probe_source_and_protected_probe() -> None:
    family = load_learning_family(_PROTOCOL_ROOT / "a01-artifact-structural-transfer" / "family.toml")
    relation = next(item for item in family.relations if item.relation_id == "brisbane-office-to-sydney-classroom")
    members = {item.member_id: item for item in family.members}

    assert [members[item].task_id for item in relation.source_member_ids] == [
        "mechanical/heat-load/single-room-office-l3/brisbane-office-85m2",
    ]
    assert not members[relation.source_member_ids[0]].probe_only
    assert members[relation.target_member_id].probe_only
    assert members[relation.target_member_id].task_id == (
        "mechanical/heat-load/single-room-office-l3/sydney-classroom-120m2"
    )


def test_family_overlay_does_not_change_task_loading() -> None:
    task_id = "mechanical/heat-load/single-room-office-l3/brisbane-office-85m2"
    before = _resolve_task(task_id).task

    load_learning_family(_PROTOCOL_ROOT / "a01-artifact-structural-transfer" / "family.toml")

    assert _resolve_task(task_id).task == before


def test_malformed_toml_names_the_file(tmp_path: Path) -> None:
    invalid = tmp_path / "family.toml"
    invalid.write_text("family_id = [\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not load learning family"):
        load_learning_family(invalid)
