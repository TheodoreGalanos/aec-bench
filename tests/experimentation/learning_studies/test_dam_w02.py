# ABOUTME: Proves safe dam feedback, named projections, and the complete deterministic W02 slice.
# ABOUTME: Verifies truthful assessment evidence, probe isolation, and relation-review downgrades.

from __future__ import annotations

import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.contracts.trial_record import EvaluationStatus, TrialOutput, TrialRecord
from aec_bench.experimentation.learning_studies.dam_w02 import (
    DAM_W02_ACQUISITION_TASK_ID,
    DAM_W02_CONSOLIDATION_OPERATION_ID,
    DAM_W02_PROBE_TASK_ID,
    DAM_W02_STUDY_ID,
    build_w02_acquisition_fidelity,
    compile_w02_dam_study,
    load_w02_dam_protocol,
    run_w02_dam_study_sync,
    w02_dam_outcome_projections,
)
from aec_bench.experimentation.learning_studies.planning import CompiledExperienceStep, CompiledFeedbackStep
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunExecutionResult,
    ArmRunStatus,
    LearningStudyExecution,
    ReleaseFeedbackRequest,
)
from aec_bench.experimentation.learning_studies.worlds import (
    WorldConsolidationContext,
    WorldLearningExecutionCondition,
    WorldLearningTreatmentKind,
    build_world_learning_operations,
)
from aec_bench.harness.dam_seepage_trial import run_dam_seepage_trial
from aec_bench.harness.prime_world_actor import run_prime_world_actor_session
from aec_bench.worlds.monitoring.dam_seepage.dam_learning import (
    DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID,
    dam_escalation_boundary_feedback,
    validate_dam_escalation_boundary_feedback,
)
from aec_bench.worlds.monitoring.dam_seepage.variants import (
    dam_seepage_profile_variants,
    validate_dam_seepage_profile_variant,
)
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID, SeepageAction
from tests.support.trial_record_factories import make_trial_record

_COMPUTE = ComputeConfig(backend="local")
_CONDITION = WorldLearningExecutionCondition(
    actor=run_prime_world_actor_session,
    actor_binding_label="prime-fake-executable",
)
_ROUTINE_ACTIONS = [
    {"action_name": SeepageAction.CHECK_MEASUREMENT_SYSTEM.value, "arguments": {}, "request_id": "check"},
    {"action_name": SeepageAction.RECORD_CONFIRMATION_READING.value, "arguments": {}, "request_id": "reading-2"},
    {"action_name": SeepageAction.RECORD_CONFIRMATION_READING.value, "arguments": {}, "request_id": "reading-3"},
    {"action_name": SeepageAction.RECORD_CONFIRMATION_READING.value, "arguments": {}, "request_id": "reading-4"},
    {"action_name": SeepageAction.INSPECT_DOWNSTREAM_AREA.value, "arguments": {}, "request_id": "inspect"},
    {"action_name": SeepageAction.CONTINUE_ROUTINE_SURVEILLANCE.value, "arguments": {}, "request_id": "submit"},
]
_ACQUISITION_ACTIONS = [
    {"action_name": SeepageAction.CHECK_MEASUREMENT_SYSTEM.value, "arguments": {}, "request_id": "check"},
    {
        "action_name": SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
        "arguments": {},
        "request_id": "escalate",
    },
]


async def _instrument_aware_actor_session(**kwargs: Any):  # noqa: ANN202
    trial = kwargs["trial"]
    actions = _ACQUISITION_ACTIONS if trial.task_id == DAM_W02_ACQUISITION_TASK_ID else _ROUTINE_ACTIONS
    environment = {
        **trial.agent.parameters["environment"],
        "FAKE_WORLD_ACTIONS": json.dumps(actions),
    }
    agent = trial.agent.model_copy(update={"parameters": {**trial.agent.parameters, "environment": environment}})
    return await run_prime_world_actor_session(**{**kwargs, "trial": replace(trial, agent=agent)})


_INSTRUMENT_AWARE_CONDITION = WorldLearningExecutionCondition(
    actor=_instrument_aware_actor_session,
    actor_binding_label=_CONDITION.actor_binding_label,
)


_PROJECTION_IDS = {
    "world.canonical-reward",
    "dam.response-correct",
    "dam.evidence-complete",
}


