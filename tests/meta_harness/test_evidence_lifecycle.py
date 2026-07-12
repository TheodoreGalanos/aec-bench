# ABOUTME: Tests staged evidence release and checkpoint persistence in the meta-harness.
# ABOUTME: Covers disclosure, submission gates, tamper detection, resume, and parent task-run evidence.

from __future__ import annotations

import hashlib
import json
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from typing import Any, Never

import pytest
from pydantic import ValidationError

import aec_bench.meta_harness.evidence_lifecycle as lifecycle_runtime
import aec_bench.meta_harness.evidence_lifecycle_local as lifecycle_local_runtime
import aec_bench.meta_harness.evidence_request_protocol as evidence_request_protocol_runtime
import aec_bench.meta_harness.evidence_request_store as evidence_request_store_runtime
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
from aec_bench.meta_harness.evidence_lifecycle_episode import (
    LifecycleEpisodeContext,
    LifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleExecutionMode,
)
from aec_bench.meta_harness.evidence_lifecycle_local import (
    EvidenceLifecycleControlTool,
    EvidenceLifecycleWorkspaceTool,
    LifecycleVisibilityPolicy,
    build_local_evidence_lifecycle_episode_environment,
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


def test_lifecycle_contract_rejects_exact_shape_without_checkpoint_id() -> None:
    payload = _checkpoint("initial_review").model_dump(mode="json")
    payload["required_submission_fields"] = ["review_matrix"]
    payload["allow_additional_submission_fields"] = False

    with pytest.raises(ValidationError, match="exact submission fields must include checkpoint_id"):
        EvidenceCheckpointSpec.model_validate(payload)


def test_lifecycle_spec_identity_preserves_legacy_default_field_omission(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    contract_path = package / "lifecycle.json"
    legacy_contract = _load_json(contract_path)
    for checkpoint in legacy_contract["checkpoints"]:
        checkpoint.pop("allow_additional_submission_fields")
    _write_json(contract_path, legacy_contract)

    expected_payload = EvidenceLifecycleSpec.model_validate(legacy_contract).model_dump(
        mode="json",
        exclude_none=True,
    )
    for checkpoint in expected_payload["checkpoints"]:
        checkpoint.pop("allow_additional_submission_fields")
    expected_sha256 = hashlib.sha256(
        json.dumps(expected_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    run_dir = tmp_path / "run"
    identity = lifecycle_runtime.evidence_lifecycle_package_identity(package)
    prepare_evidence_checkpoint(package, run_dir)
    state_path = run_dir / "state.json"
    historical_state = _load_json(state_path)
    historical_state["lifecycle_spec_sha256"] = expected_sha256
    _write_json(state_path, historical_state)
    state = read_evidence_lifecycle_state(package, run_dir)

    assert identity["spec_sha256"] == expected_sha256
    assert state["lifecycle_spec_sha256"] == expected_sha256


def test_conditional_evidence_contract_rejects_ambiguous_request_graphs() -> None:
    payload = _checkpoint("initial_review").model_dump(mode="json")
    payload["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "survey_revision",
                "title": "Survey revision",
                "description": "Obtain the revised survey.",
                "prerequisite_request_ids": ["outlet_inspection"],
            },
            {
                "request_id": "outlet_inspection",
                "title": "Outlet inspection",
                "description": "Obtain the outlet inspection.",
                "prerequisite_request_ids": ["survey_revision"],
            },
        ],
    }

    with pytest.raises(ValidationError, match="must not contain cycles"):
        EvidenceCheckpointSpec.model_validate(payload)

    payload["conditional_evidence"]["requests"][1]["request_id"] = "survey_revision"
    payload["conditional_evidence"]["requests"][1]["prerequisite_request_ids"] = []
    with pytest.raises(ValidationError, match="ids must be unique"):
        EvidenceCheckpointSpec.model_validate(payload)


@pytest.mark.parametrize(
    ("request_budget", "requests", "unreachable_request_id"),
    [
        (
            1,
            [
                {
                    "request_id": "survey_revision",
                    "title": "Survey revision",
                    "description": "Obtain the revised survey.",
                },
                {
                    "request_id": "outlet_inspection",
                    "title": "Outlet inspection",
                    "description": "Obtain the outlet inspection.",
                    "prerequisite_request_ids": ["survey_revision"],
                },
            ],
            "outlet_inspection",
        ),
        (
            2,
            [
                {
                    "request_id": "survey_revision",
                    "title": "Survey revision",
                    "description": "Obtain the revised survey.",
                },
                {
                    "request_id": "outlet_inspection",
                    "title": "Outlet inspection",
                    "description": "Obtain the outlet inspection.",
                    "prerequisite_request_ids": ["survey_revision"],
                },
                {
                    "request_id": "model_reconciliation",
                    "title": "Model reconciliation",
                    "description": "Obtain the reconciled model record.",
                    "prerequisite_request_ids": ["outlet_inspection"],
                },
            ],
            "model_reconciliation",
        ),
    ],
)
def test_conditional_evidence_contract_rejects_requests_unreachable_within_budget(
    request_budget: int,
    requests: list[dict[str, Any]],
    unreachable_request_id: str,
) -> None:
    payload = _checkpoint("initial_review").model_dump(mode="json")
    payload["conditional_evidence"] = {
        "request_budget": request_budget,
        "requests": requests,
    }

    with pytest.raises(
        ValidationError,
        match=f"budget cannot satisfy prerequisites for {unreachable_request_id}",
    ):
        EvidenceCheckpointSpec.model_validate(payload)


def test_conditional_evidence_contract_accepts_every_request_reachable_within_budget() -> None:
    payload = _checkpoint("initial_review").model_dump(mode="json")
    payload["conditional_evidence"] = {
        "request_budget": 2,
        "requests": [
            {
                "request_id": "survey_revision",
                "title": "Survey revision",
                "description": "Obtain the revised survey.",
            },
            {
                "request_id": "outlet_inspection",
                "title": "Outlet inspection",
                "description": "Obtain the outlet inspection.",
                "prerequisite_request_ids": ["survey_revision"],
            },
            {
                "request_id": "model_reconciliation",
                "title": "Model reconciliation",
                "description": "Obtain the reconciled model record.",
            },
        ],
    }

    checkpoint = EvidenceCheckpointSpec.model_validate(payload)

    assert checkpoint.conditional_evidence is not None
    assert checkpoint.conditional_evidence.request_budget == 2


def test_public_conditional_evidence_contract_rejects_hidden_resolution_paths() -> None:
    payload = _checkpoint("initial_review").model_dump(mode="json")
    payload["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "survey_revision",
                "title": "Survey revision",
                "description": "Obtain the revised survey.",
                "source_path": "hidden/evidence_requests/initial_review/survey_revision",
            }
        ],
    }

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        EvidenceCheckpointSpec.model_validate(payload)


