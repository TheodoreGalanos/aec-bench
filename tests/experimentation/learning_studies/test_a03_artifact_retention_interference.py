# ABOUTME: Runs the A03 retention and interference protocol through real artifact tasks.
# ABOUTME: Proves non-committing probes, neutral delay, explicit interference, and matched assessment.

import asyncio
import json
from pathlib import Path

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.artifact_tasks import (
    ArtifactConsolidationContext,
    ArtifactLearningTreatmentKind,
    build_artifact_learning_operations,
    public_actor_episode,
    public_episode_feedback,
)
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    assess_learning_study,
    project_trial_reward,
)
from aec_bench.experimentation.learning_studies.planning import compile_learning_study
from aec_bench.experimentation.learning_studies.protocol_collection import (
    BUILTIN_LEARNING_STUDY_PROTOCOLS,
    load_learning_study_protocol,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.runtime import ArmRunStatus, run_learning_study
from aec_bench.tasks.loader import load_task_definition
from tests.experimentation.learning_studies.support import RetentionInterferenceStudyAdapter

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_PROTOCOL_PATH = BUILTIN_LEARNING_STUDY_PROTOCOLS / "a03-artifact-retention-interference"
_NEUTRAL_TASK_ID = (
    "civil/drainage-review/drainage-model-run-provenance-issue-review-package/"
    "brownfield-drainage-upgrade-industrial-precinct-catchment-02"
)
_AGENT = AgentConfig(name="a03-test-agent", adapter="direct", model="fixed-test-model")
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)


def _resolve_task(task_id: str):  # noqa: ANN202
    return load_task_definition(_TASKS_ROOT / task_id, _TASKS_ROOT)


