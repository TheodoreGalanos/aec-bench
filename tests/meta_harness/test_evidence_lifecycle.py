# ABOUTME: Tests staged evidence release and checkpoint persistence in the meta-harness.
# ABOUTME: Covers disclosure, submission gates, tamper detection, resume, and parent task-run evidence.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

import aec_bench.meta_harness.evidence_lifecycle as lifecycle_runtime
import aec_bench.meta_harness.evidence_lifecycle_local as lifecycle_local_runtime
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    branch_evidence_lifecycle,
    build_evidence_lifecycle_task_run_resolver,
    fail_checkpoint_attempt,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    read_evidence_lifecycle_state,
    revisit_evidence_checkpoint,
    run_evidence_lifecycle,
    submit_evidence_checkpoint,
    validate_lifecycle_verification,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    EvidenceLifecycleControlTool,
    EvidenceLifecycleWorkspaceTool,
    LifecycleVisibilityPolicy,
    build_local_evidence_lifecycle_episode_resolver,
    run_local_evidence_lifecycle_fresh_context,
    run_local_evidence_lifecycle_session,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    CheckpointRunRecord,
    CheckpointRunStatus,
    EvidenceLifecycleRunState,
    LifecycleRunStatus,
)
from aec_bench.task_world_templates.contracts import EvidenceCheckpointSpec, EvidenceLifecycleSpec


def test_lifecycle_contract_rejects_duplicate_ids_and_path_escape() -> None:
    checkpoint = _checkpoint("initial_review")

    with pytest.raises(ValidationError, match="checkpoint ids must be unique"):
        EvidenceLifecycleSpec(
            lifecycle_id="lifecycle.demo",
            world_id="world.demo",
            checkpoints=[checkpoint, checkpoint],
        )

    with pytest.raises(ValidationError, match="must stay within the lifecycle package"):
        EvidenceCheckpointSpec(
            checkpoint_id="escaped",
            title="Escaped release",
            release_path="../private",
            instruction_path="instructions/escaped.md",
            submission_path="submissions/escaped.json",
        )


@pytest.mark.parametrize("checkpoint_id", ["../outside", "nested/checkpoint", "/absolute", "."])
def test_lifecycle_contract_rejects_unsafe_checkpoint_ids(checkpoint_id: str) -> None:
    with pytest.raises(ValidationError, match="checkpoint_id must be a safe path segment"):
        _checkpoint(checkpoint_id)


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("release_path", "hidden/gold", "release_path must be under releases/"),
        ("instruction_path", "hidden/instruction.md", "instruction_path must be under instructions/"),
        ("submission_path", "instruction.md", "submission_path must be under submissions/"),
    ],
)
def test_lifecycle_contract_enforces_path_namespaces(field_name: str, value: str, message: str) -> None:
    payload = _checkpoint("initial_review").model_dump()
    payload[field_name] = value

    with pytest.raises(ValidationError, match=message):
        EvidenceCheckpointSpec.model_validate(payload)


def test_lifecycle_contract_rejects_duplicate_submission_paths() -> None:
    initial = _checkpoint("initial_review")
    response = _checkpoint("response_review").model_copy(update={"submission_path": initial.submission_path})

    with pytest.raises(ValidationError, match="submission paths must be unique"):
        EvidenceLifecycleSpec(
            lifecycle_id="lifecycle.demo",
            world_id="world.demo",
            checkpoints=[initial, response],
        )


def test_lifecycle_state_rejects_contradictory_active_and_complete_state() -> None:
    with pytest.raises(ValidationError, match="complete lifecycle cannot have an active checkpoint"):
        EvidenceLifecycleRunState(
            lifecycle_id="lifecycle.demo",
            world_id="world.demo",
            lifecycle_spec_sha256="spec-sha",
            package_sha256="package-sha",
            status=LifecycleRunStatus.COMPLETE,
            active_checkpoint_id="initial_review",
            checkpoint_runs=[
                CheckpointRunRecord(
                    checkpoint_id="initial_review",
                    status=CheckpointRunStatus.ACTIVE,
                )
            ],
        )


def test_verification_contract_rejects_out_of_range_and_inconsistent_results() -> None:
    with pytest.raises(ValidationError, match="less than or equal to 1"):
        validate_lifecycle_verification(
            {
                "lifecycle_id": "lifecycle.demo",
                "overall": "pass",
                "passed": True,
                "reward": 1.1,
                "gates": {"demo": {"passed": True, "score": 1.0, "failures": []}},
            }
        )
    with pytest.raises(ValidationError, match="passed must agree with overall"):
        validate_lifecycle_verification(
            {
                "lifecycle_id": "lifecycle.demo",
                "overall": "pass",
                "passed": False,
                "reward": 0.5,
                "gates": {"demo": {"passed": False, "score": 0.5, "failures": ["demo"]}},
            }
        )


def test_verification_contract_preserves_legacy_shape_without_semantic_metrics() -> None:
    result = validate_lifecycle_verification(
        {
            "lifecycle_id": "lifecycle.demo",
            "overall": "pass",
            "passed": True,
            "reward": 1.0,
            "gates": {"demo": {"passed": True, "score": 1.0, "failures": []}},
        }
    )

    assert "semantic_metrics" not in result


def test_verification_contract_rejects_inconsistent_semantic_metric_counts() -> None:
    with pytest.raises(ValidationError, match="unsupported_update_count must equal"):
        validate_lifecycle_verification(
            {
                "lifecycle_id": "lifecycle.demo",
                "overall": "pass",
                "passed": True,
                "reward": 1.0,
                "gates": {"demo": {"passed": True, "score": 1.0, "failures": []}},
                "semantic_metrics": {
                    "initial_checkpoint_id": "initial_review",
                    "initial": {"correct_atoms": 1, "total_atoms": 1, "accuracy": 1.0},
                    "transitions": [],
                    "aggregate": {
                        "expected_update_count": 0,
                        "actual_update_count": 0,
                        "aligned_update_count": 0,
                        "updated_to_expected_count": 0,
                        "acquired_update_count": 0,
                        "unsupported_update_count": 1,
                        "stable_correct_before_count": 0,
                        "retained_count": 0,
                        "interference_count": 0,
                        "acquisition": None,
                        "update_precision": None,
                        "update_recall": None,
                        "update_f1": None,
                        "retention": None,
                        "interference": None,
                    },
                },
            }
        )


