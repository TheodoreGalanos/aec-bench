# ABOUTME: Tests structured cross-lifecycle memory, feedback, consolidation, isolation, and resume.
# ABOUTME: Proves learner state stays separate from lifecycle evidence and is read-only during complete tasks.

from __future__ import annotations

import asyncio
import json
import stat
from pathlib import Path
from types import SimpleNamespace

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
from aec_bench.contracts.learning_study_evidence import FeedbackReleaseRecord
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies import lifecycles as lifecycle_adapter
from aec_bench.experimentation.learning_studies.learner_state import (
    validate_learner_state,
)
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleConsolidationContext,
    LifecycleExecutionCondition,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
    resolve_lifecycle_learning_target,
)
from aec_bench.experimentation.learning_studies.planning import (
    CompiledConsolidationStep,
    CompiledExperienceStep,
    CompiledFeedbackStep,
    compile_learning_study,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.resume import load_resumable_study
from aec_bench.experimentation.learning_studies.runtime import (
    ArmRunStatus,
    ConsolidationRequest,
    ExecuteExperienceRequest,
    LearnerStateHandle,
    ReleaseFeedbackRequest,
    StepExecutionStatus,
    run_learning_study,
)
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from tests.support.trial_record_factories import make_trial_record

_TEMPLATE_ID = "drainage-model-evidence-lifecycle-review"
_ACQUISITION_VARIANT = "staged_full_correction"
_PROBE_VARIANT = "semantic_no_op_release"
_ACQUISITION_TASK = f"lifecycle/{_TEMPLATE_ID}/{_ACQUISITION_VARIANT}"
_PROBE_TASK = f"lifecycle/{_TEMPLATE_ID}/{_PROBE_VARIANT}"
_CONDITION = LifecycleExecutionCondition(
    execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
    visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
)
_AGENT = AgentConfig(
    name="lifecycle-memory-test-agent",
    adapter="tool_loop",
    model="fixed-test-model",
    parameters={"max_turns_per_session": 5},
)
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512})


def _initialisation_plan(*treatments: str):  # noqa: ANN202
    arms = tuple(
        LearningArmSpec(
            arm_id=f"arm-{index}",
            role=StudyArmRole.CONTROL,
            treatment_id=treatment,
            steps=(
                RunExperienceStep(
                    step_id=f"probe-{index}",
                    experience_id="probe",
                    commit_post_state=False,
                ),
            ),
        )
        for index, treatment in enumerate(treatments, start=1)
    )
    spec = LearningStudySpec(
        study_id="lifecycle-state-initialisation",
        title="Lifecycle learner-state initialisation",
        research_question="Are treatment states isolated?",
        agent=_AGENT,
        compute=_COMPUTE,
        repetitions=1,
        experiences=(LearningExperienceSpec(experience_id="probe", task_id=_PROBE_TASK, role=ExperienceRole.PROBE),),
        arms=arms,
    )
    return compile_learning_study(
        study_run_id="lifecycle-state-initialisation-run",
        spec=spec,
        resolve_task=resolve_lifecycle_learning_target,
    )


def _structured_plan():  # noqa: ANN202
    spec = LearningStudySpec(
        study_id="l01-structured-memory",
        title="L01 structured lifecycle memory",
        research_question="Can safe lifecycle feedback become portable review guidance?",
        agent=_AGENT,
        compute=_COMPUTE,
        repetitions=1,
        experiences=(
            LearningExperienceSpec(
                experience_id="acquisition",
                task_id=_ACQUISITION_TASK,
                role=ExperienceRole.ACQUISITION,
            ),
            LearningExperienceSpec(
                experience_id="probe",
                task_id=_PROBE_TASK,
                role=ExperienceRole.PROBE,
            ),
        ),
        arms=(
            LearningArmSpec(
                arm_id="structured-memory",
                role=StudyArmRole.EXPOSURE,
                treatment_id="structured-memory",
                steps=(
                    RunExperienceStep(
                        step_id="acquisition",
                        experience_id="acquisition",
                        commit_post_state=True,
                    ),
                    ReleaseFeedbackStep(
                        step_id="release-feedback",
                        source_experience_id="acquisition",
                        feedback_view_id="safe-terminal",
                    ),
                    ConsolidateStep(
                        step_id="consolidate-memory",
                        feedback_step_ids=("release-feedback",),
                        operation_id="update-review-memory",
                    ),
                    RunExperienceStep(
                        step_id="probe",
                        experience_id="probe",
                        commit_post_state=False,
                    ),
                ),
            ),
        ),
    )
    return compile_learning_study(
        study_run_id="l01-structured-memory-run",
        spec=spec,
        resolve_task=resolve_lifecycle_learning_target,
    )


