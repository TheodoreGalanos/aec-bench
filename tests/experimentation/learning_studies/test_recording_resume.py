# ABOUTME: Tests Learning Study receipt commitment, state lineage, and crash resume.
# ABOUTME: Proves committed steps do not rerun and uncommitted state does not replace prior state.

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import pytest

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
from aec_bench.contracts.learning_study_evidence import (
    FeedbackReleaseRecord,
    LearnerStateRef,
    LearnerTransitionReceipt,
    StudyEvent,
    StudyEventKind,
)
from aec_bench.experimentation.learning_studies.errors import LearningStudyPersistenceError
from aec_bench.experimentation.learning_studies.planning import (
    CompiledLearningStudy,
    CompiledStudyStep,
    PlannedArmRun,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder, create_study_run
from aec_bench.experimentation.learning_studies.resume import load_resumable_study
from aec_bench.experimentation.learning_studies.runtime import (
    ConsolidationRequest,
    ExecuteExperienceRequest,
    ExperienceExecutionResult,
    FeedbackHandle,
    FeedbackReleaseResult,
    LearnerStateHandle,
    LearnerTransitionResult,
    LearningStudyOperations,
    ReleaseFeedbackRequest,
    run_learning_study,
)
from tests.support.trial_record_factories import make_trial_record


@dataclass(frozen=True)
class _Task:
    task_id: str


@dataclass
class _FileOperations:
    root: Path
    state_counter: int = 0
    feedback_counter: int = 0
    calls: dict[str, int] = field(default_factory=dict)
    fail_steps: set[str] = field(default_factory=set)

    def state(self, source: Path | None, label: str) -> LearnerStateHandle[Path]:
        self.state_counter += 1
        destination = self.root / f"state-{self.state_counter}"
        if source is None:
            destination.mkdir(parents=True)
        else:
            shutil.copytree(source, destination)
        (destination / "last-operation.txt").write_text(label, encoding="utf-8")
        return LearnerStateHandle(state_id=f"state-{self.state_counter}", value=destination)

    def initialise(self, request: PlannedArmRun) -> LearnerStateHandle[Path]:
        return self.state(None, f"initial:{request.arm_run_id}")

    def execute(self, request: ExecuteExperienceRequest[Path]) -> ExperienceExecutionResult[Path]:
        self.calls[request.step.step_id] = self.calls.get(request.step.step_id, 0) + 1
        if request.step.step_id in self.fail_steps:
            raise RuntimeError(f"declared failure: {request.step.step_id}")
        candidate = self.state(request.state.value, f"experience:{request.step.step_id}")
        return ExperienceExecutionResult(
            trial_record=make_trial_record(
                trial_id=request.step.trial.trial_id,
                experiment_id=request.step.trial.experiment_id,
                task_id=request.step.trial.task_id,
            ),
            candidate_state=candidate,
        )

    def release(self, request: ReleaseFeedbackRequest[Path]) -> FeedbackReleaseResult[Path, Path]:
        self.calls[request.step.step_id] = self.calls.get(request.step.step_id, 0) + 1
        candidate = self.state(request.state.value, f"feedback:{request.step.step_id}")
        feedback_path = candidate.value / "feedback.txt"
        feedback_path.write_text("public outcome", encoding="utf-8")
        self.feedback_counter += 1
        return FeedbackReleaseResult(
            candidate_state=candidate,
            feedback=FeedbackHandle(
                feedback_id=f"feedback-{self.feedback_counter}",
                source_experience_id=request.step.source_experience_id,
                view_id=request.step.feedback_view_id,
                value=feedback_path,
            ),
        )

    def consolidate(self, request: ConsolidationRequest[Path, Path]) -> LearnerTransitionResult[Path]:
        self.calls[request.step.step_id] = self.calls.get(request.step.step_id, 0) + 1
        assert request.feedback and all(
            item.value.read_text(encoding="utf-8") == "public outcome" for item in request.feedback
        )
        candidate = self.state(request.state.value, f"consolidation:{request.step.step_id}")
        (candidate.value / "memory.txt").write_text("method", encoding="utf-8")
        return LearnerTransitionResult(candidate_state=candidate)

    def bundle(self) -> LearningStudyOperations[Path, Path]:
        return LearningStudyOperations(
            initialise_learner=self.initialise,
            execute_experience=self.execute,
            release_feedback=self.release,
            consolidate=self.consolidate,
            discard_state=lambda _state: None,
        )


def _plan() -> CompiledLearningStudy:
    spec = LearningStudySpec(
        study_id="recording-study",
        title="Recording study",
        research_question="Can a committed sequence resume?",
        agent=AgentConfig(name="agent", adapter="direct", model="fixed"),
        compute=ComputeConfig(backend="local"),
        experiences=(
            LearningExperienceSpec(experience_id="acquire", task_id="task/acquire", role=ExperienceRole.ACQUISITION),
            LearningExperienceSpec(experience_id="probe", task_id="task/probe", role=ExperienceRole.PROBE),
        ),
        arms=(
            LearningArmSpec(
                arm_id="cold",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(RunExperienceStep(step_id="cold-probe", experience_id="probe"),),
            ),
            LearningArmSpec(
                arm_id="exposed",
                role=StudyArmRole.EXPOSURE,
                treatment_id="structured-memory",
                steps=(
                    RunExperienceStep(step_id="acquire", experience_id="acquire"),
                    ReleaseFeedbackStep(
                        step_id="feedback",
                        source_experience_id="acquire",
                        feedback_view_id="public",
                    ),
                    ConsolidateStep(
                        step_id="consolidate",
                        feedback_step_ids=("feedback",),
                        operation_id="write-memory",
                    ),
                    RunExperienceStep(step_id="probe", experience_id="probe"),
                ),
            ),
        ),
    )
    return compile_learning_study(
        study_run_id="recording-run",
        spec=spec,
        resolve_task=lambda task_id: _Task(task_id),
    )


def _restore_state(reference: LearnerStateRef, root: Path) -> LearnerStateHandle[Path]:
    return LearnerStateHandle(state_id=reference.state_id, value=root)


def _restore_feedback(
    record: FeedbackReleaseRecord,
    state: LearnerStateHandle[Path],
) -> FeedbackHandle[Path]:
    feedback_id = record.feedback_id
    source_experience_id = record.source_experience_id
    view_id = record.view_id
    return FeedbackHandle(
        feedback_id=feedback_id,
        source_experience_id=source_experience_id,
        view_id=view_id,
        value=state.value / "feedback.txt",
    )


@pytest.mark.asyncio
async def test_recorder_persists_normal_trials_state_lineage_and_probe_discard(tmp_path: Path) -> None:
    plan = _plan()
    operations = _FileOperations(tmp_path / "live")
    recorder: StudyRunRecorder[Path, Path] = create_study_run(
        root=tmp_path / "study",
        plan=plan,
        snapshot_state=lambda state: state.value,
    )

    result = await run_learning_study(plan=plan, operations=operations.bundle(), observer=recorder)

    assert all(item.status.value == "completed" for item in result.arm_runs)
    assert len(list((tmp_path / "study" / "ledger").glob("*/*.json"))) == 3
    state_refs = [
        LearnerStateRef.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "study" / "states").glob("*.json"))
    ]
    assert len(state_refs) == 5
    transitions = [
        LearnerTransitionReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted((tmp_path / "study" / "transitions").glob("*.json"))
    ]
    probe_discards = [item for item in transitions if item.operation_kind == "probe_discard"]
    assert len(probe_discards) == 2
    assert all(not item.committed and item.committed_state_id == item.state_before_id for item in probe_discards)
    events = [
        StudyEvent.model_validate_json(line) for line in (tmp_path / "study" / "events.jsonl").read_text().splitlines()
    ]
    assert [item.sequence for item in events] == list(range(len(events)))
    assert events[-1].kind is StudyEventKind.STUDY_COMPLETED


