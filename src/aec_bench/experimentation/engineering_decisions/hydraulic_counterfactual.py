# ABOUTME: Runs hydraulic counterfactual and verifier conditions through canonical lifecycle trials.
# ABOUTME: Retains actual calculation, checkpoint, session, and verifier evidence in the trial ledger.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.engineering_decisions.definitions import (
    CHALLENGES,
    HydraulicChallenge,
    HydraulicExperiment,
    VerifierExperiment,
)
from aec_bench.experimentation.engineering_decisions.records import publish_record, write_plan
from aec_bench.harness.lifecycle_local import build_lifecycle_tool_schema
from aec_bench.lifecycles.application import run_lifecycle_trial
from aec_bench.lifecycles.compiled import load_compiled_lifecycle
from aec_bench.lifecycles.runtime.episode import (
    InProcessLifecycleEpisodeEnvironment,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.lifecycles.runtime.lifecycle import read_lifecycle, run_lifecycle
from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
    build_hydraulic_operation_resolver,
    materialize_hydraulic_review_lifecycle,
    verify_hydraulic_review_lifecycle,
)
from aec_bench.lifecycles.stormwater_design.hydraulic_review_smoke import write_hydraulic_review_smoke_submission
from aec_bench.lifecycles.stormwater_design.hydraulics.lineages import HydraulicLineage
from aec_bench.lifecycles.values import LifecycleExecution, LifecycleTrial
from aec_bench.trials import PlannedTrial


def hydraulic_plan(experiment_id: str, seed: int, revision: str, challenge: HydraulicChallenge) -> PlannedTrial:
    return PlannedTrial(
        trial_id=f"{experiment_id}-{seed}-{revision}-{challenge}",
        experiment_id=experiment_id,
        task_id=f"hydraulic/{seed}/{revision}",
        agent=AgentConfig(
            name=challenge,
            adapter="in_process",
            model="hydraulic-smoke",
            parameters={"max_turns_per_session": 1, "seed": seed, "revision": revision, "challenge": challenge},
        ),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )


def run_hydraulic_counterfactual(
    output: Path,
    *,
    seed: int,
    revision_id: str,
    challenge: HydraulicChallenge = "none",
    planned: PlannedTrial | None = None,
) -> TrialRecord:
    if challenge not in CHALLENGES:
        raise ValueError(f"unknown hydraulic challenge: {challenge}")
    planned = planned or hydraulic_plan("hydraulic-counterfactual", seed, revision_id, challenge)
    expected = hydraulic_plan(planned.experiment_id, seed, revision_id, challenge)
    if planned != expected:
        raise ValueError("hydraulic condition does not match its planned trial")
    lineage = HydraulicLineage(seed=seed)
    package = materialize_hydraulic_review_lifecycle(output / "package", variant_id=revision_id, lineage=lineage)
    run = output / "run"
    trial = LifecycleTrial(
        planned=planned,
        compiled=load_compiled_lifecycle(package),
        run_dir=run,
        execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
        visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
    )
    submissions: dict[str, Any] = {}
    sessions: list[dict[str, Any]] = []

    def episode(request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        checkpoint = request.checkpoint_id
        path = Path(request.submission_path)
        write_hydraulic_review_smoke_submission(package, run, checkpoint, request.session_id, path)
        submission = json.loads(path.read_text())
        if challenge == "reordered_decisions":
            submission["accepted_decisions"] = sorted(
                submission["accepted_decisions"], key=lambda x: x["scenario_id"], reverse=True
            )
        if checkpoint == "closeout_review":
            if challenge == "stale_source":
                submission["visible_source_state_sha256"] = submissions["baseline_analysis"][
                    "visible_source_state_sha256"
                ]
            elif challenge == "missing_memo":
                submission["memo"]["decision_ids"] = {}
            elif challenge == "false_readiness":
                submission["readiness_decision"] = (
                    "screening_ready"
                    if submission["readiness_decision"] != "screening_ready"
                    else "not_screening_ready"
                )
            elif challenge == "false_authority":
                submission["claim_boundary"]["authority_status"] = "authority_approved"
        path.write_text(json.dumps(submission, indent=2) + "\n")
        submissions[checkpoint] = submission
        session = {
            "session_id": request.session_id,
            "checkpoint_ids": [checkpoint],
            "model": request.requested_model,
            "adapter": request.requested_adapter,
            "adapter_name": "in_process",
            "resolved_model": "hydraulic-smoke",
            "session_mode": "fresh",
            "memory_visibility_policy": request.memory_visibility_policy.value,
            "max_turns": request.max_turns_per_session,
            "status": "completed",
            "configuration_record": planned.agent.parameters,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
        }
        session_path = run / "episodes" / checkpoint / request.session_id / "agent_result.json"
        session_path.write_text(json.dumps(session, indent=2) + "\n")
        sessions.append(session)
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status="completed",
            requested_adapter=request.requested_adapter,
            requested_model=request.requested_model,
            max_turns_per_session=request.max_turns_per_session,
            adapter="in_process",
            resolved_model="hydraulic-smoke",
            configuration=planned.agent.parameters,
            usage=LifecycleEpisodeUsage(),
        )

    def execute(current: LifecycleTrial) -> LifecycleExecution:
        resolver = build_hydraulic_operation_resolver(package, run)
        run_lifecycle(
            package,
            run,
            episode_environment=InProcessLifecycleEpisodeEnvironment(
                executor=episode, requested_adapter="in_process", requested_model="hydraulic-smoke"
            ),
            operation_resolver=resolver,
        )
        state = read_lifecycle(package, run, operation_resolver=resolver)
        return LifecycleExecution(
            state=state,
            agent={
                "model": planned.agent.model,
                "adapter": planned.agent.adapter,
                "execution_mode": current.execution_mode.value,
                "memory_visibility_policy": current.visibility_policy.value,
                "max_turns_per_session": 1,
                "status": "completed",
                "sessions": sessions,
                "totals": {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "failures": 0,
                },
            },
            tool_schema=tuple(
                build_lifecycle_tool_schema(
                    execution_mode="fresh_context", supports_evidence_requests=False, supports_lifecycle_operations=True
                )
            ),
        )

    record = run_lifecycle_trial(trial=trial, execute=execute, verify=verify_hydraulic_review_lifecycle)
    result = json.loads((run / "verification.json").read_text())
    baseline = submissions["baseline_analysis"]
    revision = submissions["revision_analysis"]
    state = read_lifecycle(package, run, operation_resolver=build_hydraulic_operation_resolver(package, run))
    revision_actions = next(
        c["operation_actions"] for c in state["checkpoint_runs"] if c["checkpoint_id"] == "revision_analysis"
    )
    preserved = sorted(a["operation_id"] for a in revision_actions if a["outcome"] == "already_current")
    report = {
        "lineage_id": lineage.lineage_id,
        "seed": seed,
        "revision_id": revision_id,
        "challenge": challenge,
        "expected_pass": challenge in {"none", "reordered_decisions"},
        "verification": result,
        "baseline_readiness": baseline["readiness_decision"],
        "revision_readiness": revision["readiness_decision"],
        "preserved_operations": preserved,
        "recomputed_operations": sorted(set(baseline["selected_operations"]) - set(preserved)),
        "evidence_scope": "deterministic_synthetic_control_not_model_performance",
    }
    report["expectation_met"] = result["passed"] == report["expected_pass"]
    diagnostics = output / "diagnostics.json"
    diagnostics.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    record.attach_artifact("experiment_diagnostics", diagnostics, media_type="application/json")
    return record


def run_hydraulic_experiment(output: Path, definition: HydraulicExperiment | None = None) -> list[TrialRecord]:
    definition = definition or HydraulicExperiment()
    trials = [
        hydraulic_plan(definition.experiment_id, seed, revision, "none")
        for partition in definition.partitions
        for seed in partition.seeds
        for revision in definition.revisions
    ]
    write_plan(output, definition, trials)
    return [
        publish_record(
            output,
            run_hydraulic_counterfactual(
                output / trial.trial_id,
                seed=trial.agent.parameters["seed"],
                revision_id=trial.agent.parameters["revision"],
                planned=trial,
            ),
        )
        for trial in trials
    ]


def run_verifier_experiment(output: Path, definition: VerifierExperiment | None = None) -> list[TrialRecord]:
    definition = definition or VerifierExperiment()
    trials = [
        hydraulic_plan(definition.experiment_id, definition.seed, definition.revision, challenge)
        for challenge in definition.challenges
    ]
    write_plan(output, definition, trials)
    return [
        publish_record(
            output,
            run_hydraulic_counterfactual(
                output / trial.trial_id,
                seed=definition.seed,
                revision_id=definition.revision,
                challenge=trial.agent.parameters["challenge"],
                planned=trial,
            ),
        )
        for trial in trials
    ]
