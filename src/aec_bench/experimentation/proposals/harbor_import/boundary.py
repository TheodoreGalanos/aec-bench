# ABOUTME: Reconciles proposal cleanup, verifier rotation, seal, and final output evidence.
# ABOUTME: Preserves fail-closed lineage checks across candidate and verifier containers.

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.experimentation.proposals.morph.evidence import (
    load_completed_proposal_morph_cleanup_receipt,
)
from aec_bench.experimentation.proposals.session_config import LoadedProposalSessionHostInputs
from aec_bench.harness.harbor_importing.artifact_io import (
    read_content_addressed_trial_json,
    read_required_trial_file,
    required_trial_directory,
)
from aec_bench.harness.harbor_importing.contracts import (
    HarborImportError,
    ImportEvidenceContext,
)

from .contracts import (
    ProposalBoundaryEvidence,
    ProposalCleanupReceipt,
    ProposalSealedArtifact,
)
from .seal import validate_proposal_artifact_seal


def load_boundary_evidence(
    *,
    context: ImportEvidenceContext,
    host_inputs: LoadedProposalSessionHostInputs,
    receipt: ProposalSessionReceipt,
    collected_session_root: Path,
    session_receipt_path: Path,
) -> ProposalBoundaryEvidence:
    """Load and reconcile the complete provider isolation boundary."""

    boundary = required_trial_directory(
        context.trial_dir / "proposal-morph-boundary",
        trial_dir=context.trial_dir,
        label="proposal Morph boundary",
    )
    cleanup_path = boundary / "proposal-cleanup.json"
    try:
        cleanup = _load_proposal_cleanup_receipt(
            path=cleanup_path,
            runtime_archive_sha256=(host_inputs.config.runtime_archive_sha256),
            runtime_archive_content_sha256=(host_inputs.config.runtime_archive_content_sha256),
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise HarborImportError(
            f"proposal cleanup receipt is invalid: {error}",
        ) from error
    rotation_path = boundary / "verifier-rotation.json"
    rotation_bytes, rotation = read_content_addressed_trial_json(
        rotation_path,
        trial_dir=context.trial_dir,
        label="proposal verifier rotation receipt",
    )
    _validate_proposal_rotation(
        rotation=rotation,
        rotation_bytes=rotation_bytes,
        cleanup=cleanup,
        receipt=receipt,
        host_inputs=host_inputs,
    )
    seal_path = boundary / "seal-manifest.json"
    _seal_bytes, seal = read_content_addressed_trial_json(
        seal_path,
        trial_dir=context.trial_dir,
        label="proposal artifact seal manifest",
    )
    sealed_artifacts = validate_proposal_artifact_seal(
        seal=seal,
        boundary=boundary,
        collected_session_root=collected_session_root,
        session_receipt_path=session_receipt_path,
        receipt=receipt,
        trial_dir=context.trial_dir,
        host_inputs=host_inputs,
    )
    return ProposalBoundaryEvidence(
        cleanup=cleanup,
        rotation_path=rotation_path,
        seal_path=seal_path,
        sealed_artifacts=sealed_artifacts,
    )


def validate_final_output_evidence(
    *,
    context: ImportEvidenceContext,
    receipt: ProposalSessionReceipt,
    rotation_path: Path,
    sealed_artifacts: tuple[ProposalSealedArtifact, ...],
) -> None:
    """Require completed output agreement or candidate-failure output absence."""

    _rotation_bytes, rotation = read_content_addressed_trial_json(
        rotation_path,
        trial_dir=context.trial_dir,
        label="proposal verifier rotation receipt",
    )
    if receipt.status is ProposalSessionStatus.COMPLETED:
        output_path = _required_proposal_output_path(
            trial_dir=context.trial_dir,
        )
        output_bytes = read_required_trial_file(
            output_path,
            trial_dir=context.trial_dir,
            label="collected proposal output",
        )
        output_sha256 = hashlib.sha256(output_bytes).hexdigest()
        output_seal = next(
            (artifact for artifact in sealed_artifacts if artifact.remote_path == "/workspace/output.md"),
            None,
        )
        if (
            output_seal is None
            or output_seal.sha256 != output_sha256
            or receipt.final_output_artifact_sha256 != output_sha256
            or rotation.get("sealed_output_sha256") != output_sha256
        ):
            raise HarborImportError(
                "proposal final output does not match its session, seal, and verifier rotation",
            )
        return
    if any(artifact.remote_path == "/workspace/output.md" for artifact in sealed_artifacts):
        raise HarborImportError(
            "proposal candidate failure fabricated final-output evidence",
        )


def _validate_proposal_rotation(
    *,
    rotation: dict[str, Any],
    rotation_bytes: bytes,
    cleanup: ProposalCleanupReceipt,
    receipt: ProposalSessionReceipt,
    host_inputs: LoadedProposalSessionHostInputs,
) -> None:
    candidate_failure = receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE
    _validate_rotation_fields(
        rotation=rotation,
        candidate_failure=candidate_failure,
    )
    attempted = tuple(
        node
        for node_id in receipt.plan.topological_order
        for node in receipt.node_receipts
        if (node.node_id == node_id and node.container_transition is not None)
    )
    if not attempted:
        raise HarborImportError(
            "proposal verifier rotation has no candidate container lineage",
        )
    last_transition = attempted[-1].container_transition
    assert last_transition is not None
    expected_handoff_variant = "candidate_failure" if candidate_failure else "completed_output"
    expected_failure_receipt_sha256 = receipt.content_sha256 if candidate_failure else None
    if not _rotation_lineage_matches(
        rotation=rotation,
        rotation_bytes=rotation_bytes,
        cleanup=cleanup,
        host_inputs=host_inputs,
        candidate_failure=candidate_failure,
        expected_handoff_variant=expected_handoff_variant,
        expected_failure_receipt_sha256=(expected_failure_receipt_sha256),
        candidate_container_identity=(last_transition.current_container_identity),
    ):
        raise HarborImportError(
            "proposal verifier rotation does not bind candidate, verifier, runtime, and cleanup lineage",
        )


def _validate_rotation_fields(
    *,
    rotation: dict[str, Any],
    candidate_failure: bool,
) -> None:
    expected_fields = {
        "artifacts_sealed",
        "candidate_container_identity",
        "candidate_container_stopped",
        "content_sha256",
        "mounts_wiped",
        "output_restored",
        "runtime_archive_content_sha256",
        "runtime_archive_sha256",
        "schema_version",
        "sealed_output_sha256",
        "status",
        "tests_content_sha256",
        "tests_uploaded",
        "verifier_container_identity",
    }
    if candidate_failure:
        expected_fields.update(
            {
                "candidate_failure_session_receipt_sha256",
                "handoff_variant",
            }
        )
    if set(rotation) != expected_fields:
        raise HarborImportError(
            "proposal verifier rotation receipt fields do not match its schema",
        )


def _rotation_lineage_matches(
    *,
    rotation: dict[str, Any],
    rotation_bytes: bytes,
    cleanup: ProposalCleanupReceipt,
    host_inputs: LoadedProposalSessionHostInputs,
    candidate_failure: bool,
    expected_handoff_variant: str,
    expected_failure_receipt_sha256: str | None,
    candidate_container_identity: str,
) -> bool:
    verifier_identity = rotation.get(
        "verifier_container_identity",
    )
    required_true = (
        "candidate_container_stopped",
        "artifacts_sealed",
        "mounts_wiped",
        "tests_uploaded",
    )
    candidate_failure_matches = not candidate_failure or (
        rotation.get("handoff_variant") == expected_handoff_variant
        and rotation.get(
            "candidate_failure_session_receipt_sha256",
        )
        == expected_failure_receipt_sha256
        and rotation.get("sealed_output_sha256") is None
    )
    return (
        rotation.get("schema_version") == "aecbench.proposal-verifier-rotation.v1"
        and rotation.get("status") == "completed"
        and rotation.get("runtime_archive_sha256") == host_inputs.config.runtime_archive_sha256
        and rotation.get("runtime_archive_content_sha256") == host_inputs.config.runtime_archive_content_sha256
        and all(rotation.get(field) is True for field in required_true)
        and rotation.get("output_restored") is (not candidate_failure)
        and cleanup.handoff_variant == expected_handoff_variant
        and cleanup.candidate_failure_session_receipt_sha256 == expected_failure_receipt_sha256
        and candidate_failure_matches
        and rotation.get("candidate_container_identity") == candidate_container_identity
        and isinstance(verifier_identity, str)
        and bool(verifier_identity)
        and verifier_identity != candidate_container_identity
        and verifier_identity == cleanup.verifier_container_identity
        and hashlib.sha256(rotation_bytes).hexdigest() == cleanup.rotation_receipt_sha256
        and rotation.get("content_sha256") == cleanup.rotation_receipt_content_sha256
    )


def _load_proposal_cleanup_receipt(
    *,
    path: Path,
    runtime_archive_sha256: str,
    runtime_archive_content_sha256: str,
) -> ProposalCleanupReceipt:
    result = load_completed_proposal_morph_cleanup_receipt(
        path,
        expected_runtime_archive_sha256=runtime_archive_sha256,
        expected_runtime_archive_content_sha256=(runtime_archive_content_sha256),
    )
    return cast(ProposalCleanupReceipt, result)


def _required_proposal_output_path(
    *,
    trial_dir: Path,
) -> Path:
    candidates = (
        trial_dir / "agent" / "output.md",
        trial_dir / "artifacts" / "agent" / "output.md",
    )
    existing = tuple(path for path in candidates if path.exists() or path.is_symlink())
    if len(existing) != 1:
        raise HarborImportError(
            "proposal import requires exactly one collected final output",
        )
    return existing[0]


__all__ = (
    "load_boundary_evidence",
    "validate_final_output_evidence",
)
