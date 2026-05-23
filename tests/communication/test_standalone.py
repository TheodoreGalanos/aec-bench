# ABOUTME: Tests standalone communication artefacts built from filtered ledger-backed records.
# ABOUTME: Verifies public/internal leaderboard behaviour and adaptation bundle exposure.

import json
from pathlib import Path

from aec_bench.communication.standalone import (
    build_adaptation_family_artifact,
    build_internal_experiment_artifact,
    build_internal_leaderboard_artifact,
    build_public_experiment_artifact,
    build_public_leaderboard_artifact,
    export_standalone_artifact_json,
)
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import (
    AdaptationProvenance,
    Completeness,
    DerivationStepRecord,
)
from aec_bench.ledger.writer import write_trial_record
from tests.support.trial_record_factories import make_trial_record


def test_build_public_and_internal_leaderboard_artifacts_apply_visibility_policy(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"}),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-002",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    public_payload = build_public_leaderboard_artifact(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
    )
    internal_payload = build_internal_leaderboard_artifact(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
    )

    assert public_payload["visibility_scope"] == "public"
    assert public_payload["leaderboard"]["entries"][0]["n_trials"] == 1
    assert internal_payload["visibility_scope"] == "internal"
    assert internal_payload["leaderboard"]["entries"][0]["n_trials"] == 2


def test_build_adaptation_family_artifact_returns_bundle_payload(tmp_path: Path) -> None:
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-alpha",
            experiment_id="experiment-001",
            adaptation=_adaptation(family_id="heat-load-family", variation_key="jurisdiction=us"),
            evaluation=EvaluationResult(
                reward=0.98,
                validity=ValidityCheck(
                    output_parseable=True,
                    schema_valid=True,
                    verifier_completed=True,
                ),
            ),
            completeness=Completeness.COMPLETE,
        ),
    )

    payload = build_adaptation_family_artifact(
        ledger_root=tmp_path / "ledger",
        family_id="heat-load-family",
        experiment_id="experiment-001",
    )
    output_path = export_standalone_artifact_json(payload, tmp_path / "adaptation_family.json")
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert written["artifact_type"] == "adaptation_family"
    assert written["family_id"] == "heat-load-family"
    assert written["bundle"]["preserved_trial_count"] == 1
    assert written["bundle"]["artefacts"][0]["trial_id"] == "trial-alpha"


def test_build_public_and_internal_experiment_artifacts_apply_visibility_policy(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/holdout-task",
        visibility=Visibility.HOLDOUT,
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"}),
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=make_trial_record(
            trial_id="trial-002",
            task={"task_id": "mechanical/heat-load/holdout-task", "task_revision": "git"},
        ),
    )

    public_payload = build_public_experiment_artifact(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        experiment_id="experiment-001",
    )
    internal_payload = build_internal_experiment_artifact(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        experiment_id="experiment-001",
    )

    assert public_payload["artifact_type"] == "experiment_report"
    assert public_payload["visibility_scope"] == "public"
    assert len(public_payload["report"]["trials"]) == 1
    assert internal_payload["visibility_scope"] == "internal"
    assert len(internal_payload["report"]["trials"]) == 2


def _write_task_instance(*, tasks_root: Path, relative_path: str, visibility: Visibility) -> None:
    instance_dir = tasks_root / relative_path
    (instance_dir / "environment").mkdir(parents=True)
    (instance_dir / "tests").mkdir(parents=True)
    (instance_dir / "instruction.md").write_text(
        "Write findings to /workspace/output.jsonl.\n",
        encoding="utf-8",
    )
    (instance_dir / "tests" / "test.sh").write_text("#!/bin/bash\n", encoding="utf-8")
    (instance_dir / "task.toml").write_text(
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )


def _adaptation(*, family_id: str, variation_key: str) -> AdaptationProvenance:
    variation_value = variation_key.split("=", maxsplit=1)[1]
    return AdaptationProvenance(
        family_id=family_id,
        seed_task_id="mechanical/heat-load/au-office",
        variation_key=variation_key,
        variation={"jurisdiction": variation_value},
        derivation_lineage=[
            DerivationStepRecord(
                axis="jurisdiction",
                parent_value="au",
                value=variation_value,
            )
        ],
    )
