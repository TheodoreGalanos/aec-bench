# ABOUTME: Tests for the TraceDataset contract models.
# ABOUTME: Validates schema, immutability, and content hashing for training dataset manifests.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.trace_dataset import (
    DatasetVariant,
    TraceDatasetEntry,
    TraceDatasetManifest,
    TraceDatasetVariant,
    compute_manifest_hash,
)


class TestDatasetVariantEnum:
    def test_full_variant(self) -> None:
        assert DatasetVariant.FULL == "full"

    def test_sft_memento_variant(self) -> None:
        assert DatasetVariant.SFT_MEMENTO == "sft_memento"

    def test_rl_memento_variant(self) -> None:
        assert DatasetVariant.RL_MEMENTO == "rl_memento"


class TestTraceDatasetVariant:
    def test_full_variant_no_transform(self) -> None:
        v = TraceDatasetVariant(
            name="full",
            path=Path("traces/full.jsonl"),
            transform=None,
            compression_ratio=None,
            metadata={},
        )
        assert v.transform is None
        assert v.compression_ratio is None

    def test_sft_variant_with_compression(self) -> None:
        v = TraceDatasetVariant(
            name="sft_memento",
            path=Path("traces/sft.jsonl"),
            transform="memento_sft",
            compression_ratio=0.15,
            metadata={"strategy": "dp_semantic"},
        )
        assert v.compression_ratio == 0.15
        assert v.metadata["strategy"] == "dp_semantic"

    def test_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            TraceDatasetVariant(
                name="full",
                path=Path("x.jsonl"),
                transform=None,
                compression_ratio=None,
                metadata={},
                bogus="field",
            )

    def test_frozen(self) -> None:
        v = TraceDatasetVariant(
            name="full",
            path=Path("x.jsonl"),
            transform=None,
            compression_ratio=None,
            metadata={},
        )
        with pytest.raises(ValidationError):
            v.name = "changed"


class TestTraceDatasetEntry:
    def test_entry_with_multiple_variants(self) -> None:
        full = TraceDatasetVariant(
            name="full",
            path=Path("full.jsonl"),
            transform=None,
            compression_ratio=None,
            metadata={},
        )
        sft = TraceDatasetVariant(
            name="sft_memento",
            path=Path("sft.jsonl"),
            transform="memento_sft",
            compression_ratio=0.12,
            metadata={},
        )
        entry = TraceDatasetEntry(
            task_id="voltage-drop-001",
            model="claude-sonnet-4-6",
            source_trace=Path("trajectory.jsonl"),
            variants=[full, sft],
        )
        assert len(entry.variants) == 2
        assert entry.task_id == "voltage-drop-001"


class TestTraceDatasetManifest:
    def test_manifest_creation(self) -> None:
        manifest = TraceDatasetManifest(
            name="test-dataset",
            version="1.0.0",
            entries=[],
            created_at=datetime(2026, 4, 9, tzinfo=UTC),
            content_hash="abc123",
        )
        assert manifest.name == "test-dataset"
        assert manifest.version == "1.0.0"

    def test_manifest_serialisation_roundtrip(self) -> None:
        full = TraceDatasetVariant(
            name="full",
            path=Path("full.jsonl"),
            transform=None,
            compression_ratio=None,
            metadata={},
        )
        entry = TraceDatasetEntry(
            task_id="vd-001",
            model="haiku",
            source_trace=Path("traj.jsonl"),
            variants=[full],
        )
        manifest = TraceDatasetManifest(
            name="ds",
            version="0.1.0",
            entries=[entry],
            created_at=datetime(2026, 4, 9, tzinfo=UTC),
            content_hash="hash",
        )
        data = json.loads(manifest.model_dump_json())
        restored = TraceDatasetManifest.model_validate(data)
        assert restored.entries[0].task_id == "vd-001"


class TestComputeManifestHash:
    def test_deterministic_hash(self) -> None:
        full = TraceDatasetVariant(
            name="full",
            path=Path("full.jsonl"),
            transform=None,
            compression_ratio=None,
            metadata={},
        )
        entry = TraceDatasetEntry(
            task_id="vd-001",
            model="haiku",
            source_trace=Path("traj.jsonl"),
            variants=[full],
        )
        h1 = compute_manifest_hash([entry])
        h2 = compute_manifest_hash([entry])
        assert h1 == h2
        assert len(h1) == 64

    def test_different_entries_different_hash(self) -> None:
        v = TraceDatasetVariant(
            name="full",
            path=Path("full.jsonl"),
            transform=None,
            compression_ratio=None,
            metadata={},
        )
        e1 = TraceDatasetEntry(
            task_id="a",
            model="m",
            source_trace=Path("t.jsonl"),
            variants=[v],
        )
        e2 = TraceDatasetEntry(
            task_id="b",
            model="m",
            source_trace=Path("t.jsonl"),
            variants=[v],
        )
        assert compute_manifest_hash([e1]) != compute_manifest_hash([e2])
