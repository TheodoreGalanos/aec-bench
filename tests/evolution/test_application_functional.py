# ABOUTME: Tests the functional evolution application lifecycle.
# ABOUTME: Proves paired evidence, effect ordering, exact rejection material, and deterministic run identity.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import yaml

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolverModelConfig,
    MutationSummary,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, TaskSelector
from aec_bench.contracts.identity import EntityKind, new_entity_id
from aec_bench.evolution import application
from aec_bench.evolution import proposer as proposer_module
from aec_bench.evolution.application import run_evolution, run_evolution_from_config
from aec_bench.evolution.checkpoint import AVOConfigurationIdentity
from aec_bench.evolution.core import (
    CandidateProposal,
    EvaluatedCandidate,
    ProposalStatus,
    ProposalUsage,
    RevisionAttempt,
    SelectionPlan,
)
from aec_bench.evolution.evaluation import CandidateChecks, CandidateEvaluationBatch
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.proposer import build_avo
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
        yaml.safe_dump(
            {
                "schema_version": 1,
                "name": "functional-test",
                "agent_adapter": "direct",
                "evolvable_layers": ["prompts"],
            }
        ),
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


def _write_evolution_task(root: Path, task_id: str, *, visibility: str = "public") -> Path:
    task_dir = root / task_id
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        f'[identity]\nid = "{new_entity_id(EntityKind.TASK)}"\n'
        f'key = "{task_id.lower()}"\nversion = 1\n\n'
        f'[metadata]\ndifficulty = "easy"\nlifecycle = "active"\nvisibility = "{visibility}"\n',
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text("Calculate the requested engineering result.\n", encoding="utf-8")
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    return task_dir


def _config(
    root: Path, *, threshold: float = 0.02, stagnation: int = 5, max_cycles: int = 1, strategy: str = "hill_climb"
) -> EvolutionConfig:
    return EvolutionConfig(
        workspace_path=str(root),
        models={"classifier": "test", "evolver": "test"},
        task_selector=TaskSelector(),
        batch_size=1,
        max_cycles=max_cycles,
        improvement_threshold=threshold,
        stagnation_window=stagnation,
        strategy=strategy,
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


def _submitted_result(
    request,
    child: WorkspaceSnapshot,
    mutation: MutationSummary,
    *,
    memory: tuple[AVOMemoryEntry, ...] = (),
) -> CandidateProposal:
    observations = tuple(
        observation.model_copy(update={"candidate_id": child.candidate_id})
        for observation in request.parent.observations
    )
    evaluated = EvaluatedCandidate(
        snapshot=child,
        observations=observations,
        assessment=request.parent.assessment.model_copy(update={"candidate_id": child.candidate_id}),
    )
    attempt = RevisionAttempt(
        attempt_id=f"{child.candidate_id}-attempt",
        revision=1,
        evaluated=evaluated,
        mutation=mutation,
        hypothesis="The test mutation improves the candidate.",
        usage_after=ProposalUsage(development_evaluations=1),
    )
    return CandidateProposal(
        status=ProposalStatus.SUBMITTED,
        child=child,
        mutation=mutation,
        reasoning="test child",
        usage=ProposalUsage(),
        attempt=attempt,
        memory=memory,
    )


def _run(
    workspace: Workspace,
    batch: CandidateEvaluationBatch,
    *,
    parent_reward: float,
    child_reward: float,
    proposal: object,
    config: EvolutionConfig,
    evaluated_candidates: list[str] | None = None,
    run_id: str = "run-fixed",
):
    def evaluate(snapshot: WorkspaceSnapshot, _batch: CandidateEvaluationBatch):
        if evaluated_candidates is not None:
            evaluated_candidates.append(snapshot.candidate_id)
        reward = child_reward if snapshot.candidate_id != "baseline" else parent_reward
        return (_record(snapshot.candidate_id, reward),)

    def select_archive(_model, _archive, _graveyard, shortlist, _score, selected_strategy, _limit):
        return SelectionPlan(
            parent_candidate_id=shortlist[0],
            inspiration_candidate_ids=(),
            strategy=selected_strategy,
            goal="test selection",
            reasoning="test selection",
        )

    return run_evolution(
        workspace=workspace,
        config=config,
        selection_checks=CandidateChecks(plan=lambda _size, _cycle: batch, run=evaluate),
        propose=proposal,
        run_id=run_id,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
        archive_agent=select_archive if config.strategy == "qd" else None,
    )


def test_config_rejects_holdout_before_model_or_evolution_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = tmp_path / "workspace"
    (workspace_root / "prompts").mkdir(parents=True)
    (workspace_root / "prompts" / "system.md").write_text("canonical", encoding="utf-8")
    (workspace_root / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "name": "visibility-test",
                "agent_adapter": "direct",
                "evolvable_layers": ["prompts"],
            }
        ),
        encoding="utf-8",
    )
    tasks_root = tmp_path / "tasks"
    _write_evolution_task(tasks_root, "electrical/public-case")
    _write_evolution_task(tasks_root, "electrical/holdout-case", visibility="holdout")
    config = EvolutionConfig(
        workspace_path=str(workspace_root),
        models=EvolverModelConfig(classifier="classifier", evolver="evolver"),
        task_selector=TaskSelector(),
    )

    def unexpected_effect(*_args: Any, **_kwargs: Any) -> Any:
        pytest.fail("holdout validation must happen before model or evolution composition")

    monkeypatch.setattr(
        "aec_bench.providers.behavioral_llm.build_behavioral_llm_client",
        unexpected_effect,
    )
    monkeypatch.setattr(application, "build_pydantic_model", unexpected_effect)
    monkeypatch.setattr(application, "build_avo", unexpected_effect)
    monkeypatch.setattr(application, "run_evolution", unexpected_effect)

    with pytest.raises(ValueError, match="only PUBLIC tasks are permitted"):
        run_evolution_from_config(config=config, tasks_root=tasks_root)


