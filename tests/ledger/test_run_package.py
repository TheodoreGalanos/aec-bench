# ABOUTME: Tests deterministic portable publication and closed validation of run packages.
# ABOUTME: Proves empty-ledger import, nested artifact retention, and missing-artifact rejection.

from __future__ import annotations

import io
import tarfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import zstandard

from aec_bench.contracts.authority_evidence import AuthorityEvidenceKind
from aec_bench.contracts.run_bundle import PublishedRunPackage, RunPlan
from aec_bench.contracts.trial_record import (
    AuthorityExpectation,
    EvaluationStatus,
    EvidenceStatus,
    ExecutionStatus,
    TimingRecord,
    TrialInput,
    TrialRecord,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.run_package import (
    RunPackageIntegrityError,
    export_run_package,
    import_run_package,
    publish_run_package,
    read_run_package_archive,
)
from tests.support.adaptive_harness import build_adaptive_bundle, write_adaptive_task


def test_published_run_package_round_trips_into_an_empty_ledger(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    source_ledger = tmp_path / "source-ledger"
    repository = ArtifactRepository(source_ledger / "_artifacts")
    plan = build_adaptive_bundle(tasks_root=tasks_root, artifact_repository=repository)
    provider_ref = repository.publish_bytes(data=b"provider evidence\n", media_type="text/plain")
    started_at = datetime(2026, 8, 19, 1, 2, 3, tzinfo=UTC)
    trial = TrialRecord(
        trial_id="trial-1",
        run_id=plan.run_manifest.run_id,
        task_id=plan.task_snapshots[0].task_id,
        execution_status=ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.NOT_REQUESTED,
        evidence_status=EvidenceStatus.NOT_REQUIRED,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        input=TrialInput(instruction="Attempt the task.", task_revision="task-revision"),
        timing=TimingRecord(total_seconds=1),
        provider_evidence=provider_ref,
    )
    trial_ref = repository.publish_model(value=trial, media_type="application/json")
    package = PublishedRunPackage(run_plan=plan, trial_refs=(trial_ref,))

    first_ref = publish_run_package(ledger_root=source_ledger, package=package)
    second_ref = publish_run_package(ledger_root=source_ledger, package=package)
    assert first_ref == second_ref

    exported = tmp_path / "run-package.tar.zst"
    assert (
        export_run_package(
            ledger_root=source_ledger,
            run_id=plan.run_manifest.run_id,
            output=exported,
        )
        == first_ref
    )
    imported_package, imported_ref = import_run_package(
        ledger_root=tmp_path / "empty-ledger",
        data=exported.read_bytes(),
    )

    assert imported_package == package
    assert imported_ref == first_ref
    imported_repository = ArtifactRepository(tmp_path / "empty-ledger" / "_artifacts")
    assert imported_repository.read_bytes(provider_ref) == b"provider evidence\n"


def test_run_package_rejects_a_missing_referenced_artifact(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    repository = ArtifactRepository(tmp_path / "ledger" / "_artifacts")
    plan = build_adaptive_bundle(tasks_root=tasks_root, artifact_repository=repository)
    package = PublishedRunPackage(run_plan=plan)
    package_ref = publish_run_package(ledger_root=tmp_path / "ledger", package=package)
    archive = repository.read_bytes(package_ref)
    damaged = _without_first_artifact(archive)

    with pytest.raises(RunPackageIntegrityError, match="missing artifacts"):
        read_run_package_archive(damaged)


def test_run_package_rejects_verified_trial_without_expected_authority_evidence(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    write_adaptive_task(tasks_root)
    repository = ArtifactRepository(tmp_path / "ledger" / "_artifacts")
    base_plan = build_adaptive_bundle(tasks_root=tasks_root, artifact_repository=repository)
    plan = RunPlan.model_validate(
        {
            **base_plan.model_dump(mode="python"),
            "run_manifest": base_plan.run_manifest.model_copy(
                update={
                    "expected_authorities": (
                        AuthorityExpectation(
                            authority_kind=AuthorityEvidenceKind.WORLD,
                            protocol="aec-bench/world-evidence/1",
                        ),
                    ),
                }
            ),
        }
    )
    started_at = datetime(2026, 8, 19, 1, 2, 3, tzinfo=UTC)
    trial = TrialRecord(
        trial_id="trial-with-missing-world-evidence",
        run_id=plan.run_manifest.run_id,
        task_id=plan.task_snapshots[0].task_id,
        execution_status=ExecutionStatus.FAILED,
        evaluation_status=EvaluationStatus.NOT_REQUESTED,
        evidence_status=EvidenceStatus.VERIFIED,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        input=TrialInput(instruction="Attempt the task.", task_revision="task-revision"),
        timing=TimingRecord(total_seconds=1),
    )
    trial_ref = repository.publish_model(value=trial, media_type="application/json")

    with pytest.raises(RunPackageIntegrityError, match="missing required authority references"):
        publish_run_package(
            ledger_root=tmp_path / "ledger",
            package=PublishedRunPackage(run_plan=plan, trial_refs=(trial_ref,)),
        )


def _without_first_artifact(data: bytes) -> bytes:
    tar_bytes = zstandard.ZstdDecompressor().decompress(data)
    input_buffer = io.BytesIO(tar_bytes)
    output_buffer = io.BytesIO()
    removed = False
    with (
        tarfile.open(fileobj=input_buffer, mode="r:") as source,
        tarfile.open(fileobj=output_buffer, mode="w", format=tarfile.USTAR_FORMAT) as target,
    ):
        for member in source.getmembers():
            if member.name.startswith("artifacts/") and not removed:
                removed = True
                continue
            payload = source.extractfile(member)
            assert payload is not None
            target.addfile(member, payload)
    return zstandard.ZstdCompressor(level=10, write_checksum=True, write_content_size=True).compress(
        output_buffer.getvalue()
    )
