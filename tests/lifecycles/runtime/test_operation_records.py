# ABOUTME: Tests lifecycle operation identity across episode metrics, manifests, and immutable snapshots.
# ABOUTME: Proves operation actions and transactions cannot disappear from recorded experiment evidence.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import aec_bench.lifecycles.finalization_evidence as finalization_evidence_runtime
import aec_bench.lifecycles.recording as experiment_runtime
import aec_bench.lifecycles.runtime.operation_store as operation_store_runtime
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.lifecycles.catalogue import (
    lifecycle_verifier,
    materialize_lifecycle,
)
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.invocation import (
    LifecycleExperimentMetrics,
    LifecycleExperimentRecordingResult,
    LifecycleExperimentTrialContext,
    lifecycle_experiment_metrics_payload,
)
from aec_bench.lifecycles.recording import (
    record_lifecycle_experiment,
)
from aec_bench.lifecycles.runtime.episode import (
    LifecycleExecutionMode,
    LifecycleOperationCurrentSource,
    LifecycleVisibilityPolicy,
)
from aec_bench.lifecycles.runtime.lifecycle import (
    execute_lifecycle_operation,
    load_evidence_lifecycle_spec,
    open_checkpoint_attempt,
    release_checkpoint,
    submit_checkpoint,
)
from aec_bench.lifecycles.runtime.operation_protocol import (
    lifecycle_operation_protocol_identity,
    validate_lifecycle_operation_tool_schema,
)
from aec_bench.lifecycles.runtime.operation_snapshot import validate_lifecycle_operation_snapshot
from aec_bench.lifecycles.runtime.request_protocol import EvidenceLifecycleError
from aec_bench.lifecycles.runtime.state import EvidenceLifecycleRunState
from aec_bench.lifecycles.values import LifecycleTrial
from aec_bench.trials import PlannedTrial
from tests.support.lifecycle_operations import resolve_operation_runtime

TEMPLATE_ID = "hydraulic-interaction-lifecycle-review"


def test_metrics_v2_projection_does_not_invent_v3_operation_fields() -> None:
    metrics = LifecycleExperimentMetrics(
        schema_version="2",
        checkpoint_count=1,
        requests=0,
        tool_calls=0,
        reads=0,
        revisits=0,
        retries=0,
        failures=0,
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )

    payload = lifecycle_experiment_metrics_payload(metrics)

    assert payload["schema_version"] == "2"
    assert not {
        "operation_calls",
        "completed_operations",
        "already_current_operations",
        "rejected_operations",
        "operation_budget_consumed",
        "operation_artifacts_produced",
    }.intersection(payload)


def test_operation_metrics_count_operation_outcomes_and_budget(tmp_path: Path) -> None:
    package, run_dir, completed = _operation_run(tmp_path)
    del package
    current_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    reused = execute_lifecycle_operation(
        tmp_path / "package",
        run_dir,
        operation_resolver=resolve_operation_runtime(tmp_path / "package", run_dir),
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
        reason="Reuse the current design hydrology.",
        session_id="baseline.session-001",
    )
    rejected = execute_lifecycle_operation(
        tmp_path / "package",
        run_dir,
        operation_resolver=resolve_operation_runtime(tmp_path / "package", run_dir),
        checkpoint_id="wrong-checkpoint",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
        reason="Exercise the typed inactive-checkpoint rejection.",
        session_id="baseline.session-001",
    )

    metrics = experiment_runtime._build_metrics(run_dir, _agent(), _verification())

    assert metrics.schema_version == "3"
    assert metrics.operation_calls == 3
    assert metrics.completed_operations == 1
    assert metrics.already_current_operations == 1
    assert metrics.rejected_operations == 1
    assert metrics.operation_budget_consumed == 1
    completed_artifacts = completed["artifacts"]
    assert isinstance(completed_artifacts, list)
    assert metrics.operation_artifacts_produced == len(completed_artifacts)
    assert reused["budget_consumed"] == 0
    assert rejected["budget_consumed"] == 0


