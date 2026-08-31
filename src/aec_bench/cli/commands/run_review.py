# ABOUTME: Formats persisted resolved runs, plans, semantic diffs, and accounting for CLI review.
# ABOUTME: Delegates planning, persistence, and reconciliation rules to their owning contracts.

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from aec_bench.contracts.run_accounting import TrialAccountingObservation, account_run
from aec_bench.ledger.evidence_run_store import EvidenceRunStore, StoredEvidenceRun


def load_run(store_root: Path, selector: str) -> StoredEvidenceRun:
    """Load one persisted evidence run by its key or UUID."""

    return EvidenceRunStore(store_root).find_run(selector)


def plan_data(stored: StoredEvidenceRun) -> dict[str, Any]:
    """Return the persisted requested specification and plan without executing."""

    data: dict[str, Any] = {
        "run": stored.spec.model_dump(mode="json"),
        "state": stored.state.model_dump(mode="json"),
        "plan": None if stored.plan is None else stored.plan.model_dump(mode="json"),
    }
    if stored.plan is not None:
        data["summary"] = stored.plan.summary.model_dump(mode="json")
    return data


def inspect_data(stored: StoredEvidenceRun, observations_path: Path | None = None) -> dict[str, Any]:
    """Return the compact review view for one persisted run."""

    spec = stored.spec
    plan = stored.plan
    data = {
        "run_identity": spec.run_identity.model_dump(mode="json"),
        "experiment_identity": spec.experiment_identity.model_dump(mode="json"),
        "run_name": spec.run_name,
        "created_at": spec.created_at.isoformat(),
        "agent_conditions": [condition.model_dump(mode="json") for condition in spec.agent_conditions],
        "task_releases": [release.model_dump(mode="json") for release in spec.task_releases],
        "compute": spec.compute.model_dump(mode="json"),
        "repetitions": spec.repetitions,
        "visibility": list(spec.visibility),
        "state": stored.state.state,
        "plan_identity": None if plan is None else plan.plan_identity.model_dump(mode="json"),
        "plan_trial_count": 0 if plan is None else len(plan.trials),
        "plan_summary": None if plan is None else plan.summary.model_dump(mode="json"),
        "plan_readiness": "ready" if plan is not None and plan.state == "ready" else "not_ready",
        "provider_identity": {
            "requested": None
            if spec.provider_route_request is None
            else spec.provider_route_request.model_dump(mode="json"),
            "observed": None,
        },
        "accounting": None,
    }
    if observations_path is not None:
        data["accounting"] = reconcile_data(stored, observations_path)
    return data


def diff_data(
    left: StoredEvidenceRun, right: StoredEvidenceRun, *, left_selector: str, right_selector: str
) -> dict[str, Any]:
    """Return semantic field-level changes between two persisted runs."""

    left_condition = _condition_view(left)
    right_condition = _condition_view(right)
    changes: list[dict[str, Any]] = []
    unchanged: list[str] = []
    _append_diffs(changes, "condition", left_condition, right_condition, unchanged=unchanged)
    return {"left": left_selector, "right": right_selector, "changes": changes, "unchanged": unchanged}


def reconcile_data(
    stored: StoredEvidenceRun,
    observations_path: Path,
    *,
    cancellation_requested: bool = False,
) -> dict[str, Any]:
    """Reconcile an explicit JSON observation file against a persisted ready plan."""

    if stored.plan is None:
        raise ValueError("run reconcile requires a persisted plan")
    if stored.plan.state not in {"ready", "started", "closed"}:
        raise ValueError("run reconcile requires a ready, started, or closed plan")
    if observations_path.is_symlink() or not observations_path.is_file():
        raise ValueError("reconcile observations must be a regular JSON file")
    try:
        payload = json.loads(observations_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("reconcile observations are not valid JSON") from error
    if not isinstance(payload, list):
        raise ValueError("reconcile observations must be a JSON list")
    observations = tuple(TrialAccountingObservation.model_validate(item) for item in payload)
    result = account_run(
        stored.spec,
        stored.plan,
        observations,
        cancellation_requested=cancellation_requested,
    )
    accounting: dict[str, Any] = result.accounting.model_dump(mode="json")
    accounting["observed"] = (
        accounting["counts"]["planned"] - accounting["counts"]["missing"] + accounting["counts"]["unexpected"]
    )
    accounting["accepted_record_count"] = len(result.accepted_records)
    return accounting


def _condition_view(stored: StoredEvidenceRun) -> dict[str, Any]:
    """Return requested semantics without occurrence IDs, timestamps, or trial UUID noise."""

    spec = stored.spec
    return {
        "experiment": {
            "key": str(spec.experiment_identity.key),
            "version": spec.experiment_identity.version,
        },
        "run_name": spec.run_name,
        "tasks": {
            str(release.task_id): {
                "version": release.task_identity.version,
                "snapshot": release.model_dump(mode="json", exclude={"task_identity": {"id", "aliases"}}),
            }
            for release in spec.task_releases
        },
        "agents": {
            str(condition.identity.key): {
                "version": condition.identity.version,
                **condition.model_dump(mode="json", exclude={"identity"}),
            }
            for condition in spec.agent_conditions
        },
        "compute": spec.compute.model_dump(mode="json"),
        "repetitions": spec.repetitions,
        "verification_enabled": spec.verification_enabled,
        "reviewer": None if spec.reviewer is None else spec.reviewer.model_dump(mode="json"),
        "randomization_seed": spec.randomization_seed,
        "execution_policy": spec.execution_policy.model_dump(mode="json"),
        "visibility": list(spec.visibility),
        "expected_authorities": [item.model_dump(mode="json") for item in spec.expected_authorities],
        "evaluation_profile": None
        if spec.evaluation_regime is None
        else spec.evaluation_regime.model_dump(mode="json"),
        "provider_route": None
        if spec.provider_route_request is None
        else spec.provider_route_request.model_dump(mode="json"),
    }


def _append_diffs(
    changes: list[dict[str, Any]],
    path: str,
    left: Any,
    right: Any,
    *,
    unchanged: list[str],
) -> None:
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        keys = sorted(set(left) | set(right))
        for key in keys:
            child = f"{path}.{key}"
            if key not in left:
                changes.append({"path": child, "before": None, "after": right[key]})
            elif key not in right:
                changes.append({"path": child, "before": left[key], "after": None})
            else:
                _append_diffs(changes, child, left[key], right[key], unchanged=unchanged)
        return
    if isinstance(left, Sequence) and isinstance(right, Sequence) and not isinstance(left, str | bytes):
        for index in range(max(len(left), len(right))):
            child = f"{path}[{index}]"
            if index >= len(left):
                changes.append({"path": child, "before": None, "after": right[index]})
            elif index >= len(right):
                changes.append({"path": child, "before": left[index], "after": None})
            else:
                _append_diffs(changes, child, left[index], right[index], unchanged=unchanged)
        return
    if left != right:
        changes.append({"path": path, "before": left, "after": right})
    else:
        unchanged.append(path)


__all__ = ("diff_data", "inspect_data", "load_run", "plan_data", "reconcile_data")
