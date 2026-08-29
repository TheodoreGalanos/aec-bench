# ABOUTME: Proves safe drainage feedback, named projections, and the complete deterministic L01 slice.
# ABOUTME: Verifies truthful assessment evidence, probe isolation, and relation-review downgrades.

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.contracts.trial_record import EvaluationStatus, TrialInput, TrialOutput
from aec_bench.experimentation.learning_studies.assessment import assess_learning_study
from aec_bench.experimentation.learning_studies.l01_drainage import (
    L01_CONSOLIDATION_OPERATION_ID,
    L01_DRAINAGE_STUDY_ID,
    L01_EXECUTION_CONDITION,
    compile_l01_drainage_study,
    l01_drainage_outcome_projections,
    load_l01_drainage_protocol,
    run_l01_drainage_study_sync,
)
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleConsolidationContext,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
)
from aec_bench.experimentation.learning_studies.planning import CompiledFeedbackStep
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunStatus,
    ReleaseFeedbackRequest,
)
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.lifecycle import run_lifecycle
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DRAINAGE_ACQUISITION_TASK_ID,
    DRAINAGE_PROBE_TASK_ID,
    DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
    drainage_staged_review_feedback,
    validate_drainage_staged_review_feedback,
)
from aec_bench.lifecycles.stormwater_design.drainage_model import (
    CHECKPOINT_IDS,
    TEMPLATE_ID,
    verify_drainage_model_lifecycle,
)
from tests.support.lifecycle_episode import deterministic_episode_environment
from tests.support.trial_record_factories import make_trial_record

_AGENT = AgentConfig(
    name="l01-deterministic-agent",
    adapter="tool_loop",
    model="fixed-test-model",
    parameters={"max_turns_per_session": 5},
)
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512})
_PROJECTION_IDS = {
    "lifecycle.canonical-reward",
    "drainage.staged-disclosure",
    "drainage.finding-continuity",
    "drainage.closure-evidence",
    "drainage.claim-boundary",
}


class _DeclaredFeedbackConsolidator:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, context: LifecycleConsolidationContext) -> None:
        self.calls += 1
        assert len(context.feedback) == 1
        feedback = validate_drainage_staged_review_feedback(context.feedback[0].path.read_bytes())
        principles = "\n".join(f"- {item}" for item in feedback["review_principles"])
        (context.memory_root / "drainage-review-strategy.md").write_text(
            f"# Drainage review strategy\n\n{principles}\n",
            encoding="utf-8",
        )


