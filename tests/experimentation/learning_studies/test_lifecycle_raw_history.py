from __future__ import annotations

import asyncio
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study import (
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    ReleaseFeedbackStep,
    RunExperienceStep,
    StudyArmRole,
)
from aec_bench.experimentation.learning_studies import lifecycles
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleExecutionCondition,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
    resolve_lifecycle_learning_target,
)
from aec_bench.experimentation.learning_studies.planning import compile_learning_study
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.resume import load_resumable_study
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunStatus,
    ExecuteExperienceRequest,
    run_learning_study,
)
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DRAINAGE_ACQUISITION_TASK_ID,
    DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
    drainage_staged_review_feedback,
)
from aec_bench.lifecycles.stormwater_design.drainage_model import CHECKPOINT_IDS
from tests.support.trial_record_factories import make_trial_record

_CONDITION = LifecycleExecutionCondition(
    execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
    visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
)
_AGENT = AgentConfig(name="raw-history-test-agent", adapter="tool_loop", model="fixed-test-model", parameters={})
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)
_ACQUISITION_TASK = DRAINAGE_ACQUISITION_TASK_ID
_PROBE_TASK = "lifecycle/drainage-model-evidence-lifecycle-review/semantic_no_op_release"


def _plan():
    spec = LearningStudySpec(
        study_id="raw-history-coordinator",
        title="Raw history coordinator integration",
        research_question="Does raw history remain isolated and resumable?",
        agent=_AGENT,
        compute=_COMPUTE,
        repetitions=1,
        experiences=(
            LearningExperienceSpec(
                experience_id="acquisition", task_id=_ACQUISITION_TASK, role=ExperienceRole.ACQUISITION
            ),
            LearningExperienceSpec(experience_id="probe", task_id=_PROBE_TASK, role=ExperienceRole.PROBE),
        ),
        arms=(
            LearningArmSpec(
                arm_id="raw-history",
                role=StudyArmRole.EXPOSURE,
                treatment_id="raw-history",
                steps=(
                    RunExperienceStep(step_id="acquisition", experience_id="acquisition", commit_post_state=True),
                    ReleaseFeedbackStep(
                        step_id="release-feedback",
                        source_experience_id="acquisition",
                        feedback_view_id=DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
                    ),
                    RunExperienceStep(step_id="probe", experience_id="probe", commit_post_state=False),
                ),
            ),
        ),
    )
    return compile_learning_study(
        study_run_id="raw-history-coordinator-run", spec=spec, resolve_task=resolve_lifecycle_learning_target
    )


class _RawHistoryAdapterBuilder:
    def __init__(self) -> None:
        self.executions = 0
        self.contexts: list[dict[str, str]] = []

    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        package = workspace.parent.parent / "package"
        submissions = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        builder = self
        native_tools = {tool.__name__: tool for tool in kwargs["native_tools"]}

        class _Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                builder.executions += 1
                root = json.loads(native_tools["list_workspace"]("."))
                observed: dict[str, str] = {}
                if "learner_context" in root["entries"]:
                    for channel in json.loads(native_tools["list_workspace"]("learner_context"))["entries"]:
                        for name in json.loads(native_tools["list_workspace"](f"learner_context/{channel}"))["entries"]:
                            item = json.loads(
                                native_tools["read_workspace_file"](f"learner_context/{channel}/{name}")
                            )
                            observed[f"{channel}/{name}"] = item["content"]
                builder.contexts.append(observed)
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(submissions[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="fixed-test-model",
                    configuration_record={"model": "fixed-test-model"},
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


class _InterruptedAfterFeedback(BaseException):
    pass


class _InterruptingRecorder(StudyRunRecorder):
    def step_committed(self, arm_run, step, result, state_before, candidate_state, committed_state):  # noqa: ANN001, ANN201
        super().step_committed(arm_run, step, result, state_before, candidate_state, committed_state)
        if step.step_id == "release-feedback":
            raise _InterruptedAfterFeedback


def _raw_binding(run_root: Path, adapter: _RawHistoryAdapterBuilder):
    return build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=_CONDITION,
        treatment_kinds={"raw-history": LifecycleLearningTreatmentKind.RAW_HISTORY},
        feedback_projectors={DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID: drainage_staged_review_feedback},
        adapter_builder=adapter,
    )


def test_raw_history_coordinator_runs_acquisition_release_probe_and_discards_probe(tmp_path: Path) -> None:
    plan = _plan()
    adapter = _RawHistoryAdapterBuilder()
    run_root = tmp_path / "study"
    binding = _raw_binding(run_root, adapter)
    recorder = StudyRunRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )

    result = asyncio.run(run_learning_study(plan=plan, operations=binding.operations, observer=recorder))

    assert result.arm_runs[0].status is ArmRunStatus.COMPLETED
    assert adapter.executions == 6
    assert len(adapter.contexts) == 6
    assert adapter.contexts[:3] == [{}, {}, {}]
    assert set(adapter.contexts[3]) == {
        f"history/{lifecycles._RAW_HISTORY_FILENAME}",
        "feedback/release-feedback.json",
    }
    assert adapter.contexts[3:] == [adapter.contexts[3]] * 3
    arm_root = run_root / "learner-arms" / plan.arm_runs[0].arm_run_id
    final_state = arm_root / "states" / "release-feedback"
    assert list((final_state / "memory").iterdir()) == []
    assert (final_state / "history" / lifecycles._RAW_HISTORY_FILENAME).is_file()
    assert (final_state / "feedback" / "release-feedback.json").is_file()
    assert not (arm_root / "states" / "probe").exists()


