# ABOUTME: Tests exact-byte artifact and authority-evidence reference contracts.
# ABOUTME: Proves strict digest, size, protocol, and immutability rules at the evidence boundary.

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.authority_evidence import (
    ACTOR_INVOCATION_MANIFEST_PROTOCOL,
    AuthorityEvidenceKind,
    AuthorityEvidenceRef,
)


def _artifact_ref() -> ArtifactRef:
    return ArtifactRef(
        artifact_id="artifacts/sha256/aa/" + "a" * 64,
        sha256="a" * 64,
        size_bytes=12,
        media_type="application/json",
    )


def test_artifact_ref_is_strict_and_immutable() -> None:
    reference = _artifact_ref()

    assert reference.sha256 == "a" * 64
    with pytest.raises(ValidationError):
        ArtifactRef.model_validate({**reference.model_dump(), "sha256": "A" * 64})
    with pytest.raises(ValidationError):
        ArtifactRef.model_validate({**reference.model_dump(), "size_bytes": 0})
    with pytest.raises(ValidationError):
        ArtifactRef.model_validate({**reference.model_dump(), "extra": True})
    with pytest.raises(ValidationError):
        reference.size_bytes = 13


def test_authority_evidence_ref_names_the_authority_and_protocol() -> None:
    reference = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
        protocol="aec-bench/actor-invocation-evidence/1",
        artifact=_artifact_ref(),
    )

    assert reference.authority_kind is AuthorityEvidenceKind.ACTOR_INVOCATION
    assert reference.artifact.media_type == "application/json"
    with pytest.raises(ValidationError, match="protocol"):
        AuthorityEvidenceRef.model_validate(
            {
                **reference.model_dump(),
                "protocol": "aec-bench/actor-invocation-evidence/2",
            }
        )


def test_actor_authority_accepts_a_multi_session_manifest() -> None:
    reference = AuthorityEvidenceRef(
        authority_kind=AuthorityEvidenceKind.ACTOR_INVOCATION,
        protocol=ACTOR_INVOCATION_MANIFEST_PROTOCOL,
        artifact=_artifact_ref(),
    )

    assert reference.protocol == "aec-bench/actor-invocation-manifest/1"