@pytest.mark.parametrize("crash_step", ["cold-probe", "acquire", "feedback", "consolidate", "probe"])
@pytest.mark.asyncio
async def test_resume_does_not_rerun_a_step_with_an_authoritative_receipt(
    tmp_path: Path,
    crash_step: str,
) -> None:
    plan = _plan()
    operations = _FileOperations(tmp_path / "live")
    crashed = False

    def fail_before_event(
        point: str,
        _arm: PlannedArmRun | None,
        step: CompiledStudyStep | None,
    ) -> None:
        nonlocal crashed
        if not crashed and point == "before_event" and step is not None and step.step_id == crash_step:
            crashed = True
            raise RuntimeError("simulated process stop")

    recorder: StudyRunRecorder[Path, Path] = create_study_run(
        root=tmp_path / "study",
        plan=plan,
        snapshot_state=lambda state: state.value,
        fault_injector=fail_before_event,
    )
    with pytest.raises(LearningStudyPersistenceError, match="simulated process stop"):
        await run_learning_study(plan=plan, operations=operations.bundle(), observer=recorder)
    calls_before_resume = operations.calls.get(crash_step, 0)

    resumable = load_resumable_study(
        root=tmp_path / "study",
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=lambda state: state.value,
        restore_state=_restore_state,
        restore_feedback=_restore_feedback,
    )
    result = await run_learning_study(
        plan=plan,
        operations=operations.bundle(),
        observer=resumable.recorder,
        resume=resumable.resume,
    )

    assert operations.calls[crash_step] == calls_before_resume == 1
    assert all(item.status.value == "completed" for item in result.arm_runs)
    committed_references = {
        event.reference
        for event in (
            StudyEvent.model_validate_json(line)
            for line in (tmp_path / "study" / "events.jsonl").read_text().splitlines()
        )
        if event.kind is StudyEventKind.STEP_COMMITTED
    }
    assert any(reference and reference.endswith(f"-{crash_step}.json") for reference in committed_references)


