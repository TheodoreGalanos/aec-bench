# ABOUTME: Tests for evaluation artifact persistence in the ledger.
# ABOUTME: Validates write, read, list operations for _evaluations/ directory.

from pathlib import Path

from aec_bench.evaluation.artifact import (
    EvaluationArtifact,
    EvaluationFilters,
    list_evaluation_artifacts,
    read_evaluation_artifact,
    write_evaluation_artifact,
)


def _make_artifact(**overrides) -> EvaluationArtifact:
    """Build a minimal EvaluationArtifact for testing."""
    from datetime import UTC, datetime

    payload = {
        "evaluation_id": "eval-001",
        "experiment_id": "experiment-001",
        "timestamp": datetime.now(tz=UTC),
        "filters": EvaluationFilters(),
        "summary": {"n_trials": 10, "mean_reward": 0.75, "total_cost_usd": 1.50},
        "behavioral": None,
        "framework_version": "0.1.0",
    }
    payload.update(overrides)
    return EvaluationArtifact.model_validate(payload)


def test_write_evaluation_artifact(tmp_path: Path) -> None:
    """Write should create a file in _evaluations/ directory."""
    artifact = _make_artifact()
    path = write_evaluation_artifact(tmp_path, artifact)
    assert path.exists()
    assert "_evaluations" in str(path)
    assert path.name == "eval-001.json"


def test_read_evaluation_artifact(tmp_path: Path) -> None:
    """Round-trip: write then read should return equivalent artifact."""
    artifact = _make_artifact()
    path = write_evaluation_artifact(tmp_path, artifact)
    loaded = read_evaluation_artifact(path)
    assert loaded.evaluation_id == artifact.evaluation_id
    assert loaded.summary == artifact.summary


def test_list_evaluation_artifacts(tmp_path: Path) -> None:
    """List should return all artifacts for an experiment, sorted by timestamp."""
    a1 = _make_artifact(evaluation_id="eval-001")
    a2 = _make_artifact(evaluation_id="eval-002")
    write_evaluation_artifact(tmp_path, a1)
    write_evaluation_artifact(tmp_path, a2)
    artifacts = list_evaluation_artifacts(tmp_path, experiment_id="experiment-001")
    assert len(artifacts) == 2


def test_artifact_has_correct_fields(tmp_path: Path) -> None:
    """Artifact should have all expected fields populated."""
    artifact = _make_artifact()
    path = write_evaluation_artifact(tmp_path, artifact)
    loaded = read_evaluation_artifact(path)
    assert loaded.evaluation_id == "eval-001"
    assert loaded.experiment_id == "experiment-001"
    assert loaded.framework_version == "0.1.0"
    assert loaded.filters.adapter is None
