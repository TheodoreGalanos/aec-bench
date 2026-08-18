# ABOUTME: Tests reward-blind output-completion contracts and their structural evaluator.
# ABOUTME: Covers contract safety, drainage sidecars, scaffolding, and checked-task outputs.

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.harness_kernel import canonical_json_sha256
from aec_bench.contracts.output_completion import (
    OutputCommitAttestation,
    OutputCompletionContract,
    OutputCompletionEvaluation,
    OutputCompletionReason,
    evaluate_output_completion,
)
from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import load_template

REQUIRED_KEYS = (
    "source_inventory",
    "provenance_ledger",
    "review_matrix",
    "computed_evidence",
    "transition_decision",
    "findings",
    "information_requests",
    "action_register",
    "readiness_decision",
    "claim_boundary_statement",
)
TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "civil"
    / "drainage_model_run_provenance_issue_review_package"
)
CHECKED_TASKS_DIR = (
    Path(__file__).resolve().parents[2]
    / "tasks"
    / "civil"
    / "drainage-review"
    / "drainage-model-run-provenance-issue-review-package"
)
CHECKED_TASK_NAMES = (
    "industrial-precinct-catchment-industrial-precinct-catchment-00",
    "brownfield-drainage-upgrade-industrial-precinct-catchment-02",
)


def _contract_payload() -> dict[str, object]:
    return {
        "schema_version": "aecbench.output-completion-contract.v1",
        "output_path": "/workspace/output.md",
        "format": "markdown_final_fenced_json",
        "required_top_level_keys": list(REQUIRED_KEYS),
        "require_single_final_json_block": True,
    }


def _complete_markdown(*, omitted_keys: tuple[str, ...] = ()) -> str:
    payload = {key: None for key in REQUIRED_KEYS if key not in omitted_keys}
    return "# Review\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"


def test_contract_is_strict_frozen_and_reward_blind() -> None:
    contract = OutputCompletionContract.model_validate(_contract_payload())

    assert contract.schema_version == "aecbench.output-completion-contract.v1"
    assert contract.output_path == "/workspace/output.md"
    assert contract.format == "markdown_final_fenced_json"
    assert contract.required_top_level_keys == REQUIRED_KEYS
    assert contract.require_single_final_json_block is True

    with pytest.raises(ValidationError):
        contract.output_path = "/workspace/other.md"
    with pytest.raises(ValidationError, match="extra_forbidden"):
        OutputCompletionContract.model_validate(_contract_payload() | {"unexpected": True})


@pytest.mark.parametrize(
    "required_field",
    [
        "schema_version",
        "output_path",
        "format",
        "required_top_level_keys",
        "require_single_final_json_block",
    ],
)
def test_contract_requires_every_declared_field(required_field: str) -> None:
    payload = _contract_payload()
    del payload[required_field]

    with pytest.raises(ValidationError, match="Field required"):
        OutputCompletionContract.model_validate(payload)


@pytest.mark.parametrize(
    "leaking_payload",
    [
        {"reward": 1.0},
        {"nested": {"gold_values": {"answer": 42}}},
        {"nested": [{"verifier_details": "hidden"}]},
        {"nested": {"expected_value": 42}},
        {"nested": {"ground_truth": {"answer": 42}}},
    ],
)
def test_contract_rejects_leakage_keys_recursively(leaking_payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match="reward-blind contract rejects leakage key"):
        OutputCompletionContract.model_validate(_contract_payload() | leaking_payload)


@pytest.mark.parametrize("required_key", ["reward", "gold_answer", "verifier_score", "expected_value"])
def test_contract_rejects_leakage_names_in_required_output_keys(required_key: str) -> None:
    payload = _contract_payload()
    payload["required_top_level_keys"] = [*REQUIRED_KEYS, required_key]

    with pytest.raises(ValidationError, match="reward-blind contract rejects leakage key"):
        OutputCompletionContract.model_validate(payload)


@pytest.mark.parametrize(
    ("output_text", "expected_reason"),
    [
        (None, OutputCompletionReason.OUTPUT_MISSING),
        (" \n\t", OutputCompletionReason.OUTPUT_EMPTY),
        ("# Review without a final block", OutputCompletionReason.FINAL_JSON_BLOCK_MISSING),
        ("```json\n{not-json}\n```", OutputCompletionReason.FINAL_JSON_MALFORMED),
        ("```json\n[]\n```", OutputCompletionReason.FINAL_JSON_NOT_OBJECT),
        (
            "```json\n{}\n```\n\n```json\n{}\n```",
            OutputCompletionReason.MULTIPLE_FINAL_JSON_BLOCKS,
        ),
        (
            _complete_markdown() + "Trailing prose means the JSON block was not final.\n",
            OutputCompletionReason.FINAL_JSON_BLOCK_NOT_FINAL,
        ),
    ],
)
def test_structural_evaluator_rejects_incomplete_outputs(
    output_text: str | None,
    expected_reason: OutputCompletionReason,
) -> None:
    contract = OutputCompletionContract.model_validate(_contract_payload())

    result = evaluate_output_completion(contract, output_text)

    assert result.complete is False
    assert result.reason is expected_reason


def test_structural_evaluator_reports_missing_required_keys() -> None:
    contract = OutputCompletionContract.model_validate(_contract_payload())

    result = evaluate_output_completion(
        contract,
        _complete_markdown(omitted_keys=("readiness_decision", "claim_boundary_statement")),
    )

    assert result.complete is False
    assert result.reason is OutputCompletionReason.REQUIRED_TOP_LEVEL_KEYS_MISSING
    assert result.missing_top_level_keys == ("readiness_decision", "claim_boundary_statement")


