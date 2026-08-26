# ABOUTME: Tests the bounded typed agentic variation loop and its scratch tools.
# ABOUTME: Covers fixed parent-first evaluation, limits, evidence identity, and terminal outcomes.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

import aec_bench.evolution.checkpoint as checkpoint_module
from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    FieldScore,
    MutationStrategy,
    ObservationEnrichment,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.agent_loop import (
    AgentCommand,
    AgentContext,
    AgentToolName,
    MutationInput,
    PydanticAIStructuredRunner,
    run_agentic_variation,
)
from aec_bench.evolution.agent_protocol import AgentResponse
from aec_bench.evolution.analysis import BehavioralPattern, EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.checkpoint import AVOConfigurationIdentity, AVOIncompleteExternalEffectError, read_checkpoint
from aec_bench.evolution.core import (
    AVOBudget,
    EvaluatedCandidate,
    SelectionPlan,
    VariationRequest,
    VariationStatus,
)
from aec_bench.evolution.development import DevelopmentEvaluationBoundary
from aec_bench.evolution.evaluation import CandidateEvaluationBatch
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.resume import AVOResumeMismatchError, checkpoint_path
from aec_bench.evolution.supervision import AVOSupervisionAdvice, AVOSupervisionResult
from aec_bench.evolution.workspace import Workspace
from tests.evolution.test_development import _batch, _record
from tests.support.trial_record_factories import make_trial_record


def _workspace(root: Path) -> Workspace:
    root.mkdir(parents=True)
    (root / "manifest.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_version": 1,
                "name": "agent-loop-test",
                "agent_adapter": "tool_loop",
                "evolvable_layers": ["prompts", "skills"],
            }
        )
    )
    (root / "prompts").mkdir()
    (root / "prompts" / "system.md").write_text("Canonical prompt")
    return Workspace(root)


def _request(
    workspace: Workspace,
    *,
    patterns: tuple[BehavioralPattern, ...] = (),
    parent_id: str = "parent",
    inspiration: WorkspaceSnapshot | None = None,
    memory: tuple[AVOMemoryEntry, ...] = (),
) -> VariationRequest:
    trial = make_trial_record(
        trial_id="trial-1",
        evaluation={
            "reward": 0.4,
            "validity": {"output_parseable": True, "schema_valid": True, "verifier_completed": True},
        },
    )
    observation = EvolutionObservation(
        trial=trial,
        enrichment=ObservationEnrichment(
            field_scores=[FieldScore(field_name="voltage", reward=0.0, expected="1", actual="2")]
        ),
        candidate_id=parent_id,
        discipline="electrical",
    )
    assessment = CandidateAssessment(
        candidate_id=parent_id,
        batch_score=0.4,
        structural_score=None,
        discipline_scores={"electrical": 0.4},
        trial_ids=("trial-1",),
        evaluation_case_ids=("case-1",),
        valid=True,
    )
    parent = EvaluatedCandidate(
        snapshot=workspace.export_snapshot(parent_id),
        observations=(observation,),
        assessment=assessment,
    )
    return VariationRequest(
        run_id="run-test",
        selection=SelectionPlan(
            parent_id,
            () if inspiration is None else (inspiration.candidate_id,),
            MutationStrategy.CONSERVATIVE,
            "Improve checks",
            "test",
        ),
        parent=parent,
        inspirations=() if inspiration is None else (inspiration,),
        analysis=EvolutionAnalysis([], list(patterns), GraduatedScope.TARGETED, None, 0.4),
        scope=GraduatedScope.TARGETED,
        history=(),
        graveyard=(),
        cycle=1,
        memory=memory,
    )


