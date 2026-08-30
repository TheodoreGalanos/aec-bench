# ABOUTME: Owns the optional generated-task replay sidecar and replay command behavior.
# ABOUTME: Keeps source identity and sampling inputs outside runnable task packages.

from __future__ import annotations

import io
import json
import shutil
import subprocess
import tarfile
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import Field, NonNegativeInt, field_validator, model_validator

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.identity import validate_uuidv7
from aec_bench.contracts.task_definition import Lifecycle, Visibility
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.templates.contracts import ToolMode
from aec_bench.templates.registry import LoadedTemplate, load_template

GENERATION_MANIFEST_FILENAME = "generation-manifest.json"
GENERATION_CONFIG_FILENAME = "generation-config.json"
GENERATION_ARTIFACTS_DIRNAME = ".generation-artifacts"
TEMPLATE_SOURCE_MEDIA_TYPE = "application/vnd.aec-bench.template-sources+tar"
_IGNORED_SOURCE_NAMES = frozenset({".DS_Store", "__pycache__"})


def _validate_replay_relative_path(value: str) -> str:
    segments = value.split("/")
    if (
        PurePosixPath(value).is_absolute()
        or "\\" in value
        or any(segment in {"", ".", ".."} for segment in segments)
        or segments[0].endswith(":")
    ):
        raise ValueError("generation replay path must be a portable relative path")
    return value


class GitTemplateSource(FrozenStrictModel):
    """One repository revision that owns all templates in a generated set."""

    kind: Literal["git"] = "git"
    revision: NonEmptyStr
    template_root: NonEmptyStr

    @field_validator("template_root")
    @classmethod
    def validate_template_root(cls, value: str) -> str:
        return _validate_replay_relative_path(value)

    @field_validator("revision")
    @classmethod
    def validate_revision(cls, value: str) -> str:
        if len(value) != 40 or any(character not in "0123456789abcdef" for character in value):
            raise ValueError("Git template source revision must be a lowercase 40-character commit")
        return value


class ArtifactTemplateSource(FrozenStrictModel):
    """One exact archive containing all external templates in a generated set."""

    kind: Literal["artifact"] = "artifact"
    artifact: ArtifactRef

    @model_validator(mode="after")
    def validate_artifact_media_type(self) -> Self:
        if self.artifact.media_type != TEMPLATE_SOURCE_MEDIA_TYPE:
            raise ValueError(f"template source artifact media type must be {TEMPLATE_SOURCE_MEDIA_TYPE}")
        return self


type TemplateSource = Annotated[GitTemplateSource | ArtifactTemplateSource, Field(discriminator="kind")]


class GenerationInstance(FrozenStrictModel):
    """Replay inputs for one generated runtime task."""

    task_id: NonEmptyStr
    task_kind: Literal["artifact"] = "artifact"
    template_id: NonEmptyStr
    seed: int
    instance_index: NonNegativeInt
    difficulty: NonEmptyStr
    tool_mode: ToolMode
    task_lifecycle: Lifecycle
    task_visibility: Visibility
    task_identity_id: UUID

    @field_validator("task_id", "template_id")
    @classmethod
    def validate_relative_identifiers(cls, value: str) -> str:
        return _validate_replay_relative_path(value)

    @field_validator("task_identity_id")
    @classmethod
    def validate_task_identity_id(cls, value: UUID) -> UUID:
        return validate_uuidv7(value)


class GenerationManifest(FrozenStrictModel):
    """Optional, non-runtime replay data for one generated task set."""

    schema_version: Literal[1] = 1
    suite_id: NonEmptyStr
    source: TemplateSource
    config_ref: NonEmptyStr
    instances: tuple[GenerationInstance, ...] = Field(min_length=1)

    @field_validator("config_ref")
    @classmethod
    def validate_config_ref(cls, value: str) -> str:
        return _validate_replay_relative_path(value)

    @model_validator(mode="after")
    def validate_unique_instances(self) -> Self:
        task_ids = tuple(instance.task_id for instance in self.instances)
        if len(task_ids) != len(set(task_ids)):
            raise ValueError("generation manifest task IDs must be unique")
        task_paths = tuple(PurePosixPath(task_id) for task_id in task_ids)
        for index, path in enumerate(task_paths):
            if path.parts[0] == GENERATION_ARTIFACTS_DIRNAME:
                raise ValueError("generation manifest task IDs cannot use replay artifact storage")
            for other in task_paths[index + 1 :]:
                if path.is_relative_to(other) or other.is_relative_to(path):
                    raise ValueError("generation manifest task IDs cannot overlap")

        config_path = PurePosixPath(self.config_ref)
        if self.config_ref == GENERATION_MANIFEST_FILENAME or config_path.parts[0] == GENERATION_ARTIFACTS_DIRNAME:
            raise ValueError("generation config reference conflicts with replay-owned storage")
        config_overlaps_task = any(
            config_path.is_relative_to(task_path) or task_path.is_relative_to(config_path) for task_path in task_paths
        )
        if config_overlaps_task:
            raise ValueError("generation config reference cannot overlap a runtime task")
        return self