def test_structural_evaluator_accepts_one_final_json_object_without_checking_values() -> None:
    contract = OutputCompletionContract.model_validate(_contract_payload())

    result = evaluate_output_completion(contract, _complete_markdown())

    assert result.complete is True
    assert result.reason is OutputCompletionReason.COMPLETE
    assert result.missing_top_level_keys == ()
    assert result.present_top_level_keys == REQUIRED_KEYS
    assert result.final_json_block_count == 1


def test_output_commit_attestation_binds_complete_artifact_and_contract() -> None:
    contract = OutputCompletionContract.model_validate(_contract_payload())
    output_text = _complete_markdown()
    evaluation = evaluate_output_completion(contract, output_text)
    contract_sha256 = canonical_json_sha256(contract.model_dump(mode="json"))

    attestation = OutputCommitAttestation(
        schema_version="aecbench.output-commit-attestation.v1",
        mechanism="agent_explicit_output_commit",
        output_path=contract.output_path,
        output_sha256="a" * 64,
        output_size_bytes=len(output_text.encode("utf-8")),
        completion_contract_sha256=contract_sha256,
        completion_evaluation=evaluation,
        initial_output_sha256=None,
        commit_turn=3,
    )

    assert attestation.completion_evaluation.reason is OutputCompletionReason.COMPLETE
    assert attestation.content_sha256
    assert OutputCommitAttestation.model_validate_json(attestation.model_dump_json()) == attestation


def test_output_commit_attestation_rejects_incomplete_evaluation() -> None:
    with pytest.raises(ValidationError, match="requires a complete structural evaluation"):
        OutputCommitAttestation(
            schema_version="aecbench.output-commit-attestation.v1",
            mechanism="agent_explicit_output_commit",
            output_path="/workspace/output.md",
            output_sha256="a" * 64,
            output_size_bytes=1,
            completion_contract_sha256="b" * 64,
            completion_evaluation=OutputCompletionEvaluation(
                complete=False,
                reason=OutputCompletionReason.OUTPUT_EMPTY,
            ),
            initial_output_sha256=None,
            commit_turn=1,
        )


def test_output_commit_attestation_rejects_unchanged_artifact_hash() -> None:
    with pytest.raises(ValidationError, match="must differ from initial output"):
        OutputCommitAttestation(
            schema_version="aecbench.output-commit-attestation.v1",
            mechanism="agent_explicit_output_commit",
            output_path="/workspace/output.md",
            output_sha256="a" * 64,
            output_size_bytes=1,
            completion_contract_sha256="b" * 64,
            completion_evaluation=OutputCompletionEvaluation(
                complete=True,
                reason=OutputCompletionReason.COMPLETE,
                final_json_block_count=1,
            ),
            initial_output_sha256="a" * 64,
            commit_turn=1,
        )


@pytest.mark.parametrize(
    "field_name",
    ["output_sha256", "completion_contract_sha256", "initial_output_sha256"],
)
def test_output_commit_attestation_rejects_invalid_hashes(field_name: str) -> None:
    payload = {
        "schema_version": "aecbench.output-commit-attestation.v1",
        "mechanism": "agent_explicit_output_commit",
        "output_path": "/workspace/output.md",
        "output_sha256": "a" * 64,
        "output_size_bytes": 1,
        "completion_contract_sha256": "b" * 64,
        "completion_evaluation": {
            "complete": True,
            "reason": "complete",
            "present_top_level_keys": [],
            "missing_top_level_keys": [],
            "final_json_block_count": 1,
        },
        "initial_output_sha256": "c" * 64,
        "commit_turn": 1,
    }
    payload[field_name] = "not-a-sha256"

    with pytest.raises(ValidationError, match="SHA-256"):
        OutputCommitAttestation.model_validate(payload)


def test_drainage_template_scaffolds_validated_contract_into_environment(tmp_path: Path) -> None:
    loaded_template = load_template(TEMPLATE_DIR)
    template_dir = loaded_template.path
    instance = sample_instance(loaded_template, "hard", seed=7_301, instance_index=0)

    task_dir = scaffold_task_instance(loaded_template, instance, tmp_path)

    template_contract = (template_dir / "output_contract.json").read_bytes()
    generated_contract_path = task_dir / "environment" / "output_contract.json"
    assert generated_contract_path.read_bytes() == template_contract
    contract = OutputCompletionContract.model_validate_json(generated_contract_path.read_text(encoding="utf-8"))
    assert contract.required_top_level_keys == REQUIRED_KEYS
    dockerfile = (task_dir / "environment" / "Dockerfile").read_text(encoding="utf-8")
    assert "output_contract.json" not in dockerfile


def test_checked_stage_one_tasks_carry_reward_blind_contracts_and_structurally_complete_fixtures() -> None:
    for task_name in CHECKED_TASK_NAMES:
        task_dir = CHECKED_TASKS_DIR / task_name
        contract_path = task_dir / "environment" / "output_contract.json"
        contract = OutputCompletionContract.model_validate_json(contract_path.read_text(encoding="utf-8"))

        assert contract.required_top_level_keys == REQUIRED_KEYS
        assert contract_path.read_bytes() == (TEMPLATE_DIR / "output_contract.json").read_bytes()
        for fixture_name in ("golden_pass.md", "golden_fail.md"):
            fixture = (task_dir / "tests" / "fixtures" / fixture_name).read_text(encoding="utf-8")
            result = evaluate_output_completion(contract, fixture)
            assert result.complete is True, (task_name, fixture_name, result)
