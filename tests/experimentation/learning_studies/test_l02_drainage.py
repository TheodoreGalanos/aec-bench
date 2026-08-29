# ABOUTME: Proves the deterministic four-arm L02 drainage applicability-boundary campaign.
# ABOUTME: Covers treatment isolation, matched surfaces, acquisition fidelity, and bounded projections.

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.contracts.trial_record import EvaluationStatus
from aec_bench.experimentation.learning_studies.l02_drainage import (
    L02_ACQUISITION_TASK_ID,
    L02_CONSOLIDATION_OPERATION_ID,
    L02_DRAINAGE_STUDY_ID,
    L02_EXECUTION_CONDITION,
    L02_PROBE_TASK_ID,
    compile_l02_drainage_study,
    l02_drainage_outcome_projections,
    load_l02_drainage_protocol,
    run_l02_drainage_study_sync,
)
from aec_bench.experimentation.learning_studies.lifecycles import LifecycleConsolidationContext
from aec_bench.lifecycles.catalogue import materialize_lifecycle
from aec_bench.lifecycles.compiled import compile_lifecycle
from aec_bench.lifecycles.runtime.lifecycle import run_lifecycle
from aec_bench.lifecycles.stormwater_design import drainage_learning
from aec_bench.lifecycles.stormwater_design.drainage_model import verify_drainage_model_lifecycle
from tests.support.lifecycle_episode import deterministic_episode_environment
from tests.support.trial_record_factories import make_trial_record

_AGENT = AgentConfig(name="l02-deterministic-agent", adapter="tool_loop", model="fixed-test-model", parameters={})
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512})


class _Consolidator:
    calls = 0

    def __call__(self, context: LifecycleConsolidationContext) -> None:
        type(self).calls += 1
        (context.memory_root / "review-strategy.md").write_text("Use current registered evidence.\n", encoding="utf-8")


