# ABOUTME: Exports materialized public evidence lifecycles as local-only Prime packages.
# ABOUTME: Hash-binds absolute package references without copying lifecycle or runtime sources.

from __future__ import annotations

import json
import keyword
import shutil
import tempfile
import textwrap
import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from packaging.version import InvalidVersion, Version
from pydantic import Field, PositiveInt, field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.meta_harness.evidence_lifecycle import (
    evidence_lifecycle_package_identity,
    load_evidence_lifecycle_spec,
)
from aec_bench.meta_harness.evidence_lifecycle_experiment import repository_provenance
from aec_bench.prime_lab.exporter import DEFAULT_PRIME_ENVIRONMENTS_DIR, normalise_environment_id
from aec_bench.task_world_templates.lifecycles import lifecycle_package_variant


class PrimeLifecycleSourceProvenance(StrictModel):
    root: NonEmptyStr
    commit: NonEmptyStr
    dirty: bool
    dirty_digest: NonEmptyStr
    source_inventory_sha256: NonEmptyStr
    repository_kind: Literal["git", "source_tree"]

    @field_validator("dirty_digest", "source_inventory_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


class PrimeLifecyclePackageRecord(StrictModel):
    package_dir: NonEmptyStr
    template_id: NonEmptyStr
    variant_id: NonEmptyStr
    visibility: Literal["public"]
    lifecycle_id: NonEmptyStr
    world_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    initial_instruction: NonEmptyStr
    lifecycle_spec_sha256: NonEmptyStr
    package_sha256: NonEmptyStr

    @field_validator("lifecycle_spec_sha256", "package_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)

    @model_validator(mode="after")
    def validate_checkpoint_ids(self) -> PrimeLifecyclePackageRecord:
        if len(set(self.checkpoint_ids)) != len(self.checkpoint_ids):
            raise ValueError("lifecycle checkpoint ids must be unique")
        if not Path(self.package_dir).is_absolute():
            raise ValueError("lifecycle package path must be absolute")
        return self


class PrimeLifecycleExportManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    environment_id: NonEmptyStr
    local_only: Literal[True] = True
    execution_mode: Literal["persistent_context"] = "persistent_context"
    memory_visibility_policy: Literal["persistent_context"] = "persistent_context"
    reward_owner: Literal["task_lifecycle_verifier"] = "task_lifecycle_verifier"
    hosted_supported: Literal[False] = False
    training_supported: Literal[False] = False
    continual_learning_supported: Literal[False] = False
    transfer_supported: Literal[False] = False
    max_turns: PositiveInt
    source: PrimeLifecycleSourceProvenance
    packages: tuple[PrimeLifecyclePackageRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_packages(self) -> PrimeLifecycleExportManifest:
        identities = [(record.lifecycle_id, record.variant_id) for record in self.packages]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate lifecycle package identity")
        paths = [record.package_dir for record in self.packages]
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate lifecycle package path")
        return self


@dataclass(frozen=True)
class PrimeLifecycleExportConfig:
    name: str
    package_dirs: tuple[Path, ...]
    output_dir: Path = DEFAULT_PRIME_ENVIRONMENTS_DIR
    version: str = "0.1.0"
    description: str | None = None
    max_turns: int = 60
    aec_bench_root: Path | None = None


@dataclass(frozen=True)
class PrimeLifecycleExportResult:
    package_dir: Path
    manifest_path: Path
    lifecycle_count: int
    environment_id: str


def export_prime_lifecycle_environment(config: PrimeLifecycleExportConfig) -> PrimeLifecycleExportResult:
    """Write a thin local package that references immutable materialized lifecycles."""
    if not config.package_dirs:
        raise ValueError("at least one lifecycle package is required")
    if config.max_turns <= 0:
        raise ValueError("max_turns must be positive")

    environment_id = normalise_environment_id(config.name)
    if keyword.iskeyword(environment_id):
        raise ValueError(f"environment id cannot be a Python keyword: {environment_id}")
    try:
        Version(config.version)
    except InvalidVersion as exc:
        raise ValueError(f"version must be valid PEP 440: {config.version}") from exc
    records = tuple(
        sorted(
            (_validated_public_package_record(package_dir) for package_dir in config.package_dirs),
            key=lambda record: (record.template_id, record.lifecycle_id, record.variant_id, record.package_dir),
        )
    )
    duplicate_paths = [record.package_dir for record in records]
    duplicate_identities = [(record.lifecycle_id, record.variant_id) for record in records]
    if len(set(duplicate_paths)) != len(duplicate_paths) or len(set(duplicate_identities)) != len(duplicate_identities):
        raise ValueError("duplicate lifecycle package reference")

    output_dir = Path(config.output_dir)
    package_dir = output_dir / environment_id
    _assert_destination_is_safe(package_dir, environment_id, records)

    source_root = (
        Path(config.aec_bench_root).resolve() if config.aec_bench_root is not None else Path(__file__).resolve().parent
    )
    source_payload = repository_provenance(source_root)
    source = PrimeLifecycleSourceProvenance.model_validate(source_payload)
    source_root = _validated_source_project_root(source)
    manifest = PrimeLifecycleExportManifest(
        environment_id=environment_id,
        max_turns=config.max_turns,
        source=source,
        packages=records,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{environment_id}.tmp-", dir=output_dir))
    try:
        module_dir = staging / environment_id
        module_dir.mkdir(parents=True)
        _write_text(module_dir / "__init__.py", _render_package_init(environment_id))
        _write_text(module_dir / "environment.py", _render_environment_wrapper())
        _write_json(module_dir / "lifecycle_manifest.json", manifest.model_dump(mode="json"))
        _write_text(
            staging / "pyproject.toml",
            _render_local_pyproject(
                environment_id=environment_id,
                version=config.version,
                description=config.description,
                source_root=Path(source.root),
            ),
        )
        _write_text(staging / "README.md", _render_local_readme(environment_id, records))
        actual_source = PrimeLifecycleSourceProvenance.model_validate(repository_provenance(source_root))
        if actual_source != source:
            raise ValueError(
                "generated output changes bound aec-bench source provenance; "
                "choose an ignored or external output directory"
            )
        _replace_generated_package(staging, package_dir, environment_id)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    return PrimeLifecycleExportResult(
        package_dir=package_dir,
        manifest_path=package_dir / environment_id / "lifecycle_manifest.json",
        lifecycle_count=len(records),
        environment_id=environment_id,
    )


def load_prime_lifecycle_manifest(path: Path) -> PrimeLifecycleExportManifest:
    """Load and strictly validate one generated local lifecycle manifest."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PrimeLifecycleExportManifest.model_validate(payload)


def _validated_public_package_record(package_dir: Path) -> PrimeLifecyclePackageRecord:
    package = Path(package_dir).resolve()
    if not package.is_dir():
        raise ValueError(f"lifecycle package directory not found: {package}")
    try:
        variant = lifecycle_package_variant(package)
    except (KeyError, ValueError) as exc:
        raise ValueError(f"package is not a registered public lifecycle variant: {package}") from exc
    if variant is None or variant.get("visibility") != "public" or not isinstance(variant.get("variant_id"), str):
        raise ValueError(f"package is not a registered public lifecycle variant: {package}")

    template_path = package / "template.json"
    try:
        template_payload = json.loads(template_path.read_text(encoding="utf-8"))
        template_id = template_payload["template_id"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"package is not a registered public lifecycle variant: {package}") from exc
    if not isinstance(template_id, str) or not template_id:
        raise ValueError(f"package is not a registered public lifecycle variant: {package}")

    identity = evidence_lifecycle_package_identity(package)
    spec = load_evidence_lifecycle_spec(package)
    first_checkpoint = spec.checkpoints[0]
    instruction_path = package / first_checkpoint.instruction_path
    if not instruction_path.is_file():
        raise ValueError(f"initial lifecycle instruction is missing: {instruction_path}")
    return PrimeLifecyclePackageRecord(
        package_dir=str(package),
        template_id=template_id,
        variant_id=variant["variant_id"],
        visibility="public",
        lifecycle_id=identity["lifecycle_id"],
        world_id=identity["world_id"],
        checkpoint_ids=tuple(checkpoint.checkpoint_id for checkpoint in spec.checkpoints),
        initial_instruction=instruction_path.read_text(encoding="utf-8"),
        lifecycle_spec_sha256=identity["spec_sha256"],
        package_sha256=identity["package_sha256"],
    )


def _validated_source_project_root(source: PrimeLifecycleSourceProvenance) -> Path:
    root = Path(source.root).resolve()
    pyproject_path = root / "pyproject.toml"
    try:
        pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        project_name = pyproject["project"]["name"]
    except (OSError, KeyError, TypeError, tomllib.TOMLDecodeError) as exc:
        raise ValueError(f"source root is not an installable aec-bench checkout: {root}") from exc
    runtime_candidates = (
        root / "src" / "aec_bench" / "prime_lab" / "lifecycle_environment.py",
        root / "aec_bench" / "prime_lab" / "lifecycle_environment.py",
    )
    if project_name != "aec-bench" or not any(path.is_file() for path in runtime_candidates):
        raise ValueError(f"source root is not an installable aec-bench checkout: {root}")
    return root


def _render_package_init(environment_id: str) -> str:
    return (
        "# ABOUTME: Exposes the generated local lifecycle environment loader.\n"
        "# ABOUTME: Keeps package import behavior limited to the Verifiers load contract.\n\n"
        f"from {environment_id}.environment import load_environment\n\n"
        '__all__ = ["load_environment"]\n'
    )


def _render_environment_wrapper() -> str:
    return """# ABOUTME: Loads one local-only persistent AEC evidence-lifecycle environment.
# ABOUTME: Delegates runtime behavior and task-owned scoring to the installed aec-bench checkout.

from __future__ import annotations

from pathlib import Path

from aec_bench.prime_lab.lifecycle_environment import load_local_lifecycle_environment

MANIFEST_PATH = Path(__file__).with_name("lifecycle_manifest.json")


def load_environment(
    split: str = "eval",
    variant: str | list[str] | None = None,
    num_examples: int | None = None,
    seed: int | None = None,
    harness: str | None = None,
):
    return load_local_lifecycle_environment(
        manifest_path=MANIFEST_PATH,
        split=split,
        variant=variant,
        num_examples=num_examples,
        seed=seed,
        harness=harness,
    )
"""


def _render_local_pyproject(
    *,
    environment_id: str,
    version: str,
    description: str | None,
    source_root: Path,
) -> str:
    package_description = description or "Local persistent AEC evidence-lifecycle environment"
    dependencies = [
        "datasets>=4.0",
        "verifiers>=0.1.14,<0.2",
        "aec-bench[prime]",
    ]
    dependency_lines = ",\n".join(f"    {json.dumps(item)}" for item in dependencies)
    return textwrap.dedent(
        f"""\
        [project]
        name = {json.dumps(environment_id)}
        version = {json.dumps(version)}
        description = {json.dumps(package_description)}
        readme = "README.md"
        requires-python = ">=3.13"
        dependencies = [
        {dependency_lines}
        ]

        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"

        [tool.hatch.build.targets.wheel]
        packages = [{json.dumps(environment_id)}]

        [tool.uv.sources]
        aec-bench = {{ path = {json.dumps(str(source_root.resolve()))}, editable = true }}
        """
    )


def _render_local_readme(
    environment_id: str,
    records: tuple[PrimeLifecyclePackageRecord, ...],
) -> str:
    package_lines = "\n        ".join(
        f"- `{record.variant_id}`: `{record.package_dir}` (`{record.package_sha256}`)" for record in records
    )
    return textwrap.dedent(
        f"""\
        # {environment_id}

        This is a local-only Prime/Verifiers environment for persistent AEC evidence lifecycles.
        One rollout owns one complete lifecycle and one persistent conversation. The referenced
        materialized packages remain outside this generated package and are checked by content hash
        before every rollout.

        The task lifecycle verifier is the sole reward authority. This export does not support remote
        publication, hosted execution, training, continual learning, or transfer claims.

        ## Referenced public packages

        {package_lines}

        ## Local loading

        Run from outside the aec-bench repository root so the repository `agents/` directory cannot
        shadow the installed `openai-agents` package used by Verifiers.

        ```bash
        uv sync --python 3.13 --project /absolute/path/to/generated-package
        cd /tmp
        /absolute/path/to/generated-package/.venv/bin/python \\
          -c "from {environment_id} import load_environment; print(type(load_environment()).__name__)"
        ```
        """
    )


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    _write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _assert_destination_is_safe(
    package_dir: Path,
    environment_id: str,
    records: tuple[PrimeLifecyclePackageRecord, ...],
) -> None:
    destination = package_dir.resolve()
    for record in records:
        lifecycle_package = Path(record.package_dir).resolve()
        if (
            destination == lifecycle_package
            or destination.is_relative_to(lifecycle_package)
            or lifecycle_package.is_relative_to(destination)
        ):
            raise ValueError(f"generated environment destination overlaps lifecycle package: {lifecycle_package}")
    if not package_dir.exists():
        return
    manifest_path = package_dir / environment_id / "lifecycle_manifest.json"
    try:
        manifest = load_prime_lifecycle_manifest(manifest_path)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise ValueError(f"refusing to replace existing non-export directory: {package_dir}") from exc
    if manifest.environment_id != environment_id:
        raise ValueError(f"refusing to replace existing non-export directory: {package_dir}")


def _replace_generated_package(staging: Path, package_dir: Path, environment_id: str) -> None:
    if not package_dir.exists():
        staging.replace(package_dir)
        return

    backup = Path(tempfile.mkdtemp(prefix=f".{environment_id}.backup-", dir=package_dir.parent))
    backup.rmdir()
    package_dir.replace(backup)
    try:
        staging.replace(package_dir)
    except Exception:
        backup.replace(package_dir)
        raise
    try:
        shutil.rmtree(backup)
    except OSError as exc:
        warnings.warn(
            f"generated package is active at {package_dir}, but previous export backup remains at {backup}: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
