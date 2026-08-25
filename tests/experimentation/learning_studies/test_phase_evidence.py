from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.learning_study import (
    ExperienceRole,
    LearningArmSpec,
    LearningExperienceSpec,
    LearningStudySpec,
    RunExperienceStep,
    StudyArmRole,
)
from aec_bench.contracts.trial_record import TrialExtensionRef, TrialRecord
from aec_bench.experimentation.learning_studies.lifecycles import (
    LifecycleExecutionCondition,
    LifecycleLearningTreatmentKind,
    build_lifecycle_learning_operations,
    resolve_lifecycle_learning_target,
)
from aec_bench.experimentation.learning_studies.phase_evidence import group_phase_evidence
from aec_bench.experimentation.learning_studies.planning import CompiledExperienceStep, compile_learning_study
from aec_bench.experimentation.learning_studies.runtime import ExecuteExperienceRequest
from aec_bench.ledger.artifact_repository import ArtifactRepository
from aec_bench.ledger.reader import read_trial_record
from aec_bench.ledger.writer import write_trial_record_at
from aec_bench.lifecycles.runtime.episode import LifecycleExecutionMode, LifecycleVisibilityPolicy
from aec_bench.lifecycles.stormwater_design.drainage_learning import (
    DrainageLearningEvidence,
    extract_drainage_learning_evidence,
)
from aec_bench.lifecycles.structural_review.facade_submittal import (
    FacadeLearningEvidence,
    extract_facade_learning_evidence,
)
from tests.support.trial_record_factories import make_trial_record

_DRAINAGE_TASK = "lifecycle/drainage-model-evidence-lifecycle-review/staged_full_correction"
_FACADE_TASK = "lifecycle/facade-submittal-review-lifecycle"
_DRAINAGE_GATES = (
    "checkpoint_contract",
    "reviewer_self_consistency",
    "staged_disclosure",
    "finding_continuity",
    "closure_evidence",
    "accepted_decision_preservation",
    "final_readiness",
    "claim_boundary",
)
_FACADE_GATES = (
    "checkpoint_contract",
    "evidence_use",
    "metric_accuracy",
    "finding_continuity",
    "review_decision",
    "claim_boundary",
)


def _record_with_submissions(tmp_path: Path, *, task_id: str, checkpoints: tuple[str, ...]) -> TrialRecord:
    run_dir = tmp_path / task_id.rsplit("/", 1)[-1] / "run"
    for checkpoint_id in checkpoints:
        path = run_dir / "episodes" / checkpoint_id / "submission.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if task_id == _DRAINAGE_TASK:
            payload = {
                "checkpoint_id": checkpoint_id,
                "evidence_refs": ["evidence-a"],
                "review_matrix": {"PRV-01": "pass"},
                "transition_decision": {"design_claim": "supported"},
                "findings": [],
                "closure_evidence_requests": [],
                "accepted_decisions": [],
                "readiness_decision": "ready",
                "claim_boundary_statement": "synthetic review only",
            }
        else:
            payload = {
                "checkpoint_id": checkpoint_id,
                "evidence_refs": ["facade-source-index"],
                "metrics": {"source_trace_score": 1.0},
                "findings": [],
                "review_decision": "continue_review",
                "readiness": "review_in_progress",
                "claim_boundary": {
                    "evidence_class": "task_owned_synthetic_review",
                    "authority_status": "no_authority_approval",
                    "project_evidence_status": "not_project_evidence",
                    "standards_status": "no_standards_compliance_claim",
                },
            }
        path.write_text(json.dumps(payload), encoding="utf-8")
    gates = _DRAINAGE_GATES if task_id == _DRAINAGE_TASK else _FACADE_GATES
    evaluation = EvaluationResult(
        reward=1.0,
        validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
        breakdown={"lifecycle_gates": {gate: {"passed": True, "score": 1.0} for gate in gates}},
    )
    return make_trial_record(
        task_id=task_id,
        outputs={
            "agent_output": {
                "status": "completed",
                "output_path": str(run_dir.resolve()),
                "output_format": "json",
            }
        },
        evaluation=evaluation,
    )


def test_drainage_evidence_emits_the_declared_phase_mapping(tmp_path: Path) -> None:
    evidence = extract_drainage_learning_evidence(
        _record_with_submissions(
            tmp_path,
            task_id=_DRAINAGE_TASK,
            checkpoints=("initial_review", "response_review", "closeout_review"),
        )
    )

    assert isinstance(evidence, DrainageLearningEvidence)
    assert [(item.phase_id, item.checkpoint_ids) for item in evidence.phase_records] == [
        ("evidence_assessment", ("initial_review",)),
        ("response_and_closeout", ("response_review", "closeout_review")),
    ]
    assert evidence.phase_records[0].submissions_accepted == 1
    assert evidence.phase_records[0].rework_events is None


