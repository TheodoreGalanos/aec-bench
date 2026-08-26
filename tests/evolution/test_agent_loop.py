# ABOUTME: Tests the bounded typed agentic variation loop and its scratch tools.
# ABOUTME: Covers fixed parent-first evaluation, limits, evidence identity, and terminal outcomes.

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import (
    CandidateAssessment,
    EvolutionObservation,
    FieldScore,
    MutationStrategy,
    ObservationEnrichment,
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
from aec_bench.evolution.analysis import BehavioralPattern, EvolutionAnalysis, GraduatedScope
from aec_bench.evolution.core import AVOBudget, EvaluatedCandidate, SelectionPlan, VariationRequest, VariationStatus
from aec_bench.evolution.development import DevelopmentEvaluationBoundary
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
    )


def _boundary(tmp_path: Path, *, invalid: bool = False) -> DevelopmentEvaluationBoundary:
    batch = _batch(tmp_path / "batch")
    counter = 0

    def evaluate(_snapshot: object, _batch_value: object):
        nonlocal counter
        counter += 1
        record = _record(trial_id=f"development-trial-{counter}")
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
        planner=lambda _size, _cycle: batch,
        evaluator=evaluate,
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
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