def _feedback_projector(record: TrialRecord) -> bytes:
    payload = {
        "task_id": record.task_id,
        "trial_id": record.trial_id,
        "reward": None if record.evaluation is None else record.evaluation.reward,
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()


class _Consolidator:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, context: LifecycleConsolidationContext) -> None:
        self.calls += 1
        assert context.state_root.parent.name == "states"
        assert len(context.feedback) == 1
        feedback = json.loads(context.feedback[0].path.read_text(encoding="utf-8"))
        assert feedback["reward"] == 1.0
        (context.memory_root / "review-guidance.md").write_text(
            "Change finding and readiness status only when current registered evidence supports the transition.\n",
            encoding="utf-8",
        )


class _ContextReadingGoldAdapterBuilder:
    def __init__(self) -> None:
        self.executions = 0
        self.context_by_variant: dict[str, list[dict[str, str]]] = {}
        self.system_prompts: list[str] = []

    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        package = workspace.parent.parent / "package"
        variant = json.loads((package / "hidden" / "variant.json").read_text(encoding="utf-8"))["variant_id"]
        submissions = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        native_tools = {tool.__name__: tool for tool in kwargs["native_tools"]}
        builder = self

        class _Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                builder.executions += 1
                builder.system_prompts.append(request.system_prompt)
                root = json.loads(native_tools["list_workspace"]("."))
                assert "learner_context" in root["entries"]
                context_listing = json.loads(native_tools["list_workspace"]("learner_context"))
                observed: dict[str, str] = {}
                for name in context_listing["entries"]:
                    item = json.loads(native_tools["read_workspace_file"](f"learner_context/{name}"))
                    observed[name] = item["content"]
                builder.context_by_variant.setdefault(variant, []).append(observed)
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


def _binding(
    run_root: Path,
    *,
    adapter_builder=None,  # noqa: ANN001
    consolidator=None,  # noqa: ANN001
    initial_memory_root: Path | None = None,
    resume_existing_run: bool = False,
):  # noqa: ANN202
    return build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=_CONDITION,
        treatment_kinds={
            "reset": LifecycleLearningTreatmentKind.RESET,
            "structured-memory": LifecycleLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={"safe-terminal": _feedback_projector},
        consolidation_operations={
            "update-review-memory": consolidator or _Consolidator(),
        },
        initial_memory_root=initial_memory_root,
        adapter_builder=adapter_builder,
        resume_existing_run=resume_existing_run,
    )


def _new_state_tree(root: Path) -> Path:
    (root / "memory").mkdir(parents=True)
    (root / "feedback").mkdir()
    return root


def test_reset_and_structured_initial_state_use_isolated_exact_trees(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "shared.md").write_text("Initial shared guidance.\n", encoding="utf-8")
    plan = _initialisation_plan("reset", "structured-memory", "structured-memory")
    binding = _binding(tmp_path / "study", initial_memory_root=seed)

    states = [binding.operations.initialise_learner(arm) for arm in plan.arm_runs]

    for state in states:
        assert {path.name for path in state.value.root.iterdir()} == {"memory", "feedback"}
        validate_learner_state(state.value.root)
    assert list(states[0].value.root.rglob("*.md")) == []
    first_seed = states[1].value.root / "memory" / "shared.md"
    second_seed = states[2].value.root / "memory" / "shared.md"
    assert first_seed.read_bytes() == second_seed.read_bytes() == b"Initial shared guidance.\n"
    assert first_seed.stat().st_ino != second_seed.stat().st_ino
    assert len({state.value.root for state in states}) == 3


def test_lifecycle_learner_state_accepts_allowed_structured_files(tmp_path: Path) -> None:
    state = _new_state_tree(tmp_path / "state")
    (state / "memory" / "guide.md").write_text("Guidance\n", encoding="utf-8")
    (state / "memory" / "notes.txt").write_text("Notes\n", encoding="utf-8")
    (state / "memory" / "rules.json").write_text('{"rule":"current evidence"}\n', encoding="utf-8")
    (state / "feedback" / "release.json").write_text('{"reward":1}\n', encoding="utf-8")

    validate_learner_state(state)


