# ABOUTME: Assembles portable Harbor proposal-import provenance from verified evidence.
# ABOUTME: Emits the exact sorted artifact set consumed by TrialRecord construction.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.proposal_execution import ProposalSessionReceipt
from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.harness.harbor_importing.artifact_io import artifact_reference, read_regular_trial_tree
from aec_bench.harness.harbor_importing.contracts import ImportEvidenceContext
from aec_bench.harness.proposal_session_config import LoadedProposalSessionHostInputs

from .contracts import (
    ProposalBoundaryEvidence,
    ProposalHarborImportEvidence,
)


def build_import_evidence(
    *,
    context: ImportEvidenceContext,
    host_inputs: LoadedProposalSessionHostInputs,
    receipt: ProposalSessionReceipt,
    collected_session_root: Path,
    session_receipt_path: Path,
    boundary: ProposalBoundaryEvidence,
) -> ProposalHarborImportEvidence:
    """Build portable proposal evidence only after all boundaries reconcile."""

    session_files = read_regular_trial_tree(
        collected_session_root,
        trial_dir=context.trial_dir,
        label="collected proposal session",
    )
    session_receipt_artifact = artifact_reference(
        kind="proposal_session_receipt",
        path=session_receipt_path,
        repo_root=context.repo_root,
    )
    cleanup_receipt_artifact = artifact_reference(
        kind="proposal_cleanup_receipt",
        path=boundary.cleanup.receipt_path,
        repo_root=context.repo_root,
    )
    task_package_manifest_artifact = artifact_reference(
        kind="proposal_task_package_manifest",
        path=(context.task_instance_dir / "proposal-task-package.json"),
        repo_root=context.repo_root,
    )
    runtime_archive_artifact = artifact_reference(
        kind="proposal_runtime_archive",
        path=host_inputs.runtime_archive.path,
        repo_root=context.repo_root,
    )
    artifacts = _proposal_artifacts(
        context=context,
        host_inputs=host_inputs,
        session_files=session_files,
        session_receipt_path=session_receipt_path,
        session_receipt_artifact=session_receipt_artifact,
        cleanup_receipt_artifact=cleanup_receipt_artifact,
        task_package_manifest_artifact=task_package_manifest_artifact,
        runtime_archive_artifact=runtime_archive_artifact,
        boundary=boundary,
    )
    compilation = host_inputs.bundle.compilation
    return ProposalHarborImportEvidence(
        session_id=receipt.session_id,
        candidate_id=compilation.candidate_ref.candidate_id,
        candidate_artifact_sha256=(compilation.candidate_ref.candidate_artifact_sha256),
        proposal_graph_sha256=(compilation.proposal_graph.content_sha256),
        compilation_sha256=compilation.content_sha256,
        session_plan_sha256=(host_inputs.bundle.session_plan.content_sha256),
        session_receipt=receipt,
        session_receipt_artifact=session_receipt_artifact,
        cleanup_receipt_artifact=cleanup_receipt_artifact,
        task_package_manifest_artifact=(task_package_manifest_artifact),
        runtime_archive_artifact=runtime_archive_artifact,
        artifacts=artifacts,
    )


def _proposal_artifacts(
    *,
    context: ImportEvidenceContext,
    host_inputs: LoadedProposalSessionHostInputs,
    session_files: dict[Path, bytes],
    session_receipt_path: Path,
    session_receipt_artifact: ArtifactReference,
    cleanup_receipt_artifact: ArtifactReference,
    task_package_manifest_artifact: ArtifactReference,
    runtime_archive_artifact: ArtifactReference,
    boundary: ProposalBoundaryEvidence,
) -> tuple[ArtifactReference, ...]:
    artifacts = [
        session_receipt_artifact,
        cleanup_receipt_artifact,
        task_package_manifest_artifact,
        runtime_archive_artifact,
        artifact_reference(
            kind="proposal_session_bundle",
            path=Path(host_inputs.config.bundle_path),
            repo_root=context.repo_root,
        ),
        artifact_reference(
            kind="proposal_verifier_rotation_receipt",
            path=boundary.rotation_path,
            repo_root=context.repo_root,
        ),
        artifact_reference(
            kind="proposal_artifact_seal_manifest",
            path=boundary.seal_path,
            repo_root=context.repo_root,
        ),
    ]
    artifacts.extend(
        artifact_reference(
            kind="proposal_session_artifact",
            path=path,
            repo_root=context.repo_root,
        )
        for path in session_files
        if path != session_receipt_path
    )
    artifacts.extend(
        artifact_reference(
            kind="proposal_sealed_artifact",
            path=artifact.path,
            repo_root=context.repo_root,
        )
        for artifact in boundary.sealed_artifacts
    )
    return tuple(
        sorted(
            artifacts,
            key=lambda artifact: (
                artifact.kind,
                artifact.path,
                artifact.sha256,
            ),
        )
    )


__all__ = ("build_import_evidence",)