def test_conditional_release_reserves_requests_workspace_namespace(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    reserved = package / "releases/initial_review/requests/preexisting.txt"
    reserved.parent.mkdir()
    reserved.write_text("collision\n", encoding="utf-8")

    with pytest.raises(EvidenceLifecycleError, match="reserved requests namespace"):
        prepare_evidence_checkpoint(package, tmp_path / "run")


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


def test_request_evidence_releases_only_selected_request_and_records_budget(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")

    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    catalog_path = run_dir / "workspace/checkpoints/initial_review/evidence-requests.json"
    initial_catalog = _load_json(catalog_path)
    assert prepared["evidence_request_catalog"] == initial_catalog
    assert initial_catalog["remaining_budget"] == 1
    assert [request["status"] for request in initial_catalog["requests"]] == [
        "available",
        "available",
    ]
    assert "source_path" not in json.dumps(initial_catalog)
    assert "hidden" not in json.dumps(initial_catalog)
    attempt = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="fresh_context",
    )

    result = lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )

    assert result["outcome"] == "released"
    assert result["attempt_id"] == attempt["attempt_id"]
    assert result["session_id"] == "session-001"
    assert result["budget_before"] == 1
    assert result["budget_consumed"] == 1
    assert result["budget_after"] == 0
    assert len(result["pre_action_state_sha256"]) == 64
    assert len(result["post_action_state_sha256"]) == 64
    assert result["released_artifacts"][0]["sha256"]
    requested = run_dir / "workspace/inbox/initial_review/requests"
    assert (requested / "survey_revision" / "survey-rev-b.txt").read_text(encoding="utf-8") == "revision B\n"
    assert not (requested / "outlet_inspection").exists()

    state = _load_json(run_dir / "state.json")
    checkpoint = state["checkpoint_runs"][0]
    assert checkpoint["evidence_request_budget"] == 1
    assert checkpoint["evidence_request_budget_remaining"] == 0
    assert checkpoint["evidence_request_actions"] == [result]
    updated_catalog = _load_json(catalog_path)
    assert updated_catalog["remaining_budget"] == 0
    assert [request["status"] for request in updated_catalog["requests"]] == [
        "released",
        "budget_exhausted",
    ]


def test_evidence_request_catalog_preserves_unmet_prerequisite_status_after_budget_exhaustion(
    tmp_path: Path,
) -> None:
    package = _write_prerequisite_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    for request_id in ("alternative_c", "alternative_d"):
        lifecycle_runtime.request_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            request_id=request_id,
            reason=f"Inspect {request_id}.",
            session_id="session-001",
        )

    catalog = _load_json(run_dir / "workspace/checkpoints/initial_review/evidence-requests.json")
    outlet_status = next(
        request["status"] for request in catalog["requests"] if request["request_id"] == "outlet_inspection"
    )
    rejected = lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="outlet_inspection",
        reason="Inspect the outlet evidence.",
        session_id="session-001",
    )

    assert outlet_status == "prerequisites_incomplete"
    assert rejected["rejection"] == "prerequisites_incomplete"
    assert rejected["budget_after"] == 0


def test_repeated_evidence_request_is_idempotent_and_consumes_no_budget(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    first = lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )

    repeated = lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Recover the result after a lost response.",
        session_id="session-001",
    )

    assert repeated["outcome"] == "already_released"
    assert repeated["budget_before"] == 0
    assert repeated["budget_consumed"] == 0
    assert repeated["budget_after"] == 0
    assert repeated["released_artifacts"] == first["released_artifacts"]
    assert repeated["pre_action_state_sha256"] == repeated["post_action_state_sha256"]
    checkpoint = _load_json(run_dir / "state.json")["checkpoint_runs"][0]
    assert [action["outcome"] for action in checkpoint["evidence_request_actions"]] == [
        "released",
        "already_released",
    ]


def test_invalid_evidence_requests_are_recorded_without_leaking_alternatives(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )

    rejected = lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="invented_request",
        reason="Try an undeclared source.",
        session_id="session-001",
    )

    assert rejected["outcome"] == "rejected"
    assert rejected["rejection"] == "unknown_request"
    assert rejected["budget_before"] == 1
    assert rejected["budget_consumed"] == 0
    assert rejected["budget_after"] == 1
    assert rejected["released_artifacts"] == []
    assert "survey_revision" not in json.dumps(rejected)
    assert "outlet_inspection" not in json.dumps(rejected)
    assert not (run_dir / "workspace/inbox/initial_review/requests").exists()


def test_evidence_request_recovers_once_after_release_before_state_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    original_write_state = evidence_request_store_runtime._write_state
    failed = False

    def fail_action_state_commit(
        target_run: Path,
        state: EvidenceLifecycleRunState,
    ) -> None:
        nonlocal failed
        has_action = any(checkpoint.evidence_request_actions for checkpoint in state.checkpoint_runs)
        if has_action and not failed:
            failed = True
            raise RuntimeError("simulated action state commit failure")
        original_write_state(target_run, state)

    monkeypatch.setattr(evidence_request_store_runtime, "_write_state", fail_action_state_commit)
    with pytest.raises(RuntimeError, match="simulated action state commit failure"):
        lifecycle_runtime.request_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            request_id="survey_revision",
            reason="Resolve the source revision discrepancy.",
            session_id="session-001",
        )

    monkeypatch.setattr(evidence_request_store_runtime, "_write_state", original_write_state)
    recovered = read_evidence_lifecycle_state(package, run_dir)
    checkpoint = recovered["checkpoint_runs"][0]

    assert checkpoint["evidence_request_budget_remaining"] == 0
    assert [action["outcome"] for action in checkpoint["evidence_request_actions"]] == ["released"]
    assert (run_dir / "workspace/inbox/initial_review/requests/survey_revision/survey-rev-b.txt").read_text(
        encoding="utf-8"
    ) == "revision B\n"
    action_dir = run_dir / "evidence_requests/evidence-request-000001"
    assert (action_dir / "action.json").is_file()
    assert (action_dir / "committed.json").is_file()


def test_evidence_request_recovery_does_not_publish_pending_checkpoint_catalog(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_all_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    pending_catalog = run_dir / "workspace/checkpoints/response_review/evidence-requests.json"
    assert not pending_catalog.exists()
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    original_write_state = evidence_request_store_runtime._write_state
    failed = False

    def fail_action_state_commit(
        target_run: Path,
        state: EvidenceLifecycleRunState,
    ) -> None:
        nonlocal failed
        has_action = any(checkpoint.evidence_request_actions for checkpoint in state.checkpoint_runs)
        if has_action and not failed:
            failed = True
            raise RuntimeError("simulated action state commit failure")
        original_write_state(target_run, state)

    monkeypatch.setattr(evidence_request_store_runtime, "_write_state", fail_action_state_commit)
    with pytest.raises(RuntimeError, match="simulated action state commit failure"):
        lifecycle_runtime.request_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            request_id="survey_revision",
            reason="Resolve the source revision discrepancy.",
            session_id="session-001",
        )

    monkeypatch.setattr(evidence_request_store_runtime, "_write_state", original_write_state)
    recovered = read_evidence_lifecycle_state(package, run_dir)

    assert recovered["checkpoint_runs"][0]["evidence_request_budget_remaining"] == 0
    assert not pending_catalog.exists()


