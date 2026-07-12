# ABOUTME: Tests read-only live-resolver replay of cumulative lifecycle-operation histories.
# ABOUTME: Proves internally consistent dependency and currentness forgeries fail semantic replay.

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness import lifecycle_operation_store
from aec_bench.meta_harness.evidence_lifecycle import (
    EvidenceLifecycleError,
    execute_lifecycle_operation,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    prepare_evidence_checkpoint,
    submit_evidence_checkpoint,
)
from aec_bench.meta_harness.evidence_lifecycle_state import (
    EvidenceLifecycleRunState,
    LifecycleOperationActionRecord,
    LifecycleOperationDisposition,
    LifecycleOperationOutcome,
)
from aec_bench.meta_harness.lifecycle_operation_protocol import (
    lifecycle_operation_state_sha256,
    validate_lifecycle_operation_run_state,
)
from aec_bench.meta_harness.lifecycle_operation_store import validate_lifecycle_operation_resolver_replay
from aec_bench.task_world_templates.catalogue import get_template
from aec_bench.task_world_templates.lifecycles import materialize_lifecycle_template

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_bytes(run: Path) -> dict[str, bytes]:
    return {path.relative_to(run).as_posix(): path.read_bytes() for path in sorted(run.rglob("*")) if path.is_file()}


def _visible_source_sha256(run: Path) -> str:
    source = _read_json(run / "workspace" / "hydraulics" / "current-source.json")
    return str(source["visible_source_state_sha256"])


def _execute(
    package: Path,
    run: Path,
    *,
    checkpoint_id: str,
    operation_id: str,
    session_id: str,
) -> dict[str, Any]:
    return execute_lifecycle_operation(
        package,
        run,
        checkpoint_id=checkpoint_id,
        operation_id=operation_id,
        visible_source_state_sha256=_visible_source_sha256(run),
        reason=f"Execute {operation_id} for resolver-replay testing.",
        session_id=session_id,
    )


def _prepare(tmp_path: Path, *, variant_id: str) -> tuple[Path, Path]:
    package = materialize_lifecycle_template(
        get_template(TEMPLATE_ID),
        tmp_path / "package",
        variant_id=variant_id,
    )
    run = tmp_path / "run"
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="baseline.session-001",
        execution_mode="persistent_context",
    )
    return package, run


def _advance_to_revision(package: Path, run: Path) -> None:
    submission = {
        "checkpoint_id": "baseline_analysis",
        "visible_source_state_sha256": _visible_source_sha256(run),
        "selected_operations": {},
        "accepted_decisions": {},
        "readiness_decision": "baseline_complete",
        "claim_boundary": {},
    }
    path = run / "workspace" / "submissions" / "baseline_analysis.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_json(path, submission)
    submit_evidence_checkpoint(package, run)
    prepare_evidence_checkpoint(package, run)
    open_checkpoint_attempt(
        package,
        run,
        session_id="revision.session-001",
        execution_mode="persistent_context",
    )


def _rehash_state(package: Path, run: Path, state: EvidenceLifecycleRunState) -> None:
    resolver = lifecycle_operation_store._resolver_for_package(package, run)
    prior_actions: list[LifecycleOperationActionRecord] = []
    for checkpoint in state.checkpoint_runs:
        remaining_budget = checkpoint.operation_budget
        rewritten_actions = []
        for action in checkpoint.operation_actions:
            source_before = resolver.current_source(prior_actions)
            pre_action_state_sha256 = lifecycle_operation_state_sha256(
                state,
                checkpoint_id=action.checkpoint_id,
                source=source_before,
                operation_budget_remaining=remaining_budget,
                actions=prior_actions,
            )
            budget_after = remaining_budget - action.budget_consumed
            rewritten = action.model_copy(
                update={
                    "budget_before": remaining_budget,
                    "budget_after": budget_after,
                    "pre_action_state_sha256": pre_action_state_sha256,
                }
            )
            source_after = resolver.current_source([*prior_actions, rewritten])
            rewritten = rewritten.model_copy(
                update={
                    "post_action_state_sha256": lifecycle_operation_state_sha256(
                        state,
                        checkpoint_id=rewritten.checkpoint_id,
                        source=source_after,
                        operation_budget_remaining=budget_after,
                        actions=[*prior_actions, rewritten],
                    )
                }
            )
            rewritten_actions.append(rewritten)
            prior_actions.append(rewritten)
            remaining_budget = budget_after
        checkpoint.operation_actions = rewritten_actions
        checkpoint.operation_budget_remaining = remaining_budget
    _write_json(run / "state.json", state.model_dump(mode="json"))
    for action in prior_actions:
        _write_json(
            run / "lifecycle_operations" / action.action_id / "action.json",
            action.model_dump(mode="json"),
        )
    lifecycle_operation_store._write_lifecycle_operation_catalog(
        package,
        run,
        load_evidence_lifecycle_spec(package),
        state,
    )