class _GoldAdapterBuilder:
    executions = 0
    contexts: dict[tuple[str, str], list[set[str]]] = {}

    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        package = workspace.parent.parent / "package"
        arm_id = package.parents[2].name
        variant = json.loads((package / "hidden" / "variant.json").read_text())["variant_id"]
        gold = json.loads((package / "hidden" / "gold-submissions.json").read_text())
        builder = self

        class Adapter:
            def execute(self, request):  # noqa: ANN001, ANN202
                type(builder).executions += 1
                context = workspace / "learner_context"
                visible = (
                    {path.relative_to(context).as_posix() for path in context.rglob("*") if path.is_file()}
                    if context.exists()
                    else set()
                )
                builder.contexts.setdefault((arm_id, variant), []).append(visible)
                output = Path(request.output_path)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(gold[output.stem]), encoding="utf-8")
                return SimpleNamespace(
                    adapter_name="tool_loop",
                    resolved_model="fixed-test-model",
                    configuration_record={"source": "deterministic-test"},
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

        return Adapter()


def test_l02_protocol_and_matched_surfaces(tmp_path: Path) -> None:
    spec = load_l02_drainage_protocol(agent=_AGENT, compute=_COMPUTE)
    plan = compile_l02_drainage_study(study_run_id="l02-protocol", agent=_AGENT, compute=_COMPUTE)
    assert spec.study_id == L02_DRAINAGE_STUDY_ID
    assert [item.task_id for item in spec.experiences] == [L02_ACQUISITION_TASK_ID, L02_PROBE_TASK_ID]
    assert [(item.arm_id, item.role.value, item.treatment_id) for item in spec.arms] == [
        ("cold-reset", "control", "reset"),
        ("reset-after-acquisition", "control", "reset"),
        ("raw-history", "exposure", "raw-history"),
        ("structured-memory", "exposure", "structured-memory"),
    ]
    assert L02_EXECUTION_CONDITION.adapter_id == "lifecycle-local:fresh_context:artifact_memory"
    assert any(getattr(item, "operation_id", None) == L02_CONSOLIDATION_OPERATION_ID for item in spec.arms[-1].steps)
    assert all(step.trial.extensions == {} for arm in plan.arm_runs for step in arm.steps if hasattr(step, "trial"))

    packages = {
        variant: compile_lifecycle(
            "drainage-model-evidence-lifecycle-review", tmp_path / variant, variant_id=variant
        ).package_dir
        for variant in ("staged_full_correction", "memo_closeout_missing")
    }
    for filename in ("initial_review.md", "response_review.md", "closeout_review.md"):
        assert (packages["staged_full_correction"] / "instructions" / filename).read_bytes() == (
            packages["memo_closeout_missing"] / "instructions" / filename
        ).read_bytes()
    for filename in (
        "document-register-rev-f.md",
        "response-cover.md",
        "model-input-manifest-rev-b.md",
        "run-register-rev-f.md",
        "hydraulic-report-043.md",
    ):
        assert (packages["staged_full_correction"] / "releases" / "response_review" / filename).read_bytes() == (
            packages["memo_closeout_missing"] / "releases" / "response_review" / filename
        ).read_bytes()
    assert not (
        packages["memo_closeout_missing"] / "releases" / "closeout_review" / "drainage-design-memo-rev-e.md"
    ).exists()


def test_deterministic_l02_runs_all_arms_and_preserves_fidelity(tmp_path: Path) -> None:
    adapter = _GoldAdapterBuilder()
    consolidator = _Consolidator()
    result = run_l02_drainage_study_sync(
        run_root=tmp_path / "l02",
        study_run_id="l02-deterministic",
        agent=_AGENT,
        compute=_COMPUTE,
        consolidation_operation=consolidator,
        adapter_builder=adapter,
    )
    assert [arm.status.value for arm in result.execution.arm_runs] == ["completed"] * 4
    assert type(adapter).executions == 21
    assert _Consolidator.calls == 1
    assert len({item.initial_state_equivalence_id for item in result.arm_evidence.values()}) == 1
    assert all(item.adapter_id == L02_EXECUTION_CONDITION.adapter_id for item in result.arm_evidence.values())
    assert all(item.arm_isolated and item.lineage_complete for item in result.arm_evidence.values())
    assert all(item.probe_feedback_hidden and item.probe_state_discarded for item in result.arm_evidence.values())
    assert all(not item.hidden_evaluation_leaked for item in result.arm_evidence.values())

    measurements = {item.measurement_id: item for item in result.reviewed_assessment.measurements}
    assert (
        measurements["structured-memory-versus-raw-history-inappropriate-closure"].validity
        is LearningComparisonValidity.DESCRIPTIVE_ONLY
    )
    for measurement in measurements.values():
        assert measurement.validity is not LearningComparisonValidity.INVALID
    projections = l02_drainage_outcome_projections()
    probe_records = [
        record
        for arm in result.execution.arm_runs
        for record in arm.trial_records
        if record.task_id == L02_PROBE_TASK_ID
    ]
    assert len(probe_records) == 4
    for record in probe_records:
        assert projections["drainage.inappropriate-memo-closure"](record).value == 0.0

    raw_arm = next(arm for arm in result.plan.arm_runs if arm.arm_id == "raw-history")
    structured_arm = next(arm for arm in result.plan.arm_runs if arm.arm_id == "structured-memory")
    raw_final = tmp_path / "l02" / "learner-arms" / raw_arm.arm_run_id / "states" / "raw-acquisition"
    structured_final = (
        tmp_path / "l02" / "learner-arms" / structured_arm.arm_run_id / "states" / "structured-consolidation"
    )
    assert (
        (raw_final / "history").is_dir()
        and (raw_final / "feedback").is_dir()
        and (raw_final / "memory").is_dir()
        and not any((raw_final / "memory").iterdir())
    )
    assert (
        (structured_final / "memory").is_dir()
        and (structured_final / "feedback").is_dir()
        and not (structured_final / "history").exists()
    )
    raw_result = next(arm for arm in result.execution.arm_runs if arm.arm_run_id == raw_arm.arm_run_id)
    acquisition = next(record for record in raw_result.trial_records if record.task_id == L02_ACQUISITION_TASK_ID)
    feedback_record = next(
        json.loads(path.read_text())
        for path in (tmp_path / "l02" / "feedback").glob("*.json")
        if json.loads(path.read_text())["arm_run_id"] == raw_arm.arm_run_id
    )
    assert feedback_record["source_experience_id"] == "staged-full-correction-acquisition"
    assert feedback_record["source_trial_id"] == acquisition.trial_id
    assert feedback_record["state_after_id"] != feedback_record["state_before_id"]
    acquisition_package = (
        tmp_path / "l02" / "learner-arms" / raw_arm.arm_run_id / "lifecycle-experiences" / "raw-acquisition" / "package"
    )
    assert (
        json.loads((acquisition_package / "hidden" / "variant.json").read_text())["variant_id"]
        == "staged_full_correction"
    )


def test_inappropriate_projection_separates_identified_closure_from_generic_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closeout = {
        "findings": [{"finding_id": "F-PRV06-001", "status": "closed", "closure_evidence": ["unsupported"]}],
        "closure_evidence_requests": [{"request_id": "CER-002", "status": "closed", "response_refs": ["unsupported"]}],
    }
    gate = {
        "passed": False,
        "score": 0.5,
        "failures": sorted(drainage_learning.DRAINAGE_MEMO_CLOSURE_FAILURE_TOKENS),
    }
    record = make_trial_record(
        task_id=L02_PROBE_TASK_ID,
        evaluation_status=EvaluationStatus.COMPLETED,
        evaluation=EvaluationResult(
            reward=0.0,
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={"lifecycle_gates": {"closure_evidence": gate}},
        ),
    )
    monkeypatch.setattr(drainage_learning, "_archived_submissions", lambda _record: {"closeout_review": closeout})
    assert drainage_learning.drainage_inappropriate_memo_closure(record) == 1.0
    gate["failures"] = ["closeout_review:F-PRV03-001:closure_evidence"]
    assert drainage_learning.drainage_inappropriate_memo_closure(record) == 0.0


def test_real_memo_closeout_copycat_triggers_declared_projection_tokens(tmp_path: Path) -> None:
    template = "drainage-model-evidence-lifecycle-review"
    memo_package = materialize_lifecycle(template, tmp_path / "memo" / "package", variant_id="memo_closeout_missing")
    staged_package = materialize_lifecycle(
        template, tmp_path / "staged" / "package", variant_id="staged_full_correction"
    )
    memo_gold = json.loads((memo_package / "hidden" / "gold-submissions.json").read_text())
    staged_gold = json.loads((staged_package / "hidden" / "gold-submissions.json").read_text())

    def resolve(context: dict) -> dict:
        output = Path(context["submission_path"])
        output.parent.mkdir(parents=True, exist_ok=True)
        source = staged_gold if context["checkpoint_id"] == "closeout_review" else memo_gold
        output.write_text(json.dumps(source[context["checkpoint_id"]]), encoding="utf-8")
        return {"status": "completed"}

    run_dir = tmp_path / "memo" / "run"
    run_lifecycle(memo_package, run_dir, episode_environment=deterministic_episode_environment(resolve))
    verification = verify_drainage_model_lifecycle(memo_package, run_dir)
    closure_gate = verification["gates"]["closure_evidence"]
    assert not closure_gate["passed"]
    assert set(drainage_learning.DRAINAGE_MEMO_CLOSURE_FAILURE_TOKENS).issubset(set(closure_gate["failures"]))

    record = make_trial_record(
        task_id=L02_PROBE_TASK_ID,
        output={
            "agent_output": {
                "status": "completed",
                "output_path": str(run_dir.resolve()),
                "output_format": "evidence_lifecycle",
            },
            "raw_output_path": str(run_dir.resolve()),
            "conversation_path": str(run_dir.resolve()),
            "agent_result": {"completion_status": "completed"},
        },
        evaluation=EvaluationResult(
            reward=verification["reward"],
            validity=ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True),
            breakdown={"lifecycle_gates": verification["gates"]},
        ),
    )
    assert drainage_learning.drainage_inappropriate_memo_closure(record) == 1.0
