# ABOUTME: Focused application-shell regressions for functional QD search.
# ABOUTME: Proves exact archive, graveyard, snapshot, feedback, and resume boundaries.

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    EvolutionConfig,
    MutationSummary,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig, TaskSelector
from aec_bench.evolution import agent_loop, variation_operator
from aec_bench.evolution.agent_protocol import AgentCommand, AgentToolName
from aec_bench.evolution.application import run_evolution
from aec_bench.evolution.archive import QDArchive
from aec_bench.evolution.core import (
    DevelopmentAttempt,
    EvaluatedCandidate,
    SelectionPlan,
    VariationResult,
    VariationStatus,
    VariationUsage,
)
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.evolution.selection import CellSelectionState, shortlist_cells
from aec_bench.evolution.supervision import AVOSupervisionAdvice, AVOSupervisionResult
from aec_bench.evolution.variation_operator import build_agentic_variation_operator
from aec_bench.evolution.workspace import Workspace
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.trials import PlannedTrial
from tests.support.task_factories import make_task_definition
from tests.support.trial_record_factories import make_trial_record


def _setup(tmp_path: Path, task_count: int = 1) -> tuple[Workspace, CandidateEvaluationBatch]:
    root = tmp_path / "workspace"
    (root / "prompts").mkdir(parents=True)
    (root / "prompts" / "system.md").write_text("canonical", encoding="utf-8")
    (root / "manifest.yaml").write_text(
        yaml.safe_dump({"name": "qd-test", "agent_adapter": "direct", "evolvable_layers": ["prompts"]}),
        encoding="utf-8",
    )
    workspace = Workspace(root)
    workspace.init_versioning()
    resolved_tasks = []
    trials = []
    for index in range(task_count):
        task_id = f"electrical/voltage-drop/case-{index}"
        task_dir = tmp_path / "tasks" / "electrical" / "voltage-drop" / f"case-{index}"
        task_dir.mkdir(parents=True)
        resolved = resolve_instance_paths(make_task_definition(task_id=task_id), task_dir)
        resolved_tasks.append(resolved)
        trials.append(
            PlannedTrial(
                trial_id=f"planned-{index}",
                experiment_id="qd-test",
                task_id=task_id,
                agent=AgentConfig(name="agent", adapter="direct", model="test"),
                compute=ComputeConfig(backend="local"),
                repetition=1,
            )
        )
    return workspace, CandidateEvaluationBatch(
        tasks=tuple(resolved_tasks),
        trials=tuple(trials),
        evaluation_case_ids=tuple(f"{trial.task_id}::attempt=1" for trial in trials),
    )


def _config(root: Path, *, max_cycles: int = 1, seed: int = 42, task_count: int = 1) -> EvolutionConfig:
    return EvolutionConfig(
        workspace_path=str(root),
        models={"classifier": "test", "evolver": "test"},
        task_selector=TaskSelector(),
        batch_size=task_count,
        max_cycles=max_cycles,
        improvement_threshold=0.5,
        stagnation_window=10,
        strategy="qd",
        qd_seed=seed,
        qd_n_centroids=50,
        qd_shortlist_size=5,
        qd_inspiration_limit=2,
    )


def _records(
    batch: CandidateEvaluationBatch,
    candidate_id: str,
    reward: float,
    *,
    token_cost: int = 0,
    token_costs: tuple[int, ...] | None = None,
):
    return tuple(
        make_trial_record(
            trial_id=f"{candidate_id}-trial-{index}",
            task_id=trial.task_id,
            cost={"tokens_in": token_costs[index] if token_costs is not None else token_cost},
            evaluation={
                "reward": reward,
                "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
            },
        )
        for index, trial in enumerate(batch.trials)
    )


def _selector(calls: list[dict[str, object]], *, inspiration: bool = False):
    def select(model, archive, graveyard, shortlist, score, strategy, limit):
        calls.append({"archive": archive, "graveyard": graveyard, "shortlist": tuple(shortlist), "strategy": strategy})
        return SelectionPlan(
            parent_candidate_id=shortlist[0],
            inspiration_candidate_ids=(shortlist[1],) if inspiration and len(shortlist) > 1 else (),
            strategy=strategy,
            goal="test selection",
            reasoning="test selection",
        )

    return select


