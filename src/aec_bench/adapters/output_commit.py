# ABOUTME: Owns provider-neutral output-commit validation and exact-byte attestation.
# ABOUTME: Safely reads fixed output paths and detects changes after an accepted commit.

from __future__ import annotations

import hashlib
import logging
import os
import stat
from dataclasses import dataclass
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest
from aec_bench.contracts.harness_kernel import canonical_content_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    OutputCompletionEvaluation,
    evaluate_output_completion,
)

logger = logging.getLogger(__name__)

_OUTPUT_COMPLETION_CONTRACT_KEY = "output_completion_contract"
_OUTPUT_COMPLETION_COMMIT_KEY = "output_completion_commit"
_OUTPUT_COMPLETION_MAX_BYTES = 1024 * 1024


@dataclass(frozen=True)
class OutputCommitDecision:
    """One reward-blind decision about the fixed candidate artifact."""

    attestation: OutputCommitAttestation | None
    completion_evaluation: OutputCompletionEvaluation
    diagnostic_code: str | None
    diagnostic: str


def configured_output_completion_contract(request: AdapterRequest) -> OutputCompletionContract | None:
    """Parse and bind the optional output contract to the request path."""
    raw_contract = request.configuration.get(_OUTPUT_COMPLETION_CONTRACT_KEY)
    if raw_contract is None:
        return None
    contract = OutputCompletionContract.model_validate(raw_contract)
    if contract.output_path != request.output_path:
        raise ValueError("output completion contract output_path must match the adapter request output_path")
    return contract


def configured_output_completion_commit(
    request: AdapterRequest,
    *,
    contract: OutputCompletionContract | None,
) -> bool:
    """Validate whether explicit byte commitment is enabled for this request."""
    raw_value = request.configuration.get(_OUTPUT_COMPLETION_COMMIT_KEY, False)
    if not isinstance(raw_value, bool):
        raise ValueError("output_completion_commit must be a boolean")
    if raw_value and contract is None:
        raise ValueError("output_completion_commit requires an output completion contract")
    return raw_value


def read_output_completion_content(
    contract: OutputCompletionContract,
    *,
    candidate_path: Path | None = None,
) -> str | None:
    """Read a bounded regular UTF-8 output without following symbolic links."""
    output_path = Path(contract.output_path) if candidate_path is None else candidate_path
    try:
        path_stat = output_path.lstat()
    except OSError:
        return None
    if not stat.S_ISREG(path_stat.st_mode):
        logger.debug("Output completion contract rejected non-regular path: %s", output_path)
        return None

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(output_path, flags)
    except OSError:
        return None
    try:
        opened_stat = os.fstat(fd)
        if not _same_regular_file(opened_stat, path_stat):
            logger.debug("Output completion contract rejected changed or non-regular path: %s", output_path)
            return None
        if opened_stat.st_size > _OUTPUT_COMPLETION_MAX_BYTES:
            logger.debug("Output completion contract rejected oversized artifact: %s", output_path)
            return None
        with os.fdopen(fd, "rb", closefd=False) as stream:
            content = stream.read(_OUTPUT_COMPLETION_MAX_BYTES + 1)
    except OSError:
        return None
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
    if len(content) > _OUTPUT_COMPLETION_MAX_BYTES:
        logger.debug("Output completion contract rejected oversized artifact: %s", output_path)
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def changed_output_completion_contract_satisfied(
    contract: OutputCompletionContract,
    *,
    initial_content: str | None,
) -> bool:
    """Return whether a changed output now satisfies the declared structure."""
    content = read_output_completion_content(contract)
    if content is None or content == initial_content:
        return False
    return evaluate_output_completion(contract, content).complete


def build_output_commit_attestation(
    contract: OutputCompletionContract,
    *,
    initial_content: str | None,
    commit_turn: int,
    candidate_path: Path | None = None,
) -> tuple[OutputCommitAttestation | None, str]:
    """Bind the current complete artifact bytes to an immutable attestation."""
    decision = evaluate_output_commit_candidate(
        contract,
        initial_content=initial_content,
        commit_turn=commit_turn,
        candidate_path=candidate_path,
    )
    return decision.attestation, decision.diagnostic


def evaluate_output_commit_candidate(
    contract: OutputCompletionContract,
    *,
    initial_content: str | None,
    commit_turn: int,
    candidate_path: Path | None = None,
) -> OutputCommitDecision:
    """Evaluate and, when valid, attest the fixed candidate in one safe read."""
    content = read_output_completion_content(contract, candidate_path=candidate_path)
    if content is None:
        return OutputCommitDecision(
            attestation=None,
            completion_evaluation=evaluate_output_completion(contract, None),
            diagnostic_code="output_missing",
            diagnostic="output is missing or is not a safe UTF-8 regular file.",
        )
    evaluation = evaluate_output_completion(contract, content)
    if content == initial_content:
        return OutputCommitDecision(
            attestation=None,
            completion_evaluation=evaluation,
            diagnostic_code="output_unchanged",
            diagnostic="output is unchanged from the start of this run.",
        )
    if not evaluation.complete:
        return OutputCommitDecision(
            attestation=None,
            completion_evaluation=evaluation,
            diagnostic_code=evaluation.reason.value,
            diagnostic=f"output contract is incomplete ({evaluation.reason.value}).",
        )

    encoded = content.encode("utf-8")
    attestation = OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path=contract.output_path,
        output_sha256=hashlib.sha256(encoded).hexdigest(),
        output_size_bytes=len(encoded),
        completion_contract_sha256=canonical_content_sha256(contract.model_dump(mode="json")),
        completion_evaluation=evaluation,
        initial_output_sha256=(
            hashlib.sha256(initial_content.encode("utf-8")).hexdigest() if initial_content is not None else None
        ),
        commit_turn=commit_turn,
    )
    return OutputCommitDecision(
        attestation=attestation,
        completion_evaluation=evaluation,
        diagnostic_code=None,
        diagnostic=(
            f"exact artifact bound at sha256:{attestation.output_sha256} ({attestation.output_size_bytes} bytes)."
        ),
    )


def validate_stable_output_commit(
    contract: OutputCompletionContract,
    attestation: OutputCommitAttestation,
    *,
    candidate_path: Path | None = None,
) -> str | None:
    """Return a safe diagnostic if committed bytes changed after acceptance."""
    content = read_output_completion_content(contract, candidate_path=candidate_path)
    if content is None:
        return "committed artifact is no longer a safe UTF-8 regular file."
    encoded = content.encode("utf-8")
    if (
        hashlib.sha256(encoded).hexdigest() != attestation.output_sha256
        or len(encoded) != attestation.output_size_bytes
    ):
        return "artifact changed after the commit call."
    evaluation = evaluate_output_completion(contract, content)
    if not evaluation.complete:
        return f"output contract is incomplete ({evaluation.reason.value})."
    return None


def _same_regular_file(opened_stat: os.stat_result, path_stat: os.stat_result) -> bool:
    return (
        stat.S_ISREG(opened_stat.st_mode)
        and opened_stat.st_dev == path_stat.st_dev
        and opened_stat.st_ino == path_stat.st_ino
    )