@pytest.mark.asyncio
async def test_resume_finishes_a_complete_pending_transaction_without_rerunning_trial(tmp_path: Path) -> None:
    plan = _plan()
    operations = _FileOperations(tmp_path / "live")
    crashed = False

    def fail_after_pending(
        point: str,
        _arm: PlannedArmRun | None,
        step: CompiledStudyStep | None,
    ) -> None:
        nonlocal crashed
        if not crashed and point == "after_pending" and step is not None and step.step_id == "cold-probe":
            crashed = True
            raise RuntimeError("stop after durable pending evidence")

    recorder: StudyRunRecorder[Path, Path] = create_study_run(
        root=tmp_path / "study",
        plan=plan,
        snapshot_state=lambda state: state.value,
        fault_injector=fail_after_pending,
    )
    with pytest.raises(LearningStudyPersistenceError):
        await run_learning_study(plan=plan, operations=operations.bundle(), observer=recorder)
    assert operations.calls["cold-probe"] == 1
    assert list((tmp_path / "study" / "staging").glob("*/*/pending.json"))

    resumable = load_resumable_study(
        root=tmp_path / "study",
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=lambda state: state.value,
        restore_state=_restore_state,
        restore_feedback=_restore_feedback,
    )
    await run_learning_study(
        plan=plan,
        operations=operations.bundle(),
        observer=resumable.recorder,
        resume=resumable.resume,
    )

    assert operations.calls["cold-probe"] == 1
    assert not list((tmp_path / "study" / "staging").glob("*/*/pending.json"))