def _variation(*, prompt: str, seen: list[object] | None = None):
    def submit(request, _source, child_id):
        if seen is not None:
            seen.append(request)
        child = request.parent.snapshot.model_copy(update={"candidate_id": child_id, "system_prompt": prompt})
        mutation = MutationSummary(prompt_modified=True)
        evaluated = EvaluatedCandidate(
            snapshot=child,
            observations=tuple(
                observation.model_copy(update={"candidate_id": child.candidate_id})
                for observation in request.parent.observations
            ),
            assessment=request.parent.assessment.model_copy(update={"candidate_id": child.candidate_id}),
        )
        attempt = DevelopmentAttempt(
            attempt_id=f"{child.candidate_id}-attempt",
            revision=1,
            evaluated=evaluated,
            mutation=mutation,
            hypothesis="The test mutation improves the candidate.",
            usage_after=VariationUsage(development_evaluations=1),
        )
        return VariationResult(
            status=VariationStatus.SUBMITTED,
            child=child,
            mutation=mutation,
            reasoning="test mutation",
            usage=VariationUsage(),
            attempt=attempt,
        )

    return submit


def _abstain(request, _source, _child_id):
    return VariationResult(
        status=VariationStatus.ABSTAINED,
        child=None,
        mutation=None,
        reasoning="test abstention",
        usage=VariationUsage(),
    )


def _run(
    workspace: Workspace,
    batch: CandidateEvaluationBatch,
    config: EvolutionConfig,
    *,
    evaluate,
    variation,
    calls: list[dict[str, object]],
    run_id: str = "run-fixed",
    inspiration: bool = False,
):
    return run_evolution(
        workspace=workspace,
        config=config,
        evaluate=evaluate,
        batch_planner=lambda _size, _cycle: batch,
        variation=variation,
        enrich=lambda observations: observations,
        archive_agent=_selector(calls, inspiration=inspiration),
        run_id=run_id,
        clock=lambda: datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_baseline_evidence_is_archived_before_selection(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    calls: list[dict[str, object]] = []
    result = _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=lambda snapshot, _batch: _records(batch, snapshot.candidate_id, 0.73),
        variation=_abstain,
        calls=calls,
    )
    archive = calls[0]["archive"]
    assert archive.get_entry_by_candidate_id("baseline").bd.reward == 0.73
    assert result.cycle_records[0].selection.parent_candidate_id == "baseline"


def test_real_graveyard_is_passed_to_archive_agent(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    first_calls: list[dict[str, object]] = []
    _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=lambda snapshot, _batch: _records(batch, snapshot.candidate_id, 0.5),
        variation=_variation(prompt="rejected"),
        calls=first_calls,
    )
    second_calls: list[dict[str, object]] = []
    _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=lambda snapshot, _batch: _records(batch, snapshot.candidate_id, 0.5),
        variation=_abstain,
        calls=second_calls,
        run_id="run-resumed",
    )
    graveyard = second_calls[0]["graveyard"]
    assert graveyard.size == 1
    entry = graveyard.browse(limit=1)[0]
    assert entry.candidate_id == "run-fixed:1"
    assert entry.rejected_snapshot.system_prompt == "rejected"


def test_archive_inspiration_resolves_to_exact_snapshot(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    archive = QDArchive(n_centroids=50, seed=42)
    parent = WorkspaceSnapshot(system_prompt="parent", skills=[], candidate_id="archive-parent")
    inspiration = WorkspaceSnapshot(system_prompt="inspiration", skills=[], candidate_id="archive-inspiration")
    archive.insert(
        BehaviourDescriptor(
            token_cost=0, verification_depth=0, tool_density=0, exploration_ratio=0, deliberation_ratio=0, reward=0.5
        ),
        parent,
    )
    archive.insert(
        BehaviourDescriptor(
            token_cost=500_000,
            verification_depth=1,
            tool_density=2,
            exploration_ratio=1,
            deliberation_ratio=1,
            reward=0.5,
        ),
        inspiration,
    )
    archive.save(workspace.root / "archive.json")
    calls: list[dict[str, object]] = []

    seen: list[object] = []

    def capture(request, source, child_id):
        seen.append(request)
        return _abstain(request, source, child_id)

    _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=lambda snapshot, _batch: _records(batch, snapshot.candidate_id, 0.5),
        variation=capture,
        calls=calls,
        inspiration=True,
    )
    expected = {parent.candidate_id: parent, inspiration.candidate_id: inspiration}
    selected_id = seen[0].selection.inspiration_candidate_ids[0]
    assert seen[0].inspirations == (expected[selected_id],)