def test_finalization_metrics_reject_coercive_operation_budget_and_timing(tmp_path: Path) -> None:
    package, run_dir, completed = _operation_run(tmp_path)
    recorded = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=_agent(),
        verifier=lifecycle_verifier(TEMPLATE_ID),
        verification=_verification(),
        tool_schema=_operation_tool_schema(),
        trial_context=_trial_context(package, run_dir),
        repository_dir=Path(__file__).resolve().parents[2],
    )
    trial = _trial(package, run_dir)
    evidence = finalization_evidence_runtime.validate_lifecycle_finalization_evidence(
        trial=trial,
        compiled_source=trial.compiled,
        run_dir=run_dir,
        recording=recorded,
    )
    action = next(
        action
        for checkpoint in evidence.state["checkpoint_runs"]
        for action in checkpoint["operation_actions"]
        if action["action_id"] == completed["action_id"]
    )
    action["budget_consumed"] = True

    with pytest.raises(ValueError, match="operation budget_consumed must be a non-negative integer"):
        finalization_evidence_runtime.validate_lifecycle_run_metrics(
            run_dir=run_dir,
            state=evidence.state,
            experiment=evidence.experiment,
            metrics=evidence.metrics,
            verification=evidence.verification,
        )

    action["budget_consumed"] = 1
    evidence.experiment["execution"]["whole_run_seconds"] = True
    evidence.metrics["whole_run_seconds"] = True
    with pytest.raises(ValueError, match="whole-run timing must be a finite non-negative number"):
        finalization_evidence_runtime.validate_lifecycle_run_metrics(
            run_dir=run_dir,
            state=evidence.state,
            experiment=evidence.experiment,
            metrics=evidence.metrics,
            verification=evidence.verification,
        )


