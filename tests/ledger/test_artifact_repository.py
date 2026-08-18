# ABOUTME: Tests the universal exact-byte artifact repository introduced by provenance simplification.
# ABOUTME: Proves canonical model bytes, immutable publication, and fail-closed reference reads.

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

import pytest
from pydantic import BaseModel, ConfigDict, Field

from aec_bench.ledger.artifact_repository import ArtifactRepository, canonical_model_bytes
from aec_bench.ledger.immutable_byte_store import ImmutableArtifactIntegrityError


class _Mode(StrEnum):
    ACTIVE = "active"


class _CanonicalModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=True)

    labels: set[str]
    ordered_values: list[int]
    recorded_at: datetime
    amount: Decimal
    mode: _Mode


class _FloatModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=True)

    value: float


class _AliasedModel(BaseModel):
    internal_name: str = Field(serialization_alias="wire_name")


def test_publish_model_uses_one_documented_canonical_encoding(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path / "artifacts")
    first = _CanonicalModel(
        labels={"zulu", "alpha"},
        ordered_values=[2, 1],
        recorded_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        amount=Decimal("1.2300"),
        mode=_Mode.ACTIVE,
    )
    second = _CanonicalModel(
        labels={"alpha", "zulu"},
        ordered_values=[2, 1],
        recorded_at=datetime(2025, 1, 2, 3, 4, 5, tzinfo=UTC),
        amount=Decimal("1.2300"),
        mode=_Mode.ACTIVE,
    )

    first_ref = repository.publish_model(value=first, media_type="application/json")
    second_ref = repository.publish_model(value=second, media_type="application/json")

    expected = (
        b'{"amount":"1.2300","labels":["alpha","zulu"],"mode":"active",'
        b'"ordered_values":[2,1],"recorded_at":"2025-01-02T03:04:05Z"}\n'
    )
    assert canonical_model_bytes(first) == expected
    assert first_ref == second_ref
    assert repository.read_bytes(first_ref) == expected


def test_list_order_remains_semantic_in_canonical_model_bytes(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path / "artifacts")

    first = repository.publish_model(
        value=_CanonicalModel(
            labels={"alpha"},
            ordered_values=[1, 2],
            recorded_at=datetime(2025, 1, 2, tzinfo=UTC),
            amount=Decimal("2.0"),
            mode=_Mode.ACTIVE,
        ),
        media_type="application/json",
    )
    second = repository.publish_model(
        value=_CanonicalModel(
            labels={"alpha"},
            ordered_values=[2, 1],
            recorded_at=datetime(2025, 1, 2, tzinfo=UTC),
            amount=Decimal("2.0"),
            mode=_Mode.ACTIVE,
        ),
        media_type="application/json",
    )

    assert first.sha256 != second.sha256


def test_canonical_model_bytes_uses_serialization_aliases() -> None:
    assert canonical_model_bytes(_AliasedModel(internal_name="value")) == b'{"wire_name":"value"}\n'


@pytest.mark.parametrize("amount", [Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_canonical_model_bytes_rejects_non_finite_decimals(amount: Decimal) -> None:
    value = _CanonicalModel(
        labels={"alpha"},
        ordered_values=[1],
        recorded_at=datetime(2025, 1, 2, tzinfo=UTC),
        amount=amount,
        mode=_Mode.ACTIVE,
    )

    with pytest.raises(ValueError, match="finite"):
        canonical_model_bytes(value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_canonical_model_bytes_rejects_non_finite_floats(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        canonical_model_bytes(_FloatModel(value=value))


def test_read_bytes_fails_closed_on_size_or_digest_drift(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path / "artifacts")
    reference = repository.publish_bytes(data=b"retained evidence\n", media_type="text/plain")
    artifact_path = repository.root.joinpath(*reference.artifact_id.split("/"))

    artifact_path.write_bytes(b"changed evidence\n")

    with pytest.raises(ImmutableArtifactIntegrityError, match="digest|size"):
        repository.read_bytes(reference)


def test_publish_bytes_is_idempotent_and_rejects_empty_artifacts(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path / "artifacts")

    first = repository.publish_bytes(data=b"same bytes", media_type="application/octet-stream")
    second = repository.publish_bytes(data=b"same bytes", media_type="application/octet-stream")

    assert second == first
    with pytest.raises(ValueError, match="must not be empty"):
        repository.publish_bytes(data=b"", media_type="application/octet-stream")


def test_resolve_ref_accepts_only_a_verified_canonical_artifact_id(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path / "artifacts")
    published = repository.publish_bytes(data=b"published regime\n", media_type="application/json")

    assert repository.resolve_ref(artifact_id=published.artifact_id, media_type=published.media_type) == published
    with pytest.raises(ImmutableArtifactIntegrityError, match="canonical SHA-256 locator"):
        repository.resolve_ref(
            artifact_id=f"mirror/{published.sha256}",
            media_type=published.media_type,
        )