@dataclass(frozen=True, slots=True)
class PreparedTemplateSource:
    """One source reference and the stable ID assigned to each loaded template."""

    source: TemplateSource
    template_ids: dict[Path, str]


@dataclass(frozen=True, slots=True)
class ReplayResult:
    """Comparison result returned after a replay regeneration."""

    output_dir: Path
    runtime_differences: tuple[str, ...]
    replay_metadata_differences: tuple[str, ...]

    @property
    def runtime_matches(self) -> bool:
        return not self.runtime_differences


def prepare_template_source(templates: Sequence[LoadedTemplate], output_dir: Path) -> PreparedTemplateSource:
    """Create one shared Git or artifact source reference for loaded templates."""
    if not templates:
        raise ValueError("generation requires at least one template")
    resolved_templates = tuple(dict.fromkeys(template.path.resolve() for template in templates))
    builtin_root = _builtin_template_root()
    if all(path.is_relative_to(builtin_root) for path in resolved_templates) and _git_templates_are_clean(
        templates, builtin_root
    ):
        return _prepare_git_source(templates, builtin_root)
    return _prepare_artifact_source(templates, output_dir)


def write_generation_config(
    output_dir: Path,
    payload: dict[str, Any],
    *,
    config_ref: str = GENERATION_CONFIG_FILENAME,
) -> str:
    """Write deterministic, path-free generation settings referenced by the sidecar."""
    config_path = _confined_relative_path(output_dir, _validate_replay_relative_path(config_ref))
    if config_path.exists():
        raise FileExistsError(f"refusing to overwrite generation replay config: {config_path}")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return config_ref


def require_available_sidecar_paths(output_dir: Path) -> None:
    """Fail before generation when an output already owns replay sidecars."""
    for filename in (GENERATION_MANIFEST_FILENAME, GENERATION_CONFIG_FILENAME):
        path = output_dir / filename
        if path.exists():
            raise FileExistsError(f"refusing to overwrite generation replay file: {path}")


def write_generation_manifest(output_dir: Path, manifest: GenerationManifest) -> Path:
    """Write one canonical replay sidecar outside all runtime task directories."""
    path = output_dir / GENERATION_MANIFEST_FILENAME
    if path.exists():
        raise FileExistsError(f"refusing to overwrite generation replay sidecar: {path}")
    path.write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def load_generation_manifest(path: Path) -> GenerationManifest:
    """Load and validate one replay sidecar without affecting task loading."""
    return GenerationManifest.model_validate_json(path.read_text(encoding="utf-8"))


def replay_generation(manifest_path: Path, output_dir: Path, *, overwrite: bool = False) -> ReplayResult:
    """Regenerate tasks from one sidecar and compare their runtime files."""
    source_manifest_path = manifest_path.resolve()
    manifest = load_generation_manifest(source_manifest_path)
    original_root = source_manifest_path.parent
    replay_root = output_dir.resolve()
    _prepare_replay_output(original_root, replay_root, overwrite=overwrite)

    config_source = _confined_relative_path(original_root, manifest.config_ref)
    if not config_source.is_file():
        raise FileNotFoundError(f"generation config not found: {config_source}")
    config_bytes = config_source.read_bytes()

    with tempfile.TemporaryDirectory(prefix="aec-bench-generation-replay-") as temporary:
        template_root = _resolve_template_source(manifest.source, original_root, Path(temporary))
        for record in manifest.instances:
            template = load_template(_confined_relative_path(template_root, record.template_id))
            sampled = sample_instance(
                template=template,
                difficulty_name=record.difficulty,
                seed=record.seed,
                instance_index=record.instance_index,
            )
            generated_path = scaffold_task_instance(
                template=template,
                instance=sampled,
                output_dir=replay_root,
                tool_mode_override=record.tool_mode.value,
                task_lifecycle=record.task_lifecycle,
                task_visibility=record.task_visibility,
                task_identity_id=record.task_identity_id,
            )
            actual_task_id = generated_path.relative_to(replay_root).as_posix()
            if actual_task_id != record.task_id:
                raise ValueError(
                    f"replayed task path {actual_task_id!r} does not match recorded task ID {record.task_id!r}"
                )

    replay_config = _confined_relative_path(replay_root, manifest.config_ref)
    replay_config.parent.mkdir(parents=True, exist_ok=True)
    replay_config.write_bytes(config_bytes)
    replay_manifest = manifest
    if isinstance(manifest.source, ArtifactTemplateSource):
        source_repository = ArtifactRepository(original_root / GENERATION_ARTIFACTS_DIRNAME)
        source_bytes = source_repository.read_bytes(manifest.source.artifact)
        replay_artifact = ArtifactRepository(replay_root / GENERATION_ARTIFACTS_DIRNAME).publish_bytes(
            data=source_bytes,
            media_type=TEMPLATE_SOURCE_MEDIA_TYPE,
        )
        replay_manifest = manifest.model_copy(
            update={"source": ArtifactTemplateSource(artifact=replay_artifact)},
        )
    write_generation_manifest(replay_root, replay_manifest)

    runtime_differences = _compare_runtime_tasks(original_root, replay_root, manifest.instances)
    replay_metadata_differences = _compare_replay_metadata(original_root, replay_root, manifest.config_ref)
    return ReplayResult(
        output_dir=replay_root,
        runtime_differences=runtime_differences,
        replay_metadata_differences=replay_metadata_differences,
    )