def _boundary(
    tmp_path: Path,
    *,
    invalid: bool = False,
    trial_prefix: str = "development-trial",
    batch: CandidateEvaluationBatch | None = None,
) -> DevelopmentEvaluationBoundary:
    selected_batch = batch or _batch(tmp_path / "batch")
    counter = 0

    def evaluate(_snapshot: object, _batch_value: object):
        nonlocal counter
        counter += 1
        record = _record(trial_id=f"{trial_prefix}-{counter}")
        if invalid:
            record = record.model_copy(
                update={
                    "evaluation": EvaluationResult(
                        reward=0.0,
                        validity=ValidityCheck(
                            output_parseable=False,
                            schema_valid=True,
                            verifier_completed=True,
                            errors=("invalid fixture",),
                        ),
                    )
                }
            )
        return (record,)

    return DevelopmentEvaluationBoundary(
        planner=lambda _size, _cycle: selected_batch,
        evaluator=evaluate,
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )


def _checkpoint_identity() -> AVOConfigurationIdentity:
    return AVOConfigurationIdentity(
        model_identity="test-model",
        supervisor_model_identity="test-supervisor-model",
        tool_identity="avo-tools:1",
        development_evaluator_identity="development-evaluator:test",
        configuration_identity="test-config:1",
    )


class _SequenceRunner:
    def __init__(self, commands: list[AgentCommand | Callable[[AgentContext], AgentCommand]]) -> None:
        self.commands = commands
        self.contexts: list[AgentContext] = []

    def __call__(self, context: AgentContext) -> AgentCommand:
        self.contexts.append(context)
        command = self.commands.pop(0)
        return command(context) if callable(command) else command


def _command(tool: AgentToolName, **arguments: object) -> AgentCommand:
    return AgentCommand(tool=tool, arguments=arguments)


def test_loop_exposes_only_approved_tools_and_returns_abstention(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    seen: dict[str, object] = {}

    def inspect(context: AgentContext) -> AgentCommand:
        seen["tools"] = tuple(context.tools)
        seen["parent"] = context.tools["read_parent_evidence"]()
        seen["workspace"] = context.tools["read_current_workspace"]()
        seen["inspiration"] = context.tools["read_inspiration"]()
        seen["history"] = context.tools["read_history"]()
        seen["graveyard"] = context.tools["read_graveyard"]()
        seen["knowledge"] = context.tools["read_knowledge"]()
        return _command(AgentToolName.ABSTAIN, reasoning="No safe change is justified.")

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=inspect,
        knowledge_source="Approved engineering guidance.",
    )

    assert result.status is VariationStatus.ABSTAINED
    assert seen["tools"] == (
        "read_parent_evidence",
        "read_current_workspace",
        "read_inspiration",
        "read_history",
        "read_graveyard",
        "read_knowledge",
        "apply_mutation",
        "evaluate_current_revision",
        "restore_attempt",
        "submit_current_revision",
        "abstain",
    )
    assert result.usage.development_evaluations == 1


def test_loop_fails_closed_on_incomplete_model_request(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    first_boundary = _boundary(tmp_path / "first-boundary")

    def interrupting_runner(context: AgentContext) -> AgentCommand:
        context.tools["apply_mutation"](
            mutation={"type": "modify_prompt", "content": "Child prompt with a verification step."}
        )
        raise RuntimeError("simulated interruption")

    with pytest.raises(AVOIncompleteExternalEffectError, match="simulated interruption"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=first_boundary,
            agent_runner=interrupting_runner,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    assert path.is_file()
    saved = read_checkpoint(path)
    assert saved.current_revision == 1
    assert not saved.evaluated_attempts

    with pytest.raises(AVOIncompleteExternalEffectError, match="must be reconciled"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "second-boundary", batch=first_boundary.batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not retry")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_explicit_supervision_request_persists_advice_for_next_main_context(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    main_runner = _SequenceRunner(
        [
            _command(AgentToolName.REQUEST_SUPERVISION),
            _command(AgentToolName.ABSTAIN, reasoning="The advised direction is not safe to submit."),
        ]
    )
    supervisor_calls = []

    def supervisor(supervision_request):
        supervisor_calls.append(supervision_request)
        return AVOSupervisionResult(
            output=AVOSupervisionAdvice(
                directions=("Try a bounded verification-focused direction.",),
                reasoning="The current direction has repeated without progress.",
            ),
            usage=VariationUsage(model_requests=1, supervisor_interventions=1, elapsed_seconds=0.25),
        )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path / "boundary"),
        agent_runner=main_runner,
        supervisor_runner=supervisor,
        budget=AVOBudget(max_supervisor_interventions=1),
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
    )

    assert result.status is VariationStatus.ABSTAINED
    assert len(supervisor_calls) == 1
    assert len(main_runner.contexts) == 2
    next_context = main_runner.contexts[1]
    assert next_context.latest_supervision_advice is not None
    assert next_context.latest_supervision_advice.directions == ("Try a bounded verification-focused direction.",)
    assert "request_supervision" not in next_context.tools
    assert result.usage.supervisor_interventions == 1
    saved = read_checkpoint(path)
    assert len(saved.supervision_records) == 1
    assert saved.supervision_records[0].advice == next_context.latest_supervision_advice
    assert not saved.incomplete_external_effects