@pytest.mark.parametrize(
    ("relative", "content", "category"),
    (
        ("memory/.hidden.md", b"hidden", "learner-state-invalid"),
        ("memory/code.py", b"print('no')", "learner-file-type-unsupported"),
        ("memory/bad\\name.md", b"unsafe", "learner-state-invalid"),
        ("memory/binary.txt", b"\xff\xfe", "learner-file-type-unsupported"),
        ("memory/invalid.json", b"{", "learner-state-invalid"),
    ),
)
def test_lifecycle_learner_state_rejects_unsafe_files(
    tmp_path: Path,
    relative: str,
    content: bytes,
    category: str,
) -> None:
    state = _new_state_tree(tmp_path / "state")
    path = state / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)

    with pytest.raises(ValueError, match=category):
        validate_learner_state(state)


def test_lifecycle_learner_state_rejects_symlink_executable_and_unknown_root(tmp_path: Path) -> None:
    symlink_state = _new_state_tree(tmp_path / "symlink-state")
    outside = tmp_path / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    (symlink_state / "memory" / "bridge.md").symlink_to(outside)
    with pytest.raises(ValueError, match="learner-symlink-forbidden"):
        validate_learner_state(symlink_state)

    executable_state = _new_state_tree(tmp_path / "executable-state")
    executable = executable_state / "memory" / "guide.md"
    executable.write_text("guide", encoding="utf-8")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    with pytest.raises(ValueError, match="learner-file-type-unsupported"):
        validate_learner_state(executable_state)

    unknown_state = _new_state_tree(tmp_path / "unknown-state")
    (unknown_state / "history").mkdir()
    with pytest.raises(ValueError, match="learner-state-invalid"):
        validate_learner_state(unknown_state)


def test_lifecycle_learner_state_enforces_file_and_snapshot_limits(tmp_path: Path) -> None:
    file_state = _new_state_tree(tmp_path / "file-state")
    (file_state / "memory" / "large.txt").write_bytes(b"x" * 1_000_001)
    with pytest.raises(ValueError, match="learner-file-too-large"):
        validate_learner_state(file_state)

    total_state = _new_state_tree(tmp_path / "total-state")
    for index in range(5):
        (total_state / "memory" / f"part-{index}.txt").write_bytes(b"x" * 900_000)
    with pytest.raises(ValueError, match="learner-state-too-large"):
        validate_learner_state(total_state)


def test_context_mutation_fails_experience_and_preserves_parent_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "guidance.md").write_text("Original guidance.\n", encoding="utf-8")
    plan = _initialisation_plan("structured-memory")
    arm_run = plan.arm_runs[0]
    binding = _binding(tmp_path / "study", initial_memory_root=seed)
    state = binding.operations.initialise_learner(arm_run)
    step = arm_run.steps[0]
    assert isinstance(step, CompiledExperienceStep)

    def compile_fake(template_id: str, package_dir: Path, *, variant_id: str | None = None):  # noqa: ANN202
        package_dir.mkdir(parents=True)
        return SimpleNamespace(
            package_dir=package_dir,
            envelope=SimpleNamespace(template_id=template_id, variant_id=variant_id),
        )

    def local_fake(trial, *, adapter_builder=None, read_only_context_root=None):  # noqa: ANN001, ANN202, ARG001
        assert read_only_context_root is not None
        guidance = read_only_context_root / "guidance.md"
        guidance.chmod(0o600)
        guidance.write_text("Mutated guidance.\n", encoding="utf-8")
        return SimpleNamespace()

    def run_fake(*, trial, execute, verify, persist=None):  # noqa: ANN001, ANN202, ARG001
        execute(trial)
        return make_trial_record(
            trial_id=trial.planned.trial_id,
            experiment_id=trial.planned.experiment_id,
            task_id=trial.planned.task_id,
            attempt=trial.planned.repetition,
        )

    monkeypatch.setattr(lifecycle_adapter, "compile_lifecycle", compile_fake)
    monkeypatch.setattr(lifecycle_adapter, "run_local_lifecycle", local_fake)
    monkeypatch.setattr(lifecycle_adapter, "run_lifecycle_trial", run_fake)

    with pytest.raises(ValueError, match="context-readonly-violation"):
        binding.operations.execute_experience(ExecuteExperienceRequest(arm_run=arm_run, step=step, state=state))

    assert (state.value.root / "memory" / "guidance.md").read_text() == "Original guidance.\n"
    assert not (state.value.root.parent / step.step_id).exists()


