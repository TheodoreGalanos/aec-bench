# ABOUTME: Materializes source-free Harbor task packages for governed proposal-session invocations.
# ABOUTME: Keeps public task bytes and verifier-only assets on opposite sides of Harbor's agent boundary.

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.experimentation.proposals.task_packaging.build_context import (
    verify_proposal_task_build_context as _verify_proposal_task_build_context,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    MaterializedProposalTaskPackage as MaterializedProposalTaskPackage,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageError as ProposalTaskPackageError,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageFile as ProposalTaskPackageFile,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageIdentity as ProposalTaskPackageIdentity,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    ProposalTaskPackageManifest as ProposalTaskPackageManifest,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    VerifiedProposalTaskBuildContext as VerifiedProposalTaskBuildContext,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    assert_proposal_task_verifier_scope as assert_proposal_task_verifier_scope,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    assert_proposal_task_verifier_surface as assert_proposal_task_verifier_surface,
)
from aec_bench.experimentation.proposals.task_packaging.contracts import (
    project_proposal_task_verifier_surface as project_proposal_task_verifier_surface,
)
from aec_bench.experimentation.proposals.task_packaging.file_io import (
    read_regular_payload as _read_regular_payload,
)
from aec_bench.experimentation.proposals.task_packaging.file_io import (
    update_digest_field as _update_digest_field,
)

_SOURCE_PACKAGE_DOMAIN = b"aec-bench-task-package-v1\0"
_IGNORED_NAMES = frozenset({".DS_Store"})
_IGNORED_DIRECTORIES = frozenset({"__pycache__", ".pytest_cache"})
_VERIFIER_SUFFIXES = frozenset(
    {
        ".csv",
        ".json",
        ".jsonl",
        ".md",
        ".py",
        ".sh",
        ".toml",
        ".txt",
        ".whl",
        ".yaml",
        ".yml",
    }
)
_FORBIDDEN_VERIFIER_TOKENS = frozenset(
    {
        "answer",
        "catalog",
        "catalogue",
        "expected",
        "generation",
        "gold",
        "golden",
        "oracle",
        "solution",
        "template",
        "world",
    }
)
_GENERIC_DOCKERFILE = """\
FROM --platform=linux/amd64 python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \\
    bash \\
    bc \\
    ca-certificates \\
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
"""
_DOCKERIGNORE = "*\n!Dockerfile\n"
_MAX_VERIFIER_ASSET_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class _VerifierAsset:
    """Descriptor-bound bytes for one validated public or sealed verifier member."""

    relative_path: str
    payload: bytes


def source_task_package_sha256(task_dir: Path) -> str:
    """Hash one exact source task using the existing task-package digest convention."""

    root = Path(task_dir)
    if root.is_symlink():
        raise ProposalTaskPackageError(f"source task directory must not be a symbolic link: {root}")
    if not root.is_dir():
        raise ProposalTaskPackageError(f"source task directory is missing: {root}")

    digest = hashlib.sha256(_SOURCE_PACKAGE_DOMAIN)
    for path in sorted(root.rglob("*"), key=lambda candidate: candidate.relative_to(root).as_posix()):
        relative = path.relative_to(root)
        if path.is_symlink():
            raise ProposalTaskPackageError(f"source task packages cannot contain symbolic links: {relative.as_posix()}")
        if _ignored_source_path(relative):
            continue
        if path.is_dir():
            continue
        try:
            path_stat = path.stat(follow_symlinks=False)
        except OSError as error:
            raise ProposalTaskPackageError(f"source task member cannot be inspected: {relative.as_posix()}") from error
        if not stat.S_ISREG(path_stat.st_mode):
            raise ProposalTaskPackageError(f"source task member must be a regular file: {relative.as_posix()}")
        _update_digest_field(digest, relative.as_posix().encode("utf-8"))
        _update_digest_field(digest, f"{stat.S_IMODE(path_stat.st_mode):o}".encode("ascii"))
        try:
            content = path.read_bytes()
        except OSError as error:
            raise ProposalTaskPackageError(f"source task member cannot be read: {relative.as_posix()}") from error
        _update_digest_field(digest, content)
    return digest.hexdigest()


