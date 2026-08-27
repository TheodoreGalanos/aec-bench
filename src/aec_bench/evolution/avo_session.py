# ABOUTME: Orchestrates one bounded AVO session in an isolated scratch workspace.
# ABOUTME: Owns effects, budgets, checkpoints, advice, and terminal proposal selection.

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    MutationSummary,
    ProposalUsage,
    WorkspaceSnapshot,
)
from aec_bench.evolution.advice import (
    AVOAdvice,
    AVOAdviceRecord,
    AVOAdviceRequest,
    AVOAdviceResult,
    AVOAdvisorRunner,
    advice_trigger,
    complete_advisor_usage,
    remaining_avo_budget,
    reserve_advisor_budget,
)
from aec_bench.evolution.agent_protocol import (
    ApprovedKnowledgeSource,
    AVOCommand,
    AVOContext,
    AVORunner,
    MutationInput,
)
from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.avo_tools import (
    AVOToolBudgetExceeded,
    CandidateAbstentionResult,
    CandidateCheckResult,
    CandidateEditResult,
    CandidateRestoreResult,
    CandidateSubmissionResult,
    _as_float,
    _as_int,
    _as_optional_int,
    _material_change_count,
    _memory_entry_for_attempt,
    _mutation_summary_for_material,
    _normalise_mutations,
    _normalise_response,
    _same_material,
)
from aec_bench.evolution.cancellation import (
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
    CandidateProposal,
    CandidateProposalRequest,
    EvaluatedCandidate,
    ProposalStatus,
    is_revision_valid,
)
from aec_bench.evolution.graveyard import GraveyardEntry
from aec_bench.evolution.memory import AVOMemoryEntry, retain_memory
from aec_bench.evolution.mutation import MutationAction, apply_mutations
from aec_bench.evolution.revision import RevisionEvaluation
from aec_bench.evolution.sanitiser import CompactionLLM, sanitise_workspace
from aec_bench.evolution.workspace import Workspace

_TOOL_NAMES = (
    "inspect_parent_results",
    "inspect_current_candidate",
    "inspect_inspirations",
    "inspect_previous_cycles",
    "inspect_rejected_candidates",
    "read_program_guidance",
    "edit_candidate",
    "test_candidate",
    "restore_candidate",
    "submit_candidate",
    "abstain",
)
_SCOPE_ACTION_LIMITS = {
    GraduatedScope.SKIP: 0,
    GraduatedScope.MINIMAL: 1,
    GraduatedScope.TARGETED: 3,
    GraduatedScope.COMPREHENSIVE: 5,
}