def test_supervision_provider_exception_leaves_marker_and_resume_does_not_retry(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    boundary = _boundary(tmp_path / "boundary")
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    budget = AVOBudget(max_supervisor_interventions=1)

    def failing_supervisor(_request):
        raise RuntimeError("ambiguous supervisor provider")

    with pytest.raises(AVOIncompleteExternalEffectError, match="ambiguous supervisor provider"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=boundary,
            agent_runner=lambda _context: _command(AgentToolName.REQUEST_SUPERVISION),
            supervisor_runner=failing_supervisor,
            budget=budget,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    saved = read_checkpoint(path)
    assert saved.usage.supervisor_interventions == 1
    assert saved.incomplete_external_effects[0].operation == "supervisor_request"

    with pytest.raises(AVOIncompleteExternalEffectError, match="must be reconciled"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "resume-boundary", batch=boundary.batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("main agent must not retry")),
            supervisor_runner=lambda _request: (_ for _ in ()).throw(AssertionError("supervisor must not retry")),
            budget=budget,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_loop_resumes_clean_mutation_checkpoint_without_repeating_parent_evaluation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workspace = _workspace(tmp_path / "workspace")
    prior = AVOMemoryEntry(
        source_variation_id="prior-variation",
        source_attempt_id="prior-attempt",
        hypothesis="Use a verification step.",
        change_summary="system prompt modified",
        evidence_summary="valid=True; batch_score=0.4; evaluation_cases=1; trials=1",
        outcome="improved",
    )
    request = _request(workspace, memory=(prior,))
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    first_boundary = _boundary(tmp_path / "first-boundary")
    original_write = checkpoint_module.write_checkpoint

    def crash_after_clean_mutation(selected_path: Path, checkpoint: checkpoint_module.AVOCheckpoint) -> Path:
        written_path = original_write(selected_path, checkpoint)
        if (
            checkpoint.current_revision == 1
            and not checkpoint.evaluated_attempts
            and not checkpoint.incomplete_external_effects
            and checkpoint.terminal_result is None
        ):
            raise RuntimeError("simulated crash after clean mutation checkpoint")
        return written_path

    monkeypatch.setattr(checkpoint_module, "write_checkpoint", crash_after_clean_mutation)
    with pytest.raises(RuntimeError, match="simulated crash after clean mutation checkpoint"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=first_boundary,
            agent_runner=lambda _context: _command(
                AgentToolName.APPLY_MUTATION,
                mutation={"type": "modify_prompt", "content": "Child prompt with a verification step."},
            ),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    saved = read_checkpoint(path)
    assert saved.current_revision == 1
    assert saved.structured_memory == (prior,)
    assert not saved.incomplete_external_effects
    monkeypatch.setattr(checkpoint_module, "write_checkpoint", original_write)

    runner = _SequenceRunner(
        [
            _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="Add a verification step."),
            _command(AgentToolName.SUBMIT_CURRENT_REVISION, reasoning="The evaluated revision is eligible."),
        ]
    )
    resumed = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(
            tmp_path / "second-boundary",
            trial_prefix="resumed-development-trial",
            batch=first_boundary.batch,
        ),
        agent_runner=runner,
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
    )

    assert resumed.status is VariationStatus.SUBMITTED
    assert resumed.usage.development_evaluations == 2
    assert runner.contexts[0].memory == (prior,)
    assert resumed.memory[0] == prior
    assert len(resumed.memory) == 2
    assert read_checkpoint(path).terminal_result is not None


def test_incomplete_model_request_checkpoint_preserves_structured_memory(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    prior = AVOMemoryEntry(
        source_variation_id="prior-variation",
        source_attempt_id="prior-attempt",
        hypothesis="Use a verification step.",
        change_summary="system prompt modified",
        evidence_summary="valid=True; batch_score=0.4; evaluation_cases=1; trials=1",
        outcome="improved",
        next_direction="Try one bounded follow-up.",
    )
    request = _request(workspace, memory=(prior,))
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    first_boundary = _boundary(tmp_path / "first-boundary")

    def interrupting_runner(context: AgentContext) -> AgentCommand:
        assert context.memory == (prior,)
        context.tools["apply_mutation"](
            mutation={"type": "modify_prompt", "content": "Child prompt with a verification step."}
        )
        raise RuntimeError("simulated interruption")

    with pytest.raises(AVOIncompleteExternalEffectError, match="simulated interruption"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=first_boundary,
            agent_runner=interrupting_runner,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    saved = read_checkpoint(path)
    assert saved.structured_memory == (prior,)

    with pytest.raises(AVOIncompleteExternalEffectError, match="must be reconciled"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "second-boundary", batch=first_boundary.batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not retry")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_resume_rejects_changed_incoming_memory_before_running_effects(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    boundary = _boundary(tmp_path / "boundary")

    def interrupting_runner(context: AgentContext) -> AgentCommand:
        context.tools["apply_mutation"](
            mutation={"type": "modify_prompt", "content": "Child prompt with a verification step."}
        )
        raise RuntimeError("simulated interruption")

    with pytest.raises(RuntimeError, match="simulated interruption"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=boundary,
            agent_runner=interrupting_runner,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    changed_memory = AVOMemoryEntry(
        source_variation_id="different-variation",
        source_attempt_id="different-attempt",
        hypothesis="Use a different hypothesis.",
        change_summary="system prompt modified",
        evidence_summary="valid=True; batch_score=0.4; evaluation_cases=1; trials=1",
        outcome="improved",
    )
    changed_request = _request(workspace, memory=(changed_memory,))
    with pytest.raises(AVOResumeMismatchError, match="configuration identity"):
        run_agentic_variation(
            changed_request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "changed-boundary", batch=boundary.batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_resume_rejects_development_plan_drift_with_same_case_ids(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    original_batch = _batch(tmp_path / "original-batch")

    def interrupting_runner(context: AgentContext) -> AgentCommand:
        context.tools["apply_mutation"](
            mutation={"type": "modify_prompt", "content": "Child prompt with a verification step."}
        )
        raise RuntimeError("simulated interruption")

    with pytest.raises(RuntimeError, match="simulated interruption"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "original-boundary", batch=original_batch),
            agent_runner=interrupting_runner,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    changed_trial = replace(
        original_batch.trials[0],
        agent=original_batch.trials[0].agent.model_copy(update={"model": "different-model"}),
    )
    changed_batch = replace(original_batch, trials=(changed_trial,))
    with pytest.raises(AVOResumeMismatchError, match="configuration identity"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "changed-boundary", batch=changed_batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_loop_evaluates_parent_first_and_submits_current_revision(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(
                AgentToolName.APPLY_MUTATION,
                mutation={
                    "type": "modify_prompt",
                    "content": "Child prompt with a verification step.",
                },
            ),
            _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="Add a verification step."),
            _command(AgentToolName.SUBMIT_CURRENT_REVISION, reasoning="The evaluated revision is eligible."),
        ]
    )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
        development_evaluation_cost_usd=0.2,
    )

    assert result.status is VariationStatus.SUBMITTED
    assert result.child is not None
    assert result.child.system_prompt == "Child prompt with a verification step."
    assert result.attempt is not None
    assert result.attempt.revision == 1
    assert result.attempt.evaluated.observations[0].trial.trial_id == "development-trial-2"
    assert result.usage.model_requests == 3
    assert result.usage.tool_calls == 3
    assert result.usage.development_evaluations == 2
    assert result.usage.development_evaluation_cost_usd == 0.4
    assert runner.contexts[1].previous_tool_result is not None
    assert workspace.read_prompt() == "Canonical prompt"


def test_last_allowed_development_evaluation_can_be_followed_by_submission(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "Child"}),
            _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="The child adds a verification step."),
            _command(AgentToolName.SUBMIT_CURRENT_REVISION, reasoning="The last allowed evaluation is eligible."),
        ]
    )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
        budget=AVOBudget(max_development_evaluations=2),
    )

    assert result.status is VariationStatus.SUBMITTED
    assert result.attempt is not None and result.attempt.revision == 1
    assert result.usage.development_evaluations == 2


