# ABOUTME: Loads graph-hidden public tasks and physically separate sealed evaluation authority.
# ABOUTME: Produces phase-neutral task identities without joining public and hidden roots.

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.evaluation_generation.cohort import EvaluationTaskIdentity
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import OutputCompletionContract
from aec_bench.contracts.run_bundle import TaskSnapshotRef
from aec_bench.contracts.task_definition import TaskDefinition, Visibility
from aec_bench.evaluation.task_world import TASK_WORLD_SIDECARS, load_task_world_profile
from aec_bench.harness.proposal_task_package import source_task_package_sha256
from aec_bench.meta_harness.declared_task_surface import project_declared_task_surface_payload
from aec_bench.meta_harness.decomposition_problem_view import PublicSourceBinding
from aec_bench.meta_harness.task_snapshot import (
    build_task_snapshot,
    graph_hidden_task_snapshot_sha256,
)
from aec_bench.tasks.loader import load_task_definition


class EvaluationTaskMaterialError(ValueError):
    """Reject incomplete, overlapping, or identity-drifting evaluation material."""


@dataclass(frozen=True, slots=True)
class EvaluationTaskMaterialSpec:
    """Declared public and sealed file surface for one evaluation task."""

    task_id: str
    public_sources: tuple[tuple[str, str], ...]
    sealed_file_paths: frozenset[str]

    def __post_init__(self) -> None:
        _require_package_relative_path(self.task_id, label="task id")
        source_ids = tuple(source_id for source_id, _ in self.public_sources)
        source_paths = tuple(path for _, path in self.public_sources)
        if any(not source_id.strip() for source_id in source_ids):
            raise EvaluationTaskMaterialError(
                "evaluation public source ids must be non-empty",
            )
        if len(source_ids) != len(set(source_ids)) or len(source_paths) != len(
            set(source_paths),
        ):
            raise EvaluationTaskMaterialError(
                "evaluation public source ids and paths must be unique",
            )
        for path in source_paths:
            _require_package_relative_path(path, label="public source")
        if not self.sealed_file_paths:
            raise EvaluationTaskMaterialError(
                "evaluation sealed file inventory must be non-empty",
            )
        for path in self.sealed_file_paths:
            _require_package_relative_path(path, label="sealed file")


@dataclass(frozen=True, slots=True)
class EvaluationTaskMaterial:
    """Resolved public bytes and hidden authority for one evaluation task."""

    task: TaskDefinition
    public_snapshot: TaskSnapshotRef
    identity: EvaluationTaskIdentity
    output_contract: OutputCompletionContract
    public_sources: tuple[PublicSourceBinding, ...]
    public_task_dir: Path
    sealed_task_dir: Path
    world_id: str


def load_evaluation_task_material(
    *,
    spec: EvaluationTaskMaterialSpec,
    public_tasks_root: Path,
    sealed_tasks_root: Path,
) -> EvaluationTaskMaterial:
    """Load one exact evaluation task while preserving the public/hidden boundary."""

    public_root = Path(public_tasks_root).resolve()
    sealed_root = Path(sealed_tasks_root).resolve()
    validate_disjoint_material_roots(
        public_root=public_root,
        sealed_root=sealed_root,
    )
    relative = Path(spec.task_id)
    public_dir = _contained_task_dir(
        root=public_root,
        relative=relative,
        label="public",
    )
    sealed_dir = _contained_task_dir(
        root=sealed_root,
        relative=relative,
        label="sealed",
    )
    _validate_public_package(public_dir, spec)
    _validate_sealed_package(sealed_dir, spec)

    task = load_task_definition(public_dir, public_root)
    if task.visibility is not Visibility.PUBLIC:
        raise EvaluationTaskMaterialError(
            f"evaluation task is not public: {spec.task_id}",
        )
    snapshot = build_task_snapshot(task=task, tasks_root=public_root)
    if snapshot.world is not None:
        raise EvaluationTaskMaterialError(
            f"evaluation public snapshot contains a world: {spec.task_id}",
        )
    output_contract = _load_output_contract(public_dir)
    world_path = sealed_dir / "world.json"
    world_payload = _read_json(world_path)
    profile = load_task_world_profile(sealed_dir)
    if profile is None:
        raise EvaluationTaskMaterialError(
            f"sealed evaluation world is invalid: {spec.task_id}",
        )
    surface = project_declared_task_surface_payload(
        task=task,
        payload=world_payload,
    )
    world_package_sha256 = hashlib.sha256(world_path.read_bytes()).hexdigest()
    identity = EvaluationTaskIdentity(
        task_id=spec.task_id,
        public_snapshot=snapshot,
        public_task_snapshot_sha256=graph_hidden_task_snapshot_sha256(snapshot),
        sealed_task_package_sha256=source_task_package_sha256(sealed_dir),
        world_lineage_id=world_package_sha256,
        world_package_sha256=world_package_sha256,
        topology_signature_sha256=canonical_content_sha256(
            surface.model_dump(mode="json"),
        ),
    )
    return EvaluationTaskMaterial(
        task=task,
        public_snapshot=snapshot,
        identity=identity,
        output_contract=output_contract,
        public_sources=tuple(
            PublicSourceBinding(
                source_id=source_id,
                relative_path=relative_path,
                media_type="text/markdown",
            )
            for source_id, relative_path in spec.public_sources
        ),
        public_task_dir=public_dir,
        sealed_task_dir=sealed_dir,
        world_id=profile.world_id,
    )