def test_feedback_changes_only_feedback_and_failed_consolidation_preserves_parent(tmp_path: Path) -> None:
    plan = _initialisation_plan("structured-memory")
    arm_run = plan.arm_runs[0]

    def forbidden_operation(context: LifecycleConsolidationContext) -> None:
        context.feedback[0].path.write_text('{"changed":true}\n', encoding="utf-8")
        (context.memory_root / "guide.md").write_text("New guidance.\n", encoding="utf-8")

    binding = _binding(tmp_path / "study", consolidator=forbidden_operation)
    initial = binding.operations.initialise_learner(arm_run)
    feedback_step = CompiledFeedbackStep(
        step_id="release-feedback",
        source_experience_id="probe",
        feedback_view_id="safe-terminal",
    )
    released = binding.operations.release_feedback(
        ReleaseFeedbackRequest(
            arm_run=arm_run,
            step=feedback_step,
            state=initial,
            source_trial_record=make_trial_record(),
        )
    )

    assert list(initial.value.root.rglob("*.*")) == []
    feedback_path = released.candidate_state.value.root / "feedback" / "release-feedback.json"
    original_feedback = feedback_path.read_bytes()
    assert feedback_path == released.feedback.value.path
    assert list(released.candidate_state.value.root.glob("memory/*")) == []
    consolidation_step = CompiledConsolidationStep(
        step_id="consolidate-memory",
        feedback_step_ids=("release-feedback",),
        operation_id="update-review-memory",
    )

    with pytest.raises(ValueError, match="consolidation-forbidden-state-change"):
        binding.operations.consolidate(
            ConsolidationRequest(
                arm_run=arm_run,
                step=consolidation_step,
                state=released.candidate_state,
                feedback=(released.feedback,),
            )
        )

    assert feedback_path.read_bytes() == original_feedback
    assert not (released.candidate_state.value.root.parent / "consolidate-memory").exists()


def test_structured_lifecycle_sequence_carries_only_consolidated_memory_into_probe(tmp_path: Path) -> None:
    plan = _structured_plan()
    run_root = tmp_path / "study"
    adapter = _ContextReadingGoldAdapterBuilder()
    consolidator = _Consolidator()
    binding = _binding(run_root, adapter_builder=adapter, consolidator=consolidator)
    recorder = StudyRunRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )

    execution = asyncio.run(run_learning_study(plan=plan, operations=binding.operations, observer=recorder))

    arm_result = execution.arm_runs[0]
    assert arm_result.status is ArmRunStatus.COMPLETED
    assert len(arm_result.trial_records) == 2
    assert [step.status for step in arm_result.completed_steps] == [StepExecutionStatus.COMPLETED] * 4
    assert arm_result.final_state_id is not None and arm_result.final_state_id.endswith(":state:consolidate-memory")
    assert adapter.executions == 6
    assert consolidator.calls == 1
    assert adapter.context_by_variant[_ACQUISITION_VARIANT] == [{}, {}, {}]
    expected_memory = {
        "review-guidance.md": (
            "Change finding and readiness status only when current registered evidence supports the transition.\n"
        )
    }
    assert adapter.context_by_variant[_PROBE_VARIANT] == [expected_memory, expected_memory, expected_memory]
    assert all("not task evidence" in prompt for prompt in adapter.system_prompts)

    arm_root = run_root / "learner-arms" / plan.arm_runs[0].arm_run_id
    final_state = arm_root / "states" / "consolidate-memory"
    assert (final_state / "memory" / "review-guidance.md").read_text(encoding="utf-8") == expected_memory[
        "review-guidance.md"
    ]
    assert (final_state / "feedback" / "release-feedback.json").is_file()
    acquisition_state = arm_root / "states" / "acquisition"
    feedback_state = arm_root / "states" / "release-feedback"
    assert list(acquisition_state.glob("memory/*")) == []
    assert list(acquisition_state.glob("feedback/*")) == []
    assert list(feedback_state.glob("memory/*")) == []
    assert (feedback_state / "feedback" / "release-feedback.json").read_bytes() == (
        final_state / "feedback" / "release-feedback.json"
    ).read_bytes()
    assert not (arm_root / "states" / "probe").exists()
    assert not any(
        path.name in {"variant.json", "verification.json", "metrics.json"} for path in final_state.rglob("*")
    )
    probe_context = arm_root / "lifecycle-experiences" / "probe" / "context"
    assert not any("feedback" in path.parts for path in probe_context.rglob("*"))
    assert (arm_root / "lifecycle-experiences" / "acquisition" / "context").is_dir()
    assert (arm_root / "lifecycle-experiences" / "probe" / "context" / "review-guidance.md").is_file()
    state_bytes = sum(path.stat().st_size for path in final_state.rglob("*") if path.is_file())
    assert 0 < state_bytes < 4_000_000


