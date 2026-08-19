# ABOUTME: Exports public evidence lifecycles as content-addressed local Prime packages.
# ABOUTME: Retains one source identity and one archive reference for each packaged lifecycle.

from __future__ import annotations

import hashlib
import json
import keyword
import shutil
import tempfile
import textwrap
import tomllib
import warnings
from dataclasses import dataclass
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any, Literal

from packaging.version import InvalidVersion, Version
from pydantic import Field, PositiveInt, PrivateAttr, model_validator

from aec_bench.contracts.artifacts import ArtifactRef, Sha256
from aec_bench.contracts.provider_provenance import ProviderAdapterIdentity
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.lifecycles.catalogue import lifecycle_package_variant
from aec_bench.lifecycles.runtime.lifecycle import (
    evidence_lifecycle_package_identity,
    load_evidence_lifecycle_spec,
)
from aec_bench.prime_lab.exporter import DEFAULT_PRIME_ENVIRONMENTS_DIR, normalise_environment_id
from aec_bench.providers.source_identity import (
    resolve_provider_adapter_identity,
    write_deterministic_source_snapshot,
)


class LegacyPrimeLifecycleSourceProvenance(StrictModel):
    root: NonEmptyStr
    commit: NonEmptyStr
    dirty: bool
    dirty_digest: Sha256
    source_inventory_sha256: Sha256
    repository_kind: Literal["git", "source_tree"]


class LegacyPrimeLifecyclePackageRecord(StrictModel):
    package_dir: NonEmptyStr
    template_id: NonEmptyStr
    variant_id: NonEmptyStr
    visibility: Literal["public"]
    lifecycle_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    initial_instruction: NonEmptyStr
    lifecycle_spec_sha256: Sha256
    package_sha256: Sha256

    @model_validator(mode="after")
    def validate_checkpoint_ids(self) -> LegacyPrimeLifecyclePackageRecord:
        if len(set(self.checkpoint_ids)) != len(self.checkpoint_ids):
            raise ValueError("lifecycle checkpoint ids must be unique")
        if not Path(self.package_dir).is_absolute():
            raise ValueError("lifecycle package path must be absolute")
        return self


