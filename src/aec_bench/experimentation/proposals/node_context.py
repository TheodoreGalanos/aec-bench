# ABOUTME: Materializes one least-privilege proposal-node context from frozen session evidence.
# ABOUTME: Copies only exact public sources, upstream handoffs, and the node-authorized instruction.

from __future__ import annotations

import hashlib
import json
import re
import shutil
import stat
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.proposal_execution.graph import FinalSynthesisSpec, SemanticSubtaskSpec
from aec_bench.contracts.proposal_execution_context import CompiledNodeContextScope, ScopedSourceMaterialization
from aec_bench.contracts.proposal_execution_types import NodeInstructionVisibility
from aec_bench.contracts.task_snapshot import TaskSnapshotRef
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.proposals.program_compilation import (
    ProposalRunSessionBundle,
)
from aec_bench.experimentation.proposals.task_package import (
    ProposalTaskPackageError,
    source_task_package_sha256,
)
from aec_bench.harness.compilation.task_snapshot import (
    TaskSnapshotError,
    assert_task_snapshot_matches_directory,
)

_MANIFEST_PATH = "context-manifest.json"
_INSTRUCTION_PATH = "instruction.md"
_FORBIDDEN_PATH_TOKENS = frozenset(
    {
        "gold",
        "golden",
        "hidden",
        "test",
        "tests",
        "verifier",
        "world",
    }
)
_FORBIDDEN_FILE_NAMES = frozenset(
    {
        "expected_answer.json",
        "structured_answer.json",
        "task-review.json",
        "task-review.yaml",
        "task-review.yml",
        "task.toml",
        "world.json",
        "world.yaml",
        "world.yml",
    }
)


class ProposalNodeContextError(ValueError):
    """Host-owned context materialization or integrity failure."""


class ProposalNodeContextArtifactKind(StrEnum):
    """Closed file roles permitted inside one node invocation context."""

    INSTRUCTION = "instruction"
    PUBLIC_SOURCE = "public_source"
    UPSTREAM_HANDOFF = "upstream_handoff"


class PersistedProposalHandoffArtifact(FrozenStrictModel):
    """Exact host-side handoff artifact authorized as one node input."""

    handoff_id: NonEmptyStr
    artifact_path: Path
    artifact_sha256: str
    byte_size: int = Field(ge=0)

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_sha256(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("artifact_path")
    @classmethod
    def validate_artifact_path(cls, value: Path) -> Path:
        if not value.is_absolute():
            raise ValueError("persisted handoff artifact path must be absolute")
        return value


class ProposalNodeContextArtifact(LegacyContentAddressedModel):
    """One exact file materialized into the node-visible workspace."""

    schema_version: Literal["aecbench.proposal-node-context-artifact.v1"] = "aecbench.proposal-node-context-artifact.v1"
    kind: ProposalNodeContextArtifactKind
    logical_id: NonEmptyStr
    workspace_relative_path: NonEmptyStr
    artifact_sha256: str
    byte_size: int = Field(ge=0)

    @field_validator("workspace_relative_path")
    @classmethod
    def validate_workspace_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts) or value == _MANIFEST_PATH:
            raise ValueError("node-context artifact path must be contained and cannot replace the manifest")
        return value

    @field_validator("artifact_sha256")
    @classmethod
    def validate_artifact_sha256(cls, value: str) -> str:
        return validate_sha256(value)