def test_session_id_uses_highest_existing_sequence(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    (sessions / "session-001").mkdir(parents=True)
    (sessions / "session-003").mkdir()

    assert lifecycle_local_runtime._next_session_id(tmp_path) == "session-004"


def test_prepare_releases_only_the_active_checkpoint(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    prepared = prepare_evidence_checkpoint(package, run_dir)
    workspace = Path(prepared["workspace"])

    assert prepared["status"] == "awaiting_checkpoint_submission"
    assert prepared["checkpoint_id"] == "initial_review"
    assert (workspace / "inbox" / "initial_review" / "initial.txt").read_text() == "initial evidence\n"
    assert not (workspace / "inbox" / "response_review").exists()
    assert "initial review" in (workspace / "instruction.md").read_text().lower()


def test_lifecycle_state_persists_first_class_checkpoint_records(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    prepare_evidence_checkpoint(package, run_dir)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))

    assert state["schema_version"] == "3"
    assert state["lifecycle_spec_sha256"]
    assert state["package_sha256"]
    assert state["status"] == "awaiting_checkpoint_submission"
    assert [item["checkpoint_id"] for item in state["checkpoint_runs"]] == [
        "initial_review",
        "response_review",
    ]
    assert state["checkpoint_runs"][0]["status"] == "active"
    assert state["checkpoint_runs"][1]["status"] == "pending"
    assert state["transitions"] == [
        {
            "transition_id": "transition-001",
            "kind": "release",
            "from_checkpoint_id": None,
            "to_checkpoint_id": "initial_review",
            "reason": "Evidence released for active review.",
        }
    ]


def test_lifecycle_state_migrates_legacy_dictionary_shape(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    archived_submission = run_dir / "episodes" / "initial_review" / "submission.json"
    workspace_submission = run_dir / "workspace" / "submissions" / "initial_review.json"
    _write_json(archived_submission, {"checkpoint_id": "initial_review"})
    _write_json(workspace_submission, {"checkpoint_id": "initial_review"})
    submission_sha256 = lifecycle_runtime._sha256(archived_submission)
    _write_json(
        run_dir / "state.json",
        {
            "lifecycle_id": "lifecycle.demo",
            "world_id": "world.demo",
            "status": "awaiting_checkpoint_submission",
            "active_checkpoint_id": "response_review",
            "active_released_files": ["response.txt"],
            "completed_checkpoints": [
                {
                    "checkpoint_id": "initial_review",
                    "submission_path": "submissions/initial_review.json",
                    "submission_sha256": submission_sha256,
                    "released_files": ["initial.txt"],
                }
            ],
        },
    )

    state = read_evidence_lifecycle_state(package, run_dir)
    persisted = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))

    assert state["active_checkpoint_id"] == "response_review"
    assert persisted["schema_version"] == "3"
    assert [item["status"] for item in persisted["checkpoint_runs"]] == ["submitted", "active"]


def test_lifecycle_state_migrates_v2_records_without_losing_attempts(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent",
    )
    state_path = run_dir / "state.json"
    state = _load_json(state_path)
    state["schema_version"] = "2"
    state.pop("lifecycle_spec_sha256")
    state.pop("package_sha256")
    _write_json(state_path, state)

    migrated = read_evidence_lifecycle_state(package, run_dir)

    assert _load_json(state_path)["schema_version"] == "3"
    assert migrated["checkpoint_runs"][0]["attempts"][0]["session_id"] == "session-001"


def test_open_checkpoint_attempt_marks_abandoned_attempt_interrupted(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)

    first = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent",
    )
    second = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-002",
        execution_mode="persistent",
    )
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    attempts = state["checkpoint_runs"][0]["attempts"]

    assert first["attempt_id"] == "initial_review.attempt-001"
    assert second["attempt_id"] == "initial_review.attempt-002"
    assert [attempt["status"] for attempt in attempts] == ["interrupted", "active"]
    assert second["resumed_from_attempt_id"] == first["attempt_id"]


def test_failed_checkpoint_attempt_is_closed_and_resumed_explicitly(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    first = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )

    failed = fail_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        failure_kind="provider_error",
    )
    resumed = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-002",
        execution_mode="persistent_context",
    )

    state = _load_json(run_dir / "state.json")
    attempts = state["checkpoint_runs"][0]["attempts"]
    assert failed == {
        **first,
        "status": "failed",
        "failure_kind": "provider_error",
    }
    assert [attempt["status"] for attempt in attempts] == ["failed", "active"]
    assert resumed["resumed_from_attempt_id"] == first["attempt_id"]


def test_fail_checkpoint_attempt_rejects_wrong_or_inactive_session(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )

    with pytest.raises(EvidenceLifecycleError, match="active attempt belongs to session-001"):
        fail_checkpoint_attempt(
            package,
            run_dir,
            session_id="session-002",
            failure_kind="provider_error",
        )

    fail_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        failure_kind="provider_error",
    )
    with pytest.raises(EvidenceLifecycleError, match="no checkpoint attempt is active"):
        fail_checkpoint_attempt(
            package,
            run_dir,
            session_id="session-001",
            failure_kind="provider_error",
        )


