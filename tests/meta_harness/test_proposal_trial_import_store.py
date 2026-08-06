# ABOUTME: Pins proposal trial-import artifact storage paths, bytes, and first-writer identities.
# ABOUTME: Exercises isolated persistence without constructing the full proposal execution fixture.

from __future__ import annotations

import hashlib
import json
import stat
from pathlib import Path

import pytest

from aec_bench.contracts.trial_record import ArtifactReference, TrialRecord
from aec_bench.meta_harness.proposal_trial_importing.contracts import (
    ProposalTrialImportError,
    ProposalTrialImportReceipt,
)
from aec_bench.meta_harness.proposal_trial_importing.persistence import (
    open_host_artifacts_repository,
    persist_model_path,
    prepare_host_artifacts_repository,
    snapshot_file,
    write_or_load_exact_trial_record,
)
from tests.support.trial_record_factories import make_trial_record


def _receipt() -> ProposalTrialImportReceipt:
    return ProposalTrialImportReceipt(
        import_id="proposal-import.1",
        dispatch_id="dispatch.1",
        dispatch_sha256="a" * 64,
        provider_dispatch_event_sha256="b" * 64,
        harbor_execution_receipt_sha256="c" * 64,
        trial_id="trial-001",
        trial_record=ArtifactReference(
            kind="proposal-trial-record",
            path="/host/proposal-trial-records/experiment-001/trial-001.json",
            sha256="d" * 64,
            media_type="application/json",
        ),
        session_id="session.1",
        candidate_id="candidate.1",
        candidate_artifact_sha256="e" * 64,
        proposal_graph_sha256="f" * 64,
        compilation_sha256="1" * 64,
        session_plan_sha256="2" * 64,
        world_package_sha256="3" * 64,
        topology_signature_sha256="4" * 64,
        verifier_evidence_sha256="5" * 64,
        node_receipt_sha256s=("6" * 64,),
    )


def _canonical_bytes(receipt: ProposalTrialImportReceipt) -> bytes:
    return (
        json.dumps(
            receipt.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def test_import_receipt_preserves_physical_digest_path_and_bytes(
    tmp_path: Path,
) -> None:
    repository = prepare_host_artifacts_repository(
        tmp_path / "host-artifacts",
        forbidden_roots=(),
    )
    receipt = _receipt()
    encoded = _canonical_bytes(receipt)
    physical_sha256 = hashlib.sha256(encoded).hexdigest()
    object_root = repository.root / "proposal-trial-imports" / ("7" * 64) / "objects"

    assert receipt.content_sha256 == "dd79f23f16717b2ef4162b7d982e93e78eb1c8b12d25740ab777403ba6e8010b"
    assert physical_sha256 == "d49e1a07c7940fd23ca1300b8e0886d09c7a7c93a884e0269cad391706aa9d97"
    path = persist_model_path(
        repository=repository,
        model=receipt,
        filename="proposal-trial-import-receipt.json",
        object_root=object_root,
    )

    assert path == (object_root / physical_sha256 / "proposal-trial-import-receipt.json")
    assert path.read_bytes() == encoded
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    reopened = open_host_artifacts_repository(repository.root)
    assert (
        persist_model_path(
            repository=reopened,
            model=receipt,
            filename="proposal-trial-import-receipt.json",
            object_root=object_root,
        )
        == path
    )

    path.write_bytes(b'{"tampered":true}\n')
    with pytest.raises(
        ProposalTrialImportError,
        match="different bytes",
    ):
        persist_model_path(
            repository=reopened,
            model=receipt,
            filename="proposal-trial-import-receipt.json",
            object_root=object_root,
        )


def test_raw_snapshot_and_trial_record_preserve_distinct_identity_schemes(
    tmp_path: Path,
) -> None:
    repository = prepare_host_artifacts_repository(
        tmp_path / "host-artifacts",
        forbidden_roots=(),
    )
    source = tmp_path / "candidate-output.txt"
    source.write_bytes(b"candidate output\n")
    source_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
    object_root = repository.root / "proposal-trial-imports" / ("8" * 64) / "objects"

    snapshot = snapshot_file(
        repository=repository,
        reference=ArtifactReference(
            kind="proposal-final-output",
            path=str(source),
            sha256=source_sha256,
            media_type="text/plain",
        ),
        repo_root=tmp_path,
        object_root=object_root,
    )
    record = make_trial_record(
        experiment_id="experiment/raw",
        trial_id="trial/raw",
    )
    record_path = write_or_load_exact_trial_record(
        repository=repository,
        ledger_root=repository.root / "proposal-trial-records",
        record=record,
    )

    assert Path(snapshot.path) == (object_root / source_sha256 / "proposal-final-output.txt")
    assert Path(snapshot.path).read_bytes() == b"candidate output\n"
    assert record_path == (repository.root / "proposal-trial-records" / "experiment" / "raw" / "trial" / "raw.json")
    assert record_path.read_bytes() == record.model_dump_json(indent=2).encode("utf-8")
    reopened = open_host_artifacts_repository(repository.root)
    assert (
        write_or_load_exact_trial_record(
            repository=reopened,
            ledger_root=repository.root / "proposal-trial-records",
            record=record,
        )
        == record_path
    )

    changed = TrialRecord.model_validate(
        record.model_copy(
            update={
                "evaluation": record.evaluation.model_copy(
                    update={"reward": 0.5},
                ),
            },
        ).model_dump(mode="python"),
    )
    with pytest.raises(
        ProposalTrialImportError,
        match="differs from the resumed import",
    ):
        write_or_load_exact_trial_record(
            repository=reopened,
            ledger_root=repository.root / "proposal-trial-records",
            record=changed,
        )


def test_artifact_repository_rejects_disjoint_root_overlap_and_symlink(
    tmp_path: Path,
) -> None:
    candidate_root = tmp_path / "candidate"
    candidate_root.mkdir()
    with pytest.raises(ProposalTrialImportError, match="overlap"):
        prepare_host_artifacts_repository(
            candidate_root / "host-artifacts",
            forbidden_roots=(candidate_root,),
        )

    outside = tmp_path / "outside"
    outside.mkdir()
    symlink_root = tmp_path / "linked-artifacts"
    symlink_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ProposalTrialImportError, match="symbolic|symlink"):
        prepare_host_artifacts_repository(
            symlink_root,
            forbidden_roots=(),
        )