def test_facade_evidence_emits_the_declared_phase_mapping(tmp_path: Path) -> None:
    evidence = extract_facade_learning_evidence(
        _record_with_submissions(
            tmp_path,
            task_id=_FACADE_TASK,
            checkpoints=("source_review", "comment_review", "response_review"),
        )
    )

    assert isinstance(evidence, FacadeLearningEvidence)
    assert [(item.phase_id, item.checkpoint_ids) for item in evidence.phase_records] == [
        ("source_assessment", ("source_review",)),
        ("review_and_response", ("comment_review", "response_review")),
    ]
    assert evidence.phase_records[0].metric_accuracy_pass is True
    assert evidence.phase_records[0].evidence_refs_expected is None


def test_evidence_extractors_fail_closed_when_evidence_is_missing(tmp_path: Path) -> None:
    drainage = make_trial_record(task_id=_DRAINAGE_TASK)
    facade = make_trial_record(task_id=_FACADE_TASK)

    assert extract_drainage_learning_evidence(drainage) is None
    assert extract_facade_learning_evidence(facade) is None


def _lifecycle_plan(task_id: str):
    spec = LearningStudySpec(
        study_id="phase-evidence-test",
        title="phase evidence",
        research_question="does the lifecycle adapter attach task evidence?",
        agent={
            "name": "phase-evidence-agent",
            "adapter": "tool_loop",
            "model": "fixed-test-model",
            "parameters": {"max_turns_per_session": 1},
        },
        compute={"backend": "local", "resource_limits": {"memory_mb": 256}, "timeout_override": 30},
        repetitions=1,
        experiences=(LearningExperienceSpec(experience_id="probe", task_id=task_id, role=ExperienceRole.PROBE),),
        arms=(
            LearningArmSpec(
                arm_id="cold",
                role=StudyArmRole.CONTROL,
                treatment_id="reset",
                steps=(RunExperienceStep(step_id="probe-step", experience_id="probe", commit_post_state=False),),
            ),
        ),
    )
    return compile_learning_study(
        study_run_id="phase-evidence-test-run",
        spec=spec,
        resolve_task=resolve_lifecycle_learning_target,
    )


def _fake_lifecycle_calls(monkeypatch: pytest.MonkeyPatch, task_id: str) -> None:
    from aec_bench.experimentation.learning_studies import lifecycles as adapter

    def compile_fake(template_id: str, package_dir: Path, *, variant_id: str | None = None):  # noqa: ANN202
        package_dir.mkdir(parents=True)
        return SimpleNamespace(
            package_dir=package_dir,
            envelope=SimpleNamespace(template_id=template_id, variant_id=variant_id),
        )

    def run_fake(*, trial, execute, verify, persist=None):  # noqa: ANN001, ANN202, ARG001
        trial.run_dir.mkdir(parents=True)
        return make_trial_record(
            trial_id=trial.planned.trial_id,
            experiment_id=trial.planned.experiment_id,
            task_id=task_id,
            attempt=trial.planned.repetition,
        )

    monkeypatch.setattr(adapter, "compile_lifecycle", compile_fake)
    monkeypatch.setattr(adapter, "run_lifecycle_trial", run_fake)


def _binding(tmp_path: Path, *, extractor=None):  # noqa: ANN001, ANN202
    return build_lifecycle_learning_operations(
        run_root=tmp_path / "study",
        execution_condition=LifecycleExecutionCondition(
            execution_mode=LifecycleExecutionMode.FRESH_CONTEXT,
            visibility_policy=LifecycleVisibilityPolicy.ARTIFACT_MEMORY,
        ),
        treatment_kinds={"reset": LifecycleLearningTreatmentKind.RESET},
        phase_evidence_extractors=(
            None if extractor is None else {"drainage-model-evidence-lifecycle-review": extractor}
        ),
    )


def test_coordinator_attaches_evidence_and_ledger_round_trips_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_lifecycle_calls(monkeypatch, _DRAINAGE_TASK)
    plan = _lifecycle_plan(_DRAINAGE_TASK)
    evidence = DrainageLearningEvidence(
        lifecycle_template_id="drainage-model-evidence-lifecycle-review",
        variant_id="staged_full_correction",
        phase_records=(
            {
                "phase_id": "evidence_assessment",
                "checkpoint_ids": ("initial_review",),
                "phase_outcome": "complete",
            },
        ),
    )
    binding = _binding(tmp_path, extractor=lambda record: evidence)
    state = binding.operations.initialise_learner(plan.arm_runs[0])
    step = plan.arm_runs[0].steps[0]
    assert isinstance(step, CompiledExperienceStep)
    record = binding.operations.execute_experience(
        request=ExecuteExperienceRequest(arm_run=plan.arm_runs[0], step=step, state=state)
    ).trial_record
    assert record is not None
    assert record.pending_extensions["lifecycle_learning_evidence"] == evidence

    path = write_trial_record_at(path=tmp_path / "ledger" / "experiment" / "trial.json", record=record)
    restored = read_trial_record(path, ledger_root=tmp_path / "ledger")
    extension = next(item for item in restored.extension_refs if item.extension_kind == "lifecycle_learning_evidence")
    raw = ArtifactRepository(tmp_path / "ledger" / "experiment" / "_artifacts").read_bytes(extension.artifact)
    assert DrainageLearningEvidence.model_validate_json(raw) == evidence


