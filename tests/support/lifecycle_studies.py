# ABOUTME: Provides deterministic lifecycle-study plans, runs, and canonical invocation fixtures.
# ABOUTME: Lets current and historical study tests share setup without importing another test module.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

import aec_bench.lifecycles.catalogue as lifecycle_catalogue
import aec_bench.lifecycles.recording as experiment_runtime
from aec_bench.adapters.base import AdapterRequest
from aec_bench.contracts.evidence_lifecycle import EvidenceLifecycleSpec
from aec_bench.contracts.experiment_manifest import AgentConfig
from aec_bench.experimentation.lifecycle_studies.ablation import (
    LifecycleAblationCondition,
    LifecycleAblationLimits,
    LifecycleAblationManifest,
    LifecycleAblationStudyDesign,
    LifecycleAblationTrial,
    LifecycleExecutionMode,
    build_lifecycle_ablation_plan,
)
from aec_bench.harness.lifecycle_local import (
    LifecycleVisibilityPolicy,
    _run_local_lifecycle_fresh_session,
    build_lifecycle_tool_schema,
)
from aec_bench.lifecycles.catalogue import materialize_lifecycle, verify_lifecycle
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.invocation import (
    LifecycleExperimentSweepContext,
    LifecycleExperimentTrialContext,
)

TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"


def single_lifecycle_ablation_manifest(tmp_path: Path) -> LifecycleAblationManifest:
    return LifecycleAblationManifest(
        experiment_id="stormwater-live",
        lifecycle_template_id=TEMPLATE_ID,
        variants=("response_assertion_only",),
        agents=(
            AgentConfig(
                name="gold-replay",
                adapter="tool_loop",
                model="deterministic-replay",
                parameters={"max_turns_per_session": 10},
            ),
        ),
        study_design=lifecycle_ablation_study_design(),
        conditions=(
            LifecycleAblationCondition(
                execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
                memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
            ),
        ),
        output_root=str(tmp_path / "live-output"),
        ledger_root=str(tmp_path / "live-ledger"),
        limits=LifecycleAblationLimits(max_trials=1),
    )


def recorded_lifecycle_ablation_trial(
    tmp_path: Path,
) -> tuple[LifecycleAblationManifest, LifecycleAblationTrial, Path, Path]:
    manifest = LifecycleAblationManifest(
        experiment_id="stormwater-import",
        lifecycle_template_id=TEMPLATE_ID,
        variants=("response_assertion_only",),
        agents=(
            AgentConfig(
                name="agent-a",
                adapter="tool_loop",
                model="model-a",
                parameters={"max_turns_per_session": 20},
            ),
        ),
        study_design=lifecycle_ablation_study_design(),
        conditions=(
            LifecycleAblationCondition(
                execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
                memory_visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
            ),
        ),
        repetitions=1,
        output_root=str(tmp_path / "outputs"),
        ledger_root=str(tmp_path / "ledger"),
        limits=LifecycleAblationLimits(max_trials=1),
    )
    return _record_lifecycle_ablation_trial(
        manifest,
        adapter_builder=lambda package: GoldFreshRegistry(package, resolved_model="model-a").build,
    )


