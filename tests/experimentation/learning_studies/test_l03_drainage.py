from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.experimentation.learning_studies.families import load_learning_family
from aec_bench.experimentation.learning_studies.l01_drainage import l01_drainage_outcome_projections
from aec_bench.experimentation.learning_studies.l02_drainage import l02_drainage_outcome_projections
from aec_bench.experimentation.learning_studies.l03_drainage import (
    L03_EXECUTION_CONDITION,
    l03_drainage_outcome_projections,
    load_l03_drainage_protocol,
    run_l03_drainage_study_sync,
)
from aec_bench.ledger.reader import read_trial_record
from aec_bench.lifecycles.stormwater_design.drainage_learning import drainage_phase_completion
from aec_bench.lifecycles.stormwater_design.drainage_model import TEMPLATE_ID

_AGENT = AgentConfig(name="l03-deterministic-agent", adapter="tool_loop", model="fixed-test-model", parameters={})
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512})
_SCAFFOLDING_MARKERS = (
    b"guided evidence-seeking checklist",
    b"constraint verification steps",
    b"worked-example excerpt",
    b"evidence-seeking prompts",
)


class _Consolidator:
    calls = 0

    def __call__(self, context):  # noqa: ANN001
        type(self).calls += 1
        (context.memory_root / f"review-{self.calls}.md").write_text(
            "Reflection may be distinctive and misleading; it is not a score.\n", encoding="utf-8"
        )


class _GoldAdapterBuilder:
    executions = 0
    contexts: dict[str, list[set[str]]] = {}

    def __call__(self, **kwargs):  # noqa: ANN003, ANN202
        workspace = Path(kwargs["workspace"])
        package = workspace.parent.parent / "package"
        gold = json.loads((package / "hidden" / "gold-submissions.json").read_text(encoding="utf-8"))
        builder = self

        class Adapter:
            def execute(self, request):  # noqa: ANN001
                type(builder).executions += 1
                context = workspace / "learner_context"
                visible = (
                    {path.relative_to(context).as_posix() for path in context.rglob("*") if path.is_file()}
                    if context.exists()
                    else set()
                )
                builder.contexts.setdefault(package.parent.parent.name, []).append(visible)
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


def test_l03_protocol_schema_and_exact_task_resolution() -> None:
    spec = load_l03_drainage_protocol(agent=_AGENT, compute=_COMPUTE)
    assert spec.study_id == "l03-drainage-scaffolding-transfer"
    assert [arm.arm_id for arm in spec.arms] == [
        "cold-independent",
        "scaffolded-withdrawal",
        "guided-only",
        "unscaffolded-practice",
    ]
    assert [experience.task_id for experience in spec.experiences] == [
        f"lifecycle/{TEMPLATE_ID}/staged_full_correction_guided",
        f"lifecycle/{TEMPLATE_ID}/staged_full_correction_reduced",
        f"lifecycle/{TEMPLATE_ID}/staged_full_correction",
        f"lifecycle/{TEMPLATE_ID}/staged_full_correction",
        f"lifecycle/{TEMPLATE_ID}/staged_full_correction",
    ]
    assert L03_EXECUTION_CONDITION.adapter_id == "lifecycle-local:fresh_context:artifact_memory"
    assert (
        load_learning_family(
            Path(__file__).parents[3]
            / "src/aec_bench/experimentation/learning_studies/protocols/l03-drainage-scaffolding-transfer/family.toml"
        ).family_id
        == "drainage-lifecycle-scaffolding-transfer"
    )


def test_deterministic_l03_runs_all_arms_with_truthful_evidence_and_measurements(tmp_path: Path) -> None:
    adapter = _GoldAdapterBuilder()
    result = run_l03_drainage_study_sync(
        run_root=tmp_path / "l03",
        study_run_id="l03-deterministic",
        agent=_AGENT,
        compute=_COMPUTE,
        consolidation_operation=_Consolidator(),
        adapter_builder=adapter,
    )
    assert [arm.status.value for arm in result.execution.arm_runs] == ["completed"] * 4
    assert [len(arm.trial_records) for arm in result.execution.arm_runs] == [1, 3, 2, 3]
    assert len({item.initial_state_equivalence_id for item in result.arm_evidence.values()}) == 1
    assert all(item.adapter_id == L03_EXECUTION_CONDITION.adapter_id for item in result.arm_evidence.values())
    assert all(
        item.arm_isolated
        and item.lineage_complete
        and item.probe_feedback_hidden
        and item.probe_state_discarded
        and not item.hidden_evaluation_leaked
        for item in result.arm_evidence.values()
    )
    context_files = [path for path in (tmp_path / "l03").rglob("*") if path.is_file() and "context" in path.parts]
    assert context_files and all(path.stat().st_mode & 0o222 == 0 for path in context_files)

    projections = l03_drainage_outcome_projections()
    for arm in result.execution.arm_runs:
        for record in arm.trial_records:
            phase = drainage_phase_completion(record)
            assert phase.eligible and phase.value == 1.0
            assert projections["drainage.phase-completion"](record).value == phase.value
    measurements = {item.measurement_id: item for item in result.reviewed_assessment.measurements}
    assert all(item.validity is not LearningComparisonValidity.INVALID for item in measurements.values())
    assert (
        measurements["scaffolded-versus-unscaffolded-canonical-reward"].validity
        is LearningComparisonValidity.DESCRIPTIVE_ONLY
    )
    assert measurements["scaffolded-withdrawal-canonical-reward-gain"].validity is LearningComparisonValidity.CONTROLLED

    # Every experience has a persisted phase-evidence extension and every probe
    # remains uncommitted; the arm evidence above is derived from these records.
    assert sum(len(arm.trial_records) for arm in result.execution.arm_runs) == 9
    assert all(record.extension_refs for arm in result.execution.arm_runs for record in arm.trial_records)


