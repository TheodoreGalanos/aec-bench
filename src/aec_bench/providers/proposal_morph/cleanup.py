# ABOUTME: Executes ordered Morph teardown as a receipt-bearing cleanup transaction.
# ABOUTME: Accumulates failures without skipping dependent scrub, stop, and delete steps.

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from aec_bench.providers.morph_cloud import morph_object_id

from .boundary import (
    BoundaryPhase,
    HandoffVariant,
    ProposalMorphBoundaryError,
    VerifierRotationBinding,
)
from .confinement import write_receipt
from .evidence import load_completed_verifier_rotation
from .operations import ProposalMorphHarborOperations


@dataclass
class CleanupJournal:
    """Mutable receipt and ordered failure list for one teardown transaction."""

    path: Path
    receipt: dict[str, object]
    errors: list[Exception]
    failure_steps: list[str]

    def fail(self, step: str, error: Exception) -> None:
        self.errors.append(error)
        if step not in self.failure_steps:
            self.failure_steps.append(step)

    def persist(self) -> None:
        try:
            write_receipt(self.path, self.receipt)
        except Exception as error:
            self.fail("persist_cleanup_receipt", error)


async def teardown_errors(
    *,
    operations: ProposalMorphHarborOperations,
    snapshot: object,
    instance: object,
    delete: bool,
) -> list[Exception]:
    """Best-effort rollback for provisioning before a verifier exists."""

    errors: list[Exception] = []
    if delete:
        try:
            await asyncio.to_thread(
                operations.scrub_trial_instance,
                instance=instance,
            )
        except Exception as error:
            errors.append(error)
    try:
        await asyncio.to_thread(
            operations.stop_instance,
            instance=instance,
        )
    except Exception as error:
        errors.append(error)
    if delete:
        errors.extend(
            await delete_snapshot_errors(
                operations=operations,
                snapshot=snapshot,
            )
        )
    return errors


async def delete_snapshot_errors(
    *,
    operations: ProposalMorphHarborOperations,
    snapshot: object,
) -> list[Exception]:
    """Delete one snapshot without hiding its provider failure."""

    try:
        await asyncio.to_thread(
            operations.delete_snapshot,
            snapshot=snapshot,
        )
    except Exception as error:
        return [error]
    return []


async def teardown_with_cleanup_receipt_errors(
    *,
    operations: ProposalMorphHarborOperations,
    cleanup_receipt_path: Path,
    rotation_receipt_path: Path,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    snapshot: object,
    instance: object,
    expected_container_identity: str,
    boundary_phase: BoundaryPhase,
    delete: bool,
) -> list[Exception]:
    """Run the ordered teardown and persist evidence after each material step."""

    journal = _cleanup_journal(
        path=cleanup_receipt_path,
        boundary_phase=boundary_phase,
        runtime_archive_sha256=runtime_archive_sha256,
        runtime_archive_content_sha256=runtime_archive_content_sha256,
        delete=delete,
    )
    _record_resource_identities(journal, snapshot=snapshot, instance=instance)
    rotation = _record_rotation(
        journal,
        path=rotation_receipt_path,
        boundary_phase=boundary_phase,
        runtime_archive_sha256=runtime_archive_sha256,
        runtime_archive_content_sha256=runtime_archive_content_sha256,
        expected_container_identity=expected_container_identity,
    )
    journal.persist()
    await _verify_verifier_identity(
        journal,
        operations=operations,
        instance=instance,
        rotation=rotation,
    )
    journal.persist()
    if delete:
        await _stop_and_scrub_verifier(
            journal,
            operations=operations,
            instance=instance,
            rotation=rotation,
        )
    await _stop_instance(journal, operations=operations, instance=instance)
    journal.persist()
    if delete:
        await _delete_snapshot(
            journal,
            operations=operations,
            snapshot=snapshot,
        )
    _finish_cleanup_status(
        journal,
        boundary_phase=boundary_phase,
        delete=delete,
    )
    journal.persist()
    return journal.errors


def _cleanup_journal(
    *,
    path: Path,
    boundary_phase: BoundaryPhase,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    delete: bool,
) -> CleanupJournal:
    failure_steps: list[str] = []
    return CleanupJournal(
        path=path,
        errors=[],
        failure_steps=failure_steps,
        receipt={
            "schema_version": "aecbench.proposal-morph-cleanup.v1",
            "status": "started",
            "delete_requested": delete,
            "boundary_phase_at_stop": boundary_phase.value,
            "runtime_archive_sha256": runtime_archive_sha256,
            "runtime_archive_content_sha256": runtime_archive_content_sha256,
            "runtime_snapshot_identity": None,
            "trial_instance_identity": None,
            "rotation_receipt_sha256": None,
            "rotation_receipt_content_sha256": None,
            "rotation_receipt_verified": False,
            "expected_verifier_container_identity": None,
            "observed_verifier_container_identity": None,
            "verifier_container_identity_verified": False,
            "verifier_container_stopped": False,
            "verifier_container_scrubbed": False,
            "trial_instance_scrubbed": False,
            "trial_instance_stopped": False,
            "runtime_snapshot_deleted": False,
            "failure_steps": failure_steps,
        },
    )


