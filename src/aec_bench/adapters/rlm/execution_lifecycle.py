# ABOUTME: Drives the typed RLM execution lifecycle from request resolution to terminal result.
# ABOUTME: Owns provider effects, guardrail transitions, compaction, and failure reduction.

from __future__ import annotations

import logging
from collections.abc import Callable

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
    AdapterStopReason,
)
from aec_bench.adapters.rlm.client import RlmCompletionResponse
from aec_bench.adapters.rlm.compaction_runtime import run_compaction_transition
from aec_bench.adapters.rlm.prompt_surface import REPL_TOOL_NAME, REPL_TOOL_SCHEMA
from aec_bench.adapters.rlm.repl_runtime import (
    prepare_execution_state,
    resolve_state_persistence_params,
)
from aec_bench.adapters.rlm.request_runtime import resolve_rlm_request
from aec_bench.adapters.rlm.runtime_contracts import (
    LifecycleAction,
    RlmExecutionState,
    RlmRuntimeConfig,
)
from aec_bench.adapters.rlm.turn_runtime import TurnProcessor
from aec_bench.contracts.adapter_execution import TokenUsage, TranscriptEntry, TranscriptRole
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.pricing import estimate_cost_usd

logger = logging.getLogger(__name__)

GUARDRAIL_FAILURE_KINDS = {
    AdapterStopReason.ITERATION_CAP: AdapterFailureKind.TURN_LIMIT_REACHED,
    AdapterStopReason.TOKEN_BUDGET: AdapterFailureKind.TOKEN_BUDGET_REACHED,
    AdapterStopReason.SUBCALL_LIMIT: AdapterFailureKind.SUBCALL_LIMIT_REACHED,
    AdapterStopReason.COST_BUDGET: AdapterFailureKind.COST_BUDGET_REACHED,
    AdapterStopReason.BILLABLE_INPUT_BUDGET: AdapterFailureKind.BILLABLE_INPUT_BUDGET_REACHED,
}


def run_rlm_execution(
    runtime: RlmRuntimeConfig,
    request: AdapterRequest,
    *,
    emit: Callable[[str, str], None],
) -> AdapterResult:
    """Run one RLM request until a typed terminal transition is produced."""
    resolved = resolve_rlm_request(
        request,
        guardrails=runtime.guardrails,
        execution=runtime.execution,
    )
    state = prepare_execution_state(runtime, resolved)
    processor = TurnProcessor(state, emit=emit)
    while True:
        guarded_result = _guardrail_terminal(state)
        if guarded_result is not None:
            return guarded_result
        response = _call_model(state, emit=emit)
        metrics = state.record_response(response, cost_usd=_response_cost(state, response))
        provider_failure = _provider_failure(state, response)
        if provider_failure is not None:
            return provider_failure
        transition = processor.process(response, metrics)
        if transition.action is LifecycleAction.TERMINAL:
            if transition.result is None:
                raise RuntimeError("terminal RLM transition omitted its adapter result")
            return transition.result
        if transition.action is LifecycleAction.COMPACT:
            _compact(state, emit=emit)


def _guardrail_terminal(state: RlmExecutionState) -> AdapterResult | None:
    verdict = state.guardrails.check()
    if verdict.can_continue:
        return None
    logger.info("Guardrail stop: %s", verdict.stop_reason)
    if verdict.stop_code is None:
        raise RuntimeError("stopping RLM guardrail verdict omitted its typed stop code")
    state.close_trajectory()
    return state.build_result(
        status=AgentOutputStatus.PARTIAL,
        failure_kind=GUARDRAIL_FAILURE_KINDS[verdict.stop_code],
        stop_reason=verdict.stop_code,
        error_message=verdict.stop_reason,
    )


def _call_model(
    state: RlmExecutionState,
    *,
    emit: Callable[[str, str], None],
) -> RlmCompletionResponse:
    if state.guardrails.iteration_count <= 1:
        suffix = "  (tool_use)" if state.tool_client is not None else ""
        emit("model", f"calling {state.runtime.model_name}{suffix}...")
    if state.tool_client is not None:
        return state.tool_client.generate_with_tools(
            model=state.runtime.model_name,
            messages=state.conversation,
            system_prompt=state.system_prompt,
            tool_name=REPL_TOOL_NAME,
            tool_description=state.repl_tool_description,
            tool_parameters_schema=REPL_TOOL_SCHEMA,
        )
    return state.runtime.client.generate(
        model=state.runtime.model_name,
        messages=state.conversation,
        system_prompt=state.system_prompt,
    )


def _response_cost(
    state: RlmExecutionState,
    response: RlmCompletionResponse,
) -> float:
    return (
        estimate_cost_usd(
            state.runtime.model_name,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cache_read_tokens=response.cache_read_tokens,
            cache_write_tokens=response.cache_write_tokens,
        )
        or 0.0
    )


def _provider_failure(
    state: RlmExecutionState,
    response: RlmCompletionResponse,
) -> AdapterResult | None:
    if response.error_message is None:
        return None
    logger.warning("Provider error: %s", response.error_message)
    state.transcript.append(
        TranscriptEntry(
            role=TranscriptRole.ASSISTANT,
            content=response.error_message,
            usage=TokenUsage(
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
            ),
        )
    )
    state.close_trajectory()
    return state.build_result(
        status=AgentOutputStatus.FAILED,
        failure_kind=AdapterFailureKind.PROVIDER_ERROR,
        error_message=response.error_message,
        raw_output_text=response.output_text or None,
    )


def _compact(
    state: RlmExecutionState,
    *,
    emit: Callable[[str, str], None],
) -> None:
    execution = state.runtime.execution
    model = execution.compaction_model or state.runtime.model_name
    client = state.runtime.compaction_client or state.runtime.client
    transition = run_compaction_transition(
        client=client,
        model=model,
        repl=state.repl,
        scratchpad=state.scratchpad,
        template=state.runtime.template,
        params=resolve_state_persistence_params(state.runtime),
        previous_count=state.compaction_count,
        pre_message_count=len(state.conversation),
        token_tracker=state.tokens,
        scaffolding=state.scaffolding,
        trajectory=state.trajectory,
        emit=emit,
    )
    state.compaction_count = transition.number
    state.conversation = list(transition.conversation)
