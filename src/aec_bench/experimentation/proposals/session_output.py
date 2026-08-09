# ABOUTME: Resolves the exact finalizer bytes produced by a completed proposal session.
# ABOUTME: Prevents pooled output publication unless file and receipt identities match.

from __future__ import annotations

import hashlib
import re
import stat
from pathlib import Path

from aec_bench.contracts.proposal_execution.session import ProposalNodeReceipt, ProposalSessionReceipt
from aec_bench.contracts.proposal_execution_types import ProposalNodeReceiptStatus, ProposalSessionStatus

_INVOCATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")
_MAX_FINAL_OUTPUT_BYTES = 64 * 1024 * 1024


class ProposalSessionOutputError(RuntimeError):
    """Reject output bytes that are absent, unsafe, or identity-mismatched."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def verified_proposal_final_output_path(
    *,
    session_root: Path | str,
    receipt: ProposalSessionReceipt,
) -> Path | None:
    """Return verified completed bytes, or no path for a candidate failure."""

    if receipt.status is ProposalSessionStatus.CANDIDATE_FAILURE:
        _validate_candidate_failure_has_no_output(receipt)
        return None
    finalizer = _publishable_finalizer(receipt)
    assert finalizer.invocation_id is not None
    assert receipt.final_output_artifact_sha256 is not None

    root = Path(session_root)
    output_path = root / "invocations" / finalizer.invocation_id / "output.bin"
    if output_path.is_symlink():
        raise ProposalSessionOutputError(
            "final_output_path_invalid",
            "proposal final output must not be a symbolic link",
        )
    try:
        output_stat = output_path.stat(follow_symlinks=False)
        resolved_root = root.resolve(strict=True)
        resolved_output = output_path.resolve(strict=True)
        resolved_output.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ProposalSessionOutputError(
            "final_output_path_invalid",
            f"proposal final output cannot be resolved safely: {error}",
        ) from error
    if (
        not stat.S_ISREG(output_stat.st_mode)
        or output_stat.st_size < 1
        or output_stat.st_size > _MAX_FINAL_OUTPUT_BYTES
    ):
        raise ProposalSessionOutputError(
            "final_output_path_invalid",
            "proposal final output must be a bounded non-empty regular file",
        )
    try:
        output_bytes = output_path.read_bytes()
    except OSError as error:
        raise ProposalSessionOutputError(
            "final_output_path_invalid",
            f"proposal final output cannot be read: {error}",
        ) from error
    if hashlib.sha256(output_bytes).hexdigest() != receipt.final_output_artifact_sha256:
        raise ProposalSessionOutputError(
            "final_output_identity_mismatch",
            "proposal final output bytes differ from the completed receipt",
        )
    return output_path


def _validate_candidate_failure_has_no_output(
    receipt: ProposalSessionReceipt,
) -> None:
    if (
        receipt.trial_record_permitted
        or receipt.final_output_artifact_sha256 is not None
        or receipt.output_commit_attestation_sha256 is not None
    ):
        raise ProposalSessionOutputError(
            "candidate_failure_output_invalid",
            "candidate-failure proposal receipt cannot publish final output",
        )


def _publishable_finalizer(
    receipt: ProposalSessionReceipt,
) -> ProposalNodeReceipt:
    if (
        receipt.status is not ProposalSessionStatus.COMPLETED
        or not receipt.trial_record_permitted
        or receipt.final_output_artifact_sha256 is None
        or receipt.output_commit_attestation_sha256 is None
    ):
        raise ProposalSessionOutputError(
            "final_output_receipt_invalid",
            "completed proposal receipt lacks publishable final output evidence",
        )
    finalizer_id = receipt.plan.compilation.proposal_graph.finalizer.node_id
    finalizers = tuple(node for node in receipt.node_receipts if node.node_id == finalizer_id)
    if len(finalizers) != 1:
        raise ProposalSessionOutputError(
            "final_output_receipt_invalid",
            "proposal receipt does not contain exactly one finalizer node",
        )
    finalizer = finalizers[0]
    if (
        finalizer.status is not ProposalNodeReceiptStatus.COMPLETED
        or finalizer.invocation_id is None
        or not _INVOCATION_ID.fullmatch(finalizer.invocation_id)
        or finalizer.output_artifact_sha256 != receipt.final_output_artifact_sha256
    ):
        raise ProposalSessionOutputError(
            "final_output_receipt_invalid",
            "proposal finalizer receipt does not bind the session final output",
        )
    return finalizer