@pytest.mark.asyncio
async def test_resume_abandons_an_unpublished_candidate_and_reruns_from_committed_state(tmp_path: Path) -> None:
    plan = _plan()
    operations = _FileOperations(tmp_path / "live")
    snapshot_calls = 0

    def fail_candidate_snapshot(state: LearnerStateHandle[Path]) -> Path:
        nonlocal snapshot_calls
        snapshot_calls += 1
        if snapshot_calls == 3:
            raise RuntimeError("snapshot interrupted before pending evidence")
        return state.value

    recorder: StudyRunRecorder[Path, Path] = create_study_run(
        root=tmp_path / "study",
        plan=plan,
        snapshot_state=fail_candidate_snapshot,
    )
    with pytest.raises(LearningStudyPersistenceError, match="snapshot interrupted"):
        await run_learning_study(plan=plan, operations=operations.bundle(), observer=recorder)
    assert operations.calls["acquire"] == 1
    assert not list((tmp_path / "study" / "staging").glob("*/*/pending.json"))
    assert not (tmp_path / "study" / "states" / "state-4.json").exists()

    resumable = load_resumable_study(
        root=tmp_path / "study",
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=lambda state: state.value,
        restore_state=_restore_state,
        restore_feedback=_restore_feedback,
    )
    await run_learning_study(
        plan=plan,
        operations=operations.bundle(),
        observer=resumable.recorder,
        resume=resumable.resume,
    )

    assert operations.calls["acquire"] == 2
    transitions = [
        LearnerTransitionReceipt.model_validate_json(path.read_text(encoding="utf-8"))
        for path in (tmp_path / "study" / "transitions").glob("*.json")
    ]
    transition = next(item for item in transitions if item.step_id == "acquire")
    assert transition.state_before_id == "state-3"


def test_recorder_rejects_state_snapshot_symlinks(tmp_path: Path) -> None:
    state_root = tmp_path / "state"
    state_root.mkdir()
    (state_root / "real.txt").write_text("state", encoding="utf-8")
    (state_root / "link.txt").symlink_to(state_root / "real.txt")
    plan = _plan()
    recorder: StudyRunRecorder[Path, Path] = create_study_run(
        root=tmp_path / "study",
        plan=plan,
        snapshot_state=lambda _state: state_root,
    )

    with pytest.raises(LearningStudyPersistenceError, match="symlink"):
        recorder.learner_initialised(
            plan.arm_runs[0],
            LearnerStateHandle(state_id="unsafe-state", value=state_root),
        )


@pytest.mark.asyncio
async def test_resume_preserves_a_terminal_arm_failure_and_does_not_rerun_it(tmp_path: Path) -> None:
    plan = _plan()
    operations = _FileOperations(tmp_path / "live", fail_steps={"cold-probe"})
    recorder: StudyRunRecorder[Path, Path] = create_study_run(
        root=tmp_path / "study",
        plan=plan,
        snapshot_state=lambda state: state.value,
    )
    first = await run_learning_study(plan=plan, operations=operations.bundle(), observer=recorder)
    assert first.arm_runs[0].status.value == "failed"
    assert first.arm_runs[1].status.value == "completed"
    calls_before_resume = dict(operations.calls)

    resumable = load_resumable_study(
        root=tmp_path / "study",
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=lambda state: state.value,
        restore_state=_restore_state,
        restore_feedback=_restore_feedback,
    )
    second = await run_learning_study(
        plan=plan,
        operations=operations.bundle(),
        observer=resumable.recorder,
        resume=resumable.resume,
    )

    assert operations.calls == calls_before_resume
    assert [item.status.value for item in second.arm_runs] == ["failed", "completed"]


def test_recorder_rejects_a_changed_compiled_plan(tmp_path: Path) -> None:
    plan = _plan()
    create_study_run(root=tmp_path / "study", plan=plan, snapshot_state=lambda state: state.value)
    changed_spec = plan.spec.model_copy(update={"title": "Changed after start"})
    changed_plan = compile_learning_study(
        study_run_id=plan.study_run_id,
        spec=changed_spec,
        resolve_task=lambda task_id: _Task(task_id),
    )

    with pytest.raises(LearningStudyPersistenceError, match="study-spec.json"):
        create_study_run(root=tmp_path / "study", plan=changed_plan, snapshot_state=lambda state: state.value)