def test_operation_protocol_and_transactions_are_manifest_bound(tmp_path: Path) -> None:
    package, run_dir, action = _operation_run(tmp_path)
    trial_context = _trial_context(package, run_dir)
    tool_schema = [
        {
            "name": "execute_operation",
            "description": "Execute one declared lifecycle operation.",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkpoint_id": {"type": "string"},
                    "operation_id": {"type": "string"},
                    "visible_source_state_sha256": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "checkpoint_id",
                    "operation_id",
                    "visible_source_state_sha256",
                    "reason",
                ],
            },
        }
    ]

    recorded = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=_agent(),
        verifier=lifecycle_verifier(TEMPLATE_ID),
        verification=_verification(),
        tool_schema=tool_schema,
        trial_context=trial_context,
        repository_dir=Path(__file__).resolve().parents[2],
    )
    manifest = _read_json(Path(str(recorded["manifest"])))

    assert manifest["schema_version"] == "2"
    assert manifest["trial"] == trial_context.model_dump(mode="json")
    encoded_schema = json.dumps(tool_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    interaction = manifest["interaction"]
    assert isinstance(interaction, dict)
    assert interaction["lifecycle_operation_protocol"] == {
        **lifecycle_operation_protocol_identity(),
        "tool_schema_sha256": hashlib.sha256(encoded_schema).hexdigest(),
    }
    action_id = str(action["action_id"])
    outputs = manifest["outputs"]
    assert isinstance(outputs, dict)
    declared = outputs["artifacts"]
    assert isinstance(declared, dict)
    assert f"lifecycle_operations/{action_id}/request.json" in declared
    assert f"lifecycle_operations/{action_id}/action.json" in declared
    assert f"lifecycle_operations/{action_id}/result-manifest.json" in declared
    assert f"lifecycle_operations/{action_id}/committed.json" in declared
    assert any(path.startswith(f"lifecycle_operations/{action_id}/artifacts/") for path in declared)
    assert any(f"/operations/{action_id}/" in path for path in declared)
    assert "workspace/checkpoints/baseline_analysis/operations.json" in declared
    assert "workspace/operations/current-source.json" in declared
    validate_lifecycle_operation_tool_schema(tool_schema)


def test_recording_rejects_malformed_operation_tool_before_publishing_identity(tmp_path: Path) -> None:
    package, run_dir, _action = _operation_run(tmp_path)
    malformed_schema = [
        {
            "name": "execute_operation",
            "signature": ("(checkpoint_id: 'str', operation_id: 'str', visible_source_state_sha256: 'str') -> 'str'"),
        }
    ]

    with pytest.raises(EvidenceLifecycleError, match="execute_operation tool schema"):
        record_lifecycle_experiment(
            package_dir=package,
            run_dir=run_dir,
            agent=_agent(),
            verifier=lifecycle_verifier(TEMPLATE_ID),
            verification=_verification(),
            tool_schema=malformed_schema,
            trial_context=_trial_context(package, run_dir),
            repository_dir=Path(__file__).resolve().parents[2],
        )

    assert not (run_dir / "experiment-manifest.json").exists()


def test_core_finalization_rejects_rehashed_malformed_operation_tool_schema(tmp_path: Path) -> None:
    package, run_dir, _action = _operation_run(tmp_path)
    valid_schema = [
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str') -> 'str'"
            ),
        }
    ]
    recorded = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=_agent(),
        verifier=lifecycle_verifier(TEMPLATE_ID),
        verification=_verification(),
        tool_schema=valid_schema,
        trial_context=_trial_context(package, run_dir),
        repository_dir=Path(__file__).resolve().parents[2],
    )
    manifest = _read_json(Path(str(recorded["manifest"])))
    malformed_schema = [
        {
            "name": "execute_operation",
            "signature": ("(checkpoint_id: 'str', operation_id: 'str', visible_source_state_sha256: 'str') -> 'str'"),
        }
    ]
    encoded = json.dumps(malformed_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
    interaction = manifest["interaction"]
    assert isinstance(interaction, dict)
    interaction["tool_schema"] = malformed_schema
    protocol = interaction["lifecycle_operation_protocol"]
    assert isinstance(protocol, dict)
    protocol["tool_schema_sha256"] = hashlib.sha256(encoded).hexdigest()

    _rewrite_recorded_manifest(recorded, manifest)

    with pytest.raises(ValueError, match="operation tool schema does not match the public contract"):
        _validate_finalization(package, run_dir, recorded)


@pytest.mark.parametrize("forgery", ["semantic_schema", "protocol_tool"])
def test_core_finalization_rejects_rehashed_operation_protocol_forgeries(
    tmp_path: Path,
    forgery: str,
) -> None:
    package, run_dir, _action = _operation_run(tmp_path)
    valid_schema = [
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str') -> 'str'"
            ),
        }
    ]
    recorded = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=_agent(),
        verifier=lifecycle_verifier(TEMPLATE_ID),
        verification=_verification(),
        tool_schema=valid_schema,
        trial_context=_trial_context(package, run_dir),
        repository_dir=Path(__file__).resolve().parents[2],
    )
    manifest = _read_json(Path(str(recorded["manifest"])))
    interaction = manifest["interaction"]
    assert isinstance(interaction, dict)
    protocol = interaction["lifecycle_operation_protocol"]
    assert isinstance(protocol, dict)
    if forgery == "semantic_schema":
        forged_schema = [
            {
                "name": "execute_operation",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "checkpoint_id": {"type": "string"},
                        "operation_id": {"type": "string"},
                        "visible_source_state_sha256": {"type": "string"},
                        "reason": {"type": "string", "enum": []},
                    },
                    "required": [
                        "checkpoint_id",
                        "operation_id",
                        "visible_source_state_sha256",
                        "reason",
                    ],
                },
            }
        ]
        encoded = json.dumps(forged_schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
        interaction["tool_schema"] = forged_schema
        protocol["tool_schema_sha256"] = hashlib.sha256(encoded).hexdigest()
    else:
        protocol["tool"] = {
            "name": "execute_operation",
            "arguments": ["checkpoint_id", "operation_id", "visible_source_state_sha256"],
        }

    _rewrite_recorded_manifest(recorded, manifest)

    expected = (
        "operation tool schema does not match the public contract"
        if forgery == "semantic_schema"
        else "operation protocol does not match the public tool contract"
    )
    with pytest.raises(ValueError, match=expected):
        _validate_finalization(package, run_dir, recorded)


def test_snapshotted_operation_state_rejects_tampered_operation_request(tmp_path: Path) -> None:
    package, run_dir, action = _operation_run(tmp_path)
    _record_and_validate(package, run_dir)
    request_path = run_dir / "lifecycle_operations" / str(action["action_id"]) / "request.json"
    request = _read_json(request_path)
    request["reason"] = "tampered after the operation committed"
    request_path.write_text(json.dumps(request, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(EvidenceLifecycleError, match="operation request does not match its action"):
        _record_and_validate(package, run_dir)


def test_completed_operation_snapshot_preserves_each_checkpoint_source_identity(tmp_path: Path) -> None:
    package, run_dir, baseline_action = _operation_run(tmp_path)
    baseline_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    _write_submission(
        run_dir,
        "baseline_analysis",
        {
            "checkpoint_id": "baseline_analysis",
            "visible_source_state_sha256": baseline_source["visible_source_state_sha256"],
            "selected_operations": {"hydrology.design-10yr": baseline_action["action_id"]},
            "accepted_decisions": {},
            "readiness_decision": "baseline_complete",
            "claim_boundary": {},
        },
    )
    submit_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    release_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    open_checkpoint_attempt(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        session_id="revision.session-001",
        execution_mode="persistent_context",
    )
    revision_action = execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        visible_source_state_sha256=str(baseline_source["visible_source_state_sha256"]),
        reason="Activate the declared tailwater revision.",
        session_id="revision.session-001",
    )
    revision_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    retained_hydrology = execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="revision_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=str(revision_source["visible_source_state_sha256"]),
        reason="Retain hydrology that remains current after revision.",
        session_id="revision.session-001",
    )
    _write_submission(
        run_dir,
        "revision_analysis",
        {
            "checkpoint_id": "revision_analysis",
            "revision_id": "tailwater_revision",
            "visible_source_state_sha256": revision_source["visible_source_state_sha256"],
            "selected_operations": {
                "source-revision.current": revision_action["action_id"],
                "hydrology.design-10yr": retained_hydrology["action_id"],
            },
            "accepted_decisions": {},
            "supersession_lineage": {},
            "readiness_decision": "revision_complete",
            "claim_boundary": {},
        },
    )
    submit_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    release_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    open_checkpoint_attempt(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        session_id="closeout.session-001",
        execution_mode="persistent_context",
    )
    _write_submission(
        run_dir,
        "closeout_review",
        {
            "checkpoint_id": "closeout_review",
            "visible_source_state_sha256": revision_source["visible_source_state_sha256"],
            "selected_operations": {},
            "run_reference": {},
            "report_reference": {},
            "memo": {},
            "accepted_decisions": {},
            "supersession_lineage": {},
            "readiness_decision": "not_screening_ready",
            "claim_boundary": {},
        },
    )
    submit_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))

    _record_and_validate(package, run_dir)
    baseline_catalog = _read_json(run_dir / "workspace" / "checkpoints" / "baseline_analysis" / "operations.json")
    revision_catalog = _read_json(run_dir / "workspace" / "checkpoints" / "revision_analysis" / "operations.json")
    assert baseline_catalog["visible_source_state_sha256"] == baseline_source["visible_source_state_sha256"]
    assert revision_catalog["visible_source_state_sha256"] == revision_source["visible_source_state_sha256"]
    assert baseline_catalog["visible_source_state_sha256"] != revision_catalog["visible_source_state_sha256"]