def build_proposal_task_package(
    *,
    source_task_dir: Path,
    destination_task_dir: Path,
    identity: ProposalTaskPackageIdentity,
    output_contract: OutputCompletionContract,
    verifier_asset_paths: tuple[str, ...],
    sealed_task_dir: Path | None = None,
    sealed_verifier_asset_paths: tuple[str, ...] = (),
) -> MaterializedProposalTaskPackage:
    """Publish one invocation-local Harbor task with no public source bytes in its image."""

    identity = ProposalTaskPackageIdentity.model_validate(identity.model_dump(mode="python"))
    source = Path(source_task_dir)
    destination = Path(destination_task_dir)
    _require_available_destination(destination)
    observed_source_sha256 = _require_package_identity(
        source,
        expected_sha256=identity.source_task_package_sha256,
        label="source",
    )
    _validate_governed_output_contract(
        source=source,
        identity=identity,
        output_contract=output_contract,
    )
    source_config = _read_source_task_config(source)
    verifier_assets = _resolve_verifier_assets(
        source,
        verifier_asset_paths=verifier_asset_paths,
        require_entrypoint=True,
    )
    sealed_assets, observed_sealed_sha256 = _resolve_sealed_verifier_bundle(
        source=source,
        sealed_task_dir=sealed_task_dir,
        identity=identity,
        verifier_asset_paths=sealed_verifier_asset_paths,
        public_assets=verifier_assets,
    )
    payloads = _derived_payloads(
        identity=identity,
        output_contract=output_contract,
        source_config=source_config,
        verifier_assets=verifier_assets,
        sealed_verifier_assets=sealed_assets,
    )
    _require_stable_package_identities(
        source=source,
        observed_source_sha256=observed_source_sha256,
        sealed_task_dir=sealed_task_dir,
        observed_sealed_sha256=observed_sealed_sha256,
    )
    manifest = _proposal_task_package_manifest(
        identity=identity,
        payloads=payloads,
        sealed_assets=sealed_assets,
    )
    _publish_proposal_task_package(
        destination=destination,
        payloads=payloads,
        manifest=manifest,
    )
    return MaterializedProposalTaskPackage(path=destination, manifest=manifest)


