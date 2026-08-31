# ABOUTME: Runs the A02 drainage applicability boundary through real tasks and verifiers.
# ABOUTME: Proves deterministic public-output projections without an LLM judge.

import asyncio
import json
from pathlib import Path

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity, ProjectionResult
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.artifact_tasks import (
    ArtifactConsolidationContext,
    ArtifactLearningTreatmentKind,
    build_artifact_learning_operations,
    public_episode_feedback,
)
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    assess_learning_study,
)
from aec_bench.experimentation.learning_studies.families import load_learning_family
from aec_bench.experimentation.learning_studies.planning import compile_learning_study
from aec_bench.experimentation.learning_studies.protocol_collection import (
    BUILTIN_LEARNING_STUDY_PROTOCOLS,
    load_learning_study_protocol,
)
from aec_bench.experimentation.learning_studies.recording import StudyRunRecorder
from aec_bench.experimentation.learning_studies.runtime import ArmRunStatus, run_learning_study
from aec_bench.tasks.loader import load_task_definition
from aec_bench.templates.builtin.civil.drainage_model_run_provenance_issue_review_package.outcomes import (
    has_correct_downstream_memo_boundary_decision,
    has_upstream_model_invalidation_decision,
)
from tests.experimentation.learning_studies.support import DrainageBoundaryStudyAdapter

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_AGENT = AgentConfig(name="a02-test-agent", adapter="direct", model="fixed-test-model")
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)
_PROTOCOL_PATH = BUILTIN_LEARNING_STUDY_PROTOCOLS / "a02-artifact-applicability-boundary"
_ACQUISITION_TASK_ID = (
    "civil/drainage-review/drainage-model-run-provenance-issue-review-package/"
    "brownfield-drainage-upgrade-industrial-precinct-catchment-02"
)
_PROBE_TASK_ID = (
    "civil/drainage-review/drainage-model-run-provenance-issue-review-package/"
    "industrial-precinct-catchment-industrial-precinct-catchment-00"
)
_BOUNDARY_PROJECTION_ID = "drainage-boundary-judgment"
_UPSTREAM_INVALIDATION_PROJECTION_ID = "drainage-upstream-invalidation"
_FEEDBACK_VIEW_ID = "drainage-public-episode"
_CONSOLIDATION_OPERATION_ID = "update-applicability-memory"


def _resolve_task_definition(task_id: str):  # noqa: ANN202
    return load_task_definition(_TASKS_ROOT / task_id, _TASKS_ROOT)


def _golden_output(task_id: str) -> str:
    return (_TASKS_ROOT / task_id / "tests" / "fixtures" / "golden_pass.md").read_text(encoding="utf-8")


def _public_output_text(record: TrialRecord) -> str:
    path_value = None if record.output is None else record.output.raw_output_path
    if path_value is None:
        return ""
    return Path(path_value).read_text(encoding="utf-8")


def _project_boundary_judgment(record: TrialRecord) -> ProjectionResult:
    correct = has_correct_downstream_memo_boundary_decision(_public_output_text(record))
    return ProjectionResult(eligible=True, value=float(correct), lower_bound=0.0, upper_bound=1.0)


def _project_upstream_invalidation(record: TrialRecord) -> ProjectionResult:
    invalidated = has_upstream_model_invalidation_decision(_public_output_text(record))
    return ProjectionResult(eligible=True, value=float(invalidated), lower_bound=0.0, upper_bound=1.0)