def _prepare_git_source(templates: Sequence[LoadedTemplate], builtin_root: Path) -> PreparedTemplateSource:
    repository_root = Path(_git_output(builtin_root, "rev-parse", "--show-toplevel"))
    revision = _git_output(repository_root, "rev-parse", "HEAD")
    template_root = builtin_root.relative_to(repository_root).as_posix()
    template_ids = {
        template.path.resolve(): template.path.resolve().relative_to(builtin_root).as_posix() for template in templates
    }
    return PreparedTemplateSource(
        source=GitTemplateSource(revision=revision, template_root=template_root),
        template_ids=template_ids,
    )


def _git_templates_are_clean(templates: Sequence[LoadedTemplate], builtin_root: Path) -> bool:
    try:
        repository_root = Path(_git_output(builtin_root, "rev-parse", "--show-toplevel"))
        selected_paths = sorted(
            {template.path.resolve().relative_to(repository_root).as_posix() for template in templates}
        )
        _git_output(repository_root, "ls-files", "--error-unmatch", "--", *selected_paths)
        status = _git_output(
            repository_root,
            "status",
            "--porcelain",
            "--untracked-files=all",
            "--",
            *selected_paths,
        )
    except (OSError, ValueError):
        return False
    return not status


def _prepare_artifact_source(templates: Sequence[LoadedTemplate], output_dir: Path) -> PreparedTemplateSource:
    template_ids = _external_template_ids(templates)
    archive = _build_template_archive(templates, template_ids)
    artifact = ArtifactRepository(output_dir / GENERATION_ARTIFACTS_DIRNAME).publish_bytes(
        data=archive,
        media_type=TEMPLATE_SOURCE_MEDIA_TYPE,
    )
    return PreparedTemplateSource(source=ArtifactTemplateSource(artifact=artifact), template_ids=template_ids)


def _external_template_ids(templates: Sequence[LoadedTemplate]) -> dict[Path, str]:
    builtin_root = _builtin_template_root()
    result: dict[Path, str] = {}
    used: set[str] = set()
    for template in templates:
        path = template.path.resolve()
        if path.is_relative_to(builtin_root):
            template_id = path.relative_to(builtin_root).as_posix()
        else:
            template_id = f"{template.config.meta.discipline}/{path.name}"
        if template_id in used:
            raise ValueError(f"template source ID is not unique: {template_id}")
        used.add(template_id)
        result[path] = template_id
    return result


def _build_template_archive(templates: Sequence[LoadedTemplate], template_ids: dict[Path, str]) -> bytes:
    buffer = io.BytesIO()
    entries: list[tuple[str, Path]] = []
    for template in templates:
        source_root = template.path.resolve()
        template_id = template_ids[source_root]
        for path in source_root.rglob("*"):
            relative = path.relative_to(source_root)
            if _source_path_is_ignored(relative):
                continue
            if path.is_symlink():
                raise ValueError(f"template source archive does not support symbolic links: {path}")
            if path.is_file():
                entries.append((f"{template_id}/{relative.as_posix()}", path))
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for archive_name, path in sorted(entries):
            data = path.read_bytes()
            info = tarfile.TarInfo(archive_name)
            info.size = len(data)
            info.mode = 0o644
            info.mtime = 0
            info.uid = 0
            info.gid = 0
            info.uname = ""
            info.gname = ""
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


def _resolve_template_source(source: TemplateSource, manifest_root: Path, temporary_root: Path) -> Path:
    if isinstance(source, GitTemplateSource):
        repository_root = Path(_git_output(_builtin_template_root(), "rev-parse", "--show-toplevel"))
        archive = _git_bytes(repository_root, "archive", "--format=tar", source.revision, source.template_root)
        _extract_template_archive(archive, temporary_root)
        return _confined_relative_path(temporary_root, source.template_root)

    repository = ArtifactRepository(manifest_root / GENERATION_ARTIFACTS_DIRNAME)
    archive = repository.read_bytes(source.artifact)
    _extract_template_archive(archive, temporary_root)
    return temporary_root