class _InterruptedAfterFeedback(BaseException):
    pass


class _InterruptingRecorder(StudyRunRecorder):
    def step_committed(self, arm_run, step, result, state_before, candidate_state, committed_state):  # noqa: ANN001, ANN201
        super().step_committed(arm_run, step, result, state_before, candidate_state, committed_state)
        if step.step_id == "release-feedback":
            raise _InterruptedAfterFeedback


def test_resume_restores_exact_feedback_and_memory_without_rerunning_prior_steps(tmp_path: Path) -> None:
    plan = _structured_plan()
    run_root = tmp_path / "study"
    adapter = _ContextReadingGoldAdapterBuilder()
    consolidator = _Consolidator()
    projector_calls = 0

    def counted_projector(record: TrialRecord) -> bytes:
        nonlocal projector_calls
        projector_calls += 1
        return _feedback_projector(record)

    binding = build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=_CONDITION,
        treatment_kinds={"structured-memory": LifecycleLearningTreatmentKind.STRUCTURED_MEMORY},
        feedback_projectors={"safe-terminal": counted_projector},
        consolidation_operations={"update-review-memory": consolidator},
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

    assert adapter.executions == 3
    assert projector_calls == 1
    resumed_binding = build_lifecycle_learning_operations(
        run_root=run_root,
        execution_condition=_CONDITION,
        treatment_kinds={"structured-memory": LifecycleLearningTreatmentKind.STRUCTURED_MEMORY},
        feedback_projectors={"safe-terminal": counted_projector},
        consolidation_operations={"update-review-memory": consolidator},
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
    assert adapter.executions == 6
    assert projector_calls == 1
    assert consolidator.calls == 1
    restored_feedback = tmp_path / "restored" / plan.arm_runs[0].arm_run_id
    restored_files = list(restored_feedback.rglob("release-feedback.json"))
    assert len(restored_files) == 1
    evidence_record = next((run_root / "feedback").glob("*.json"))
    evidence = json.loads(evidence_record.read_text(encoding="utf-8"))
    artifact_id = evidence["public_artifact_refs"][0]["artifact_id"]
    artifact_path = run_root / "_artifacts" / artifact_id
    assert restored_files[0].read_bytes() == artifact_path.read_bytes()


def test_restore_feedback_rejects_a_record_from_another_arm(tmp_path: Path) -> None:
    plan = _initialisation_plan("structured-memory", "structured-memory")
    binding = _binding(tmp_path / "study")
    arm_one, arm_two = plan.arm_runs
    state_one = binding.operations.initialise_learner(arm_one)
    state_two = binding.operations.initialise_learner(arm_two)
    assert state_one.value.arm_run_id != state_two.value.arm_run_id

    foreign_record = FeedbackReleaseRecord(
        feedback_id=f"{arm_one.arm_run_id}:feedback:release",
        arm_run_id=arm_one.arm_run_id,
        release_step_id="release",
        source_experience_id="acquisition",
        source_trial_id="some-trial",
        view_id="safe-terminal",
        public_artifact_refs=(),
        state_before_id=state_one.state_id,
        state_after_id=f"{arm_one.arm_run_id}:state:release",
    )

    with pytest.raises(ValueError, match="cross-arm-path-detected"):
        binding.restore_feedback(foreign_record, state_two)


def test_discard_rejects_initial_and_lifecycle_evidence_roots(tmp_path: Path) -> None:
    plan = _initialisation_plan("structured-memory")
    binding = _binding(tmp_path / "study")
    state = binding.operations.initialise_learner(plan.arm_runs[0])

    with pytest.raises(ValueError, match="state-discard-invalid"):
        binding.operations.discard_state(state)

    evidence_state = state.value.root.parents[1] / "lifecycle-experiences" / "step" / "run"
    _new_state_tree(evidence_state)
    invalid = LearnerStateHandle(
        state_id="invalid",
        value=type(state.value)(
            arm_run_id=state.value.arm_run_id,
            treatment_id=state.value.treatment_id,
            root=evidence_state,
        ),
    )
    with pytest.raises(ValueError, match="state-discard-invalid"):
        binding.operations.discard_state(invalid)