@pytest.mark.parametrize("forgery", ["source", "prerequisite_status"])
def test_resolver_replay_rejects_action_free_catalog_forgeries(
    tmp_path: Path,
    forgery: str,
) -> None:
    package, run = _prepare(tmp_path, variant_id="tailwater_revision")
    catalog_path = run / "workspace" / "checkpoints" / "baseline_analysis" / "operations.json"
    catalog = _read_json(catalog_path)
    if forgery == "source":
        catalog["visible_source_state_sha256"] = "0" * 64
    else:
        operations = cast(list[dict[str, Any]], catalog["operations"])
        detention = next(
            operation
            for operation in operations
            if operation["operation_id"] == "detention-outlet.design-10yr.declared-outlet"
        )
        assert detention["status"] == "prerequisites_incomplete"
        detention["status"] = "available"
    _write_json(catalog_path, catalog)
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    spec = load_evidence_lifecycle_spec(package)
    before = _run_bytes(run)

    with pytest.raises(EvidenceLifecycleError, match="catalogue does not match"):
        validate_lifecycle_operation_resolver_replay(package, run, state, spec)

    assert _run_bytes(run) == before


def test_resolver_replay_rejects_unexpected_empty_transaction_directory(tmp_path: Path) -> None:
    package, run = _prepare(tmp_path, variant_id="tailwater_revision")
    unexpected = run / "lifecycle_operations" / "operation-999999"
    unexpected.mkdir(parents=True)
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    spec = load_evidence_lifecycle_spec(package)
    before = _run_bytes(run)

    with pytest.raises(EvidenceLifecycleError, match="transaction inventory"):
        validate_lifecycle_operation_resolver_replay(package, run, state, spec)

    assert unexpected.is_dir()
    assert _run_bytes(run) == before


def test_resolver_replay_rejects_owner_reassignment_absent_from_append_only_ledger(tmp_path: Path) -> None:
    package, run = _prepare(tmp_path, variant_id="tailwater_revision")
    completed = _execute(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        session_id="baseline.session-001",
    )
    later_attempt = open_checkpoint_attempt(
        package,
        run,
        session_id="baseline.session-002",
        execution_mode="persistent_context",
    )
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    checkpoint = state.checkpoint("baseline_analysis")
    index = next(
        index for index, action in enumerate(checkpoint.operation_actions) if action.action_id == completed["action_id"]
    )
    action = checkpoint.operation_actions[index]
    reassigned = action.model_copy(
        update={
            "attempt_id": later_attempt["attempt_id"],
            "session_id": later_attempt["session_id"],
        }
    )
    checkpoint.operation_actions[index] = reassigned
    _write_json(run / "state.json", state.model_dump(mode="json"))
    _write_json(
        run / "lifecycle_operations" / reassigned.action_id / "action.json",
        reassigned.model_dump(mode="json"),
    )
    spec = load_evidence_lifecycle_spec(package)
    validate_lifecycle_operation_run_state(state, spec)
    before = _run_bytes(run)

    with pytest.raises(EvidenceLifecycleError, match="ledger entry conflicts"):
        validate_lifecycle_operation_resolver_replay(package, run, state, spec)

    assert _run_bytes(run) == before


