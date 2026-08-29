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

from aec_bench.contracts.identity import EntityIdentity, EntityKind, new_entity_id, validate_uuidv7
from aec_bench.contracts.task_definition import Lifecycle, Visibility
from aec_bench.tasks.loader import canonical_task_key, iter_task_instance_dirs

REPORT_SCHEMA_VERSION = 1


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


def apply_task_metadata_migration(tasks_root: Path, report: TaskMetadataMigrationReport) -> tuple[str, ...]:
    """Write reviewed identity and policy values to the listed task packages."""

    changes = _task_metadata_changes(tasks_root, report, require_policy=True)
    for entry, after in changes:
        task_toml = tasks_root / entry.current_path / "task.toml"
        task_toml.write_text(after, encoding="utf-8")
    return tuple(entry.current_path for entry, _after in changes)


def planned_task_metadata_changes(tasks_root: Path, report: TaskMetadataMigrationReport) -> tuple[str, ...]:
    """Return task paths that would change when the reviewed report is applied."""

    return tuple(
        entry.current_path for entry, _after in _task_metadata_changes(tasks_root, report, require_policy=False)
    )


def _task_metadata_changes(
    tasks_root: Path,
    report: TaskMetadataMigrationReport,
    *,
    require_policy: bool,
) -> list[tuple[TaskMetadataMigrationEntry, str]]:
    changes: list[tuple[TaskMetadataMigrationEntry, str]] = []
    for entry in report.tasks:
        task_path = tasks_root / entry.current_path
        task_toml = task_path / "task.toml"
        if not task_toml.is_file():
            raise MigrationReportError(f"cannot write {entry.current_path}: task.toml is missing")
        before = task_toml.read_text(encoding="utf-8")
        try:
            raw_toml = tomllib.loads(before)
        except tomllib.TOMLDecodeError as error:
            raise MigrationReportError(
                f"cannot write {entry.current_path}: task.toml is not valid TOML: {error}"
            ) from error
        metadata = raw_toml.get("metadata")
        if not isinstance(metadata, dict):
            if not require_policy:
                continue
            raise MigrationReportError(
                f"cannot write {entry.current_path}: reviewer must author [metadata].lifecycle and visibility"
            )
        authored_lifecycle = metadata.get("lifecycle")
        authored_visibility = metadata.get("visibility")
        if not require_policy and (
            not isinstance(authored_lifecycle, str)
            or authored_lifecycle not in {item.value for item in Lifecycle}
            or not isinstance(authored_visibility, str)
            or authored_visibility not in {item.value for item in Visibility}
        ):
            continue
        if entry.current_inferred_visibility not in {item.value for item in Visibility}:
            raise MigrationReportError(
                f"cannot write {entry.current_path}: visibility is not classified as public, private, or holdout"
            )
        if entry.current_inferred_lifecycle not in {item.value for item in Lifecycle}:
            raise MigrationReportError(f"cannot write {entry.current_path}: lifecycle is not supported")
        if not isinstance(authored_lifecycle, str) or authored_lifecycle not in {item.value for item in Lifecycle}:
            raise MigrationReportError(
                f"cannot write {entry.current_path}: reviewer must author a supported [metadata].lifecycle"
            )
        if not isinstance(authored_visibility, str) or authored_visibility not in {item.value for item in Visibility}:
            raise MigrationReportError(
                f"cannot write {entry.current_path}: reviewer must author public, private, or holdout visibility"
            )
        if (
            authored_lifecycle != entry.current_inferred_lifecycle
            or authored_visibility != entry.current_inferred_visibility
        ):
            raise MigrationReportError(
                f"cannot write {entry.current_path}: reviewed report policy does not match authored metadata"
            )
        after = _with_explicit_metadata(
            before,
            identity={
                "id": str(entry.generated_uuid),
                "key": entry.proposed_key,
                "version": entry.proposed_version,
            },
            lifecycle=authored_lifecycle,
            visibility=authored_visibility,
        )
        if after != before:
            changes.append((entry, after))
    return changes


def _with_explicit_metadata(
    text: str,
    *,
    identity: dict[str, str | int],
    lifecycle: str,
    visibility: str,
) -> str:
    """Add or replace the small explicit metadata sections without reformatting other TOML."""

    lines = text.splitlines()
    first_section = next((index for index, line in enumerate(lines) if line.lstrip().startswith("[")), len(lines))
    identity_block = [
        "[identity]",
        f'id = "{identity["id"]}"',
        f'key = "{identity["key"]}"',
        f"version = {identity['version']}",
        "",
    ]
    if first_section == len(lines):
        lines.extend(identity_block)
    else:
        identity_start = next((index for index, line in enumerate(lines) if line.strip() == "[identity]"), None)
        if identity_start is None:
            lines[first_section:first_section] = identity_block
        else:
            identity_end = next(
                (index for index in range(identity_start + 1, len(lines)) if lines[index].lstrip().startswith("[")),
                len(lines),
            )
            lines[identity_start:identity_end] = identity_block

    metadata_start = next((index for index, line in enumerate(lines) if line.strip() == "[metadata]"), None)
    if metadata_start is None:
        if lines and lines[-1] != "":
            lines.append("")
        lines.extend(["[metadata]", f'lifecycle = "{lifecycle}"', f'visibility = "{visibility}"'])
    else:
        metadata_end = next(
            (index for index in range(metadata_start + 1, len(lines)) if lines[index].lstrip().startswith("[")),
            len(lines),
        )
        section = lines[metadata_start + 1 : metadata_end]
        section = _replace_toml_string(section, "lifecycle", lifecycle)
        section = _replace_toml_string(section, "visibility", visibility)
        lines[metadata_start + 1 : metadata_end] = section
    return "\n".join(lines) + "\n"


def _replace_toml_string(lines: list[str], key: str, value: str) -> list[str]:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=")
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = f'{key} = "{value}"'
            return lines
    lines.insert(0, f'{key} = "{value}"')
    return lines


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
    proposed_key = str(canonical_task_key(current_path))

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
    "apply_task_metadata_migration",
    "generate_task_metadata_migration_report",
    "planned_task_metadata_changes",
)
