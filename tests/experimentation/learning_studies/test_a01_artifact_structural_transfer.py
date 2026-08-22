# ABOUTME: Runs the A01 Stage 1 study through real artifact tasks and verifiers.
# ABOUTME: Proves the cold-to-exposed comparison while making no model-learning claim.

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
    terminal_outcome_feedback,
)
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    assess_learning_study,
    project_trial_reward,
)
from aec_bench.experimentation.learning_studies.families import (
    load_learning_family,
    resolve_learning_family,
    resolve_learning_relation,
)
from aec_bench.experimentation.learning_studies.planning import compile_learning_study
from aec_bench.experimentation.learning_studies.protocol_collection import (
    BUILTIN_LEARNING_STUDY_PROTOCOLS,
    load_learning_study_protocol,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.resume import load_resumable_study
from aec_bench.experimentation.learning_studies.runtime import ArmRunStatus, run_learning_study
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition
from tests.experimentation.learning_studies.support import HeatLoadStudyAdapter

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_PROTOCOL_PATH = BUILTIN_LEARNING_STUDY_PROTOCOLS / "a01-artifact-structural-transfer"
_FEEDBACK_VIEW_ID = "heat-load-public-evaluation"
_CONSOLIDATION_OPERATION_ID = "update-structured-memory"
_PROJECTION_ID = "heat-load-verifier-reward"


def _resolve_task_definition(task_id: str):  # noqa: ANN202
    return load_task_definition(_TASKS_ROOT / task_id, _TASKS_ROOT)


def _resolve_task_instance(task_id: str):  # noqa: ANN202
    instance_dir = _TASKS_ROOT / task_id
    return resolve_instance_paths(load_task_definition(instance_dir, _TASKS_ROOT), instance_dir)


def test_a01_real_artifact_tasks_return_a_matched_structural_transfer_result(tmp_path: Path) -> None:
    spec = load_learning_study_protocol(
        _PROTOCOL_PATH,
        agent=AgentConfig(name="a01-test-agent", adapter="direct", model="fixed-test-model"),
        compute=ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30),
    )
    family = resolve_learning_family(
        load_learning_family(_PROTOCOL_PATH / "family.toml"),
        _resolve_task_instance,
    )
    family_relation = resolve_learning_relation(family, "brisbane-office-to-sydney-classroom")
    assert [item.task.task.task_id for item in family_relation.sources] == [spec.experiences[0].task_id]
    assert family_relation.target.task.task.task_id == spec.experiences[1].task_id
    plan = compile_learning_study(
        study_run_id="a01-stage-1",
        spec=spec,
        resolve_task=_resolve_task_definition,
    )

    observations: list[dict[str, object]] = []
    run_root = tmp_path / "a01-stage-1"

    def consolidate_method(context: ArtifactConsolidationContext) -> None:
        assert len(context.feedback) == 1
        public_feedback = json.loads(context.feedback[0].path.read_text(encoding="utf-8"))
        assert public_feedback["reward"] == 1.0
        assert set(public_feedback) == {"execution_status", "reward", "task_id", "trial_id", "validity"}
        assert set(public_feedback["validity"]) == {
            "output_parseable",
            "schema_valid",
            "verifier_completed",
        }
        context.memory_root.mkdir(parents=True, exist_ok=True)
        (context.memory_root / "method.json").write_text(
            json.dumps(
                {
                    "applicability": "Use the room-type values stated in the task.",
                    "method": "Calculate occupancy, outside air, component loads, then sensible and latent totals.",
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
        feedback_projectors={_FEEDBACK_VIEW_ID: terminal_outcome_feedback},
        consolidation_operations={_CONSOLIDATION_OPERATION_ID: consolidate_method},
        adapter_builder=lambda **kwargs: HeatLoadStudyAdapter(Path(kwargs["workspace"]), observations),
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
    assert [len(arm.trial_records) for arm in execution.arm_runs] == [1, 2]
    records = [record for arm in execution.arm_runs for record in arm.trial_records]
    assert all(isinstance(record, TrialRecord) for record in records)
    assert all(not record.extension_refs for record in records)
    rewards = [record.evaluation.reward for record in records if record.evaluation is not None]
    assert rewards == [0.0, 1.0, 1.0]

    assert observations == [
        {
            "location": "sydney",
            "has_memory": False,
            "has_feedback": False,
            "has_verifier": False,
            "has_family_file": False,
        },
        {
            "location": "brisbane",
            "has_memory": False,
            "has_feedback": False,
            "has_verifier": False,
            "has_family_file": False,
        },
        {
            "location": "sydney",
            "has_memory": True,
            "has_feedback": True,
            "has_verifier": False,
            "has_family_file": False,
        },
    ]

    cold_root = run_root / "learner-arms" / "a01-stage-1--cold-reset--r01"
    exposed_root = run_root / "learner-arms" / "a01-stage-1--structured-memory--r01"
    assert cold_root != exposed_root
    assert not (cold_root / "states" / "cold-probe").exists()
    assert not (exposed_root / "states" / "exposed-probe").exists()
    committed_memory = exposed_root / "states" / "consolidate-method" / ".aec-bench-learning" / "memory" / "method.json"
    assert committed_memory.is_file()
    state_files = [path for path in (run_root / "learner-arms").rglob("*") if path.is_file() and "states" in path.parts]
    assert all("tests" not in path.parts and "verifier" not in path.parts for path in state_files)
    assert all(path.name != "output.md" for path in state_files)

    evidence = {
        arm.arm_run_id: AssessmentArmEvidence(
            arm_run_id=arm.arm_run_id,
            adapter_id="local-artifact-single-attempt",
            initial_state_equivalence_id="a01-empty-fixed-agent-state-r01",
            family_reviewed=False,
        )
        for arm in plan.arm_runs
    }
    assessment = assess_learning_study(
        spec=spec,
        plan=plan,
        execution=execution,
        projections={_PROJECTION_ID: project_trial_reward},
        arm_evidence=evidence,
    )

    result = assessment.measurements[0]
    assert result.validity is LearningComparisonValidity.DESCRIPTIVE_ONLY
    assert result.focal_mean == 1.0
    assert result.comparator_mean == 0.0
    assert result.mean_effect == 1.0
    assert len(result.included_pairs) == 1
    assert result.included_pairs[0].repetition == 1
    assert "learning-family relation is not reviewed" in " ".join(result.diagnostics)

    assert (run_root / "study-spec.json").is_file()
    assert (run_root / "study-plan.json").is_file()
    assert (run_root / "events.jsonl").is_file()
    assert (run_root / "result.json").is_file()

    resumable = load_resumable_study(
        root=run_root,
        plan=plan,
        restore_root=tmp_path / "restored",
        snapshot_state=binding.snapshot_state,
        restore_state=binding.restore_state,
        restore_feedback=binding.restore_feedback,
        feedback_artifacts=binding.feedback_artifacts,
    )
    resumed_execution = asyncio.run(
        run_learning_study(
            plan=plan,
            operations=binding.operations,
            working_root=run_root,
            observer=resumable.recorder,
            resume=resumable.resume,
        )
    )
    assert [item.arm_run_id for item in resumed_execution.arm_runs] == [item.arm_run_id for item in execution.arm_runs]
    assert len(observations) == 3
