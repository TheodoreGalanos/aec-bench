# ABOUTME: Tests standalone communication artefacts built from filtered ledger-backed records.
# ABOUTME: Verifies public and internal leaderboard and experiment visibility.

from pathlib import Path

from aec_bench.communication.standalone import (
    build_internal_experiment_artifact,
    build_internal_leaderboard_artifact,
    build_public_experiment_artifact,
    build_public_leaderboard_artifact,
)
from aec_bench.contracts.task_definition import Visibility
from aec_bench.contracts.trial_record import AgentReference, OutputRecord
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


def test_public_experiment_artifact_excludes_runtime_and_episode_private_data(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _write_task_instance(
        tasks_root=tasks_root,
        relative_path="mechanical/heat-load/public-task",
        visibility=Visibility.PUBLIC,
    )
    episode_path = tmp_path / "private" / "run" / "state" / "inventory.json"
    episode_path.parent.mkdir(parents=True)
    episode_path.write_text("{}\n", encoding="utf-8")
    record = make_trial_record(
        task={"task_id": "mechanical/heat-load/public-task", "task_revision": "git"},
        agent=AgentReference(
            adapter="tool_loop",
            model="test-model",
            adapter_revision="test-revision",
            configuration={"provider_api_key": "secret-provider-key", "recovery_path": "private/run/state"},
        ),
        outputs=OutputRecord(
            agent_result={"verifier_path": "private/verifier/details.json", "sealed_id": "sealed-target-1"},
            terminated=True,
        ),
    )
    record.attach_artifact(
        "output:episode-inventory:0",
        episode_path,
        media_type="application/json",
        logical_path="private/run/state/inventory.json",
    )
    write_trial_record(
        ledger_root=tmp_path / "ledger",
        record=record,
    )

    payload = build_public_experiment_artifact(
        ledger_root=tmp_path / "ledger",
        tasks_root=tasks_root,
        experiment_id="experiment-001",
    )
    serialized = str(payload)

    assert "secret-provider-key" not in serialized
    assert "private/run/state" not in serialized
    assert "private/verifier" not in serialized
    assert "sealed-target-1" not in serialized


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
        f'[identity]\nid = "019c2c7a-5a33-7b8d-a702-8f7f3e8c21aa"\nkey = "{relative_path}"\nversion = 1\n\n'
        f'[agent]\ntimeout_sec = 600\n\n[metadata]\nlifecycle = "active"\nvisibility = "{visibility.value}"\n',
        encoding="utf-8",
    )
