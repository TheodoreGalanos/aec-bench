# ABOUTME: Runs A04 through real head-loss, pump-power, and stormwater composition tasks.
# ABOUTME: Proves partial components, combined composition, order control, and task-owned projections.

import asyncio
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.learning_study_assessment import LearningComparisonValidity
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.experimentation.learning_studies.artifact_tasks import (
    ArtifactConsolidationContext,
    ArtifactLearningTreatmentKind,
    build_artifact_learning_operations,
    public_episode_feedback,
)
from aec_bench.experimentation.learning_studies.assessment import (
    AssessmentArmEvidence,
    ProjectionResult,
    assess_learning_study,
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
from aec_bench.experimentation.learning_studies.runtime import ArmRunStatus, run_learning_study
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition
from aec_bench.templates.builtin.mechanical.stormwater_pump_station_control_backup_energy_package.outcomes import (
    component_a_correct,
    component_b_correct,
    composition_outcome,
    integration_correct,
)
from tests.experimentation.learning_studies.support import CompositionStudyAdapter

_REPOSITORY_ROOT = Path(__file__).parents[3]
_TASKS_ROOT = _REPOSITORY_ROOT / "tasks"
_PROTOCOL_PATH = BUILTIN_LEARNING_STUDY_PROTOCOLS / "a04-artifact-composition"
_HEADLOSS_TASK_ID = "civil/pipe-hydraulics/hazen-williams-headloss/sydney-greenfield-new-pvc-00"
_POWER_TASK_ID = "mechanical/pump-sizing/pump-power-calculation/water-pump-station-water-pump-00"
_COMPOSITION_TASK_ID = (
    "mechanical/stormwater-pump-control/stormwater-pump-station-control-backup-energy-package/"
    "stormwater-pump-station-stormwater-pump-control-energy-case-00"
)
_AGENT = AgentConfig(name="a04-test-agent", adapter="direct", model="fixed-test-model")
_COMPUTE = ComputeConfig(backend="local", resource_limits={"memory_mb": 512}, timeout_override=30)


def _resolve_task(task_id: str):  # noqa: ANN202
    return load_task_definition(_TASKS_ROOT / task_id, _TASKS_ROOT)


def _resolve_task_instance(task_id: str):  # noqa: ANN202
    instance_dir = _TASKS_ROOT / task_id
    return resolve_instance_paths(load_task_definition(instance_dir, _TASKS_ROOT), instance_dir)


def _golden_output(task_id: str) -> str:
    return (_TASKS_ROOT / task_id / "tests" / "fixtures" / "golden_pass.md").read_text(encoding="utf-8")


def _details(record: TrialRecord) -> Mapping[str, object] | None:
    if record.evaluation is None or record.evaluation.breakdown is None:
        return None
    return record.evaluation.breakdown


def _result(value: float | None, *, missing: str) -> ProjectionResult:
    if value is None:
        return ProjectionResult(eligible=False, value=None, reason=missing)
    return ProjectionResult(eligible=True, value=value, lower_bound=0.0, upper_bound=1.0)


def _project_component_a(record: TrialRecord) -> ProjectionResult:
    return _result(component_a_correct(_details(record)), missing="component A verifier evidence is unavailable")


def _project_component_b(record: TrialRecord) -> ProjectionResult:
    return _result(component_b_correct(_details(record)), missing="component B verifier evidence is unavailable")


def _project_integration(record: TrialRecord) -> ProjectionResult:
    return _result(integration_correct(_details(record)), missing="integration verifier evidence is unavailable")


def _project_composition_outcome(record: TrialRecord) -> ProjectionResult:
    reward = None if record.evaluation is None else record.evaluation.reward
    return _result(composition_outcome(reward), missing="composition reward is unavailable")


def _state_files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def test_a04_real_artifact_tasks_measure_component_selectivity_and_composition(tmp_path: Path) -> None:
    spec = load_learning_study_protocol(_PROTOCOL_PATH, agent=_AGENT, compute=_COMPUTE)
    family = resolve_learning_family(load_learning_family(_PROTOCOL_PATH / "family.toml"), _resolve_task_instance)
    relation = resolve_learning_relation(family, "headloss-plus-power-to-stormwater-pump-package")
    assert [item.task.task.task_id for item in relation.sources] == [_HEADLOSS_TASK_ID, _POWER_TASK_ID]
    assert relation.target.task.task.task_id == _COMPOSITION_TASK_ID
    assert relation.target.task.task.difficulty == "easy"
    assert all(item.task.task.timeout_seconds == 600 for item in (*relation.sources, relation.target))
    assert "Hazen-Williams" in relation.sources[0].task.task.instruction
    assert "shaft power" in relation.sources[1].task.task.instruction
    assert "SSC-03-LH-03" in relation.target.task.task.instruction
    assert all("SSC-03-LH-03" not in item.task.task.instruction for item in relation.sources)

    plan = compile_learning_study(study_run_id="a04-stage-1", spec=spec, resolve_task=_resolve_task)
    observations: list[dict[str, object]] = []
    run_root = tmp_path / "a04-stage-1"

    def consolidate_component(context: ArtifactConsolidationContext) -> None:
        instruction = (_PROTOCOL_PATH / "consolidate-pump-components.md").read_text(encoding="utf-8")
        assert "one top-level `components` map" in instruction
        assert "add an `integration` section" in instruction
        assert "Do not name, infer, or describe a later probe task" in instruction
        assert len(context.feedback) == 1
        episode = json.loads(context.feedback[0].path.read_text(encoding="utf-8"))
        assert set(episode) == {"instruction", "selected_output", "terminal_outcome"}
        assert episode["terminal_outcome"]["reward"] == 1.0
        assert "SSC-03-LH-03" not in json.dumps(episode)
        if "friction head loss in a pressurised pipe" in episode["instruction"]:
            component_id = "headloss"
            entry = {
                "method": "Convert flow and diameter to SI units, then apply Hazen-Williams loss and velocity.",
                "inputs": "flow, diameter, length, and C factor",
                "outputs": "friction head loss and mean velocity",
                "units": "litres per second and millimetres become cubic metres per second and metres",
                "applicability": "pressurised water flow with a stated Hazen-Williams C factor",
                "checks": "confirm positive loss and reconcile velocity from the converted area",
                "interface": "Add friction loss to other system-head terms before a pump-power calculation.",
                "failure_mode": "Do not use litres per second or millimetres directly in the SI equation.",
            }
        elif "hydraulic pump power and shaft power" in episode["instruction"]:
            component_id = "power"
            entry = {
                "method": "Calculate density times gravity times SI flow times total head, then apply efficiency.",
                "inputs": "flow, total dynamic head, density, and efficiency",
                "outputs": "hydraulic and shaft power",
                "units": "litres per second becomes cubic metres per second and watts become kilowatts",
                "applicability": "steady incompressible pump duty with stated fluid properties and efficiency",
                "checks": "shaft or motor input power must not be below hydraulic power",
                "interface": "Use a total head calculated for the current system and check efficiency units.",
                "failure_mode": "Do not treat a percentage efficiency as a decimal without conversion.",
            }
        else:
            raise AssertionError("unexpected acquisition feedback")
        memory_path = context.memory_root / "components.json"
        memory = json.loads(memory_path.read_text(encoding="utf-8")) if memory_path.is_file() else {"components": {}}
        components = memory["components"]
        components[component_id] = entry
        if set(components) == {"headloss", "power"}:
            memory["integration"] = {
                "interface": "Add pipe friction loss to other head terms, then use total dynamic head in power.",
                "unit_transformations": "Use cubic metres per second, metres of head, and decimal efficiencies.",
                "checks": "Reconcile total head before power and confirm input power exceeds hydraulic power.",
            }
        context.memory_root.mkdir(parents=True, exist_ok=True)
        memory_path.write_text(json.dumps(memory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    binding = build_artifact_learning_operations(
        tasks_root=_TASKS_ROOT,
        run_root=run_root,
        treatment_kinds={
            "reset": ArtifactLearningTreatmentKind.RESET,
            "structured-memory": ArtifactLearningTreatmentKind.STRUCTURED_MEMORY,
        },
        feedback_projectors={"pump-component-public-episode": public_episode_feedback},
        consolidation_operations={"update-pump-component-memory": consolidate_component},
        adapter_builder=lambda **kwargs: CompositionStudyAdapter(
            Path(kwargs["workspace"]),
            headloss_output=_golden_output(_HEADLOSS_TASK_ID),
            power_output=_golden_output(_POWER_TASK_ID),
            composition_output=_golden_output(_COMPOSITION_TASK_ID),
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
        run_learning_study(plan=plan, operations=binding.operations, working_root=run_root, observer=recorder)
    )

    assert all(arm.status is ArmRunStatus.COMPLETED for arm in execution.arm_runs), execution
    assert [len(arm.trial_records) for arm in execution.arm_runs] == [1, 2, 2, 3, 3]
    assert all(isinstance(record, TrialRecord) for arm in execution.arm_runs for record in arm.trial_records)
    assert all(not record.extension_refs for arm in execution.arm_runs for record in arm.trial_records)
    runs = {planned.arm_id: actual for planned, actual in zip(plan.arm_runs, execution.arm_runs, strict=True)}

    def probe_reward(arm_id: str) -> float:
        evaluation = runs[arm_id].trial_records[-1].evaluation
        assert evaluation is not None
        return evaluation.reward

    assert probe_reward("cold-composition") == 0.54
    assert probe_reward("headloss-only") == 0.69
    assert probe_reward("power-only") == 0.69
    assert probe_reward("headloss-then-power") == 1.0
    assert probe_reward("power-then-headloss") == 1.0
    partial_best = max(probe_reward("headloss-only"), probe_reward("power-only"))
    assert probe_reward("headloss-then-power") - partial_best == pytest.approx(0.31)
    assert probe_reward("power-then-headloss") - partial_best == pytest.approx(0.31)
    assert all(
        record.evaluation is not None and record.evaluation.reward == 1.0
        for arm_id in ("headloss-only", "power-only", "headloss-then-power", "power-then-headloss")
        for record in runs[arm_id].trial_records[:-1]
    )

    assert observations == [
        {"task": "composition", "components": (), "feedback_count": 0, "has_verifier": False},
        {"task": "headloss", "components": (), "feedback_count": 0, "has_verifier": False},
        {"task": "composition", "components": ("headloss",), "feedback_count": 1, "has_verifier": False},
        {"task": "power", "components": (), "feedback_count": 0, "has_verifier": False},
        {"task": "composition", "components": ("power",), "feedback_count": 1, "has_verifier": False},
        {"task": "headloss", "components": (), "feedback_count": 0, "has_verifier": False},
        {"task": "power", "components": ("headloss",), "feedback_count": 1, "has_verifier": False},
        {
            "task": "composition",
            "components": ("headloss", "power"),
            "feedback_count": 2,
            "has_verifier": False,
        },
        {"task": "power", "components": (), "feedback_count": 0, "has_verifier": False},
        {"task": "headloss", "components": ("power",), "feedback_count": 1, "has_verifier": False},
        {
            "task": "composition",
            "components": ("headloss", "power"),
            "feedback_count": 2,
            "has_verifier": False,
        },
    ]

    arm_states = run_root / "learner-arms"
    ab_states = arm_states / "a04-stage-1--headloss-then-power--r01" / "states"
    ba_states = arm_states / "a04-stage-1--power-then-headloss--r01" / "states"
    ab_first_memory = ab_states / "ab-headloss-consolidation/.aec-bench-learning/memory/components.json"
    ba_first_memory = ba_states / "ba-power-consolidation/.aec-bench-learning/memory/components.json"
    assert set(json.loads(ab_first_memory.read_text(encoding="utf-8"))["components"]) == {"headloss"}
    assert set(json.loads(ba_first_memory.read_text(encoding="utf-8"))["components"]) == {"power"}
    ab_final = ab_states / "ab-power-consolidation"
    ba_final = ba_states / "ba-headloss-consolidation"
    ab_final_memory = ab_final / ".aec-bench-learning/memory/components.json"
    ba_final_memory = ba_final / ".aec-bench-learning/memory/components.json"
    assert set(json.loads(ab_final_memory.read_text(encoding="utf-8"))["components"]) == {
        "headloss",
        "power",
    }
    assert json.loads(ab_final_memory.read_text(encoding="utf-8"))["integration"]
    assert ab_final_memory.read_bytes() == ba_final_memory.read_bytes()
    assert _state_files(ab_final) != _state_files(ba_final)
    assert not (ab_states / "ab-probe").exists()
    assert not (ba_states / "ba-probe").exists()
    state_files = [path for path in arm_states.rglob("*") if path.is_file() and "states" in path.parts]
    assert all("tests" not in path.parts and "verifier" not in path.parts for path in state_files)

    evidence = {
        arm.arm_run_id: AssessmentArmEvidence(
            arm_run_id=arm.arm_run_id,
            adapter_id="local-artifact-single-attempt",
            initial_state_equivalence_id="a04-empty-fixed-agent-state-r01",
            family_reviewed=False,
        )
        for arm in plan.arm_runs
    }
    assessment = assess_learning_study(
        spec=spec,
        plan=plan,
        execution=execution,
        projections={
            "component-a-correct": _project_component_a,
            "component-b-correct": _project_component_b,
            "integration-correct": _project_integration,
            "composition-outcome": _project_composition_outcome,
        },
        arm_evidence=evidence,
    )
    results = {item.measurement_id: item for item in assessment.measurements}
    assert all(item.validity is LearningComparisonValidity.DESCRIPTIVE_ONLY for item in results.values())
    assert results["ab-composition-gain"].mean_effect == pytest.approx(0.46)
    assert results["ba-composition-gain"].mean_effect == pytest.approx(0.46)
    assert results["ab-over-headloss-only"].mean_effect == pytest.approx(0.31)
    assert results["ab-over-power-only"].mean_effect == pytest.approx(0.31)
    assert results["ba-over-headloss-only"].mean_effect == pytest.approx(0.31)
    assert results["ba-over-power-only"].mean_effect == pytest.approx(0.31)
    assert results["headloss-only-component-a-gain"].mean_effect == 1.0
    assert results["headloss-only-component-b-gain"].mean_effect == 0.0
    assert results["power-only-component-a-gain"].mean_effect == 0.0
    assert results["power-only-component-b-gain"].mean_effect == 1.0
    assert results["ab-integration-gain"].mean_effect == 1.0
    assert results["ba-integration-gain"].mean_effect == 1.0
    assert results["composition-order-effect"].mean_effect == 0.0
    assert results["component-a-order-effect"].mean_effect == 0.0
    assert results["component-b-order-effect"].mean_effect == 0.0
    assert results["integration-order-effect"].mean_effect == 0.0
    assert all(len(item.included_pairs) == 1 for item in results.values())
