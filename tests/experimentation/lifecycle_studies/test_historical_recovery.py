# ABOUTME: Tests protected schema-1 lifecycle study recovery from retained conditional and operation evidence.
# ABOUTME: Keeps historical compatibility cases separate from the large current ablation test module.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import aec_bench.experimentation.lifecycle_studies.ablation_plan as ablation_plan_runtime
import aec_bench.experimentation.lifecycle_studies.historical_evidence as historical_evidence_runtime
import aec_bench.lifecycles.recording as lifecycle_recording_runtime
from aec_bench.experimentation.lifecycle_studies.ablation import (
    LifecycleAblationManifest,
    LifecycleAblationTrial,
    build_lifecycle_ablation_plan,
)
from aec_bench.experimentation.lifecycle_studies.retention import (
    recover_lifecycle_ablation_record,
    validate_lifecycle_ablation_record,
)
from aec_bench.harness.lifecycle_local import _run_local_lifecycle_fresh_session
from aec_bench.ledger.reader import read_trial_record
from aec_bench.lifecycles.catalogue import (
    lifecycle_operation_resolver,
    materialize_lifecycle,
    verify_lifecycle,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_review_smoke import (
    write_hydraulic_review_smoke_submission,
)
from tests.support.lifecycle_studies import (
    downgrade_canonical_lifecycle_invocation_to_schema_one as _downgrade_canonical_invocation_to_schema_one,
)
from tests.support.lifecycle_studies import (
    record_completed_lifecycle_invocation as _record_completed_lifecycle_invocation,
)
from tests.support.lifecycle_studies import (
    recorded_conditional_lifecycle_ablation_trial as _conditional_recorded_trial,
)
from tests.support.lifecycle_studies import (
    recorded_lifecycle_ablation_trial as _recorded_trial,
)
from tests.support.lifecycle_studies import (
    rewrite_canonical_lifecycle_invocation as _rewrite_canonical_invocation,
)
from tests.support.lifecycle_studies import (
    single_lifecycle_ablation_manifest as _single_manifest,
)

OPERATION_TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def test_schema_one_recovery_preserves_conditional_evidence_transaction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, trial, package, run_dir = _conditional_recorded_trial(tmp_path, monkeypatch)
    state = _read_json(run_dir / "state.json")
    assert state["schema_version"] == "6"
    assert sum(len(checkpoint["evidence_request_actions"]) for checkpoint in state["checkpoint_runs"]) == 1
    _downgrade_canonical_invocation_to_schema_one(run_dir)

    record_path = recover_lifecycle_ablation_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    record = read_trial_record(record_path, ledger_root=Path(manifest.ledger_root))
    validate_lifecycle_ablation_record(record, manifest, trial)


def test_schema_one_recovery_preserves_operation_transaction(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _operation_recorded_trial(tmp_path)
    state = _read_json(run_dir / "state.json")
    assert state["schema_version"] == "7"
    assert sum(len(checkpoint["operation_actions"]) for checkpoint in state["checkpoint_runs"]) > 0
    _downgrade_canonical_invocation_to_schema_one(run_dir)

    record_path = recover_lifecycle_ablation_record(
        manifest=manifest,
        trial=trial,
        package_dir=package,
        run_dir=run_dir,
    )

    record = read_trial_record(record_path, ledger_root=Path(manifest.ledger_root))
    validate_lifecycle_ablation_record(record, manifest, trial)


def test_schema_one_metrics_reject_coercive_operation_budget(tmp_path: Path) -> None:
    _manifest, _trial, _package, run_dir = _operation_recorded_trial(tmp_path)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = _read_json(experiment_path)
    state = _read_json(run_dir / "state.json")
    metrics = _read_json(run_dir / "metrics.json")
    verification = _read_json(run_dir / "verification.json")
    completed_action = next(
        action
        for checkpoint in state["checkpoint_runs"]
        for action in checkpoint["operation_actions"]
        if action["outcome"] == "completed"
    )
    completed_action["budget_consumed"] = True
    metrics["operation_budget_consumed"] = True

    with pytest.raises(ValueError, match="operation budget_consumed must be a non-negative integer"):
        historical_evidence_runtime._validate_metrics_against_run(
            run_dir,
            state,
            experiment,
            metrics,
            verification,
        )


@pytest.mark.parametrize("snapshot_kind", ["conditional", "operation"])
def test_schema_one_recovery_rejects_undeclared_reserved_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot_kind: str,
) -> None:
    if snapshot_kind == "conditional":
        manifest, trial, package, run_dir = _conditional_recorded_trial(tmp_path, monkeypatch)
        unexpected = run_dir / "evidence_requests" / "forged" / "action.json"
    else:
        manifest, trial, package, run_dir = _operation_recorded_trial(tmp_path)
        unexpected = run_dir / "lifecycle_operations" / "forged" / "action.json"
    _downgrade_canonical_invocation_to_schema_one(run_dir)
    unexpected.parent.mkdir(parents=True, exist_ok=True)
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


def test_schema_one_recovery_rejects_unknown_execution_status(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    _downgrade_canonical_invocation_to_schema_one(run_dir)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = _read_json(experiment_path)
    experiment["execution"]["status"] = "forged"
    _rewrite_canonical_invocation(run_dir, experiment)

    with pytest.raises(ValueError, match="historical lifecycle execution status is invalid"):
        recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


@pytest.mark.parametrize(
    ("field_name", "raw_value", "message"),
    [
        ("max_turns_per_session", 5.0, "max_turns_per_session must be a positive integer"),
        ("session_count", 3.0, "session_count must be a non-negative integer"),
    ],
)
def test_schema_one_recovery_rejects_coercive_execution_counts(
    tmp_path: Path,
    field_name: str,
    raw_value: object,
    message: str,
) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    _downgrade_canonical_invocation_to_schema_one(run_dir)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = _read_json(experiment_path)
    if field_name == "session_count":
        raw_value = float(experiment["execution"]["session_count"])
    experiment["execution"][field_name] = raw_value
    _rewrite_canonical_invocation(run_dir, experiment)

    with pytest.raises(ValueError, match=message):
        recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


def test_schema_one_recovery_rejects_unknown_session_status(tmp_path: Path) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    _downgrade_canonical_invocation_to_schema_one(run_dir)
    agent_result_path = next(run_dir.glob("**/agent_result.json"))
    agent_result = _read_json(agent_result_path)
    agent_result["status"] = "forged"
    agent_result_path.write_text(json.dumps(agent_result, sort_keys=True) + "\n", encoding="utf-8")
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = _read_json(experiment_path)
    relative = agent_result_path.relative_to(run_dir).as_posix()
    experiment["outputs"]["artifacts"][relative] = hashlib.sha256(agent_result_path.read_bytes()).hexdigest()
    _rewrite_canonical_invocation(run_dir, experiment)

    with pytest.raises(ValueError, match="lifecycle session status is invalid"):
        recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("repository_commit", "repository does not match"),
        ("repository_kind", "repository provenance kind is invalid"),
        ("repository_kind_source_tree", "source-tree commit does not match"),
        ("repository_dirty", "repository dirty state is invalid"),
        ("repository_dirty_string", "repository dirty state is invalid"),
        ("repository_dirty_digest", "repository dirty digest is invalid"),
        ("repository_clean_nonempty_digest", "dirty state and digest are inconsistent"),
        ("repository_dirty_empty_digest", "dirty state and digest are inconsistent"),
        ("runtime_adapter", "runtime dependencies do not match"),
        ("runtime_provider", "runtime dependencies do not match"),
        ("requested_adapter", "adapter does not match planned trial"),
    ],
)
def test_schema_one_recovery_rejects_incomplete_or_malformed_recorded_provenance(
    tmp_path: Path,
    mutation: str,
    message: str,
) -> None:
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    _downgrade_canonical_invocation_to_schema_one(run_dir)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = _read_json(experiment_path)
    if mutation == "repository_kind_source_tree":
        experiment["repository"]["repository_kind"] = "source_tree"
        experiment["repository"]["dirty"] = False
        experiment["repository"]["dirty_digest"] = hashlib.sha256(b"").hexdigest()
    elif mutation == "repository_dirty_string":
        experiment["repository"]["dirty"] = "false"
    elif mutation == "repository_clean_nonempty_digest":
        experiment["repository"]["dirty"] = False
        experiment["repository"]["dirty_digest"] = "f" * 64
    elif mutation == "repository_dirty_empty_digest":
        experiment["repository"]["dirty"] = True
        experiment["repository"]["dirty_digest"] = hashlib.sha256(b"").hexdigest()
    elif mutation == "repository_kind":
        experiment["repository"].pop("repository_kind")
    elif mutation.startswith("repository_"):
        experiment["repository"].pop(mutation.removeprefix("repository_"))
    elif mutation.startswith("runtime_"):
        key = mutation.removeprefix("runtime_")
        experiment["environment"]["runtime_provenance"].pop(key)
    else:
        experiment["model"].pop(mutation)
    _rewrite_canonical_invocation(run_dir, experiment)

    with pytest.raises(ValueError, match=message):
        recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )

    artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
    assert not artifact_dir.exists()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("reclassified_as_git", "Git repository commit is invalid"),
        ("dirty", "source-tree repository must be clean"),
        ("nonempty_clean_digest", "dirty state and digest are inconsistent"),
    ],
)
def test_schema_one_recovery_rejects_malformed_source_tree_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    source_inventory_sha256 = "a" * 64
    source_tree_provenance = {
        "root": str(tmp_path / "source-tree"),
        "commit": f"source-sha256:{source_inventory_sha256}",
        "dirty": False,
        "dirty_digest": hashlib.sha256(b"").hexdigest(),
        "source_inventory_sha256": source_inventory_sha256,
        "repository_kind": "source_tree",
    }
    monkeypatch.setattr(
        ablation_plan_runtime,
        "repository_provenance",
        lambda _path: dict(source_tree_provenance),
    )
    monkeypatch.setattr(
        lifecycle_recording_runtime,
        "repository_provenance",
        lambda _path: dict(source_tree_provenance),
    )
    manifest, trial, package, run_dir = _recorded_trial(tmp_path)
    _downgrade_canonical_invocation_to_schema_one(run_dir)
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = _read_json(experiment_path)
    if mutation == "reclassified_as_git":
        experiment["repository"]["repository_kind"] = "git"
    elif mutation == "dirty":
        experiment["repository"]["dirty"] = True
        experiment["repository"]["dirty_digest"] = "f" * 64
    else:
        experiment["repository"]["dirty_digest"] = "f" * 64
    _rewrite_canonical_invocation(run_dir, experiment)

    with pytest.raises(ValueError, match=message):
        recover_lifecycle_ablation_record(
            manifest=manifest,
            trial=trial,
            package_dir=package,
            run_dir=run_dir,
        )

    artifact_dir = Path(manifest.ledger_root) / manifest.experiment_id / "_artifacts" / trial.trial_id
    assert not artifact_dir.exists()