def recorded_conditional_lifecycle_ablation_trial(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[LifecycleAblationManifest, LifecycleAblationTrial, Path, Path]:
    definition = lifecycle_catalogue._DEFINITIONS[TEMPLATE_ID]

    def materialize_conditional_lifecycle(
        output_dir: Path,
        *,
        variant_id: str | None = None,
    ) -> Path:
        package = Path(definition.materializer(output_dir, variant_id=variant_id))
        add_later_conditional_evidence(package)
        return package

    probe = materialize_conditional_lifecycle(
        tmp_path / "conditional-definition",
        variant_id="response_assertion_only",
    )
    monkeypatch.setitem(
        lifecycle_catalogue._DEFINITIONS,
        TEMPLATE_ID,
        replace(
            definition,
            lifecycle=EvidenceLifecycleSpec.model_validate(_read_json_object(probe / "lifecycle.json")),
            materializer=materialize_conditional_lifecycle,
        ),
    )
    lifecycle_catalogue.lifecycle_executable_artifact_sha256.cache_clear()
    manifest = single_lifecycle_ablation_manifest(tmp_path).model_copy(
        update={"experiment_id": "conditional-lifecycle-retention"}
    )
    return _record_lifecycle_ablation_trial(
        manifest,
        adapter_builder=lambda package: _ConditionalGoldFreshRegistry(package).build,
    )


def _record_lifecycle_ablation_trial(
    manifest: LifecycleAblationManifest,
    *,
    adapter_builder: Callable[[Path], Callable[..., Any]],
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
        TEMPLATE_ID,
        Path(trial.package_dir),
        variant_id=trial.variant_id,
    )
    run_dir = Path(trial.run_dir)
    execution = _run_local_lifecycle_fresh_session(
        package_dir=package,
        run_dir=run_dir,
        model=trial.agent.model,
        adapter_kind=trial.agent.adapter,
        max_turns=trial.max_turns_per_session,
        adapter_builder=adapter_builder(package),
        visibility_policy=trial.memory_visibility_policy,
    )
    record_completed_lifecycle_invocation(
        manifest=manifest,
        trial=trial,
        package=package,
        run_dir=run_dir,
        execution=execution,
        verifier=verify_lifecycle,
        plan_sha256=plan.plan_sha256,
    )
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["repository"]["commit"] = plan.code_provenance.repository_commit
    experiment["repository"]["source_inventory_sha256"] = plan.code_provenance.source_inventory_sha256
    experiment["environment"]["runtime_provenance"] = trial.runtime_provenance.model_dump(mode="json")
    experiment["verifier"]["qualified_name"] = plan.code_provenance.verifier_qualified_name
    experiment["verifier"]["source_sha256"] = plan.code_provenance.verifier_source_sha256
    experiment["verifier"]["entrypoint"]["qualified_name"] = plan.code_provenance.verifier_entrypoint_qualified_name
    experiment["verifier"]["entrypoint"]["source_sha256"] = plan.code_provenance.verifier_entrypoint_source_sha256
    rewrite_canonical_lifecycle_invocation(run_dir, experiment)
    return manifest, trial, package, run_dir


def rewrite_canonical_lifecycle_invocation(run_dir: Path, experiment: dict[str, Any]) -> None:
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment_path.write_text(
        json.dumps(experiment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest_sha256 = hashlib.sha256(experiment_path.read_bytes()).hexdigest()
    seal_path = experiment_path.parent / "index-entry.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    seal["manifest_sha256"] = manifest_sha256
    seal_path.write_text(json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    index_path = run_dir.parent / "experiment-index.jsonl"
    entries = [json.loads(line) for line in index_path.read_text(encoding="utf-8").splitlines()]
    for entry in entries:
        if entry.get("experiment_id") == experiment["experiment_id"]:
            entry["manifest_sha256"] = manifest_sha256
    index_path.write_text("".join(json.dumps(entry, sort_keys=True) + "\n" for entry in entries), encoding="utf-8")


def downgrade_canonical_lifecycle_invocation_to_schema_one(run_dir: Path) -> None:
    experiment_path = next((run_dir / "experiments").glob("*/experiment-manifest.json"))
    experiment = json.loads(experiment_path.read_text(encoding="utf-8"))
    experiment["schema_version"] = "1"
    experiment.pop("trial")
    rewrite_canonical_lifecycle_invocation(run_dir, experiment)


def record_completed_lifecycle_invocation(
    *,
    manifest: LifecycleAblationManifest,
    trial: LifecycleAblationTrial,
    package: Path,
    run_dir: Path,
    execution: dict[str, Any],
    verifier: Callable[[Path, Path], dict[str, object]],
    plan_sha256: str,
) -> None:
    lifecycle = json.loads((package / "lifecycle.json").read_text(encoding="utf-8"))
    checkpoints = lifecycle["checkpoints"]
    experiment_runtime.record_lifecycle_experiment(
        package_dir=package,
        run_dir=run_dir,
        agent=cast(dict[str, Any], execution["evidence"]["agent"]),
        verifier=verifier,
        verification=cast(dict[str, Any], verifier(package, run_dir)),
        tool_schema=build_lifecycle_tool_schema(
            "fresh_context",
            supports_evidence_requests=any(
                checkpoint.get("conditional_evidence") is not None for checkpoint in checkpoints
            ),
            supports_lifecycle_operations=any(
                checkpoint.get("conditional_operations") is not None for checkpoint in checkpoints
            ),
        ),
        trial_context=LifecycleExperimentTrialContext(
            trial_id=trial.trial_id,
            planned_experiment_id=manifest.experiment_id,
            task_id=manifest.lifecycle_template_id,
            repetition=trial.repetition,
            run_id=trial.trial_id,
            compiled=load_compiled_lifecycle(package).envelope,
        ),
        sweep_context=LifecycleExperimentSweepContext(
            sweep_experiment_id=manifest.experiment_id,
            planned_trial_id=trial.trial_id,
            plan_sha256=plan_sha256,
            condition_id=f"{trial.execution_mode.value}__{trial.memory_visibility_policy.value}",
            repetition=trial.repetition,
        ),
    )


def add_later_conditional_evidence(package: Path) -> None:
    lifecycle_path = package / "lifecycle.json"
    lifecycle = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    checkpoint_id = lifecycle["checkpoints"][1]["checkpoint_id"]
    lifecycle["checkpoints"][1]["conditional_evidence"] = {
        "request_budget": 1,
        "requests": [
            {
                "request_id": "response_support",
                "title": "Response support",
                "description": "Obtain the response-stage support record.",
                "prerequisite_request_ids": [],
            }
        ],
    }
    lifecycle_path.write_text(json.dumps(lifecycle, indent=2, sort_keys=True), encoding="utf-8")
    resolution = package / "hidden" / "evidence-request-resolutions.json"
    resolution.write_text(
        json.dumps(
            {
                "schema_version": "1",
                "lifecycle_id": lifecycle["lifecycle_id"],
                "resolutions": [
                    {
                        "checkpoint_id": checkpoint_id,
                        "request_id": "response_support",
                        "source_path": f"hidden/evidence_requests/{checkpoint_id}/response_support",
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    evidence = package / "hidden" / "evidence_requests" / checkpoint_id / "response_support"
    evidence.mkdir(parents=True)
    (evidence / "support.txt").write_text("response support\n", encoding="utf-8")


def lifecycle_ablation_study_design() -> LifecycleAblationStudyDesign:
    return LifecycleAblationStudyDesign(
        interpretation="descriptive_calibration",
        turn_budget_scope="per_session",
        execution_order="deterministic_sequential_plan_order",
        randomized=False,
        counterbalanced=False,
        causal_effects_supported=False,
    )


class GoldFreshRegistry:
    def __init__(self, package: Path, *, resolved_model: str = "deterministic-replay") -> None:
        self.gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        self.resolved_model = resolved_model
        self.build_count = 0

    def build(self, **_kwargs: Any) -> Any:
        self.build_count += 1
        gold = self.gold
        resolved_model = self.resolved_model

        class _GoldAdapter:
            def execute(self, request: AdapterRequest) -> Any:
                output_path = Path(request.output_path)
                checkpoint_id = output_path.stem
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(json.dumps(gold[checkpoint_id]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model=resolved_model,
                    configuration_record={"model": resolved_model, "source": "in_process_replay"},
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

        return _GoldAdapter()


class _ConditionalGoldFreshRegistry(GoldFreshRegistry):
    def build(self, **kwargs: Any) -> Any:
        native_tools = cast(list[Callable[..., str]], kwargs["native_tools"])
        adapter = super().build(**kwargs)
        request_evidence = next(tool for tool in native_tools if tool.__name__ == "request_evidence")

        class _ConditionalGoldAdapter:
            def execute(self, request: AdapterRequest) -> Any:
                if Path(request.output_path).stem == "response_review":
                    response = json.loads(
                        request_evidence(
                            "response_review",
                            "response_support",
                            "Resolve the response support gap.",
                        )
                    )
                    assert response["status"] == "released"
                return adapter.execute(request)

        return _ConditionalGoldAdapter()


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


__all__ = (
    "GoldFreshRegistry",
    "TEMPLATE_ID",
    "add_later_conditional_evidence",
    "downgrade_canonical_lifecycle_invocation_to_schema_one",
    "lifecycle_ablation_study_design",
    "record_completed_lifecycle_invocation",
    "recorded_conditional_lifecycle_ablation_trial",
    "recorded_lifecycle_ablation_trial",
    "rewrite_canonical_lifecycle_invocation",
    "single_lifecycle_ablation_manifest",
)