def _agent(
    tmp_path: Path,
    *,
    isolation: str = "development_same_user",
) -> AgentConfig:
    from tests.prime_agent.test_acp import _fake_prime_agent

    return AgentConfig(
        name="prime",
        adapter="prime-agent",
        model="anthropic/test",
        parameters={
            "isolation": isolation,
            "max_world_actions": 10,
            "max_model_calls": 10,
            "max_tokens": 1_000,
            "max_cost_usd": "10",
            "max_wall_seconds": 5,
            "executable": str(_fake_prime_agent(tmp_path)),
            "environment": {
                **os.environ,
                "FAKE_ACP_SCENARIO": "world",
                "FAKE_WORLD_ACTIONS": json.dumps(_ROUTINE_ACTIONS),
            },
        },
    )


class _DeclaredDamMemoryConsolidator:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, context: WorldConsolidationContext) -> None:
        self.calls += 1
        assert len(context.feedback) == 1
        feedback = validate_dam_escalation_boundary_feedback(context.feedback[0].path.read_bytes())
        principles = "\n".join(f"- {item}" for item in feedback["monitoring_discipline_principles"])
        (context.memory_root / "dam-monitoring-strategy.md").write_text(
            f"# Dam monitoring strategy\n\n{principles}\n",
            encoding="utf-8",
        )


def _completed_acquisition_record(tmp_path: Path):  # noqa: ANN202
    evidence_path = tmp_path / "world-evidence" / "dam-world-evidence.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    actions = [
        SeepageAction.CHECK_MEASUREMENT_SYSTEM.value,
        SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
    ]
    evidence_path.write_text(
        json.dumps({"actions": actions, "status": "terminated", "replay_valid": True}),
        encoding="utf-8",
    )
    return make_trial_record(
        task_id=DAM_W02_ACQUISITION_TASK_ID,
        output=TrialOutput(
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=str(evidence_path),
                output_format="json",
            ),
        ),
        evaluation=EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={
                "assessment_submitted": True,
                "selected_response": "engineering-review",
                "required_response": "engineering-review",
                "response_correct": True,
                "all_scheduled_readings_reviewed": False,
                "measurement_system_checked": True,
                "latest_downstream_area_inspected": False,
                "evidence_complete": True,
                "successful": True,
            },
        ),
    )


def test_all_registered_dam_profiles_validate_including_w02_probe() -> None:
    variants = dam_seepage_profile_variants()

    assert [variant.profile_id for variant in variants] == [
        "unreliable-instrument-escalation",
        "reliable-routine-surveillance",
        "unreliable-instrument-surface-transfer",
    ]
    assert validate_dam_seepage_profile_variant(variants[2]).profile_id == "unreliable-instrument-surface-transfer"
    for variant in variants:
        scenario = validate_dam_seepage_profile_variant(variant)
        assert scenario.profile_id == variant.profile_id


def test_w02_protocol_declares_exact_tasks_arms_treatments_and_measurements() -> None:
    agent = AgentConfig(name="prime", adapter="prime-agent", model="anthropic/test", parameters={})
    spec = load_w02_dam_protocol(agent=agent, compute=_COMPUTE)
    plan = compile_w02_dam_study(study_run_id="w02-protocol-test", agent=agent, compute=_COMPUTE)

    assert spec.study_id == DAM_W02_STUDY_ID
    assert [item.task_id for item in spec.experiences] == [
        DAM_W02_ACQUISITION_TASK_ID,
        DAM_W02_PROBE_TASK_ID,
    ]
    assert [(item.arm_id, item.role.value, item.treatment_id) for item in spec.arms] == [
        ("cold-reset", "control", "reset"),
        ("reset-after-acquisition", "control", "reset"),
        ("structured-memory", "exposure", "structured-memory"),
    ]
    assert {item.projection_id for item in spec.measurements} == _PROJECTION_IDS
    assert spec.relations[0].relation_id == "unreliable-instrument-escalation-to-surface-transfer"
    structured_steps = spec.arms[2].steps
    assert structured_steps[1].feedback_view_id == DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID
    assert structured_steps[2].operation_id == DAM_W02_CONSOLIDATION_OPERATION_ID
    assert all(isinstance(item, type(plan.arm_runs[0])) for item in plan.arm_runs)