def _require_available_destination(destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise ProposalTaskPackageError(f"derived task package destination already exists: {destination}")


def _require_package_identity(
    task_dir: Path,
    *,
    expected_sha256: str,
    label: str,
) -> str:
    observed_sha256 = source_task_package_sha256(task_dir)
    if observed_sha256 != expected_sha256:
        raise ProposalTaskPackageError(f"{label} task package identity changed before derivation")
    return observed_sha256


def _validate_governed_output_contract(
    *,
    source: Path,
    identity: ProposalTaskPackageIdentity,
    output_contract: OutputCompletionContract,
) -> None:
    contract_sha256 = canonical_content_sha256(output_contract.model_dump(mode="json"))
    if contract_sha256 != identity.output_contract_sha256:
        raise ProposalTaskPackageError("output completion contract identity does not match")
    if output_contract.output_path != "/workspace/output.md":
        raise ProposalTaskPackageError("proposal task output path must be /workspace/output.md")
    _validate_source_output_contract(source, output_contract)


def _resolve_sealed_verifier_bundle(
    *,
    source: Path,
    sealed_task_dir: Path | None,
    identity: ProposalTaskPackageIdentity,
    verifier_asset_paths: tuple[str, ...],
    public_assets: tuple[_VerifierAsset, ...],
) -> tuple[tuple[_VerifierAsset, ...], str | None]:
    expected_sha256 = identity.sealed_task_package_sha256
    if expected_sha256 is None:
        if sealed_task_dir is not None or verifier_asset_paths:
            raise ProposalTaskPackageError("sealed verifier inputs require a governed sealed task package identity")
        return (), None
    if sealed_task_dir is None or not verifier_asset_paths:
        raise ProposalTaskPackageError("governed sealed task package identity requires its verifier bundle")

    sealed = Path(sealed_task_dir)
    _validate_disjoint_package_roots(public=source, sealed=sealed)
    observed_sha256 = _require_package_identity(
        sealed,
        expected_sha256=expected_sha256,
        label="sealed",
    )
    sealed_assets = _resolve_verifier_assets(
        sealed,
        verifier_asset_paths=verifier_asset_paths,
        require_entrypoint=False,
    )
    public_paths = {asset.relative_path for asset in public_assets}
    sealed_paths = {asset.relative_path for asset in sealed_assets}
    collisions = public_paths.intersection(sealed_paths)
    if collisions:
        raise ProposalTaskPackageError("public and sealed verifier assets collide: " + ", ".join(sorted(collisions)))
    return sealed_assets, observed_sha256


def _require_stable_package_identities(
    *,
    source: Path,
    observed_source_sha256: str,
    sealed_task_dir: Path | None,
    observed_sealed_sha256: str | None,
) -> None:
    if source_task_package_sha256(source) != observed_source_sha256:
        raise ProposalTaskPackageError("source task package changed during derivation")
    if sealed_task_dir is None:
        return
    final_sealed_sha256 = source_task_package_sha256(Path(sealed_task_dir))
    if observed_sealed_sha256 is None or final_sealed_sha256 != observed_sealed_sha256:
        raise ProposalTaskPackageError("sealed task package changed during derivation")


def _proposal_task_package_manifest(
    *,
    identity: ProposalTaskPackageIdentity,
    payloads: dict[str, bytes],
    sealed_assets: tuple[_VerifierAsset, ...],
) -> ProposalTaskPackageManifest:
    sealed_paths = frozenset(asset.relative_path for asset in sealed_assets)
    return ProposalTaskPackageManifest(
        schema_version=(
            "aecbench.proposal-task-package.v2"
            if identity.sealed_task_package_sha256 is not None
            else "aecbench.proposal-task-package.v1"
        ),
        task_id=identity.task_id,
        task_revision=identity.task_revision,
        source_task_package_sha256=identity.source_task_package_sha256,
        sealed_task_package_sha256=identity.sealed_task_package_sha256,
        problem_view_sha256=identity.problem_view_sha256,
        output_contract_sha256=identity.output_contract_sha256,
        visibility=identity.visibility,
        files=tuple(
            ProposalTaskPackageFile(
                path=relative_path,
                sha256=hashlib.sha256(content).hexdigest(),
                byte_size=len(content),
                role=_file_role(
                    relative_path,
                    sealed_verifier_paths=sealed_paths,
                ),
            )
            for relative_path, content in sorted(payloads.items())
        ),
    )


def _proposal_task_package_manifest_bytes(manifest: ProposalTaskPackageManifest) -> bytes:
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def _publish_proposal_task_package(
    *,
    destination: Path,
    payloads: dict[str, bytes],
    manifest: ProposalTaskPackageManifest,
) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
    )
    try:
        for relative_path, content in sorted(payloads.items()):
            target = temporary / PurePosixPath(relative_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        (temporary / "proposal-task-package.json").write_bytes(
            _proposal_task_package_manifest_bytes(manifest),
        )
        if destination.exists() or destination.is_symlink():
            raise ProposalTaskPackageError(
                f"derived task package destination appeared during publication: {destination}"
            )
        temporary.rename(destination)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise


def verify_proposal_task_build_context(
    context_dir: Path,
) -> VerifiedProposalTaskBuildContext:
    """Prove a Morph build context is the exact source-free derived surface."""

    return _verify_proposal_task_build_context(
        context_dir,
        expected_dockerfile=_GENERIC_DOCKERFILE.encode("utf-8"),
        expected_dockerignore=_DOCKERIGNORE.encode("utf-8"),
    )


@dataclass(frozen=True)
class _SourceTaskConfig:
    agent_timeout_sec: float
    verifier_timeout_sec: float
    build_timeout_sec: float
    cpus: int
    memory_mb: int
    storage_mb: int
    gpus: int
    allow_internet: bool


def _read_source_task_config(task_dir: Path) -> _SourceTaskConfig:
    try:
        from harbor.models.task.config import TaskConfig  # type: ignore[import-untyped]

        config = TaskConfig.model_validate_toml((task_dir / "task.toml").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ProposalTaskPackageError("source task.toml is missing or invalid") from error
    numeric_values = {
        "agent timeout": config.agent.timeout_sec,
        "verifier timeout": config.verifier.timeout_sec,
        "environment build timeout": config.environment.build_timeout_sec,
    }
    if any(isinstance(value, bool) or value <= 0 for value in numeric_values.values()):
        raise ProposalTaskPackageError("source task timeout values must be positive")
    resource_values = {
        "cpus": config.environment.cpus,
        "memory_mb": config.environment.memory_mb,
        "storage_mb": config.environment.storage_mb,
        "gpus": config.environment.gpus,
    }
    if (
        any(isinstance(value, bool) or not isinstance(value, int) for value in resource_values.values())
        or config.environment.cpus <= 0
        or config.environment.memory_mb <= 0
        or config.environment.storage_mb <= 0
        or config.environment.gpus < 0
    ):
        raise ProposalTaskPackageError("source task environment resources are invalid")
    return _SourceTaskConfig(
        agent_timeout_sec=float(config.agent.timeout_sec),
        verifier_timeout_sec=float(config.verifier.timeout_sec),
        build_timeout_sec=float(config.environment.build_timeout_sec),
        cpus=config.environment.cpus,
        memory_mb=config.environment.memory_mb,
        storage_mb=config.environment.storage_mb,
        gpus=config.environment.gpus,
        allow_internet=config.environment.allow_internet,
    )


def _validate_source_output_contract(
    task_dir: Path,
    expected: OutputCompletionContract,
) -> None:
    contract_path = task_dir / "environment" / "output_contract.json"
    if contract_path.is_symlink() or not contract_path.is_file():
        raise ProposalTaskPackageError("source task output completion contract is missing or unsafe")
    try:
        observed = OutputCompletionContract.model_validate_json(contract_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ProposalTaskPackageError("source task output completion contract is invalid") from error
    if observed != expected:
        raise ProposalTaskPackageError("source task output completion contract differs from the governed contract")


def _resolve_verifier_assets(
    task_dir: Path,
    *,
    verifier_asset_paths: tuple[str, ...],
    require_entrypoint: bool,
) -> tuple[_VerifierAsset, ...]:
    if len(verifier_asset_paths) != len(set(verifier_asset_paths)):
        raise ProposalTaskPackageError("verifier asset paths must be unique")
    canonical = tuple(sorted(verifier_asset_paths))
    if require_entrypoint and "tests/test.sh" not in canonical:
        raise ProposalTaskPackageError("derived Harbor task requires tests/test.sh")
    if not canonical:
        raise ProposalTaskPackageError("verifier asset paths must not be empty")

    return tuple(_resolve_verifier_asset(task_dir, raw_path) for raw_path in canonical)


def _resolve_verifier_asset(task_dir: Path, raw_path: str) -> _VerifierAsset:
    relative = _validated_verifier_relative_path(raw_path)
    path = task_dir / relative
    if path.is_symlink() or not path.is_file():
        raise ProposalTaskPackageError(f"verifier asset is missing or unsafe: {raw_path}")
    try:
        path_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalTaskPackageError(f"verifier asset cannot be inspected: {raw_path}") from error
    if not stat.S_ISREG(path_stat.st_mode):
        raise ProposalTaskPackageError(f"verifier asset must be a regular file: {raw_path}")
    return _VerifierAsset(
        relative_path=relative.as_posix(),
        payload=_read_regular_payload(
            path,
            label=f"verifier asset {raw_path}",
            max_bytes=_MAX_VERIFIER_ASSET_BYTES,
        ),
    )


def _validated_verifier_relative_path(raw_path: str) -> PurePosixPath:
    relative = PurePosixPath(raw_path)
    if (
        relative.is_absolute()
        or any(part in {"", ".", ".."} for part in relative.parts)
        or not relative.parts
        or relative.parts[0] != "tests"
    ):
        raise ProposalTaskPackageError(f"verifier asset must be a contained tests/ path: {raw_path}")
    if relative.suffix.casefold() not in _VERIFIER_SUFFIXES:
        raise ProposalTaskPackageError(f"verifier asset type is not allowlisted: {raw_path}")
    _reject_privileged_verifier_path(relative, raw_path=raw_path)
    return relative


def _reject_privileged_verifier_path(relative: PurePosixPath, *, raw_path: str) -> None:
    tokens = {token for part in relative.parts[1:] for token in re.split(r"[^a-z0-9]+", part.casefold()) if token}
    collapsed_path = re.sub(
        r"[^a-z0-9]+",
        "",
        "/".join(relative.parts[1:]).casefold(),
    )
    if tokens & _FORBIDDEN_VERIFIER_TOKENS or "metaharness" in collapsed_path:
        raise ProposalTaskPackageError(f"verifier asset path exposes a forbidden privileged marker: {raw_path}")


def _derived_payloads(
    *,
    identity: ProposalTaskPackageIdentity,
    output_contract: OutputCompletionContract,
    source_config: _SourceTaskConfig,
    verifier_assets: tuple[_VerifierAsset, ...],
    sealed_verifier_assets: tuple[_VerifierAsset, ...],
) -> dict[str, bytes]:
    payloads = {
        "instruction.md": (
            "Execute the governed proposal session supplied by the fixed kernel.\n"
            f"Write the final artifact to {output_contract.output_path}.\n"
        ).encode(),
        "task.toml": _sanitized_task_toml(identity=identity, source_config=source_config).encode("utf-8"),
        "environment/.dockerignore": _DOCKERIGNORE.encode("utf-8"),
        "environment/Dockerfile": _GENERIC_DOCKERFILE.encode("utf-8"),
        "environment/output_contract.json": (
            json.dumps(
                output_contract.model_dump(mode="json"),
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8"),
    }
    for asset in (*verifier_assets, *sealed_verifier_assets):
        payloads[asset.relative_path] = asset.payload
    return payloads


def _sanitized_task_toml(
    *,
    identity: ProposalTaskPackageIdentity,
    source_config: _SourceTaskConfig,
) -> str:
    visibility = json.dumps(identity.visibility.value)
    allow_internet = "true" if source_config.allow_internet else "false"
    return (
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "medium"\n'
        'category = "proposal-session"\n'
        f"visibility = {visibility}\n"
        'tags = ["proposal-session", "source-free"]\n\n'
        "[agent]\n"
        f"timeout_sec = {source_config.agent_timeout_sec!r}\n\n"
        "[verifier]\n"
        f"timeout_sec = {source_config.verifier_timeout_sec!r}\n\n"
        "[environment]\n"
        f"build_timeout_sec = {source_config.build_timeout_sec!r}\n"
        f"cpus = {source_config.cpus}\n"
        f"memory_mb = {source_config.memory_mb}\n"
        f"storage_mb = {source_config.storage_mb}\n"
        f"gpus = {source_config.gpus}\n"
        f"allow_internet = {allow_internet}\n"
    )


def _file_role(
    relative_path: str,
    *,
    sealed_verifier_paths: frozenset[str],
) -> Literal[
    "harbor_metadata",
    "agent_build_context",
    "public_output_contract",
    "verifier_only",
    "sealed_verifier_only",
]:
    if relative_path in sealed_verifier_paths:
        return "sealed_verifier_only"
    if relative_path.startswith("tests/"):
        return "verifier_only"
    if relative_path == "environment/output_contract.json":
        return "public_output_contract"
    if relative_path.startswith("environment/"):
        return "agent_build_context"
    return "harbor_metadata"


def _validate_disjoint_package_roots(*, public: Path, sealed: Path) -> None:
    try:
        public_root = public.resolve(strict=True)
        sealed_root = sealed.resolve(strict=True)
    except OSError as error:
        raise ProposalTaskPackageError("public and sealed task package roots must exist") from error
    if public_root == sealed_root or public_root.is_relative_to(sealed_root) or sealed_root.is_relative_to(public_root):
        raise ProposalTaskPackageError("public and sealed task package roots must be physically disjoint")


def _ignored_source_path(relative: Path) -> bool:
    return relative.name in _IGNORED_NAMES or any(part in _IGNORED_DIRECTORIES for part in relative.parts)