def test_child_is_evaluated_before_commit_and_both_evidence_sets_persist(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    candidates_seen_during_eval: list[str] = []

    def submit(request, _source, child_id):
        return _submitted_result(
            request,
            request.parent.snapshot.model_copy(update={"candidate_id": child_id, "system_prompt": "child"}),
            MutationSummary(prompt_modified=True),
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.9,
        proposal=submit,
        config=_config(workspace.root),
        evaluated_candidates=candidates_seen_during_eval,
    )
    assert candidates_seen_during_eval == ["baseline", "run-fixed:1"]
    assert workspace.read_prompt() == "child"
    assert [item.candidate_id for item in workspace.list_candidates()] == ["baseline", "run-fixed:1"]
    assert result.cycle_records[0].child_assessment is not None
    trial_path = workspace.root / "_trials" / "run-fixed" / "cycle_001.jsonl"
    rows = [json.loads(line) for line in trial_path.read_text(encoding="utf-8").splitlines()]
    assert {row["candidate_id"] for row in rows} == {"baseline", "run-fixed:1"}


def test_rejected_child_keeps_canonical_workspace_and_exact_graveyard_snapshot(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)

    def submit(request, _source, child_id):
        return _submitted_result(
            request,
            request.parent.snapshot.model_copy(update={"candidate_id": child_id, "system_prompt": "rejected"}),
            MutationSummary(prompt_modified=True),
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.6,
        proposal=submit,
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
        return CandidateProposal(
            status=ProposalStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="no change",
            usage=ProposalUsage(),
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.5,
        proposal=abstain,
        config=_config(workspace.root),
    )
    assert result.cycle_records[0].gate_decision.value == "skipped"
    assert [item.candidate_id for item in workspace.list_candidates()] == ["baseline"]
    assert json.loads((workspace.root / "graveyard.json").read_text(encoding="utf-8")) == []


def test_runs_configured_multi_cycle_count_and_projects_best_and_final_scores(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)

    def submit(request, _source, child_id):
        return _submitted_result(
            request,
            request.parent.snapshot.model_copy(update={"candidate_id": child_id}),
            MutationSummary(prompt_modified=True),
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.9,
        proposal=submit,
        config=_config(workspace.root, max_cycles=3),
    )
    assert result.cycles_completed == 3
    assert result.final_score == 0.9
    assert result.best_score == 0.9
    assert result.score_history == [0.9, 0.9, 0.9]


def test_direct_cycles_carry_structured_memory_without_changing_selection(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    seen_memory: list[tuple[AVOMemoryEntry, ...]] = []
    entry = AVOMemoryEntry(
        source_variation_id="run-fixed:variation-1:child-run-fixed:1",
        source_attempt_id="run-fixed:variation-1:child-run-fixed:1:attempt-1",
        hypothesis="Add a verification step.",
        change_summary="system prompt modified",
        evidence_summary="valid=True; batch_score=0.9; evaluation_cases=1; trials=1",
        outcome="improved",
        next_direction="Test one bounded follow-up.",
    )

    def submit(request, _source, child_id):
        seen_memory.append(request.memory)
        return _submitted_result(
            request,
            request.parent.snapshot.model_copy(update={"candidate_id": child_id}),
            MutationSummary(prompt_modified=True),
            memory=(entry,),
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.9,
        proposal=submit,
        config=_config(workspace.root, max_cycles=2),
    )

    assert seen_memory == [(), (entry,)]
    assert result.cycle_records[0].selection.parent_candidate_id == "baseline"
    assert result.cycle_records[1].selection.parent_candidate_id == "run-fixed:1"


def test_stagnation_converges_before_configured_limit(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)

    def submit(request, _source, child_id):
        return _submitted_result(
            request,
            request.parent.snapshot.model_copy(update={"candidate_id": child_id}),
            MutationSummary(prompt_modified=True),
        )

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.5,
        proposal=submit,
        config=_config(workspace.root, max_cycles=10, stagnation=2),
    )
    assert result.converged is True
    assert result.cycles_completed < 10


def test_graveyard_loads_and_saves_existing_entries(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    existing = {
        "cycle": 1,
        "strategy": "conservative",
        "mutation_description": "prior failed mutation",
        "score_before": 0.4,
        "score_after": 0.3,
        "candidate_id": "old:1",
        "failure_reason": "prior rejection",
    }
    (workspace.root / "graveyard.json").write_text(json.dumps([existing]), encoding="utf-8")

    result = _run(
        workspace,
        batch,
        parent_reward=0.5,
        child_reward=0.5,
        proposal=lambda _request, _source, _child_id: CandidateProposal(
            status=ProposalStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="no change",
            usage=ProposalUsage(),
        ),
        config=_config(workspace.root),
    )
    assert result.cycles_completed == 1
    saved = json.loads((workspace.root / "graveyard.json").read_text(encoding="utf-8"))
    assert saved[0]["candidate_id"] == "old:1"


def test_qd_strategy_persists_archive_summary_on_functional_path(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    result = _run(
        workspace,
        batch,
        parent_reward=0.7,
        child_reward=0.7,
        proposal=lambda _request, _source, _child_id: CandidateProposal(
            status=ProposalStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="no change",
            usage=ProposalUsage(),
        ),
        config=_config(workspace.root, strategy="qd"),
    )
    assert result.archive_summary is not None
    assert result.archive_summary["mode"] == "qd"
    assert (workspace.root / "archive.json").exists()
    archive = json.loads((workspace.root / "archive.json").read_text(encoding="utf-8"))
    assert {entry["snapshot"]["candidate_id"] for entry in archive["entries"]} == {"baseline"}
    qd_state = json.loads((workspace.root / "qd_state.json").read_text(encoding="utf-8"))
    assert qd_state["cycle"] == 1


def test_avo_proposer_creates_one_revision_boundary_per_call(tmp_path: Path, monkeypatch) -> None:
    from pydantic_ai.models.test import TestModel

    workspace, batch = _setup(tmp_path)
    planned_cycles: list[int] = []
    boundaries = []
    budgets = []

    def development_plan(_size: int, cycle: int) -> CandidateEvaluationBatch:
        planned_cycles.append(cycle)
        return batch

    def development_evaluate(snapshot: WorkspaceSnapshot, attempt_batch: CandidateEvaluationBatch):
        trial = attempt_batch.trials[0]
        return (
            make_trial_record(
                experiment_id=trial.experiment_id,
                trial_id=trial.trial_id,
                task_id=trial.task_id,
                task={"task_id": trial.task_id, "task_revision": "task-revision", "visibility": "public"},
                inputs={
                    "instruction": "Review the task and write output.",
                    "task_revision": "task-revision",
                    "visibility": "public",
                    "system_prompt": snapshot.system_prompt,
                },
            ),
        )

    original_run = proposer_module.run_avo

    def capture(*args, **kwargs):
        boundaries.append(kwargs["revision_evaluation"])
        budgets.append(kwargs["budget"])
        return original_run(*args, **kwargs)

    monkeypatch.setattr(proposer_module, "run_avo", capture)
    operator = build_avo(
        model=TestModel(custom_output_args={"tool": "abstain", "arguments": {"reasoning": "No safe change."}}),
        model_identity="test-agent",
        advisor_model=TestModel(),
        advisor_model_identity="test-supervisor",
        revision_checks=CandidateChecks(plan=development_plan, run=development_evaluate),
        batch_size=1,
        revision_experiment_prefix="functional-development",
    )

    def host_evaluate(snapshot: WorkspaceSnapshot, _batch: CandidateEvaluationBatch):
        return (_record(snapshot.candidate_id, 0.5),)

    result = run_evolution(
        workspace=workspace,
        config=_config(workspace.root, max_cycles=2),
        selection_checks=CandidateChecks(plan=lambda _size, _cycle: batch, run=host_evaluate),
        propose=operator,
        run_id="run-fixed",
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert result.cycles_completed == 2
    assert planned_cycles == [0, 1]
    assert len(boundaries) == 2
    assert all(budget.max_supervisor_interventions == 1 for budget in budgets)
    assert boundaries[0] is not boundaries[1]
    assert all(boundary.role.value == "development" for boundary in boundaries)
    assert all(boundary.selection_experiment_id == "experiment-001" for boundary in boundaries)
    assert all(boundary.experiment_id != boundary.selection_experiment_id for boundary in boundaries)
    assert all(boundary.experiment_id.startswith("functional-development-cycle-") for boundary in boundaries)
    assert all(
        trial.experiment_id == boundary.experiment_id for boundary in boundaries for trial in boundary.batch.trials
    )
    assert all(
        trial.trial_id not in boundary.selection_trial_ids for boundary in boundaries for trial in boundary.batch.trials
    )


def test_avo_proposer_names_revision_evidence_by_run(tmp_path: Path, monkeypatch) -> None:
    workspace_one, batch_one = _setup(tmp_path / "one")
    workspace_two, batch_two = _setup(tmp_path / "two")
    boundaries = []

    def capture(*args, **kwargs):
        boundaries.append(kwargs["revision_evaluation"])
        return CandidateProposal(
            status=ProposalStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="No safe change.",
            usage=ProposalUsage(),
        )

    monkeypatch.setattr(proposer_module, "run_avo", capture)
    operator = build_avo(
        model=object(),
        model_identity="test-agent",
        revision_checks=CandidateChecks(
            plan=lambda _size, _cycle: batch_one,
            run=lambda _snapshot, _batch: (),
        ),
        batch_size=1,
    )

    _run(
        workspace_one,
        batch_one,
        parent_reward=0.5,
        child_reward=0.5,
        proposal=operator,
        config=_config(workspace_one.root),
        run_id="run-one",
    )
    _run(
        workspace_two,
        batch_two,
        parent_reward=0.5,
        child_reward=0.5,
        proposal=operator,
        config=_config(workspace_two.root),
        run_id="run-two",
    )

    assert len(boundaries) == 2
    assert boundaries[0].experiment_id != boundaries[1].experiment_id


def test_avo_proposer_requires_matching_advisor_identity_for_checkpoints(tmp_path: Path) -> None:
    identity = AVOConfigurationIdentity(
        model_identity="test-model",
        supervisor_model_identity="test-supervisor",
        tool_identity="avo-tools:1",
        development_evaluator_identity="development-evaluator:test",
        configuration_identity="test-config:1",
    )
    common = {
        "revision_checks": CandidateChecks(
            plan=lambda _size, _cycle: None,
            run=lambda _snapshot, _batch: (),
        ),
        "batch_size": 1,
        "configuration_identity": identity,
    }

    with pytest.raises(ValueError, match="model_identity must match"):
        build_avo(
            model=object(),
            model_identity="wrong-model",
            advisor_model=object(),
            advisor_model_identity="test-supervisor",
            **common,
        )

    with pytest.raises(ValueError, match="advisor_model_identity must match"):
        build_avo(
            model=object(),
            model_identity="test-model",
            advisor_model=object(),
            advisor_model_identity="wrong-supervisor",
            **common,
        )

    model = object()
    operator = build_avo(
        model=model,
        model_identity="test-model",
        advisor_model=model,
        advisor_model_identity="test-supervisor",
        **common,
    )
    assert callable(operator)