@pytest.mark.parametrize(
    ("duplicate", "message"),
    [
        ("canonical", "artifact path values must be unique"),
        ("workspace", "workspace path values must be unique"),
    ],
)
def test_operation_action_rejects_duplicate_artifact_lineage(
    tmp_path: Path,
    duplicate: str,
    message: str,
) -> None:
    package, run = _prepare(tmp_path, variant_id="tailwater_revision")
    completed = _execute(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        session_id="baseline.session-001",
    )
    payload = cast(dict[str, Any], json.loads(json.dumps(completed)))
    artifacts = cast(list[dict[str, Any]], payload["artifacts"])
    duplicated = dict(artifacts[0])
    action_id = str(payload["action_id"])
    if duplicate == "canonical":
        duplicated["workspace_path"] = f"inbox/baseline_analysis/operations/{action_id}/duplicate.json"
    else:
        duplicated["path"] = f"lifecycle_operations/{action_id}/artifacts/duplicate.json"
    artifacts.append(duplicated)

    with pytest.raises(ValidationError, match=message):
        LifecycleOperationActionRecord.model_validate(payload)


def test_resolver_replay_rejects_rehashed_detention_without_required_hydrology_action(tmp_path: Path) -> None:
    package, run = _prepare(tmp_path, variant_id="tailwater_revision")
    _execute(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        session_id="baseline.session-001",
    )
    detention = _execute(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="detention-outlet.design-10yr.declared-outlet",
        session_id="baseline.session-001",
    )
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    checkpoint = state.checkpoint("baseline_analysis")
    index = next(
        index for index, action in enumerate(checkpoint.operation_actions) if action.action_id == detention["action_id"]
    )
    action = checkpoint.operation_actions[index]
    result_manifest_path = run / "lifecycle_operations" / action.action_id / "result-manifest.json"
    result_manifest = _read_json(result_manifest_path)
    result_manifest["prerequisite_action_ids"] = []
    _write_json(result_manifest_path, result_manifest)
    checkpoint.operation_actions[index] = action.model_copy(
        update={
            "prerequisite_action_ids": (),
            "result_manifest_sha256": _sha256(result_manifest_path),
        }
    )
    _rehash_state(package, run, state)
    spec = load_evidence_lifecycle_spec(package)
    validate_lifecycle_operation_run_state(state, spec)
    before = _run_bytes(run)

    with pytest.raises(EvidenceLifecycleError, match="prerequisites do not match"):
        validate_lifecycle_operation_resolver_replay(package, run, state, spec)

    assert _run_bytes(run) == before


def test_resolver_replay_rejects_forged_major_hydrology_reuse_after_input_drift(tmp_path: Path) -> None:
    package, run = _prepare(tmp_path, variant_id="major_idf_revision")
    baseline = _execute(
        package,
        run,
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.major-100yr",
        session_id="baseline.session-001",
    )
    _advance_to_revision(package, run)
    _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        session_id="revision.session-001",
    )
    revised = _execute(
        package,
        run,
        checkpoint_id="revision_analysis",
        operation_id="hydrology.major-100yr",
        session_id="revision.session-001",
    )
    state = EvidenceLifecycleRunState.model_validate(_read_json(run / "state.json"))
    baseline_action = next(
        action
        for action in state.checkpoint("baseline_analysis").operation_actions
        if action.action_id == baseline["action_id"]
    )
    checkpoint = state.checkpoint("revision_analysis")
    index = next(
        index for index, action in enumerate(checkpoint.operation_actions) if action.action_id == revised["action_id"]
    )
    revised_action = checkpoint.operation_actions[index]
    checkpoint.operation_actions[index] = revised_action.model_copy(
        update={
            "outcome": LifecycleOperationOutcome.ALREADY_CURRENT,
            "disposition": LifecycleOperationDisposition.REUSED,
            "input_projection_sha256": baseline_action.input_projection_sha256,
            "result_manifest_sha256": None,
            "prerequisite_action_ids": baseline_action.prerequisite_action_ids,
            "retained_from_action_id": baseline_action.action_id,
            "artifacts": baseline_action.artifacts,
            "budget_consumed": 0,
        }
    )
    transaction = run / "lifecycle_operations" / revised_action.action_id
    (transaction / "result-manifest.json").unlink()
    shutil.rmtree(transaction / "artifacts")
    shutil.rmtree(run / "workspace" / "inbox" / revised_action.checkpoint_id / "operations" / revised_action.action_id)
    _rehash_state(package, run, state)
    spec = load_evidence_lifecycle_spec(package)
    validate_lifecycle_operation_run_state(state, spec)
    before = _run_bytes(run)

    with pytest.raises(EvidenceLifecycleError, match="currentness does not match"):
        validate_lifecycle_operation_resolver_replay(package, run, state, spec)

    assert _run_bytes(run) == before