def test_stale_and_unchanged_submission_are_rejected_without_child(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(AgentToolName.SUBMIT_CURRENT_REVISION),
            _command(
                AgentToolName.APPLY_MUTATION,
                mutation={"type": "modify_prompt", "content": "Canonical prompt"},
            ),
            _command(AgentToolName.ABSTAIN, reasoning="The candidate stayed unchanged."),
        ]
    )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
    )

    assert result.status is VariationStatus.ABSTAINED
    assert isinstance(runner.contexts[1].previous_tool_result, object)
    assert "eligible" in str(runner.contexts[1].previous_tool_result).lower()
    assert "no effective" in str(runner.contexts[2].previous_tool_result).lower()
    assert workspace.read_prompt() == "Canonical prompt"


def test_next_request_receives_typed_tool_error(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(AgentToolName.EVALUATE_CURRENT_REVISION),
            lambda context: (
                pytest.fail("tool error was not returned to the next request")
                if context.previous_tool_error is None
                else _command(AgentToolName.ABSTAIN, reasoning="The malformed request was diagnosed.")
            ),
        ]
    )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
    )

    assert result.status is VariationStatus.ABSTAINED
    assert "hypothesis" in str(runner.contexts[1].previous_tool_error)


def test_restore_keeps_attempt_evidence_and_makes_exact_material_current(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "First"}),
            _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="First hypothesis."),
            _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "Second"}),
            _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="Second hypothesis."),
            _command(AgentToolName.RESTORE_ATTEMPT, revision=1),
            _command(AgentToolName.SUBMIT_CURRENT_REVISION, reasoning="Restore is the safer evaluated revision."),
        ]
    )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
        budget=AVOBudget(max_stagnant_evaluations=10),
    )

    assert result.status is VariationStatus.SUBMITTED
    assert result.child is not None and result.child.system_prompt == "First"
    assert result.attempt is not None and result.attempt.revision == 1
    assert result.usage.development_evaluations == 3
    assert tuple(attempt.revision for attempt in runner.contexts[-1].state.attempts) == (1, 2)


