# ABOUTME: Tests confined immutable publication and exact typed artifact reload in the ledger owner.
# ABOUTME: Proves canonical replay, collision rejection, and symbolic-link confinement.

from __future__ import annotations

import hashlib
import json
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from pydantic import TypeAdapter

import aec_bench.ledger.immutable_artifact_store as store_runtime
from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.ledger.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifact,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
    ImmutableArtifactStore,
)
from aec_bench.ledger.immutable_byte_store import (
    ImmutableArtifact as LowerImmutableArtifact,
)
from aec_bench.ledger.immutable_byte_store import (
    ImmutableArtifactCollisionError as LowerImmutableArtifactCollisionError,
)
from aec_bench.ledger.immutable_byte_store import (
    ImmutableArtifactConfinementError as LowerImmutableArtifactConfinementError,
)
from aec_bench.ledger.immutable_byte_store import (
    ImmutableArtifactIntegrityError as LowerImmutableArtifactIntegrityError,
)
from aec_bench.ledger.immutable_byte_store import ImmutableByteStore


class _Artifact(ContentAddressedModel):
    schema_version: str = "test.immutable-artifact.v1"
    label: str


class _ArtifactClaim(ContentAddressedModel):
    schema_version: str = "test.immutable-artifact-claim.v1"
    target_content_sha256: str


def test_meta_harness_store_is_a_compatible_policy_facade_over_lower_bytes() -> None:
    assert issubclass(ImmutableArtifactStore, ImmutableByteStore)
    assert ImmutableArtifact is LowerImmutableArtifact
    assert ImmutableArtifactCollisionError is LowerImmutableArtifactCollisionError
    assert ImmutableArtifactConfinementError is LowerImmutableArtifactConfinementError
    assert ImmutableArtifactIntegrityError is LowerImmutableArtifactIntegrityError


def test_publishes_and_reloads_exact_model_and_bytes(tmp_path: Path) -> None:
    store = ImmutableArtifactStore(tmp_path / "store")
    artifact = _Artifact(label="alpha")

    selected = store.publish_model(
        "models/alpha.json",
        artifact,
        TypeAdapter(_Artifact),
    )
    replayed = store.load_model(
        "models/alpha.json",
        TypeAdapter(_Artifact),
    )
    raw = store.publish_bytes("raw/value.json", b'{"value":1}\n')

    assert selected == artifact
    assert replayed == artifact
    assert raw.sha256 == hashlib.sha256(b'{"value":1}\n').hexdigest()
    assert store.publish_bytes("raw/value.json", b'{"value":1}\n') == raw


def test_rejects_collisions_and_symlink_escape(tmp_path: Path) -> None:
    store = ImmutableArtifactStore(tmp_path / "store")
    store.publish_bytes("value.json", b"first")

    with pytest.raises(ImmutableArtifactCollisionError, match="collision"):
        store.publish_bytes("value.json", b"second")

    outside = tmp_path / "outside"
    outside.mkdir()
    (store.root / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ImmutableArtifactConfinementError, match="symbolic"):
        store.publish_bytes("linked/escape.json", b"forbidden")