def _record_resource_identities(
    journal: CleanupJournal,
    *,
    snapshot: object,
    instance: object,
) -> None:
    try:
        journal.receipt["runtime_snapshot_identity"] = morph_object_id(snapshot)
    except Exception as error:
        journal.fail("resolve_runtime_snapshot_identity", error)
    try:
        journal.receipt["trial_instance_identity"] = morph_object_id(instance)
    except Exception as error:
        journal.fail("resolve_trial_instance_identity", error)


def _record_rotation(
    journal: CleanupJournal,
    *,
    path: Path,
    boundary_phase: BoundaryPhase,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
    expected_container_identity: str,
) -> VerifierRotationBinding | None:
    if boundary_phase is not BoundaryPhase.VERIFIER:
        return None
    try:
        rotation = load_completed_verifier_rotation(
            path=path,
            runtime_archive_sha256=runtime_archive_sha256,
            runtime_archive_content_sha256=runtime_archive_content_sha256,
            expected_container_identity=expected_container_identity,
        )
    except Exception as error:
        journal.fail("validate_verifier_rotation", error)
        return None
    journal.receipt["rotation_receipt_sha256"] = rotation.receipt_sha256
    journal.receipt["rotation_receipt_content_sha256"] = rotation.receipt_content_sha256
    journal.receipt["rotation_receipt_verified"] = True
    journal.receipt["expected_verifier_container_identity"] = rotation.verifier_container_identity
    if rotation.handoff_variant is HandoffVariant.CANDIDATE_FAILURE:
        journal.receipt["handoff_variant"] = rotation.handoff_variant.value
        journal.receipt["candidate_failure_session_receipt_sha256"] = rotation.candidate_failure_session_receipt_sha256
    return rotation


async def _verify_verifier_identity(
    journal: CleanupJournal,
    *,
    operations: ProposalMorphHarborOperations,
    instance: object,
    rotation: VerifierRotationBinding | None,
) -> None:
    if rotation is None:
        return
    try:
        observed_identity = await asyncio.to_thread(
            operations.trial_container_identity,
            instance=instance,
        )
    except Exception as error:
        journal.fail("verify_verifier_container_identity", error)
        return
    journal.receipt["observed_verifier_container_identity"] = observed_identity
    if observed_identity != rotation.verifier_container_identity:
        journal.fail(
            "verify_verifier_container_identity",
            ProposalMorphBoundaryError("proposal verifier container identity changed before cleanup"),
        )
        return
    journal.receipt["verifier_container_identity_verified"] = True


async def _stop_and_scrub_verifier(
    journal: CleanupJournal,
    *,
    operations: ProposalMorphHarborOperations,
    instance: object,
    rotation: VerifierRotationBinding | None,
) -> None:
    if journal.receipt["verifier_container_identity_verified"] is True:
        assert rotation is not None
        try:
            await asyncio.to_thread(
                operations.stop_trial_container,
                instance=instance,
                expected_container_identity=rotation.verifier_container_identity,
            )
        except Exception as error:
            journal.fail("stop_verifier_container", error)
        else:
            journal.receipt["verifier_container_stopped"] = True
        journal.persist()
    try:
        await asyncio.to_thread(
            operations.scrub_trial_instance,
            instance=instance,
        )
    except Exception as error:
        journal.fail("scrub_trial_instance", error)
    else:
        journal.receipt["trial_instance_scrubbed"] = True
        journal.receipt["verifier_container_scrubbed"] = bool(journal.receipt["verifier_container_stopped"])
    journal.persist()


async def _stop_instance(
    journal: CleanupJournal,
    *,
    operations: ProposalMorphHarborOperations,
    instance: object,
) -> None:
    try:
        await asyncio.to_thread(
            operations.stop_instance,
            instance=instance,
        )
    except Exception as error:
        journal.fail("stop_instance", error)
    else:
        journal.receipt["trial_instance_stopped"] = True


async def _delete_snapshot(
    journal: CleanupJournal,
    *,
    operations: ProposalMorphHarborOperations,
    snapshot: object,
) -> None:
    try:
        await asyncio.to_thread(
            operations.delete_snapshot,
            snapshot=snapshot,
        )
    except Exception as error:
        journal.fail("delete_snapshot", error)
    else:
        journal.receipt["runtime_snapshot_deleted"] = True


def _finish_cleanup_status(
    journal: CleanupJournal,
    *,
    boundary_phase: BoundaryPhase,
    delete: bool,
) -> None:
    if journal.errors:
        journal.receipt["status"] = "failed"
    elif not delete:
        journal.receipt["status"] = "retained"
    elif boundary_phase is not BoundaryPhase.VERIFIER:
        journal.receipt["status"] = "not_applicable"
    else:
        journal.receipt["status"] = "completed"