def test_scope_limits_current_material_not_iterative_repairs(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = replace(_request(workspace), scope=GraduatedScope.MINIMAL)
    runner = _SequenceRunner(
        [
            _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "Prompt change"}),
            _command(
                AgentToolName.APPLY_MUTATION,
                mutation={
                    "type": "write_skill",
                    "name": "verification",
                    "description": "Verification guidance",
                    "body": "Always verify the result before submission.",
                },
            ),
            _command(AgentToolName.ABSTAIN, reasoning="Scope rejected the second material change."),
        ]
    )
    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
        budget=AVOBudget(max_stagnant_evaluations=10),
    )

    assert result.status is VariationStatus.ABSTAINED
    rejected = runner.contexts[2].previous_tool_result
    assert rejected is not None and "scope exceeded" in str(rejected)


def test_sanitiser_reverted_mutation_does_not_create_revision(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(
                AgentToolName.APPLY_MUTATION,
                mutation={
                    "type": "write_skill",
                    "name": "trivial",
                    "description": "A deliberately short skill.",
                    "body": "Too short.",
                },
            ),
            _command(AgentToolName.ABSTAIN, reasoning="The sanitiser removed the trivial skill."),
        ]
    )

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
    )

    assert result.status is VariationStatus.ABSTAINED
    mutation_result = runner.contexts[1].previous_tool_result
    assert mutation_result is not None
    assert "sanitisation removed" in str(mutation_result)
    assert runner.contexts[1].state.current_revision == 0