def test_coordinator_without_extractor_has_no_extension(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_lifecycle_calls(monkeypatch, _DRAINAGE_TASK)
    plan = _lifecycle_plan(_DRAINAGE_TASK)
    binding = _binding(tmp_path)
    state = binding.operations.initialise_learner(plan.arm_runs[0])
    step = plan.arm_runs[0].steps[0]
    assert isinstance(step, CompiledExperienceStep)
    record = binding.operations.execute_experience(
        ExecuteExperienceRequest(arm_run=plan.arm_runs[0], step=step, state=state)
    ).trial_record
    assert record is not None
    assert record.extension_refs == ()
    assert "lifecycle_learning_evidence" not in record.pending_extensions


def test_facade_evidence_round_trips_through_the_ledger(tmp_path: Path) -> None:
    record = _record_with_submissions(
        tmp_path,
        task_id=_FACADE_TASK,
        checkpoints=("source_review", "comment_review", "response_review"),
    )
    evidence = extract_facade_learning_evidence(record)
    assert evidence is not None
    record.attach_extension("lifecycle_learning_evidence", evidence)

    path = write_trial_record_at(path=tmp_path / "ledger" / "experiment" / "facade.json", record=record)
    restored = read_trial_record(path, ledger_root=tmp_path / "ledger")
    extension = next(item for item in restored.extension_refs if item.extension_kind == "lifecycle_learning_evidence")
    raw = ArtifactRepository(tmp_path / "ledger" / "experiment" / "_artifacts").read_bytes(extension.artifact)

    assert FacadeLearningEvidence.model_validate_json(raw) == evidence


def test_phase_grouping_is_opaque_and_fail_closed(tmp_path: Path) -> None:
    repository = ArtifactRepository(tmp_path / "artifacts")
    drainage = make_trial_record(task_id=_DRAINAGE_TASK, trial_id="drainage-trial")
    facade = make_trial_record(task_id=_FACADE_TASK, trial_id="facade-trial")
    drainage_model = DrainageLearningEvidence(
        lifecycle_template_id="drainage-model-evidence-lifecycle-review",
        variant_id="staged_full_correction",
        phase_records=(
            {"phase_id": "evidence_assessment", "checkpoint_ids": ("initial_review",), "phase_outcome": "complete"},
        ),
    )
    facade_model = FacadeLearningEvidence(
        lifecycle_template_id="facade-submittal-review-lifecycle",
        phase_records=(
            {
                "phase_id": "source_assessment",
                "checkpoint_ids": ("source_review",),
                "phase_outcome": "complete",
                "evidence_refs_cited": 1,
                "metric_accuracy_pass": True,
                "finding_continuity_pass": True,
                "review_decision_correct": True,
            },
        ),
    )
    drainage_ref = repository.publish_model(value=drainage_model, media_type="application/json")
    facade_ref = repository.publish_model(value=facade_model, media_type="application/json")
    malformed_ref = repository.publish_bytes(data=b"{", media_type="application/json")
    missing_ref = repository.publish_bytes(data=b'{"phase_records":[{}]}', media_type="application/json")
    unknown_ref = repository.publish_bytes(
        data=b'{"phase_records":[{"phase_id":"ignored"}]}',
        media_type="application/json",
    )
    drainage.extension_refs = (TrialExtensionRef(extension_kind="lifecycle_learning_evidence", artifact=drainage_ref),)
    facade.extension_refs = (TrialExtensionRef(extension_kind="lifecycle_learning_evidence", artifact=facade_ref),)
    malformed = make_trial_record(task_id=_FACADE_TASK, trial_id="malformed")
    malformed.extension_refs = (
        TrialExtensionRef(extension_kind="lifecycle_learning_evidence", artifact=malformed_ref),
    )
    missing = make_trial_record(task_id=_FACADE_TASK, trial_id="missing")
    missing.extension_refs = (TrialExtensionRef(extension_kind="lifecycle_learning_evidence", artifact=missing_ref),)
    unknown = make_trial_record(task_id=_FACADE_TASK, trial_id="unknown")
    unknown.extension_refs = (TrialExtensionRef(extension_kind="other", artifact=unknown_ref),)

    groups = group_phase_evidence([drainage, facade, malformed, missing, unknown], artifact_repository=repository)

    assert {phase_id: [entry.trial_id for entry in entries] for phase_id, entries in groups.items()} == {
        "evidence_assessment": ["drainage-trial"],
        "source_assessment": ["facade-trial"],
    }
    source = Path("src/aec_bench/experimentation/learning_studies/phase_evidence.py").read_text()
    assert "stormwater_design" not in source
    assert "structural_review" not in source
