# ABOUTME: Owns deterministic motif archives and content-addressed filesystem persistence.
# ABOUTME: Verifies physical and semantic archive identity when saving or loading motif records.

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import field_validator, model_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import FrozenStrictModel, NonEmptyStr
from aec_bench.experimentation.governance.motifs.contracts import (
    HarnessProgramMotif,
    MotifApplicabilityDescriptor,
    MotifStatus,
    MotifStructuralDescriptor,
    _canonical_json,
    _canonical_sha256,
    _validate_sha256,
)


class MotifLibrary(FrozenStrictModel):
    """Deterministic content-addressed archive of immutable motif records."""

    schema_version: Literal["1"] = "1"
    archive_sha256: NonEmptyStr
    motifs: tuple[HarnessProgramMotif, ...]

    @field_validator("archive_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("motifs")
    @classmethod
    def canonicalize_motifs(
        cls,
        value: tuple[HarnessProgramMotif, ...],
    ) -> tuple[HarnessProgramMotif, ...]:
        ordered = tuple(sorted(value, key=lambda motif: motif.motif_sha256))
        addresses = [motif.motif_sha256 for motif in ordered]
        if len(addresses) != len(set(addresses)):
            raise ValueError("motif library cannot contain duplicate motif addresses")
        return ordered

    @model_validator(mode="after")
    def validate_archive(self) -> MotifLibrary:
        expected = _canonical_sha256(self.model_dump(mode="json", exclude={"archive_sha256"}))
        if self.archive_sha256 != expected:
            raise ValueError("archive_sha256 must bind the canonical motif library")
        return self

    @classmethod
    def create(cls, motifs: tuple[HarnessProgramMotif, ...] = ()) -> MotifLibrary:
        ordered = tuple(sorted(motifs, key=lambda motif: motif.motif_sha256))
        payload: dict[str, Any] = {
            "schema_version": "1",
            "motifs": [motif.model_dump(mode="json") for motif in ordered],
        }
        return cls(archive_sha256=_canonical_sha256(payload), **payload)

    def add(self, motif: HarnessProgramMotif) -> MotifLibrary:
        """Return a new archive containing the motif; exact repeated adds are idempotent."""

        normalized = HarnessProgramMotif.model_validate(motif.model_dump(mode="json"))
        if any(existing.motif_sha256 == normalized.motif_sha256 for existing in self.motifs):
            return self
        return MotifLibrary.create((*self.motifs, normalized))

    def query(
        self,
        *,
        kernel_abi_sha256: str | None = None,
        applicability: MotifApplicabilityDescriptor | None = None,
        descriptor: MotifStructuralDescriptor | None = None,
        statuses: tuple[MotifStatus | str, ...] | None = None,
        include_retired: bool = False,
        limit: int | None = None,
    ) -> tuple[HarnessProgramMotif, ...]:
        """Return deterministic quality-ranked matches without using reward as a descriptor axis."""

        if kernel_abi_sha256 is not None:
            _validate_sha256(kernel_abi_sha256)
        if limit is not None and (isinstance(limit, bool) or limit < 1):
            raise ValueError("motif query limit must be a positive integer")
        selected_statuses = None if statuses is None else {MotifStatus(status) for status in statuses}
        matches = [
            motif
            for motif in self.motifs
            if (kernel_abi_sha256 is None or motif.kernel_abi_sha256 == kernel_abi_sha256)
            and (applicability is None or motif.applicability == applicability)
            and (descriptor is None or motif.descriptor == descriptor)
            and (selected_statuses is None or motif.status in selected_statuses)
            and (include_retired or selected_statuses is not None or motif.status is not MotifStatus.RETIRED)
        ]
        ordered = tuple(sorted(matches, key=_motif_query_key))
        return ordered if limit is None else ordered[:limit]

    def save(self, path: Path) -> None:
        """Write canonical JSON whose archive and nested record hashes can be verified on load."""

        normalized = MotifLibrary.model_validate(self.model_dump(mode="json"))
        path.write_text(_canonical_json(normalized.model_dump(mode="json")) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> MotifLibrary:
        """Load and verify a saved archive, returning an empty archive when none exists."""

        if not path.exists():
            return cls.create()
        return cls.model_validate_json(path.read_text(encoding="utf-8"))


class MotifLibraryArtifact(FrozenStrictModel):
    """Physical and semantic pin for one immutable motif-library archive."""

    artifact: ArtifactReference
    archive_sha256: NonEmptyStr

    @field_validator("archive_sha256")
    @classmethod
    def validate_archive_sha256(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def validate_artifact_kind(self) -> MotifLibraryArtifact:
        if self.artifact.kind != "motif-library":
            raise ValueError("pinned motif library requires a motif-library artifact")
        return self


def write_motif_library_artifact(
    library: MotifLibrary,
    *,
    artifacts_root: Path,
) -> MotifLibraryArtifact:
    """Persist and reload one explicit motif archive without an implicit empty fallback."""

    normalized = MotifLibrary.model_validate(library.model_dump(mode="json"))
    encoded = (_canonical_json(normalized.model_dump(mode="json")) + "\n").encode("utf-8")
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    path = Path(artifacts_root) / normalized.archive_sha256 / "motif-library.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != encoded:
        raise ValueError("content-addressed motif library path contains different bytes")
    if not path.exists():
        path.write_bytes(encoded)
    pin = MotifLibraryArtifact(
        artifact=ArtifactReference(
            kind="motif-library",
            path=str(path),
            sha256=physical_sha256,
            media_type="application/json",
        ),
        archive_sha256=normalized.archive_sha256,
    )
    if load_pinned_motif_library(pin) != normalized:
        raise ValueError("persisted motif library differs from its source archive")
    return pin


def load_pinned_motif_library(pin: MotifLibraryArtifact) -> MotifLibrary:
    """Load one exact archive and fail closed on missing, changed, or semantically different bytes."""

    source = MotifLibraryArtifact.model_validate(pin.model_dump(mode="python"))
    path = Path(source.artifact.path)
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != source.artifact.sha256:
        raise ValueError("motif library artifact digest mismatch")
    try:
        library = MotifLibrary.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception as error:
        raise ValueError("pinned motif library artifact is invalid") from error
    if library.archive_sha256 != source.archive_sha256:
        raise ValueError("pinned motif library semantic archive identity mismatch")
    return library


def _motif_query_key(motif: HarnessProgramMotif) -> tuple[float, float, float, str]:
    objective = motif.objective_reward
    validity = motif.validity_rate
    return (
        math.inf if objective is None else -objective,
        math.inf if validity is None else -validity,
        motif.estimated_cost_usd,
        motif.motif_sha256,
    )