def test_evidence_repository_publishes_content_models_and_logical_claims(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository(tmp_path / "evidence", host_private=True)
    artifact = _Artifact(label="alpha")
    adapter = TypeAdapter(_Artifact)
    stored = repository.publish_content_addressed_model(
        collection="artifacts",
        filename="artifact.json",
        model=artifact,
        adapter=adapter,
    )
    claim = _ArtifactClaim(target_content_sha256=artifact.content_sha256)
    claim_adapter = TypeAdapter(_ArtifactClaim)
    logical_identity = {
        "namespace": "artifact",
        "logical_id": "alpha",
    }
    claimed = repository.publish_logical_model(
        collection="claims",
        logical_identity=logical_identity,
        filename="claim.json",
        model=claim,
        adapter=claim_adapter,
    )

    expected_claim_digest = hashlib.sha256(
        b'{"logical_id":"alpha","namespace":"artifact"}',
    ).hexdigest()
    assert stored.model == artifact
    assert stored.artifact.path == (repository.root / "artifacts" / artifact.content_sha256 / "artifact.json")
    assert claimed.model == claim
    assert claimed.artifact.path == (repository.root / "claims" / expected_claim_digest / "claim.json")
    assert (
        repository.load_content_addressed_model(
            collection="artifacts",
            content_sha256=artifact.content_sha256,
            filename="artifact.json",
            adapter=adapter,
        ).model
        == artifact
    )
    assert (
        repository.load_logical_model(
            collection="claims",
            logical_identity=logical_identity,
            filename="claim.json",
            adapter=claim_adapter,
        ).model
        == claim
    )
    assert repository.root.stat().st_mode & 0o077 == 0

    with pytest.raises(ImmutableArtifactCollisionError, match="collision"):
        repository.publish_logical_model(
            collection="claims",
            logical_identity=logical_identity,
            filename="claim.json",
            model=_ArtifactClaim(target_content_sha256="a" * 64),
            adapter=claim_adapter,
        )


def test_meta_facade_rechecks_disjoint_roots_during_descriptor_bound_creation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    safe_parent = tmp_path / "safe"
    safe_parent.mkdir()
    original_parent = tmp_path / "original-safe"
    protected = tmp_path / "protected"
    protected.mkdir()
    selected = safe_parent / "evidence"
    original_validate = store_runtime.validate_evidence_root

    def validate_and_swap(
        root: Path,
        *,
        disjoint_roots: tuple[Path, ...] = (),
        must_exist: bool = False,
    ) -> Path:
        validated = original_validate(
            root,
            disjoint_roots=disjoint_roots,
            must_exist=must_exist,
        )
        safe_parent.rename(original_parent)
        safe_parent.symlink_to(protected, target_is_directory=True)
        return validated

    monkeypatch.setattr(store_runtime, "validate_evidence_root", validate_and_swap)

    with pytest.raises(ImmutableArtifactConfinementError, match="overlap"):
        ImmutableArtifactStore(
            selected,
            disjoint_roots=(protected,),
        )

    assert not (protected / "evidence").exists()


def test_evidence_repository_revalidates_digests_and_disjoint_roots(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    with pytest.raises(ImmutableArtifactConfinementError, match="overlap"):
        EvidenceRepository(
            candidate_root / "evidence",
            disjoint_roots=(candidate_root,),
        )

    repository = EvidenceRepository(
        tmp_path / "evidence",
        disjoint_roots=(candidate_root,),
    )
    original = _Artifact(label="alpha")
    adapter = TypeAdapter(_Artifact)
    stored = repository.publish_content_addressed_model(
        collection="artifacts",
        filename="artifact.json",
        model=original,
        adapter=adapter,
    )
    replacement = _Artifact(label="beta")
    replacement_bytes = (
        json.dumps(
            replacement.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    stored.artifact.path.write_bytes(replacement_bytes)

    with pytest.raises(ImmutableArtifactIntegrityError, match="digest|identity"):
        repository.load_content_addressed_model(
            collection="artifacts",
            content_sha256=original.content_sha256,
            filename="artifact.json",
            adapter=adapter,
        )


def test_evidence_repository_logical_claim_has_one_atomic_first_writer(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository(tmp_path / "evidence")
    adapter = TypeAdapter(_ArtifactClaim)
    identity = {"namespace": "artifact", "logical_id": "shared"}
    barrier = Barrier(2)

    def publish(claim: _ArtifactClaim) -> _ArtifactClaim | ImmutableArtifactCollisionError:
        barrier.wait()
        try:
            return repository.publish_logical_model(
                collection="claims",
                logical_identity=identity,
                filename="claim.json",
                model=claim,
                adapter=adapter,
            ).model
        except ImmutableArtifactCollisionError as error:
            return error

    claims = (
        _ArtifactClaim(target_content_sha256="a" * 64),
        _ArtifactClaim(target_content_sha256="b" * 64),
    )
    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = tuple(executor.map(publish, claims))

    winners = tuple(outcome for outcome in outcomes if isinstance(outcome, _ArtifactClaim))
    collisions = tuple(outcome for outcome in outcomes if isinstance(outcome, ImmutableArtifactCollisionError))
    replayed = repository.load_logical_model(
        collection="claims",
        logical_identity=identity,
        filename="claim.json",
        adapter=adapter,
    )

    assert len(winners) == 1
    assert len(collisions) == 1
    assert replayed.model == winners[0]


def test_host_private_repository_confines_paths_and_lists_exact_child_files(
    tmp_path: Path,
) -> None:
    repository = EvidenceRepository(
        tmp_path / "monitor-runtime",
        host_private=True,
    )
    adapter = TypeAdapter(_ArtifactClaim)
    first = repository.publish_canonical_model(
        "cycles/cycle/flows/claims/first/claim.json",
        _ArtifactClaim(target_content_sha256="a" * 64),
        adapter,
    )
    second = repository.publish_canonical_model(
        "cycles/cycle/flows/claims/second/claim.json",
        _ArtifactClaim(target_content_sha256="b" * 64),
        adapter,
    )
    repository.publish_bytes(
        "cycles/cycle/flows/claims/second/unrelated.json",
        b"{}\n",
    )

    assert repository.relative_path(first.artifact.path) == ("cycles/cycle/flows/claims/first/claim.json")
    assert repository.list_child_files(
        "cycles/cycle/flows/claims",
        filename="claim.json",
    ) == (
        "cycles/cycle/flows/claims/first/claim.json",
        "cycles/cycle/flows/claims/second/claim.json",
    )
    assert (
        repository.list_child_files(
            "cycles/cycle/references/claims",
            filename="claim.json",
        )
        == ()
    )
    assert stat.S_IMODE(repository.root.stat().st_mode) == 0o700
    for directory in (
        repository.root / "cycles",
        repository.root / "cycles" / "cycle",
        repository.root / "cycles" / "cycle" / "flows",
        repository.root / "cycles" / "cycle" / "flows" / "claims",
        repository.root / "cycles" / "cycle" / "flows" / "claims" / "first",
        repository.root / "cycles" / "cycle" / "flows" / "claims" / "second",
    ):
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(first.artifact.path.stat().st_mode) == 0o600
    assert stat.S_IMODE(second.artifact.path.stat().st_mode) == 0o600

    with pytest.raises(ImmutableArtifactConfinementError, match="root"):
        repository.relative_path(tmp_path / "outside.json")

    outside = tmp_path / "outside"
    outside.mkdir()
    (repository.root / "cycles" / "cycle" / "references").symlink_to(
        outside,
        target_is_directory=True,
    )
    with pytest.raises(ImmutableArtifactConfinementError, match="symbolic"):
        repository.list_child_files(
            "cycles/cycle/references/claims",
            filename="claim.json",
        )