def test_dam_feedback_selects_only_public_evidence_and_rejects_forbidden_fields(tmp_path: Path) -> None:
    record = _completed_acquisition_record(tmp_path)

    data = dam_escalation_boundary_feedback(record)
    payload = validate_dam_escalation_boundary_feedback(data)

    assert payload["trial_id"] == record.trial_id
    assert payload["task_id"] == DAM_W02_ACQUISITION_TASK_ID
    assert payload["action_sequence"] == [
        SeepageAction.CHECK_MEASUREMENT_SYSTEM.value,
        SeepageAction.ESCALATE_FOR_ENGINEERING_REVIEW.value,
    ]
    assert payload["selected_response"] == "engineering-review"
    assert payload["evaluation_outcomes"] == {
        "response_correct": True,
        "evidence_complete": True,
        "all_scheduled_readings_reviewed": False,
        "measurement_system_checked": True,
        "latest_downstream_area_inspected": False,
    }
    assert payload["terminal_outcome"]["canonical_reward"] == 1.0
    assert payload["terminal_outcome"]["validity"] == {
        "output_parseable": True,
        "schema_valid": True,
        "verifier_completed": True,
    }

    text = data.decode()
    assert "required_response" not in text
    assert "instrument_condition" not in text
    assert "visual_alert_conditions" not in text
    assert "required_consecutive_alert_readings" not in text
    assert str(tmp_path) not in text

    # Leakage regression: fails if the scenario's gold answer is reintroduced into the payload.
    leaked = json.loads(data)
    leaked["required_response"] = "routine-surveillance"
    with pytest.raises(ValueError, match="dam-feedback-forbidden-field-detected"):
        validate_dam_escalation_boundary_feedback(json.dumps(leaked).encode())

    with pytest.raises(ValueError, match="dam-feedback-source-mismatch"):
        dam_escalation_boundary_feedback(make_trial_record(task_id="unrelated/task"))
    incomplete = record.model_copy(update={"execution_status": "failed"})
    with pytest.raises(ValueError, match="dam-feedback-projection-failed"):
        dam_escalation_boundary_feedback(incomplete)
    unavailable = record.model_copy(update={"evaluation_status": "not_requested", "evaluation": None})
    with pytest.raises(ValueError, match="dam-feedback-projection-failed"):
        dam_escalation_boundary_feedback(unavailable)

    evidence_path = Path(record.output.agent_output.output_path)  # type: ignore[union-attr]
    evidence_path.write_text(json.dumps({"status": "terminated"}), encoding="utf-8")
    with pytest.raises(ValueError, match="dam-feedback-projection-failed"):
        dam_escalation_boundary_feedback(record)


def test_dam_adapter_rejects_unsafe_feedback_before_state_or_artifact_write(tmp_path: Path) -> None:
    plan = compile_w02_dam_study(
        study_run_id="w02-unsafe-feedback",
        agent=_agent(tmp_path),
        compute=_COMPUTE,
    )
    arm_run = next(item for item in plan.arm_runs if item.arm_id == "structured-memory")
    feedback_step = next(item for item in arm_run.steps if isinstance(item, CompiledFeedbackStep))
    run_root = tmp_path / "study"
    binding = build_world_learning_operations(
        run_root=run_root,
        world_id=DAM_SEEPAGE_TASK_WORLD_ID,
        execution_condition=_CONDITION,
        run_trial=run_dam_seepage_trial,
        instructions={DAM_W02_ACQUISITION_TASK_ID: "Monitor.", DAM_W02_PROBE_TASK_ID: "Monitor."},
        treatment_kinds={"structured-memory": WorldLearningTreatmentKind.STRUCTURED_MEMORY},
        feedback_projectors={
            DAM_ESCALATION_BOUNDARY_FEEDBACK_VIEW_ID: lambda _record: b'{"private_path":"/private/secret"}\n'
        },
        consolidation_operations={DAM_W02_CONSOLIDATION_OPERATION_ID: _DeclaredDamMemoryConsolidator()},
    )
    state = binding.operations.initialise_learner(arm_run)

    with pytest.raises(ValueError, match="feedback-projection-unsafe"):
        binding.operations.release_feedback(
            ReleaseFeedbackRequest(
                arm_run=arm_run,
                step=feedback_step,
                state=state,
                source_trial_record=make_trial_record(task_id=DAM_W02_ACQUISITION_TASK_ID),
            )
        )

    assert not (state.value.root.parent / feedback_step.step_id).exists()
    assert not any(path.is_file() for path in (run_root / "_artifacts").rglob("*"))