def test_a02_real_artifact_tasks_identify_upstream_invalidation_from_public_output(tmp_path: Path) -> None:
    spec = load_learning_study_protocol(_PROTOCOL_PATH, agent=_AGENT, compute=_COMPUTE)
    family = load_learning_family(_PROTOCOL_PATH / "family.toml")
    relation = next(item for item in family.relations if item.relation_id == "stale-upstream-to-stale-downstream")
    members = {item.member_id: item for item in family.members}
    assert [members[item].task_id for item in relation.source_member_ids] == [_ACQUISITION_TASK_ID]
    assert members[relation.target_member_id].task_id == _PROBE_TASK_ID
    plan = compile_learning_study(
        study_run_id="a02-stage-1",
        spec=spec,
        resolve_task=_resolve_task_definition,
    )

    observations: list[dict[str, object]] = []
    acquisition_output = _golden_output(_ACQUISITION_TASK_ID)
    probe_output = _golden_output(_PROBE_TASK_ID)
    run_root = tmp_path / "a02-stage-1"

    def consolidate_applicability(context: ArtifactConsolidationContext) -> None:
        instruction = (_PROTOCOL_PATH / "consolidate-applicability-memory.md").read_text(encoding="utf-8")
        assert "evidence preconditions" in instruction
        assert "Do not infer or mention a later probe task" in instruction
        assert len(context.feedback) == 1
        episode = json.loads(context.feedback[0].path.read_text(encoding="utf-8"))
        assert set(episode) == {"instruction", "selected_output", "terminal_outcome"}
        assert episode["terminal_outcome"]["reward"] == 1.0
        assert '"PRV-03"' in episode["selected_output"]
        context.memory_root.mkdir(parents=True, exist_ok=True)
        (context.memory_root / "applicability.json").write_text(
            json.dumps(
                {
                    "method": "Trace the defect through the provenance chain and localize its transition scope.",
                    "precondition": "Invalidate the run only when a governing model input or run identity is stale.",
                    "disconfirming_evidence": "Current model inputs and run identity disprove upstream staleness.",
                    "stopping_condition": "Keep upstream evidence governing when only downstream propagation is stale.",
                    "known_failure_mode": "Copying the acquisition transition creates a false upstream rejection.",
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
            "raw-history": ArtifactLearningTreatmentKind.RAW_HISTORY,
            "structured-memory": ArtifactLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={_FEEDBACK_VIEW_ID: public_episode_feedback},
        consolidation_operations={_CONSOLIDATION_OPERATION_ID: consolidate_applicability},
        adapter_builder=lambda **kwargs: DrainageBoundaryStudyAdapter(
            Path(kwargs["workspace"]),
            acquisition_output=acquisition_output,
            probe_output=probe_output,
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
            observer=recorder,
        )
    )

    assert all(arm.status is ArmRunStatus.COMPLETED for arm in execution.arm_runs), execution
    assert [len(arm.trial_records) for arm in execution.arm_runs] == [1, 2, 2, 2]
    records = [record for arm in execution.arm_runs for record in arm.trial_records]
    assert all(isinstance(record, TrialRecord) for record in records)
    assert all(not record.extension_refs for record in records)
    raw_probe = execution.arm_runs[2].trial_records[-1]
    assert raw_probe.evaluation is not None and raw_probe.evaluation.reward == 0.82
    assert all(
        record.evaluation is not None and record.evaluation.reward == 1.0
        for arm_index, arm in enumerate(execution.arm_runs)
        for record_index, record in enumerate(arm.trial_records)
        if (arm_index, record_index) != (2, len(arm.trial_records) - 1)
    )

    assert observations == [
        {"task": "probe", "has_history": False, "has_memory": False, "has_feedback": False, "has_verifier": False},
        {
            "task": "acquisition",
            "has_history": False,
            "has_memory": False,
            "has_feedback": False,
            "has_verifier": False,
        },
        {"task": "probe", "has_history": False, "has_memory": False, "has_feedback": False, "has_verifier": False},
        {
            "task": "acquisition",
            "has_history": False,
            "has_memory": False,
            "has_feedback": False,
            "has_verifier": False,
        },
        {"task": "probe", "has_history": True, "has_memory": False, "has_feedback": True, "has_verifier": False},
        {
            "task": "acquisition",
            "has_history": False,
            "has_memory": False,
            "has_feedback": False,
            "has_verifier": False,
        },
        {"task": "probe", "has_history": False, "has_memory": True, "has_feedback": True, "has_verifier": False},
    ]

    raw_root = run_root / "learner-arms" / "a02-stage-1--raw-history--r01"
    history_path = raw_root / "states" / "raw-release" / ".aec-bench-learning" / "history" / "raw-release.json"
    history = json.loads(history_path.read_text(encoding="utf-8"))
    assert set(history) == {"feedback_view_id", "public_feedback", "source_experience_id"}
    assert history["source_experience_id"] == "stale-upstream-acquisition"
    assert set(history["public_feedback"]) == {"instruction", "selected_output", "terminal_outcome"}
    assert set(history["public_feedback"]["terminal_outcome"]) == {
        "execution_status",
        "reward",
        "task_id",
        "trial_id",
        "validity",
    }
    state_files = [path for path in (run_root / "learner-arms").rglob("*") if path.is_file() and "states" in path.parts]
    assert all("tests" not in path.parts and "verifier" not in path.parts for path in state_files)
    for arm_run, probe_step in zip(
        plan.arm_runs, ("cold-probe", "reset-probe", "raw-probe", "structured-probe"), strict=True
    ):
        arm_root = run_root / "learner-arms" / arm_run.arm_run_id
        assert not (arm_root / "states" / probe_step).exists()

    evidence = {
        arm.arm_run_id: AssessmentArmEvidence(
            adapter_id="local-artifact-single-attempt",
            initial_state_equivalence_id="a02-empty-fixed-agent-state-r01",
            arm_isolated=True,
            lineage_complete=True,
            probe_feedback_hidden=True,
            probe_state_discarded=True,
            hidden_evaluation_leaked=False,
        )
        for arm in plan.arm_runs
    }
    assessment = assess_learning_study(
        spec=spec,
        plan=plan,
        execution=execution,
        projections={
            _BOUNDARY_PROJECTION_ID: _project_boundary_judgment,
            _UPSTREAM_INVALIDATION_PROJECTION_ID: _project_upstream_invalidation,
        },
        arm_evidence=evidence,
        relations_reviewed=False,
    )
    results = {item.measurement_id: item for item in assessment.measurements}
    assert all(item.validity is LearningComparisonValidity.DESCRIPTIVE_ONLY for item in results.values())
    assert results["raw-history-boundary-gain"].mean_effect == -1.0
    assert results["structured-memory-boundary-gain"].mean_effect == 0.0
    assert results["raw-history-upstream-invalidation-effect"].mean_effect == -1.0
    assert results["structured-memory-upstream-invalidation-effect"].mean_effect == 0.0
    assert results["reset-after-acquisition-boundary-effect"].mean_effect == 0.0
    assert results["structured-memory-advantage"].mean_effect == 1.0
