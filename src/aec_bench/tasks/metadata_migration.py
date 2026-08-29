# ABOUTME: Builds a stable, reviewable report for task metadata migration.
# ABOUTME: Allocates UUIDv7 values once without modifying maintained task packages.

from __future__ import annotations

import json
import os
import re
import tempfile
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from aec_bench.contracts.identity import EntityIdentity, EntityKey, EntityKind, new_entity_id, validate_uuidv7
from aec_bench.contracts.task_definition import Lifecycle, Visibility
from aec_bench.tasks.loader import iter_task_instance_dirs

REPORT_SCHEMA_VERSION = 1
_KEY_COMPONENT_RE = re.compile(r"[^a-z0-9_-]+")


class MigrationReportError(ValueError):
    """Raised when a previous migration report cannot provide stable allocations."""


@dataclass(frozen=True, slots=True)
class TaskMetadataMigrationEntry:
    current_path: str
    proposed_key: str
    generated_uuid: UUID
    proposed_version: int
    current_inferred_lifecycle: str
    current_inferred_visibility: str
    required_reviewer_decisions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["generated_uuid"] = str(self.generated_uuid)
        value["required_reviewer_decisions"] = list(self.required_reviewer_decisions)
        return value


@dataclass(frozen=True, slots=True)
class TaskMetadataMigrationReport:
    tasks: tuple[TaskMetadataMigrationEntry, ...]
    schema_version: int = REPORT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tasks": [entry.to_dict() for entry in self.tasks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def generate_task_metadata_migration_report(
    tasks_root: Path,
    output_path: Path,
) -> TaskMetadataMigrationReport:
    """Write and return a deterministic task metadata migration report.

    Existing report entries supply allocations for unchanged task paths. New
    paths receive one UUIDv7, which is then retained in the report on later
    reads. This function never edits a task's ``task.toml``.
    """

    allocations = _read_existing_allocations(output_path)
    entries = tuple(
        _build_entry(instance_dir, tasks_root, allocations) for instance_dir in iter_task_instance_dirs(tasks_root)
    )
    report = TaskMetadataMigrationReport(tasks=entries)
    _validate_report_entries(report.tasks)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _write_report_atomically(output_path, report.to_json())
    return report


def _validate_report_entries(entries: tuple[TaskMetadataMigrationEntry, ...]) -> None:
    paths_by_key: dict[str, str] = {}
    paths_by_uuid: dict[UUID, str] = {}
    for entry in entries:
        previous_path = paths_by_key.get(entry.proposed_key)
        if previous_path is not None:
            raise MigrationReportError(
                f"duplicate proposed key {entry.proposed_key!r} for task paths {previous_path!r} and "
                f"{entry.current_path!r}"
            )
        paths_by_key[entry.proposed_key] = entry.current_path

        previous_path = paths_by_uuid.get(entry.generated_uuid)
        if previous_path is not None:
            raise MigrationReportError(
                f"duplicate generated UUID {entry.generated_uuid} for task paths {previous_path!r} and "
                f"{entry.current_path!r}"
            )
        paths_by_uuid[entry.generated_uuid] = entry.current_path


def _write_report_atomically(output_path: Path, content: str) -> None:
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            temporary_file.write(content)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, output_path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _build_entry(
    instance_dir: Path,
    tasks_root: Path,
    allocations: dict[str, UUID],
) -> TaskMetadataMigrationEntry:
    current_path = instance_dir.relative_to(tasks_root).as_posix()
    raw_toml = _read_toml_for_report(instance_dir / "task.toml")
    metadata = raw_toml.get("metadata")
    metadata_mapping = metadata if isinstance(metadata, dict) else {}
    identity = _read_identity(raw_toml)
    proposed_key = _proposed_key(current_path)

    if identity is not None:
        generated_uuid = identity.id
    else:
        allocated_uuid = allocations.get(current_path)
        generated_uuid = allocated_uuid if allocated_uuid is not None else new_entity_id(EntityKind.TASK)
    proposed_version = identity.version if identity is not None else 1
    lifecycle = _inferred_lifecycle(metadata_mapping)
    visibility = _inferred_visibility(metadata_mapping)
    decisions = _reviewer_decisions(
        raw_toml=raw_toml,
        identity=identity,
        current_path=current_path,
        proposed_key=proposed_key,
        visibility=visibility,
    )
    return TaskMetadataMigrationEntry(
        current_path=current_path,
        proposed_key=proposed_key,
        generated_uuid=generated_uuid,
        proposed_version=proposed_version,
        current_inferred_lifecycle=lifecycle,
        current_inferred_visibility=visibility,
        required_reviewer_decisions=decisions,
    )


