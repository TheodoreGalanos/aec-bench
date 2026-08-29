# ABOUTME: Tests canonical lifecycle finalization, retained evidence, and exact run identity.
# ABOUTME: Proves core trials finalize once and remain valid after live execution files disappear.

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.lifecycle_local import run_local_lifecycle
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import write_trial_record
from aec_bench.lifecycles.application import (
    LifecycleExecution,
    LifecycleTrial,
    run_lifecycle_experiment,
    run_lifecycle_trial,
)
from aec_bench.lifecycles.catalogue import verify_lifecycle
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.finalization import LifecycleFinalizationSource, finalize_lifecycle_trial
from aec_bench.lifecycles.invocation import (
    LifecycleCallableProvenanceIdentity,
    LifecycleExperimentRecordingResult,
    LifecycleExperimentSweepContext,
    LifecycleInvocationPlanExpectation,
    LifecycleRepositoryProvenanceIdentity,
    LifecycleRuntimeProvenance,
    LifecycleVerifierProvenanceExpectation,
)
from aec_bench.lifecycles.provenance import callable_provenance
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.trials import PlannedTrial

_MISSING = object()


class _GoldAdapterBuilder:
    def __init__(
        self,
        package_dir: Path,
        *,
        resolved_models: tuple[str, ...] = (),
        resolved_adapters: tuple[str, ...] = (),
    ) -> None:
        self._submissions = json.loads((package_dir / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        self._resolved_models = iter(resolved_models)
        self._resolved_adapters = iter(resolved_adapters)

    def __call__(self, **_kwargs: Any) -> Any:
        submissions = self._submissions
        trajectory_writer = _kwargs["trajectory_writer"]
        trajectory_writer.system("Core finalization test adapter.")
        resolved_model = next(self._resolved_models, "test-model")
        resolved_adapter = next(self._resolved_adapters, "tool_loop")

        class _Adapter:
            def execute(self, request: Any) -> Any:
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(submissions[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name=resolved_adapter,
                    resolved_model=resolved_model,
                    configuration_record={"model": "test-model", "max_turns": 5},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[
                        SimpleNamespace(
                            role="assistant",
                            event="message",
                            content="Submitted the declared gold checkpoint.",
                            tool_name=None,
                            tool_call_id=None,
                        )
                    ],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=2,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


def _trial(
    tmp_path: Path,
    trial_id: str,
    *,
    template_id: str = "drainage-model-evidence-lifecycle-review",
    variant_id: str | None = "staged_full_correction",
    parameters: dict[str, object] | None = None,
    sweep_context: LifecycleExperimentSweepContext | None = None,
) -> LifecycleTrial:
    compiled = compile_lifecycle(
        template_id,
        tmp_path / f"package-{trial_id}",
        variant_id=variant_id,
    )
    return LifecycleTrial(
        planned=PlannedTrial(
            trial_id=trial_id,
            experiment_id="core-finalization-tests",
            task_id=template_id,
            agent=AgentConfig(
                name="test-agent",
                adapter="tool_loop",
                model="test-model",
                parameters={"max_turns": 5} if parameters is None else parameters,
            ),
            compute=ComputeConfig(backend="local"),
            repetition=1,
        ),
        compiled=compiled,
        run_dir=tmp_path / f"run-{trial_id}",
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        sweep_context=sweep_context,
    )


def _execute(trial: LifecycleTrial) -> LifecycleExecution:
    return run_local_lifecycle(trial=trial, adapter_builder=_GoldAdapterBuilder(trial.package_dir))


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(dict[str, Any], payload)


def _write_json_object(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan_expectation_from_recording_fixture(
    recording: LifecycleExperimentRecordingResult,
) -> LifecycleInvocationPlanExpectation:
    manifest = _read_json_object(Path(recording["canonical_manifest"]))
    repository = cast(dict[str, Any], manifest["repository"])
    environment = cast(dict[str, Any], manifest["environment"])
    runtime = cast(dict[str, Any], environment["runtime_provenance"])
    verifier = cast(dict[str, Any], manifest["verifier"])
    entrypoint = cast(dict[str, Any], verifier["entrypoint"])
    return LifecycleInvocationPlanExpectation(
        repository=LifecycleRepositoryProvenanceIdentity(
            commit=cast(str, repository["commit"]),
            source_inventory_sha256=cast(str, repository["source_inventory_sha256"]),
        ),
        runtime=LifecycleRuntimeProvenance.model_validate(runtime),
        verifier=LifecycleVerifierProvenanceExpectation(
            registered=LifecycleCallableProvenanceIdentity(
                qualified_name=cast(str, verifier["qualified_name"]),
                source_sha256=cast(str, verifier["source_sha256"]),
            ),
            entrypoint=LifecycleCallableProvenanceIdentity(
                qualified_name=cast(str, entrypoint["qualified_name"]),
                source_sha256=cast(str, entrypoint["source_sha256"]),
            ),
        ),
    )


def _source_with_manifest_mutation(
    trial: LifecycleTrial,
    recording: LifecycleExperimentRecordingResult,
    *,
    mutate: Callable[[dict[str, Any]], None],
    index_updates: Mapping[str, Any] | None = None,
) -> LifecycleFinalizationSource:
    manifest_path = Path(recording["canonical_manifest"])
    manifest = _read_json_object(manifest_path)
    mutate(manifest)
    _write_json_object(manifest_path, manifest)
    _write_json_object(Path(recording["manifest"]), manifest)
    manifest_sha256 = _file_sha256(manifest_path)
    revised_recording = recording.copy()
    revised_recording["manifest_sha256"] = manifest_sha256

    seal_path = manifest_path.with_name("index-entry.json")
    seal = _read_json_object(seal_path)
    seal["manifest_sha256"] = manifest_sha256
    seal.update(index_updates or {})
    _write_json_object(seal_path, seal)

    index_path = Path(recording["index"])
    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for entry in entries:
        if entry.get("experiment_id") == recording["experiment_id"]:
            entry["manifest_sha256"] = manifest_sha256
            entry.update(index_updates or {})
    index_path.write_text(
        "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries),
        encoding="utf-8",
    )
    return LifecycleFinalizationSource(
        compiled=trial.compiled,
        run_dir=trial.run_dir,
        recording=revised_recording,
    )


def _source_with_metrics_mutation(
    trial: LifecycleTrial,
    recording: LifecycleExperimentRecordingResult,
    *,
    mutate: Callable[[dict[str, Any]], None],
    mutate_manifest: Callable[[dict[str, Any]], None] | None = None,
) -> LifecycleFinalizationSource:
    manifest_path = Path(recording["canonical_manifest"])
    canonical_metrics_path = manifest_path.with_name("metrics.json")
    metrics = _read_json_object(canonical_metrics_path)
    mutate(metrics)
    _write_json_object(canonical_metrics_path, metrics)
    _write_json_object(Path(recording["metrics"]), metrics)
    metrics_sha256 = _file_sha256(canonical_metrics_path)

    def bind_metrics_hash(manifest: dict[str, Any]) -> None:
        outputs = cast(dict[str, Any], manifest["outputs"])
        outputs["metrics.json"] = metrics_sha256
        cast(dict[str, Any], outputs["artifacts"])["metrics.json"] = metrics_sha256
        if mutate_manifest is not None:
            mutate_manifest(manifest)

    return _source_with_manifest_mutation(trial, recording, mutate=bind_metrics_hash)


def test_non_variant_lifecycle_finalizes_with_exact_compiled_provenance(tmp_path: Path) -> None:
    trial = _trial(
        tmp_path,
        "facade-trial",
        template_id="facade-submittal-review-lifecycle",
        variant_id=None,
        parameters={},
    )

    record = run_lifecycle_trial(trial=trial, execute=_execute, verify=verify_lifecycle)

    provenance = record.lifecycle_provenance
    execution = record.lifecycle_execution
    assert provenance is not None
    assert execution is not None
    assert record.run_id == record.trial_id == "facade-trial"
    assert record.run_manifest.run_id == "facade-trial"
    assert provenance.lifecycle_id == trial.compiled.envelope.lifecycle_id
    assert provenance.executable_artifact_sha256 == trial.compiled.envelope.executable_artifact_sha256
    assert provenance.operation_protocol_sha256 is None
    assert provenance.variant_id is None
    assert record.adaptation is None
    assert execution.max_turns_per_session == 20


def test_package_drift_is_rejected_before_executor_call(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "package-drift")
    instruction = next((trial.package_dir / "instructions").glob("*.md"))
    instruction.write_text(instruction.read_text(encoding="utf-8") + "\nDrifted after compilation.\n", encoding="utf-8")
    executor_called = False

    def execute(_trial: LifecycleTrial) -> LifecycleExecution:
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor must not run for a drifted package")

    with pytest.raises(ValueError, match="compiled lifecycle identity does not match package bytes"):
        run_lifecycle_trial(trial=trial, execute=execute, verify=verify_lifecycle)

    assert not executor_called
    assert not trial.run_dir.exists()


def test_invalid_turn_limit_is_rejected_before_executor_call(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "invalid-turn-limit", parameters={"max_turns": "5"})
    executor_called = False

    def execute(_trial: LifecycleTrial) -> LifecycleExecution:
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor must not run for an invalid turn limit")

    with pytest.raises(ValueError, match="lifecycle agent max_turns_per_session must be a positive integer"):
        run_lifecycle_trial(trial=trial, execute=execute, verify=verify_lifecycle)

    assert not executor_called
    assert not trial.run_dir.exists()


def test_finalization_rejects_recording_manifest_hash_mismatch(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "manifest-mismatch")
    persisted: list[TrialRecord] = []

    def retain_with_bad_hash(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        corrupted = recording.copy()
        corrupted["manifest_sha256"] = "0" * 64
        return LifecycleFinalizationSource(
            compiled=selected_trial.compiled,
            run_dir=selected_trial.run_dir,
            recording=corrupted,
        )

    with pytest.raises(ValueError, match="canonical lifecycle manifest hash does not match the recording result"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_bad_hash,
            persist=persisted.append,
        )

    assert persisted == []


def test_finalization_rejects_tampered_run_metrics(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "tampered-metrics")

    def retain_with_tampered_metrics(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        metrics_path = Path(recording["metrics"])
        metrics = _read_json_object(metrics_path)
        metrics["reads"] = 999
        _write_json_object(metrics_path, metrics)
        return LifecycleFinalizationSource(
            compiled=selected_trial.compiled,
            run_dir=selected_trial.run_dir,
            recording=recording,
        )

    with pytest.raises(ValueError, match="run metrics hash does not match the canonical manifest"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_tampered_metrics,
        )


def test_finalization_rejects_self_consistent_forged_token_totals(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-token-totals")

    def retain_with_forged_tokens(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def forge_input_tokens(metrics: dict[str, Any]) -> None:
            metrics["input_tokens"] = 999

        return _source_with_metrics_mutation(selected_trial, recording, mutate=forge_input_tokens)

    with pytest.raises(ValueError, match="lifecycle input_tokens does not match session artifacts"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_tokens,
        )


def test_finalization_rejects_recorded_visibility_outside_planned_condition(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-visibility")
    forged_visibility = LifecycleVisibilityPolicy.RAW_EVIDENCE_ONLY.value

    def retain_with_forged_visibility(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def forge_visibility(manifest: dict[str, Any]) -> None:
            cast(dict[str, Any], manifest["execution"])["memory_visibility_policy"] = forged_visibility

        return _source_with_manifest_mutation(
            selected_trial,
            recording,
            mutate=forge_visibility,
            index_updates={"memory_visibility_policy": forged_visibility},
        )

    with pytest.raises(ValueError, match="lifecycle run visibility policy does not match the planned trial"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_visibility,
        )


def test_finalization_rejects_canonical_turn_limit_outside_plan(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-turn-limit")

    def retain_with_forged_turn_limit(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def forge_turn_limit(manifest: dict[str, Any]) -> None:
            cast(dict[str, Any], manifest["execution"])["max_turns_per_session"] = 999

        return _source_with_manifest_mutation(selected_trial, recording, mutate=forge_turn_limit)

    with pytest.raises(ValueError, match="lifecycle run turn limit does not match the planned trial"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_turn_limit,
        )


def test_finalization_rejects_sweep_context_mismatch(tmp_path: Path) -> None:
    sweep = LifecycleExperimentSweepContext(
        sweep_experiment_id="core-finalization-tests",
        planned_trial_id="forged-sweep",
        plan_sha256="a" * 64,
        condition_id="fresh_context__artifact_memory",
        repetition=1,
    )
    trial = _trial(tmp_path, "forged-sweep", sweep_context=sweep)
    forged_sweep = sweep.model_copy(update={"condition_id": "fresh_context__raw_evidence_only"}).model_dump(mode="json")

    def retain_with_forged_sweep(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def forge_sweep(manifest: dict[str, Any]) -> None:
            manifest["sweep"] = forged_sweep

        return _source_with_manifest_mutation(
            selected_trial,
            recording,
            mutate=forge_sweep,
            index_updates={"sweep": forged_sweep},
        )

    with pytest.raises(ValueError, match="canonical lifecycle invocation sweep does not match the planned trial"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_sweep,
        )


def test_recorded_metrics_omit_absent_semantic_transition_but_keep_nullable_fields(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "nullable-metrics")

    def verify_without_semantic_transition(package: Path, run_dir: Path) -> dict[str, object]:
        verification = verify_lifecycle(package, run_dir)
        verification.pop("semantic_metrics", None)
        return cast(dict[str, object], verification)

    run_lifecycle_trial(
        trial=trial,
        execute=_execute,
        verify=verify_without_semantic_transition,
    )
    metrics = _read_json_object(trial.run_dir / "metrics.json")

    assert set(metrics) == {
        "accepted_evidence_requests",
        "already_current_operations",
        "already_released_evidence_requests",
        "cache_read_tokens",
        "cache_write_tokens",
        "checkpoint_count",
        "checkpoint_seconds",
        "completed_operations",
        "estimated_cost_usd",
        "evidence_request_artifacts_released",
        "evidence_request_budget_consumed",
        "evidence_request_calls",
        "failures",
        "input_tokens",
        "operation_artifacts_produced",
        "operation_budget_consumed",
        "operation_calls",
        "output_tokens",
        "reads",
        "rejected_evidence_requests",
        "rejected_operations",
        "requests",
        "retries",
        "revisits",
        "schema_version",
        "tool_calls",
        "whole_run_seconds",
    }
    assert metrics["estimated_cost_usd"] is None
    assert "whole_run_seconds" in metrics


def test_finalization_rejects_self_consistent_wrong_index_fields(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "wrong-index-model")

    def retain_with_wrong_index(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        seal_path = Path(recording["canonical_manifest"]).with_name("index-entry.json")
        seal = json.loads(seal_path.read_text(encoding="utf-8"))
        seal["model"] = "wrong-model"
        seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        index_path = Path(recording["index"])
        entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        for entry in entries:
            if entry["experiment_id"] == recording["experiment_id"]:
                entry["model"] = "wrong-model"
        index_path.write_text(
            "".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries),
            encoding="utf-8",
        )
        return LifecycleFinalizationSource(
            compiled=selected_trial.compiled,
            run_dir=selected_trial.run_dir,
            recording=recording,
        )

    with pytest.raises(ValueError, match="canonical lifecycle invocation model does not match its index entry"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_wrong_index,
        )


def test_finalization_rejects_external_run_artifact_symlink(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "external-symlink")

    def retain_with_symlink(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        metrics_path = Path(recording["metrics"])
        external_path = tmp_path / "external-metrics.json"
        external_path.write_bytes(metrics_path.read_bytes())
        metrics_path.unlink()
        metrics_path.symlink_to(external_path)
        return LifecycleFinalizationSource(
            compiled=selected_trial.compiled,
            run_dir=selected_trial.run_dir,
            recording=recording,
        )

    with pytest.raises(ValueError, match="run metrics is not a contained regular file"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_symlink,
        )


def test_recording_omits_external_symlink_artifact(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "recording-symlink")

    def execute_with_symlink(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = _execute(selected_trial)
        external = tmp_path / "external-result.json"
        external.write_text('{"external": true}\n', encoding="utf-8")
        (selected_trial.run_dir / "result.json").symlink_to(external)
        return execution

    record = run_lifecycle_trial(trial=trial, execute=execute_with_symlink, verify=verify_lifecycle)

    assert all(logical_path != "run/result.json" for _path, _media, logical_path in record.pending_artifacts.values())


def test_finalization_rejects_multiple_resolved_model_identities(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "mixed-models")

    def execute_with_mixed_models(selected_trial: LifecycleTrial) -> LifecycleExecution:
        return run_local_lifecycle(
            trial=selected_trial,
            adapter_builder=_GoldAdapterBuilder(
                selected_trial.package_dir,
                resolved_models=("resolved-model-a", "resolved-model-b", "resolved-model-b"),
            ),
        )

    with pytest.raises(ValueError, match="lifecycle sessions contain multiple resolved model identities"):
        run_lifecycle_trial(
            trial=trial,
            execute=execute_with_mixed_models,
            verify=verify_lifecycle,
        )

    assert not (trial.run_dir / "verification.json").exists()
    assert not (trial.run_dir / "metrics.json").exists()
    assert not (trial.run_dir / "experiment-manifest.json").exists()
    assert not (trial.run_dir / "experiments").exists()
    assert not (trial.run_dir.parent / "experiment-index.jsonl").exists()


@pytest.mark.parametrize("raw_status", ["forged", "ok"])
def test_current_finalization_rejects_unknown_raw_session_status(tmp_path: Path, raw_status: str) -> None:
    trial = _trial(tmp_path, "forged-session-status")

    def execute_with_forged_status(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = _execute(selected_trial)
        result_path = next(selected_trial.run_dir.rglob("agent_result.json"))
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["status"] = raw_status
        result["failure_kind"] = "agent_failed"
        result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        execution.agent["status"] = "failed"
        return execution

    with pytest.raises(ValueError, match="lifecycle session status is invalid"):
        run_lifecycle_trial(
            trial=trial,
            execute=execute_with_forged_status,
            verify=verify_lifecycle,
        )


@pytest.mark.parametrize("raw_value", [_MISSING, ""])
def test_current_finalization_rejects_missing_or_blank_resolved_model(tmp_path: Path, raw_value: object) -> None:
    trial = _trial(tmp_path, "invalid-resolved-model")

    def execute_with_invalid_resolved_model(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = _execute(selected_trial)
        result_path = next(selected_trial.run_dir.rglob("agent_result.json"))
        result = _read_json_object(result_path)
        if raw_value is _MISSING:
            result.pop("resolved_model")
        else:
            result["resolved_model"] = raw_value
        _write_json_object(result_path, result)
        return execution

    with pytest.raises(ValueError, match="lifecycle session resolved model is invalid"):
        run_lifecycle_trial(
            trial=trial,
            execute=execute_with_invalid_resolved_model,
            verify=verify_lifecycle,
        )


@pytest.mark.parametrize(
    ("field", "raw_value", "message"),
    [
        ("resolved_model", _MISSING, "lifecycle recording session resolved model is invalid"),
        ("resolved_model", "", "lifecycle recording session resolved model is invalid"),
        ("resolved_model", 7, "lifecycle recording session resolved model is invalid"),
        ("adapter_name", _MISSING, "lifecycle recording session resolved adapter is invalid"),
        ("adapter_name", "", "lifecycle recording session resolved adapter is invalid"),
        ("adapter_name", 7, "lifecycle recording session resolved adapter is invalid"),
    ],
)
def test_recording_rejects_invalid_session_identity_before_publication(
    tmp_path: Path,
    field: str,
    raw_value: object,
    message: str,
) -> None:
    trial = _trial(tmp_path, f"invalid-recording-{field}")

    def execute_with_invalid_recording_identity(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = _execute(selected_trial)
        sessions = cast(list[dict[str, Any]], execution.agent["sessions"])
        if raw_value is _MISSING:
            sessions[0].pop(field)
        else:
            sessions[0][field] = raw_value
        return execution

    with pytest.raises(ValueError, match=message):
        run_lifecycle_trial(
            trial=trial,
            execute=execute_with_invalid_recording_identity,
            verify=verify_lifecycle,
        )

    assert not (trial.run_dir / "verification.json").exists()
    assert not (trial.run_dir / "metrics.json").exists()
    assert not (trial.run_dir / "experiment-manifest.json").exists()
    assert not (trial.run_dir / "experiments").exists()
    assert not (trial.run_dir.parent / "experiment-index.jsonl").exists()


@pytest.mark.parametrize(
    ("field", "raw_value"),
    [
        ("requested_adapter", _MISSING),
        ("adapter", "other_adapter"),
    ],
)
def test_finalization_requires_both_recorded_adapter_identities_to_match_plan(
    tmp_path: Path,
    field: str,
    raw_value: object,
) -> None:
    trial = _trial(tmp_path, f"invalid-manifest-{field}")

    def retain_with_invalid_adapter_identity(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_model(manifest: dict[str, Any]) -> None:
            model = cast(dict[str, Any], manifest["model"])
            if raw_value is _MISSING:
                model.pop(field)
            else:
                model[field] = raw_value

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_model)

    with pytest.raises(ValueError, match="lifecycle run adapter does not match the planned trial"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_invalid_adapter_identity,
        )


@pytest.mark.parametrize(
    ("field", "raw_value", "index_updates", "message"),
    [
        ("commit", _MISSING, {"repository_commit": None}, "lifecycle repository commit is missing"),
        ("commit", "   ", {"repository_commit": "   "}, "lifecycle repository commit is missing"),
        (
            "commit",
            "not-a-revision",
            {"repository_commit": "not-a-revision"},
            "lifecycle repository commit is invalid",
        ),
        ("repository_kind", _MISSING, None, "lifecycle repository provenance kind is invalid"),
        ("dirty", _MISSING, None, "lifecycle repository dirty flag is invalid"),
        ("dirty", "false", None, "lifecycle repository dirty flag is invalid"),
        (
            "dirty_digest",
            int("1" * 64),
            None,
            "lifecycle repository dirty digest is invalid",
        ),
        (
            "dirty_digest",
            "not-a-sha256",
            None,
            "lifecycle repository dirty digest is invalid",
        ),
        (
            "source_inventory_sha256",
            "not-a-sha256",
            None,
            "lifecycle repository source inventory hash is invalid",
        ),
    ],
)
def test_finalization_rejects_malformed_repository_provenance(
    tmp_path: Path,
    field: str,
    raw_value: object,
    index_updates: Mapping[str, Any] | None,
    message: str,
) -> None:
    trial = _trial(tmp_path, f"invalid-repository-{field}")

    def retain_with_invalid_repository(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_repository(manifest: dict[str, Any]) -> None:
            repository = cast(dict[str, Any], manifest["repository"])
            if raw_value is _MISSING:
                repository.pop(field)
            else:
                repository[field] = raw_value

        return _source_with_manifest_mutation(
            selected_trial,
            recording,
            mutate=mutate_repository,
            index_updates=index_updates,
        )

    with pytest.raises(ValueError, match=message):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_invalid_repository,
        )


def test_finalization_rejects_source_tree_commit_that_does_not_match_inventory(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "mismatched-source-tree-commit")
    forged_commit = f"source-sha256:{'1' * 64}"

    def retain_with_mismatched_source_tree(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_repository(manifest: dict[str, Any]) -> None:
            repository = cast(dict[str, Any], manifest["repository"])
            repository["repository_kind"] = "source_tree"
            repository["commit"] = forged_commit
            repository["source_inventory_sha256"] = "2" * 64

        return _source_with_manifest_mutation(
            selected_trial,
            recording,
            mutate=mutate_repository,
            index_updates={"repository_commit": forged_commit},
        )

    with pytest.raises(ValueError, match="lifecycle source-tree commit does not match its source inventory"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_mismatched_source_tree,
        )


@pytest.mark.parametrize(
    ("dirty", "dirty_digest", "message"),
    [
        (False, "1" * 64, "clean lifecycle repository dirty digest is invalid"),
        (True, hashlib.sha256(b"").hexdigest(), "dirty lifecycle repository dirty digest is invalid"),
    ],
)
def test_finalization_rejects_repository_dirty_flag_that_contradicts_digest(
    tmp_path: Path,
    dirty: bool,
    dirty_digest: str,
    message: str,
) -> None:
    trial = _trial(tmp_path, "contradictory-clean-source")

    def retain_with_contradictory_clean_source(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_repository(manifest: dict[str, Any]) -> None:
            repository = cast(dict[str, Any], manifest["repository"])
            repository["dirty"] = dirty
            repository["dirty_digest"] = dirty_digest

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_repository)

    with pytest.raises(ValueError, match=message):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_contradictory_clean_source,
        )


@pytest.mark.parametrize(
    ("field", "raw_value", "message"),
    [
        ("provider", _MISSING, "lifecycle runtime provider is missing"),
        ("provider", "   ", "lifecycle runtime provider is missing"),
        ("provider", 7, "lifecycle runtime provider is invalid"),
        ("adapter", _MISSING, "lifecycle runtime adapter does not match the planned trial"),
        ("adapter", "other_adapter", "lifecycle runtime adapter does not match the planned trial"),
        ("distributions", _MISSING, "lifecycle runtime distributions are invalid"),
        ("distributions", "abc", "lifecycle runtime distributions are invalid"),
        ("distributions", [1], "lifecycle runtime distributions are invalid"),
        (
            "dependency_inventory_sha256",
            _MISSING,
            "lifecycle runtime dependency hash is invalid",
        ),
        (
            "dependency_inventory_sha256",
            int("1" * 64),
            "lifecycle runtime dependency hash is invalid",
        ),
        (
            "dependency_inventory_sha256",
            "not-a-sha256",
            "lifecycle runtime dependency hash is invalid",
        ),
    ],
)
def test_finalization_rejects_malformed_runtime_provenance(
    tmp_path: Path,
    field: str,
    raw_value: object,
    message: str,
) -> None:
    trial = _trial(tmp_path, f"invalid-runtime-{field}")

    def retain_with_invalid_runtime(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_runtime(manifest: dict[str, Any]) -> None:
            environment = cast(dict[str, Any], manifest["environment"])
            runtime = cast(dict[str, Any], environment["runtime_provenance"])
            if raw_value is _MISSING:
                runtime.pop(field)
            else:
                runtime[field] = raw_value

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_runtime)

    with pytest.raises(ValueError, match=message):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_invalid_runtime,
        )


def test_finalization_rejects_non_string_python_version(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "invalid-python-version")

    def retain_with_invalid_python_version(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_environment(manifest: dict[str, Any]) -> None:
            environment = cast(dict[str, Any], manifest["environment"])
            environment["python_version"] = 313

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_environment)

    with pytest.raises(ValueError, match="lifecycle invocation Python version is invalid"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_invalid_python_version,
        )


@pytest.mark.parametrize(
    ("field", "raw_value", "message"),
    [
        ("qualified_name", 313, "lifecycle verifier qualified name is invalid"),
        ("source_sha256", "not-a-sha256", "lifecycle verifier source hash is invalid"),
    ],
)
def test_finalization_rejects_malformed_verifier_provenance(
    tmp_path: Path,
    field: str,
    raw_value: object,
    message: str,
) -> None:
    trial = _trial(tmp_path, "invalid-verifier-identity")

    def retain_with_invalid_verifier_identity(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_verifier(manifest: dict[str, Any]) -> None:
            verifier = cast(dict[str, Any], manifest["verifier"])
            verifier[field] = raw_value

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_verifier)

    with pytest.raises(ValueError, match=message):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_invalid_verifier_identity,
        )


def test_finalization_rejects_repository_forgery_against_recorder_capture(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-recorded-repository")
    forged_commit = "1" * 40

    def retain_with_forged_repository(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_repository(manifest: dict[str, Any]) -> None:
            repository = cast(dict[str, Any], manifest["repository"])
            repository["repository_kind"] = "git"
            repository["commit"] = forged_commit

        return _source_with_manifest_mutation(
            selected_trial,
            recording,
            mutate=mutate_repository,
            index_updates={"repository_commit": forged_commit},
        )

    with pytest.raises(ValueError, match="lifecycle invocation manifest does not match its recorder capture"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_repository,
        )


def test_finalization_rejects_runtime_forgery_against_recorder_capture(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-recorded-runtime")

    def retain_with_forged_runtime(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_runtime(manifest: dict[str, Any]) -> None:
            environment = cast(dict[str, Any], manifest["environment"])
            runtime = cast(dict[str, Any], environment["runtime_provenance"])
            runtime["provider"] = "forged"
            runtime["distributions"] = ["forged-runtime==1"]
            runtime["dependency_inventory_sha256"] = "1" * 64

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_runtime)

    with pytest.raises(ValueError, match="lifecycle invocation manifest does not match its recorder capture"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_runtime,
        )


def test_finalization_rejects_self_consistent_verifier_forgery(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-recorded-verifier")

    def retain_with_forged_verifier(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_verifier(manifest: dict[str, Any]) -> None:
            forged = callable_provenance(_execute)
            manifest["verifier"] = {**forged, "entrypoint": forged, "chain": [forged]}

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_verifier)

    with pytest.raises(ValueError, match="lifecycle verifier does not match the registered verifier"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_verifier,
        )


def test_finalization_rejects_creation_time_forgery_against_recorder_capture(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-recorded-creation-time")
    forged_created_at = "2000-01-01T00:00:00+00:00"

    def retain_with_forged_creation_time(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_created_at(manifest: dict[str, Any]) -> None:
            manifest["created_at"] = forged_created_at

        return _source_with_manifest_mutation(
            selected_trial,
            recording,
            mutate=mutate_created_at,
            index_updates={"created_at": forged_created_at},
        )

    with pytest.raises(ValueError, match="lifecycle invocation manifest does not match its recorder capture"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_creation_time,
        )


def test_run_lifecycle_trial_rejects_retention_authority_substitution(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "substituted-retention-authority")
    forged_created_at = "2000-01-01T00:00:00+00:00"
    persisted: list[TrialRecord] = []

    def retain_with_substituted_authority(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        revised_recording = recording.copy()
        revised_recording["finalization_authority"] = _plan_expectation_from_recording_fixture(recording)

        def mutate_created_at(manifest: dict[str, Any]) -> None:
            manifest["created_at"] = forged_created_at

        return _source_with_manifest_mutation(
            selected_trial,
            revised_recording,
            mutate=mutate_created_at,
            index_updates={"created_at": forged_created_at},
        )

    with pytest.raises(ValueError, match="lifecycle evidence retention did not preserve the recorder capture"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_substituted_authority,
            persist=persisted.append,
        )

    assert persisted == []


def test_finalization_rejects_python_version_forgery_against_recorder_capture(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-recorded-python-version")

    def retain_with_forged_python_version(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_python_version(manifest: dict[str, Any]) -> None:
            environment = cast(dict[str, Any], manifest["environment"])
            environment["python_version"] = "0.0-forged"

        return _source_with_manifest_mutation(selected_trial, recording, mutate=mutate_python_version)

    with pytest.raises(ValueError, match="lifecycle invocation manifest does not match its recorder capture"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_python_version,
        )


def test_finalization_rejects_transitively_bound_metrics_forgery(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "forged-recorded-metrics")
    forged_seconds = 999.0
    forged_checkpoint_seconds: dict[str, float] = {}

    def retain_with_forged_metrics(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        def mutate_metrics(metrics: dict[str, Any]) -> None:
            metrics["estimated_cost_usd"] = 999.0
            metrics["whole_run_seconds"] = forged_seconds
            recorded_checkpoint_seconds = cast(dict[str, Any], metrics["checkpoint_seconds"])
            forged_checkpoint_seconds.update(
                {checkpoint_id: forged_seconds for checkpoint_id in recorded_checkpoint_seconds}
            )
            metrics["checkpoint_seconds"] = forged_checkpoint_seconds

        def bind_execution_metrics(manifest: dict[str, Any]) -> None:
            execution = cast(dict[str, Any], manifest["execution"])
            execution["whole_run_seconds"] = forged_seconds
            execution["checkpoint_seconds"] = forged_checkpoint_seconds

        return _source_with_metrics_mutation(
            selected_trial,
            recording,
            mutate=mutate_metrics,
            mutate_manifest=bind_execution_metrics,
        )

    with pytest.raises(ValueError, match="lifecycle invocation manifest does not match its recorder capture"):
        run_lifecycle_trial(
            trial=trial,
            execute=_execute,
            verify=verify_lifecycle,
            retain=retain_with_forged_metrics,
        )


def test_planned_finalization_expectation_does_not_trust_callable_source_paths(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "relocated-verifier-source")
    captured_source: LifecycleFinalizationSource | None = None

    def capture_live_source(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        nonlocal captured_source
        captured_source = LifecycleFinalizationSource(
            compiled=selected_trial.compiled,
            run_dir=selected_trial.run_dir,
            recording=recording,
        )
        return captured_source

    run_lifecycle_trial(
        trial=trial,
        execute=_execute,
        verify=verify_lifecycle,
        retain=capture_live_source,
    )
    assert captured_source is not None
    revised_recording = captured_source.recording.copy()
    revised_recording["finalization_authority"] = _plan_expectation_from_recording_fixture(captured_source.recording)

    def relocate_source_paths(payload: dict[str, Any]) -> None:
        recorded_verifier = cast(dict[str, Any], payload["verifier"])
        recorded_entrypoint = cast(dict[str, Any], recorded_verifier["entrypoint"])
        recorded_verifier["source_path"] = "/relocated/registered.py"
        recorded_entrypoint["source_path"] = "/relocated/entrypoint.py"
        recorded_registered = {
            "qualified_name": recorded_verifier["qualified_name"],
            "source_path": recorded_verifier["source_path"],
            "source_sha256": recorded_verifier["source_sha256"],
        }
        recorded_verifier["chain"] = (
            [recorded_entrypoint]
            if recorded_entrypoint == recorded_registered
            else [recorded_entrypoint, recorded_registered]
        )

    recovery_source = _source_with_manifest_mutation(
        trial=trial,
        recording=revised_recording,
        mutate=relocate_source_paths,
    )
    record = finalize_lifecycle_trial(trial=trial, source=recovery_source)

    assert record.lifecycle_provenance is not None


def test_planned_finalization_rejects_coercive_session_count(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "coercive-session-count")
    captured_source: LifecycleFinalizationSource | None = None

    def capture_live_source(
        selected_trial: LifecycleTrial,
        recording: LifecycleExperimentRecordingResult,
    ) -> LifecycleFinalizationSource:
        nonlocal captured_source
        captured_source = LifecycleFinalizationSource(
            compiled=selected_trial.compiled,
            run_dir=selected_trial.run_dir,
            recording=recording,
        )
        return captured_source

    run_lifecycle_trial(
        trial=trial,
        execute=_execute,
        verify=verify_lifecycle,
        retain=capture_live_source,
    )
    assert captured_source is not None
    revised_recording = captured_source.recording.copy()
    revised_recording["finalization_authority"] = _plan_expectation_from_recording_fixture(captured_source.recording)

    def coerce_session_count(payload: dict[str, Any]) -> None:
        execution = cast(dict[str, Any], payload["execution"])
        execution["session_count"] = float(cast(int, execution["session_count"]))

    recovery_source = _source_with_manifest_mutation(
        trial=trial,
        recording=revised_recording,
        mutate=coerce_session_count,
    )
    with pytest.raises(ValueError, match="session_count must be a non-negative integer"):
        finalize_lifecycle_trial(trial=trial, source=recovery_source)


def test_recording_rejects_multiple_resolved_adapter_identities_before_publication(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "mixed-adapters")

    def execute_with_mixed_adapters(selected_trial: LifecycleTrial) -> LifecycleExecution:
        return run_local_lifecycle(
            trial=selected_trial,
            adapter_builder=_GoldAdapterBuilder(
                selected_trial.package_dir,
                resolved_adapters=("tool_loop", "other_adapter", "other_adapter"),
            ),
        )

    with pytest.raises(ValueError, match="lifecycle sessions contain multiple resolved adapter identities"):
        run_lifecycle_trial(
            trial=trial,
            execute=execute_with_mixed_adapters,
            verify=verify_lifecycle,
        )

    assert not (trial.run_dir / "verification.json").exists()
    assert not (trial.run_dir / "metrics.json").exists()
    assert not (trial.run_dir / "experiment-manifest.json").exists()
    assert not (trial.run_dir / "experiments").exists()
    assert not (trial.run_dir.parent / "experiment-index.jsonl").exists()


def test_finalization_preserves_recovered_corrupt_agent_result_kind(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "corrupt-agent-result")
    ledger_root = tmp_path / "ledger"

    def execute_with_corrupt_result(selected_trial: LifecycleTrial) -> LifecycleExecution:
        execution = _execute(selected_trial)
        result_path = next(selected_trial.run_dir.rglob("agent_result.json"))
        result_path.with_name("agent_result.corrupt.json").write_text(
            '{"status": "recovered"}\n',
            encoding="utf-8",
        )
        return execution

    record = run_lifecycle_trial(
        trial=trial,
        execute=execute_with_corrupt_result,
        verify=verify_lifecycle,
    )
    record_path = write_trial_record(ledger_root=ledger_root, record=record)
    loaded = read_trial_record(record_path, ledger_root=ledger_root)

    assert any(artifact.kind == "corrupt_agent_result" for artifact in loaded.outputs.artifacts)


def test_delayed_persistence_rejects_shared_index_changed_by_sibling_trial(tmp_path: Path) -> None:
    first = run_lifecycle_trial(
        trial=_trial(tmp_path, "delayed-first"),
        execute=_execute,
        verify=verify_lifecycle,
    )
    run_lifecycle_trial(
        trial=_trial(tmp_path, "delayed-second"),
        execute=_execute,
        verify=verify_lifecycle,
    )

    with pytest.raises(ValueError, match="trial artifact changed after attachment: output:lifecycle_invocation_index"):
        write_trial_record(ledger_root=tmp_path / "ledger", record=first)


def test_persisted_lifecycle_keeps_full_artifact_and_session_evidence(tmp_path: Path) -> None:
    trial = _trial(tmp_path, "durable-evidence")
    ledger_root = tmp_path / "ledger"
    persisted_paths: list[Path] = []
    pending_artifact_counts: list[int] = []

    def persist(record: TrialRecord) -> None:
        pending_artifact_counts.append(len(record.pending_artifacts))
        persisted_paths.append(write_trial_record(ledger_root=ledger_root, record=record))

    run_lifecycle_trial(trial=trial, execute=_execute, verify=verify_lifecycle, persist=persist)
    shutil.rmtree(trial.package_dir)
    shutil.rmtree(trial.run_dir)

    loaded = read_trial_record(persisted_paths[0], ledger_root=ledger_root)
    repository = ArtifactRepository(ledger_root / "_artifacts")
    assert not trial.package_dir.exists()
    assert not trial.run_dir.exists()
    assert loaded.output is not None
    assert loaded.lifecycle_execution is not None
    assert loaded.lifecycle_provenance is not None
    retained_count = len(loaded.input.input_files or ()) + len(loaded.output.artifacts) + len(loaded.authority_evidence)
    assert retained_count == pending_artifact_counts[0]
    for input_file in loaded.input.input_files or ():
        assert repository.read_bytes(input_file.artifact)
    for output_artifact in loaded.output.artifacts:
        assert repository.read_bytes(output_artifact.artifact)
    for authority in loaded.authority_evidence:
        assert repository.read_bytes(authority.artifact)
    for extension in loaded.extension_refs:
        assert repository.read_bytes(extension.artifact)

    retained_session_artifacts = {(item.path, item.sha256) for item in loaded.output.artifacts}
    assert loaded.lifecycle_execution.sessions
    assert all(session.artifacts for session in loaded.lifecycle_execution.sessions)
    assert all(
        (artifact.path, artifact.sha256) in retained_session_artifacts
        for session in loaded.lifecycle_execution.sessions
        for artifact in session.artifacts
    )


def test_distinct_trial_ids_persist_identical_conditions_without_run_manifest_conflict(tmp_path: Path) -> None:
    trials = [_trial(tmp_path, "same-condition-a"), _trial(tmp_path, "same-condition-b")]
    ledger_root = tmp_path / "ledger"
    paths: list[Path] = []

    def persist(record: TrialRecord) -> None:
        paths.append(write_trial_record(ledger_root=ledger_root, record=record))

    records = run_lifecycle_experiment(
        trials=trials,
        execute=_execute,
        verify=verify_lifecycle,
        persist=persist,
    )

    assert trials[0].compiled.envelope.package_sha256 == trials[1].compiled.envelope.package_sha256
    assert [record.run_id for record in records] == ["same-condition-a", "same-condition-b"]
    assert [read_trial_record(path, ledger_root=ledger_root).run_id for path in paths] == [
        "same-condition-a",
        "same-condition-b",
    ]
    assert records[0].run_manifest.agent == records[1].run_manifest.agent