class AVOSession:
    """Mutable orchestration shell around immutable AVO state values."""

    def __init__(
        self,
        *,
        request: CandidateProposalRequest,
        scratch: Workspace,
        child_candidate_id: str,
        revision_evaluation: RevisionEvaluation,
        budget: AVOBudget,
        knowledge_source: ApprovedKnowledgeSource | None,
        compaction_llm: CompactionLLM | None,
        development_evaluation_cost_usd: float | None,
        variation_id: str,
        clock: Callable[[], float],
        avo_checkpoint_path: Path | None,
        configuration_identity: AVOConfigurationIdentity | None,
        resume_checkpoint: AVOCheckpoint | None,
        cancellation_signal: AVOCancellationSignal,
        advisor_runner: AVOAdvisorRunner | None,
    ) -> None:
        self.request = request
        self.scratch = scratch
        self.child_candidate_id = child_candidate_id
        self.revision_evaluation = revision_evaluation
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
        self.terminal_status: ProposalStatus | None = None
        self.terminal_message = ""
        self.cancellation_reason: AVOCancellationReason | None = None
        self.avo_checkpoint_path = avo_checkpoint_path
        self.configuration_identity = configuration_identity
        self.resume_checkpoint = resume_checkpoint
        self.cancellation_signal = cancellation_signal
        self.advisor_runner = advisor_runner
        self.incomplete_external_effects: tuple[AVOIncompleteExternalEffect, ...] = ()

    def run(self, runner: AVORunner) -> CandidateProposal:
        """Evaluate the parent, then run agent requests until one terminal outcome."""
        try:
            if self.request.scope is GraduatedScope.SKIP:
                self._check_cancellation()
                self.terminal_status = ProposalStatus.ABSTAINED
                self.terminal_message = "Proposal scope does not permit a mutation."
                return self._terminal_result()
            if self.resume_checkpoint is not None:
                self._restore_checkpoint()
                if self.terminal_status is None:
                    try:
                        # A crash can occur after a deterministic trigger was
                        # checkpointed but before the normal post-command
                        # advice turn. Resolve that trigger first so the
                        # next main-agent context contains the outcome.
                        self._maybe_get_advice()
                    except AVOToolBudgetExceeded as exc:
                        return self._exhausted(exc.limit)
            else:
                self._start_new_call()

            if self.terminal_status is not None:
                return self._terminal_result()
            while self.terminal_status is None:
                tools = MappingProxyType(self._build_tools())
                self._refresh_elapsed()
                limit = self._loop_limit_reason()
                if limit is not None:
                    return self._exhausted(limit)
                self._check_cancellation()
                self._ensure_model_request_budget()
                self._increment_usage(model_requests=1)
                assert self.parent_evidence is not None
                context = AVOContext(
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
                    command, model_cost, input_tokens, output_tokens = _normalise_response(response)
                    self._record_model_cost(model_cost)
                    self._record_model_tokens(input_tokens, output_tokens)
                finally:
                    # The provider returned, so the marker can be cleared only
                    # after its usage has been recorded durably.
                    self._clear_external_effect(effect.effect_id)
                self._check_cancellation()
                if self.terminal_status is not None:
                    break
                try:
                    self._dispatch(command, tools)
                except AVOToolBudgetExceeded as exc:
                    return self._exhausted(exc.limit)
                if self.terminal_status is None:
                    try:
                        self._maybe_get_advice()
                    except AVOToolBudgetExceeded as exc:
                        return self._exhausted(exc.limit)
            return self._terminal_result()
        except AVOCancellationError as exc:
            return self._finish_cancellation(exc.reason)

    def _start_new_call(self) -> None:
        """Plan and evaluate the parent before the first checkpoint."""
        self._refresh_elapsed()
        limit = self._loop_limit_reason()
        if limit is not None:
            self.terminal_status = ProposalStatus.BUDGET_EXHAUSTED
            self.terminal_message = f"Budget exhausted: {limit}."
            return
        try:
            self.revision_evaluation.plan()
            self._ensure_effect_budget("max_development_evaluations")
            self._check_cancellation()
            effect = self._begin_external_effect("development_evaluation", "development-parent")
            try:
                self.parent_evidence = self.revision_evaluation.evaluate(self.request.parent.snapshot, revision=0)
            except Exception as exc:
                raise AVOIncompleteExternalEffectError(effect, exc) from exc
            self._record_development_evaluation()
            self._clear_external_effect(effect.effect_id)
            self._check_cancellation()
        except AVOToolBudgetExceeded as exc:
            self.terminal_status = ProposalStatus.BUDGET_EXHAUSTED
            self.terminal_message = f"Budget exhausted: {exc.limit}."
        except Exception:
            raise

    def _restore_checkpoint(self) -> None:
        """Restore explicit state and scratch material from the validated checkpoint."""
        assert self.resume_checkpoint is not None
        checkpoint = self.resume_checkpoint
        self.revision_evaluation.plan()
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
        *,
        check_cancellation: bool = True,
    ) -> AVOIncompleteExternalEffect:
        """Durably mark one provider or evaluator call before invoking it."""
        if check_cancellation:
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

    def _finish_cancellation(self, reason: AVOCancellationReason) -> CandidateProposal:
        """Publish a truthful cancellation result before propagating it."""
        # A pending advice request is a trigger, not a terminal outcome. Clear
        # it before publishing cancellation so the terminal checkpoint is a
        # valid consumed state even when cancellation wins before advice.
        self.state = replace(self.state, exhausted_direction_requested=False)
        self.cancellation_reason = reason
        self.terminal_status = ProposalStatus.CANCELLED
        self.terminal_message = reason.detail
        self._terminal_result()
        error = AVOCancellationError(reason)
        raise error

    def _write_checkpoint(self, terminal_result: CandidateProposal | None = None) -> None:
        """Persist the explicit call state when checkpointing is enabled."""
        if self.avo_checkpoint_path is None:
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
            development_case_ids=self.revision_evaluation.batch.evaluation_case_ids,
            configuration_identity=self.configuration_identity,
            budget=self.budget,
            current_snapshot=self.scratch.export_snapshot(self.child_candidate_id),
            incomplete_external_effects=self.incomplete_external_effects,
            terminal_result=terminal_record,
        )
        write_checkpoint(self.avo_checkpoint_path, checkpoint)

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
                except AVOToolBudgetExceeded as exc:
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
            "inspect_parent_results": guarded("inspect_parent_results", self.inspect_parent_results),
            "inspect_current_candidate": guarded("inspect_current_candidate", self.inspect_current_candidate),
            "inspect_inspirations": guarded("inspect_inspirations", self.inspect_inspirations),
            "inspect_previous_cycles": guarded("inspect_previous_cycles", self.inspect_previous_cycles),
            "inspect_rejected_candidates": guarded("inspect_rejected_candidates", self.inspect_rejected_candidates),
            "read_program_guidance": guarded("read_program_guidance", self.read_program_guidance),
            "edit_candidate": guarded("edit_candidate", self.edit_candidate),
            "test_candidate": guarded("test_candidate", self.test_candidate),
            "restore_candidate": guarded("restore_candidate", self.restore_candidate),
            "submit_candidate": guarded("submit_candidate", self.submit_candidate),
            "abstain": guarded("abstain", self.abstain),
        }
        if (
            self.advisor_runner is not None
            and self.budget.max_supervisor_interventions > self.state.usage.supervisor_interventions
        ):
            tools["request_advice"] = guarded("request_advice", self.request_advice)
        expected_names = _TOOL_NAMES + (("request_advice",) if "request_advice" in tools else ())
        if tuple(tools) != expected_names:
            raise AssertionError("agent tool surface does not match the approved AVO contract")
        return tools

    def inspect_parent_results(self) -> EvaluatedCandidate:
        """Return the exact selected-parent evidence supplied to AVO."""
        return self.request.parent

    def inspect_current_candidate(self) -> WorkspaceSnapshot:
        """Return the current scratch material, never the canonical workspace."""
        return self.scratch.export_snapshot(self.child_candidate_id)

    def inspect_inspirations(self) -> tuple[WorkspaceSnapshot, ...]:
        """Return only authorised inspiration snapshots."""
        return self.request.inspirations

    def inspect_previous_cycles(self) -> tuple[EvolutionCycleRecord, ...]:
        """Return approved evolution history without a write capability."""
        return self.request.history

    def inspect_rejected_candidates(self) -> tuple[GraveyardEntry, ...]:
        """Return approved failed-attempt summaries without graveyard mutation."""
        return self.request.graveyard

    def read_program_guidance(self) -> str:
        """Read the approved knowledge source supplied by composition."""
        if self.knowledge_source is None:
            return "No approved knowledge source is available."
        return self.knowledge_source() if callable(self.knowledge_source) else self.knowledge_source

    def edit_candidate(
        self,
        mutation: MutationInput | MutationAction | Mapping[str, Any] | Sequence[MutationInput],
    ) -> CandidateEditResult:
        """Apply validated prompt or skill edits to scratch and invalidate evidence."""
        mutations = _normalise_mutations(mutation)
        action_count = len(mutations)
        scope_limit = _SCOPE_ACTION_LIMITS[self.request.scope]
        if action_count > scope_limit:
            return CandidateEditResult(
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
                return CandidateEditResult(
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
            return CandidateEditResult(
                success=False,
                revision=self.state.current_revision,
                mutation=None,
                message="sanitisation removed the proposed workspace change",
            )
        if _material_change_count(self.request.parent.snapshot, after) > scope_limit:
            self.scratch.apply_snapshot(before)
            self.state = replace(self.state, current_revision=previous_revision)
            self._clear_compaction_effects()
            return CandidateEditResult(
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
        return CandidateEditResult(
            success=True,
            revision=self.state.current_revision,
            mutation=cumulative_mutation,
            message="mutation applied to scratch",
        )

    def test_candidate(self, hypothesis: str) -> CandidateCheckResult:
        """Evaluate exact current scratch material with the fixed revision checks."""
        self._check_cancellation()
        if not isinstance(hypothesis, str) or not hypothesis.strip():
            return CandidateCheckResult(
                success=False,
                revision=self.state.current_revision,
                message="hypothesis must not be blank",
            )
        snapshot = self.scratch.export_snapshot(self.child_candidate_id)
        if _same_material(snapshot, self.request.parent.snapshot):
            return CandidateCheckResult(
                success=False,
                revision=self.state.current_revision,
                message="unchanged parent material cannot be evaluated as a child",
            )
        if self.state.current_revision == 0:
            return CandidateCheckResult(
                success=False,
                revision=0,
                message="apply an effective mutation before evaluating a child revision",
            )
        if any(attempt.revision == self.state.current_revision for attempt in self.state.attempts):
            return CandidateCheckResult(
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
            attempt = self.revision_evaluation.evaluate_revision(
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
        return CandidateCheckResult(
            success=True,
            revision=self.state.current_revision,
            attempt=attempt,
            message="current revision evaluated",
        )

    def restore_candidate(self, attempt_id: str | None = None, revision: int | None = None) -> CandidateRestoreResult:
        """Restore exact material from one persisted evaluated attempt."""
        self._check_cancellation()
        if attempt_id is None and revision is None:
            return CandidateRestoreResult(
                False,
                self.state.current_revision,
                message="attempt_id or revision is required",
            )
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
            return CandidateRestoreResult(False, self.state.current_revision, message="revision attempt not found")
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
        return CandidateRestoreResult(
            success=True,
            revision=attempt.revision,
            snapshot=self.scratch.export_snapshot(self.child_candidate_id),
            message="exact evaluated attempt material restored",
        )

    def submit_candidate(
        self,
        reasoning: str = "Submitted the current evaluated revision.",
    ) -> CandidateSubmissionResult:
        """Select one current, evaluated, changed revision for submission."""
        self._check_cancellation()
        if not isinstance(reasoning, str) or not reasoning.strip():
            return CandidateSubmissionResult(False, self.state.current_revision, message="reasoning must not be blank")
        snapshot = self.scratch.export_snapshot(self.child_candidate_id)
        if not is_revision_valid(self.state, self.state.current_revision, snapshot):
            return CandidateSubmissionResult(
                False,
                self.state.current_revision,
                message="current revision has no eligible exact revision evidence",
            )
        attempt = next(item for item in self.state.attempts if item.revision == self.state.current_revision)
        self.explicit_reasoning = reasoning.strip()
        self.terminal_status = ProposalStatus.SUBMITTED
        self.terminal_message = self.explicit_reasoning
        return CandidateSubmissionResult(True, self.state.current_revision, attempt, self.explicit_reasoning)

    def abstain(self, reasoning: str) -> CandidateAbstentionResult:
        """Explicitly abstain without returning scratch material."""
        if not isinstance(reasoning, str) or not reasoning.strip():
            return CandidateAbstentionResult(False, "reasoning must not be blank")
        self.explicit_reasoning = reasoning.strip()
        self.terminal_status = ProposalStatus.ABSTAINED
        self.terminal_message = self.explicit_reasoning
        return CandidateAbstentionResult(True, self.explicit_reasoning)

    def request_advice(self) -> str:
        """Persist the main agent's request for a new direction."""
        if (
            self.advisor_runner is None
            or self.state.usage.supervisor_interventions >= self.budget.max_supervisor_interventions
        ):
            return "Advisor input is unavailable within the configured budget."
        self.state = replace(self.state, exhausted_direction_requested=True)
        self._write_checkpoint()
        return "The exhausted-direction request was recorded for advisor input."

    def _dispatch(self, command: AVOCommand, tools: Mapping[str, Callable[..., object]]) -> None:
        try:
            function = tools[command.tool.value]
            function(**command.arguments)
        except AVOToolBudgetExceeded:
            raise
        except (KeyError, TypeError, ValueError):
            # Typed argument errors are returned to the next model request.
            # Provider and evaluation failures use their own propagation rules.
            return

    def _maybe_get_advice(self) -> None:
        """Run one advisor intervention after a completed main-agent outcome."""
        trigger_reason = advice_trigger(
            self.state,
            self.budget,
            exhausted_direction_requested=self.state.exhausted_direction_requested,
        )
        if trigger_reason is None or self.advisor_runner is None:
            return

        self._check_cancellation()
        usage_before = self.state.usage
        try:
            reserved_usage = reserve_advisor_budget(usage_before, self.budget)
        except ValueError as exc:
            raise AVOToolBudgetExceeded(str(exc)) from exc
        reserved_state = replace(self.state, usage=reserved_usage)
        request = AVOAdviceRequest(
            goal=self.request.selection.goal,
            selected_parent_id=reserved_state.parent_candidate_id,
            strategy=self.request.selection.strategy,
            attempt_summaries=reserved_state.memory,
            remaining_budget=remaining_avo_budget(self.budget, reserved_state),
            trigger_reason=trigger_reason,
        )
        self.state = reserved_state
        effect = self._begin_external_effect(
            "supervisor_request",
            f"supervisor-{reserved_usage.supervisor_interventions}",
            check_cancellation=False,
        )
        try:
            result = self.advisor_runner(request)
            if not isinstance(result, AVOAdviceResult):
                raise TypeError("supervisor runner must return AVOAdviceResult")
            reconciled_usage = complete_advisor_usage(usage_before, self.budget, result.usage)
            self._model_cost_known = reconciled_usage.model_cost_usd is not None
            self._model_cost_total = reconciled_usage.model_cost_usd or 0.0
            if isinstance(result.output, AVOAdvice):
                record = AVOAdviceRecord(trigger_reason=trigger_reason, advice=result.output)
            else:
                record = AVOAdviceRecord(trigger_reason=trigger_reason, failure=result.output)
            self.state = replace(
                self.state,
                usage=reconciled_usage,
                supervision_records=(*self.state.supervision_records, record),
                exhausted_direction_requested=False,
                consecutive_without_progress=0,
                consecutive_evaluation_errors=0,
            )
            # Publish the confirmed outcome, exact usage, and marker removal in
            # one atomic checkpoint replacement. A crash before this write
            # retains the prior incomplete marker and therefore fails closed.
            self.incomplete_external_effects = tuple(
                item for item in self.incomplete_external_effects if item.effect_id != effect.effect_id
            )
            self._write_checkpoint()
        except AVOIncompleteExternalEffectError:
            raise
        except Exception as exc:
            # A provider, transport, malformed adapter, or reconciliation
            # failure is not safe to retry because completion is unknown.
            raise AVOIncompleteExternalEffectError(effect, exc) from exc
        self._check_cancellation()

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

    def _record_model_tokens(self, input_tokens: int | None, output_tokens: int | None) -> None:
        """Aggregate one response's token counts, retaining unknown values."""
        usage = self.state.usage
        previous_requests = usage.model_requests - 1

        def merge(previous: int | None, added: int | None) -> int | None:
            if added is None:
                return None
            if previous_requests == 0:
                return added
            if previous is None:
                return None
            return previous + added

        self._set_usage(
            input_tokens=merge(usage.input_tokens, input_tokens),
            output_tokens=merge(usage.output_tokens, output_tokens),
        )

    def _set_usage(self, **updates: int | float | None) -> None:
        usage = self.state.usage
        self.state = replace(
            self.state,
            usage=ProposalUsage(
                model_requests=_as_int(updates.get("model_requests"), usage.model_requests),
                tool_calls=_as_int(updates.get("tool_calls"), usage.tool_calls),
                development_evaluations=_as_int(updates.get("development_evaluations"), usage.development_evaluations),
                supervisor_interventions=usage.supervisor_interventions,
                input_tokens=_as_optional_int(updates.get("input_tokens", usage.input_tokens)),
                output_tokens=_as_optional_int(updates.get("output_tokens", usage.output_tokens)),
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
                raise AVOToolBudgetExceeded(name)

    def _ensure_tool_budget(self, _tool_name: str) -> None:
        self._refresh_elapsed()
        usage = self.state.usage
        if usage.tool_calls >= self.budget.max_tool_calls:
            raise AVOToolBudgetExceeded("max_tool_calls")
        if usage.elapsed_seconds >= self.budget.max_elapsed_seconds:
            raise AVOToolBudgetExceeded("max_elapsed_seconds")
        limit = self._known_token_limit()
        if limit is not None:
            raise AVOToolBudgetExceeded(limit)
        limit = self._known_cost_limit()
        if limit is not None:
            raise AVOToolBudgetExceeded(limit)

    def _ensure_effect_budget(self, name: str) -> None:
        self._refresh_elapsed()
        usage = self.state.usage
        if (
            name == "max_development_evaluations"
            and usage.development_evaluations >= self.budget.max_development_evaluations
        ):
            raise AVOToolBudgetExceeded(name)
        if self.state.consecutive_evaluation_errors >= self.budget.max_consecutive_evaluation_errors:
            raise AVOToolBudgetExceeded("max_consecutive_evaluation_errors")
        if self.state.consecutive_without_progress >= self.budget.max_stagnant_evaluations:
            raise AVOToolBudgetExceeded("max_stagnant_evaluations")
        limit = self._loop_limit_reason()
        if limit is not None:
            raise AVOToolBudgetExceeded(limit)

    def _loop_limit_reason(self) -> str | None:
        """Return limits that stop the next model request or tool effect."""
        usage = self.state.usage
        if usage.model_requests >= self.budget.max_model_requests:
            return "max_model_requests"
        if usage.tool_calls >= self.budget.max_tool_calls:
            return "max_tool_calls"
        if usage.elapsed_seconds >= self.budget.max_elapsed_seconds:
            return "max_elapsed_seconds"
        token_limit = self._known_token_limit()
        if token_limit is not None:
            return token_limit
        return self._known_cost_limit()

    def _known_token_limit(self) -> str | None:
        usage = self.state.usage
        if usage.model_requests == 0:
            return None
        for name, observed, limit in (
            ("max_input_tokens", usage.input_tokens, self.budget.max_input_tokens),
            ("max_output_tokens", usage.output_tokens, self.budget.max_output_tokens),
        ):
            if limit is not None:
                if observed is None:
                    return f"{name}_unknown"
                if observed >= limit:
                    return name
        return None

    def _known_cost_limit(self) -> str | None:
        if self.budget.max_cost_usd is None:
            return None
        total_cost = self.state.usage.total_cost_usd
        if total_cost is None:
            return "max_cost_usd_unknown"
        if total_cost >= self.budget.max_cost_usd:
            return "max_cost_usd"
        return None

    def _exhausted(self, limit: str) -> CandidateProposal:
        self.terminal_status = ProposalStatus.BUDGET_EXHAUSTED
        self.terminal_message = f"Budget exhausted: {limit}."
        return self._terminal_result()

    def _terminal_result(self) -> CandidateProposal:
        if self.terminal_status is not ProposalStatus.CANCELLED:
            self._check_cancellation()
        self._refresh_elapsed()
        self.state = replace(self.state, terminal_status=self.terminal_status or ProposalStatus.BUDGET_EXHAUSTED)
        usage = self.state.usage
        if self.terminal_status is ProposalStatus.SUBMITTED:
            snapshot = self.scratch.export_snapshot(self.child_candidate_id)
            attempt = next(item for item in self.state.attempts if item.revision == self.state.current_revision)
            result = CandidateProposal(
                status=ProposalStatus.SUBMITTED,
                child=snapshot,
                mutation=attempt.mutation,
                reasoning=self.terminal_message,
                usage=usage,
                attempt=attempt,
                memory=self.state.memory,
            )
        else:
            result = CandidateProposal(
                status=self.terminal_status or ProposalStatus.BUDGET_EXHAUSTED,
                child=None,
                mutation=None,
                reasoning=self.terminal_message or "Variation ended without a submitted child.",
                usage=usage,
                memory=self.state.memory,
            )
        self._write_checkpoint(result)
        return result


__all__ = ("AVOSession",)
