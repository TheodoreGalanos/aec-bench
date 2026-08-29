# ABOUTME: Tests current lifecycle-study retention for released conditional evidence.
# ABOUTME: Exercises schema-2 finalization roles and reserved-artifact inventory checks end to end.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aec_bench.experimentation.lifecycle_studies.retention import recover_lifecycle_ablation_record
from aec_bench.ledger.reader import read_trial_record
from tests.support.lifecycle_studies import recorded_conditional_lifecycle_ablation_trial


def test_schema_two_recovery_finalizes_released_conditional_evidence_with_semantic_roles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, trial, package, run_dir = recorded_conditional_lifecycle_ablation_trial(tmp_path, monkeypatch)
    state = _read_json(run_dir / "state.json")
    actions = [action for checkpoint in state["checkpoint_runs"] for action in checkpoint["evidence_request_actions"]]
    assert state["schema_version"] == "6"
    assert [action["outcome"] for action in actions] == ["released"]

    record_path = recover_lifecycle_ablation_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    record = read_trial_record(record_path, ledger_root=Path(manifest.ledger_root))
    semantic_roles = {artifact.role for artifact in record.outputs.artifacts}
    assert {
        "evidence_request_action",
        "evidence_request_catalog",
        "evidence_request_commit",
        "requested_evidence",
        "requested_evidence_projection",
    } <= semantic_roles


def test_schema_two_recovery_rejects_undeclared_reserved_conditional_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, trial, package, run_dir = recorded_conditional_lifecycle_ablation_trial(tmp_path, monkeypatch)
    unexpected = run_dir / "evidence_requests" / "forged" / "action.json"
    unexpected.parent.mkdir(parents=True)
    unexpected.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="reserved artifact inventory"):
        recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )

    artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
    assert not artifact_dir.exists()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
