# ABOUTME: Runs one bounded, typed agentic variation loop in an isolated workspace.
# ABOUTME: Keeps development evidence and scratch revisions separate from host-owned search effects.

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    MutationSummary,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.agent_protocol import (
    AgentCommand,
    AgentContext,
    AgentResponse,
    AgentRunner,
    AgentToolName,
    ApprovedKnowledgeSource,
    MutationInput,
    PydanticAIStructuredRunner,
)
from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.cancellation import (
    AVOCancellationCode,
    AVOCancellationError,
    AVOCancellationReason,
    AVOCancellationSignal,
)
from aec_bench.evolution.checkpoint import (
    AVOCheckpoint,
    AVOConfigurationIdentity,
    AVOExternalEffectOperation,
    AVOIncompleteExternalEffect,
    AVOIncompleteExternalEffectError,
)
from aec_bench.evolution.core import (
    AVOBudget,
    AVOState,
    DevelopmentAttempt,
    EvaluatedCandidate,
    VariationRequest,
    VariationResult,
    VariationStatus,
    is_revision_valid,
)
from aec_bench.evolution.development import DevelopmentEvaluationBoundary
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.memory import AVOMemoryEntry, AVOMemoryOutcome, retain_memory
from aec_bench.evolution.mutation import MutationAction, apply_mutations
from aec_bench.evolution.resume import (
    evaluation_batch_identity,
    load_checkpoint_for_resume,
    request_configuration_identity,
    terminal_result_from_checkpoint,
)
from aec_bench.evolution.sanitiser import CompactionLLM, sanitise_workspace
from aec_bench.evolution.workspace import Workspace, scratch_workspace_from

_TOOL_NAMES = (
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
_SCOPE_ACTION_LIMITS = {
    GraduatedScope.SKIP: 0,
    GraduatedScope.MINIMAL: 1,
    GraduatedScope.TARGETED: 3,
    GraduatedScope.COMPREHENSIVE: 5,
}


class AgentToolBudgetExceeded(RuntimeError):
    """Internal signal that a guarded tool cannot start within the budget."""

    def __init__(self, limit: str) -> None:
        super().__init__(f"budget exhausted before tool effect: {limit}")
        self.limit = limit


@dataclass(frozen=True)
class MutationToolResult:
    """Result from applying one or more typed mutations to scratch."""

    success: bool
    revision: int
    mutation: MutationSummary | None = None
    message: str = ""


@dataclass(frozen=True)
class EvaluationToolResult:
    """Result from evaluating the current scratch revision."""

    success: bool
    revision: int
    attempt: DevelopmentAttempt | None = None
    message: str = ""


@dataclass(frozen=True)
class RestoreToolResult:
    """Result from restoring exact material from a development attempt."""

    success: bool
    revision: int
    snapshot: WorkspaceSnapshot | None = None
    message: str = ""


@dataclass(frozen=True)
class SubmissionToolResult:
    """Result from explicitly selecting the current eligible revision."""

    success: bool
    revision: int
    attempt: DevelopmentAttempt | None = None
    message: str = ""


@dataclass(frozen=True)
class AbstentionToolResult:
    """Result from an explicit agent abstention."""

    terminal: bool
    message: str


def run_agentic_variation(
    request: VariationRequest,
    source: Workspace,
    child_candidate_id: str,
    *,
    development_boundary: DevelopmentEvaluationBoundary,
    agent_runner: AgentRunner,
    budget: AVOBudget | None = None,
    knowledge_source: ApprovedKnowledgeSource | None = None,
    compaction_llm: CompactionLLM | None = None,
    development_evaluation_cost_usd: float | None = None,
    variation_id: str | None = None,
    checkpoint_path: Path | None = None,
    configuration_identity: AVOConfigurationIdentity | None = None,
    cancellation_signal: AVOCancellationSignal | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> VariationResult:
    """Run one bounded, self-directed variation call in isolated scratch.

    ``agent_runner`` is the provider composition seam. It receives an
    ``AgentContext`` and must return one validated ``AgentCommand`` per model
    request. A PydanticAI adapter can be supplied by production composition;
    tests can provide a deterministic callable without a provider.
    """
    if not isinstance(request, VariationRequest):
        raise TypeError("request must be a VariationRequest")
    if not isinstance(source, Workspace):
        raise TypeError("source must be a Workspace")
    if not isinstance(development_boundary, DevelopmentEvaluationBoundary):
        raise TypeError("development_boundary must be a DevelopmentEvaluationBoundary")
    if not callable(agent_runner):
        raise TypeError("agent_runner must be callable")
    if cancellation_signal is None:
        cancellation_signal = AVOCancellationSignal()
    if not isinstance(cancellation_signal, AVOCancellationSignal):
        raise TypeError("cancellation_signal must be an AVOCancellationSignal")
    if budget is None:
        budget = AVOBudget()
    if not isinstance(budget, AVOBudget):
        raise TypeError("budget must be an AVOBudget")
    if development_evaluation_cost_usd is not None and development_evaluation_cost_usd < 0:
        raise ValueError("development_evaluation_cost_usd must be non-negative")
    if checkpoint_path is not None:
        if not isinstance(checkpoint_path, Path):
            raise TypeError("checkpoint_path must be a Path")
        if configuration_identity is None:
            raise ValueError("configuration_identity is required when checkpointing is enabled")
    if variation_id is None:
        variation_id = f"{request.run_id}:variation-{request.cycle}:child-{child_candidate_id}"
    if cancellation_signal.is_set() and checkpoint_path is None:
        # Do not even plan a development batch when cancellation is already
        # known and there is no durable authority to publish.
        cancellation_signal.raise_if_cancelled()
    planned_batch = None
    if checkpoint_path is not None or request.scope is not GraduatedScope.SKIP:
        planned_batch = development_boundary.plan()
    effective_configuration_identity = (
        None
        if configuration_identity is None
        else request_configuration_identity(
            configuration_identity,
            request,
            development_evaluation_cost_usd=development_evaluation_cost_usd,
            development_batch_identity=(None if planned_batch is None else evaluation_batch_identity(planned_batch)),
        )
    )
    resume_checkpoint: AVOCheckpoint | None = None
    if checkpoint_path is not None and checkpoint_path.exists():
        assert planned_batch is not None
        assert effective_configuration_identity is not None
        resume_checkpoint = load_checkpoint_for_resume(
            checkpoint_path,
            run_id=request.run_id,
            variation_id=variation_id,
            parent_snapshot=request.parent.snapshot,
            final_child_candidate_id=child_candidate_id,
            selection=request.selection,
            development_case_ids=planned_batch.evaluation_case_ids,
            budget=budget,
            configuration_identity=effective_configuration_identity,
        )
        if resume_checkpoint.terminal_result is not None:
            if resume_checkpoint.terminal_result.status is VariationStatus.CANCELLED:
                cancellation_signal.cancel(
                    AVOCancellationReason(
                        code=resume_checkpoint.terminal_result.cancellation_code or AVOCancellationCode.REQUESTED,
                        detail=resume_checkpoint.terminal_result.reasoning,
                    )
                )
                cancellation_signal.raise_if_cancelled()
            return terminal_result_from_checkpoint(resume_checkpoint)
    if request.scope is GraduatedScope.SKIP and checkpoint_path is None and not cancellation_signal.is_set():
        return VariationResult(
            status=VariationStatus.ABSTAINED,
            child=None,
            mutation=None,
            reasoning="Variation scope does not permit a mutation.",
            usage=VariationUsage(),
            memory=request.memory,
        )

    with scratch_workspace_from(source, request.parent.snapshot, child_candidate_id) as scratch:
        controller = _LoopController(
            request=request,
            scratch=scratch,
            child_candidate_id=child_candidate_id,
            development_boundary=development_boundary,
            budget=budget,
            knowledge_source=knowledge_source,
            compaction_llm=compaction_llm,
            development_evaluation_cost_usd=development_evaluation_cost_usd,
            variation_id=variation_id,
            clock=clock,
            checkpoint_path=checkpoint_path,
            configuration_identity=effective_configuration_identity,
            resume_checkpoint=resume_checkpoint,
            cancellation_signal=cancellation_signal,
        )
        return controller.run(agent_runner)


class _LoopController:
    """Mutable orchestration shell around immutable AVO state values."""

    def __init__(
        self,
        *,
        request: VariationRequest,
        scratch: Workspace,
        child_candidate_id: str,
        development_boundary: DevelopmentEvaluationBoundary,
        budget: AVOBudget,
        knowledge_source: ApprovedKnowledgeSource | None,
        compaction_llm: CompactionLLM | None,
        development_evaluation_cost_usd: float | None,
        variation_id: str,
        clock: Callable[[], float],
        checkpoint_path: Path | None,
        configuration_identity: AVOConfigurationIdentity | None,
        resume_checkpoint: AVOCheckpoint | None,
        cancellation_signal: AVOCancellationSignal,
    ) -> None:
        self.request = request
        self.scratch = scratch
        self.child_candidate_id = child_candidate_id
        self.development_boundary = development_boundary
        self.budget = budget
        self.knowledge_source = knowledge_source
        self.compaction_llm = compaction_llm
        self.development_evaluation_cost_usd = development_evaluation_cost_usd
        self.clock = clock
        self.started_at = clock()
        self.last_mutation = MutationSummary()
        self.last_hypothesis = ""
        self.previous_tool_result: object | None = None
        self.previous_tool_error: str | None = None
        self.explicit_reasoning = ""
        self._model_cost_known = True
        self._model_cost_total = 0.0
        self.state = AVOState(
            variation_id=variation_id,
            parent_candidate_id=request.parent.snapshot.candidate_id,
            child_candidate_id=child_candidate_id,
            current_revision=0,
            memory=request.memory,
            parent_snapshot=request.parent.snapshot,
        )
        self.parent_evidence: EvaluatedCandidate | None = None
        self.terminal_status: VariationStatus | None = None
        self.terminal_message = ""
        self.cancellation_reason: AVOCancellationReason | None = None
        self.checkpoint_path = checkpoint_path
        self.configuration_identity = configuration_identity
        self.resume_checkpoint = resume_checkpoint
        self.cancellation_signal = cancellation_signal
        self.incomplete_external_effects: tuple[AVOIncompleteExternalEffect, ...] = ()

    def run(self, runner: AgentRunner) -> VariationResult:
        """Evaluate the parent, then run agent requests until one terminal outcome."""
        try:
            if self.request.scope is GraduatedScope.SKIP:
                self._check_cancellation()
                self.terminal_status = VariationStatus.ABSTAINED
                self.terminal_message = "Variation scope does not permit a mutation."
                return self._terminal_result()
            if self.resume_checkpoint is not None:
                self._restore_checkpoint()
            else:
                self._start_new_call()

            if self.terminal_status is not None:
                return self._terminal_result()
            tools = MappingProxyType(self._build_tools())
            while self.terminal_status is None:
                self._refresh_elapsed()
                limit = self._loop_limit_reason()
                if limit is not None:
                    return self._exhausted(limit)
                self._check_cancellation()
                self._ensure_model_request_budget()
                self._increment_usage(model_requests=1)
                assert self.parent_evidence is not None
                context = AgentContext(
                    request=self.request,
                    parent_evidence=self.parent_evidence,
                    state=self.state,
                    tools=tools,
                    previous_tool_result=self.previous_tool_result,
                    previous_tool_error=self.previous_tool_error,
                    cancellation_signal=self.cancellation_signal,
                )
                effect = self._begin_external_effect("model_request", f"model-{self.state.usage.model_requests}")
                try:
                    response = runner(context)
                except Exception as exc:
                    # A provider exception cannot prove whether the request was
                    # accepted. Leave the marker for explicit reconciliation.
                    raise AVOIncompleteExternalEffectError(effect, exc) from exc
                try:
                    command, model_cost = _normalise_response(response)
                    self._record_model_cost(model_cost)
                finally:
                    # The provider returned, so the marker can be cleared only
                    # after its usage has been recorded durably.
                    self._clear_external_effect(effect.effect_id)
                self._check_cancellation()
                if self.terminal_status is not None:
                    break
                try:
                    self._dispatch(command, tools)
                except AgentToolBudgetExceeded as exc:
                    return self._exhausted(exc.limit)
            return self._terminal_result()
        except AVOCancellationError as exc:
            return self._finish_cancellation(exc.reason)

    def _start_new_call(self) -> None:
        """Plan and evaluate the parent before the first checkpoint."""
        self._refresh_elapsed()
        limit = self._loop_limit_reason()
        if limit is not None:
            self.terminal_status = VariationStatus.BUDGET_EXHAUSTED
            self.terminal_message = f"Budget exhausted: {limit}."
            return
        try:
            self.development_boundary.plan()
            self._ensure_effect_budget("max_development_evaluations")
            self._check_cancellation()
            effect = self._begin_external_effect("development_evaluation", "development-parent")
            try:
                self.parent_evidence = self.development_boundary.evaluate(self.request.parent.snapshot, revision=0)
            except Exception as exc:
                raise AVOIncompleteExternalEffectError(effect, exc) from exc
            self._record_development_evaluation()
            self._clear_external_effect(effect.effect_id)
            self._check_cancellation()
        except AgentToolBudgetExceeded as exc:
            self.terminal_status = VariationStatus.BUDGET_EXHAUSTED
            self.terminal_message = f"Budget exhausted: {exc.limit}."
        except Exception:
            raise

    def _restore_checkpoint(self) -> None:
        """Restore explicit state and scratch material from the validated checkpoint."""
        assert self.resume_checkpoint is not None
        checkpoint = self.resume_checkpoint
        self.development_boundary.plan()
        if checkpoint.parent_evidence is None:
            raise AVOIncompleteExternalEffectError()
        self.parent_evidence = checkpoint.parent_evidence.to_evaluated_candidate()
        self.state = checkpoint.to_state()
        self.scratch.apply_snapshot(checkpoint.current_snapshot)
        self.started_at = self.clock() - checkpoint.usage.elapsed_seconds
        saved_model_cost = checkpoint.usage.model_cost_usd
        self._model_cost_known = saved_model_cost is not None or checkpoint.usage.model_requests == 0
        self._model_cost_total = saved_model_cost or 0.0
        current_attempt = next(
            (item for item in self.state.attempts if item.revision == self.state.current_revision),
            None,
        )
        if current_attempt is None:
            self.last_mutation = _mutation_summary_for_material(
                self.request.parent.snapshot,
                checkpoint.current_snapshot,
            )
            self.last_hypothesis = ""
        else:
            self.last_mutation = current_attempt.mutation
            self.last_hypothesis = current_attempt.hypothesis
        self.terminal_status = self.state.terminal_status
        if self.terminal_status is not None:
            self.terminal_message = checkpoint.terminal_result.reasoning if checkpoint.terminal_result else ""

    def _check_cancellation(self) -> None:
        """Raise the typed cancellation signal at an effect boundary."""
        self.cancellation_signal.raise_if_cancelled()

    def _begin_external_effect(
        self,
        operation: AVOExternalEffectOperation,
        effect_id_suffix: str,
    ) -> AVOIncompleteExternalEffect:
        """Durably mark one provider or evaluator call before invoking it."""
        self._check_cancellation()
        effect = AVOIncompleteExternalEffect(
            effect_id=f"{self.state.variation_id}:{effect_id_suffix}",
            operation=operation,
            reason=f"{operation} started; completion is not yet confirmed.",
            observed_at=datetime.now(tz=UTC),
        )
        self.incomplete_external_effects = (*self.incomplete_external_effects, effect)
        self._write_checkpoint()
        return effect

    def _clear_external_effect(self, effect_id: str) -> None:
        """Clear one confirmed external effect and publish the updated state."""
        self.incomplete_external_effects = tuple(
            effect for effect in self.incomplete_external_effects if effect.effect_id != effect_id
        )
        self._write_checkpoint()

    def _begin_compaction_effect(self, skill_name: str) -> None:
        """Mark one compaction request before calling its external LLM."""
        self._begin_external_effect("compaction", f"compaction-{skill_name}")

    def _clear_compaction_effects(self) -> None:
        """Clear all confirmed compactions after workspace reconciliation."""
        for effect in tuple(self.incomplete_external_effects):
            if effect.operation == "compaction":
                self._clear_external_effect(effect.effect_id)

    def _finish_cancellation(self, reason: AVOCancellationReason) -> VariationResult:
        """Publish a truthful cancellation result before propagating it."""
        self.cancellation_reason = reason
        self.terminal_status = VariationStatus.CANCELLED
        self.terminal_message = reason.detail
        self._terminal_result()
        error = AVOCancellationError(reason)
        raise error

    def _write_checkpoint(self, terminal_result: VariationResult | None = None) -> None:
        """Persist the explicit call state when checkpointing is enabled."""
        if self.checkpoint_path is None:
            return
        if self.configuration_identity is None:
            raise RuntimeError("checkpoint requires configuration identity")
        terminal_record = None
        if terminal_result is not None:
            from aec_bench.evolution.checkpoint import AVOCheckpointTerminalResult

            terminal_record = AVOCheckpointTerminalResult.from_result(
                terminal_result,
                cancellation_code=(None if self.cancellation_reason is None else self.cancellation_reason.code),
            )
        from aec_bench.evolution.checkpoint import AVOCheckpoint, write_checkpoint

        checkpoint = AVOCheckpoint.from_state(
            run_id=self.request.run_id,
            state=self.state,
            parent_evidence=self.parent_evidence,
            selection=self.request.selection.to_record(),
            development_case_ids=self.development_boundary.batch.evaluation_case_ids,
            configuration_identity=self.configuration_identity,
            budget=self.budget,
            current_snapshot=self.scratch.export_snapshot(self.child_candidate_id),
            incomplete_external_effects=self.incomplete_external_effects,
            terminal_result=terminal_record,
        )
        write_checkpoint(self.checkpoint_path, checkpoint)

    def _build_tools(self) -> dict[str, Callable[..., object]]:
        """Build the exact guarded tool surface for this loop."""

        def guarded(name: str, function: Callable[..., object]) -> Callable[..., object]:
            def call(*args: object, **kwargs: object) -> object:
                self.previous_tool_result = None
                self.previous_tool_error = None
                try:
                    self._check_cancellation()
                    self._ensure_tool_budget(name)
                    self._increment_usage(tool_calls=1)
                    result = function(*args, **kwargs)
                except AgentToolBudgetExceeded as exc:
                    self.previous_tool_error = str(exc)
                    raise
                except Exception as exc:
                    self.previous_tool_error = f"{type(exc).__name__}: {exc}"
                    raise
                self.previous_tool_result = result
                self.previous_tool_error = None
                return result

            call.__name__ = name
            call.__doc__ = function.__doc__
            return call

        tools: dict[str, Callable[..., object]] = {
            "read_parent_evidence": guarded("read_parent_evidence", self.read_parent_evidence),
            "read_current_workspace": guarded("read_current_workspace", self.read_current_workspace),
            "read_inspiration": guarded("read_inspiration", self.read_inspiration),
            "read_history": guarded("read_history", self.read_history),
            "read_graveyard": guarded("read_graveyard", self.read_graveyard),
            "read_knowledge": guarded("read_knowledge", self.read_knowledge),
            "apply_mutation": guarded("apply_mutation", self.apply_mutation),
            "evaluate_current_revision": guarded("evaluate_current_revision", self.evaluate_current_revision),
            "restore_attempt": guarded("restore_attempt", self.restore_attempt),
            "submit_current_revision": guarded("submit_current_revision", self.submit_current_revision),
            "abstain": guarded("abstain", self.abstain),
        }
        if tuple(tools) != _TOOL_NAMES:
            raise AssertionError("agent tool surface does not match the approved AVO contract")
        return tools

    def read_parent_evidence(self) -> EvaluatedCandidate:
        """Return the exact host-selected parent evidence supplied to AVO."""
        return self.request.parent

    def read_current_workspace(self) -> WorkspaceSnapshot:
        """Return the current scratch material, never the canonical workspace."""
        return self.scratch.export_snapshot(self.child_candidate_id)

    def read_inspiration(self) -> tuple[WorkspaceSnapshot, ...]:
        """Return only host-authorised inspiration snapshots."""
        return self.request.inspirations

    def read_history(self) -> tuple[EvolutionCycleRecord, ...]:
        """Return approved evolution history without a write capability."""
        return self.request.history

    def read_graveyard(self) -> tuple[GraveyardEntry, ...]:
        """Return approved failed-attempt summaries without graveyard mutation."""
        return self.request.graveyard

    def read_knowledge(self) -> str:
        """Read the approved knowledge source supplied by composition."""
        if self.knowledge_source is None:
            return "No approved knowledge source is available."
        return self.knowledge_source() if callable(self.knowledge_source) else self.knowledge_source

    def apply_mutation(
        self,
        mutation: MutationInput | MutationAction | Mapping[str, Any] | Sequence[MutationInput],
    ) -> MutationToolResult:
        """Apply validated prompt or skill edits to scratch and invalidate evidence."""
        mutations = _normalise_mutations(mutation)
        action_count = len(mutations)
        scope_limit = _SCOPE_ACTION_LIMITS[self.request.scope]
        if action_count > scope_limit:
            return MutationToolResult(
                success=False,
                revision=self.state.current_revision,
                message=f"mutation scope exceeded ({scope_limit} actions permitted)",
            )
        before = self.scratch.export_snapshot(self.child_candidate_id)
        previous_revision = self.state.current_revision
        try:
            apply_mutations([item.to_action() for item in mutations], self.scratch)
            raw_after = self.scratch.export_snapshot(self.child_candidate_id)
            if _same_material(before, raw_after):
                return MutationToolResult(
                    success=False,
                    revision=self.state.current_revision,
                    mutation=None,
                    message="mutation made no effective workspace change",
                )
            revisions = [self.state.current_revision, *(attempt.revision for attempt in self.state.attempts)]
            self.state = replace(self.state, current_revision=max(revisions) + 1)
            sanitise_workspace(
                self.scratch,
                compaction_llm=self.compaction_llm,
                before_compaction=self._begin_compaction_effect,
            )
        except Exception as exc:
            self.scratch.apply_snapshot(before)
            self.state = replace(self.state, current_revision=previous_revision)
            compaction_effect = next(
                (effect for effect in reversed(self.incomplete_external_effects) if effect.operation == "compaction"),
                None,
            )
            if compaction_effect is not None:
                self._write_checkpoint()
                if isinstance(exc, AVOIncompleteExternalEffectError):
                    raise
                raise AVOIncompleteExternalEffectError(compaction_effect, exc) from exc
            raise
        after = self.scratch.export_snapshot(self.child_candidate_id)
        if _same_material(before, after):
            self.scratch.apply_snapshot(before)
            self.state = replace(self.state, current_revision=previous_revision)
            self._clear_compaction_effects()
            return MutationToolResult(
                success=False,
                revision=self.state.current_revision,
                mutation=None,
                message="sanitisation removed the proposed workspace change",
            )
        if _material_change_count(self.request.parent.snapshot, after) > scope_limit:
            self.scratch.apply_snapshot(before)
            self.state = replace(self.state, current_revision=previous_revision)
            self._clear_compaction_effects()
            return MutationToolResult(
                success=False,
                revision=self.state.current_revision,
                mutation=None,
                message=f"mutation scope exceeded ({scope_limit} material changes permitted)",
            )
        cumulative_mutation = _mutation_summary_for_material(self.request.parent.snapshot, after)
        self.last_mutation = cumulative_mutation
        self.last_hypothesis = ""
        self._clear_compaction_effects()
        self._write_checkpoint()
        self._check_cancellation()
        return MutationToolResult(
            success=True,
            revision=self.state.current_revision,
            mutation=cumulative_mutation,
            message="mutation applied to scratch",
        )

    def evaluate_current_revision(self, hypothesis: str) -> EvaluationToolResult:
        """Evaluate exact current scratch material on the fixed development batch."""
        self._check_cancellation()
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            return EvaluationToolResult(
                success=False,
                revision=self.state.current_revision,
                message="hypothesis must not be blank",
            )
        snapshot = self.scratch.export_snapshot(self.child_candidate_id)
        if _same_material(snapshot, self.request.parent.snapshot):
            return EvaluationToolResult(
                success=False,
                revision=self.state.current_revision,
                message="unchanged parent material cannot be evaluated as a child",
            )
        if self.state.current_revision == 0:
            return EvaluationToolResult(
                success=False,
                revision=0,
                message="apply an effective mutation before evaluating a child revision",
            )
        if any(attempt.revision == self.state.current_revision for attempt in self.state.attempts):
            return EvaluationToolResult(
                success=False,
                revision=self.state.current_revision,
                message="current revision was already evaluated; restore or apply a new mutation",
            )
        self._ensure_effect_budget("max_development_evaluations")
        self._increment_usage(development_evaluations=1)
        self.last_hypothesis = hypothesis.strip()
        evaluated_snapshot = snapshot.model_copy(
            update={"candidate_id": f"{self.child_candidate_id}:revision-{self.state.current_revision}"}
        )
        effect = self._begin_external_effect(
            "development_evaluation",
            f"development-revision-{self.state.current_revision}",
        )
        try:
            attempt = self.development_boundary.evaluate_revision(
                evaluated_snapshot,
                attempt_id=f"{self.state.variation_id}:attempt-{self.state.current_revision}",
                revision=self.state.current_revision,
                mutation=self.last_mutation,
                hypothesis=self.last_hypothesis,
                usage_after=self.state.usage,
            )
        except Exception as exc:
            raise AVOIncompleteExternalEffectError(effect, exc) from exc
        self._refresh_elapsed()
        attempt = replace(attempt, usage_after=self.state.usage)
        attempts = (*self.state.attempts, attempt)
        best_attempt_id = self.state.best_attempt_id
        previous_best = self._best_score()
        improved = attempt.evaluated.assessment.valid and attempt.evaluated.assessment.batch_score > previous_best
        if improved:
            best_attempt_id = attempt.attempt_id
        self.state = replace(
            self.state,
            attempts=attempts,
            best_attempt_id=best_attempt_id,
            consecutive_without_progress=0 if improved else self.state.consecutive_without_progress + 1,
            consecutive_evaluation_errors=0,
        )
        self._remember(_memory_entry_for_attempt(self.state.variation_id, attempt, improved=improved))
        self._clear_external_effect(effect.effect_id)
        self._check_cancellation()
        return EvaluationToolResult(
            success=True,
            revision=self.state.current_revision,
            attempt=attempt,
            message="current revision evaluated",
        )

    def restore_attempt(self, attempt_id: str | None = None, revision: int | None = None) -> RestoreToolResult:
        """Restore exact material from one persisted evaluated attempt."""
        self._check_cancellation()
        if attempt_id is None and revision is None:
            return RestoreToolResult(False, self.state.current_revision, message="attempt_id or revision is required")
        attempt = next(
            (
                item
                for item in self.state.attempts
                if (attempt_id is not None and item.attempt_id == attempt_id)
                or (revision is not None and item.revision == revision)
            ),
            None,
        )
        if attempt is None:
            return RestoreToolResult(False, self.state.current_revision, message="development attempt not found")
        self.scratch.apply_snapshot(attempt.evaluated.snapshot)
        self.state = replace(
            self.state,
            current_revision=attempt.revision,
            consecutive_evaluation_errors=0,
        )
        self.last_mutation = attempt.mutation
        self.last_hypothesis = attempt.hypothesis
        self._write_checkpoint()
        self._check_cancellation()
        return RestoreToolResult(
            success=True,
            revision=attempt.revision,
            snapshot=self.scratch.export_snapshot(self.child_candidate_id),
            message="exact evaluated attempt material restored",
        )

    def submit_current_revision(
        self,
        reasoning: str = "Submitted the current evaluated revision.",
    ) -> SubmissionToolResult:
        """Select one current, evaluated, changed revision for host submission."""
        self._check_cancellation()
        if not isinstance(reasoning, str) or not reasoning.strip():
            return SubmissionToolResult(False, self.state.current_revision, message="reasoning must not be blank")
        snapshot = self.scratch.export_snapshot(self.child_candidate_id)
        if not is_revision_valid(self.state, self.state.current_revision, snapshot):
            return SubmissionToolResult(
                False,
                self.state.current_revision,
                message="current revision has no eligible exact development evidence",
            )
        attempt = next(item for item in self.state.attempts if item.revision == self.state.current_revision)
        self.explicit_reasoning = reasoning.strip()
        self.terminal_status = VariationStatus.SUBMITTED
        self.terminal_message = self.explicit_reasoning
        return SubmissionToolResult(True, self.state.current_revision, attempt, self.explicit_reasoning)

    def abstain(self, reasoning: str) -> AbstentionToolResult:
        """Explicitly abstain without returning scratch material."""
        if not isinstance(reasoning, str) or not reasoning.strip():
            return AbstentionToolResult(False, "reasoning must not be blank")
        self.explicit_reasoning = reasoning.strip()
        self.terminal_status = VariationStatus.ABSTAINED
        self.terminal_message = self.explicit_reasoning
        return AbstentionToolResult(True, self.explicit_reasoning)

    def _dispatch(self, command: AgentCommand, tools: Mapping[str, Callable[..., object]]) -> None:
        function = tools[command.tool.value]
        try:
            function(**command.arguments)
        except AgentToolBudgetExceeded:
            raise
        except (KeyError, TypeError, ValueError):
            # Typed argument errors are returned to the next model request.
            # Provider and evaluation failures use their own propagation rules.
            return

    def _best_score(self) -> float:
        if self.state.best_attempt_id is None:
            return self.parent_evidence.assessment.batch_score if self.parent_evidence is not None else float("-inf")
        attempt = next(item for item in self.state.attempts if item.attempt_id == self.state.best_attempt_id)
        return attempt.evaluated.assessment.batch_score

    def _record_development_evaluation(self) -> None:
        self._increment_usage(development_evaluations=1)

    def _remember(self, entry: AVOMemoryEntry) -> None:
        """Replace one attempt fact and retain the bounded structured memory."""
        existing = tuple(
            item
            for item in self.state.memory
            if (item.source_variation_id, item.source_attempt_id)
            != (entry.source_variation_id, entry.source_attempt_id)
        )
        self.state = replace(
            self.state,
            memory=retain_memory(
                (*existing, entry),
                best_attempt_id=self.state.best_attempt_id,
            ),
        )

    def _record_model_cost(self, cost: float | None) -> None:
        if cost is None:
            self._model_cost_known = False
            self._set_usage(model_cost_usd=None)
            return
        if self._model_cost_known:
            self._model_cost_total += cost
            self._set_usage(model_cost_usd=self._model_cost_total)

    def _set_usage(self, **updates: int | float | None) -> None:
        usage = self.state.usage
        self.state = replace(
            self.state,
            usage=VariationUsage(
                model_requests=_as_int(updates.get("model_requests"), usage.model_requests),
                tool_calls=_as_int(updates.get("tool_calls"), usage.tool_calls),
                development_evaluations=_as_int(updates.get("development_evaluations"), usage.development_evaluations),
                supervisor_interventions=usage.supervisor_interventions,
                model_cost_usd=updates.get("model_cost_usd", usage.model_cost_usd),
                development_evaluation_cost_usd=updates.get(
                    "development_evaluation_cost_usd", usage.development_evaluation_cost_usd
                ),
                elapsed_seconds=_as_float(updates.get("elapsed_seconds"), usage.elapsed_seconds),
            ),
        )

    def _increment_usage(self, **increments: int) -> None:
        usage = self.state.usage
        self._set_usage(
            model_requests=usage.model_requests + increments.get("model_requests", 0),
            tool_calls=usage.tool_calls + increments.get("tool_calls", 0),
            development_evaluations=usage.development_evaluations + increments.get("development_evaluations", 0),
            development_evaluation_cost_usd=(
                None
                if self.development_evaluation_cost_usd is None
                else (
                    self.development_evaluation_cost_usd
                    * (usage.development_evaluations + increments.get("development_evaluations", 0))
                )
            ),
        )

    def _refresh_elapsed(self) -> None:
        elapsed = max(0.0, self.clock() - self.started_at)
        self._set_usage(elapsed_seconds=elapsed)

    def _ensure_model_request_budget(self) -> None:
        self._refresh_elapsed()
        usage = self.state.usage
        checks = (
            ("max_model_requests", usage.model_requests, self.budget.max_model_requests),
            ("max_elapsed_seconds", usage.elapsed_seconds, self.budget.max_elapsed_seconds),
        )
        for name, observed, limit in checks:
            if observed >= limit:
                raise AgentToolBudgetExceeded(name)

    def _ensure_tool_budget(self, _tool_name: str) -> None:
        self._refresh_elapsed()
        usage = self.state.usage
        if usage.tool_calls >= self.budget.max_tool_calls:
            raise AgentToolBudgetExceeded("max_tool_calls")
        if usage.elapsed_seconds >= self.budget.max_elapsed_seconds:
            raise AgentToolBudgetExceeded("max_elapsed_seconds")
        limit = self._known_cost_limit()
        if limit is not None:
            raise AgentToolBudgetExceeded(limit)

    def _ensure_effect_budget(self, name: str) -> None:
        self._refresh_elapsed()
        usage = self.state.usage
        if (
            name == "max_development_evaluations"
            and usage.development_evaluations >= self.budget.max_development_evaluations
        ):
            raise AgentToolBudgetExceeded(name)
        if self.state.consecutive_evaluation_errors >= self.budget.max_consecutive_evaluation_errors:
            raise AgentToolBudgetExceeded("max_consecutive_evaluation_errors")
        if self.state.consecutive_without_progress >= self.budget.max_stagnant_evaluations:
            raise AgentToolBudgetExceeded("max_stagnant_evaluations")
        limit = self._loop_limit_reason()
        if limit is not None:
            raise AgentToolBudgetExceeded(limit)

    def _loop_limit_reason(self) -> str | None:
        """Return limits that stop the next model request or tool effect."""
        usage = self.state.usage
        if usage.model_requests >= self.budget.max_model_requests:
            return "max_model_requests"
        if usage.tool_calls >= self.budget.max_tool_calls:
            return "max_tool_calls"
        if usage.elapsed_seconds >= self.budget.max_elapsed_seconds:
            return "max_elapsed_seconds"
        return self._known_cost_limit()

    def _known_cost_limit(self) -> str | None:
        if self.budget.max_cost_usd is None:
            return None
        total_cost = self.state.usage.total_cost_usd
        if total_cost is None:
            return "max_cost_usd_unknown"
        if total_cost >= self.budget.max_cost_usd:
            return "max_cost_usd"
        return None

    def _exhausted(self, limit: str) -> VariationResult:
        self.terminal_status = VariationStatus.BUDGET_EXHAUSTED
        self.terminal_message = f"Budget exhausted: {limit}."
        return self._terminal_result()

    def _terminal_result(self) -> VariationResult:
        if self.terminal_status is not VariationStatus.CANCELLED:
            self._check_cancellation()
        self._refresh_elapsed()
        self.state = replace(self.state, terminal_status=self.terminal_status or VariationStatus.BUDGET_EXHAUSTED)
        usage = self.state.usage
        if self.terminal_status is VariationStatus.SUBMITTED:
            snapshot = self.scratch.export_snapshot(self.child_candidate_id)
            attempt = next(item for item in self.state.attempts if item.revision == self.state.current_revision)
            result = VariationResult(
                status=VariationStatus.SUBMITTED,
                child=snapshot,
                mutation=attempt.mutation,
                reasoning=self.terminal_message,
                usage=usage,
                attempt=attempt,
                memory=self.state.memory,
            )
        else:
            result = VariationResult(
                status=self.terminal_status or VariationStatus.BUDGET_EXHAUSTED,
                child=None,
                mutation=None,
                reasoning=self.terminal_message or "Variation ended without a submitted child.",
                usage=usage,
                memory=self.state.memory,
            )
        self._write_checkpoint(result)
        return result


def _normalise_response(response: AgentCommand | AgentResponse) -> tuple[AgentCommand, float | None]:
    if isinstance(response, AgentResponse):
        return response.command, response.model_cost_usd
    if isinstance(response, AgentCommand):
        return response, None
    raise TypeError("agent runner must return AgentCommand or AgentResponse")


def _normalise_mutations(
    mutation: MutationInput | MutationAction | Mapping[str, Any] | Sequence[MutationInput],
) -> tuple[MutationInput, ...]:
    if isinstance(mutation, MutationInput):
        return (mutation,)
    if isinstance(mutation, MutationAction):
        return (MutationInput.model_validate(_mutation_action_dict(mutation)),)
    if isinstance(mutation, Mapping):
        return (MutationInput.model_validate(mutation),)
    values = tuple(mutation)
    if not values:
        raise ValueError("at least one mutation is required")
    if any(not isinstance(value, MutationInput) for value in values):
        raise TypeError("mutation sequences must contain MutationInput values")
    return values


def _mutation_action_dict(action: MutationAction) -> dict[str, Any]:
    return {
        "type": action.action_type,
        "name": action.skill_name,
        "description": action.skill_description,
        "discipline": action.skill_discipline,
        "body": action.skill_body,
        "content": action.prompt_content,
    }


def _same_material(left: WorkspaceSnapshot, right: WorkspaceSnapshot) -> bool:
    return left.system_prompt == right.system_prompt and left.skills == right.skills


def _material_change_count(parent: WorkspaceSnapshot, current: WorkspaceSnapshot) -> int:
    """Count distinct prompt and skill changes in the current material."""
    changes = int(parent.system_prompt != current.system_prompt)
    parent_skills = {skill.name: skill for skill in parent.skills}
    current_skills = {skill.name: skill for skill in current.skills}
    changes += sum(
        1
        for name in parent_skills.keys() | current_skills.keys()
        if parent_skills.get(name) != current_skills.get(name)
    )
    return changes


def _mutation_summary_for_material(parent: WorkspaceSnapshot, current: WorkspaceSnapshot) -> MutationSummary:
    """Describe the exact cumulative material difference from the parent."""
    parent_skills = {skill.name: skill for skill in parent.skills}
    current_skills = {skill.name: skill for skill in current.skills}
    return MutationSummary(
        prompt_modified=parent.system_prompt != current.system_prompt,
        skills_added=sorted(current_skills.keys() - parent_skills.keys()),
        skills_modified=sorted(
            name for name in parent_skills.keys() & current_skills.keys() if parent_skills[name] != current_skills[name]
        ),
        skills_removed=sorted(parent_skills.keys() - current_skills.keys()),
    )


def _change_summary(mutation: MutationSummary) -> str:
    """Summarise mutation material without retaining model or tool text."""
    changes: list[str] = []
    if mutation.prompt_modified:
        changes.append("system prompt modified")
    if mutation.skills_added:
        changes.append(f"skills added: {', '.join(mutation.skills_added)}")
    if mutation.skills_modified:
        changes.append(f"skills modified: {', '.join(mutation.skills_modified)}")
    if mutation.skills_removed:
        changes.append(f"skills removed: {', '.join(mutation.skills_removed)}")
    return "; ".join(changes) if changes else "no workspace material change"


def _evidence_summary(attempt: DevelopmentAttempt) -> str:
    """Summarise only the explicit assessment values for structured memory."""
    assessment = attempt.evaluated.assessment
    return (
        f"valid={assessment.valid}; batch_score={assessment.batch_score:.6g}; "
        f"evaluation_cases={len(assessment.evaluation_case_ids)}; trials={len(assessment.trial_ids)}"
    )


def _memory_entry_for_attempt(
    variation_id: str,
    attempt: DevelopmentAttempt,
    *,
    improved: bool,
) -> AVOMemoryEntry:
    """Build a deterministic fact from one completed development evaluation."""
    assessment = attempt.evaluated.assessment
    if not assessment.valid:
        outcome = AVOMemoryOutcome.INVALID
        failure_category = "invalid_candidate"
        next_direction = "Correct the invalid result before another evaluation."
    elif improved:
        outcome = AVOMemoryOutcome.IMPROVED
        failure_category = None
        next_direction = "Preserve the successful change and test one bounded follow-up."
    else:
        outcome = AVOMemoryOutcome.NOT_IMPROVED
        failure_category = "no_improvement"
        next_direction = "Try a different bounded change direction."
    return AVOMemoryEntry(
        source_variation_id=variation_id,
        source_attempt_id=attempt.attempt_id,
        hypothesis=attempt.hypothesis,
        change_summary=_change_summary(attempt.mutation),
        evidence_summary=_evidence_summary(attempt),
        outcome=outcome,
        failure_category=failure_category,
        next_direction=next_direction,
    )


def _memory_entry_for_evaluation_error(
    *,
    variation_id: str,
    attempt_id: str,
    hypothesis: str,
    mutation: MutationSummary,
) -> AVOMemoryEntry:
    """Build a coarse fact for an evaluator exception without its text."""
    return AVOMemoryEntry(
        source_variation_id=variation_id,
        source_attempt_id=attempt_id,
        hypothesis=hypothesis or "Evaluation hypothesis was not recorded.",
        change_summary=_change_summary(mutation),
        evidence_summary="development evaluation did not produce evidence",
        outcome=AVOMemoryOutcome.EVALUATION_ERROR,
        failure_category="evaluation_error",
        next_direction="Retry the same bounded change only after the evaluator is available.",
    )


def _as_int(value: int | float | None, default: int) -> int:
    return default if value is None else int(value)


def _as_float(value: int | float | None, default: float) -> float:
    return default if value is None else float(value)


__all__ = (
    "AbstentionToolResult",
    "AgentCommand",
    "AgentContext",
    "AgentResponse",
    "AgentRunner",
    "AgentToolName",
    "ApprovedKnowledgeSource",
    "EvaluationToolResult",
    "MutationInput",
    "MutationToolResult",
    "PydanticAIStructuredRunner",
    "RestoreToolResult",
    "SubmissionToolResult",
    "run_agentic_variation",
)