def test_evidence_request_repairs_action_ledger_after_state_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    original_append = evidence_request_store_runtime.append_ledger_entry

    def fail_action_ledger(*args: Any, **kwargs: Any) -> None:
        if kwargs.get("stage") == "evidence_request":
            raise RuntimeError("simulated action ledger failure")
        original_append(*args, **kwargs)

    monkeypatch.setattr(evidence_request_store_runtime, "append_ledger_entry", fail_action_ledger)
    with pytest.raises(RuntimeError, match="simulated action ledger failure"):
        lifecycle_runtime.request_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            request_id="survey_revision",
            reason="Resolve the source revision discrepancy.",
            session_id="session-001",
        )

    monkeypatch.setattr(evidence_request_store_runtime, "append_ledger_entry", original_append)
    recovered = read_evidence_lifecycle_state(package, run_dir)
    action_entries = [
        json.loads(line)
        for line in (run_dir / "lifecycle_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if json.loads(line)["stage"] == "evidence_request"
    ]

    assert len(recovered["checkpoint_runs"][0]["evidence_request_actions"]) == 1
    assert len(action_entries) == 1
    assert action_entries[0]["summary"]["action_id"] == "evidence-request-000001"
    assert (run_dir / "evidence_requests/evidence-request-000001/committed.json").is_file()


def test_evidence_request_recovers_torn_atomic_commit_marker_publish(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    original_write_atomic = evidence_request_store_runtime._write_json_atomic_durable
    interrupted = False

    def interrupt_commit_marker(path: Path, payload: dict[str, Any]) -> None:
        nonlocal interrupted
        if path.name == "committed.json" and not interrupted:
            interrupted = True
            path.with_suffix(".json.tmp").write_text("{", encoding="utf-8")
            raise RuntimeError("simulated commit marker publication death")
        original_write_atomic(path, payload)

    monkeypatch.setattr(
        evidence_request_store_runtime,
        "_write_json_atomic_durable",
        interrupt_commit_marker,
    )
    with pytest.raises(RuntimeError, match="simulated commit marker publication death"):
        lifecycle_runtime.request_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            request_id="survey_revision",
            reason="Resolve the source revision discrepancy.",
            session_id="session-001",
        )

    monkeypatch.setattr(
        evidence_request_store_runtime,
        "_write_json_atomic_durable",
        original_write_atomic,
    )
    recovered = read_evidence_lifecycle_state(package, run_dir)
    transaction = run_dir / "evidence_requests/evidence-request-000001"

    assert len(recovered["checkpoint_runs"][0]["evidence_request_actions"]) == 1
    assert _load_json(transaction / "committed.json") == {
        "action_id": "evidence-request-000001",
        "status": "committed",
    }
    assert not (transaction / "committed.json.tmp").exists()


def test_concurrent_evidence_requests_preserve_sequence_and_budget(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )

    def request(request_id: str) -> dict[str, Any]:
        return lifecycle_runtime.request_evidence_checkpoint(
            package,
            run_dir,
            checkpoint_id="initial_review",
            request_id=request_id,
            reason=f"Inspect {request_id}.",
            session_id="session-001",
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(request, ["survey_revision", "outlet_inspection"]))

    assert sorted(result["outcome"] for result in results) == ["rejected", "released"]
    rejected = next(result for result in results if result["outcome"] == "rejected")
    assert rejected["rejection"] == "budget_exhausted"
    checkpoint = _load_json(run_dir / "state.json")["checkpoint_runs"][0]
    assert [action["sequence"] for action in checkpoint["evidence_request_actions"]] == [1, 2]
    assert checkpoint["evidence_request_budget_remaining"] == 0
    assert len(list((run_dir / "evidence_requests").glob("evidence-request-*"))) == 2


def test_concurrent_submission_cannot_overwrite_an_evidence_request_transition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    _write_json(Path(prepared["submission_path"]), {"checkpoint_id": "initial_review"})
    submission_ready = Event()
    release_submission = Event()
    request_entered = Event()
    original_write_state = lifecycle_runtime._write_state
    original_record_action = lifecycle_runtime._record_evidence_request_action

    def pause_submission_publish(
        target_run: Path,
        state: EvidenceLifecycleRunState,
    ) -> None:
        initial = state.checkpoint("initial_review")
        if (
            state.active_checkpoint_id is None
            and initial.status == CheckpointRunStatus.SUBMITTED
            and not submission_ready.is_set()
        ):
            submission_ready.set()
            if not release_submission.wait(timeout=5):
                raise AssertionError("submission concurrency barrier timed out")
        original_write_state(target_run, state)

    def note_request_entry(*args: Any, **kwargs: Any) -> dict[str, Any]:
        request_entered.set()
        return original_record_action(*args, **kwargs)

    monkeypatch.setattr(lifecycle_runtime, "_write_state", pause_submission_publish)
    monkeypatch.setattr(lifecycle_runtime, "_record_evidence_request_action", note_request_entry)
    submit_errors: list[Exception] = []
    request_errors: list[Exception] = []

    def submit() -> None:
        try:
            submit_evidence_checkpoint(package, run_dir)
        except Exception as exc:  # pragma: no cover - asserted below
            submit_errors.append(exc)

    def request() -> None:
        try:
            lifecycle_runtime.request_evidence_checkpoint(
                package,
                run_dir,
                checkpoint_id="initial_review",
                request_id="survey_revision",
                reason="Resolve the source revision discrepancy.",
                session_id="session-001",
            )
        except Exception as exc:
            request_errors.append(exc)

    submit_thread = Thread(target=submit)
    submit_thread.start()
    assert submission_ready.wait(timeout=5)
    request_thread = Thread(target=request)
    request_thread.start()
    request_entered.wait(timeout=1)
    release_submission.set()
    submit_thread.join(timeout=5)
    request_thread.join(timeout=5)

    assert not submit_thread.is_alive()
    assert not request_thread.is_alive()
    assert submit_errors == []
    assert len(request_errors) == 1
    assert isinstance(request_errors[0], EvidenceLifecycleError)
    assert "no checkpoint is active" in str(request_errors[0])
    state = read_evidence_lifecycle_state(package, run_dir)
    state_transitions = {transition["transition_id"]: transition for transition in state["transitions"]}
    ledger_transitions = {
        entry["summary"]["transition_id"]: entry["summary"]
        for entry in _load_jsonl(run_dir / "lifecycle_ledger.jsonl")
        if entry["stage"] == "lifecycle_transition"
    }
    assert ledger_transitions == state_transitions


@pytest.mark.parametrize("tamper", ["status", "summary", "artifact_refs"])
def test_evidence_request_ledger_rejects_conflicting_existing_action_entry(
    tmp_path: Path,
    tamper: str,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    ledger_path = run_dir / "lifecycle_ledger.jsonl"
    entries = _load_jsonl(ledger_path)
    action_entry = next(entry for entry in entries if entry["stage"] == "evidence_request")
    if tamper == "status":
        action_entry["status"] = "rejected"
    elif tamper == "summary":
        action_entry["summary"]["reason"] = "Forged reason."
    else:
        action_entry["artifact_refs"] = []
    _write_jsonl(ledger_path, entries)

    with pytest.raises(EvidenceLifecycleError, match="evidence request ledger entry conflicts"):
        read_evidence_lifecycle_state(package, run_dir)


def test_transition_ledger_rejects_conflicting_existing_transition_entry(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    ledger_path = run_dir / "lifecycle_ledger.jsonl"
    entries = _load_jsonl(ledger_path)
    transition_entry = next(entry for entry in entries if entry["stage"] == "lifecycle_transition")
    transition_entry["status"] = "submit"
    _write_jsonl(ledger_path, entries)

    with pytest.raises(EvidenceLifecycleError, match="lifecycle transition ledger entry conflicts"):
        read_evidence_lifecycle_state(package, run_dir)


def test_requested_evidence_rejects_unbound_projection_files(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    unexpected = run_dir / "workspace/inbox/initial_review/requests/survey_revision/unbound.txt"
    unexpected.write_text("unbound evidence\n", encoding="utf-8")

    with pytest.raises(EvidenceLifecycleError, match="artifact file set changed"):
        read_evidence_lifecycle_state(package, run_dir)


def test_lifecycle_state_rejects_cross_checkpoint_action_identity_reordering(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    lifecycle_path = package / "lifecycle.json"
    lifecycle = _load_json(lifecycle_path)
    lifecycle["checkpoints"][1]["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "response_support",
                "title": "Response support",
                "description": "Obtain the response-stage support record.",
            }
        ],
    }
    _write_json(lifecycle_path, lifecycle)
    resolution_path = package / "hidden/evidence-request-resolutions.json"
    resolutions = _load_json(resolution_path)
    resolutions["resolutions"].append(
        {
            "checkpoint_id": "response_review",
            "request_id": "response_support",
            "source_path": "hidden/evidence_requests/response_review/response_support",
        }
    )
    _write_json(resolution_path, resolutions)
    support = package / "hidden/evidence_requests/response_review/response_support/support.txt"
    support.parent.mkdir(parents=True)
    support.write_text("response support\n", encoding="utf-8")

    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    _write_json(Path(prepared["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, run_dir)
    prepared = prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-002",
        execution_mode="persistent_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="response_review",
        request_id="response_support",
        reason="Inspect the response-stage support record.",
        session_id="session-002",
    )

    state = _load_json(run_dir / "state.json")
    first = state["checkpoint_runs"][0]["evidence_request_actions"][0]
    second = state["checkpoint_runs"][1]["evidence_request_actions"][0]
    first["sequence"], second["sequence"] = second["sequence"], first["sequence"]
    first["action_id"], second["action_id"] = second["action_id"], first["action_id"]

    with pytest.raises(ValidationError, match="globally ordered"):
        EvidenceLifecycleRunState.model_validate(state)


def test_lifecycle_state_persists_first_class_checkpoint_records(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"

    prepare_evidence_checkpoint(package, run_dir)
    state = json.loads((run_dir / "state.json").read_text(encoding="utf-8"))

    assert state["schema_version"] == "4"
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
    assert persisted["schema_version"] == "4"
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

    assert _load_json(state_path)["schema_version"] == "4"
    assert migrated["checkpoint_runs"][0]["attempts"][0]["session_id"] == "session-001"


def test_lifecycle_state_migrates_v2_branch_with_action_lineage_hash(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="initial_review",
        branch_id="branch.v2-lineage",
        reason="Resume a branch persisted before action lineage hashes.",
    )
    state_path = branch_run / "state.json"
    state = _load_json(state_path)
    state["schema_version"] = "2"
    state.pop("lifecycle_spec_sha256")
    state.pop("package_sha256")
    state["branch"].pop("parent_action_state_sha256")
    for checkpoint in state["checkpoint_runs"]:
        checkpoint.pop("evidence_request_budget")
        checkpoint.pop("evidence_request_budget_remaining")
        checkpoint.pop("evidence_request_actions")
        for attempt in checkpoint["attempts"]:
            attempt.pop("inherited_from_parent")
    _write_json(state_path, state)

    migrated = read_evidence_lifecycle_state(package, branch_run)
    persisted = _load_json(state_path)

    assert persisted["schema_version"] == "4"
    assert migrated["branch"]["parent_action_state_sha256"]
    assert migrated["branch"]["branched_from_checkpoint_id"] == "initial_review"


def test_lifecycle_state_migrates_v3_to_v4_without_inventing_actions(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    state_path = run_dir / "state.json"
    state = _load_json(state_path)
    state["schema_version"] = "3"
    for checkpoint in state["checkpoint_runs"]:
        checkpoint.pop("evidence_request_budget")
        checkpoint.pop("evidence_request_budget_remaining")
        checkpoint.pop("evidence_request_actions")
    _write_json(state_path, state)

    migrated = read_evidence_lifecycle_state(package, run_dir)

    assert migrated["checkpoint_runs"][0]["evidence_request_actions"] == []
    assert _load_json(state_path)["schema_version"] == "4"


def test_v3_branch_rejects_attempts_on_inherited_checkpoint_records(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="response_review",
        branch_id="branch.impossible-v3-lineage",
        reason="Construct an impossible v3 inherited-attempt payload.",
    )
    state_path = branch_run / "state.json"
    state = _load_json(state_path)
    state["schema_version"] = "3"
    state["branch"].pop("parent_action_state_sha256")
    for checkpoint in state["checkpoint_runs"]:
        checkpoint.pop("evidence_request_budget")
        checkpoint.pop("evidence_request_budget_remaining")
        checkpoint.pop("evidence_request_actions")
        for attempt in checkpoint["attempts"]:
            attempt.pop("inherited_from_parent")
    _write_json(state_path, state)

    with pytest.raises(EvidenceLifecycleError, match="v3 inherited checkpoint cannot contain attempts"):
        read_evidence_lifecycle_state(package, branch_run)


def test_v3_branch_migration_preserves_branch_local_attempts(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    _complete_demo_lifecycle(package, parent_run)
    branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="response_review",
        branch_id="branch.legacy-local-attempt",
        reason="Match the attempt lineage emitted by the PR16 v3 branch runtime.",
    )
    state_path = branch_run / "state.json"
    state = _load_json(state_path)
    for checkpoint in state["checkpoint_runs"]:
        checkpoint["attempts"] = []
    _write_json(state_path, state)
    open_checkpoint_attempt(
        package,
        branch_run,
        session_id="branch-session-001",
        execution_mode="fresh_context",
    )
    state = _load_json(state_path)
    state["schema_version"] = "3"
    state["branch"].pop("parent_action_state_sha256")
    for checkpoint in state["checkpoint_runs"]:
        checkpoint.pop("evidence_request_budget")
        checkpoint.pop("evidence_request_budget_remaining")
        checkpoint.pop("evidence_request_actions")
        for attempt in checkpoint["attempts"]:
            attempt.pop("inherited_from_parent")
    _write_json(state_path, state)

    migrated = read_evidence_lifecycle_state(package, branch_run)

    assert migrated["checkpoint_runs"][0]["attempts"] == []
    assert migrated["checkpoint_runs"][1]["attempts"] == [
        {
            "attempt_id": "response_review.attempt-001",
            "session_id": "branch-session-001",
            "sequence": 1,
            "execution_mode": "fresh_context",
            "status": "active",
            "resumed_from_attempt_id": None,
            "failure_kind": None,
            "episode_request_sha256": None,
            "inherited_from_parent": False,
        }
    ]


def test_v3_state_cannot_smuggle_conditional_evidence_fields(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    state_path = run_dir / "state.json"
    state = _load_json(state_path)
    state["schema_version"] = "3"
    _write_json(state_path, state)

    with pytest.raises(EvidenceLifecycleError, match="v3 lifecycle state cannot contain"):
        read_evidence_lifecycle_state(package, run_dir)


def test_lifecycle_state_budget_must_match_conditional_contract(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    state_path = run_dir / "state.json"
    state = _load_json(state_path)
    state["checkpoint_runs"][0]["evidence_request_budget"] = 2
    state["checkpoint_runs"][0]["evidence_request_budget_remaining"] = 2
    _write_json(state_path, state)

    with pytest.raises(EvidenceLifecycleError, match="budget does not match"):
        read_evidence_lifecycle_state(package, run_dir)


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


def test_requested_evidence_and_budget_survive_failed_attempt_retry(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    first_attempt = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="fresh_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    fail_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        failure_kind="provider_error",
    )
    second_attempt = open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-002",
        execution_mode="fresh_context",
    )

    repeated = lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Confirm the evidence acquired by the failed attempt remains available.",
        session_id="session-002",
    )

    assert repeated["outcome"] == "already_released"
    assert repeated["attempt_id"] == second_attempt["attempt_id"]
    assert repeated["budget_after"] == 0
    checkpoint = _load_json(run_dir / "state.json")["checkpoint_runs"][0]
    assert [attempt["status"] for attempt in checkpoint["attempts"]] == ["failed", "active"]
    assert checkpoint["evidence_request_actions"][0]["attempt_id"] == first_attempt["attempt_id"]
    assert (run_dir / "workspace/inbox/initial_review/requests/survey_revision/survey-rev-b.txt").is_file()


def test_fresh_retry_episode_request_binds_acquired_conditional_evidence(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="fresh_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    fail_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        failure_kind="provider_error",
    )
    context = LifecycleEpisodeContext.from_runtime_context(
        prepare_evidence_checkpoint(package, run_dir),
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )

    request = lifecycle_runtime._build_episode_request(
        context,
        _FunctionEpisodeEnvironment(lambda _request: {}),
        attempt_id="initial_review.attempt-002",
        session_id="session-002",
    )

    assert request.schema_version == "3"
    assert request.evidence_request_catalog is not None
    assert request.evidence_request_catalog.remaining_budget == 0
    assert len(request.released_evidence_artifacts) == 1
    artifact = request.released_evidence_artifacts[0]
    assert artifact.workspace_path == ("inbox/initial_review/requests/survey_revision/survey-rev-b.txt")
    assert len(artifact.sha256) == 64
    assert "hidden" not in request.model_dump_json()


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


def test_branch_inherits_requested_evidence_actions_and_consumed_budget(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    parent_run = tmp_path / "parent"
    branch_run = tmp_path / "branch"
    prepared = prepare_evidence_checkpoint(package, parent_run)
    open_checkpoint_attempt(
        package,
        parent_run,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        parent_run,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    _write_json(Path(prepared["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, parent_run)

    branch = branch_evidence_lifecycle(
        package,
        parent_run,
        branch_run,
        checkpoint_id="initial_review",
        branch_id="branch.conditional-evidence",
        reason="Reconsider the review without unseeing acquired evidence.",
    )

    checkpoint = branch["checkpoint_runs"][0]
    assert checkpoint["evidence_request_budget"] == 1
    assert checkpoint["evidence_request_budget_remaining"] == 0
    assert len(checkpoint["evidence_request_actions"]) == 1
    assert checkpoint["evidence_request_actions"][0]["inherited_from_parent"] is True
    assert branch["branch"]["parent_action_state_sha256"]
    assert (branch_run / "workspace/inbox/initial_review/requests/survey_revision/survey-rev-b.txt").read_text(
        encoding="utf-8"
    ) == "revision B\n"
    assert (branch_run / "evidence_requests/evidence-request-000001/artifacts/survey-rev-b.txt").is_file()


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


def test_submission_gate_rejects_undeclared_fields_when_checkpoint_contract_is_exact(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    contract_path = package / "lifecycle.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["checkpoints"][0]["required_submission_fields"] = ["checkpoint_id", "review_matrix"]
    contract["checkpoints"][0]["allow_additional_submission_fields"] = False
    _write_json(contract_path, contract)
    run_dir = tmp_path / "run"
    prepared = prepare_evidence_checkpoint(package, run_dir)
    _write_json(
        Path(prepared["submission_path"]),
        {
            "checkpoint_id": "initial_review",
            "review_matrix": {},
            "memo": {},
        },
    )

    with pytest.raises(EvidenceLifecycleError, match="undeclared fields: memo"):
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
    original_append = evidence_request_store_runtime.append_ledger_entry
    calls = 0

    def fail_first_append(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated ledger append failure")
        return original_append(*args, **kwargs)

    monkeypatch.setattr(evidence_request_store_runtime, "append_ledger_entry", fail_first_append)
    with pytest.raises(RuntimeError, match="simulated ledger append failure"):
        prepare_evidence_checkpoint(package, run_dir)

    monkeypatch.setattr(evidence_request_store_runtime, "append_ledger_entry", original_append)
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

    result = run_evidence_lifecycle(
        package,
        run_dir,
        episode_environment=_FunctionEpisodeEnvironment(resolve),
    )

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
        episode_environment=_FunctionEpisodeEnvironment(resolve),
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


def test_local_episode_environment_builds_fresh_adapters_in_one_workspace(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _WritingRegistry()
    environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=registry,
    )

    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    assert registry.build_count == 2
    assert len(set(registry.workspaces)) == 1
    assert (run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "agent_result.json").exists()
    assert (run_dir / "episodes" / "response_review" / "response_review.session-001" / "agent_result.json").exists()
    assert (run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "conversation.jsonl").exists()
    state = _load_json(run_dir / "state.json")
    assert [[attempt["status"] for attempt in checkpoint["attempts"]] for checkpoint in state["checkpoint_runs"]] == [
        ["submitted"],
        ["submitted"],
    ]
    assert {
        attempt["execution_mode"] for checkpoint in state["checkpoint_runs"] for attempt in checkpoint["attempts"]
    } == {"fresh_context"}


def test_fresh_local_environment_exposes_session_bound_conditional_request_tool(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _ConditionalWritingRegistry()
    environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=registry,
    )

    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    assert all("request_evidence" in names for names in registry.native_tool_names)
    assert all("request_evidence" in names for names in registry.request_tool_names)
    action = _load_json(run_dir / "state.json")["checkpoint_runs"][0]["evidence_request_actions"][0]
    assert action["session_id"] == "initial_review.session-001"
    assert action["attempt_id"] == "initial_review.attempt-001"


def test_local_episode_environment_marks_provider_failure_immediately(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_CrashingRegistry(),
    )

    with pytest.raises(RuntimeError, match="simulated crash"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    state = _load_json(run_dir / "state.json")
    attempt = state["checkpoint_runs"][0]["attempts"][0]
    assert attempt["status"] == "failed"
    assert attempt["failure_kind"] == "adapter_exception"
    assert (run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "agent_result.json").exists()


def test_local_episode_environment_reconciles_completed_result_when_submission_is_missing(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_CompletedWithoutSubmissionRegistry(),
    )

    with pytest.raises(EvidenceLifecycleError, match="checkpoint submission not found"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    session_dir = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    agent_result = _load_json(session_dir / "agent_result.json")
    assert agent_result["status"] == "failed"
    assert agent_result["failure_kind"] == "episode_submission_invalid"
    episode_result = _load_json(session_dir / "episode_result.json")
    assert episode_result["status"] == "completed"
    state = _load_json(run_dir / "state.json")
    assert state["checkpoint_runs"][0]["attempts"][0]["status"] == "failed"
    normalized = lifecycle_local_runtime._normalized_agent_evidence(
        model="test-model",
        adapter_kind="tool_loop",
        execution_mode="fresh_context",
        memory_visibility_policy="artifact_memory",
        max_turns=20,
        sessions=lifecycle_local_runtime._fresh_context_sessions(run_dir),
        lifecycle=state,
    )
    assert normalized["status"] == "failed"
    assert normalized["totals"]["failures"] == 1


def test_normalized_evidence_uses_host_attempt_when_failure_callback_breaks(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    base_environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_CompletedWithoutSubmissionRegistry(),
    )
    environment = _FailureRecordingCrashWrapper(base_environment)

    with pytest.raises(EvidenceLifecycleError, match="checkpoint submission not found") as raised:
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert any("failure reconciliation failed" in note for note in raised.value.__notes__)
    session_dir = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    assert _load_json(session_dir / "agent_result.json")["status"] == "completed"
    state = _load_json(run_dir / "state.json")
    normalized = lifecycle_local_runtime._normalized_agent_evidence(
        model="test-model",
        adapter_kind="tool_loop",
        execution_mode="fresh_context",
        memory_visibility_policy="artifact_memory",
        max_turns=20,
        sessions=lifecycle_local_runtime._fresh_context_sessions(run_dir),
        lifecycle=state,
    )
    assert normalized["status"] == "failed"
    assert normalized["sessions"][0]["failure_kind"] == "episode_submission_invalid"
    assert normalized["totals"]["failures"] == 1


def test_local_episode_environment_preserves_failed_attempt_artifacts_on_retry(tmp_path: Path) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    failed = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_CrashingRegistry(),
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        run_evidence_lifecycle(package, run_dir, episode_environment=failed)
    failed_result = run_dir / "episodes" / "initial_review" / "initial_review.session-001" / "agent_result.json"
    failed_bytes = failed_result.read_bytes()

    retry = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_WritingRegistry(),
    )
    result = run_evidence_lifecycle(package, run_dir, episode_environment=retry)

    assert result["status"] == "complete"
    assert failed_result.read_bytes() == failed_bytes
    assert (run_dir / "episodes" / "initial_review" / "initial_review.session-002" / "agent_result.json").is_file()


def test_local_episode_environment_recovers_crash_after_attempt_publication(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    environment = build_local_evidence_lifecycle_episode_environment(
        package_dir=package,
        model="test-model",
        adapter_kind="tool_loop",
        registry=_WritingRegistry(),
    )
    original_open_attempt = lifecycle_runtime.open_checkpoint_attempt

    def interrupt_after_publication(*args: Any, **kwargs: Any) -> Never:
        original_open_attempt(*args, **kwargs)
        raise KeyboardInterrupt("simulated host interruption")

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", interrupt_after_publication)
    with pytest.raises(KeyboardInterrupt, match="simulated host interruption"):
        run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    interrupted_dir = run_dir / "episodes" / "initial_review" / "initial_review.session-001"
    assert (interrupted_dir / "trajectory.jsonl").is_file()
    assert not (interrupted_dir / "agent_result.json").exists()

    monkeypatch.setattr(lifecycle_runtime, "open_checkpoint_attempt", original_open_attempt)
    result = run_evidence_lifecycle(package, run_dir, episode_environment=environment)

    assert result["status"] == "complete"
    interrupted = _load_json(interrupted_dir / "agent_result.json")
    assert interrupted["status"] == "failed"
    assert interrupted["failure_kind"] == "interrupted"
    assert interrupted["adapter_name"] == "unresolved"
    state = _load_json(run_dir / "state.json")
    assert [attempt["status"] for attempt in state["checkpoint_runs"][0]["attempts"]] == [
        "interrupted",
        "submitted",
    ]


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


def test_local_runner_records_aec_bench_source_provenance_not_caller_repository(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = _write_package(tmp_path / "package")
    caller_repository = tmp_path / "caller-repository"
    caller_repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=caller_repository, check=True)
    (caller_repository / "README.md").write_text("caller repository\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=caller_repository, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Lifecycle Test",
            "-c",
            "user.email=lifecycle@example.invalid",
            "commit",
            "-q",
            "-m",
            "initial",
        ],
        cwd=caller_repository,
        check=True,
    )
    monkeypatch.chdir(caller_repository)
    run_dir = tmp_path / "run"
    verification = {
        "lifecycle_id": "lifecycle.demo",
        "reward": 1.0,
        "overall": "pass",
        "passed": True,
        "gates": {"continuity": {"passed": True, "score": 1.0, "failures": []}},
    }

    run_local_evidence_lifecycle_fresh_context(
        package_dir=package,
        run_dir=run_dir,
        model="test-model",
        registry=_WritingRegistry(),
        verifier=lambda _package, _run: verification,
    )

    invocation = _load_json(run_dir / "experiment-manifest.json")
    expected_root = subprocess.check_output(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=Path(lifecycle_local_runtime.__file__).resolve().parent,
        text=True,
    ).strip()
    assert invocation["repository"]["root"] == expected_root
    assert invocation["repository"]["root"] != str(caller_repository)


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


def test_control_tool_requests_conditional_evidence_without_exposing_host_identity(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    tool = EvidenceLifecycleControlTool(
        package_dir=package,
        run_dir=run_dir,
        session_id="session-001",
    )

    response = json.loads(
        tool.request_evidence(
            "initial_review",
            "survey_revision",
            "Resolve the source revision discrepancy.",
        )
    )

    assert response == {
        "status": "released",
        "checkpoint_id": "initial_review",
        "request_id": "survey_revision",
        "remaining_budget": 0,
        "released_files": ["inbox/initial_review/requests/survey_revision/survey-rev-b.txt"],
    }
    assert "session" not in json.dumps(response)
    assert "attempt" not in json.dumps(response)
    assert "sha256" not in json.dumps(response)


def test_control_tool_rejects_blank_evidence_request_without_recording_an_action(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="fresh_context",
    )
    tool = EvidenceLifecycleControlTool(
        package_dir=package,
        run_dir=run_dir,
        session_id="session-001",
    )

    response = json.loads(tool.request_evidence("initial_review", "survey_revision", "  "))

    assert response == {
        "status": "rejected",
        "error": "evidence request arguments must not be blank",
    }
    assert _load_json(run_dir / "state.json")["checkpoint_runs"][0]["evidence_request_actions"] == []
    assert not (run_dir / "evidence_requests").exists()
    assert "hidden" not in json.dumps(response)


def test_fresh_context_prompt_explains_conditional_evidence_boundary() -> None:
    prompt = lifecycle_local_runtime._workspace_policy(
        {
            "branch": None,
            "evidence_request_catalog": {
                "checkpoint_id": "initial_review",
                "remaining_budget": 1,
            },
        },
        persistent=False,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        supports_evidence_requests=True,
    )

    assert "Declared within-checkpoint evidence is released only by request_evidence." in prompt


def test_evidence_request_protocol_binds_host_call_validation_boundary() -> None:
    assert evidence_request_protocol_runtime._EVIDENCE_REQUEST_PROTOCOL["call_validation_rule"] == (
        "malformed_or_blank_arguments_fail_without_lifecycle_action"
    )


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


def test_requested_evidence_obeys_lifecycle_visibility_policies(tmp_path: Path) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    initial = prepare_evidence_checkpoint(package, run_dir)
    open_checkpoint_attempt(
        package,
        run_dir,
        session_id="session-001",
        execution_mode="persistent_context",
    )
    lifecycle_runtime.request_evidence_checkpoint(
        package,
        run_dir,
        checkpoint_id="initial_review",
        request_id="survey_revision",
        reason="Resolve the source revision discrepancy.",
        session_id="session-001",
    )
    requested_path = "inbox/initial_review/requests/survey_revision/survey-rev-b.txt"
    current = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.CURRENT_RELEASE_ONLY,
    )
    assert json.loads(current.read_workspace_file(requested_path))["status"] == "ok"

    _write_json(Path(initial["submission_path"]), {"checkpoint_id": "initial_review"})
    submit_evidence_checkpoint(package, run_dir)
    prepare_evidence_checkpoint(package, run_dir)
    raw = EvidenceLifecycleWorkspaceTool(
        package_dir=package,
        run_dir=run_dir,
        visibility_policy=LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY,
    )

    assert json.loads(current.read_workspace_file(requested_path))["status"] == "rejected"
    assert json.loads(raw.read_workspace_file(requested_path))["status"] == "ok"


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
        build_local_evidence_lifecycle_episode_environment(
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


def test_persistent_local_session_exposes_conditional_request_tool_only_for_capable_package(
    tmp_path: Path,
) -> None:
    package = _write_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _ConditionalLifecycleSessionRegistry(package=package, run_dir=run_dir)

    task_run = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=run_dir,
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

    assert registry.tool_names == [
        "list_workspace",
        "read_workspace_file",
        "write_checkpoint_submission",
        "request_evidence",
        "submit_checkpoint",
        "revisit_checkpoint",
    ]
    assert registry.request_tool_names == registry.tool_names
    action = task_run["evidence"]["lifecycle"]["checkpoint_runs"][0]["evidence_request_actions"][0]
    assert action["session_id"] == "session-001"
    manifest = _load_json(run_dir / "experiment-manifest.json")
    metrics = _load_json(run_dir / "metrics.json")
    tool_schema_names = [item["name"] for item in manifest["interaction"]["tool_schema"]]
    assert "request_evidence" in tool_schema_names
    request_schema = next(item for item in manifest["interaction"]["tool_schema"] if item["name"] == "request_evidence")
    assert "self" not in request_schema["signature"]
    assert "session_id" not in request_schema["signature"]
    assert metrics["evidence_request_calls"] == 1
    assert metrics["accepted_evidence_requests"] == 1
    assert metrics["already_released_evidence_requests"] == 0
    assert metrics["rejected_evidence_requests"] == 0
    assert metrics["evidence_request_budget_consumed"] == 1
    assert manifest["interaction"]["evidence_request_protocol"]["sha256"]
    assert manifest["interaction"]["evidence_request_protocol"]["tool_schema_sha256"]
    artifact_paths = set(manifest["outputs"]["artifacts"])
    assert "evidence_requests/evidence-request-000001/action.json" in artifact_paths
    assert "evidence_requests/evidence-request-000001/committed.json" in artifact_paths
    assert "evidence_requests/evidence-request-000001/artifacts/survey-rev-b.txt" in artifact_paths
    assert "workspace/inbox/initial_review/requests/survey_revision/survey-rev-b.txt" in artifact_paths
    assert "workspace/checkpoints/initial_review/evidence-requests.json" in artifact_paths


def test_persistent_session_guidance_uses_package_capability_when_only_later_checkpoint_is_conditional(
    tmp_path: Path,
) -> None:
    package = _write_later_checkpoint_conditional_package(tmp_path / "package")
    run_dir = tmp_path / "run"
    registry = _LifecycleSessionRegistry(package=package, run_dir=run_dir)

    task_run = run_local_evidence_lifecycle_session(
        package_dir=package,
        run_dir=run_dir,
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

    assert task_run["evidence"]["lifecycle"]["status"] == "complete"
    assert "request_evidence" in registry.tool_names
    assert "Declared within-checkpoint evidence is released only by request_evidence." in registry.system_prompt
    assert "inspect checkpoints/<checkpoint_id>/evidence-requests.json" in registry.instruction


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


def _write_conditional_package(package: Path) -> Path:
    package = _write_package(package)
    lifecycle_path = package / "lifecycle.json"
    lifecycle = _load_json(lifecycle_path)
    lifecycle["checkpoints"][0]["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "survey_revision",
                "title": "Revised survey",
                "description": "Obtain the revised survey source.",
            },
            {
                "request_id": "outlet_inspection",
                "title": "Outlet inspection",
                "description": "Obtain the outlet inspection record.",
            },
        ],
    }
    _write_json(lifecycle_path, lifecycle)
    _write_json(
        package / "hidden" / "evidence-request-resolutions.json",
        {
            "schema_version": "1",
            "lifecycle_id": "lifecycle.demo",
            "resolutions": [
                {
                    "checkpoint_id": "initial_review",
                    "request_id": "survey_revision",
                    "source_path": "hidden/evidence_requests/initial_review/survey_revision",
                },
                {
                    "checkpoint_id": "initial_review",
                    "request_id": "outlet_inspection",
                    "source_path": "hidden/evidence_requests/initial_review/outlet_inspection",
                },
            ],
        },
    )
    survey = package / "hidden/evidence_requests/initial_review/survey_revision/survey-rev-b.txt"
    survey.parent.mkdir(parents=True)
    survey.write_text("revision B\n", encoding="utf-8")
    inspection = package / "hidden/evidence_requests/initial_review/outlet_inspection/inspection.txt"
    inspection.parent.mkdir(parents=True)
    inspection.write_text("inspection\n", encoding="utf-8")
    return package


def _write_prerequisite_conditional_package(package: Path) -> Path:
    package = _write_conditional_package(package)
    lifecycle_path = package / "lifecycle.json"
    lifecycle = _load_json(lifecycle_path)
    conditional = lifecycle["checkpoints"][0]["conditional_evidence"]
    conditional["request_budget"] = 2
    conditional["requests"][1]["prerequisite_request_ids"] = ["survey_revision"]

    resolution_path = package / "hidden" / "evidence-request-resolutions.json"
    resolutions = _load_json(resolution_path)
    for request_id in ("alternative_c", "alternative_d"):
        conditional["requests"].append(
            {
                "request_id": request_id,
                "title": request_id.replace("_", " ").title(),
                "description": f"Obtain {request_id.replace('_', ' ')} evidence.",
            }
        )
        source_path = f"hidden/evidence_requests/initial_review/{request_id}"
        resolutions["resolutions"].append(
            {
                "checkpoint_id": "initial_review",
                "request_id": request_id,
                "source_path": source_path,
            }
        )
        evidence = package / source_path / f"{request_id}.txt"
        evidence.parent.mkdir(parents=True)
        evidence.write_text(f"{request_id}\n", encoding="utf-8")
    _write_json(lifecycle_path, lifecycle)
    _write_json(resolution_path, resolutions)
    return package


def _write_later_checkpoint_conditional_package(package: Path) -> Path:
    package = _write_package(package)
    lifecycle_path = package / "lifecycle.json"
    lifecycle = _load_json(lifecycle_path)
    lifecycle["checkpoints"][1]["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "response_support",
                "title": "Response support",
                "description": "Obtain the response-stage support record.",
            }
        ],
    }
    _write_json(lifecycle_path, lifecycle)
    _write_json(
        package / "hidden" / "evidence-request-resolutions.json",
        {
            "schema_version": "1",
            "lifecycle_id": "lifecycle.demo",
            "resolutions": [
                {
                    "checkpoint_id": "response_review",
                    "request_id": "response_support",
                    "source_path": "hidden/evidence_requests/response_review/response_support",
                }
            ],
        },
    )
    support = package / "hidden/evidence_requests/response_review/response_support/support.txt"
    support.parent.mkdir(parents=True)
    support.write_text("response support\n", encoding="utf-8")
    return package


def _write_all_conditional_package(package: Path) -> Path:
    package = _write_conditional_package(package)
    lifecycle_path = package / "lifecycle.json"
    lifecycle = _load_json(lifecycle_path)
    lifecycle["checkpoints"][1]["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "response_support",
                "title": "Response support",
                "description": "Obtain the response-stage support record.",
            }
        ],
    }
    _write_json(lifecycle_path, lifecycle)
    resolutions_path = package / "hidden" / "evidence-request-resolutions.json"
    resolutions = _load_json(resolutions_path)
    resolutions["resolutions"].append(
        {
            "checkpoint_id": "response_review",
            "request_id": "response_support",
            "source_path": "hidden/evidence_requests/response_review/response_support",
        }
    )
    _write_json(resolutions_path, resolutions)
    support = package / "hidden/evidence_requests/response_review/response_support/support.txt"
    support.parent.mkdir(parents=True)
    support.write_text("response support\n", encoding="utf-8")
    return package


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, entries: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(entry, sort_keys=True)}\n" for entry in entries),
        encoding="utf-8",
    )


class _FunctionEpisodeEnvironment:
    execution_mode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY
    requested_adapter = "deterministic"
    requested_model = "gold"
    max_turns_per_session = 1

    def __init__(self, resolve: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
        self._resolve = resolve

    def recover(self, _context: LifecycleEpisodeContext) -> None:
        return None

    def prepare(self, _request: LifecycleEpisodeRequest) -> None:
        return None

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        return None

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        configuration = self._resolve(request.model_dump(mode="json"))
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="completed",
            requested_adapter="deterministic",
            requested_model="gold",
            max_turns_per_session=request.max_turns_per_session,
            adapter="in_process",
            resolved_model="gold",
            configuration=configuration,
            usage=LifecycleEpisodeUsage(),
        )


def _complete_demo_lifecycle(package: Path, run_dir: Path) -> None:
    def resolve(context: dict) -> dict:
        _write_json(Path(context["submission_path"]), {"checkpoint_id": context["checkpoint_id"]})
        return {"status": "completed"}

    run_evidence_lifecycle(
        package,
        run_dir,
        episode_environment=_FunctionEpisodeEnvironment(resolve),
    )


class _WritingRegistry:
    def __init__(self) -> None:
        self.build_count = 0
        self.workspaces: list[str] = []

    def build(self, *, workspace: str, **_kwargs):
        self.build_count += 1
        self.workspaces.append(workspace)
        return _WritingAdapter()


class _ConditionalWritingRegistry:
    def __init__(self) -> None:
        self.native_tool_names: list[list[str]] = []
        self.request_tool_names: list[list[str]] = []

    def build(self, *, native_tools, **_kwargs):
        self.native_tool_names.append([tool.__name__ for tool in native_tools])
        request_evidence = next(
            (tool for tool in native_tools if tool.__name__ == "request_evidence"),
            None,
        )
        registry = self

        class _ConditionalWritingAdapter:
            def execute(self, request):
                registry.request_tool_names.append([tool.name for tool in request.tools])
                output_path = Path(request.output_path)
                checkpoint_id = output_path.stem
                if checkpoint_id == "initial_review":
                    assert request_evidence is not None
                    response = json.loads(
                        request_evidence(
                            checkpoint_id,
                            "survey_revision",
                            "Resolve the source revision discrepancy.",
                        )
                    )
                    assert response["status"] == "released"
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

        return _ConditionalWritingAdapter()


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


class _CompletedWithoutSubmissionRegistry:
    def build(self, **_kwargs: Any) -> _CompletedWithoutSubmissionAdapter:
        return _CompletedWithoutSubmissionAdapter()


class _CompletedWithoutSubmissionAdapter:
    def execute(self, _request: Any) -> SimpleNamespace:
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


class _FailureRecordingCrashWrapper:
    def __init__(self, environment: LifecycleEpisodeEnvironment) -> None:
        self._environment = environment

    @property
    def execution_mode(self) -> LifecycleExecutionMode:
        return self._environment.execution_mode

    @property
    def memory_visibility_policy(self) -> LifecycleVisibilityPolicy:
        return self._environment.memory_visibility_policy

    @property
    def requested_adapter(self) -> str:
        return self._environment.requested_adapter

    @property
    def requested_model(self) -> str:
        return self._environment.requested_model

    @property
    def max_turns_per_session(self) -> int:
        return self._environment.max_turns_per_session

    def recover(self, context: LifecycleEpisodeContext) -> None:
        return self._environment.recover(context)

    def prepare(self, request: LifecycleEpisodeRequest) -> None:
        return self._environment.prepare(request)

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        return self._environment.execute(request)

    def record_failure(
        self,
        _request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        raise RuntimeError("cannot reconcile local agent result")


class _LifecycleSessionRegistry:
    def __init__(self, *, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir
        self.build_count = 0
        self.execute_count = 0
        self.tool_names: list[str] = []
        self.instruction = ""
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
                registry.instruction = request.instruction
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


class _ConditionalLifecycleSessionRegistry:
    def __init__(self, *, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir
        self.tool_names: list[str] = []
        self.request_tool_names: list[str] = []

    def build(self, *, native_tools, **_kwargs):
        self.tool_names = [tool.__name__ for tool in native_tools]
        request_evidence = next(tool for tool in native_tools if tool.__name__ == "request_evidence")
        submit_checkpoint = next(tool for tool in native_tools if tool.__name__ == "submit_checkpoint")
        registry = self

        class _ConditionalSessionAdapter:
            def execute(self, request):
                registry.request_tool_names = [tool.name for tool in request.tools]
                requested = False
                while True:
                    state = read_evidence_lifecycle_state(registry.package, registry.run_dir)
                    checkpoint_id = state["active_checkpoint_id"]
                    if checkpoint_id is None:
                        break
                    if checkpoint_id == "initial_review" and not requested:
                        response = json.loads(
                            request_evidence(
                                checkpoint_id,
                                "survey_revision",
                                "Resolve the source revision discrepancy.",
                            )
                        )
                        assert response["status"] == "released"
                        requested = True
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

        return _ConditionalSessionAdapter()


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