def test_lower_global_score_can_enter_a_new_niche_without_replacing_best(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    calls: list[dict[str, object]] = []

    def evaluate(snapshot, _batch):
        return _records(
            batch,
            snapshot.candidate_id,
            0.8 if snapshot.candidate_id == "baseline" else 0.1,
            token_cost=0 if snapshot.candidate_id == "baseline" else 500_000,
        )

    result = _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=evaluate,
        variation=_variation(prompt="lower-score"),
        calls=calls,
    )
    assert result.cycle_records[0].gate_decision.value == "accepted"
    assert result.best_candidate_id == "baseline"
    assert result.best_score == 0.8


def test_non_inserted_child_keeps_exact_snapshot_and_evidence_in_graveyard(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    calls: list[dict[str, object]] = []
    _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=lambda snapshot, _batch: _records(batch, snapshot.candidate_id, 0.5),
        variation=_variation(prompt="rejected-exact"),
        calls=calls,
    )
    entry = json.loads((workspace.root / "graveyard.json").read_text(encoding="utf-8"))[0]
    assert entry["rejected_snapshot"]["system_prompt"] == "rejected-exact"
    assert entry["child_assessment"]["candidate_id"] == "run-fixed:1"


def test_feedback_is_single_counted_and_abstention_has_no_feedback(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path, task_count=2)
    calls: list[dict[str, object]] = []
    _run(
        workspace,
        batch,
        _config(workspace.root, task_count=2),
        evaluate=lambda snapshot, _batch: _records(
            batch,
            snapshot.candidate_id,
            0.5 if snapshot.candidate_id == "baseline" else 0.9,
        ),
        variation=_variation(prompt="accepted"),
        calls=calls,
    )
    state = json.loads((workspace.root / "qd_state.json").read_text(encoding="utf-8"))
    assert sum(item["selection_count"] for item in state["cell_selection"]) == 1
    assert sum(item["improvement_count"] for item in state["cell_selection"]) <= 1
    assert state["strategy_bandit"] == [
        {"strategy": state["last_selection"]["strategy"], "attempts": 1, "successes": 1}
    ]

    workspace2, batch2 = _setup(tmp_path / "abstain")
    calls2: list[dict[str, object]] = []
    _run(
        workspace2,
        batch2,
        _config(workspace2.root),
        evaluate=lambda snapshot, _batch: _records(batch2, snapshot.candidate_id, 0.8),
        variation=_abstain,
        calls=calls2,
    )
    state2 = json.loads((workspace2.root / "qd_state.json").read_text(encoding="utf-8"))
    assert state2["strategy_bandit"] == []
    assert all(item["selection_count"] == 0 for item in state2["cell_selection"])


def test_qd_uses_the_shared_variation_seam_and_hosts_only_the_final_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from pydantic_ai.models.test import TestModel

    workspace, batch = _setup(tmp_path)
    calls: list[dict[str, object]] = []
    host_evaluated_ids: list[str] = []

    def development_evaluate(snapshot, attempt_batch):
        return tuple(
            make_trial_record(
                experiment_id=trial.experiment_id,
                trial_id=trial.trial_id,
                task_id=trial.task_id,
                task={"task_id": trial.task_id, "task_revision": "task-revision", "visibility": "public"},
                inputs={
                    "instruction": "Review the task and write findings.",
                    "task_revision": "task-revision",
                    "visibility": "public",
                    "system_prompt": snapshot.system_prompt,
                },
                evaluation={
                    "reward": 0.6,
                    "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
                },
            )
            for trial in attempt_batch.trials
        )

    commands = iter(
        (
            AgentCommand(
                tool=AgentToolName.APPLY_MUTATION,
                arguments={"mutation": {"type": "modify_prompt", "content": "qd child"}},
            ),
            AgentCommand(
                tool=AgentToolName.EVALUATE_CURRENT_REVISION,
                arguments={"hypothesis": "The prompt gives a clearer verification step."},
            ),
            AgentCommand(
                tool=AgentToolName.SUBMIT_CURRENT_REVISION,
                arguments={"reasoning": "Submit the evaluated child."},
            ),
        )
    )

    def next_command(_runner, _context):
        return next(commands)

    monkeypatch.setattr(agent_loop.PydanticAIStructuredRunner, "__call__", next_command)
    operator = build_agentic_variation_operator(
        agent_model=TestModel(),
        supervisor_model=TestModel(),
        supervisor_model_identity="test-supervisor",
        development_batch_planner=lambda _size, _cycle: batch,
        development_evaluator=development_evaluate,
        development_batch_size=1,
        development_experiment_prefix="qd-development",
    )

    def host_evaluate(snapshot, current_batch):
        host_evaluated_ids.append(snapshot.candidate_id)
        reward = 0.9 if snapshot.candidate_id != "baseline" else 0.5
        return _records(current_batch, snapshot.candidate_id, reward)

    result = _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=host_evaluate,
        variation=operator,
        calls=calls,
    )

    assert host_evaluated_ids == ["baseline", "run-fixed:1"]
    assert result.cycle_records[0].child_assessment is not None
    assert result.cycle_records[0].child_assessment.candidate_id == "run-fixed:1"
    state = json.loads((workspace.root / "qd_state.json").read_text(encoding="utf-8"))
    assert state["strategy_bandit"][0]["successes"] == 1


