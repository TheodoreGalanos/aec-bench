# ABOUTME: Tests the legacy self-addressed reader and current plain domain contracts.
# ABOUTME: Prevents ambient model hashes from returning to Kernel, Harness, evaluation, and run bundles.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from aec_bench.contracts.commitments import canonical_json_sha256
from aec_bench.contracts.evaluation_outcome import EvaluationOutcome
from aec_bench.contracts.evaluation_plane import CriticSpec, EvaluationPlan
from aec_bench.contracts.execution_program import CompiledExecutionProgram, ExecutionProgram
from aec_bench.contracts.harness_instance import CompiledHarnessInstance, HarnessRecipe
from aec_bench.contracts.harness_kernel import KernelCapabilitySpec, KernelManifest
from aec_bench.contracts.legacy_content_address import (
    LegacyContentAddressedModel,
    read_legacy_content_addressed_model,
)
from aec_bench.contracts.run_bundle import RunBundle, TaskReviewSnapshotRef, TaskSnapshotRef
from aec_bench.contracts.stage_execution import (
    DeclaredStageGraph,
    StageContextManifest,
    StageExecutionReceipt,
    StageOutput,
)
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.harness.program_execution.contracts import ProgramExecutionResult
from aec_bench.ledger.immutable_artifact_store import ImmutableArtifactIntegrityError, ImmutableArtifactStore


class _CurrentRecord(FrozenStrictModel):
    record_id: str
    values: tuple[int, ...]


def _legacy_payload() -> dict[str, object]:
    body: dict[str, object] = {"record_id": "record-1", "values": [1, 2, 3]}
    return {**body, "content_sha256": canonical_json_sha256(body)}


def test_legacy_reader_validates_digest_and_returns_plain_current_model() -> None:
    payload = _legacy_payload()

    record = read_legacy_content_addressed_model(
        json.dumps(payload, sort_keys=True).encode("utf-8"),
        TypeAdapter(_CurrentRecord),
    )

    assert record == _CurrentRecord(record_id="record-1", values=(1, 2, 3))
    assert "content_sha256" not in record.model_dump(mode="json")


def test_legacy_store_reader_returns_plain_current_model(tmp_path: Path) -> None:
    store = ImmutableArtifactStore(tmp_path / "artifacts")
    encoded = json.dumps(_legacy_payload(), sort_keys=True).encode("utf-8")
    store.publish_bytes("legacy/record.json", encoded)

    record = store.load_legacy_model("legacy/record.json", TypeAdapter(_CurrentRecord))

    assert record == _CurrentRecord(record_id="record-1", values=(1, 2, 3))


def test_legacy_store_reader_rejects_corrupted_embedded_digest(tmp_path: Path) -> None:
    store = ImmutableArtifactStore(tmp_path / "artifacts")
    payload = {**_legacy_payload(), "record_id": "changed"}
    store.publish_bytes("legacy/record.json", json.dumps(payload, sort_keys=True).encode("utf-8"))

    with pytest.raises(ImmutableArtifactIntegrityError, match="legacy content_sha256 does not match"):
        store.load_legacy_model("legacy/record.json", TypeAdapter(_CurrentRecord))


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"record_id": "record-1", "values": [1, 2, 3]}, "must include content_sha256"),
        (
            {**_legacy_payload(), "record_id": "changed"},
            "does not match canonical model content",
        ),
    ],
)
def test_legacy_reader_rejects_missing_or_corrupted_digest(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        read_legacy_content_addressed_model(payload, TypeAdapter(_CurrentRecord))


@pytest.mark.parametrize(
    "contract_type",
    [
        KernelCapabilitySpec,
        KernelManifest,
        HarnessRecipe,
        CompiledHarnessInstance,
        ExecutionProgram,
        CompiledExecutionProgram,
        CriticSpec,
        EvaluationPlan,
        EvaluationOutcome,
        RunBundle,
        TaskReviewSnapshotRef,
        TaskSnapshotRef,
        DeclaredStageGraph,
        StageContextManifest,
        StageOutput,
        StageExecutionReceipt,
        ProgramExecutionResult,
    ],
)
def test_current_execution_contracts_have_no_ambient_content_address(contract_type: type[FrozenStrictModel]) -> None:
    assert not issubclass(contract_type, LegacyContentAddressedModel)
    assert "content_sha256" not in contract_type.model_fields