class ProposalNodeContextManifest(LegacyContentAddressedModel):
    """Content-addressed inventory of one least-privilege node workspace."""

    schema_version: Literal["aecbench.proposal-node-context-manifest.v1"] = "aecbench.proposal-node-context-manifest.v1"
    context_id: NonEmptyStr
    bundle_sha256: str
    compilation_sha256: str
    session_plan_sha256: str
    proposal_graph_sha256: str
    source_scope_manifest_sha256: str
    source_task_package_sha256: str
    node_id: NonEmptyStr
    node_spec_sha256: str
    node_scope_sha256: str
    instruction_visibility: NodeInstructionVisibility
    artifacts: tuple[ProposalNodeContextArtifact, ...] = Field(min_length=1)

    @field_validator(
        "bundle_sha256",
        "compilation_sha256",
        "session_plan_sha256",
        "proposal_graph_sha256",
        "source_scope_manifest_sha256",
        "source_task_package_sha256",
        "node_spec_sha256",
        "node_scope_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("artifacts")
    @classmethod
    def canonicalize_artifacts(
        cls,
        value: tuple[ProposalNodeContextArtifact, ...],
    ) -> tuple[ProposalNodeContextArtifact, ...]:
        canonical = tuple(
            sorted(
                value,
                key=lambda artifact: (artifact.kind.value, artifact.logical_id),
            )
        )
        keys = tuple((artifact.kind, artifact.logical_id) for artifact in canonical)
        paths = tuple(artifact.workspace_relative_path for artifact in canonical)
        if len(keys) != len(set(keys)):
            raise ValueError("node-context artifact identities must be unique")
        if len(paths) != len(set(paths)):
            raise ValueError("node-context artifact paths must be unique")
        return canonical

    @model_validator(mode="after")
    def validate_instruction_artifact(self) -> Self:
        instructions = tuple(
            artifact for artifact in self.artifacts if artifact.kind is ProposalNodeContextArtifactKind.INSTRUCTION
        )
        if (
            len(instructions) != 1
            or instructions[0].logical_id != "instruction"
            or instructions[0].workspace_relative_path != _INSTRUCTION_PATH
        ):
            raise ValueError("node context requires exactly one canonical instruction artifact")
        for artifact in self.artifacts:
            path = PurePosixPath(artifact.workspace_relative_path)
            if artifact.kind is ProposalNodeContextArtifactKind.PUBLIC_SOURCE and path.parts[0] != "sources":
                raise ValueError("public source artifacts must remain under the sources directory")
            if artifact.kind is ProposalNodeContextArtifactKind.UPSTREAM_HANDOFF and path.parts[0] != "upstream":
                raise ValueError("upstream handoff artifacts must remain under the upstream directory")
        return self

    def artifact(
        self,
        kind: ProposalNodeContextArtifactKind,
        logical_id: str,
    ) -> ProposalNodeContextArtifact:
        """Return one exact context artifact or fail closed."""
        match = next(
            (artifact for artifact in self.artifacts if artifact.kind is kind and artifact.logical_id == logical_id),
            None,
        )
        if match is None:
            raise ProposalNodeContextError(f"node context does not contain {kind.value} artifact {logical_id!r}")
        return match


def materialize_proposal_node_context(
    *,
    bundle: ProposalRunSessionBundle,
    node_id: str,
    source_task_root: Path,
    invocation_workspace: Path,
    upstream_handoff_artifacts: tuple[
        PersistedProposalHandoffArtifact,
        ...,
    ],
) -> ProposalNodeContextManifest:
    """Publish one exact node-visible context without provider or runtime dispatch."""
    workspace = Path(invocation_workspace)
    _assert_fresh_workspace(workspace)

    for source in bundle.compilation.source_scope_manifest.sources:
        _assert_public_source_path(source.task_relative_path)
    exact_bundle = _validate_exact_bundle(bundle)
    graph = exact_bundle.compilation.proposal_graph
    node, node_scope = _resolve_node(exact_bundle, node_id=node_id)

    source_root, source_package_sha256 = _validate_source_task_root(
        source_task_root,
        task_snapshot=exact_bundle.task_snapshot,
    )
    _assert_workspace_disjoint_from_source(
        workspace=workspace,
        source_task_root=source_root,
    )
    upstream_by_id = _validate_upstream_set(
        expected_handoff_ids=node_scope.upstream_handoff_ids,
        artifacts=upstream_handoff_artifacts,
    )

    materialized: list[tuple[ProposalNodeContextArtifact, bytes]] = []
    instruction = _instruction_bytes(
        bundle=exact_bundle,
        node_id=node_id,
        node_objective=node.objective,
        visibility=node_scope.instruction_visibility,
    )
    materialized.append(
        (
            _context_artifact(
                kind=ProposalNodeContextArtifactKind.INSTRUCTION,
                logical_id="instruction",
                workspace_relative_path=_INSTRUCTION_PATH,
                content=instruction,
            ),
            instruction,
        )
    )

    sources_by_id = {source.source_id: source for source in exact_bundle.compilation.source_scope_manifest.sources}
    for index, source_id in enumerate(node_scope.source_ids, start=1):
        selected_source = sources_by_id.get(source_id)
        if selected_source is None:
            raise ProposalNodeContextError(f"node scope references unknown public source {source_id!r}")
        content = _read_exact_source(
            source_root=source_root,
            materialization=selected_source,
        )
        relative_path = f"sources/{index:04d}.bin"
        materialized.append(
            (
                _context_artifact(
                    kind=ProposalNodeContextArtifactKind.PUBLIC_SOURCE,
                    logical_id=source_id,
                    workspace_relative_path=relative_path,
                    content=content,
                ),
                content,
            )
        )

    for index, handoff_id in enumerate(
        node_scope.upstream_handoff_ids,
        start=1,
    ):
        persisted = upstream_by_id[handoff_id]
        content = _read_exact_handoff(
            persisted,
            source_task_root=source_root,
        )
        relative_path = f"upstream/{index:04d}.bin"
        materialized.append(
            (
                _context_artifact(
                    kind=ProposalNodeContextArtifactKind.UPSTREAM_HANDOFF,
                    logical_id=handoff_id,
                    workspace_relative_path=relative_path,
                    content=content,
                ),
                content,
            )
        )

    final_source_sha256 = _source_task_package_sha256(source_root)
    if final_source_sha256 != source_package_sha256:
        raise ProposalNodeContextError("source task package changed during node-context materialization")

    manifest = ProposalNodeContextManifest(
        context_id=(
            "proposal-node-context."
            f"{exact_bundle.content_sha256[:16]}."
            f"{hashlib.sha256(node_id.encode('utf-8')).hexdigest()[:16]}"
        ),
        bundle_sha256=exact_bundle.content_sha256,
        compilation_sha256=exact_bundle.compilation.content_sha256,
        session_plan_sha256=exact_bundle.session_plan.content_sha256,
        proposal_graph_sha256=graph.content_sha256,
        source_scope_manifest_sha256=(exact_bundle.compilation.source_scope_manifest.content_sha256),
        source_task_package_sha256=source_package_sha256,
        node_id=node_id,
        node_spec_sha256=canonical_json_sha256(node.model_dump(mode="json")),
        node_scope_sha256=node_scope.content_sha256,
        instruction_visibility=node_scope.instruction_visibility,
        artifacts=tuple(artifact for artifact, _ in materialized),
    )
    _publish_workspace(
        workspace=workspace,
        materialized=tuple(materialized),
        manifest=manifest,
    )
    return manifest


def _assert_fresh_workspace(workspace: Path) -> None:
    if workspace.exists() or workspace.is_symlink():
        raise ProposalNodeContextError("proposal node invocation requires a fresh, previously absent workspace")
    if not workspace.name:
        raise ProposalNodeContextError("proposal node invocation workspace must have a concrete leaf name")


def _validate_exact_bundle(
    bundle: ProposalRunSessionBundle,
) -> ProposalRunSessionBundle:
    try:
        exact = ProposalRunSessionBundle.model_validate(bundle.model_dump(mode="python"))
    except ValueError as error:
        raise ProposalNodeContextError(f"proposal session bundle is not exact: {error}") from error
    if exact != bundle:
        raise ProposalNodeContextError("proposal session bundle changed during context validation")
    return exact


def _resolve_node(
    bundle: ProposalRunSessionBundle,
    *,
    node_id: str,
) -> tuple[
    SemanticSubtaskSpec | FinalSynthesisSpec,
    CompiledNodeContextScope,
]:
    graph = bundle.compilation.proposal_graph
    node: SemanticSubtaskSpec | FinalSynthesisSpec | None = next(
        (candidate for candidate in graph.semantic_subtasks if candidate.node_id == node_id),
        None,
    )
    if node is None and graph.finalizer.node_id == node_id:
        node = graph.finalizer
    scope = next(
        (
            candidate
            for candidate in bundle.compilation.source_scope_manifest.node_scopes
            if candidate.node_id == node_id
        ),
        None,
    )
    if node is None or scope is None:
        raise ProposalNodeContextError(f"node {node_id!r} is outside the exact proposal session plan")
    is_finalizer = node_id == graph.finalizer.node_id
    expected_visibility = (
        NodeInstructionVisibility.PUBLIC_TASK if is_finalizer else NodeInstructionVisibility.OBJECTIVE_ONLY
    )
    if scope.instruction_visibility is not expected_visibility:
        raise ProposalNodeContextError(f"node {node_id!r} has an invalid instruction-visibility scope")
    return node, scope


def _assert_workspace_disjoint_from_source(
    *,
    workspace: Path,
    source_task_root: Path,
) -> None:
    resolved_workspace = workspace.resolve(strict=False)
    if resolved_workspace.is_relative_to(source_task_root) or source_task_root.is_relative_to(resolved_workspace):
        raise ProposalNodeContextError("proposal invocation workspace must be disjoint from the frozen source task")


def _validate_source_task_root(
    source_task_root: Path,
    *,
    task_snapshot: TaskSnapshotRef,
) -> tuple[Path, str]:
    root = Path(source_task_root)
    if root.is_symlink():
        raise ProposalNodeContextError("source task package root must not be a symbolic link")
    try:
        resolved = root.resolve(strict=True)
    except OSError as error:
        raise ProposalNodeContextError(f"source task package root cannot be resolved: {error}") from error
    if not resolved.is_dir():
        raise ProposalNodeContextError("source task package root must be a directory")
    observed = _source_task_package_sha256(resolved)
    try:
        assert_task_snapshot_matches_directory(reference=task_snapshot, task_dir=resolved)
    except (OSError, TaskSnapshotError, ValueError) as error:
        raise ProposalNodeContextError("source task package does not match the exact task reference") from error
    return resolved, observed


def _source_task_package_sha256(source_task_root: Path) -> str:
    try:
        return source_task_package_sha256(source_task_root)
    except ProposalTaskPackageError as error:
        raise ProposalNodeContextError(f"source task package is invalid: {error}") from error


def _validate_upstream_set(
    *,
    expected_handoff_ids: tuple[str, ...],
    artifacts: tuple[PersistedProposalHandoffArtifact, ...],
) -> dict[str, PersistedProposalHandoffArtifact]:
    try:
        exact_artifacts = tuple(
            PersistedProposalHandoffArtifact.model_validate(artifact.model_dump(mode="python"))
            for artifact in artifacts
        )
    except ValueError as error:
        raise ProposalNodeContextError(f"persisted upstream handoff reference is invalid: {error}") from error
    actual_ids = tuple(artifact.handoff_id for artifact in exact_artifacts)
    if len(actual_ids) != len(set(actual_ids)):
        raise ProposalNodeContextError("upstream handoff artifacts contain duplicate identities")
    missing = tuple(sorted(set(expected_handoff_ids) - set(actual_ids)))
    extra = tuple(sorted(set(actual_ids) - set(expected_handoff_ids)))
    if missing:
        raise ProposalNodeContextError("missing upstream handoff artifacts: " + ", ".join(missing))
    if extra:
        raise ProposalNodeContextError("extra upstream handoff artifacts: " + ", ".join(extra))
    return {
        artifact.handoff_id: artifact
        for artifact in sorted(
            exact_artifacts,
            key=lambda item: item.handoff_id,
        )
    }


def _instruction_bytes(
    *,
    bundle: ProposalRunSessionBundle,
    node_id: str,
    node_objective: str,
    visibility: NodeInstructionVisibility,
) -> bytes:
    if visibility is NodeInstructionVisibility.OBJECTIVE_ONLY:
        instruction = node_objective
    elif visibility is NodeInstructionVisibility.PUBLIC_TASK:
        instruction = bundle.compilation.proposal_freeze.problem_view.public_instruction
    else:
        raise ProposalNodeContextError(f"node {node_id!r} has unsupported instruction visibility")
    return instruction.encode("utf-8")


def _read_exact_source(
    *,
    source_root: Path,
    materialization: ScopedSourceMaterialization,
) -> bytes:
    relative_path = _assert_public_source_path(materialization.task_relative_path)
    candidate = source_root.joinpath(*relative_path.parts)
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ProposalNodeContextError(
            f"public source {materialization.source_id!r} cannot be resolved: {error}"
        ) from error
    if not resolved.is_relative_to(source_root):
        raise ProposalNodeContextError(f"public source {materialization.source_id!r} escapes the source task root")
    content = _read_regular_file(
        resolved,
        label=f"public source {materialization.source_id!r}",
    )
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if observed_sha256 != materialization.source_sha256:
        raise ProposalNodeContextError(
            f"public source {materialization.source_id!r} SHA does not match its frozen manifest"
        )
    if len(content) != materialization.byte_size:
        raise ProposalNodeContextError(
            f"public source {materialization.source_id!r} size does not match its frozen manifest"
        )
    return content


def _read_exact_handoff(
    artifact: PersistedProposalHandoffArtifact,
    *,
    source_task_root: Path,
) -> bytes:
    path = Path(artifact.artifact_path)
    if path.is_symlink():
        raise ProposalNodeContextError(f"upstream handoff {artifact.handoff_id!r} must not be a symbolic link")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise ProposalNodeContextError(
            f"upstream handoff {artifact.handoff_id!r} cannot be resolved: {error}"
        ) from error
    if resolved.is_relative_to(source_task_root):
        raise ProposalNodeContextError(
            f"upstream handoff {artifact.handoff_id!r} cannot read from the source task package"
        )
    _assert_not_forbidden_path(
        resolved,
        split_parent_tokens=False,
    )
    content = _read_regular_file(
        resolved,
        label=f"upstream handoff {artifact.handoff_id!r}",
    )
    observed_sha256 = hashlib.sha256(content).hexdigest()
    if observed_sha256 != artifact.artifact_sha256:
        raise ProposalNodeContextError(
            f"upstream handoff {artifact.handoff_id!r} SHA does not match its persisted reference"
        )
    if len(content) != artifact.byte_size:
        raise ProposalNodeContextError(
            f"upstream handoff {artifact.handoff_id!r} size does not match its persisted reference"
        )
    return content


def _read_regular_file(path: Path, *, label: str) -> bytes:
    if path.is_symlink():
        raise ProposalNodeContextError(f"{label} must not be a symbolic link")
    try:
        path_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalNodeContextError(f"{label} cannot be inspected: {error}") from error
    if not stat.S_ISREG(path_stat.st_mode):
        raise ProposalNodeContextError(f"{label} must be a regular file")
    try:
        return path.read_bytes()
    except OSError as error:
        raise ProposalNodeContextError(f"{label} cannot be read: {error}") from error


def _assert_public_source_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ProposalNodeContextError(f"public source path is forbidden or escapes containment: {value!r}")
    _assert_not_forbidden_path(path)
    return path


def _assert_not_forbidden_path(
    path: PurePosixPath | Path,
    *,
    split_parent_tokens: bool = True,
) -> None:
    for index, part in enumerate(path.parts):
        normalized = part.casefold()
        tokens = set(re.split(r"[-_.]+", normalized))
        if (
            normalized in _FORBIDDEN_FILE_NAMES
            or normalized in _FORBIDDEN_PATH_TOKENS
            or ((split_parent_tokens or index == len(path.parts) - 1) and tokens & _FORBIDDEN_PATH_TOKENS)
        ):
            raise ProposalNodeContextError(f"context materialization rejects forbidden path component {part!r}")


def _context_artifact(
    *,
    kind: ProposalNodeContextArtifactKind,
    logical_id: str,
    workspace_relative_path: str,
    content: bytes,
) -> ProposalNodeContextArtifact:
    return ProposalNodeContextArtifact(
        kind=kind,
        logical_id=logical_id,
        workspace_relative_path=workspace_relative_path,
        artifact_sha256=hashlib.sha256(content).hexdigest(),
        byte_size=len(content),
    )


def _publish_workspace(
    *,
    workspace: Path,
    materialized: tuple[
        tuple[ProposalNodeContextArtifact, bytes],
        ...,
    ],
    manifest: ProposalNodeContextManifest,
) -> None:
    workspace.parent.mkdir(parents=True, exist_ok=True)
    if workspace.exists() or workspace.is_symlink():
        raise ProposalNodeContextError("proposal node invocation workspace ceased to be fresh before publication")
    try:
        workspace.mkdir(mode=0o700)
        for artifact, content in materialized:
            target = workspace.joinpath(*PurePosixPath(artifact.workspace_relative_path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
            persisted = target.read_bytes()
            if (
                hashlib.sha256(persisted).hexdigest() != artifact.artifact_sha256
                or len(persisted) != artifact.byte_size
            ):
                raise ProposalNodeContextError(f"published context artifact changed: {artifact.logical_id}")
        manifest_bytes = (
            json.dumps(
                manifest.model_dump(mode="json"),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode("utf-8")
        manifest_path = workspace / _MANIFEST_PATH
        manifest_path.write_bytes(manifest_bytes)
        persisted_manifest = ProposalNodeContextManifest.model_validate_json(manifest_path.read_bytes())
        if persisted_manifest != manifest:
            raise ProposalNodeContextError("published node-context manifest changed after materialization")
    except Exception as error:
        if workspace.exists() and not workspace.is_symlink():
            shutil.rmtree(workspace)
        if isinstance(error, ProposalNodeContextError):
            raise
        raise ProposalNodeContextError(f"node context workspace could not be published: {error}") from error