class _GoldLifecycleAdapterBuilder:
    def __init__(self) -> None:
        self.executions = 0
        self.contexts: dict[tuple[str, str], list[dict[str, str] | None]] = {}
        self.system_prompts: list[str] = []

    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        package = workspace.parent.parent / "package"
        arm_run_id = package.parents[2].name
        variant_id = _read_json(package / "hidden" / "variant.json")["variant_id"]
        submissions = _read_json(package / "hidden" / "gold-submissions.json")
        native_tools = {tool.__name__: tool for tool in kwargs["native_tools"]}
        builder = self

        class _Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                builder.executions += 1
                builder.system_prompts.append(request.system_prompt)
                root = json.loads(native_tools["list_workspace"]("."))
                context: dict[str, str] | None = None
                if "learner_context" in root["entries"]:
                    context = {}
                    listing = json.loads(native_tools["list_workspace"]("learner_context"))
                    for name in listing["entries"]:
                        item = json.loads(native_tools["read_workspace_file"](f"learner_context/{name}"))
                        context[name] = item["content"]
                builder.contexts.setdefault((arm_run_id, variant_id), []).append(context)
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(submissions[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="fixed-test-model",
                    configuration_record={"model": "fixed-test-model", "source": "deterministic-test"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=2,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


def test_l01_protocol_declares_exact_tasks_arms_treatments_and_measurements() -> None:
    spec = load_l01_drainage_protocol(agent=_AGENT, compute=_COMPUTE)
    plan = compile_l01_drainage_study(
        study_run_id="l01-protocol-test",
        agent=_AGENT,
        compute=_COMPUTE,
    )

    assert spec.study_id == L01_DRAINAGE_STUDY_ID
    assert [item.task_id for item in spec.experiences] == [
        DRAINAGE_ACQUISITION_TASK_ID,
        DRAINAGE_PROBE_TASK_ID,
    ]
    assert [(item.arm_id, item.role.value, item.treatment_id) for item in spec.arms] == [
        ("cold-reset", "control", "reset"),
        ("reset-after-acquisition", "control", "reset"),
        ("structured-memory", "exposure", "structured-memory"),
    ]
    assert {item.projection_id for item in spec.measurements} == _PROJECTION_IDS
    assert spec.relations[0].relation_id == "staged-correction-to-semantic-no-op"
    assert all(
        step.trial.extensions == {} for arm_run in plan.arm_runs for step in arm_run.steps if hasattr(step, "trial")
    )
    assert L01_EXECUTION_CONDITION.adapter_id == "lifecycle-local:fresh_context:artifact_memory"
    structured_steps = spec.arms[2].steps
    assert structured_steps[1].feedback_view_id == DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID
    assert structured_steps[2].operation_id == L01_CONSOLIDATION_OPERATION_ID


def test_drainage_feedback_selects_only_public_evidence_and_rejects_archive_ambiguity(tmp_path: Path) -> None:
    record, package, run = _completed_acquisition_record(tmp_path)

    data = drainage_staged_review_feedback(record)
    payload = validate_drainage_staged_review_feedback(data)

    assert payload["trial_id"] == record.trial_id
    assert payload["task_id"] == DRAINAGE_ACQUISITION_TASK_ID
    assert set(payload["checkpoint_submissions"]) == set(CHECKPOINT_IDS)
    assert all(set(gate) == {"passed", "score"} for gate in payload["review_gates"].values())
    assert payload["terminal_outcome"]["canonical_reward"] == 1.0
    assert payload["terminal_outcome"]["validity"] == {
        "output_parseable": True,
        "schema_valid": True,
        "verifier_completed": True,
    }
    text = data.decode()
    assert "hidden evaluator detail" not in text
    assert "failures" not in text
    assert "gold-submissions" not in text
    assert "verifier-config" not in text
    assert str(package) not in text
    assert str(run) not in text

    with pytest.raises(ValueError, match="feedback-source-task-mismatch"):
        drainage_staged_review_feedback(make_trial_record(task_id="unrelated/task"))
    incomplete = record.model_copy(update={"execution_status": "failed"})
    with pytest.raises(ValueError, match="feedback-source-trial-missing"):
        drainage_staged_review_feedback(incomplete)
    unavailable = record.model_copy(update={"evaluation_status": "not_requested", "evaluation": None})
    with pytest.raises(ValueError, match="feedback-source-evaluation-missing"):
        drainage_staged_review_feedback(unavailable)

    duplicate = run / "episodes" / "duplicate" / "initial_review" / "submission.json"
    duplicate.parent.mkdir(parents=True)
    duplicate.write_bytes((run / "episodes" / "initial_review" / "submission.json").read_bytes())
    with pytest.raises(ValueError, match="feedback-submission-missing"):
        drainage_staged_review_feedback(record)
    duplicate.unlink()
    (run / "episodes" / "closeout_review" / "submission.json").unlink()
    with pytest.raises(ValueError, match="feedback-submission-missing"):
        drainage_staged_review_feedback(record)


def test_lifecycle_adapter_rejects_unsafe_feedback_before_state_or_artifact_write(tmp_path: Path) -> None:
    plan = compile_l01_drainage_study(
        study_run_id="l01-unsafe-feedback",
        agent=_AGENT,
        compute=_COMPUTE,
    )
    arm_run = next(item for item in plan.arm_runs if item.arm_id == "structured-memory")
    feedback_step = next(item for item in arm_run.steps if isinstance(item, CompiledFeedbackStep))
    run_root = tmp_path / "study"
    binding = build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=L01_EXECUTION_CONDITION,
        treatment_kinds={"structured-memory": LifecycleLearningTreatmentKind.STRUCTURED_MEMORY},
        feedback_projectors={
            DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID: lambda _record: b'{"private_path":"/tmp/secret"}\n'
        },
        consolidation_operations={L01_CONSOLIDATION_OPERATION_ID: _DeclaredFeedbackConsolidator()},
    )
    state = binding.operations.initialise_learner(arm_run)

    with pytest.raises(ValueError, match="feedback-projection-unsafe"):
        binding.operations.release_feedback(
            ReleaseFeedbackRequest(
                arm_run=arm_run,
                step=feedback_step,
                state=state,
                source_trial_record=make_trial_record(task_id=DRAINAGE_ACQUISITION_TASK_ID),
            )
        )

    assert not (state.value.root.parent / feedback_step.step_id).exists()
    assert not any(path.is_file() for path in (run_root / "_artifacts").rglob("*"))


def test_required_l01_projections_are_bounded_and_missing_evidence_is_ineligible() -> None:
    projections = l01_drainage_outcome_projections()
    gates = {
        gate_id: {"passed": True, "score": 0.75, "failures": ["not learner-visible"]}
        for gate_id in ("staged_disclosure", "finding_continuity", "closure_evidence", "claim_boundary")
    }
    valid = make_trial_record(
        task_id=DRAINAGE_PROBE_TASK_ID,
        evaluation=EvaluationResult(
            reward=0.8,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={"lifecycle_gates": gates},
        ),
    )

    assert set(projections) == _PROJECTION_IDS
    for projection_id, projection in projections.items():
        result = projection(valid)
        assert result.eligible is True
        assert result.value == (0.8 if projection_id == "lifecycle.canonical-reward" else 0.75)
        assert (result.lower_bound, result.upper_bound) == (0.0, 1.0)

        mismatch = projection(make_trial_record(task_id="unrelated/task"))
        assert mismatch.eligible is False and mismatch.value is None
        assert mismatch.reason is not None and mismatch.reason.startswith("projection-task-mismatch")

        missing_evaluation = projection(
            make_trial_record(
                task_id=DRAINAGE_PROBE_TASK_ID,
                evaluation=None,
                evaluation_status=EvaluationStatus.NOT_REQUESTED,
            )
        )
        assert missing_evaluation.eligible is False and missing_evaluation.value is None
        assert missing_evaluation.reason is not None and "projection-evaluation-missing" in missing_evaluation.reason

    for projection_id in _PROJECTION_IDS - {"lifecycle.canonical-reward"}:
        missing_breakdown = projections[projection_id](
            make_trial_record(
                task_id=DRAINAGE_PROBE_TASK_ID,
                evaluation=EvaluationResult(
                    reward=0.8,
                    validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
                ),
            )
        )
        assert missing_breakdown.eligible is False and missing_breakdown.value is None
        assert missing_breakdown.reason is not None and "projection-breakdown-missing" in missing_breakdown.reason
        missing_gate = projections[projection_id](
            make_trial_record(
                task_id=DRAINAGE_PROBE_TASK_ID,
                evaluation=EvaluationResult(
                    reward=0.8,
                    validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
                    breakdown={"lifecycle_gates": {}},
                ),
            )
        )
        assert missing_gate.eligible is False and missing_gate.value is None
        assert missing_gate.reason is not None and "projection-gate-missing" in missing_gate.reason
        malformed_gate = projections[projection_id](
            make_trial_record(
                task_id=DRAINAGE_PROBE_TASK_ID,
                evaluation=EvaluationResult(
                    reward=0.8,
                    validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
                    breakdown={
                        "lifecycle_gates": {
                            projection_id.removeprefix("drainage.").replace("-", "_"): {
                                "passed": "yes",
                                "score": "0.75",
                            }
                        }
                    },
                ),
            )
        )
        assert malformed_gate.eligible is False and malformed_gate.value is None
        assert malformed_gate.reason is not None and "projection-value-invalid" in malformed_gate.reason


def test_deterministic_l01_runs_all_arms_and_builds_truthful_assessment_evidence(tmp_path: Path) -> None:
    run_root = tmp_path / "l01"
    adapter = _GoldLifecycleAdapterBuilder()
    consolidator = _DeclaredFeedbackConsolidator()

    result = run_l01_drainage_study_sync(
        run_root=run_root,
        study_run_id="l01-deterministic",
        agent=_AGENT,
        compute=_COMPUTE,
        consolidation_operation=consolidator,
        adapter_builder=adapter,
    )

    assert adapter.executions == 15
    assert consolidator.calls == 1
    assert all(arm.status is ArmRunStatus.COMPLETED for arm in result.execution.arm_runs)
    assert len({item.initial_state_equivalence_id for item in result.arm_evidence.values()}) == 1
    assert all(item.adapter_id == L01_EXECUTION_CONDITION.adapter_id for item in result.arm_evidence.values())
    assert all(item.arm_isolated for item in result.arm_evidence.values())
    assert all(item.lineage_complete for item in result.arm_evidence.values())
    assert all(item.probe_feedback_hidden for item in result.arm_evidence.values())
    assert all(item.probe_state_discarded for item in result.arm_evidence.values())
    assert all(not item.hidden_evaluation_leaked for item in result.arm_evidence.values())

    assert all(
        measurement.validity is LearningComparisonValidity.DESCRIPTIVE_ONLY
        for measurement in result.unreviewed_assessment.measurements
    )
    reviewed = {item.measurement_id: item for item in result.reviewed_assessment.measurements}
    assert reviewed["reset-after-acquisition-canonical-effect"].validity is LearningComparisonValidity.DESCRIPTIVE_ONLY
    for measurement_id, measurement in reviewed.items():
        if measurement_id == "reset-after-acquisition-canonical-effect":
            continue
        assert measurement.validity is LearningComparisonValidity.CONTROLLED
        assert len(measurement.included_pairs) == 1
        assert measurement.excluded_repetitions == ()
        assert measurement.included_pairs[0].focal_value == 1.0
        assert measurement.included_pairs[0].comparator_value == 1.0
        assert measurement.included_pairs[0].normalised_effect == 0.0

    structured_evidence_id = next(
        arm_run.arm_run_id for arm_run in result.plan.arm_runs if arm_run.arm_id == "structured-memory"
    )
    invalid_evidence = dict(result.arm_evidence)
    invalid_evidence[structured_evidence_id] = replace(
        invalid_evidence[structured_evidence_id],
        probe_state_discarded=False,
        hidden_evaluation_leaked=True,
    )
    invalid = assess_learning_study(
        spec=result.spec,
        plan=result.plan,
        execution=result.execution,
        projections=l01_drainage_outcome_projections(),
        arm_evidence=invalid_evidence,
        relations_reviewed=True,
    )
    assert all(
        measurement.validity is LearningComparisonValidity.INVALID
        for measurement in invalid.measurements
        if measurement.measurement_id != "reset-after-acquisition-canonical-effect"
    )

    structured_arm = next(item for item in result.plan.arm_runs if item.arm_id == "structured-memory")
    structured_root = run_root / "learner-arms" / structured_arm.arm_run_id
    final_state = structured_root / "states" / "consolidate-review-method"
    memory = final_state / "memory" / "drainage-review-strategy.md"
    feedback = final_state / "feedback" / "release-acquisition-feedback.json"
    assert memory.is_file()
    assert "Current registered evidence controls" in memory.read_text(encoding="utf-8")
    feedback_payload = validate_drainage_staged_review_feedback(feedback.read_bytes())
    assert set(feedback_payload["checkpoint_submissions"]) == set(CHECKPOINT_IDS)
    feedback_record_path = next((run_root / "feedback").glob("*.json"))
    feedback_record = _read_json(feedback_record_path)
    published = run_root / "_artifacts" / feedback_record["public_artifact_refs"][0]["artifact_id"]
    assert feedback.read_bytes() == published.read_bytes()
    assert feedback_record["source_experience_id"] == "staged-full-correction-acquisition"
    assert not any(item["source_experience_id"] == "semantic-no-op-release-probe" for item in [feedback_record])

    structured_key = (structured_arm.arm_run_id, "semantic_no_op_release")
    expected_context = {"drainage-review-strategy.md": memory.read_text(encoding="utf-8")}
    assert adapter.contexts[structured_key] == [expected_context, expected_context, expected_context]
    assert all("not task evidence" in prompt for prompt in adapter.system_prompts if "learner_context" in prompt)
    assert not (structured_root / "states" / "structured-probe").exists()

    records = [record for arm in result.execution.arm_runs for record in arm.trial_records]
    assert len(records) == 5
    assert sum(record.cost.tokens_in or 0 for record in records if record.cost is not None) == 30
    assert sum(record.cost.tokens_out or 0 for record in records if record.cost is not None) == 15
    assert all(record.cost is not None and record.cost.estimated_cost_usd is None for record in records)


def _completed_acquisition_record(tmp_path: Path):  # noqa: ANN202
    package = compile_lifecycle(
        TEMPLATE_ID,
        tmp_path / "experience" / "package",
        variant_id="staged_full_correction",
    ).package_dir
    run = tmp_path / "experience" / "run"
    gold = _read_json(package / "hidden" / "gold-submissions.json")

    def resolve(context: dict) -> dict:
        output = Path(context["submission_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(gold[context["checkpoint_id"]]), encoding="utf-8")
        return {"status": "completed"}

    run_lifecycle(package, run, episode_environment=deterministic_episode_environment(resolve))
    verification = verify_drainage_model_lifecycle(package, run)
    record = make_trial_record(
        task_id=DRAINAGE_ACQUISITION_TASK_ID,
        input=TrialInput(
            instruction="Complete the drainage review lifecycle.",
            task_revision="test-package",
            task_kind="lifecycle",
        ),
        output=TrialOutput(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=str(run),
                output_format="evidence_lifecycle",
            ),
            terminated=True,
            final_reason="completed",
        ),
        evaluation=EvaluationResult(
            reward=verification["reward"],
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
                errors=["hidden evaluator detail"],
            ),
            breakdown={"lifecycle_gates": verification["gates"]},
        ),
    )
    return record, package, run


def _read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value