def _operation_recorded_trial(
    tmp_path: Path,
) -> tuple[LifecycleAblationManifest, LifecycleAblationTrial, Path, Path]:
    payload = _single_manifest(tmp_path).model_dump(mode="json")
    payload.update(
        {
            "experiment_id": "schema-one-operation-recovery",
            "lifecycle_template_id": OPERATION_TEMPLATE_ID,
            "variants": ["tailwater_revision"],
        }
    )
    payload["agents"][0]["model"] = "deterministic-operation-probe"
    manifest = LifecycleAblationManifest.model_validate(payload)
    return _record_trial(
        manifest,
        adapter_builder=lambda package, run: _HydraulicSmokeRegistry(package, run).build,
    )


def _record_trial(
    manifest: LifecycleAblationManifest,
    *,
    adapter_builder: Callable[[Path, Path], Callable[..., Any]],
) -> tuple[LifecycleAblationManifest, LifecycleAblationTrial, Path, Path]:
    plan = build_lifecycle_ablation_plan(manifest)
    trial = plan.trials[0]
    output_root = Path(manifest.output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_root / "plan.json").write_text(
        json.dumps(plan.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    package = materialize_lifecycle(
        manifest.lifecycle_template_id,
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    resolver = lifecycle_operation_resolver(package, run_dir)
    execution = _run_local_lifecycle_fresh_session(
        package_dir=package,
        run_dir=run_dir,
        model=trial.agent.model,
        adapter_kind=trial.agent.adapter,
        max_turns=trial.max_turns_per_session,
        adapter_builder=adapter_builder(package, run_dir),
        visibility_policy=trial.memory_visibility_policy,
        operation_resolver=resolver,
    )
    _record_completed_lifecycle_invocation(
        manifest=manifest,
        trial=trial,
        package=package,
        run_dir=run_dir,
        execution=execution,
        verifier=verify_lifecycle,
        plan_sha256=plan.plan_sha256,
    )
    return manifest, trial, package, run_dir


class _HydraulicSmokeRegistry:
    def __init__(self, package: Path, run_dir: Path) -> None:
        self.package = package
        self.run_dir = run_dir

    def build(self, **_kwargs: Any) -> Any:
        package = self.package
        run_dir = self.run_dir

        class _HydraulicSmokeAdapter:
            def execute(self, request: Any) -> Any:
                checkpoint_id = Path(request.output_path).stem
                state = _read_json(run_dir / "state.json")
                checkpoint = next(item for item in state["checkpoint_runs"] if item["checkpoint_id"] == checkpoint_id)
                session_id = checkpoint["attempts"][-1]["session_id"]
                write_hydraulic_review_smoke_submission(
                    package,
                    run_dir,
                    checkpoint_id,
                    session_id,
                    Path(request.output_path),
                )
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="deterministic-operation-probe",
                    configuration_record={"source": "registered_task_smoke"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=0,
                    usage_output_tokens=0,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _HydraulicSmokeAdapter()


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload
