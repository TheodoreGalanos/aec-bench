# ABOUTME: Tests cooperative AVO cancellation and durable external-effect reconciliation.
# ABOUTME: Covers pre-effect guards, successful in-flight returns, fail-closed resume, and compaction ordering.

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from aec_bench.evolution.agent_loop import AgentCommand, AgentContext, run_agentic_variation
from aec_bench.evolution.agent_protocol import AgentToolName
from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.cancellation import (
    AVOCancellationCode,
    AVOCancellationError,
    AVOCancellationReason,
    AVOCancellationSignal,
)
from aec_bench.evolution.checkpoint import (
    AVOIncompleteExternalEffectError,
    read_checkpoint,
)
from aec_bench.evolution.core import AVOBudget, VariationStatus
from aec_bench.evolution.development import DevelopmentEvaluationBoundary
from aec_bench.evolution.resume import checkpoint_path
from tests.evolution.test_agent_loop import _boundary, _checkpoint_identity, _command, _request, _workspace


def test_cancel_before_model_writes_prebaseline_terminal_checkpoint(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    signal = AVOCancellationSignal()
    signal.cancel(AVOCancellationReason(AVOCancellationCode.TIMEOUT, "test timeout"))
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")

    with pytest.raises(AVOCancellationError) as raised:
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "boundary"),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
            cancellation_signal=signal,
        )

    assert raised.value.reason.code is AVOCancellationCode.TIMEOUT
    saved = read_checkpoint(path)
    assert saved.parent_evidence is None
    assert saved.terminal_result is not None
    assert saved.terminal_result.status.value == "cancelled"
    assert saved.terminal_result.cancellation_code is AVOCancellationCode.TIMEOUT
    assert not saved.incomplete_external_effects


def test_cancel_before_tool_dispatch_reconciles_provider_return(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    signal = AVOCancellationSignal()
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")

    def runner(_context: AgentContext) -> AgentCommand:
        signal.cancel("stop before mutation")
        return _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "must not apply"})

    with pytest.raises(AVOCancellationError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "boundary"),
            agent_runner=runner,
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
            cancellation_signal=signal,
        )

    saved = read_checkpoint(path)
    assert saved.terminal_result is not None
    assert saved.terminal_result.status.value == "cancelled"
    assert saved.current_snapshot.system_prompt == request.parent.snapshot.system_prompt
    assert not saved.incomplete_external_effects


def test_cancel_after_evaluator_return_reconciles_parent_evidence(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    signal = AVOCancellationSignal()
    delegate = _boundary(tmp_path / "boundary")

    def evaluate(snapshot: object, batch: object):
        result = delegate.evaluator(snapshot, batch)
        signal.cancel("stop after baseline evaluation")
        return result

    boundary = DevelopmentEvaluationBoundary(
        planner=delegate.planner,
        evaluator=evaluate,
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")

    with pytest.raises(AVOCancellationError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=boundary,
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
            cancellation_signal=signal,
        )

    saved = read_checkpoint(path)
    assert saved.parent_evidence is not None
    assert saved.usage.development_evaluations == 1
    assert not saved.incomplete_external_effects


def test_incomplete_provider_effect_fails_closed_on_resume(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    boundary = _boundary(tmp_path / "boundary")

    with pytest.raises(AVOIncompleteExternalEffectError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=boundary,
            agent_runner=lambda _context: (_ for _ in ()).throw(RuntimeError("ambiguous provider")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    saved = read_checkpoint(path)
    assert saved.incomplete_external_effects[0].operation == "model_request"
    with pytest.raises(AVOIncompleteExternalEffectError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "resume-boundary", batch=boundary.batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not retry")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_incomplete_baseline_effect_fails_closed_on_resume(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")

    def fail(_snapshot: object, _batch: object):
        raise RuntimeError("ambiguous evaluator")

    boundary = DevelopmentEvaluationBoundary(
        planner=lambda _size, _cycle: _boundary(tmp_path / "plan").batch,
        evaluator=fail,
        batch_size=1,
        experiment_id="development-experiment",
        host_experiment_id="host-experiment",
    )
    with pytest.raises(AVOIncompleteExternalEffectError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=boundary,
            agent_runner=lambda _context: _command(AgentToolName.ABSTAIN, reasoning="unused"),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )

    saved = read_checkpoint(path)
    assert saved.parent_evidence is None
    assert saved.incomplete_external_effects[0].operation == "development_evaluation"
    with pytest.raises(AVOIncompleteExternalEffectError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=DevelopmentEvaluationBoundary(
                planner=lambda _size, _cycle: boundary.batch,
                evaluator=fail,
                batch_size=1,
                experiment_id="development-experiment",
                host_experiment_id="host-experiment",
            ),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
        )


def test_terminal_cancellation_resume_is_idempotent_and_preserves_reason(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    signal = AVOCancellationSignal()
    signal.cancel(AVOCancellationReason(AVOCancellationCode.TIMEOUT, "deadline reached"))

    with pytest.raises(AVOCancellationError):
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "boundary"),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
            cancellation_signal=signal,
        )

    resumed_signal = AVOCancellationSignal()
    with pytest.raises(AVOCancellationError) as resumed:
        run_agentic_variation(
            request,
            workspace,
            "child",
            development_boundary=_boundary(tmp_path / "resume", batch=_boundary(tmp_path / "boundary").batch),
            agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("terminal model must not run")),
            checkpoint_path=path,
            configuration_identity=_checkpoint_identity(),
            cancellation_signal=resumed_signal,
        )
    assert resumed.value.reason.code is AVOCancellationCode.TIMEOUT


def test_scope_skip_writes_idempotent_prebaseline_abstention_checkpoint(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = replace(_request(workspace), scope=GraduatedScope.SKIP)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    boundary = _boundary(tmp_path / "boundary")

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=boundary,
        agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("skip must not evaluate or call model")),
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
    )
    assert result.status is VariationStatus.ABSTAINED
    saved = read_checkpoint(path)
    assert saved.parent_evidence is None
    assert saved.terminal_result is not None
    assert saved.terminal_result.status is VariationStatus.ABSTAINED

    resumed = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path / "resume-boundary", batch=boundary.batch),
        agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("terminal skip must not call model")),
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
    )
    assert resumed.status is VariationStatus.ABSTAINED


def test_budget_exhaustion_before_parent_evaluation_is_idempotent(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    boundary = _boundary(tmp_path / "boundary")
    clock_values = iter((0.0, 2.0, 2.0))

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=boundary,
        agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("model must not run")),
        budget=AVOBudget(max_elapsed_seconds=1.0),
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
        clock=lambda: next(clock_values),
    )

    assert result.status is VariationStatus.BUDGET_EXHAUSTED
    saved = read_checkpoint(path)
    assert saved.parent_evidence is None
    assert saved.terminal_result is not None
    assert saved.terminal_result.status is VariationStatus.BUDGET_EXHAUSTED

    resumed = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path / "resume-boundary", batch=boundary.batch),
        agent_runner=lambda _context: (_ for _ in ()).throw(AssertionError("terminal model must not run")),
        budget=AVOBudget(max_elapsed_seconds=1.0),
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
    )

    assert resumed == result


def test_compaction_marker_is_reconciled_after_an_existing_attempt(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path / "workspace")
    request = _request(workspace)
    path = checkpoint_path(tmp_path / "state", run_id=request.run_id, variation_id="run-test:variation-1:child-child")
    commands = [
        _command(AgentToolName.APPLY_MUTATION, mutation={"type": "modify_prompt", "content": "revision one"}),
        _command(AgentToolName.EVALUATE_CURRENT_REVISION, hypothesis="Evaluate revision one."),
        _command(
            AgentToolName.APPLY_MUTATION,
            mutation={
                "type": "write_skill",
                "name": "large-skill",
                "description": "A compaction fixture.",
                "body": "engineering data " * 1500,
            },
        ),
        _command(AgentToolName.ABSTAIN, reasoning="No further change."),
    ]

    class Compactor:
        def complete(self, _prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
            del temperature, max_tokens
            return "Compacted engineering data with verification guidance."

    def runner(_context: AgentContext) -> AgentCommand:
        return commands.pop(0)

    result = run_agentic_variation(
        request,
        workspace,
        "child",
        development_boundary=_boundary(tmp_path / "boundary"),
        agent_runner=runner,
        compaction_llm=Compactor(),
        checkpoint_path=path,
        configuration_identity=_checkpoint_identity(),
    )
    assert result.status.value == "abstained"
    saved = read_checkpoint(path)
    assert saved.current_revision == 2
    assert len(saved.evaluated_attempts) == 1
    assert not saved.incomplete_external_effects