def validate_disjoint_material_roots(
    *,
    public_root: Path,
    sealed_root: Path,
) -> None:
    """Require public and hidden task material to occupy disjoint directory trees."""

    public = Path(public_root).resolve()
    sealed = Path(sealed_root).resolve()
    if public == sealed or public.is_relative_to(sealed) or sealed.is_relative_to(public):
        raise EvaluationTaskMaterialError(
            "public and sealed evaluation roots must be physically disjoint",
        )


def _validate_public_package(
    task_dir: Path,
    spec: EvaluationTaskMaterialSpec,
) -> None:
    forbidden = [
        *(task_dir / sidecar for sidecar in TASK_WORLD_SIDECARS),
        task_dir / "tests" / "instance.json",
        task_dir / "tests" / "fixtures",
    ]
    present = [path.relative_to(task_dir).as_posix() for path in forbidden if path.exists()]
    if present:
        raise EvaluationTaskMaterialError(
            "public evaluation task contains sealed authority material: " + ", ".join(sorted(present)),
        )
    required = (
        task_dir / "tests" / "test.sh",
        task_dir / "tests" / "verify.py",
        task_dir / "environment" / "output_contract.json",
        *(task_dir / relative for _, relative in spec.public_sources),
    )
    missing = [path.relative_to(task_dir).as_posix() for path in required if not path.is_file()]
    if missing:
        raise EvaluationTaskMaterialError(
            "public evaluation task is incomplete: " + ", ".join(sorted(missing)),
        )


def _validate_sealed_package(
    task_dir: Path,
    spec: EvaluationTaskMaterialSpec,
) -> None:
    observed = frozenset(path.relative_to(task_dir).as_posix() for path in task_dir.rglob("*") if path.is_file())
    if observed != spec.sealed_file_paths:
        raise EvaluationTaskMaterialError(
            "sealed evaluation task file inventory does not match its contract",
        )


def _load_output_contract(task_dir: Path) -> OutputCompletionContract:
    path = task_dir / "environment" / "output_contract.json"
    try:
        return OutputCompletionContract.model_validate_json(
            path.read_text(encoding="utf-8"),
        )
    except (OSError, ValueError) as error:
        raise EvaluationTaskMaterialError(
            "public evaluation output contract is invalid",
        ) from error


def _contained_task_dir(
    *,
    root: Path,
    relative: Path,
    label: str,
) -> Path:
    unresolved = root / relative
    if unresolved.is_symlink():
        raise EvaluationTaskMaterialError(
            f"{label} evaluation task cannot be a symbolic link",
        )
    try:
        resolved = unresolved.resolve(strict=True)
    except OSError as error:
        raise EvaluationTaskMaterialError(
            f"{label} evaluation task is missing: {relative.as_posix()}",
        ) from error
    if not resolved.is_relative_to(root) or not resolved.is_dir():
        raise EvaluationTaskMaterialError(
            f"{label} evaluation task escapes its root",
        )
    return resolved


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EvaluationTaskMaterialError(
            f"invalid evaluation JSON: {path.name}",
        ) from error
    if not isinstance(payload, dict):
        raise EvaluationTaskMaterialError(
            f"evaluation JSON must be an object: {path.name}",
        )
    return payload


def _require_package_relative_path(value: str, *, label: str) -> None:
    selected = Path(value)
    if (
        not value.strip()
        or selected.is_absolute()
        or not selected.parts
        or any(part in {"", ".", ".."} for part in selected.parts)
    ):
        raise EvaluationTaskMaterialError(
            f"evaluation {label} must be a package-relative path",
        )
