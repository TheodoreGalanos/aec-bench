# ABOUTME: Tests for verifier artifact ingestion in aec-bench Python.
# ABOUTME: Covers converting reward/details JSON files into an EvaluationResult.

from pathlib import Path

from aec_bench.harness.verifier_artifacts import read_verifier_artifacts


def test_read_verifier_artifacts_builds_evaluation_result(tmp_path: Path) -> None:
    reward_path = tmp_path / "reward.json"
    details_path = tmp_path / "details.json"
    reward_path.write_text('{"reward": 0.75}\n', encoding="utf-8")
    details_path.write_text('{"matched": 3, "missed": 1}\n', encoding="utf-8")

    evaluation = read_verifier_artifacts(
        reward_path=reward_path,
        details_path=details_path,
        output_parseable=True,
        schema_valid=True,
    )

    assert evaluation.reward == 0.75
    assert evaluation.validity.verifier_completed is True
    assert evaluation.breakdown == {"matched": 3, "missed": 1}


def test_read_verifier_artifacts_marks_missing_reward_as_failed_verifier(tmp_path: Path) -> None:
    evaluation = read_verifier_artifacts(
        reward_path=tmp_path / "missing.json",
        details_path=None,
        output_parseable=False,
        schema_valid=False,
    )

    assert evaluation.reward == 0.0
    assert evaluation.validity.verifier_completed is False
    assert evaluation.validity.errors == ["missing verifier reward artifact"]