def test_snapshotted_operation_state_rejects_current_source_from_a_different_package(tmp_path: Path) -> None:
    package, run_dir, baseline_action = _operation_run(tmp_path)
    baseline_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    _write_submission(
        run_dir,
        "baseline_analysis",
        {
            "checkpoint_id": "baseline_analysis",
            "visible_source_state_sha256": baseline_source["visible_source_state_sha256"],
            "selected_operations": {"hydrology.design-10yr": baseline_action["action_id"]},
            "accepted_decisions": {},
            "readiness_decision": "baseline_complete",
            "claim_boundary": {},
        },
    )
    submit_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    release_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    open_checkpoint_attempt(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        session_id="revision.session-001",
        execution_mode="persistent_context",
    )
    execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="revision_analysis",
        operation_id="source-revision.current",
        visible_source_state_sha256=str(baseline_source["visible_source_state_sha256"]),
        reason="Activate the declared tailwater revision.",
        session_id="revision.session-001",
    )
    different_package = materialize_lifecycle(
        TEMPLATE_ID,
        tmp_path / "different-package",
        variant_id="major_idf_revision",
    )

    with pytest.raises(
        (ValueError, EvidenceLifecycleError),
        match="live resolver (plan|replay)|expected packaged source",
    ):
        _validate_core_operation_state(different_package, run_dir)


def test_snapshotted_operation_state_runs_exact_live_resolver_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package, run_dir, _action = _operation_run(tmp_path)

    def reject_replay(*_args: object, **_kwargs: object) -> None:
        raise EvidenceLifecycleError("live resolver replay sentinel")

    monkeypatch.setattr(
        finalization_evidence_runtime,
        "validate_lifecycle_operation_resolver_replay",
        reject_replay,
    )

    with pytest.raises(EvidenceLifecycleError, match="live resolver replay sentinel"):
        _record_and_validate(package, run_dir)


