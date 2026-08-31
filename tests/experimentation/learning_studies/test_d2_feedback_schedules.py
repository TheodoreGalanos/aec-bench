"""Targeted proofs for LS-07 feedback views and composed schedules."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ConsolidateStep,
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    ReleaseFeedbackStep,
    RunExperienceStep,
    StudyArmRole,
)
from aec_bench.contracts.trial_record import TrialInput, TrialOutput
from aec_bench.experimentation.learning_studies.errors import LearningStudyOrderInvalid
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleExecutionCondition,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
    resolve_lifecycle_learning_target,
)
from aec_bench.experimentation.learning_studies.planning import (
    CompiledExperienceStep,
    CompiledFeedbackStep,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.runtime import ExecuteExperienceRequest, ReleaseFeedbackRequest
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.runtime.lifecycle import run_lifecycle
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DRAINAGE_ACQUISITION_TASK_ID,
    DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
    DRAINAGE_PHASE_SUMMARY_FEEDBACK_VIEW_ID,
    DRAINAGE_TERMINAL_FEEDBACK_VIEW_ID,
    drainage_checkpoint_detailed_feedback,
    drainage_phase_summary_feedback,
    drainage_terminal_feedback,
    validate_drainage_checkpoint_detailed_feedback,
    validate_drainage_phase_summary_feedback,
    validate_drainage_terminal_feedback,
)
from aec_bench.lifecycles.stormwater_design.drainage_model import (
    TEMPLATE_ID,
    verify_drainage_model_lifecycle,
)
from tests.support.lifecycle_episode import deterministic_episode_environment
from tests.support.trial_record_factories import make_trial_record

_PROBE_TASK_ID = f"lifecycle/{TEMPLATE_ID}/semantic_no_op_release"
_CONDITION = LifecycleExecutionCondition(
    execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
    visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
)
_AGENT = AgentConfig(
    name="d2-feedback-test-agent",
    adapter="tool_loop",
    model="fixed-test-model",
    parameters={"max_turns_per_session": 5},
)
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512})


def _spec(
    steps: tuple[object, ...],
    *,
    experiences: tuple[LearningExperienceSpec, ...] | None = None,
) -> LearningStudySpec:
    return LearningStudySpec(
        study_id="d2-feedback-schedule",
        title="D2 feedback schedule",
        research_question="Can feedback schedules be composed from existing steps?",
        agent=_AGENT,
        compute=_COMPUTE,
        experiences=experiences
        or (
            LearningExperienceSpec(
                experience_id="acquisition",
                task_id=DRAINAGE_ACQUISITION_TASK_ID,
                role=ExperienceRole.ACQUISITION,
            ),
            LearningExperienceSpec(experience_id="probe", task_id=_PROBE_TASK_ID, role=ExperienceRole.PROBE),
        ),
        arms=(
            LearningArmSpec(
                arm_id="schedule",
                role=StudyArmRole.EXPOSURE,
                treatment_id="structured-memory",
                steps=steps,
            ),
        ),
    )


def _compile(steps: tuple[object, ...], *, experiences: tuple[LearningExperienceSpec, ...] | None = None):
    return compile_learning_study(
        study_run_id="d2-schedule-test",
        spec=_spec(steps, experiences=experiences),
        resolve_task=resolve_lifecycle_learning_target,
    )


@pytest.mark.parametrize(
    ("schedule", "steps"),
    (
        (
            "no-feedback",
            (
                RunExperienceStep(step_id="acq", experience_id="acquisition"),
                RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
            ),
        ),
        (
            "terminal-only",
            (
                RunExperienceStep(step_id="acq", experience_id="acquisition"),
                ReleaseFeedbackStep(
                    step_id="release",
                    source_experience_id="acquisition",
                    feedback_view_id=DRAINAGE_TERMINAL_FEEDBACK_VIEW_ID,
                ),
                ConsolidateStep(step_id="consolidate", feedback_step_ids=("release",), operation_id="memory"),
                RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
            ),
        ),
        (
            "immediate-checkpoint",
            (
                RunExperienceStep(step_id="acq", experience_id="acquisition"),
                ReleaseFeedbackStep(
                    step_id="release",
                    source_experience_id="acquisition",
                    feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
                ),
                ConsolidateStep(step_id="consolidate", feedback_step_ids=("release",), operation_id="memory"),
                RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
            ),
        ),
        (
            "summary-after-phase",
            (
                RunExperienceStep(step_id="acq", experience_id="acquisition"),
                ReleaseFeedbackStep(
                    step_id="release",
                    source_experience_id="acquisition",
                    feedback_view_id=DRAINAGE_PHASE_SUMMARY_FEEDBACK_VIEW_ID,
                ),
                ConsolidateStep(step_id="consolidate", feedback_step_ids=("release",), operation_id="memory"),
                RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
            ),
        ),
    ),
)
def test_named_feedback_schedule_compiles_through_planner(schedule: str, steps: tuple[object, ...]) -> None:
    plan = _compile(steps)
    assert plan.arm_runs[0].steps
    assert schedule in {"no-feedback", "terminal-only", "immediate-checkpoint", "summary-after-phase"}


def test_delayed_checkpoint_feedback_compiles_after_multiple_acquisitions() -> None:
    experiences = (
        LearningExperienceSpec(
            experience_id="acquisition-1",
            task_id=DRAINAGE_ACQUISITION_TASK_ID,
            role=ExperienceRole.ACQUISITION,
        ),
        LearningExperienceSpec(
            experience_id="acquisition-2",
            task_id=DRAINAGE_ACQUISITION_TASK_ID,
            role=ExperienceRole.PRACTICE,
        ),
        LearningExperienceSpec(experience_id="probe", task_id=_PROBE_TASK_ID, role=ExperienceRole.PROBE),
    )
    plan = _compile(
        (
            RunExperienceStep(step_id="acq-1", experience_id="acquisition-1"),
            RunExperienceStep(step_id="acq-2", experience_id="acquisition-2"),
            ReleaseFeedbackStep(
                step_id="release-1",
                source_experience_id="acquisition-1",
                feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
            ),
            ReleaseFeedbackStep(
                step_id="release-2",
                source_experience_id="acquisition-2",
                feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
            ),
            ConsolidateStep(
                step_id="consolidate",
                feedback_step_ids=("release-1", "release-2"),
                operation_id="memory",
            ),
            RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
        ),
        experiences=experiences,
    )
    assert [step.step_id for step in plan.arm_runs[0].steps] == [
        "acq-1",
        "acq-2",
        "release-1",
        "release-2",
        "consolidate",
        "probe",
    ]


def test_planner_rejects_duplicate_source_and_feedback_view_pair() -> None:
    steps = (
        RunExperienceStep(step_id="acq", experience_id="acquisition"),
        ReleaseFeedbackStep(
            step_id="release-1",
            source_experience_id="acquisition",
            feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
        ),
        ReleaseFeedbackStep(
            step_id="release-2",
            source_experience_id="acquisition",
            feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
        ),
    )
    with pytest.raises(LearningStudyOrderInvalid, match="feedback view was already released"):
        _compile(steps)


def test_immediate_and_delayed_arms_use_same_tasks_but_different_release_timing() -> None:
    experiences = (
        LearningExperienceSpec(
            experience_id="acquisition",
            task_id=DRAINAGE_ACQUISITION_TASK_ID,
            role=ExperienceRole.ACQUISITION,
        ),
        LearningExperienceSpec(
            experience_id="acquisition-repeat",
            task_id=DRAINAGE_ACQUISITION_TASK_ID,
            role=ExperienceRole.PRACTICE,
        ),
        LearningExperienceSpec(experience_id="probe", task_id=_PROBE_TASK_ID, role=ExperienceRole.PROBE),
    )
    immediate = _compile(
        (
            RunExperienceStep(step_id="acq", experience_id="acquisition"),
            ReleaseFeedbackStep(
                step_id="release",
                source_experience_id="acquisition",
                feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
            ),
            RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
        ),
        experiences=experiences,
    )
    delayed = _compile(
        (
            RunExperienceStep(step_id="acq-1", experience_id="acquisition"),
            RunExperienceStep(step_id="acq-2", experience_id="acquisition-repeat"),
            ReleaseFeedbackStep(
                step_id="release-1",
                source_experience_id="acquisition",
                feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
            ),
            ReleaseFeedbackStep(
                step_id="release-2",
                source_experience_id="acquisition-repeat",
                feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
            ),
            RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
        ),
        experiences=experiences,
    )
    immediate_steps = immediate.arm_runs[0].steps
    delayed_steps = delayed.arm_runs[0].steps
    assert [step.step_id for step in immediate_steps] == ["acq", "release", "probe"]
    assert [step.step_id for step in delayed_steps] == ["acq-1", "acq-2", "release-1", "release-2", "probe"]
    assert all(
        isinstance(step, CompiledExperienceStep) and step.trial.task_id == DRAINAGE_ACQUISITION_TASK_ID
        for step in delayed_steps[:2]
    )
    assert isinstance(immediate_steps[1], CompiledFeedbackStep)
    assert isinstance(delayed_steps[2], CompiledFeedbackStep)


def _completed_acquisition_record(tmp_path: Path):  # noqa: ANN202
    package = compile_lifecycle(
        TEMPLATE_ID,
        tmp_path / "experience" / "package",
        variant_id="staged_full_correction",
    ).package_dir
    run = tmp_path / "experience" / "run"
    gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

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
            task_revision="test",
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
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={"lifecycle_gates": verification["gates"]},
        ),
    )
    return record


def test_drainage_feedback_views_have_distinct_detail_levels_and_safe_allowlists(tmp_path: Path) -> None:
    record = _completed_acquisition_record(tmp_path)
    detailed = drainage_checkpoint_detailed_feedback(record)
    phase = drainage_phase_summary_feedback(record)
    terminal = drainage_terminal_feedback(record)

    detailed_payload = validate_drainage_checkpoint_detailed_feedback(detailed)
    phase_payload = validate_drainage_phase_summary_feedback(phase)
    terminal_payload = validate_drainage_terminal_feedback(terminal)
    assert set(detailed_payload["checkpoints"]) == {"initial_review", "response_review", "closeout_review"}
    assert all("review_matrix" in item and "gate_scores" in item for item in detailed_payload["checkpoints"].values())
    assert set(phase_payload["phases"]) == {"evidence_assessment", "response_and_closeout"}
    assert "checkpoints" not in phase_payload
    assert "checkpoints" not in terminal_payload
    assert "canonical_reward" in terminal_payload["terminal_outcome"]
    for data in (detailed, phase, terminal):
        text = data.decode()
        assert "gold-submissions" not in text
        assert "verifier-config" not in text
        assert "expected_answer" not in text
        assert str(tmp_path) not in text

    with pytest.raises(ValueError, match="fields do not match"):
        validate_drainage_checkpoint_detailed_feedback(detailed.replace(b'"checkpoints":', b'"private_path":'))
    with pytest.raises(ValueError, match="fields do not match"):
        validate_drainage_phase_summary_feedback(phase.replace(b'"phases":', b'"gold":'))


class _GoldLifecycleAdapterBuilder:
    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        package = Path(kwargs["workspace"]).parent.parent / "package"
        gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))

        class _Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(gold[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="fixed-test-model",
                    configuration_record={"model": "fixed-test-model"},
                    agent_output=SimpleNamespace(status=SimpleNamespace(value="completed")),
                    transcript=[],
                    raw_output_text=None,
                    provider_error=None,
                    failure_kind=None,
                    usage_input_tokens=1,
                    usage_output_tokens=1,
                    usage_cache_read_tokens=0,
                    usage_cache_write_tokens=0,
                )

        return _Adapter()


def test_new_feedback_view_flows_through_coordinator_after_acquisition(tmp_path: Path) -> None:
    plan = _compile(
        (
            RunExperienceStep(step_id="acq", experience_id="acquisition"),
            ReleaseFeedbackStep(
                step_id="release",
                source_experience_id="acquisition",
                feedback_view_id=DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID,
            ),
        )
    )
    binding = build_lifecycle_learning_operations(
        run_root=tmp_path / "study",
        execution_condition=_CONDITION,
        treatment_kinds={"structured-memory": LifecycleLearningTreatmentKind.STRUCTURED_MEMORY},
        feedback_projectors={DRAINAGE_CHECKPOINT_DETAILED_FEEDBACK_VIEW_ID: drainage_checkpoint_detailed_feedback},
        adapter_builder=_GoldLifecycleAdapterBuilder(),
    )
    arm_run = plan.arm_runs[0]
    state = binding.operations.initialise_learner(arm_run)
    experience_step, feedback_step = arm_run.steps
    assert isinstance(experience_step, CompiledExperienceStep)
    assert isinstance(feedback_step, CompiledFeedbackStep)
    execution = binding.operations.execute_experience(
        ExecuteExperienceRequest(arm_run=arm_run, step=experience_step, state=state)
    )
    released = binding.operations.release_feedback(
        ReleaseFeedbackRequest(
            arm_run=arm_run,
            step=feedback_step,
            state=execution.candidate_state,
            source_trial_record=execution.trial_record,
        )
    )
    assert released.feedback.value.path.read_bytes() == drainage_checkpoint_detailed_feedback(execution.trial_record)
    assert released.feedback.value.artifact.size_bytes == released.feedback.value.path.stat().st_size