def _state_files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_a03_real_artifact_tasks_measure_retention_and_explicit_interference(tmp_path: Path) -> None:
    spec = load_learning_study_protocol(_PROTOCOL_PATH, agent=_AGENT, compute=_COMPUTE)
    plan = compile_learning_study(study_run_id="a03-stage-1", spec=spec, resolve_task=_resolve_task)
    experiences = {item.experience_id: _resolve_task(item.task_id) for item in spec.experiences}
    immediate_probe = experiences["sydney-classroom-immediate-probe"]
    delayed_probe = experiences["adelaide-library-delayed-probe"]
    assert immediate_probe.difficulty == delayed_probe.difficulty
    assert immediate_probe.tags == delayed_probe.tags
    assert immediate_probe.timeout_seconds == delayed_probe.timeout_seconds == 600
    assert immediate_probe.verifier.expected_output_path == delayed_probe.verifier.expected_output_path
    interference_instruction = experiences["cairns-server-interference"].instruction
    assert "| Data Centres / Server Rooms | 0.0 | 0.0 | 1.0 |" in interference_instruction
    assert "| Libraries | 5.0 | 10.0 | 0.0 |" in delayed_probe.instruction
    assert experiences["drainage-review-neutral"].timeout_seconds == delayed_probe.timeout_seconds
    neutral_output = (_TASKS_ROOT / _NEUTRAL_TASK_ID / "tests" / "fixtures" / "golden_pass.md").read_text(
        encoding="utf-8"
    )
    observations: list[dict[str, object]] = []
    run_root = tmp_path / "a03-stage-1"

    def consolidate_method(context: ArtifactConsolidationContext) -> None:
        instruction = (_PROTOCOL_PATH / "consolidate-occupied-heat-load-method.md").read_text(encoding="utf-8")
        assert "occupied-space ventilation calculation" in instruction
        assert "Do not infer or mention either probe task" in instruction
        assert len(context.feedback) == 1
        episode = json.loads(context.feedback[0].path.read_text(encoding="utf-8"))
        assert episode["terminal_outcome"]["reward"] == 1.0
        assert "Brisbane" in episode["instruction"]
        context.memory_root.mkdir(parents=True, exist_ok=True)
        (context.memory_root / "method.json").write_text(
            json.dumps(
                {
                    "method": "For occupied spaces, calculate people from area and outside air per person.",
                    "applicability": "Use another ventilation regime only when the task evidence requires it.",
                    "check": "Recalculate each room value; do not copy acquisition values.",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    binding = build_artifact_learning_operations(
        tasks_root=_TASKS_ROOT,
        run_root=run_root,
        treatment_kinds={
            "reset": ArtifactLearningTreatmentKind.RESET,
            "structured-memory": ArtifactLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={
            "heat-load-public-episode": public_episode_feedback,
            "heat-load-actor-episode": public_actor_episode,
        },
        consolidation_operations={"consolidate-occupied-heat-load-method": consolidate_method},
        adapter_builder=lambda **kwargs: RetentionInterferenceStudyAdapter(
            Path(kwargs["workspace"]),
            neutral_output=neutral_output,
            observations=observations,
        ),
    )
    recorder = StudyRunRecorder(
        root=run_root,
        plan=plan,
        snapshot_state=binding.snapshot_state,
        feedback_artifacts=binding.feedback_artifacts,
    )

    execution = asyncio.run(
        run_learning_study(
            plan=plan,
            operations=binding.operations,
            working_root=run_root,
            observer=recorder,
        )
    )

    assert all(arm.status is ArmRunStatus.COMPLETED for arm in execution.arm_runs), execution
    assert [len(arm.trial_records) for arm in execution.arm_runs] == [1, 2, 2, 2, 4, 4]
    assert all(isinstance(record, TrialRecord) for arm in execution.arm_runs for record in arm.trial_records)
    assert all(not record.extension_refs for arm in execution.arm_runs for record in arm.trial_records)
    runs = {planned.arm_id: actual for planned, actual in zip(plan.arm_runs, execution.arm_runs, strict=True)}

    def reward(arm_id: str, index: int) -> float:
        evaluation = runs[arm_id].trial_records[index].evaluation
        assert evaluation is not None
        return evaluation.reward

    assert reward("cold-immediate", 0) == 0.0
    assert [reward("cold-delayed-neutral", index) for index in range(2)] == [1.0, 0.0]
    assert [reward("cold-delayed-interference", index) for index in range(2)] == [1.0, 0.0]
    assert [reward("immediate-transfer", index) for index in range(2)] == [1.0, 1.0]
    assert [reward("neutral-retention", index) for index in range(4)] == [1.0, 1.0, 1.0, 1.0]
    interference_probe_reward = reward("interference", 3)
    assert [reward("interference", index) for index in range(3)] == [1.0, 1.0, 1.0]
    assert interference_probe_reward == 0.25

    assert len(observations) == 15
    assert all(not item["has_verifier"] for item in observations)
    adelaide = [item for item in observations if item["task"] == "adelaide"]
    assert len(adelaide) == 4
    assert sum(bool(item["has_memory"]) for item in adelaide) == 2
    assert sum(bool(item["has_interference_episode"]) for item in adelaide) == 1
    assert next(item for item in adelaide if item["has_interference_episode"])["feedback_count"] == 2
    assert any(item["task"] == "neutral-drainage" and item["has_memory"] for item in observations)
    assert any(item["task"] == "cairns" and item["has_memory"] for item in observations)

    neutral_root = run_root / "learner-arms" / "a03-stage-1--neutral-retention--r01" / "states"
    assert (neutral_root / "neutral-consolidation").is_dir()
    assert not (neutral_root / "neutral-immediate-probe").exists()
    assert not (neutral_root / "neutral-intervening-task").exists()
    assert not (neutral_root / "neutral-delayed-probe").exists()
    interference_root = run_root / "learner-arms" / "a03-stage-1--interference--r01" / "states"
    assert not (interference_root / "interference-immediate-probe").exists()
    assert _state_files(interference_root / "interference-consolidation") == _state_files(
        interference_root / "interference-task"
    )
    interference_feedback_root = interference_root / "interference-episode" / ".aec-bench-learning" / "feedback"
    assert len(list(interference_feedback_root.glob("*"))) == 2
    interference_episode = json.loads((interference_feedback_root / "interference-episode.json").read_text())
    assert set(interference_episode) == {"instruction", "selected_output", "task_id"}
    assert interference_episode["task_id"].endswith("cairns-server-60m2")
    assert not (interference_root / "interference-delayed-probe").exists()

    evidence = {
        arm.arm_run_id: AssessmentArmEvidence(
            arm_run_id=arm.arm_run_id,
            adapter_id="local-artifact-single-attempt",
            initial_state_equivalence_id="a03-empty-fixed-agent-state-r01",
            family_reviewed=False,
        )
        for arm in plan.arm_runs
    }
    assessment = assess_learning_study(
        spec=spec,
        plan=plan,
        execution=execution,
        projections={"heat-load-verifier-reward": project_trial_reward},
        arm_evidence=evidence,
    )
    results = {item.measurement_id: item for item in assessment.measurements}
    assert all(item.validity is LearningComparisonValidity.DESCRIPTIVE_ONLY for item in results.values())
    assert results["immediate-transfer-gain"].mean_effect == 1.0
    assert results["retained-gain-after-neutral"].mean_effect == 1.0
    assert results["within-order-retention-decay"].mean_effect == 0.0
    assert results["interference-effect"].mean_effect == -0.75
    assert results["reset-interference-control"].mean_effect == 0.0
    assert all(len(item.included_pairs) == 1 for item in results.values())