def test_operation_snapshot_recomputes_rejected_operation_projection(tmp_path: Path) -> None:
    package, run_dir, _completed = _operation_run(tmp_path)
    current_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    rejected = execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="wrong-checkpoint",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
        reason="Record a typed inactive-checkpoint rejection.",
        session_id="baseline.session-001",
    )
    _replace_action_field(run_dir, str(rejected["action_id"]), "input_projection_sha256", "f" * 64)

    with pytest.raises(EvidenceLifecycleError, match="rejected operation projection does not match its request"):
        _record_and_validate(package, run_dir)


def test_operation_snapshot_resolves_reuse_to_exact_prior_completed_action(tmp_path: Path) -> None:
    package, run_dir, hydrology = _operation_run(tmp_path)
    current_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    detention = execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="baseline_analysis",
        operation_id="detention-outlet.design-10yr.declared-outlet",
        visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
        reason="Compute detention evidence for a distinct retained candidate.",
        session_id="baseline.session-001",
    )
    reused = execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
        reason="Reuse the current hydrology result.",
        session_id="baseline.session-001",
    )
    assert reused["retained_from_action_id"] == hydrology["action_id"]
    forged_fields = {
        "retained_from_action_id": detention["action_id"],
        "input_projection_sha256": detention["input_projection_sha256"],
        "prerequisite_action_ids": detention["prerequisite_action_ids"],
        "artifacts": detention["artifacts"],
    }
    _replace_action_fields(run_dir, str(reused["action_id"]), forged_fields)

    with pytest.raises(EvidenceLifecycleError, match="reused operation does not match its retained completed action"):
        _record_and_validate(package, run_dir)


def _record_and_validate(package: Path, run_dir: Path) -> None:
    recorded = record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=_agent(),
        verifier=lifecycle_verifier(TEMPLATE_ID),
        verification=_verification(),
        tool_schema=_operation_tool_schema(),
        trial_context=_trial_context(package, run_dir),
        repository_dir=Path(__file__).resolve().parents[2],
    )
    _validate_finalization(package, run_dir, recorded)


def _validate_finalization(
    package: Path,
    run_dir: Path,
    recorded: LifecycleExperimentRecordingResult,
) -> None:
    trial = _trial(package, run_dir)
    evidence = finalization_evidence_runtime.validate_lifecycle_finalization_evidence(
        trial=trial,
        compiled_source=trial.compiled,
        run_dir=run_dir,
        recording=recorded,
    )
    finalization_evidence_runtime.validate_lifecycle_run_metrics(
        run_dir=run_dir,
        state=evidence.state,
        experiment=evidence.experiment,
        metrics=evidence.metrics,
        verification=evidence.verification,
    )


def _rewrite_recorded_manifest(
    recorded: LifecycleExperimentRecordingResult,
    manifest: dict[str, object],
) -> None:
    run_manifest = Path(recorded["manifest"])
    canonical_manifest = Path(recorded["canonical_manifest"])
    _write_json_object(run_manifest, manifest)
    _write_json_object(canonical_manifest, manifest)
    digest = hashlib.sha256(canonical_manifest.read_bytes()).hexdigest()
    recorded["manifest_sha256"] = digest

    seal_path = canonical_manifest.with_name("index-entry.json")
    seal = _read_json(seal_path)
    seal["manifest_sha256"] = digest
    _write_json_object(seal_path, seal)

    index_path = Path(recorded["index"])
    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    matched = False
    for entry in entries:
        if entry.get("experiment_id") == recorded["experiment_id"]:
            entry["manifest_sha256"] = digest
            matched = True
    assert matched
    index_path.write_text(
        "".join(f"{json.dumps(entry, sort_keys=True)}\n" for entry in entries),
        encoding="utf-8",
    )


def _validate_core_operation_state(package: Path, run_dir: Path) -> None:
    state = EvidenceLifecycleRunState.model_validate(_read_json(run_dir / "state.json"))
    spec = load_evidence_lifecycle_spec(package)
    resolver = resolve_operation_runtime(package, run_dir)
    operation_store_runtime.validate_lifecycle_operation_resolver_replay(run_dir, state, spec, resolver)
    current = operation_store_runtime.resolve_lifecycle_operation_current_source(state, resolver)
    validate_lifecycle_operation_snapshot(
        run_dir,
        state,
        spec,
        expected_current_source=LifecycleOperationCurrentSource(
            revision_id=current.revision_id,
            physical_source_state_sha256=current.physical_source_state_sha256,
            visible_source_state_sha256=current.visible_source_state_sha256,
            source_state=current.source_state,
        ),
    )