class LegacyPrimeLifecycleExportManifest(StrictModel):
    schema_version: Literal["2"] = "2"
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
    source: LegacyPrimeLifecycleSourceProvenance
    packages: tuple[LegacyPrimeLifecyclePackageRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_packages(self) -> LegacyPrimeLifecycleExportManifest:
        identities = [(record.lifecycle_id, record.variant_id) for record in self.packages]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate lifecycle package identity")
        paths = [record.package_dir for record in self.packages]
        if len(set(paths)) != len(paths):
            raise ValueError("duplicate lifecycle package path")
        return self


class PrimeLifecycleProtocolVersions(StrictModel):
    environment: Literal["aec-bench/prime-lifecycle-environment/1"] = "aec-bench/prime-lifecycle-environment/1"
    evidence_request: Literal["1"] = "1"
    lifecycle_operation: Literal["1"] = "1"


class PrimeLifecyclePackageRecord(StrictModel):
    package: ArtifactRef
    template_id: NonEmptyStr
    variant_id: NonEmptyStr
    visibility: Literal["public"]
    lifecycle_id: NonEmptyStr
    checkpoint_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    initial_instruction: NonEmptyStr

    _package_dir: Path | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def validate_checkpoint_ids(self) -> PrimeLifecyclePackageRecord:
        if len(set(self.checkpoint_ids)) != len(self.checkpoint_ids):
            raise ValueError("lifecycle checkpoint ids must be unique")
        return self

    def bind_package_dir(self, path: Path) -> PrimeLifecyclePackageRecord:
        self._package_dir = Path(path)
        return self

    @property
    def package_dir(self) -> str:
        if self._package_dir is None:
            raise RuntimeError("lifecycle package archive has not been materialized")
        return str(self._package_dir)


class PrimeLifecycleExportManifest(StrictModel):
    schema_version: Literal["3"] = "3"
    environment_id: NonEmptyStr
    package_version: NonEmptyStr
    local_only: Literal[True] = True
    execution_mode: Literal["persistent_context"] = "persistent_context"
    memory_visibility_policy: Literal["persistent_context"] = "persistent_context"
    reward_owner: Literal["task_lifecycle_verifier"] = "task_lifecycle_verifier"
    hosted_supported: Literal[False] = False
    training_supported: Literal[False] = False
    continual_learning_supported: Literal[False] = False
    transfer_supported: Literal[False] = False
    max_turns: PositiveInt
    source: ProviderAdapterIdentity
    protocols: PrimeLifecycleProtocolVersions = Field(default_factory=PrimeLifecycleProtocolVersions)
    packages: tuple[PrimeLifecyclePackageRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_packages(self) -> PrimeLifecycleExportManifest:
        identities = [(record.lifecycle_id, record.variant_id) for record in self.packages]
        if len(set(identities)) != len(identities):
            raise ValueError("duplicate lifecycle package identity")
        artifact_ids = [record.package.artifact_id for record in self.packages]
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("duplicate lifecycle package artifact")
        return self


PrimeLifecycleManifestDocument = PrimeLifecycleExportManifest | LegacyPrimeLifecycleExportManifest


@dataclass(frozen=True)
class _ValidatedLifecyclePackage:
    package_dir: Path
    template_id: str
    variant_id: str
    lifecycle_id: str
    checkpoint_ids: tuple[str, ...]
    initial_instruction: str


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
    """Write a local package with exact source and lifecycle package artifacts."""
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
    duplicate_paths = [str(record.package_dir) for record in records]
    duplicate_identities = [(record.lifecycle_id, record.variant_id) for record in records]
    if len(set(duplicate_paths)) != len(duplicate_paths) or len(set(duplicate_identities)) != len(duplicate_identities):
        raise ValueError("duplicate lifecycle package reference")

    output_dir = Path(config.output_dir)
    package_dir = output_dir / environment_id
    _assert_destination_is_safe(package_dir, environment_id, records)

    source_root = _validated_source_project_root(
        Path(config.aec_bench_root).resolve()
        if config.aec_bench_root is not None
        else Path(__file__).resolve().parents[3]
    )
    source_paths = _prime_source_paths(source_root)

    output_dir.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{environment_id}.tmp-", dir=output_dir))
    try:
        module_dir = staging / environment_id
        module_dir.mkdir(parents=True)
        source = resolve_provider_adapter_identity(
            adapter_id="aec-bench/prime-lifecycle",
            package_version=_distribution_version("aec-bench"),
            source_root=source_root,
            source_paths=source_paths,
            snapshot_path=module_dir / "provider-source.tar",
            snapshot_artifact_id="provider-source.tar",
        )
        packaged_records = tuple(
            _archive_lifecycle_package(record, module_dir=module_dir, index=index)
            for index, record in enumerate(records)
        )
        manifest = PrimeLifecycleExportManifest(
            environment_id=environment_id,
            package_version=config.version,
            max_turns=config.max_turns,
            source=source,
            packages=packaged_records,
        )
        _write_text(module_dir / "__init__.py", _render_package_init(environment_id))
        _write_text(module_dir / "environment.py", _render_environment_wrapper())
        _write_json(module_dir / "lifecycle_manifest.json", manifest.model_dump(mode="json"))
        _write_text(
            staging / "pyproject.toml",
            _render_local_pyproject(
                environment_id=environment_id,
                version=config.version,
                description=config.description,
                aec_bench_version=source.package_version,
            ),
        )
        _write_text(staging / "README.md", _render_local_readme(environment_id, packaged_records))
        recheck_path = staging / ".source-recheck.tar"
        actual_source = resolve_provider_adapter_identity(
            adapter_id="aec-bench/prime-lifecycle",
            package_version=source.package_version,
            source_root=source_root,
            source_paths=source_paths,
            snapshot_path=recheck_path,
            snapshot_artifact_id="provider-source.tar",
        )
        recheck_path.unlink(missing_ok=True)
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


def load_prime_lifecycle_manifest(path: Path) -> PrimeLifecycleManifestDocument:
    """Load current package archives or retained local-reference manifests."""
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") == "2":
        return LegacyPrimeLifecycleExportManifest.model_validate(payload)
    return PrimeLifecycleExportManifest.model_validate(payload)


def _validated_public_package_record(package_dir: Path) -> _ValidatedLifecyclePackage:
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
    return _ValidatedLifecyclePackage(
        package_dir=package,
        template_id=template_id,
        variant_id=variant["variant_id"],
        lifecycle_id=identity["lifecycle_id"],
        checkpoint_ids=tuple(checkpoint.checkpoint_id for checkpoint in spec.checkpoints),
        initial_instruction=instruction_path.read_text(encoding="utf-8"),
    )


def _validated_source_project_root(source_root: Path) -> Path:
    root = Path(source_root).resolve()
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


def _prime_source_paths(source_root: Path) -> tuple[Path, ...]:
    package_root = source_root / "src" / "aec_bench"
    if not package_root.is_dir():
        package_root = source_root / "aec_bench"
    paths = [
        source_root / "pyproject.toml",
        package_root / "prime_lab",
        package_root / "lifecycles",
        package_root / "contracts" / "provider_provenance.py",
        package_root / "providers" / "source_identity.py",
    ]
    lockfile = source_root / "uv.lock"
    if lockfile.is_file():
        paths.append(lockfile)
    return tuple(paths)


def _archive_lifecycle_package(
    record: _ValidatedLifecyclePackage,
    *,
    module_dir: Path,
    index: int,
) -> PrimeLifecyclePackageRecord:
    archive_path = module_dir / "lifecycle-packages" / f"{index:04d}.tar"
    write_deterministic_source_snapshot(
        root=record.package_dir,
        source_paths=(record.package_dir,),
        destination=archive_path,
    )
    content = archive_path.read_bytes()
    return PrimeLifecyclePackageRecord(
        package=ArtifactRef(
            artifact_id=archive_path.relative_to(module_dir).as_posix(),
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
            media_type="application/x-tar",
        ),
        template_id=record.template_id,
        variant_id=record.variant_id,
        visibility="public",
        lifecycle_id=record.lifecycle_id,
        checkpoint_ids=record.checkpoint_ids,
        initial_instruction=record.initial_instruction,
    )


def _distribution_version(name: str) -> str:
    try:
        return importlib_metadata.version(name)
    except importlib_metadata.PackageNotFoundError:
        return "not-installed"


def _render_package_init(environment_id: str) -> str:
    return (
        "# ABOUTME: Exposes the generated local lifecycle environment loader.\n"
        "# ABOUTME: Keeps package import behavior limited to the Verifiers load contract.\n\n"
        f"from {environment_id}.environment import load_environment\n\n"
        '__all__ = ["load_environment"]\n'
    )


def _render_environment_wrapper() -> str:
    return """# ABOUTME: Loads one local-only persistent AEC evidence-lifecycle environment.
# ABOUTME: Delegates runtime behavior and task-owned scoring to the attested aec-bench package.

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
    aec_bench_version: str,
) -> str:
    package_description = description or "Local persistent AEC evidence-lifecycle environment"
    dependencies = [
        "datasets>=4.0",
        "verifiers>=0.1.14,<0.2",
        f"aec-bench[prime]=={aec_bench_version}",
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
        """
    )


def _render_local_readme(
    environment_id: str,
    records: tuple[PrimeLifecyclePackageRecord, ...],
) -> str:
    package_lines = "\n        ".join(
        f"- `{record.variant_id}`: `{record.package.artifact_id}` (`{record.package.sha256}`)" for record in records
    )
    return textwrap.dedent(
        f"""\
        # {environment_id}

        This is a local-only Prime/Verifiers environment for persistent AEC evidence lifecycles.
        One rollout owns one complete lifecycle and one persistent conversation. The referenced
        materialized packages are retained inside this generated package and checked through their
        `ArtifactRef` values before every rollout.

        The task lifecycle verifier is the sole reward authority. This export does not support remote
        publication, hosted execution, training, continual learning, or transfer claims.

        ## Referenced public packages

        {package_lines}

        ## Local loading

        Install the exact `aec-bench` version declared in `pyproject.toml` from its release artifact or
        source distribution. Then install this generated package without replacing that resolved runtime.
        Run the import from outside the aec-bench repository root so the repository `agents/` directory
        cannot shadow the installed `openai-agents` package used by Verifiers.

        ```bash
        uv pip install /absolute/path/to/aec_bench-0.1.0-py3-none-any.whl
        uv pip install --no-deps /absolute/path/to/generated-package
        cd /tmp
        python \\
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
    records: tuple[_ValidatedLifecyclePackage, ...],
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
