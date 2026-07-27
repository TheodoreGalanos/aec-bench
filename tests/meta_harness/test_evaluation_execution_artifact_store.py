# ABOUTME: Tests the phase-neutral execution artifact store with real immutable evidence.
# ABOUTME: Covers binding, extensions, terminal claims, replay, and first-writer collisions.

from __future__ import annotations

from typing import Literal

import pytest
from pydantic import TypeAdapter, field_validator

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
    validate_sha256,
)
from aec_bench.meta_harness.evaluation_execution_artifact_store import (
    EvaluationExecutionArtifactStore,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
)


class _Binding(ContentAddressedModel):
    schema_version: Literal["test.evaluation-binding.v1"] = "test.evaluation-binding.v1"
    execution_id: str


class _Extension(ContentAddressedModel):
    schema_version: Literal["test.evaluation-extension.v1"] = "test.evaluation-extension.v1"
    step: str


class _Terminal(ContentAddressedModel):
    schema_version: Literal["test.evaluation-terminal.v1"] = "test.evaluation-terminal.v1"
    execution_id: str
    result: str


class _TerminalClaim(ContentAddressedModel):
    schema_version: Literal["test.evaluation-terminal-claim.v1"] = "test.evaluation-terminal-claim.v1"
    execution_id: str
    terminal_sha256: str

    @field_validator("terminal_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return validate_sha256(value)


def test_execution_artifact_store_persists_and_replays_one_bound_terminal(
    tmp_path,
) -> None:
    repository = EvidenceRepository(tmp_path / "execution")
    binding = _Binding(execution_id="execution.generic")
    store = EvaluationExecutionArtifactStore.bind(
        artifacts=repository,
        binding=binding,
        binding_path="orchestration/binding.json",
        binding_adapter=TypeAdapter(_Binding),
    )
    extension = _Extension(step="prepared")
    terminal = _Terminal(
        execution_id=binding.execution_id,
        result="completed",
    )
    claim = _TerminalClaim(
        execution_id=binding.execution_id,
        terminal_sha256=terminal.content_sha256,
    )

    assert (
        store.persist_extension(
            relative_path="orchestration/extension.json",
            model=extension,
            adapter=TypeAdapter(_Extension),
        )
        == extension
    )
    assert (
        store.persist_claimed_terminal(
            terminal=terminal,
            terminal_adapter=TypeAdapter(_Terminal),
            object_collection="terminal/objects",
            object_filename="report.json",
            claim=claim,
            claim_adapter=TypeAdapter(_TerminalClaim),
            claim_collection="terminal/claims",
            claim_identity=binding.execution_id,
            claim_filename="claim.json",
        )
        == terminal
    )

    replayed = EvaluationExecutionArtifactStore.replay(
        artifacts=EvidenceRepository(tmp_path / "execution"),
        binding_path="orchestration/binding.json",
        binding_adapter=TypeAdapter(_Binding),
    )
    assert replayed.binding == binding
    assert (
        replayed.load_extension(
            relative_path="orchestration/extension.json",
            adapter=TypeAdapter(_Extension),
        )
        == extension
    )
    assert (
        replayed.load_claimed_terminal(
            terminal_adapter=TypeAdapter(_Terminal),
            object_collection="terminal/objects",
            object_filename="report.json",
            claim_adapter=TypeAdapter(_TerminalClaim),
            claim_collection="terminal/claims",
            claim_identity=binding.execution_id,
            claim_filename="claim.json",
            terminal_sha256=lambda selected: selected.terminal_sha256,
        )
        == terminal
    )

    with pytest.raises(ImmutableArtifactCollisionError):
        replayed.persist_extension(
            relative_path="orchestration/extension.json",
            model=_Extension(step="different"),
            adapter=TypeAdapter(_Extension),
        )