def test_required_w02_projections_are_bounded_and_missing_evidence_is_ineligible() -> None:
    projections = w02_dam_outcome_projections()
    assert set(projections) == _PROJECTION_IDS

    correct = make_trial_record(
        task_id=DAM_W02_PROBE_TASK_ID,
        evaluation=EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={
                "assessment_submitted": True,
                "selected_response": "engineering-review",
                "required_response": "engineering-review",
                "response_correct": True,
                "all_scheduled_readings_reviewed": False,
                "measurement_system_checked": True,
                "latest_downstream_area_inspected": False,
                "evidence_complete": True,
                "successful": True,
            },
        ),
    )
    for projection in projections.values():
        result = projection(correct)
        assert result.eligible is True
        assert (result.lower_bound, result.upper_bound) == (0.0, 1.0)
    assert projections["world.canonical-reward"](correct).value == 1.0
    assert projections["dam.response-correct"](correct).value == 1.0
    assert projections["dam.evidence-complete"](correct).value == 1.0

    failure = make_trial_record(
        task_id=DAM_W02_PROBE_TASK_ID,
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={
                "assessment_submitted": True,
                "selected_response": "routine-surveillance",
                "required_response": "engineering-review",
                "response_correct": False,
                "all_scheduled_readings_reviewed": False,
                "measurement_system_checked": True,
                "latest_downstream_area_inspected": False,
                "evidence_complete": False,
                "successful": False,
            },
        ),
    )
    assert projections["dam.response-correct"](failure).value == 0.0
    assert projections["dam.evidence-complete"](failure).value == 0.0
    assert projections["world.canonical-reward"](failure).value == 0.0

    for projection_id, projection in projections.items():
        mismatch = projection(make_trial_record(task_id="unrelated/task"))
        assert mismatch.eligible is False and mismatch.value is None
        assert mismatch.reason is not None and mismatch.reason.startswith("projection-task-mismatch")

        no_evaluation = projection(
            make_trial_record(
                task_id=DAM_W02_PROBE_TASK_ID,
                evaluation=None,
                evaluation_status=EvaluationStatus.NOT_REQUESTED,
            )
        )
        assert no_evaluation.eligible is False and no_evaluation.value is None

        invalid_replay = projection(
            make_trial_record(
                task_id=DAM_W02_PROBE_TASK_ID,
                evaluation=EvaluationResult(
                    reward=0.0,
                    validity=ValidityCheck(output_parseable=True, schema_valid=False, verifier_completed=False),
                    breakdown={"assessment_submitted": True},
                ),
            )
        )
        assert invalid_replay.eligible is False and invalid_replay.value is None

        no_submission = projection(
            make_trial_record(
                task_id=DAM_W02_PROBE_TASK_ID,
                evaluation=EvaluationResult(
                    reward=0.0,
                    validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
                    breakdown={"assessment_submitted": False},
                ),
            )
        )
        if projection_id != "world.canonical-reward":
            assert no_submission.eligible is False and no_submission.value is None


