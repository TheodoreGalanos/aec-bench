# ABOUTME: Verifies typed output-commit attestations against collected Harbor artifacts and task contracts.
# ABOUTME: Keeps byte, size, turn, contract, and structural-evaluation checks outside import orchestration.

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any

from aec_bench.adapters.base import AdapterResult
from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    evaluate_output_completion,
)
from aec_bench.harness.harbor_importing.contracts import HarborImportError


def verify_output_commit(
    *,
    execution_result: AdapterResult | None,
    untrusted_agent_result: dict[str, Any],
    output_path: Path | None,
    expected_output_path: str,
    task_instance_dir: Path,
) -> dict[str, Any] | None:
    """Return the verified commit payload or reject any untrusted commit claim."""

    attestation = execution_result.completion_commit if execution_result is not None else None
    untrusted_claim = (
        untrusted_agent_result.get("completion_reason") == "output_contract_committed"
        or untrusted_agent_result.get("completion_commit") is not None
    )
    if attestation is None:
        if untrusted_claim:
            raise HarborImportError(
                "metadata-only output commit claim is not trusted without a typed execution result attestation"
            )
        return None
    if execution_result is None:
        raise HarborImportError(
            "output commit attestation requires a current execution result",
        )
    _validate_attestation_binding(
        attestation=attestation,
        execution_result=execution_result,
        expected_output_path=expected_output_path,
    )
    output_bytes = _read_committed_output(
        output_path=output_path,
        attestation=attestation,
    )
    contract = _load_completion_contract(
        task_instance_dir=task_instance_dir,
        expected_output_path=expected_output_path,
    )
    _validate_committed_output(
        attestation=attestation,
        contract=contract,
        output_bytes=output_bytes,
    )
    return attestation.model_dump(mode="json")


def _validate_attestation_binding(
    *,
    attestation: OutputCommitAttestation,
    execution_result: AdapterResult,
    expected_output_path: str,
) -> None:
    if attestation.output_path != expected_output_path:
        raise HarborImportError(
            "output commit path does not match the task expected output path",
        )
    if execution_result.agent_output.output_path != expected_output_path:
        raise HarborImportError(
            "output commit path does not match the executed agent output path",
        )
    if attestation.commit_turn != execution_result.turns_used:
        raise HarborImportError(
            "output commit turn does not match executed turns_used",
        )


def _read_committed_output(
    *,
    output_path: Path | None,
    attestation: OutputCommitAttestation,
) -> bytes:
    if output_path is None:
        raise HarborImportError(
            "output commit artifact is missing from collected Harbor artifacts",
        )
    try:
        output_stat = output_path.lstat()
    except OSError as error:
        raise HarborImportError(
            "output commit artifact cannot be inspected",
        ) from error
    if output_path.is_symlink() or not stat.S_ISREG(output_stat.st_mode):
        raise HarborImportError(
            "output commit artifact must be a non-symlink regular file",
        )
    try:
        output_bytes = output_path.read_bytes()
    except OSError as error:
        raise HarborImportError(
            "output commit artifact cannot be read",
        ) from error
    if hashlib.sha256(output_bytes).hexdigest() != attestation.output_sha256:
        raise HarborImportError(
            "output commit SHA-256 does not match the collected artifact",
        )
    if len(output_bytes) != attestation.output_size_bytes:
        raise HarborImportError(
            "output commit byte size does not match the collected artifact",
        )
    return output_bytes


def _load_completion_contract(
    *,
    task_instance_dir: Path,
    expected_output_path: str,
) -> OutputCompletionContract:
    contract_path = task_instance_dir / "environment" / "output_contract.json"
    try:
        contract_stat = contract_path.lstat()
    except OSError as error:
        raise HarborImportError(
            "output commit task contract is missing",
        ) from error
    if contract_path.is_symlink() or not stat.S_ISREG(contract_stat.st_mode):
        raise HarborImportError(
            "output commit task contract must be a non-symlink regular file",
        )
    try:
        contract = OutputCompletionContract.model_validate_json(
            contract_path.read_text(encoding="utf-8"),
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise HarborImportError(
            "output commit task contract is invalid",
        ) from error
    if contract.output_path != expected_output_path:
        raise HarborImportError(
            "output commit task contract path does not match expected output",
        )
    return contract


def _validate_committed_output(
    *,
    attestation: OutputCommitAttestation,
    contract: OutputCompletionContract,
    output_bytes: bytes,
) -> None:
    contract_sha256 = canonical_json_sha256(
        contract.model_dump(mode="json"),
    )
    if contract_sha256 != attestation.completion_contract_sha256:
        raise HarborImportError(
            "output commit contract SHA-256 does not match the task contract",
        )
    try:
        output_text = output_bytes.decode("utf-8")
    except UnicodeDecodeError as error:
        raise HarborImportError(
            "output commit artifact is not valid UTF-8",
        ) from error
    evaluation = evaluate_output_completion(contract, output_text)
    if evaluation != attestation.completion_evaluation:
        raise HarborImportError(
            "output commit structural evaluation does not match the collected artifact",
        )


__all__ = ("verify_output_commit",)