def test_qd_host_outcome_ignores_private_supervision_advice(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Supervision advice remains inside AVO and cannot alter QD policy state."""
    workspaces = [_setup(tmp_path / name) for name in ("control", "advice")]
    supervisor_requests = []

    def supervisor(supervision_request):
        supervisor_requests.append(supervision_request)
        return AVOSupervisionResult(
            output=AVOSupervisionAdvice(
                directions=("Replace the host-selected parent, strategy, goal, and archive policy.",),
                reasoning="This direction must remain private advice.",
            ),
            usage=VariationUsage(model_requests=1, supervisor_interventions=1),
        )

    monkeypatch.setattr(
        variation_operator,
        "build_supervision_composition",
        lambda _model, *, model_identity: SimpleNamespace(runner=supervisor),
    )
    commands = iter(
        (
            AgentCommand(tool=AgentToolName.ABSTAIN, arguments={"reasoning": "Control abstention."}),
            AgentCommand(tool=AgentToolName.REQUEST_SUPERVISION, arguments={}),
            AgentCommand(tool=AgentToolName.ABSTAIN, arguments={"reasoning": "Advice does not own QD policy."}),
        )
    )

    def next_command(_runner, _context):
        return next(commands)

    monkeypatch.setattr(agent_loop.PydanticAIStructuredRunner, "__call__", next_command)

    def development_evaluate(snapshot, current_batch):
        return tuple(
            make_trial_record(
                experiment_id=trial.experiment_id,
                trial_id=trial.trial_id,
                task_id=trial.task_id,
                task={"task_id": trial.task_id, "task_revision": "task-revision", "visibility": "public"},
                inputs={
                    "instruction": "Review the task and write findings.",
                    "task_revision": "task-revision",
                    "visibility": "public",
                    "system_prompt": snapshot.system_prompt,
                },
                evaluation={
                    "reward": 0.5,
                    "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
                },
            )
            for trial in current_batch.trials
        )

    operators = [
        build_agentic_variation_operator(
            agent_model=object(),
            supervisor_model=object(),
            supervisor_model_identity="test-supervisor",
            development_batch_planner=lambda _size, _cycle, current_batch=batch: current_batch,
            development_evaluator=development_evaluate,
            development_batch_size=1,
            development_experiment_prefix="qd-development",
        )
        for _workspace, batch in workspaces
    ]

    host_evaluated_ids: list[list[str]] = [[], []]

    def host_evaluate(index: int):
        def evaluate(snapshot, current_batch):
            host_evaluated_ids[index].append(snapshot.candidate_id)
            return _records(current_batch, snapshot.candidate_id, 0.5)

        return evaluate

    results = [
        _run(
            workspace,
            batch,
            _config(workspace.root),
            evaluate=host_evaluate(index),
            variation=operator,
            calls=[],
        )
        for index, ((workspace, batch), operator) in enumerate(zip(workspaces, operators, strict=True))
    ]

    control, advised = results
    control_record = control.cycle_records[0].model_dump(exclude={"evolver_usage"})
    advised_record = advised.cycle_records[0].model_dump(exclude={"evolver_usage"})
    assert advised_record == control_record
    assert advised.cycle_records[0].evolver_usage.supervisor_interventions == 1
    assert control.cycle_records[0].evolver_usage.supervisor_interventions == 0
    assert host_evaluated_ids == [["baseline"], ["baseline"]]
    assert len(supervisor_requests) == 1
    assert supervisor_requests[0].goal == "test selection"
    assert supervisor_requests[0].selected_parent_id == "baseline"
    assert supervisor_requests[0].strategy == control.cycle_records[0].selection.strategy
    assert json.loads((workspaces[0][0].root / "archive.json").read_text(encoding="utf-8")) == json.loads(
        (workspaces[1][0].root / "archive.json").read_text(encoding="utf-8")
    )
    assert json.loads((workspaces[0][0].root / "qd_state.json").read_text(encoding="utf-8")) == json.loads(
        (workspaces[1][0].root / "qd_state.json").read_text(encoding="utf-8")
    )


def test_fixed_seed_selection_and_resume_numbering_are_reproducible(tmp_path: Path) -> None:
    traces = []
    for index in range(2):
        workspace, batch = _setup(tmp_path / str(index))
        calls: list[dict[str, object]] = []
        _run(
            workspace,
            batch,
            _config(workspace.root, seed=17),
            evaluate=lambda snapshot, _batch, current_batch=batch: _records(current_batch, snapshot.candidate_id, 0.5),
            variation=_abstain,
            calls=calls,
        )
        resumed = _run(
            workspace,
            batch,
            _config(workspace.root, seed=17),
            evaluate=lambda snapshot, _batch, current_batch=batch: _records(current_batch, snapshot.candidate_id, 0.5),
            variation=_abstain,
            calls=calls,
            run_id="resume",
        )
        traces.append((calls[0]["strategy"], calls[0]["shortlist"], calls[1]["strategy"], calls[1]["shortlist"]))
        assert json.loads((workspace.root / "qd_state.json").read_text(encoding="utf-8"))["cycle"] == 2
        assert resumed.cycle_records[0].cycle == 2
    assert traces[0] == traces[1]


def test_duplicate_candidate_feedback_uses_one_shortlisted_cell(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path, task_count=2)
    calls: list[dict[str, object]] = []
    _run(
        workspace,
        batch,
        _config(workspace.root, task_count=2, seed=17),
        evaluate=lambda snapshot, _batch: _records(
            batch,
            snapshot.candidate_id,
            0.8,
            token_costs=(0, 500_000),
        ),
        variation=_variation(prompt="duplicate-cell-child"),
        calls=calls,
    )
    state = json.loads((workspace.root / "qd_state.json").read_text(encoding="utf-8"))
    archive_view = calls[0]["archive"]
    occupied_cells = [entry.cell_index for entry in archive_view.entries]
    assert len(occupied_cells) == 2
    ranked_cells = shortlist_cells(CellSelectionState(), occupied_cells, seed=17)
    candidate_id = calls[0]["shortlist"][0]
    candidate_cells = {
        entry.cell_index for entry in archive_view.entries if entry.snapshot.candidate_id == candidate_id
    }
    expected_cell = next(cell for cell in ranked_cells if cell in candidate_cells)
    selected_cells = [item for item in state["cell_selection"] if item["selection_count"]]
    assert [item["cell_index"] for item in selected_cells] == [expected_cell]


def test_current_baseline_snapshot_wins_over_stale_persisted_archive_material(tmp_path: Path) -> None:
    workspace, batch = _setup(tmp_path)
    archive = QDArchive(n_centroids=50, seed=42)
    archive.insert(
        BehaviourDescriptor(
            token_cost=0, verification_depth=0, tool_density=0, exploration_ratio=0, deliberation_ratio=0, reward=0.9
        ),
        WorkspaceSnapshot(system_prompt="stale", skills=[], candidate_id="baseline"),
    )
    archive.save(workspace.root / "archive.json")
    seen: list[object] = []
    calls: list[dict[str, object]] = []
    _run(
        workspace,
        batch,
        _config(workspace.root),
        evaluate=lambda snapshot, _batch: _records(batch, snapshot.candidate_id, 0.5),
        variation=_variation(prompt="unused", seen=seen),
        calls=calls,
    )
    assert seen[0].parent.snapshot.system_prompt == "canonical"