def test_acquisition_fidelity_fails_closed_on_missing_or_ambiguous_records() -> None:
    agent = AgentConfig(name="prime", adapter="prime-agent", model="anthropic/test", parameters={})
    plan = compile_w02_dam_study(study_run_id="w02-fidelity-inputs", agent=agent, compute=_COMPUTE)
    arm_run = next(item for item in plan.arm_runs if item.arm_id == "structured-memory")
    acquisition_step = next(
        item for item in arm_run.steps if isinstance(item, CompiledExperienceStep) and item.role.value == "acquisition"
    )

    def arm_result(records: tuple[TrialRecord, ...]) -> ArmRunExecutionResult[object]:
        return ArmRunExecutionResult(
            arm_run_id=arm_run.arm_run_id,
            status=ArmRunStatus.COMPLETED,
            initial_state_id="initial",
            completed_steps=(),
            trial_records=records,
            final_state_id="final",
            failure=None,
        )

    missing = build_w02_acquisition_fidelity(
        plan=plan,
        execution=LearningStudyExecution(
            study_run_id=plan.study_run_id,
            arm_runs=(arm_result(()),),
        ),
    )
    assert missing[arm_run.arm_run_id].trial_record_present is False
    assert missing[arm_run.arm_run_id].acquisition_successful is False

    record = make_trial_record(
        task_id=DAM_W02_ACQUISITION_TASK_ID,
        trial_id=acquisition_step.trial.trial_id,
    )
    malformed = make_trial_record(
        task_id=DAM_W02_ACQUISITION_TASK_ID,
        trial_id=acquisition_step.trial.trial_id,
        evaluation=EvaluationResult(
            reward=1.0,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={
                "response_correct": 1,
                "evidence_complete": True,
                "selected_response": "engineering-review",
            },
        ),
    )
    malformed_result = build_w02_acquisition_fidelity(
        plan=plan,
        execution=LearningStudyExecution(
            study_run_id=plan.study_run_id,
            arm_runs=(arm_result((malformed,)),),
        ),
    )
    assert malformed_result[arm_run.arm_run_id].response_correct is None
    assert malformed_result[arm_run.arm_run_id].acquisition_successful is False

    with pytest.raises(ValueError, match="acquisition-fidelity-ambiguous"):
        build_w02_acquisition_fidelity(
            plan=plan,
            execution=LearningStudyExecution(
                study_run_id=plan.study_run_id,
                arm_runs=(arm_result((record, record)),),
            ),
        )
    with pytest.raises(ValueError, match="acquisition-fidelity-ambiguous"):
        build_w02_acquisition_fidelity(
            plan=plan,
            execution=LearningStudyExecution(
                study_run_id=plan.study_run_id,
                arm_runs=(arm_result((record,)), arm_result((record,))),
            ),
        )


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="execution_status is only benchmark-complete under the macOS Seatbelt boundary",
)
def test_deterministic_w02_runs_all_arms_and_builds_truthful_assessment_evidence(tmp_path: Path) -> None:
    run_root = tmp_path / "w02"
    consolidator = _DeclaredDamMemoryConsolidator()
    agent = _agent(tmp_path, isolation="macos_sandbox")

    result = run_w02_dam_study_sync(
        run_root=run_root,
        study_run_id="w02-deterministic",
        agent=agent,
        compute=_COMPUTE,
        execution_condition=_INSTRUMENT_AWARE_CONDITION,
        consolidation_operation=consolidator,
    )

    assert consolidator.calls == 1
    assert all(arm.status is ArmRunStatus.COMPLETED for arm in result.execution.arm_runs)
    assert len({item.initial_state_equivalence_id for item in result.arm_evidence.values()}) == 1
    assert all(item.adapter_id == _CONDITION.adapter_id for item in result.arm_evidence.values())
    assert all(item.arm_isolated for item in result.arm_evidence.values())
    assert all(item.lineage_complete for item in result.arm_evidence.values())
    assert all(item.probe_feedback_hidden for item in result.arm_evidence.values())
    assert all(item.probe_state_discarded for item in result.arm_evidence.values())
    assert all(not item.hidden_evaluation_leaked for item in result.arm_evidence.values())
    assert set(result.acquisition_fidelity) == {
        arm.arm_run_id for arm in result.plan.arm_runs if arm.arm_id in {"reset-after-acquisition", "structured-memory"}
    }
    assert all(
        item.trial_record_present
        and item.replay_valid is True
        and item.response_correct is True
        and item.evidence_complete is True
        and item.escalation_selected is True
        and item.acquisition_successful
        and item.fidelity_satisfied
        for item in result.acquisition_fidelity.values()
    )

    assert all(
        measurement.validity is LearningComparisonValidity.DESCRIPTIVE_ONLY
        for measurement in result.unreviewed_assessment.measurements
    )
    reviewed = {item.measurement_id: item for item in result.reviewed_assessment.measurements}
    for measurement_id, measurement in reviewed.items():
        expected_validity = (
            LearningComparisonValidity.DESCRIPTIVE_ONLY
            if measurement_id.startswith("reset-after-acquisition-")
            else LearningComparisonValidity.CONTROLLED
        )
        assert measurement.validity is expected_validity
        assert len(measurement.included_pairs) == 1
        assert measurement.excluded_repetitions == ()

    structured_arm = next(item for item in result.plan.arm_runs if item.arm_id == "structured-memory")
    structured_root = run_root / "learner-arms" / structured_arm.arm_run_id
    final_state = structured_root / "states" / "consolidate-monitoring-method"
    memory = final_state / "memory" / "dam-monitoring-strategy.md"
    feedback = final_state / "feedback" / "release-acquisition-feedback.json"
    assert memory.is_file()
    feedback_payload = validate_dam_escalation_boundary_feedback(feedback.read_bytes())
    assert feedback_payload["task_id"] == DAM_W02_ACQUISITION_TASK_ID

    feedback_record_path = next((run_root / "feedback").glob("*.json"))
    feedback_record = json.loads(feedback_record_path.read_text(encoding="utf-8"))
    published = run_root / "_artifacts" / feedback_record["public_artifact_refs"][0]["artifact_id"]
    assert feedback.read_bytes() == published.read_bytes()
    assert feedback_record["source_experience_id"] == "unreliable-instrument-escalation-acquisition"
    assert not any(
        item["source_experience_id"] == "unreliable-instrument-surface-transfer-probe" for item in [feedback_record]
    )
    assert not (structured_root / "states" / "structured-probe").exists()

    records = [record for arm in result.execution.arm_runs for record in arm.trial_records]
    assert len(records) == 5
