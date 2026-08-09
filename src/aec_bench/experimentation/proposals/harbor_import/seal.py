# ABOUTME: Validates the proposal artifact seal against its exact physical trees.
# ABOUTME: Rejects path escapes, duplicate identities, hash drift, and missing receipt evidence.

from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
from typing import Any

from aec_bench.contracts.proposal_execution.session import ProposalSessionReceipt
from aec_bench.contracts.proposal_execution_types import ProposalSessionStatus
from aec_bench.experimentation.proposals.session_config import LoadedProposalSessionHostInputs
from aec_bench.harness.harbor_importing.artifact_io import (
    read_regular_trial_tree,
    read_required_trial_file,
)
from aec_bench.harness.harbor_importing.contracts import HarborImportError

from .contracts import ProposalSealedArtifact


def validate_proposal_artifact_seal(
    *,
    seal: dict[str, Any],
    boundary: Path,
    collected_session_root: Path,
    session_receipt_path: Path,
    receipt: ProposalSessionReceipt,
    trial_dir: Path,
    host_inputs: LoadedProposalSessionHostInputs,
) -> tuple[ProposalSealedArtifact, ...]:
    """Reconcile a seal manifest with its captured and collected artifact trees."""

    candidate_failure = receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE
    _validate_seal_header(
        seal=seal,
        receipt=receipt,
        host_inputs=host_inputs,
        candidate_failure=candidate_failure,
    )
    sealed = _load_sealed_artifacts(
        entries=seal.get("artifacts"),
        boundary=boundary,
        trial_dir=trial_dir,
    )
    _validate_sealed_tree(
        sealed=sealed,
        boundary=boundary,
        trial_dir=trial_dir,
    )
    _validate_collected_session_against_seal(
        sealed=sealed,
        collected_session_root=collected_session_root,
        session_receipt_path=session_receipt_path,
        receipt=receipt,
        trial_dir=trial_dir,
    )
    return sealed


def _validate_seal_header(
    *,
    seal: dict[str, Any],
    receipt: ProposalSessionReceipt,
    host_inputs: LoadedProposalSessionHostInputs,
    candidate_failure: bool,
) -> None:
    expected_fields = {
        "artifacts",
        "content_sha256",
        "runtime_archive_content_sha256",
        "runtime_archive_sha256",
        "schema_version",
    }
    if candidate_failure:
        expected_fields.update(
            {
                "candidate_failure_session_receipt_sha256",
                "handoff_variant",
            }
        )
    if set(seal) != expected_fields:
        raise HarborImportError(
            "proposal artifact seal fields do not match its schema",
        )
    candidate_failure_matches = not candidate_failure or (
        seal.get("handoff_variant") == "candidate_failure"
        and seal.get(
            "candidate_failure_session_receipt_sha256",
        )
        == receipt.content_sha256
    )
    if (
        seal.get("schema_version") != "aecbench.proposal-artifact-seal.v1"
        or seal.get("runtime_archive_sha256") != host_inputs.config.runtime_archive_sha256
        or seal.get("runtime_archive_content_sha256") != host_inputs.config.runtime_archive_content_sha256
        or not candidate_failure_matches
    ):
        raise HarborImportError(
            "proposal artifact seal does not bind the exact runtime",
        )


def _load_sealed_artifacts(
    *,
    entries: object,
    boundary: Path,
    trial_dir: Path,
) -> tuple[ProposalSealedArtifact, ...]:
    if not isinstance(entries, list) or not entries:
        raise HarborImportError(
            "proposal artifact seal has no artifacts",
        )
    sealed: list[ProposalSealedArtifact] = []
    seen_paths: set[str] = set()
    for entry in entries:
        artifact = _load_sealed_artifact(
            entry=entry,
            boundary=boundary,
            trial_dir=trial_dir,
            seen_paths=seen_paths,
        )
        seen_paths.add(artifact.remote_path)
        sealed.append(artifact)
    ordered_paths = tuple(artifact.remote_path for artifact in sealed)
    if ordered_paths != tuple(sorted(ordered_paths)):
        raise HarborImportError(
            "proposal artifact seal entries must be sorted",
        )
    return tuple(sealed)