def test_raw_history_resume_restores_without_reprojecting_and_rejects_cross_arm_state(tmp_path: Path) -> None:
    plan = _plan()
    adapter = _RawHistoryAdapterBuilder()
    run_root = tmp_path / "study"
    projector_calls = 0

    def counted_projector(record):  # noqa: ANN001
        nonlocal projector_calls
        projector_calls += 1
        return drainage_staged_review_feedback(record)

    binding = build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=_CONDITION,
        treatment_kinds={"raw-history": LifecycleLearningTreatmentKind.RAW_HISTORY},
        feedback_projectors={DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID: counted_projector},
        adapter_builder=adapter,
    )
    recorder = _InterruptingRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )
    with pytest.raises(_InterruptedAfterFeedback):
        asyncio.run(run_learning_study(plan=plan, operations=binding.operations, observer=recorder))

    resumed_binding = build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=_CONDITION,
        treatment_kinds={"raw-history": LifecycleLearningTreatmentKind.RAW_HISTORY},
        feedback_projectors={DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID: counted_projector},
        adapter_builder=adapter,
        resume_existing_run=True,
    )
    resumable = load_resumable_study(
        root=run_root,
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=resumed_binding.snapshot_state,
        restore_state=resumed_binding.restore_state,
        restore_feedback=resumed_binding.restore_feedback,
        feedback_artifacts=resumed_binding.feedback_artifacts,
    )
    resumed = asyncio.run(
        run_learning_study(
            plan=plan,
            operations=resumed_binding.operations,
            observer=resumable.recorder,
            resume=resumable.resume,
        )
    )
    assert resumed.arm_runs[0].status is ArmRunStatus.COMPLETED
    assert projector_calls == 1
    assert adapter.executions == 6

    first_arm = plan.arm_runs[0]
    foreign_arm = type(first_arm)(
        arm_run_id="foreign-arm",
        arm_id="foreign-arm",
        arm_role=first_arm.arm_role,
        treatment_id="raw-history",
        repetition=first_arm.repetition,
        steps=first_arm.steps,
    )
    foreign_state = resumed_binding.operations.initialise_learner(foreign_arm)
    step = first_arm.steps[0]
    with pytest.raises(ValueError, match="cross-arm-path-detected"):
        resumed_binding.operations.execute_experience(
            ExecuteExperienceRequest(arm_run=first_arm, step=step, state=foreign_state)
        )

def _feedback() -> dict:
    return {
        "feedback_view_id": DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
        "trial_id": "trial-1",
        "task_id": DRAINAGE_ACQUISITION_TASK_ID,
        "execution_status": "completed",
        "terminal_outcome": {
            "canonical_reward": 1.0,
            "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
        },
        "review_gates": {
            key: {"passed": True, "score": 1.0}
            for key in (
                "checkpoint_contract",
                "staged_disclosure",
                "finding_continuity",
                "closure_evidence",
                "accepted_decision_preservation",
                "final_readiness",
                "claim_boundary",
            )
        },
        "checkpoint_submissions": {key: {} for key in CHECKPOINT_IDS},
        "review_principles": [
            "Current registered evidence controls finding, closure, and readiness status transitions.",
            "Non-governing administrative material does not justify correction or closure.",
            "Preserve stable finding and accepted-decision identities unless current evidence supports a transition.",
            "Closure and readiness require the relevant current evidence chain.",
        ],
    }


def _history() -> bytes:
    feedback = _feedback()
    return lifecycles._canonical_json_bytes(
        {
            "history_schema": lifecycles._RAW_HISTORY_SCHEMA,
            "source_experience_id": "acquisition",
            "source_task_id": DRAINAGE_ACQUISITION_TASK_ID,
            "source_trial_id": "trial-1",
            "feedback_view_id": DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
            "public_input": {"instruction": "Review the released drainage evidence."},
            "public_outputs": feedback["checkpoint_submissions"],
            "released_feedback": feedback,
        },
        category="test",
    )


def test_raw_history_is_adapter_owned_and_initialises_three_channels(tmp_path: Path) -> None:
    assert LifecycleLearningTreatmentKind.RAW_HISTORY.value == "raw-history"
    root = tmp_path / "state"
    lifecycles._initialise_raw_history_state(root)
    assert {item.name for item in root.iterdir()} == {"history", "memory", "feedback"}
    assert not any((root / "memory").iterdir())


