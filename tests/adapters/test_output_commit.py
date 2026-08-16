# ABOUTME: Tests the provider-neutral output-commit authority used by execution adapters.
# ABOUTME: Proves safe reads, exact-byte attestation, rejection, and post-commit stability.

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.output_commit import (
    build_output_commit_attestation,
    configured_output_completion_commit,
    configured_output_completion_contract,
    read_output_completion_content,
    validate_stable_output_commit,
)
from aec_bench.contracts.output_completion import OutputCompletionContract


def _contract(output_path: Path) -> OutputCompletionContract:
    return OutputCompletionContract.model_validate(
        {
            "schema_version": "aecbench.output-completion-contract.v1",
            "output_path": str(output_path),
            "format": "markdown_final_fenced_json",
            "required_top_level_keys": ["findings", "summary"],
            "require_single_final_json_block": True,
        }
    )


def _complete_output(label: str = "Review") -> str:
    return f'{label}\n```json\n{{"findings": [], "summary": {{}}}}\n```\n'


def test_request_configuration_binds_commit_to_the_declared_output_path(tmp_path: Path) -> None:
    contract = _contract(tmp_path / "output.md")
    request = AdapterRequest(
        instruction="Produce the output.",
        output_path=contract.output_path,
        configuration={
            "output_completion_contract": contract.model_dump(mode="json"),
            "output_completion_commit": True,
        },
    )

    configured_contract = configured_output_completion_contract(request)

    assert configured_contract == contract
    assert configured_output_completion_commit(request, contract=configured_contract) is True


def test_commit_attests_exact_bytes_and_detects_later_mutation(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    content = _complete_output()
    output_path.write_text(content, encoding="utf-8")
    contract = _contract(output_path)

    attestation, diagnostic = build_output_commit_attestation(
        contract,
        initial_content=None,
        commit_turn=2,
    )

    assert attestation is not None
    assert diagnostic.startswith("exact artifact bound at sha256:")
    assert attestation.output_sha256 == hashlib.sha256(content.encode()).hexdigest()
    assert attestation.output_size_bytes == len(content.encode())
    assert validate_stable_output_commit(contract, attestation) is None

    output_path.write_text(_complete_output("Changed"), encoding="utf-8")

    assert validate_stable_output_commit(contract, attestation) == "artifact changed after the commit call."


def test_commit_rejects_unchanged_output(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    content = _complete_output()
    output_path.write_text(content, encoding="utf-8")

    attestation, diagnostic = build_output_commit_attestation(
        _contract(output_path),
        initial_content=content,
        commit_turn=1,
    )

    assert attestation is None
    assert diagnostic == "output is unchanged from the start of this run."


def test_safe_reader_rejects_symbolic_links(tmp_path: Path) -> None:
    target = tmp_path / "target.md"
    target.write_text(_complete_output(), encoding="utf-8")
    output_path = tmp_path / "output.md"
    output_path.symlink_to(target)

    assert read_output_completion_content(_contract(output_path)) is None


def test_commit_configuration_requires_a_contract() -> None:
    request = AdapterRequest(
        instruction="Produce the output.",
        configuration={"output_completion_commit": True},
    )

    with pytest.raises(ValueError, match="requires an output completion contract"):
        configured_output_completion_commit(request, contract=None)
