# ABOUTME: Defines confined public-source materialization and compiled node context scopes.
# ABOUTME: Keeps host-owned path validation separate from proposal graphs, compilation, and receipts.

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Literal, TypeVar

from pydantic import Field, field_validator

from aec_bench.contracts.harness_kernel import ContentAddressedModel, FrozenStrictModel, validate_sha256
from aec_bench.contracts.proposal_execution_types import NodeInstructionVisibility
from aec_bench.contracts.validators import NonEmptyStr

_ModelT = TypeVar("_ModelT")


class ScopedSourceMaterialization(FrozenStrictModel):
    """Host-only mapping from one public source identity to a contained task path."""

    source_id: NonEmptyStr
    source_sha256: str
    byte_size: int = Field(ge=0)
    task_relative_path: NonEmptyStr

    @field_validator("source_sha256")
    @classmethod
    def validate_source_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("task_relative_path")
    @classmethod
    def validate_task_relative_path(cls, value: str) -> str:
        path = PurePosixPath(value)
        forbidden_names = {
            "expected_answer.json",
            "structured_answer.json",
            "task-review.json",
            "task.toml",
            "world.json",
        }
        forbidden_parts = {
            "gold",
            "hidden",
            "tests",
            "verifier",
            "world",
        }
        normalized_parts = {part.casefold() for part in path.parts}
        if (
            path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.name.casefold() in forbidden_names
            or normalized_parts & forbidden_parts
        ):
            raise ValueError("source materialization requires a contained public source path")
        return value


class CompiledNodeContextScope(ContentAddressedModel):
    """Exact sources, handoffs, and instruction mode materialized for one node."""

    schema_version: Literal["aecbench.compiled-node-context-scope.v1"] = "aecbench.compiled-node-context-scope.v1"
    node_id: NonEmptyStr
    source_ids: tuple[NonEmptyStr, ...] = ()
    upstream_handoff_ids: tuple[NonEmptyStr, ...] = ()
    instruction_visibility: NodeInstructionVisibility

    @field_validator("source_ids", "upstream_handoff_ids")
    @classmethod
    def canonicalize_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return _canonical_unique_strings(value, label="node context scope ids")


class ProposalSourceScopeManifest(ContentAddressedModel):
    """Host-owned source materialization and per-node context scopes."""

    schema_version: Literal["aecbench.proposal-source-scope-manifest.v1"] = "aecbench.proposal-source-scope-manifest.v1"
    proposal_graph_sha256: str
    problem_view_sha256: str
    task_package_sha256: str
    sources: tuple[ScopedSourceMaterialization, ...] = Field(min_length=1)
    node_scopes: tuple[CompiledNodeContextScope, ...] = Field(min_length=1)

    @field_validator(
        "proposal_graph_sha256",
        "problem_view_sha256",
        "task_package_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("sources")
    @classmethod
    def canonicalize_sources(
        cls,
        value: tuple[ScopedSourceMaterialization, ...],
    ) -> tuple[ScopedSourceMaterialization, ...]:
        canonical = _canonical_unique_models(
            value,
            identity="source_id",
            label="source materializations",
        )
        paths = tuple(source.task_relative_path for source in canonical)
        if len(paths) != len(set(paths)):
            raise ValueError("source materialization paths must be unique")
        return canonical

    @field_validator("node_scopes")
    @classmethod
    def canonicalize_node_scopes(
        cls,
        value: tuple[CompiledNodeContextScope, ...],
    ) -> tuple[CompiledNodeContextScope, ...]:
        return _canonical_unique_models(
            value,
            identity="node_id",
            label="compiled node context scopes",
        )


def _canonical_unique_strings(
    value: tuple[str, ...],
    *,
    label: str,
) -> tuple[str, ...]:
    if len(value) != len(set(value)):
        raise ValueError(f"{label} must be unique")
    return tuple(sorted(value))


def _canonical_unique_models(
    value: tuple[_ModelT, ...],
    *,
    identity: str,
    label: str,
) -> tuple[_ModelT, ...]:
    identities = [getattr(item, identity) for item in value]
    if len(identities) != len(set(identities)):
        raise ValueError(f"{label} must be unique by {identity}")
    return tuple(sorted(value, key=lambda item: getattr(item, identity)))