def test_raw_history_validates_exact_allowlisted_envelope(tmp_path: Path) -> None:
    root = tmp_path / "state"
    lifecycles._initialise_raw_history_state(root)
    (root / "history" / lifecycles._RAW_HISTORY_FILENAME).write_bytes(_history())
    feedback = lifecycles._canonical_json_bytes(_feedback(), category="test")
    (root / "feedback" / "release.json").write_bytes(feedback)
    lifecycles._validate_raw_history_state(root)

    payload = json.loads((root / "history" / lifecycles._RAW_HISTORY_FILENAME).read_text())
    assert set(payload) == {
        "history_schema",
        "source_experience_id",
        "source_task_id",
        "source_trial_id",
        "feedback_view_id",
        "public_input",
        "public_outputs",
        "released_feedback",
    }


def test_raw_history_entry_binds_source_identity_and_public_instruction() -> None:
    record = make_trial_record(
        task={"task_id": DRAINAGE_ACQUISITION_TASK_ID, "task_revision": "fixture"},
        trial_id="trial-1",
        input={
            "instruction": "Review the released drainage evidence.",
            "task_revision": "fixture",
            "visibility": "public",
            "system_prompt": "Use tools carefully.",
        },
    )
    data = lifecycles._canonical_json_bytes(_feedback(), category="test")
    entry = lifecycles._raw_history_entry(
        source_experience_id="acquisition",
        source_record=record,
        feedback_view_id=DRAINAGE_STAGED_REVIEW_FEEDBACK_VIEW_ID,
        public_feedback=data,
    )
    assert json.loads(entry)["source_trial_id"] == "trial-1"


def test_raw_history_rejects_memory_writes_and_noncanonical_history(tmp_path: Path) -> None:
    root = tmp_path / "state"
    lifecycles._initialise_raw_history_state(root)
    (root / "memory" / "summary.md").write_text("not allowed")
    with pytest.raises(ValueError, match="raw-history-channel-write-forbidden"):
        lifecycles._validate_raw_history_state(root)

    (root / "memory" / "summary.md").unlink()
    (root / "history" / "entry.json").write_text(json.dumps(json.loads(_history())))
    with pytest.raises(ValueError, match="raw-history-state-invalid"):
        lifecycles._validate_raw_history_state(root)


def test_raw_history_rejects_unsafe_executable_and_oversized_files(tmp_path: Path) -> None:
    root = tmp_path / "state"
    lifecycles._initialise_raw_history_state(root)
    unsafe = root / "history" / "unsafe.py"
    unsafe.write_text("pass")
    with pytest.raises(ValueError, match="raw-history-selection-invalid"):
        lifecycles._validate_raw_history_state(root)
    unsafe.unlink()

    large = root / "history" / "large.json"
    large.write_bytes(b"x" * (lifecycles._MAX_RAW_HISTORY_FILE_BYTES + 1))
    with pytest.raises(ValueError, match="raw-history-file-too-large"):
        lifecycles._validate_raw_history_state(root)
    large.unlink()
    valid = root / "history" / lifecycles._RAW_HISTORY_FILENAME
    valid.write_bytes(_history())
    (root / "history" / "executable.json").write_bytes(b"{}")
    (root / "history" / "executable.json").chmod(stat.S_IRUSR | stat.S_IXUSR)
    with pytest.raises(ValueError, match="raw-history-path-unsafe"):
        lifecycles._validate_raw_history_state(root)


def test_raw_history_rejects_forbidden_material_and_symlinks(tmp_path: Path) -> None:
    root = tmp_path / "state"
    lifecycles._initialise_raw_history_state(root)
    forbidden = json.loads(_history())
    forbidden["public_input"]["instruction"] = "Read /host/hidden/gold-submissions.json"
    (root / "history" / lifecycles._RAW_HISTORY_FILENAME).write_bytes(
        lifecycles._canonical_json_bytes(forbidden, category="test")
    )
    with pytest.raises(ValueError, match="raw-history-forbidden-material"):
        lifecycles._validate_raw_history_state(root)

    (root / "history" / lifecycles._RAW_HISTORY_FILENAME).unlink()
    outside = tmp_path / "outside"
    outside.write_bytes(_history())
    (root / "history" / "link.json").symlink_to(outside)
    with pytest.raises(ValueError, match="raw-history-path-unsafe"):
        lifecycles._validate_raw_history_state(root)


def test_raw_history_context_projection_excludes_memory_and_is_immutable(tmp_path: Path) -> None:
    root = tmp_path / "state"
    lifecycles._initialise_raw_history_state(root)
    (root / "history" / lifecycles._RAW_HISTORY_FILENAME).write_bytes(_history())
    (root / "feedback" / "release.json").write_bytes(
        lifecycles._canonical_json_bytes(_feedback(), category="test")
    )
    context = tmp_path / "context"
    snapshot = lifecycles._create_raw_history_context_projection(root, context)
    assert {item.name for item in context.iterdir()} == {"history", "feedback"}
    assert not (context / "memory").exists()
    with pytest.raises(PermissionError):
        (context / "feedback" / "release.json").write_bytes(b"changed")
    lifecycles._validate_raw_history_context_projection(context, snapshot)