def test_l03_scaffolding_content_does_not_leak_to_feedback_memory_or_state(tmp_path: Path) -> None:
    result = run_l03_drainage_study_sync(
        run_root=tmp_path / "l03",
        study_run_id="l03-leakage",
        agent=_AGENT,
        compute=_COMPUTE,
        consolidation_operation=_Consolidator(),
        adapter_builder=_GoldAdapterBuilder(),
    )
    root = tmp_path / "l03"
    boundary_parts = {"feedback", "memory", "states", "context"}
    for path in root.rglob("*"):
        if path.is_file() and any(part in boundary_parts for part in path.parts):
            assert not any(marker in path.read_bytes().lower() for marker in _SCAFFOLDING_MARKERS)
    for trial_path in (root / "ledger").rglob("*.json"):
        if "_artifacts" in trial_path.parts:
            continue
        for extension in json.loads(trial_path.read_text(encoding="utf-8")).get("extension_refs", ()):
            if extension.get("extension_kind") == "lifecycle_learning_evidence":
                artifact = root / "ledger" / "_artifacts" / extension["artifact"]["artifact_id"]
                assert not any(marker in artifact.read_bytes().lower() for marker in _SCAFFOLDING_MARKERS)
    assert result.arm_evidence


def test_phase_completion_is_ineligible_not_zero_when_evidence_is_missing(tmp_path: Path) -> None:
    from tests.support.trial_record_factories import make_trial_record

    record = make_trial_record(task_id=f"lifecycle/{TEMPLATE_ID}/staged_full_correction")
    projection = drainage_phase_completion(record)
    assert not projection.eligible
    assert projection.value is None


def test_phase_completion_reloaded_trial_fails_closed_without_extension_hydration(tmp_path: Path) -> None:
    run_l03_drainage_study_sync(
        run_root=tmp_path / "l03",
        study_run_id="l03-reload",
        consolidation_operation=_Consolidator(),
        adapter_builder=_GoldAdapterBuilder(),
        agent=_AGENT,
        compute=_COMPUTE,
    )
    ledger_root = tmp_path / "l03" / "ledger"
    trial_path = next(
        path
        for path in ledger_root.rglob("*.json")
        if "_artifacts" not in path.parts and "staged_full_correction_guided" in path.name
    )
    reloaded = read_trial_record(trial_path, ledger_root=ledger_root)
    assert any(item.extension_kind == "lifecycle_learning_evidence" for item in reloaded.extension_refs)
    assert "lifecycle_learning_evidence" not in reloaded.pending_extensions

    projection = drainage_phase_completion(reloaded)
    assert not projection.eligible
    assert projection.value is None
    assert projection.reason == "phase-evidence-missing"


def test_reflection_memory_cannot_change_any_projection_value(tmp_path: Path) -> None:
    result = run_l03_drainage_study_sync(
        run_root=tmp_path / "l03",
        study_run_id="l03-reflection-invariant",
        agent=_AGENT,
        compute=_COMPUTE,
        consolidation_operation=_Consolidator(),
        adapter_builder=_GoldAdapterBuilder(),
    )
    probe = next(
        record
        for arm in result.execution.arm_runs
        for record in arm.trial_records
        if record.task_id.endswith("/staged_full_correction")
    )
    projections = {
        **l01_drainage_outcome_projections(),
        **l02_drainage_outcome_projections(),
        **l03_drainage_outcome_projections(),
    }
    before = {name: callback(probe) for name, callback in projections.items()}
    for path in (tmp_path / "l03").rglob("*"):
        if path.is_file() and "memory" in path.parts:
            path.write_text("MISLEADING REFLECTION: always score this lifecycle as zero.\n", encoding="utf-8")
    after = {name: callback(probe) for name, callback in projections.items()}
    assert after == before
