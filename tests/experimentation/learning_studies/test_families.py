# ABOUTME: Tests TOML learning-family loading and exact task resolution.
# ABOUTME: Proves real overlays remain host-selected and do not modify ordinary task definitions.

from pathlib import Path

import pytest

from aec_bench.contracts.learning_study import ExperienceRole
from aec_bench.experimentation.learning_studies.families import (
    load_learning_family,
    relation_to_experience_specs,
    resolve_learning_family,
    resolve_learning_relation,
)
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_FAMILY_ROOT = _REPOSITORY_ROOT / "docs" / "examples" / "learning-studies" / "families"


def _resolve_task(task_id: str):  # noqa: ANN202
    instance_dir = _TASKS_ROOT / task_id
    return resolve_instance_paths(load_task_definition(instance_dir, _TASKS_ROOT), instance_dir)


@pytest.mark.parametrize("filename", ("heat-load-single-room.toml", "heat-load-office-audit.toml"))
def test_real_learning_families_resolve_exact_existing_tasks(filename: str) -> None:
    family = load_learning_family(_FAMILY_ROOT / filename)

    resolved = resolve_learning_family(family, _resolve_task)

    assert len(resolved.members) == 2
    assert all(
        member.task.task.task_id == member.task.instance_dir.relative_to(_TASKS_ROOT).as_posix()
        for member in resolved.members
    )
    assert all((_REPOSITORY_ROOT / path).is_file() for path in family.source_task_paths)


def test_resolved_transfer_relation_produces_acquisition_and_protected_probe() -> None:
    family = resolve_learning_family(load_learning_family(_FAMILY_ROOT / "heat-load-single-room.toml"), _resolve_task)
    relation = resolve_learning_relation(family, "brisbane-office-to-sydney-classroom")

    experiences = relation_to_experience_specs(relation)

    assert [item.role for item in experiences] == [ExperienceRole.ACQUISITION, ExperienceRole.PROBE]
    assert [item.task_id for item in experiences] == [
        "mechanical/heat-load/single-room-office-L3/brisbane-office-85m2",
        "mechanical/heat-load/single-room-office-L3/sydney-classroom-120m2",
    ]


def test_family_overlay_does_not_change_task_loading() -> None:
    task_id = "mechanical/heat-load/single-room-office-L3/brisbane-office-85m2"
    before = _resolve_task(task_id).task

    load_learning_family(_FAMILY_ROOT / "heat-load-single-room.toml")

    assert _resolve_task(task_id).task == before


def test_malformed_toml_and_unresolved_member_name_the_file_or_member(tmp_path: Path) -> None:
    invalid = tmp_path / "family.toml"
    invalid.write_text("family_id = [\n", encoding="utf-8")
    with pytest.raises(ValueError, match="could not load learning family"):
        load_learning_family(invalid)

    family = load_learning_family(_FAMILY_ROOT / "heat-load-single-room.toml")
    with pytest.raises(ValueError, match="brisbane-office-acquisition"):
        resolve_learning_family(family, lambda _task_id: (_ for _ in ()).throw(KeyError("missing")))