def test_revisit_returns_immutable_prior_snapshot_without_rewinding_state(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    initial = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(initial["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, run_dir)
    prepare_evidence_checkpoint(package, run_dir)

    revisit = revisit_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        reason="Recheck the source identity before closeout.",
    )
    state = read_evidence_lifecycle_state(package, run_dir)

    assert revisit["revisit_id"] == "revisit-001"
    assert revisit["checkpoint_id"] == "initial_review"
    assert revisit["submission"]["checkpoint_id"] == "initial_review"
    assert state["active_checkpoint_id"] == "response_review"
    assert state["revisits"][0]["reason"] == "Recheck the source identity before closeout."
    assert state["transitions"][-1]["kind"] == "revisit"
    assert state["transitions"][-1]["from_checkpoint_id"] == "response_review"
    assert state["transitions"][-1]["to_checkpoint_id"] == "initial_review"


def test_branch_reopens_selected_checkpoint_without_mutating_parent(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    parent_state_before = (parent_run / "state.json").read_bytes()

    branch = branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="initial_review",
        branch_id="branch.recheck-initial",
        reason="Reconsider the initial source interpretation.",
    )

    assert (parent_run / "state.json").read_bytes() == parent_state_before
    assert branch["active_checkpoint_id"] == "initial_review"
    assert branch["completed_checkpoints"] == []
    assert branch["branch"]["parent_run_dir"] == str(parent_run)
    assert branch["branch"]["branched_from_checkpoint_id"] == "initial_review"
    assert sorted(path.name for path in (branch_run / "workspace" / "inbox").iterdir()) == ["initial_review"]
    assert not (branch_run / "workspace" / "inbox" / "response_review").exists()
    assert _load_json(branch_run / "workspace" / "branch_origin" / "initial_review.json") == {
        "checkpoint_id": "initial_review"
    }
    assert _load_json(branch_run / "workspace" / "submissions" / "initial_review.json") == {
        "checkpoint_id": "initial_review"
    }
    assert branch["transitions"][0]["kind"] == "branch"


def test_branch_rejects_package_drift_from_parent_run(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    (package / "releases" / "initial_review" / "initial.txt").write_text(
        "Package evidence changed after the parent run.",
        encoding="utf-8",
    )
    (package / "instructions" / "initial_review.md").write_text(
        "Package instruction changed after the parent run.",
        encoding="utf-8",
    )

    with pytest.raises(EvidenceLifecycleError, match="package does not match lifecycle run"):
        branch_evidence_lifecycle(
            package,
            parent_run,
            branch_run,
            checkpoint_id="initial_review",
            branch_id="branch.parent-state",
            reason="Re-run against the evidence actually observed by the parent.",
        )


def test_branch_inherits_only_submissions_before_selected_checkpoint(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)

    branch = branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="response_review",
        branch_id="branch.recheck-response",
        reason="Re-evaluate the response against the initial finding.",
    )

    assert [item["checkpoint_id"] for item in branch["completed_checkpoints"]] == ["initial_review"]
    assert branch["active_checkpoint_id"] == "response_review"
    assert (branch_run / "episodes" / "initial_review" / "submission.json").exists()
    assert not (branch_run / "episodes" / "response_review" / "submission.json").exists()
    assert sorted(path.name for path in (branch_run / "workspace" / "inbox").iterdir()) == [
        "initial_review",
        "response_review",
    ]


def test_branch_rejects_unsubmitted_checkpoint_and_existing_destination(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    prepare_evidence_checkpoint(package, parent_run)

    with pytest.raises(EvidenceLifecycleError, match="checkpoint is not available for branching"):
        branch_evidence_lifecycle(
            package,
            parent_run,
            tmp_path / "unsubmitted-branch",
            checkpoint_id="initial_review",
            branch_id="branch.unsubmitted",
            reason="This checkpoint is still active.",
        )

    _write_json(
        parent_run / "workspace" / "submissions" / "initial_review.json",
        {"checkpoint_id": "initial_review"},
    )
    submit_evidence_checkpoint(package, parent_run)
    existing_branch = tmp_path / "existing-branch"
    existing_branch.mkdir()
    with pytest.raises(EvidenceLifecycleError, match="branch run directory already exists"):
        branch_evidence_lifecycle(
            package,
            parent_run,
            existing_branch,
            checkpoint_id="initial_review",
            branch_id="branch.existing",
            reason="Do not overwrite an existing derived run.",
        )


def test_branch_rejects_modified_parent_snapshot(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="initial_review",
        branch_id="branch.tamper-check",
        reason="Reconsider the initial review.",
    )
    _write_json(
        branch_run / "workspace" / "branch_origin" / "initial_review.json",
        {"checkpoint_id": "initial_review", "changed": True},
    )

    with pytest.raises(EvidenceLifecycleError, match="branch origin submission changed"):
        submit_evidence_checkpoint(package, branch_run)


def test_submission_gate_does_not_release_next_checkpoint_automatically(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    submission = Path(prepared["submission_path"])
    _write_json(submission, {"checkpoint_id": "initial_review", "value": "submitted"})

    submitted = submit_evidence_checkpoint(package, run_dir)
    workspace = Path(prepared["workspace"])

    assert submitted["status"] == "awaiting_evidence_release"
    assert not (workspace / "inbox" / "response_review").exists()

    resumed = prepare_evidence_checkpoint(package, run_dir)
    assert resumed["checkpoint_id"] == "response_review"
    assert (workspace / "inbox" / "response_review" / "response.txt").exists()
    assert (workspace / "submissions" / "initial_review.json").exists()


def test_submission_gate_requires_checkpoint_declared_fields(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    contract_path = package / "lifecycle.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["checkpoints"][0]["required_submission_fields"] = ["checkpoint_id", "review_matrix"]
    _write_json(contract_path, contract)
    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(prepared["submission_path"]), {"checkpoint_id": "initial_review"})

    with pytest.raises(EvidenceLifecycleError, match="missing required fields: review_matrix"):
        submit_evidence_checkpoint(package, run_dir)


def test_prior_submission_tampering_blocks_later_checkpoint(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    first = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(first["submission_path"]), {"checkpoint_id": "initial_review", "value": "original"})
    submit_evidence_checkpoint(package, run_dir)
    second = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(first["submission_path"]), {"checkpoint_id": "initial_review", "value": "rewritten"})
    _write_json(Path(second["submission_path"]), {"checkpoint_id": "response_review", "value": "submitted"})

    with pytest.raises(EvidenceLifecycleError, match="prior checkpoint submission changed"):
        submit_evidence_checkpoint(package, run_dir)


def test_archived_submission_tampering_blocks_status_revisit_and_verification(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    first = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(first["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, run_dir)
    archive = run_dir / "episodes" / "initial_review" / "submission.json"
    _write_json(archive, {"checkpoint_id": "initial_review", "rewritten": True})

    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed"):
        read_evidence_lifecycle_state(package, run_dir)
    with pytest.raises(EvidenceLifecycleError, match="archived checkpoint submission changed"):
        revisit_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            reason="Inspect the archived submission.",
        )


def test_prepare_recovers_from_interrupted_release_materialization(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    instruction = package / "instructions" / "initial_review.md"
    content = instruction.read_text(encoding="utf-8")
    instruction.unlink()

    with pytest.raises(EvidenceLifecycleError, match="checkpoint instruction not found"):
        prepare_evidence_checkpoint(package, run_dir)

    instruction.write_text(content, encoding="utf-8")
    prepared = prepare_evidence_checkpoint(package, run_dir)

    assert prepared["checkpoint_id"] == "initial_review"
    assert (run_dir / "workspace" / "inbox" / "initial_review" / "initial.txt").is_file()


def test_prepare_recovers_when_state_commit_fails_after_release(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    original_write_state = lifecycle_runtime._write_state
    calls = 0

    def fail_second_write(path: Path, state: EvidenceLifecycleRunState) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated state commit failure")
        original_write_state(path, state)

    monkeypatch.setattr(lifecycle_runtime, "_write_state", fail_second_write)
    with pytest.raises(RuntimeError, match="simulated state commit failure"):
        prepare_evidence_checkpoint(package, run_dir)

    monkeypatch.setattr(lifecycle_runtime, "_write_state", original_write_state)
    prepared = prepare_evidence_checkpoint(package, run_dir)

    assert prepared["checkpoint_id"] == "initial_review"
    assert prepared["status"] == "awaiting_checkpoint_submission"


def test_prepare_reconciles_transition_ledger_after_append_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    original_append = lifecycle_runtime.append_ledger_entry
    calls = 0

    def fail_first_append(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated ledger append failure")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(lifecycle_runtime, "append_ledger_entry", fail_first_append)
    with pytest.raises(RuntimeError, match="simulated ledger append failure"):
        prepare_evidence_checkpoint(package, run_dir)

    monkeypatch.setattr(lifecycle_runtime, "append_ledger_entry", original_append)
    prepared = prepare_evidence_checkpoint(package, run_dir)
    entries = [
        json.loads(line) for line in (run_dir / "lifecycle_ledger.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert prepared["checkpoint_id"] == "initial_review"
    assert any(
        entry["stage"] == "lifecycle_transition" and entry["summary"]["transition_id"] == "transition-001"
        for entry in entries
    )


def test_branch_failure_leaves_destination_available_for_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    original_copy = lifecycle_runtime._copy_file_atomic
    calls = 0

    def fail_second_copy(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated branch copy failure")
        original_copy(source, destination)

    monkeypatch.setattr(lifecycle_runtime, "_copy_file_atomic", fail_second_copy)
    with pytest.raises(RuntimeError, match="simulated branch copy failure"):
        branch_evidence_lifecycle(
            package,
            parent_run,
            branch_run,
            checkpoint_id="response_review",
            branch_id="branch.retryable",
            reason="Exercise atomic branch creation.",
        )
    assert not branch_run.exists()

    monkeypatch.setattr(lifecycle_runtime, "_copy_file_atomic", original_copy)
    branch = branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="response_review",
        branch_id="branch.retryable",
        reason="Exercise atomic branch creation.",
    )

    assert branch["active_checkpoint_id"] == "response_review"


def test_unknown_state_schema_version_is_rejected_without_rewrite(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    state_path = run_dir / "state.json"
    state = _load_json(state_path)
    state["schema_version"] = "99"
    _write_json(state_path, state)
    before = state_path.read_bytes()

    with pytest.raises(EvidenceLifecycleError, match="unsupported lifecycle state schema version: 99"):
        read_evidence_lifecycle_state(package, run_dir)

    assert state_path.read_bytes() == before


def test_invalid_persisted_state_is_reported_through_runtime_error_contract(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    state_path = run_dir / "state.json"
    state = _load_json(state_path)
    state["status"] = "complete"
    _write_json(state_path, state)

    with pytest.raises(EvidenceLifecycleError, match="invalid lifecycle state"):
        read_evidence_lifecycle_state(package, run_dir)


def test_status_does_not_initialize_a_missing_run(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "missing-run"

    with pytest.raises(EvidenceLifecycleError, match="lifecycle state not found"):
        read_evidence_lifecycle_state(package, run_dir)

    assert not run_dir.exists()


def test_full_runner_uses_fresh_episode_calls_with_one_persistent_workspace(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    observations: list[dict] = []

    def resolve(context: dict) -> dict:
        workspace = Path(context["workspace"])
        visible = sorted(path.name for path in (workspace / "inbox").iterdir())
        observations.append(
            {
                "checkpoint_id": context["checkpoint_id"],
                "workspace": workspace,
                "visible": visible,
                "prior_submission_visible": (workspace / "submissions" / "initial_review.json").exists(),
            }
        )
        _write_json(Path(context["submission_path"]), {"checkpoint_id": context["checkpoint_id"]})
        return {"episode_id": f"episode.{context['checkpoint_id']}"}

    result = run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)

    assert result["status"] == "complete"
    assert [item["checkpoint_id"] for item in observations] == ["initial_review", "response_review"]
    assert len({item["workspace"] for item in observations}) == 1
    assert observations[0]["visible"] == ["initial_review"]
    assert observations[0]["prior_submission_visible"] is False
    assert observations[1]["visible"] == ["initial_review", "response_review"]
    assert observations[1]["prior_submission_visible"] is True


def test_parent_task_run_resolver_preserves_existing_meta_harness_boundary(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), {"checkpoint_id": context["checkpoint_id"]})
        return {"status": "completed"}

    resolver = build_evidence_lifecycle_task_run_resolver(
        package_dir=package,
        run_dir=run_dir,
        episode_resolver=resolve,
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 0.75,
            "overall": "fail",
            "passed": False,
            "gates": {"continuity": {"passed": False, "score": 0.75, "failures": ["demo"]}},
        },
    )
    task_run = resolver({"process_id": "process.demo"})

    assert task_run["run_id"] == "process.demo.lifecycle.demo"
    assert task_run["evidence"]["score"] == {"reward": 0.75, "passed": False}
    assert task_run["evidence"]["gates"]["continuity"]["passed"] is False
    assert task_run["evidence"]["lifecycle"]["status"] == "complete"


def test_local_episode_resolver_builds_fresh_adapters_in_one_workspace(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _WritingRegistry()
    resolver = build_local_evidence_lifecycle_episode_resolver(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=registry,
    )

    result = run_evidence_lifecycle(package, run_dir, episode_resolver=resolver)

    assert result["status"] == "complete"
    assert registry.build_count == 2
    assert len(set(registry.workspaces)) == 1
    assert (run_dir / "episodes" / "initial_review" / "agent_result.json").exists()
    assert (run_dir / "episodes" / "response_review" / "agent_result.json").exists()
    assert (run_dir / "episodes" / "initial_review" / "conversation.jsonl").exists()
    state = _load_json(run_dir / "state.json")
    assert [[attempt["status"] for attempt in checkpoint["attempts"]] for checkpoint in state["checkpoint_runs"]] == [
        ["submitted"],
        ["submitted"],
    ]
    assert {
        attempt["execution_mode"] for checkpoint in state["checkpoint_runs"] for attempt in checkpoint["attempts"]
    } == {"fresh_context"}


def test_local_episode_resolver_marks_provider_failure_immediately(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    resolver = build_local_evidence_lifecycle_episode_resolver(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_CrashingRegistry(),
    )

    with pytest.raises(RuntimeError, match="simulated crash"):
        run_evidence_lifecycle(package, run_dir, episode_resolver=resolver)

    state = _load_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "adapter_exception"
    assert (run_dir / "episodes" / "initial_review" / "agent_result.json").exists()


def test_local_runners_return_the_same_normalized_evidence_schema(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    verification = {
        "lifecycle_id": "lifecycle.demo",
        "reward": 1.0,
        "overall": "pass",
        "passed": True,
        "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
    }
    fresh = run_local_evidence_lifecycle_fresh_context(
        package_dir=package,
        run_dir=tmp_path / "fresh-run",
        model="test-model",
        registry=_WritingRegistry(),
        verifier=lambda _package, _run: verification,
        process_id="process.demo",
    )
    persistent = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=tmp_path / "persistent-run",
        model="test-model",
        registry=_LifecycleSessionRegistry(package=package, run_dir=tmp_path / "persistent-run"),
        verifier=lambda _package, _run: verification,
        process_id="process.demo",
    )

    assert set(fresh["evidence"]) == set(persistent["evidence"])
    assert set(fresh["evidence"]["agent"]) == set(persistent["evidence"]["agent"])
    assert set(fresh["evidence"]["artifacts"]) == set(persistent["evidence"]["artifacts"])
    assert fresh["evidence"]["agent"]["execution_mode"] == "fresh_context"
    assert fresh["evidence"]["agent"]["memory_visibility_policy"] == "artifact_memory"
    assert len(fresh["evidence"]["agent"]["sessions"]) == 2
    assert persistent["evidence"]["agent"]["execution_mode"] == "persistent_context"
    assert persistent["evidence"]["agent"]["memory_visibility_policy"] == "persistent_context"
    assert len(persistent["evidence"]["agent"]["sessions"]) == 1
    assert fresh["evidence"]["agent"]["totals"] == {
        "input_tokens": 20,
        "output_tokens": 4,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
        "failures": 0,
    }


@pytest.mark.parametrize("mode", ["persistent_context", "fresh_context"])
def test_local_runners_close_returned_provider_failures(tmp_path: Path, mode: str) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    kwargs = {
        "package_dir": package,
        "run_dir": run_dir,
        "model": "test-model",
        "registry": _FailedRegistry(),
        "verifier": lambda _package, _run: {},
    }

    if mode == "persistent_context":
        task_run = run_local_evidence_lifecycle_session(**kwargs)
    else:
        task_run = run_local_evidence_lifecycle_fresh_context(**kwargs)

    state = _load_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "provider_error"
    assert task_run["evidence"]["agent"]["status"] == "failed"
    assert task_run["evidence"]["agent"]["totals"]["failures"] == 1


def test_local_run_records_complete_experiment_provenance_and_normalized_metrics(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    task_run = run_local_evidence_lifecycle_fresh_context(
        package_dir=package,
        run_dir=run_dir,
        model="claude-haiku-test-revision",
        registry=_TracingRegistry(),
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 1.0,
            "overall": "pass",
            "passed": True,
            "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
        },
    )

    manifest = _load_json(run_dir / "experiment-manifest.json")
    metrics = _load_json(run_dir / "metrics.json")
    verification = _load_json(run_dir / "verification.json")
    index_entries = [
        json.loads(line) for line in (tmp_path / "experiment-index.jsonl").read_text(encoding="utf-8").splitlines()
    ]

    assert manifest["schema_version"] == "1"
    assert manifest["repository"]["commit"]
    assert manifest["repository"]["dirty_digest"]
    assert manifest["lifecycle"]["package_files"]["lifecycle.json"]
    assert manifest["lifecycle"]["spec_sha256"]
    assert manifest["model"]["requested_model"] == "claude-haiku-test-revision"
    assert manifest["model"]["resolved_models"] == ["claude-haiku-resolved-test"]
    assert manifest["execution"]["mode"] == "fresh_context"
    assert manifest["execution"]["memory_visibility_policy"] == "artifact_memory"
    assert manifest["interaction"]["system_prompts"][0]["sha256"]
    assert manifest["interaction"]["user_prompts"][0]["sha256"]
    assert {tool["name"] for tool in manifest["interaction"]["tool_schema"]} == {
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
    }
    assert manifest["outputs"]["verification.json"]
    assert manifest["outputs"]["metrics.json"]
    assert metrics["requests"] == 2
    assert metrics["tool_calls"] == 2
    assert metrics["reads"] == 2
    assert metrics["checkpoint_count"] == 2
    assert metrics["input_tokens"] == 20
    assert metrics["estimated_cost_usd"] is not None
    assert verification["reward"] == 1.0
    assert len(index_entries) == 1
    assert index_entries[0]["experiment_id"] == manifest["experiment_id"]
    assert index_entries[0]["manifest_sha256"] == task_run["evidence"]["experiment"]["manifest_sha256"]


def test_operational_metrics_preserve_nullable_legacy_fields_without_semantic_diagnostics(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    run_local_evidence_lifecycle_fresh_context(
        package_dir=package,
        run_dir=run_dir,
        model="unpriced-test-model",
        registry=_WritingRegistry(),
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 1.0,
            "overall": "pass",
            "passed": True,
            "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
        },
    )

    metrics = _load_json(run_dir / "metrics.json")

    assert "semantic_transition" not in metrics
    assert "estimated_cost_usd" in metrics
    assert metrics["estimated_cost_usd"] is None
    assert "whole_run_seconds" in metrics


def test_lifecycle_control_tool_submits_and_releases_next_checkpoint(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    initial = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(initial["submission_path"]), {"checkpoint_id": "initial_review"})
    tool = EvidenceLifecycleControlTool(package_dir=package, run_dir=run_dir)

    response = json.loads(tool.submit_checkpoint("initial_review"))

    assert response["status"] == "awaiting_checkpoint_submission"
    assert response["checkpoint_id"] == "response_review"
    assert "Complete the response review." in response["instruction"]
    assert (run_dir / "workspace" / "inbox" / "response_review" / "response.txt").exists()
    assert (run_dir / "episodes" / "initial_review" / "submission.json").exists()


def test_lifecycle_control_tool_rejects_wrong_checkpoint_without_advancing(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    initial = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(initial["submission_path"]), {"checkpoint_id": "initial_review"})
    tool = EvidenceLifecycleControlTool(package_dir=package, run_dir=run_dir)

    response = json.loads(tool.submit_checkpoint("response_review"))

    assert response["status"] == "rejected"
    assert "active checkpoint is 'initial_review'" in response["error"]
    assert read_evidence_lifecycle_state(package, run_dir)["active_checkpoint_id"] == "initial_review"
    assert not (run_dir / "workspace" / "inbox" / "response_review").exists()


def test_lifecycle_workspace_tool_confines_reads_and_submission_writes(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    tool = EvidenceLifecycleWorkspaceTool(package_dir=package, run_dir=run_dir)

    listed = json.loads(tool.list_workspace("inbox"))
    read = json.loads(tool.read_workspace_file("inbox/initial_review/initial.txt"))
    escaped = json.loads(tool.read_workspace_file("../state.json"))
    absolute = json.loads(tool.read_workspace_file(str(run_dir / "state.json")))
    written = json.loads(
        tool.write_checkpoint_submission(
            "initial_review",
            json.dumps({"checkpoint_id": "initial_review"}),
        )
    )

    assert listed == {"status": "ok", "path": "inbox", "entries": ["initial_review"]}
    assert read["status"] == "ok"
    assert read["content"] == "initial evidence\n"
    assert escaped["status"] == "rejected"
    assert absolute["status"] == "rejected"
    assert written["status"] == "written"
    assert _load_json(run_dir / "workspace" / "submissions" / "initial_review.json") == {
        "checkpoint_id": "initial_review"
    }


def test_lifecycle_workspace_visibility_policies_control_model_reads_without_deleting_audit_files(
    tmp_path: Path,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    initial = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(initial["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, run_dir)
    prepare_evidence_checkpoint(package, run_dir)

    artifact_memory = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )
    raw_evidence = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
    )
    current_release = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY,
    )

    assert json.loads(artifact_memory.read_workspace_file("submissions/initial_review.json"))["status"] == "ok"
    assert json.loads(raw_evidence.read_workspace_file("submissions/initial_review.json"))["status"] == "rejected"
    assert json.loads(raw_evidence.read_workspace_file("inbox/initial_review/initial.txt"))["status"] == "ok"
    assert json.loads(current_release.read_workspace_file("inbox/initial_review/initial.txt"))["status"] == "rejected"
    assert json.loads(current_release.read_workspace_file("inbox/response_review/response.txt"))["status"] == "ok"
    assert json.loads(current_release.list_workspace("inbox"))["entries"] == ["response_review"]
    assert "submissions" not in json.loads(current_release.list_workspace("."))["entries"]
    assert (run_dir / "workspace" / "submissions" / "initial_review.json").is_file()


def test_execution_modes_reject_incompatible_visibility_policies(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")

    with pytest.raises(ValueError, match="persistent_context visibility"):
        run_local_evidence_lifecycle_session(
            package_dir=package,
            run_dir=tmp_path / "persistent-run",
            model="test-model",
            verifier=lambda _package, _run: {},
            visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        )
    with pytest.raises(ValueError, match="fresh-context visibility"):
        run_local_evidence_lifecycle_fresh_context(
            package_dir=package,
            run_dir=tmp_path / "fresh-run",
            model="test-model",
            verifier=lambda _package, _run: {},
            visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        )
    with pytest.raises(ValueError, match="fresh-context visibility"):
        build_local_evidence_lifecycle_episode_resolver(
            package_dir=package,
            model="test-model",
            visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
        )


def test_lifecycle_control_tool_revisits_prior_checkpoint_without_rewinding(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    initial = prepare_evidence_checkpoint(package, run_dir)
    _write_json(Path(initial["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, run_dir)
    prepare_evidence_checkpoint(package, run_dir)
    tool = EvidenceLifecycleControlTool(package_dir=package, run_dir=run_dir)

    response = json.loads(
        tool.revisit_checkpoint(
            "initial_review",
            "Check whether the original source identity supports the current conclusion.",
        )
    )

    assert response["status"] == "revisited"
    assert response["checkpoint_id"] == "initial_review"
    assert response["submission"]["checkpoint_id"] == "initial_review"
    assert read_evidence_lifecycle_state(package, run_dir)["active_checkpoint_id"] == "response_review"


def test_local_session_builds_one_adapter_for_all_checkpoints(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _LifecycleSessionRegistry(package=package, run_dir=run_dir)

    task_run = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=run_dir,
        model="test-model",
        registry=registry,
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 0.75,
            "overall": "fail",
            "passed": False,
            "gates": {"continuity": {"passed": False, "score": 0.75, "failures": ["demo"]}},
        },
        process_id="process.demo",
    )

    assert registry.build_count == 1
    assert registry.execute_count == 1
    assert registry.tool_names == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    assert registry.enable_bash is False
    assert registry.request_tool_names == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    assert task_run["run_id"] == "process.demo.lifecycle.demo"
    assert task_run["evidence"]["lifecycle"]["status"] == "complete"
    assert task_run["evidence"]["score"] == {"reward": 0.75, "passed": False}
    assert (run_dir / "sessions" / "session-001" / "agent_result.json").exists()
    assert (run_dir / "sessions" / "session-001" / "conversation.jsonl").exists()


def test_local_session_continues_branch_with_editable_active_draft(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="response_review",
        branch_id="branch.response-recheck",
        reason="Reconsider the response review.",
    )
    registry = _LifecycleSessionRegistry(package=package, run_dir=branch_run)

    task_run = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=branch_run,
        model="test-model",
        registry=registry,
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 1.0,
            "overall": "pass",
            "passed": True,
            "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
        },
    )

    lifecycle = task_run["evidence"]["lifecycle"]
    assert lifecycle["status"] == "complete"
    assert lifecycle["branch"]["branch_id"] == "branch.response-recheck"
    assert lifecycle["checkpoint_runs"][0]["inherited_from_parent"] is True
    assert "active checkpoint submission path is editable" in registry.system_prompt
    assert "branch_origin/" in registry.system_prompt


def test_local_session_preserves_agent_artifacts_before_verifier_failure(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _LifecycleSessionRegistry(package=package, run_dir=run_dir)

    with pytest.raises(RuntimeError, match="verifier failed"):
        run_local_evidence_lifecycle_session(
            package_dir=package,
            run_dir=run_dir,
            model="test-model",
            registry=registry,
            verifier=lambda _package, _run: (_ for _ in ()).throw(RuntimeError("verifier failed")),
        )

    assert (run_dir / "sessions" / "session-001" / "agent_result.json").exists()
    assert (run_dir / "sessions" / "session-001" / "conversation.jsonl").exists()
    assert (run_dir / "sessions" / "session-001" / "raw_output.md").read_text(encoding="utf-8") == "Lifecycle complete."
    verification = _load_json(run_dir / "verification.json")
    manifest = _load_json(run_dir / "experiment-manifest.json")
    assert verification["overall"] == "incomplete"
    assert verification["gates"]["lifecycle_verifier"]["failures"] == [
        "verifier_exception:RuntimeError:verifier failed"
    ]
    assert manifest["outputs"]["verification.json"]


def test_persistent_session_resumes_active_checkpoint_without_overwriting_failed_trajectory(
    tmp_path: Path,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError, match="simulated crash"):
        run_local_evidence_lifecycle_session(
            package_dir=package,
            run_dir=run_dir,
            model="test-model",
            registry=_CrashingRegistry(),
            verifier=lambda _package, _run: {},
        )

    resumed = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=run_dir,
        model="test-model",
        registry=_LifecycleSessionRegistry(package=package, run_dir=run_dir),
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 1.0,
            "overall": "pass",
            "passed": True,
            "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
        },
    )
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))
    attempts = state["checkpoint_runs"][0]["attempts"]

    assert resumed["evidence"]["lifecycle"]["status"] == "complete"
    assert [attempt["status"] for attempt in attempts] == ["failed", "submitted"]
    assert attempts[0]["failure_kind"] == "adapter_exception"
    assert attempts[1]["resumed_from_attempt_id"] == attempts[0]["attempt_id"]
    assert (run_dir / "sessions" / "session-001" / "trajectory.jsonl").exists()
    assert (run_dir / "sessions" / "session-002" / "trajectory.jsonl").exists()
    index_entries = [
        json.loads(line) for line in (tmp_path / "experiment-index.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(index_entries) == 2
    assert len({entry["manifest_path"] for entry in index_entries}) == 2
    for entry in index_entries:
        manifest_path = Path(entry["manifest_path"])
        assert manifest_path.is_file()
        assert lifecycle_runtime._sha256(manifest_path) == entry["manifest_sha256"]


def test_fresh_context_exception_records_experiment_before_propagating(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    with pytest.raises(RuntimeError, match="simulated crash"):
        run_local_evidence_lifecycle_fresh_context(
            package_dir=package,
            run_dir=run_dir,
            model="test-model",
            registry=_CrashingRegistry(),
            verifier=lambda _package, _run: {},
        )

    manifest = _load_json(run_dir / "experiment-manifest.json")
    metrics = _load_json(run_dir / "metrics.json")
    assert manifest["execution"]["status"] == "failed"
    assert metrics["failures"] == 1

    resumed = run_local_evidence_lifecycle_fresh_context(
        package_dir=package,
        run_dir=run_dir,
        model="test-model",
        registry=_WritingRegistry(),
        verifier=lambda _package, _run: {
            "lifecycle_id": "lifecycle.demo",
            "reward": 1.0,
            "overall": "pass",
            "passed": True,
            "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
        },
    )
    state = _load_json(run_dir / "state.json")
    initial_attempts = state["checkpoint_runs"][0]["attempts"]
    assert resumed["evidence"]["lifecycle"]["status"] == "complete"
    assert [attempt["status"] for attempt in initial_attempts] == ["failed", "submitted"]
    assert initial_attempts[1]["resumed_from_attempt_id"] == initial_attempts[0]["attempt_id"]
    assert len((tmp_path / "experiment-index.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def _checkpoint(checkpoint_id: str) -> EvidenceCheckpointSpec:
    return EvidenceCheckpointSpec(
        checkpoint_id=checkpoint_id,
        title=checkpoint_id.replace("_", " ").title(),
        release_path=f"releases/{checkpoint_id}",
        instruction_path=f"instructions/{checkpoint_id}.md",
        submission_path=f"submissions/{checkpoint_id}.json",
    )


def _write_package(package: Path) -> Path:
    spec = EvidenceLifecycleSpec(
        lifecycle_id="lifecycle.demo",
        world_id="world.demo",
        checkpoints=[_checkpoint("initial_review"), _checkpoint("response_review")],
    )
    _write_json(package / "lifecycle.json", spec.model_dump(mode="json"))
    (package / "instructions").mkdir(parents=True, exist_ok=True)
    (package / "instructions" / "initial_review.md").write_text("Complete the initial review.\n")
    (package / "instructions" / "response_review.md").write_text("Complete the response review.\n")
    (package / "releases" / "initial_review").mkdir(parents=True)
    (package / "releases" / "response_review").mkdir(parents=True)
    (package / "releases" / "initial_review" / "initial.txt").write_text("initial evidence\n")
    (package / "releases" / "response_review" / "response.txt").write_text("response evidence\n")
    return package


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _complete_demo_lifecycle(package: Path, run_dir: Path) -> None:
    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), {"checkpoint_id": context["checkpoint_id"]})
        return {"status": "completed"}

    run_evidence_lifecycle(package, run_dir, episode_resolver=resolve)


class _WritingRegistry:
    def __init__(self) -> None:
        self.build_count = 0
        self.workspaces: list[str] = []

    def build(self, *, workspace: str, **_kwargs):
        self.build_count += 1
        self.workspaces.append(workspace)
        return _WritingAdapter()


class _WritingAdapter:
    def execute(self, request):
        output_path = Path(request.output_path)
        checkpoint_id = output_path.stem
        _write_json(output_path, {"checkpoint_id": checkpoint_id})
        return SimpleNamespace(
            agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
            transcript=[],
            raw_output_text=None,
            provider_error=None,
            failure_kind=None,
            usage_input_tokens=10,
            usage_output_tokens=2,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
        )


class _LifecycleSessionRegistry:
    def __init__(self, *, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir
        self.build_count = 0
        self.execute_count = 0
        self.tool_names: list[str] = []
        self.system_prompt = ""
        self.enable_bash: bool | None = None
        self.request_tool_names: list[str] = []

    def build(self, *, native_tools, enable_bash=True, **_kwargs):
        self.build_count += 1
        self.tool_names = [tool.__name__ for tool in native_tools]
        self.enable_bash = enable_bash
        submit_checkpoint = next(tool for tool in native_tools if tool.__name__ == "submit_checkpoint")
        registry = self

        class _SessionAdapter:
            def execute(self, request):
                registry.execute_count += 1
                registry.system_prompt = request.system_prompt
                registry.request_tool_names = [tool.name for tool in request.tools]
                while True:
                    state = read_evidence_lifecycle_state(registry.package, registry.run_dir)
                    checkpoint_id = state["active_checkpoint_id"]
                    if checkpoint_id is None:
                        break
                    _write_json(
                        registry.run_dir / "workspace" / "submissions" / f"{checkpoint_id}.json",
                        {"checkpoint_id": checkpoint_id},
                    )
                    response = json.loads(submit_checkpoint(checkpoint_id))
                    if response["status"] == "complete":
                        break
                return SimpleNamespace(
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text="Lifecycle complete.",
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=30,
                    usage_output_tokens=6,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _SessionAdapter()


class _CrashingRegistry:
    def build(self, **_kwargs):
        class _CrashingAdapter:
            def execute(self, _request):
                raise RuntimeError("simulated crash")

        return _CrashingAdapter()


class _FailedRegistry:
    def build(self, **_kwargs):
        class _FailedAdapter:
            def execute(self, request):
                return SimpleNamespace(
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="failed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error="provider unavailable",
                    failure_kind=SimpleNamespace(value="provider_error"),
                    usage_input_tokens=3,
                    usage_output_tokens=0,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _FailedAdapter()


class _TracingRegistry:
    def build(self, *, trajectory_writer, **_kwargs):
        class _TracingAdapter:
            def execute(self, request):
                trajectory_writer.system(request.system_prompt or "")
                trajectory_writer.user(request.instruction)
                trajectory_writer.new_step()
                trajectory_writer.tool_call(
                    "read_workspace_file",
                    "read_workspace_file",
                    {"path": "instruction.md"},
                )
                output_path = Path(request.output_path)
                _write_json(output_path, {"checkpoint_id": output_path.stem})
                return SimpleNamespace(
                    adapter_name="test-tool-loop",
                    resolved_model="claude-haiku-resolved-test",
                    configuration_record={"model": "claude-haiku-resolved-test", "temperature": 0.0},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=10,
                    usage_output_tokens=2,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _TracingAdapter()