def _operation_tool_schema() -> list[dict[str, str]]:
    return [
        {
            "name": "execute_operation",
            "signature": (
                "(checkpoint_id: 'str', operation_id: 'str', "
                "visible_source_state_sha256: 'str', reason: 'str') -> 'str'"
            ),
        }
    ]


def _operation_run(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    package = materialize_lifecycle(
        TEMPLATE_ID,
        tmp_path / "package",
        variant_id="tailwater_revision",
    )
    run_dir = tmp_path / "run"
    release_checkpoint(package, run_dir, operation_resolver=resolve_operation_runtime(package, run_dir))
    open_checkpoint_attempt(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        session_id="baseline.session-001",
        execution_mode="persistent_context",
    )
    current_source = _read_json(run_dir / "workspace" / "operations" / "current-source.json")
    action = execute_lifecycle_operation(
        package,
        run_dir,
        operation_resolver=resolve_operation_runtime(package, run_dir),
        checkpoint_id="baseline_analysis",
        operation_id="hydrology.design-10yr",
        visible_source_state_sha256=str(current_source["visible_source_state_sha256"]),
        reason="Compute the declared design hydrology.",
        session_id="baseline.session-001",
    )
    return package, run_dir, action


def _write_submission(run_dir: Path, checkpoint_id: str, payload: dict[str, object]) -> None:
    path = run_dir / "workspace" / "submissions" / f"{checkpoint_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _replace_action_field(run_dir: Path, action_id: str, field_name: str, value: object) -> None:
    _replace_action_fields(run_dir, action_id, {field_name: value})


def _replace_action_fields(run_dir: Path, action_id: str, updates: dict[str, object]) -> None:
    state_path = run_dir / "state.json"
    state = _read_json(state_path)
    checkpoint_runs = state["checkpoint_runs"]
    assert isinstance(checkpoint_runs, list)
    matched = False
    for checkpoint in checkpoint_runs:
        assert isinstance(checkpoint, dict)
        actions = checkpoint["operation_actions"]
        assert isinstance(actions, list)
        for action in actions:
            assert isinstance(action, dict)
            if action["action_id"] == action_id:
                action.update(updates)
                matched = True
    assert matched
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    action_path = run_dir / "lifecycle_operations" / action_id / "action.json"
    action = _read_json(action_path)
    action.update(updates)
    action_path.write_text(json.dumps(action, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _trial(package: Path, run_dir: Path) -> LifecycleTrial:
    compiled = load_compiled_lifecycle(package)
    return LifecycleTrial(
        planned=PlannedTrial(
            trial_id=f"trial-{run_dir.name}",
            experiment_id="operation-recording-tests",
            task_id=compiled.envelope.template_id,
            agent=AgentConfig(
                name="operation-recording-test-agent",
                adapter="in_process",
                model="gold",
                parameters={"max_turns_per_session": 20},
            ),
            compute=ComputeConfig(backend="local"),
            repetition=1,
        ),
        compiled=compiled,
        run_dir=run_dir,
        execution_mode=LifecycleExecutionMode.PERSISTENT_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.PERSISTENT_CONTEXT,
    )


def _trial_context(package: Path, run_dir: Path) -> LifecycleExperimentTrialContext:
    trial = _trial(package, run_dir)
    return LifecycleExperimentTrialContext(
        trial_id=trial.planned.trial_id,
        planned_experiment_id=trial.planned.experiment_id,
        task_id=trial.planned.task_id,
        repetition=trial.planned.repetition,
        run_id=trial.planned.trial_id,
        compiled=trial.compiled.envelope,
    )


def _agent() -> dict[str, object]:
    return {
        "adapter": "in_process",
        "model": "gold",
        "execution_mode": "persistent_context",
        "memory_visibility_policy": "persistent_context",
        "max_turns_per_session": 20,
        "status": "failed",
        "sessions": [],
        "resolved_adapters": [],
        "totals": {
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        },
    }


def _verification() -> dict[str, object]:
    return {
        "lifecycle_id": "hydraulic-interaction-review",
        "overall": "incomplete",
        "passed": False,
        "reward": 0.0,
        "gates": {
            "lifecycle_runtime": {
                "passed": False,
                "score": 0.0,
                "failures": ["incomplete"],
            }
        },
    }


def _read_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _write_json_object(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