def test_hard_limit_exhausts_without_silent_submission(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [_command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "Child"})]
    )
    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=runner,
        budget=AVOBudget(max_model_requests=1),
    )

    assert result.status is VariationStatus.BUDGET_EXHAUSTED
    assert result.child is None
    assert result.usage.model_requests == 1
    assert result.usage.development_evaluations == 1


def test_token_limit_blocks_model_selected_tool_effect(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=lambda _context: AgentResponse(
            command=_command(
                AgentToolName.APPLY_MUTATION,
                mutation={"type": "modify_prompt", "content": "Must not be applied."},
            ),
            input_tokens=11,
            output_tokens=1,
        ),
        budget=AVOBudget(max_input_tokens=10),
    )

    assert result.status is VariationStatus.BUDGET_EXHAUSTED
    assert workspace.export_snapshot("parent").system_prompt == request.parent.snapshot.system_prompt
    assert result.usage.input_tokens == 11


def test_invalid_development_evidence_cannot_become_best_attempt(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    runner = _SequenceRunner(
        [
            _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "Invalid"}),
            _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="Invalid evidence."),
            _command(AgentToolName.ABSTAIN, reasoning="Invalid evidence cannot support submission."),
        ]
    )
    run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path, invalid=True),
        agent_runner=runner,
    )

    assert runner.contexts[-1].state.best_attempt_id is None


def test_provider_failure_propagates(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)

    def fail(_context: AgentContext) -> AgentCommand:
        raise RuntimeError("provider unavailable")

    with pytest.raises(RuntimeError, match="provider unavailable"):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path),
            agent_runner=fail,
        )
    assert workspace.read_prompt() == "Canonical prompt"


def test_typed_mutation_rejects_unknown_action() -> None:
    with pytest.raises(ValueError):
        MutationInput.model_validate({"type": "shell", "command": "rm -rf /"})


@pytest.mark.parametrize("field_name", ["input_tokens", "output_tokens"])
def test_agent_response_rejects_negative_token_usage(field_name: str) -> None:
    with pytest.raises(ValueError, match="non-negative integers"):
        AgentResponse(
            command=AgentCommand(tool=AgentToolName.ABSTAIN, arguments={"reasoning": "No change."}),
            **{field_name: -1},
        )


def test_pydantic_ai_runner_is_a_provider_boundary() -> None:
    runner = PydanticAIStructuredRunner(object())
    assert callable(runner)


def test_pydantic_ai_test_model_executes_typed_abstention(tmp_path: Path) -> None:
    pytest.importorskip("pydantic_ai")
    from pydantic_ai.models.test import TestModel

    workspace = _workspace(tmp_path / "workspace")
    result = run_agentic_variation(
        _request(workspace),
        workspace,
        "child",
        development_boundary=_boundary(tmp_path),
        agent_runner=PydanticAIStructuredRunner(
            TestModel(
                custom_output_args={
                    "tool": "abstain",
                    "arguments": {"reasoning": "Provider-free typed test abstention."},
                }
            )
        ),
    )

    assert result.status is VariationStatus.ABSTAINED