def _extract_template_archive(payload: bytes, destination: Path) -> None:
    seen: set[str] = set()
    with tarfile.open(fileobj=io.BytesIO(payload), mode="r:") as archive:
        for member in archive:
            raw_name = member.name.rstrip("/") if member.isdir() else member.name
            try:
                canonical_name = _validate_replay_relative_path(raw_name)
            except ValueError as error:
                raise ValueError(f"unsafe template source archive member: {member.name}") from error
            if canonical_name in seen:
                raise ValueError(f"unsafe template source archive member: {member.name}")
            seen.add(canonical_name)
            if member.isdir():
                _confined_relative_path(destination, canonical_name).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile():
                raise ValueError(f"template source archive member is not a regular file: {member.name}")
            target = _confined_relative_path(destination, canonical_name)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise ValueError(f"template source archive member cannot be read: {member.name}")
            target.write_bytes(source.read())


def _compare_runtime_tasks(
    original_root: Path,
    replay_root: Path,
    instances: Sequence[GenerationInstance],
) -> tuple[str, ...]:
    differences: list[str] = []
    for instance in instances:
        original = _confined_relative_path(original_root, instance.task_id)
        replayed = _confined_relative_path(replay_root, instance.task_id)
        original_files = _file_bytes_by_relative_path(original)
        replayed_files = _file_bytes_by_relative_path(replayed)
        for relative in sorted(original_files.keys() | replayed_files.keys()):
            if relative not in original_files:
                differences.append(f"{instance.task_id}/{relative}: added")
            elif relative not in replayed_files:
                differences.append(f"{instance.task_id}/{relative}: missing")
            elif original_files[relative] != replayed_files[relative]:
                differences.append(f"{instance.task_id}/{relative}: content differs")
    return tuple(differences)


def _compare_replay_metadata(original_root: Path, replay_root: Path, config_ref: str) -> tuple[str, ...]:
    differences: list[str] = []
    for name in (GENERATION_MANIFEST_FILENAME,):
        original = json.loads((original_root / name).read_text(encoding="utf-8"))
        replayed = json.loads((replay_root / name).read_text(encoding="utf-8"))
        if original != replayed:
            differences.append(f"{name}: content differs")
    original_config = _confined_relative_path(original_root, config_ref)
    replayed_config = _confined_relative_path(replay_root, config_ref)
    if original_config.read_bytes() != replayed_config.read_bytes():
        differences.append(f"{config_ref}: content differs")
    return tuple(differences)


def _file_bytes_by_relative_path(root: Path) -> dict[str, bytes]:
    if not root.is_dir():
        return {}
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _prepare_replay_output(original_root: Path, output_root: Path, *, overwrite: bool) -> None:
    if (
        output_root == original_root
        or output_root.is_relative_to(original_root)
        or original_root.is_relative_to(output_root)
    ):
        raise ValueError("replay output must be separate from the original generated output")
    if output_root in {Path("/").resolve(), Path.home().resolve()}:
        raise ValueError("replay output cannot be a filesystem root or home directory")
    if (output_root / ".git").exists():
        raise ValueError("replay output cannot replace a Git repository root")
    if output_root.exists():
        if not overwrite:
            raise FileExistsError(f"replay output already exists: {output_root}; use --overwrite to replace it")
        if output_root.is_dir():
            shutil.rmtree(output_root)
        else:
            output_root.unlink()
    output_root.mkdir(parents=True)


def _confined_relative_path(root: Path, relative: str) -> Path:
    target = (root / relative).resolve()
    if not target.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes its generation root: {relative}")
    return target


def _source_path_is_ignored(relative: Path) -> bool:
    return any(part in _IGNORED_SOURCE_NAMES for part in relative.parts) or relative.suffix == ".pyc"


def _builtin_template_root() -> Path:
    return Path(__file__).resolve().parents[1] / "templates" / "builtin"


def _git_output(cwd: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise ValueError(f"Git source resolution failed: {detail}")
    return process.stdout.strip()


def _git_bytes(cwd: Path, *arguments: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(cwd), *arguments],
        check=False,
        capture_output=True,
    )
    if process.returncode != 0:
        detail = process.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"Git source resolution failed: {detail}")
    return process.stdout


__all__ = (
    "GENERATION_CONFIG_FILENAME",
    "GENERATION_MANIFEST_FILENAME",
    "ArtifactTemplateSource",
    "GenerationInstance",
    "GenerationManifest",
    "GitTemplateSource",
    "PreparedTemplateSource",
    "ReplayResult",
    "load_generation_manifest",
    "prepare_template_source",
    "require_available_sidecar_paths",
    "replay_generation",
    "write_generation_config",
    "write_generation_manifest",
)