def _read_existing_allocations(output_path: Path) -> dict[str, UUID]:
    if not output_path.exists():
        return {}
    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        if payload["schema_version"] != REPORT_SCHEMA_VERSION:
            raise ValueError(f"unsupported report schema version: {payload['schema_version']}")
        entries = payload["tasks"]
        if not isinstance(entries, list):
            raise TypeError("tasks must be a list")
        allocations: dict[str, UUID] = {}
        paths_by_uuid: dict[UUID, str] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise TypeError("each task entry must be an object")
            current_path = entry["current_path"]
            generated_uuid = entry["generated_uuid"]
            if not isinstance(current_path, str) or not isinstance(generated_uuid, str):
                raise TypeError("task allocation fields must be strings")
            if current_path in allocations:
                raise ValueError(f"duplicate task allocation: {current_path}")
            parsed_uuid = validate_uuidv7(generated_uuid)
            previous_path = paths_by_uuid.get(parsed_uuid)
            if previous_path is not None:
                raise ValueError(
                    f"duplicate generated UUID {parsed_uuid} for task paths {previous_path!r} and {current_path!r}"
                )
            allocations[current_path] = parsed_uuid
            paths_by_uuid[parsed_uuid] = current_path
        return allocations
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        raise MigrationReportError(f"cannot read stable task UUID allocations from {output_path}: {error}") from error


def _read_toml_for_report(task_toml_path: Path) -> dict[str, Any]:
    try:
        raw = tomllib.loads(task_toml_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        return {"_report_error": f"cannot read task metadata: {error}"}
    return raw


def _read_identity(raw_toml: dict[str, Any]) -> EntityIdentity | None:
    identity = raw_toml.get("identity")
    if not isinstance(identity, dict):
        return None
    try:
        return EntityIdentity.model_validate(identity)
    except (TypeError, ValueError):
        return None


def _proposed_key(current_path: str) -> str:
    components: list[str] = []
    for component in current_path.split("/"):
        normalised = _KEY_COMPONENT_RE.sub("-", component.lower()).strip("-_")
        if not normalised or not normalised[0].isalnum() or not normalised[0].isascii():
            normalised = f"task-{normalised}" if normalised else "task"
        components.append(normalised)
    return str(EntityKey("/".join(components)))


def _inferred_lifecycle(metadata: dict[str, Any]) -> str:
    value = metadata.get("lifecycle")
    if isinstance(value, str):
        try:
            return Lifecycle(value).value
        except ValueError:
            pass
    return Lifecycle.PROPOSED.value


def _inferred_visibility(metadata: dict[str, Any]) -> str:
    value = metadata.get("visibility")
    if isinstance(value, str):
        try:
            return Visibility(value).value
        except ValueError:
            pass
    return "unknown"


def _reviewer_decisions(
    *,
    raw_toml: dict[str, Any],
    identity: EntityIdentity | None,
    current_path: str,
    proposed_key: str,
    visibility: str,
) -> tuple[str, ...]:
    decisions: list[str] = []
    if identity is None:
        if "_report_error" in raw_toml:
            decisions.append("resolve task metadata read error")
        elif "identity" in raw_toml:
            decisions.append("repair malformed identity metadata and approve generated UUIDv7")
        else:
            decisions.append("approve generated UUIDv7 and proposed key")
    if proposed_key != current_path:
        decisions.append("approve canonical key normalisation")
    metadata = raw_toml.get("metadata")
    metadata_mapping = metadata if isinstance(metadata, dict) else {}
    if metadata_mapping.get("lifecycle") not in {
        Lifecycle.PROPOSED.value,
        Lifecycle.ACTIVE.value,
        Lifecycle.DEPRECATED.value,
        Lifecycle.RETIRED.value,
    }:
        decisions.append("confirm lifecycle; compatibility inference is proposed")
    if visibility == "unknown":
        decisions.append("classify visibility; no default is permitted")
    if not decisions:
        decisions.append("confirm metadata mapping")
    return tuple(decisions)


__all__ = (
    "MigrationReportError",
    "REPORT_SCHEMA_VERSION",
    "TaskMetadataMigrationEntry",
    "TaskMetadataMigrationReport",
    "generate_task_metadata_migration_report",
)
