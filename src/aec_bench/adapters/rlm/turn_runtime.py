# ABOUTME: Executes and reduces one normalized RLM provider turn.
# ABOUTME: Shares REPL, accounting, compaction, and completion logic across response surfaces.

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from aec_bench.adapters.base import AdapterFailureKind, AdapterStopReason
from aec_bench.adapters.rlm.client import RlmCompletionResponse, RlmMessage
from aec_bench.adapters.rlm.engine import ExecutionResult
from aec_bench.adapters.rlm.errors import ErrorLevel
from aec_bench.adapters.rlm.metadata import format_iteration_metadata
from aec_bench.adapters.rlm.prompt_surface import (
    build_var_summary,
    format_code_preview,
    iteration_budget_warning,
)
from aec_bench.adapters.rlm.runtime_contracts import (
    LifecycleAction,
    LifecycleTransition,
    RlmExecutionState,
)
from aec_bench.adapters.rlm.template import TemplateStatus
from aec_bench.adapters.rlm.tokens import TurnMetrics
from aec_bench.adapters.rlm.turn_execution import TurnExecution, TurnExecutionSurface
from aec_bench.contracts.adapter_execution import (
    TokenUsage,
    TranscriptEntry,
    TranscriptEvent,
    TranscriptRole,
)
from aec_bench.contracts.agent_output import AgentOutputStatus

logger = logging.getLogger(__name__)

_FINAL_MARKER = "FINAL"


@dataclass(frozen=True, slots=True)
class ReplTurn:
    """Evidence produced by one optional REPL execution."""

    result: ExecutionResult | None
    code: str | None
    new_variables: tuple[str, ...] = ()
    removed_variables: tuple[str, ...] = ()


