# ABOUTME: Tests the functional evolution application lifecycle.
# ABOUTME: Proves paired evidence, effect ordering, exact rejection material, and deterministic run identity.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import yaml

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    MutationSummary,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, TaskSelector
from aec_bench.evolution.application import run_evolution
from aec_bench.evolution.core import VariationResult, VariationStatus
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.evolution.strategy import HillClimbStrategy
from aec_bench.evolution.workspace import Workspace
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def _setup(tmp_path: Path) -> tuple[Workspace, CandidateEvaluationBatch]:
    root = tmp_path / "workspace"
    (root / "prompts").mkdir(parents=True)
    (root / "prompts" / "system.md").write_text("canonical", encoding="utf-8")
    (root / "manifest.yaml").write_text(
        yaml.safe_dump({"name": "functional-test", "agent_adapter": "direct", "evolvable_layers": ["prompts"]}),
        encoding="utf-8",
    )
    workspace = Workspace(root)
    workspace.init_versioning()
    task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop" / "case"
    task_dir.mkdir(parents=True)
    resolved = resolve_instance_paths(make_task_definition(task_id="electrical/voltage-drop/case"), task_dir)
    trial = PlannedTrial(
        trial_id="planned-trial",
        experiment_id="functional-test",
        task_id=resolved.task.task_id,
        agent=AgentConfig(name="agent", adapter="direct", model="test"),
        compute=ComputeConfig(backend="local"),
        repetition=1,
    )
    return workspace, CandidateEvaluationBatch(
        tasks=(resolved,),
        trials=(trial,),
        evaluation_case_ids=("electrical/voltage-drop/case::attempt=1",),
    )


def _config(root: Path, *, threshold: float = 0.02, stagnation: int = 5) -> EvolutionConfig:
    return EvolutionConfig(
        workspace_path=str(root),
        models={"classifier": "test", "evolver": "test"},
        task_selector=TaskSelector(),
        batch_size=1,
        max_cycles=1,
        improvement_threshold=threshold,
        stagnation_window=stagnation,
    )


def _record(candidate_id: str, reward: float):
    return make_trial_record(
        trial_id=f"{candidate_id}-trial",
        task_id="electrical/voltage-drop/case",
        attempt=1,
        evaluation={
            "reward": reward,
            "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
        },
    )


def _run(
    workspace: Workspace,
    batch: CandidateEvaluationBatch,
    *,
    parent_reward: float,
    child_reward: float,
    variation: object,
    config: EvolutionConfig,
    evaluated_candidates: list[str] | None = None,
):
    def evaluate(snapshot: WorkspaceSnapshot, _batch: CandidateEvaluationBatch):
        if evaluated_candidates is not None:
            evaluated_candidates.append(snapshot.candidate_id)
        reward = child_reward if snapshot.candidate_id != "baseline" else parent_reward
        return (_record(snapshot.candidate_id, reward),)

    return run_evolution(
        workspace=workspace,
        config=config,
        evaluate=evaluate,
        strategy=HillClimbStrategy(),
        batch_planner=lambda _size, _cycle: batch,
        variation=variation,
        enrich=lambda observations: observations,
        run_id="run-fixed",
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_child_is_evaluated_before_commit_and_both_evidence_sets_persist(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    candidates_seen_during_eval: list[str] = []

    def submit(request, _source, child_id):
        return VariationResult(
            status=VariationStatus.SUBMITTED,
            child=request.parent.snapshot.model_copy(update={"candidate_id": child_id, "system_prompt": "child"}),
            mutation=MutationSummary(prompt_modified=True),
            reasoning="test child",
            model_cost_usd=0.0,
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.9,
        variation=submit,
        config=_config(workspace.root),
        evaluated_candidates=candidates_seen_during_eval,
    )
    assert candidates_seen_during_eval == ["baseline", "run-fixed:1"]
    assert [item.candidate_id for item in workspace.list_candidates()] == ["baseline", "run-fixed:1"]
    assert result.cycle_records[0].child_assessment is not None
    trial_path = workspace.root / "_trials" / "run-fixed" / "cycle_001.jsonl"
    rows = [json.loads(line) for line in trial_path.read_text(encoding="utf-8").splitlines()]
    assert {row["candidate_id"] for row in rows} == {"baseline", "run-fixed:1"}


def test_rejected_child_keeps_canonical_workspace_and_exact_graveyard_snapshot(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)

    def submit(request, _source, child_id):
        return VariationResult(
            status=VariationStatus.SUBMITTED,
            child=request.parent.snapshot.model_copy(update={"candidate_id": child_id, "system_prompt": "rejected"}),
            mutation=MutationSummary(prompt_modified=True),
            reasoning="rejected test child",
            model_cost_usd=0.0,
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.6,
        variation=submit,
        config=_config(workspace.root, threshold=0.9, stagnation=1),
    )
    assert result.cycle_records[0].gate_decision.value == "rejected"
    assert result.final_score == result.cycle_records[0].parent_assessment.batch_score
    assert result.cycle_records[0].child_assessment is not None
    assert result.cycle_records[0].child_assessment.batch_score == 0.6
    assert workspace.read_prompt() == "canonical"
    entry = json.loads((workspace.root / "graveyard.json").read_text(encoding="utf-8"))[0]
    assert entry["parent_candidate_id"] == "baseline"
    assert entry["rejected_snapshot"]["candidate_id"] == "run-fixed:1"
    assert entry["rejected_snapshot"]["system_prompt"] == "rejected"
    assert [item.candidate_id for item in workspace.list_candidates()] == ["baseline"]


def test_abstention_creates_no_child_version(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)

    def abstain(_request, _source, _child_id):
        return VariationResult(
            status=VariationStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="no change",
            model_cost_usd=0.0,
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.5,
        variation=abstain,
        config=_config(workspace.root),
    )
    assert result.cycle_records[0].gate_decision.value == "skipped"
    assert [item.candidate_id for item in workspace.list_candidates()] == ["baseline"]
    assert json.loads((workspace.root / "graveyard.json").read_text(encoding="utf-8")) == []
