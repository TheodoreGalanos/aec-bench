# ABOUTME: Tests explicit task metadata loading and migration report allocation.
# ABOUTME: Verifies bounded legacy compatibility, missing-policy errors, and stable report output.

import os
import tomllib
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

from aec_bench.contracts.identity import EntityKind, new_entity_id, validate_uuidv7
from aec_bench.tasks import metadata_migration
from aec_bench.tasks.loader import (
    LoadError,
    derive_task_id,
    iter_task_instance_dirs,
    load_legacy_task_definition,
    load_task_catalog,
    load_task_definition,
    parse_task_metadata,
)
from aec_bench.tasks.metadata_migration import apply_task_metadata_migration, generate_task_metadata_migration_report

TASKS_ROOT = Path(__file__).resolve().parents[2] / "tasks"


def _write_task(
    tasks_root: Path,
    *parts: str,
    identity: UUID | None = None,
    key: str | None = None,
    lifecycle: str | None = "active",
    visibility: str | None = "public",
) -> Path:
    task_dir = tasks_root.joinpath(*parts)
    (task_dir / "environment").mkdir(parents=True)
    (task_dir / "tests").mkdir()
    (task_dir / "instruction.md").write_text("Write findings to /workspace/output.jsonl.\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    metadata = ['difficulty = "easy"', 'category = "reasoning"', 'tags = ["test"]']
    if lifecycle is not None:
        metadata.append(f'lifecycle = "{lifecycle}"')
    if visibility is not None:
        metadata.append(f'visibility = "{visibility}"')
    lines = []
    if identity is not None:
        lines.extend(
            [
                "[identity]",
                f'id = "{identity}"',
                f'key = "{key or "/".join(parts)}"',
                "version = 1",
                "",
            ]
        )
    lines.extend(["[metadata]", *metadata, "", "[agent]", "timeout_sec = 600", "", "[environment]", "extensions = []"])
    (task_dir / "task.toml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return task_dir


def test_parse_task_metadata_requires_explicit_policy() -> None:
    task_id = new_entity_id(EntityKind.TASK)
    raw = {
        "identity": {"id": str(task_id), "key": "electrical/voltage-drop", "version": 1},
        "metadata": {"lifecycle": "active", "visibility": "private"},
    }

    metadata = parse_task_metadata(raw)

    assert metadata.identity.id == task_id
    assert metadata.lifecycle.value == "active"
    assert metadata.visibility.value == "private"


def test_parse_task_metadata_rejects_missing_visibility_without_default() -> None:
    task_id = new_entity_id(EntityKind.TASK)

    with pytest.raises(ValueError, match="visibility.*no default"):
        parse_task_metadata(
            {
                "identity": {"id": str(task_id), "key": "electrical/voltage-drop", "version": 1},
                "metadata": {"lifecycle": "active"},
            }
        )


def test_loader_reads_explicit_metadata_and_preserves_identity(tmp_path: Path) -> None:
    task_id = new_entity_id(EntityKind.TASK)
    task_dir = _write_task(tmp_path, "electrical", "voltage-drop", identity=task_id)

    task = load_task_definition(task_dir, tmp_path)

    assert task.identity is not None
    assert task.identity.id == task_id
    assert task.task_id == "electrical/voltage-drop"
    assert task.lifecycle.value == "active"
    assert task.visibility.value == "public"


def test_loader_rejects_explicit_metadata_with_missing_visibility(tmp_path: Path) -> None:
    task_id = new_entity_id(EntityKind.TASK)
    task_dir = _write_task(tmp_path, "electrical", "voltage-drop", identity=task_id, visibility=None)

    with pytest.raises(LoadError, match="visibility.*no default"):
        load_task_definition(task_dir, tmp_path)


def test_loader_uses_named_legacy_reader_without_allocating_identity(tmp_path: Path) -> None:
    task_dir = _write_task(tmp_path, "electrical", "voltage-drop", identity=None, visibility=None, lifecycle=None)

    task = load_legacy_task_definition(task_dir, tmp_path)

    assert task.identity is None
    assert task.lifecycle.value == "proposed"
    assert task.visibility.value == "public"


def test_legacy_reader_rejects_explicit_identity_metadata(tmp_path: Path) -> None:
    task_id = new_entity_id(EntityKind.TASK)
    task_dir = _write_task(tmp_path, "electrical", "voltage-drop", identity=task_id)

    with pytest.raises(LoadError, match="legacy task reader cannot load.*identity"):
        load_legacy_task_definition(task_dir, tmp_path)


def test_loader_does_not_fallback_when_identity_section_is_malformed(tmp_path: Path) -> None:
    task_dir = _write_task(tmp_path, "electrical", "voltage-drop", identity=None)
    (task_dir / "task.toml").write_text(
        '[identity]\nid = "not-a-uuid"\nkey = "electrical/voltage-drop"\nversion = 1\n\n'
        '[metadata]\nlifecycle = "active"\n',
        encoding="utf-8",
    )

    with pytest.raises(LoadError, match="invalid task metadata"):
        load_task_definition(task_dir, tmp_path)


def test_migration_report_flags_malformed_identity_for_review(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _write_task(tasks_root, "electrical", "voltage-drop")
    (task_dir / "task.toml").write_text(
        '[identity]\nid = "not-a-uuid"\nkey = "electrical/voltage-drop"\nversion = 1\n\n'
        '[metadata]\nlifecycle = "active"\nvisibility = "public"\n',
        encoding="utf-8",
    )

    report = generate_task_metadata_migration_report(tasks_root, tmp_path / "report.json")

    assert "repair malformed identity metadata" in report.tasks[0].required_reviewer_decisions[0]


def test_migration_report_allocates_stable_ids_and_does_not_edit_tasks(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_a = _write_task(tasks_root, "electrical", "Voltage-Drop", visibility=None, lifecycle=None)
    task_b = _write_task(tasks_root, "civil", "drainage", visibility="holdout", lifecycle="active")
    before = {path: path.read_bytes() for path in (task_a / "task.toml", task_b / "task.toml")}
    report_path = tmp_path / "migration" / "task-metadata.json"

    first = generate_task_metadata_migration_report(tasks_root, report_path)
    first_bytes = report_path.read_bytes()
    second = generate_task_metadata_migration_report(tasks_root, report_path)

    assert first == second
    assert report_path.read_bytes() == first_bytes
    assert [entry.current_path for entry in first.tasks] == ["civil/drainage", "electrical/Voltage-Drop"]
    assert first.tasks[0].current_inferred_visibility == "holdout"
    assert first.tasks[1].current_inferred_visibility == "unknown"
    assert "classify visibility; no default is permitted" in first.tasks[1].required_reviewer_decisions
    assert all(validate_uuidv7(entry.generated_uuid) == entry.generated_uuid for entry in first.tasks)
    assert all(path.read_bytes() == content for path, content in before.items())


def test_migration_report_preserves_existing_explicit_uuid(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = new_entity_id(EntityKind.TASK)
    _write_task(tasks_root, "electrical", "voltage-drop", identity=task_id)
    report = generate_task_metadata_migration_report(tasks_root, tmp_path / "report.json")

    assert report.tasks[0].generated_uuid == task_id
    assert report.tasks[0].proposed_version == 1


def test_migration_report_rejects_corrupt_existing_allocations(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "electrical", "voltage-drop")
    report_path = tmp_path / "report.json"
    report_path.write_text('{"schema_version": 99, "tasks": []}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported report schema version"):
        generate_task_metadata_migration_report(tasks_root, report_path)


def test_migration_report_rejects_duplicate_proposed_keys(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "electrical", "a-b")
    _write_task(tasks_root, "electrical", "a!b")

    with pytest.raises(ValueError, match="duplicate proposed key.*electrical/a-b"):
        generate_task_metadata_migration_report(tasks_root, tmp_path / "report.json")


def test_migration_report_rejects_duplicate_generated_uuids(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = new_entity_id(EntityKind.TASK)
    _write_task(tasks_root, "electrical", "first")
    _write_task(tasks_root, "electrical", "second")
    report_path = tmp_path / "report.json"
    report_path.write_text(
        '{"schema_version": 1, "tasks": ['
        f'{{"current_path": "electrical/first", "generated_uuid": "{task_id}"}},'
        f'{{"current_path": "electrical/second", "generated_uuid": "{task_id}"}}]}}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate generated UUID.*electrical/first.*electrical/second"):
        generate_task_metadata_migration_report(tasks_root, report_path)


def test_migration_report_rejects_new_duplicate_generated_uuids(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_id = new_entity_id(EntityKind.TASK)
    _write_task(tasks_root, "electrical", "first")
    _write_task(tasks_root, "electrical", "second")

    with patch.object(metadata_migration, "new_entity_id", return_value=task_id):
        with pytest.raises(ValueError, match="duplicate generated UUID.*electrical/first.*electrical/second"):
            generate_task_metadata_migration_report(tasks_root, tmp_path / "report.json")


def test_metadata_migration_write_refuses_inferred_lifecycle(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "electrical", "voltage-drop", lifecycle=None, visibility="public")
    report = generate_task_metadata_migration_report(tasks_root, tmp_path / "report.json")

    with pytest.raises(ValueError, match="reviewer must author.*lifecycle"):
        apply_task_metadata_migration(tasks_root, report)


def test_migration_report_keeps_existing_bytes_when_replacement_fails(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task(tasks_root, "electrical", "voltage-drop")
    report_path = tmp_path / "report.json"
    generate_task_metadata_migration_report(tasks_root, report_path)
    original_bytes = report_path.read_bytes()

    with patch.object(os, "replace", side_effect=OSError("replacement failed")):
        with pytest.raises(OSError, match="replacement failed"):
            generate_task_metadata_migration_report(tasks_root, report_path)

    assert report_path.read_bytes() == original_bytes
    assert list(report_path.parent.glob(f".{report_path.name}.*.tmp")) == []


def test_repository_tasks_have_complete_explicit_metadata_and_strict_loader_success(tmp_path: Path) -> None:
    report_path = tmp_path / "task-metadata-report.json"

    first_report = generate_task_metadata_migration_report(TASKS_ROOT, report_path)
    first_bytes = report_path.read_bytes()
    second_report = generate_task_metadata_migration_report(TASKS_ROOT, report_path)
    catalogue = load_task_catalog(TASKS_ROOT)

    assert first_report == second_report
    assert report_path.read_bytes() == first_bytes
    assert len(first_report.tasks) == len(iter_task_instance_dirs(TASKS_ROOT))
    assert len(catalogue) == len(first_report.tasks)
    assert len({entry.generated_uuid for entry in first_report.tasks}) == len(first_report.tasks)
    assert len({entry.proposed_key for entry in first_report.tasks}) == len(first_report.tasks)

    entries_by_path = {entry.current_path: entry for entry in first_report.tasks}
    for task_dir in iter_task_instance_dirs(TASKS_ROOT):
        current_path = derive_task_id(task_dir, TASKS_ROOT)
        entry = entries_by_path[current_path]
        task = catalogue[entry.proposed_key]
        assert task.identity is not None
        assert str(task.identity.id) == str(entry.generated_uuid)
        assert str(task.identity.key) == entry.proposed_key
        assert task.task_id == entry.proposed_key
        assert task.identity.version == 1
        assert task.lifecycle.value == "proposed"
        assert task.visibility.value == "public"

        raw_toml = tomllib.loads((task_dir / "task.toml").read_text(encoding="utf-8"))
        assert raw_toml.get("version") in {None, "1.0"}
        assert raw_toml["identity"] == {
            "id": str(entry.generated_uuid),
            "key": entry.proposed_key,
            "version": 1,
        }
        assert raw_toml["metadata"]["lifecycle"] == "proposed"
        assert raw_toml["metadata"]["visibility"] == "public"