class TurnProcessor:
    """Advances one execution state across a normalized provider response."""

    def __init__(
        self,
        state: RlmExecutionState,
        *,
        emit: Callable[[str, str], None],
    ) -> None:
        self._state = state
        self._emit = emit

    def process(
        self,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
    ) -> LifecycleTransition:
        """Execute and reduce one provider response."""
        execution = TurnExecution.from_response(response)
        if execution.surface is TurnExecutionSurface.STRUCTURED_TOOL_CALL:
            return self._process_structured(execution, response, metrics)
        return self._process_text(execution, response, metrics)

    def _process_structured(
        self,
        execution: TurnExecution,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
    ) -> LifecycleTransition:
        code = execution.code
        if code is None:
            raise RuntimeError("structured tool-call turn omitted executable code")
        turn = self._execute_code(code, response, metrics, structured=True)
        self._append_assistant(response, only_when_nonempty=True)
        footer = self._scaffolding_footer()
        self._append_tool_transcript(turn, footer=footer)
        context_message = self._structured_context(turn, footer=footer)
        contract_satisfied = self._state.output.contract_satisfied(turn.result)
        reminder = self._state.output.register_reminder(
            contract_satisfied=contract_satisfied,
            final_called=self._state.repl.final_called,
            iteration=self._iteration,
        )
        if reminder:
            context_message += self._state.output.reminder
        if not self._state.repl.final_called:
            context_message += self._budget_warning()
        self._append_structured_conversation(execution, context_message)
        if self._state.repl.final_called:
            return self._completed_transition(
                output_text=execution.output_text,
                contract_satisfied=contract_satisfied,
                status=AgentOutputStatus.COMPLETED,
                missing_output=False,
            )
        return self._post_nonterminal(response, metrics)

    def _process_text(
        self,
        execution: TurnExecution,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
    ) -> LifecycleTransition:
        self._append_assistant(response, only_when_nonempty=False)
        turn = self._execute_text_surface(execution, response, metrics)
        contract_satisfied = self._state.output.contract_satisfied(turn.result)
        reminder = self._state.output.register_reminder(
            contract_satisfied=contract_satisfied,
            final_called=self._state.repl.final_called,
            iteration=self._iteration,
        )
        is_final = self._text_is_final(execution)
        if is_final and self._intercept_early_return(execution):
            return LifecycleTransition.continue_execution()
        budget_warning = "" if is_final else self._budget_warning()
        if is_final:
            status = AgentOutputStatus.COMPLETED if execution.output_text else AgentOutputStatus.EMPTY
            return self._completed_transition(
                output_text=execution.output_text,
                contract_satisfied=contract_satisfied,
                status=status,
                missing_output=not execution.output_text,
            )
        transition = self._post_nonterminal(response, metrics)
        if transition.action is LifecycleAction.CONTINUE:
            self._append_text_conversation(
                execution,
                turn,
                reminder=reminder,
                budget_warning=budget_warning,
            )
        return transition

    @property
    def _iteration(self) -> int:
        return self._state.guardrails.iteration_count

    def _execute_text_surface(
        self,
        execution: TurnExecution,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
    ) -> ReplTurn:
        if execution.surface is TurnExecutionSurface.TEXT:
            preview = execution.output_text.strip()[:80].replace("\n", " ")
            self._emit(f"turn {self._iteration}", f"(text) {preview}")
            return ReplTurn(result=None, code=None)
        code = execution.code
        if code is None:
            raise RuntimeError("text-code turn omitted executable code")
        if execution.additional_code_block_count:
            logger.info(
                "Truncated %d extra code blocks from response (first-block-only execution)",
                execution.additional_code_block_count,
            )
        turn = self._execute_code(code, response, metrics, structured=False)
        self._append_tool_transcript(turn)
        return turn

    def _execute_code(
        self,
        code: str,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
        *,
        structured: bool,
    ) -> ReplTurn:
        state = self._state
        state.output.begin_turn(state.repl, self._iteration)
        result = state.repl.execute(code)
        state.repl.restore_protected(state.scaffolds)
        result = state.output.finish_turn(state.repl, result)
        self._record_repl_error(code, result)
        new_variables, removed_variables = self._variable_changes()
        self._record_trajectory(code, result, metrics, new_variables, removed_variables)
        self._emit_code_progress(
            code,
            result,
            response,
            metrics,
            new_variables,
            structured=structured,
        )
        return ReplTurn(
            result=result,
            code=code,
            new_variables=tuple(new_variables),
            removed_variables=tuple(removed_variables),
        )

    def _record_repl_error(self, code: str, result: ExecutionResult) -> None:
        if not result.error:
            return
        self._state.errors.record(
            level=ErrorLevel.REPL,
            iteration=self._iteration,
            error=result.error,
            code_attempted=code,
        )
        logger.debug(
            "REPL error at iteration %d: %s",
            self._iteration,
            result.error.strip().split("\n")[-1],
        )

    def _variable_changes(self) -> tuple[list[str], list[str]]:
        state = self._state
        current = set(state.repl.list_variables())
        new_variables = sorted(name for name in current - state.previous_variable_names if len(name) > 1)
        removed_variables = sorted(state.previous_variable_names - current)
        state.previous_variable_names = current
        return new_variables, removed_variables

    def _record_trajectory(
        self,
        code: str,
        result: ExecutionResult,
        metrics: TurnMetrics,
        new_variables: list[str],
        removed_variables: list[str],
    ) -> None:
        trajectory = self._state.trajectory
        if trajectory is None:
            return
        trajectory.new_step()
        trajectory.tool_call("repl", code)
        trajectory.tool_result(
            "repl",
            stdout=result.error or result.stdout or "(no output)",
            metadata=self._build_step_metadata(
                metrics,
                new_variables,
                removed_variables,
            ),
        )

    def _build_step_metadata(
        self,
        metrics: TurnMetrics,
        new_variables: list[str],
        removed_variables: list[str],
    ) -> dict[str, Any]:
        state = self._state
        metadata: dict[str, Any] = {
            "var_diff": {
                "new": new_variables,
                "removed": removed_variables,
            },
            "scratchpad_keys": state.scratchpad.keys if state.scratchpad else [],
        }
        template = state.runtime.template
        if template is not None:
            status = template.get_status()
            metadata["template_progress"] = {
                "completed": status.completed_sections,
                "total": status.total_sections,
                "filled": status.completed,
                "unlocked": status.unlocked,
            }
        metadata["variables"] = build_var_summary(state.repl)
        metadata["tokens"] = {
            "call_input": metrics.call_input_tokens,
            "grand_total": metrics.grand_total_tokens,
        }
        return metadata

    def _emit_code_progress(
        self,
        code: str,
        result: ExecutionResult,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
        new_variables: list[str],
        *,
        structured: bool,
    ) -> None:
        state = self._state
        template_info = ""
        if not structured and state.runtime.template is not None:
            status = state.runtime.template.get_status()
            template_info = f" [{status.completed_sections}/{status.total_sections} sections]"
        cost_info = f"${state.guardrails.total_cost_usd:.3f}" if state.guardrails.total_cost_usd else ""
        token_info = f"{metrics.call_input_tokens:,}in/{response.output_tokens:,}out"
        variable_info = f" +{new_variables}" if new_variables else ""
        error_flag = " ERR" if result.error else ""
        self._emit(
            f"turn {self._iteration}",
            f"{format_code_preview(code)} ({token_info} {cost_info}{template_info}{variable_info}{error_flag})",
        )

    def _append_assistant(
        self,
        response: RlmCompletionResponse,
        *,
        only_when_nonempty: bool,
    ) -> None:
        if only_when_nonempty and not response.output_text:
            return
        self._state.transcript.append(
            TranscriptEntry(
                role=TranscriptRole.ASSISTANT,
                content=response.output_text,
                usage=TokenUsage(
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                ),
            )
        )

    def _append_tool_transcript(self, turn: ReplTurn, *, footer: str = "") -> None:
        result = turn.result
        if result is None:
            return
        content = result.error or result.stdout or "(no output)"
        snapshot = self._state.repl.snapshot_variables()
        if snapshot:
            content += "\n--- variables ---\n" + json.dumps(snapshot, indent=2, default=str)
        self._state.transcript.append(
            TranscriptEntry(
                role=TranscriptRole.TOOL,
                content=content + footer,
                event=TranscriptEvent.TOOL_RESULT,
                tool_name="repl",
            )
        )

    def _scaffolding_footer(self) -> str:
        state = self._state
        template = state.runtime.template
        if template is None:
            return ""
        return state.scaffolding.build_footer(
            template_status=template.get_status(),
            scratchpad_keys=state.scratchpad.keys if state.scratchpad else [],
        )

    def _structured_context(self, turn: ReplTurn, *, footer: str) -> str:
        result = turn.result
        code = turn.code
        if result is None or code is None:
            raise RuntimeError("structured context requires REPL execution evidence")
        state = self._state
        new_variables = list(turn.new_variables)
        removed_variables = list(turn.removed_variables)
        context_message = state.context_filter.build_context_message(
            stdout=result.stdout,
            error=result.error,
            code=code,
            new_vars=new_variables or None,
        )
        variable_diff = state.context_filter.format_var_diff(
            new=new_variables,
            removed=removed_variables,
            repl_vars={
                name: state.repl.get_variable(name)
                for name in new_variables
                if state.repl.get_variable(name) is not None
            },
        )
        if variable_diff:
            context_message += "\n" + variable_diff
        return context_message + footer

    def _budget_warning(self) -> str:
        state = self._state
        if state.iteration_budget_warning_sent:
            return ""
        warning = iteration_budget_warning(
            iteration=self._iteration,
            max_iterations=state.resolved.max_iterations,
            output_path=state.request.output_path,
            output_commit_enabled=state.output.commit_enabled,
        )
        if warning is not None:
            state.iteration_budget_warning_sent = True
        return warning or ""

    def _append_structured_conversation(
        self,
        execution: TurnExecution,
        context_message: str,
    ) -> None:
        conversation = self._state.conversation
        if execution.output_text:
            conversation.append(RlmMessage(role="assistant", content=execution.output_text))
        conversation.append(
            RlmMessage(
                role="tool_call",
                content=execution.code or "",
                tool_call_id=execution.tool_call_id,
                tool_name=execution.tool_call_name,
            )
        )
        conversation.append(
            RlmMessage(
                role="tool_result",
                content=context_message,
                tool_call_id=execution.tool_call_id,
                tool_name=execution.tool_call_name,
            )
        )

    def _text_is_final(self, execution: TurnExecution) -> bool:
        state = self._state
        return state.repl.final_called or (
            state.output.contract is None and (_FINAL_MARKER in execution.effective_response or execution.done)
        )

    def _intercept_early_return(self, execution: TurnExecution) -> bool:
        if self._iteration != 1 or execution.code is not None:
            return False
        logger.info("Early return intercepted at iteration 0 — forcing verification")
        self._state.repl.final_called = False
        self._state.conversation.extend(
            (
                RlmMessage(role="assistant", content=execution.output_text),
                RlmMessage(
                    role="user",
                    content=(
                        "[Early return intercepted] You returned on the first "
                        "iteration without doing any work in the REPL. Verify "
                        "your answer is correct by reading the task, extracting "
                        "the relevant data, and checking your result before "
                        "calling FINAL_VAR()."
                    ),
                ),
            )
        )
        return True

    def _completed_transition(
        self,
        *,
        output_text: str,
        contract_satisfied: bool,
        status: AgentOutputStatus,
        missing_output: bool,
    ) -> LifecycleTransition:
        state = self._state
        assistance = state.output.completion_assistance(
            contract_satisfied=contract_satisfied,
            explicit_final_turn=self._iteration,
        )
        self._emit(
            "done",
            f"{self._iteration} turns, "
            f"{state.total_input_tokens + state.total_output_tokens:,} tokens, "
            f"${state.guardrails.total_cost_usd:.3f}",
        )
        state.close_trajectory()
        result = state.build_result(
            status=status,
            completion_reason=state.output.completion_reason(assistance),
            completion_assistance=assistance,
            completion_commit=state.output.attestation,
            failure_kind=AdapterFailureKind.MISSING_OUTPUT if missing_output else None,
            raw_output_text=output_text or None,
        )
        return LifecycleTransition.terminal(result)

    def _post_nonterminal(
        self,
        response: RlmCompletionResponse,
        metrics: TurnMetrics,
    ) -> LifecycleTransition:
        state = self._state
        template = state.runtime.template
        if template is not None:
            state.scaffolding.record_progress(template.get_status().completed_sections)
        execution_config = state.runtime.execution
        if state.tokens.needs_compaction(
            metrics.call_input_tokens,
            execution_config.compaction_threshold_pct,
        ):
            return LifecycleTransition.compact()
        if state.tokens.hit_hard_ceiling(
            metrics.call_input_tokens,
            execution_config.hard_ceiling_pct,
        ):
            logger.warning(
                "Hard ceiling hit: %d tokens (%.0f%% of %d)",
                metrics.call_input_tokens,
                execution_config.hard_ceiling_pct * 100,
                state.resolved.context_limit,
            )
            state.close_trajectory()
            return LifecycleTransition.terminal(
                state.build_result(
                    status=AgentOutputStatus.PARTIAL,
                    failure_kind=AdapterFailureKind.CONTEXT_LIMIT_REACHED,
                    stop_reason=AdapterStopReason.CONTEXT_LIMIT,
                    error_message="Hard ceiling on context size reached.",
                    raw_output_text=response.output_text or None,
                )
            )
        return LifecycleTransition.continue_execution()

    def _append_text_conversation(
        self,
        execution: TurnExecution,
        turn: ReplTurn,
        *,
        reminder: bool,
        budget_warning: str,
    ) -> None:
        state = self._state
        template = state.runtime.template
        template_status: TemplateStatus | None = template.get_status() if template is not None else None
        footer = state.scaffolding.build_footer(
            template_status=template_status,
            scratchpad_keys=state.scratchpad.keys if state.scratchpad else [],
        )
        metadata = format_iteration_metadata(
            result=turn.result,
            variables=state.repl.list_variables(),
            iteration=self._iteration,
            token_budget_pct=state.guardrails.check().budget_consumed_pct,
            template_status=template_status,
        )
        if footer:
            metadata += footer
        if reminder:
            metadata += state.output.reminder
        metadata += budget_warning
        state.conversation.extend(
            (
                RlmMessage(role="assistant", content=execution.effective_response),
                RlmMessage(role="user", content=metadata),
            )
        )
