# ABOUTME: Tests receipt-driven evaluation status and reward mapping.
# ABOUTME: Proves verifier process truth overrides stale legacy evaluation fields.

from datetime import UTC, datetime
from typing import Any

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.contracts.trial_extensions import (
    ArtifactReference,
    VerifierExecutionReceipt,
    VerifierOutputParseStatus,
)
from aec_bench.contracts.trial_record import EvaluationStatus
from aec_bench.evaluation.verifier_outcome import map_verifier_execution

EXPECTED_KEY = "civil/check/verifier"
EXPECTED_VERSION = 1


def _artifact(kind: str) -> ArtifactReference:
    return ArtifactReference(
        kind=kind,
        path=f"logs/verifier/{kind}.json",
        sha256="a" * 64,
        media_type="application/json",
    )


def _receipt(**updates: Any) -> VerifierExecutionReceipt:
    started_at = datetime(2026, 1, 1, tzinfo=UTC)
    payload: dict[str, object] = {
        "receipt_id": new_entity_id(EntityKind.RECEIPT),
        "verifier_key": EXPECTED_KEY,
        "verifier_version": EXPECTED_VERSION,
        "started_at": started_at,
        "finished_at": started_at,
        "duration_seconds": 0.0,
        "command_name": "python3",
        "exit_code": 0,
        "timed_out": False,
        "cancelled": False,
        "reward_artifact": _artifact("verifier_reward"),
        "output_parse_status": VerifierOutputParseStatus.VALID,
        "runtime_transform_version": 1,
    }
    return VerifierExecutionReceipt.model_validate({**payload, **updates})


def _evaluation(*, reward: float = 0.75, verifier_completed: bool = True) -> EvaluationResult:
    return EvaluationResult(
        reward=reward,
        validity=ValidityCheck(
            output_parseable=True,
            schema_valid=True,
            verifier_completed=verifier_completed,
        ),
    )


@pytest.mark.parametrize(
    ("receipt_updates", "status"),
    [
        ({"output_parse_status": VerifierOutputParseStatus.MALFORMED}, EvaluationStatus.INVALID),
        ({"output_parse_status": VerifierOutputParseStatus.MISSING, "reward_artifact": None}, EvaluationStatus.FAILED),
        ({"exit_code": 3}, EvaluationStatus.FAILED),
        ({"timed_out": True, "exit_code": None}, EvaluationStatus.FAILED),
        ({"cancelled": True, "exit_code": None}, EvaluationStatus.FAILED),
    ],
)
def test_failed_receipt_never_completes_or_accepts_reward(
    receipt_updates: dict[str, object],
    status: EvaluationStatus,
) -> None:
    mapped = map_verifier_execution(
        receipt=_receipt(**receipt_updates),
        evaluation=_evaluation(),
        expected_verifier_key=EXPECTED_KEY,
        expected_verifier_version=EXPECTED_VERSION,
    )

    assert mapped.status is status
    assert mapped.evaluation.reward == 0.0
    assert mapped.evaluation.validity.verifier_completed is False


def test_success_receipt_completes_and_overrides_legacy_verifier_flag() -> None:
    mapped = map_verifier_execution(
        receipt=_receipt(),
        evaluation=_evaluation(reward=0.75, verifier_completed=False),
        expected_verifier_key=EXPECTED_KEY,
        expected_verifier_version=EXPECTED_VERSION,
    )

    assert mapped.status is EvaluationStatus.COMPLETED
    assert mapped.evaluation.reward == 0.75
    assert mapped.evaluation.validity.verifier_completed is True


@pytest.mark.parametrize("field", ["verifier_key", "verifier_version"])
def test_verifier_identity_mismatch_is_invalid_and_rejects_reward(field: str) -> None:
    value: object = "other/verifier" if field == "verifier_key" else 2
    mapped = map_verifier_execution(
        receipt=_receipt(**{field: value}),
        evaluation=_evaluation(reward=1.0),
        expected_verifier_key=EXPECTED_KEY,
        expected_verifier_version=EXPECTED_VERSION,
    )

    assert mapped.status is EvaluationStatus.INVALID
    assert mapped.evaluation.reward == 0.0
    assert mapped.evaluation.validity.verifier_completed is False
    assert "verifier identity mismatch" in mapped.evaluation.validity.errors


def test_failed_receipt_overrides_completed_legacy_evaluation() -> None:
    mapped = map_verifier_execution(
        receipt=_receipt(exit_code=7),
        evaluation=_evaluation(reward=1.0, verifier_completed=True),
        expected_verifier_key=EXPECTED_KEY,
        expected_verifier_version=EXPECTED_VERSION,
    )

    assert mapped.status is EvaluationStatus.FAILED
    assert mapped.evaluation.reward == 0.0
    assert mapped.evaluation.validity.verifier_completed is False