def _load_sealed_artifact(
    *,
    entry: object,
    boundary: Path,
    trial_dir: Path,
    seen_paths: set[str],
) -> ProposalSealedArtifact:
    if not isinstance(entry, dict) or set(entry) != {
        "path",
        "sha256",
        "size_bytes",
    }:
        raise HarborImportError(
            "proposal artifact seal contains an invalid artifact entry",
        )
    remote_path = entry.get("path")
    sha256 = entry.get("sha256")
    size_bytes = entry.get("size_bytes")
    if not _valid_sealed_identity(
        remote_path=remote_path,
        sha256=sha256,
        size_bytes=size_bytes,
        seen_paths=seen_paths,
    ):
        raise HarborImportError(
            "proposal artifact seal contains an invalid artifact identity",
        )
    assert isinstance(remote_path, str)
    assert isinstance(sha256, str)
    assert type(size_bytes) is int
    artifact_path = boundary / "sealed-artifacts" / remote_path.removeprefix("/")
    content = read_required_trial_file(
        artifact_path,
        trial_dir=trial_dir,
        label=f"sealed proposal artifact {remote_path}",
    )
    if len(content) != size_bytes or hashlib.sha256(content).hexdigest() != sha256:
        raise HarborImportError(
            f"sealed proposal artifact changed after capture: {remote_path}",
        )
    return ProposalSealedArtifact(
        remote_path=remote_path,
        path=artifact_path,
        sha256=sha256,
        size_bytes=size_bytes,
    )


def _valid_sealed_identity(
    *,
    remote_path: object,
    sha256: object,
    size_bytes: object,
    seen_paths: set[str],
) -> bool:
    return (
        isinstance(remote_path, str)
        and _is_contained_workspace_path(remote_path)
        and remote_path not in seen_paths
        and isinstance(sha256, str)
        and len(sha256) == 64
        and all(character in "0123456789abcdef" for character in sha256)
        and type(size_bytes) is int
        and size_bytes >= 0
    )


def _validate_sealed_tree(
    *,
    sealed: tuple[ProposalSealedArtifact, ...],
    boundary: Path,
    trial_dir: Path,
) -> None:
    seal_tree = read_regular_trial_tree(
        boundary / "sealed-artifacts",
        trial_dir=trial_dir,
        label="sealed proposal artifact tree",
    )
    if {artifact.path for artifact in sealed} != set(seal_tree):
        raise HarborImportError(
            "proposal artifact seal manifest does not cover its exact physical tree",
        )


def _validate_collected_session_against_seal(
    *,
    sealed: tuple[ProposalSealedArtifact, ...],
    collected_session_root: Path,
    session_receipt_path: Path,
    receipt: ProposalSessionReceipt,
    trial_dir: Path,
) -> None:
    collected = read_regular_trial_tree(
        collected_session_root,
        trial_dir=trial_dir,
        label="collected proposal session",
    )
    collected_by_remote = {
        (
            "/workspace/proposal-session/"
            + path.relative_to(
                collected_session_root,
            ).as_posix()
        ): content
        for path, content in collected.items()
    }
    sealed_by_remote = {artifact.remote_path: artifact for artifact in sealed}
    sealed_session_paths = {path for path in sealed_by_remote if path.startswith("/workspace/proposal-session/")}
    if set(collected_by_remote) != sealed_session_paths:
        raise HarborImportError(
            "collected proposal session differs from the exact sealed session tree",
        )
    for remote_path, content in collected_by_remote.items():
        artifact = sealed_by_remote[remote_path]
        if len(content) != artifact.size_bytes or hashlib.sha256(content).hexdigest() != artifact.sha256:
            raise HarborImportError(
                f"collected proposal session artifact differs from its seal: {remote_path}",
            )
    receipt_remote_path = (
        "/workspace/proposal-session/"
        + session_receipt_path.relative_to(
            collected_session_root,
        ).as_posix()
    )
    if receipt_remote_path not in sealed_by_remote:
        raise HarborImportError(
            "proposal artifact seal does not contain the collected session receipt",
        )
    _validate_receipt_artifact_files(
        receipt=receipt,
        collected_session_root=collected_session_root,
        collected=collected,
    )


def _validate_receipt_artifact_files(
    *,
    receipt: ProposalSessionReceipt,
    collected_session_root: Path,
    collected: dict[Path, bytes],
) -> None:
    references = tuple(
        reference
        for node in receipt.node_receipts
        for reference in (
            node.container_transition,
            node.execution_result,
            node.contract_check_result,
            *node.emitted_handoffs,
        )
        if reference is not None
    )
    for reference in references:
        path = collected_session_root / reference.session_relative_path
        content = collected.get(path)
        if (
            content is None
            or len(content) != reference.byte_size
            or hashlib.sha256(content).hexdigest() != reference.artifact_sha256
        ):
            raise HarborImportError(
                "proposal session receipt references missing or changed physical evidence",
            )
    collected_hashes = {hashlib.sha256(content).hexdigest() for content in collected.values()}
    if any(
        node.output_artifact_sha256 is not None and node.output_artifact_sha256 not in collected_hashes
        for node in receipt.node_receipts
    ):
        raise HarborImportError(
            "proposal session node output evidence is missing from the collected session",
        )


def _is_contained_workspace_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (
        path.is_absolute()
        and path.is_relative_to(PurePosixPath("/workspace"))
        and all(part not in {"", ".", ".."} for part in path.parts[1:])
    )


__all__ = ("validate_proposal_artifact_seal",)
