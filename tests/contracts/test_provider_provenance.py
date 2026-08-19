# ABOUTME: Tests exact provider source, runtime, and qualification provenance contracts.
# ABOUTME: Prevents source ambiguity and unsupported live-provider qualification claims.

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.artifacts import ArtifactRef
from aec_bench.contracts.provider_provenance import (
    ProviderAdapterIdentity,
    ProviderQualificationCell,
    ResolvedRuntimeIdentity,
)


def _artifact(artifact_id: str = "provider/evidence.json") -> ArtifactRef:
    return ArtifactRef(
        artifact_id=artifact_id,
        sha256="a" * 64,
        size_bytes=12,
        media_type="application/json",
    )


def _adapter() -> ProviderAdapterIdentity:
    return ProviderAdapterIdentity(
        adapter_id="deepseek-harness",
        package_version="0.1.0",
        source_revision="b" * 40,
    )


def _runtime(name: str) -> ResolvedRuntimeIdentity:
    return ResolvedRuntimeIdentity(
        distribution_name=name,
        distribution_version="0.1.0rc6",
        reported_version="0.1.0rc6",
    )


def test_adapter_identity_requires_one_reconstructive_source_identity() -> None:
    revision = _adapter()
    snapshot = ProviderAdapterIdentity(
        adapter_id="deepseek-harness",
        package_version="0.1.0",
        source_snapshot=_artifact("provider/source.tar"),
    )

    assert revision.source_revision == "b" * 40
    assert snapshot.source_snapshot is not None
    with pytest.raises(ValidationError, match="exactly one source revision or source snapshot"):
        ProviderAdapterIdentity(adapter_id="deepseek-harness", package_version="0.1.0")
    with pytest.raises(ValidationError, match="exactly one source revision or source snapshot"):
        ProviderAdapterIdentity(
            adapter_id="deepseek-harness",
            package_version="0.1.0",
            source_revision="b" * 40,
            source_snapshot=_artifact("provider/source.tar"),
        )
    with pytest.raises(ValidationError, match="40-character Git commit"):
        ProviderAdapterIdentity(
            adapter_id="deepseek-harness",
            package_version="0.1.0",
            source_revision="short",
        )


def test_qualification_keeps_keyless_and_live_evidence_explicit() -> None:
    qualified = ProviderQualificationCell(
        provider_route="azure",
        feature="keyless_protocol",
        adapter_identity=_adapter(),
        sdk=_runtime("deepseek-harness-sdk"),
        runtime=_runtime("deepseek-harness-runtime-bin"),
        evidence_level="keyless",
        status="qualified",
        evidence=(_artifact(),),
        qualified_at=datetime(2026, 8, 17, tzinfo=UTC),
    )
    partial = ProviderQualificationCell(
        provider_route="azure",
        feature="live_basic",
        adapter_identity=_adapter(),
        sdk=_runtime("deepseek-harness-sdk"),
        runtime=_runtime("deepseek-harness-runtime-bin"),
        evidence_level="live",
        status="partial",
        reason="No retained credentialed provider evidence is available.",
    )

    assert qualified.evidence_level == "keyless"
    assert partial.evidence_level == "live"
    with pytest.raises(ValidationError, match="requires retained evidence and an event time"):
        ProviderQualificationCell(
            provider_route="azure",
            feature="live_basic",
            adapter_identity=_adapter(),
            sdk=_runtime("deepseek-harness-sdk"),
            runtime=_runtime("deepseek-harness-runtime-bin"),
            evidence_level="live",
            status="qualified",
        )
