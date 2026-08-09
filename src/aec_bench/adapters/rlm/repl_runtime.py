# ABOUTME: Prepares the persistent REPL and its declared command surface for one RLM run.
# ABOUTME: Isolates capability injection from provider-turn orchestration and terminal reduction.

from __future__ import annotations

import importlib.util
import logging
import re
import threading
import tomllib
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from aec_bench.adapters.advisor_usage import AdvisorUsageAccumulator
from aec_bench.adapters.base import initialize_transcript
from aec_bench.adapters.rlm.client import RlmMessage, ToolCapableRlmClient
from aec_bench.adapters.rlm.context_filter import ContextFilter
from aec_bench.adapters.rlm.engine import ReplEnvironment
from aec_bench.adapters.rlm.errors import ErrorTracker
from aec_bench.adapters.rlm.fill_parallel import SectionGenerator
from aec_bench.adapters.rlm.fill_parallel import fill_parallel as fill_template_parallel
from aec_bench.adapters.rlm.guardrails import GuardrailState
from aec_bench.adapters.rlm.output_commit import OutputCompletionState
from aec_bench.adapters.rlm.parallel import parallel
from aec_bench.adapters.rlm.prompt_surface import (
    build_repl_tool_description,
    build_system_prompt,
    enabled_subcall_names,
    make_final_var,
    make_help,
    make_show_vars,
)
from aec_bench.adapters.rlm.request_runtime import ResolvedRlmRequest
from aec_bench.adapters.rlm.runtime_contracts import (
    RlmExecutionState,
    RlmRuntimeConfig,
)
from aec_bench.adapters.rlm.scaffolding import ScaffoldingState
from aec_bench.adapters.rlm.scratchpad import Scratchpad
from aec_bench.adapters.rlm.subcall_log import SubcallLog
from aec_bench.adapters.rlm.subcall_registry import build_subcall_functions
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.tokens import TokenTracker
from aec_bench.contracts.adapter_execution import TranscriptEntry
from aec_bench.contracts.advisor import AdvisorRequest, AdvisorResponse
from aec_bench.contracts.constitution import (
    EarnedAutonomyParams,
    InformationMinimalityParams,
    ProgressObligationParams,
    StatePersistenceParams,
)
from aec_bench.contracts.pricing import estimate_cost_usd

if TYPE_CHECKING:
    from aec_bench.adapters.advisor import AdvisorResult

logger = logging.getLogger(__name__)


def build_context_filter(runtime: RlmRuntimeConfig) -> ContextFilter:
    """Create the configured information-minimality filter."""
    constitution = runtime.constitution
    params = (
        constitution.information_minimality
        if constitution is not None and constitution.information_minimality is not None
        else InformationMinimalityParams()
    )
    return ContextFilter(params)


def build_scaffolding_state(runtime: RlmRuntimeConfig) -> ScaffoldingState:
    """Create progress/autonomy scaffolding from the configured constitution."""
    constitution = runtime.constitution
    progress = (
        constitution.progress_obligation
        if constitution is not None and constitution.progress_obligation is not None
        else ProgressObligationParams()
    )
    autonomy = (
        constitution.earned_autonomy
        if constitution is not None and constitution.earned_autonomy is not None
        else EarnedAutonomyParams()
    )
    return ScaffoldingState(
        enabled=runtime.execution.scaffolding,
        progress_params=progress,
        autonomy_params=autonomy,
    )


def resolve_state_persistence_params(runtime: RlmRuntimeConfig) -> StatePersistenceParams:
    """Return configured state-persistence parameters or their defaults."""
    constitution = runtime.constitution
    if constitution is not None and constitution.state_persistence is not None:
        return constitution.state_persistence
    return StatePersistenceParams()


def prepare_execution_state(
    runtime: RlmRuntimeConfig,
    resolved: ResolvedRlmRequest,
) -> RlmExecutionState:
    """Prepare all local state before the first provider effect."""
    repl = ReplEnvironment()
    output = OutputCompletionState.from_request(resolved.request)
    guardrails = _build_guardrails(runtime, resolved)
    token_tracker = TokenTracker(context_limit=resolved.context_limit)
    scaffolding = build_scaffolding_state(runtime)
    context_filter = build_context_filter(runtime)
    transcript = initialize_transcript(resolved.request)
    enabled_subcalls = enabled_subcall_names(runtime.subcall_configs)
    scratchpad_enabled = runtime.scratchpad_path is not None
    template_enabled = runtime.template is not None
    advisor_enabled = _advisor_enabled(runtime)
    advisor_usage = AdvisorUsageAccumulator() if advisor_enabled else None
    system_prompt = (
        build_system_prompt(
            hints=runtime.hints,
            variables=None,
            prohibited=runtime.prohibited,
            external_system_prompt=runtime.external_system_prompt,
            constitution=runtime.constitution,
            max_iterations=resolved.max_iterations,
            scratchpad_enabled=scratchpad_enabled,
            enabled_subcalls=enabled_subcalls,
            template_enabled=template_enabled,
        )
        + output.system_prompt_suffix
    )
    scaffolds: dict[str, object] = {}
    scratchpad = _inject_repl_surface(
        repl=repl,
        scaffolds=scaffolds,
        output=output,
        runtime=runtime,
        resolved=resolved,
        transcript=transcript,
        guardrails=guardrails,
        token_tracker=token_tracker,
        enabled_subcalls=enabled_subcalls,
        advisor_usage=advisor_usage,
    )
    if runtime.workspace_path and runtime.execution.scaffolding:
        load_repl_commands(
            repl,
            workspace_path=runtime.workspace_path,
            template=runtime.template,
        )
    if runtime.trajectory is not None:
        runtime.trajectory.system(system_prompt)
        runtime.trajectory.user(resolved.request.instruction)
    tool_client = runtime.client if isinstance(runtime.client, ToolCapableRlmClient) else None
    tool_description = build_repl_tool_description(
        max_iterations=resolved.max_iterations,
        scratchpad_enabled=scratchpad_enabled,
        enabled_subcalls=enabled_subcalls,
        template_enabled=template_enabled,
        output_commit_enabled=output.commit_enabled,
        advisor_enabled=advisor_enabled,
    )
    return RlmExecutionState(
        runtime=runtime,
        resolved=resolved,
        output=output,
        repl=repl,
        errors=ErrorTracker(),
        guardrails=guardrails,
        tokens=token_tracker,
        scaffolding=scaffolding,
        context_filter=context_filter,
        transcript=transcript,
        system_prompt=system_prompt,
        scaffolds=scaffolds,
        scratchpad=scratchpad,
        advisor_usage=advisor_usage,
        conversation=[RlmMessage(role="user", content=resolved.request.instruction)],
        tool_client=tool_client,
        repl_tool_description=tool_description,
    )


def _build_guardrails(
    runtime: RlmRuntimeConfig,
    resolved: ResolvedRlmRequest,
) -> GuardrailState:
    configured = runtime.guardrails
    return GuardrailState(
        token_budget=resolved.token_budget,
        max_iterations=resolved.max_iterations,
        max_subcall_depth=configured.max_subcall_depth,
        budget_warning_pct=configured.budget_warning_pct,
        max_subcalls=configured.max_subcalls,
        max_budget_usd=resolved.max_budget_usd,
        billable_input_budget=configured.billable_input_budget,
    )


def _advisor_enabled(runtime: RlmRuntimeConfig) -> bool:
    return bool(runtime.advisor_client and runtime.advisor_config and runtime.advisor_config.enabled)


def _inject_repl_surface(
    *,
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    output: OutputCompletionState,
    runtime: RlmRuntimeConfig,
    resolved: ResolvedRlmRequest,
    transcript: list[TranscriptEntry],
    guardrails: GuardrailState,
    token_tracker: TokenTracker,
    enabled_subcalls: set[str],
    advisor_usage: AdvisorUsageAccumulator | None,
) -> Scratchpad | None:
    _inject_core_commands(
        repl=repl,
        scaffolds=scaffolds,
        output=output,
        runtime=runtime,
        resolved=resolved,
        enabled_subcalls=enabled_subcalls,
    )
    scratchpad = _inject_scratchpad(repl, scaffolds, runtime.scratchpad_path)
    _inject_subcalls(
        repl=repl,
        scaffolds=scaffolds,
        runtime=runtime,
        guardrails=guardrails,
        token_tracker=token_tracker,
    )
    _inject_parallel_and_template(repl, scaffolds, runtime)
    _inject_grep(repl, scaffolds)
    _inject_advisor(
        repl=repl,
        scaffolds=scaffolds,
        runtime=runtime,
        transcript=transcript,
        scratchpad=scratchpad,
        usage=advisor_usage,
    )
    return scratchpad


def _inject_core_commands(
    *,
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    output: OutputCompletionState,
    runtime: RlmRuntimeConfig,
    resolved: ResolvedRlmRequest,
    enabled_subcalls: set[str],
) -> None:
    final_var = make_final_var(repl, output_commit_required=output.commit_enabled)
    _inject_protected(repl, scaffolds, "FINAL_VAR", final_var)
    _inject_protected(repl, scaffolds, "FINAL", final_var)
    _inject_protected(repl, scaffolds, "context", resolved.request.instruction)
    output.inject_commit_command(repl, scaffolds)
    _inject_protected(repl, scaffolds, "SHOW_VARS", make_show_vars(repl))
    help_command = make_help(
        enabled_subcalls=enabled_subcalls,
        output_commit_enabled=output.commit_enabled,
        scratchpad_enabled=runtime.scratchpad_path is not None,
        template_enabled=runtime.template is not None,
        advisor_enabled=_advisor_enabled(runtime),
        max_iterations=resolved.max_iterations,
    )
    _inject_protected(repl, scaffolds, "HELP", help_command)


def _inject_protected(
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    name: str,
    value: object,
) -> None:
    repl.inject_object(name, value, protected=True)
    scaffolds[name] = value


def _inject_scratchpad(
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    path: str | None,
) -> Scratchpad | None:
    if path is None:
        return None
    scratchpad = Scratchpad(path=path)
    _inject_protected(repl, scaffolds, "NOTE", scratchpad.note)
    _inject_protected(repl, scaffolds, "RECALL", scratchpad.recall)
    return scratchpad


def _inject_subcalls(
    *,
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    runtime: RlmRuntimeConfig,
    guardrails: GuardrailState,
    token_tracker: TokenTracker,
) -> None:
    subcall_log = SubcallLog()
    if runtime.subcall_configs:
        client = runtime.subcall_client or runtime.client
        model = runtime.subcall_model or runtime.model_name
        callback = _subcall_accounting_callback(
            model=model,
            guardrails=guardrails,
            token_tracker=token_tracker,
        )
        functions = build_subcall_functions(
            configs=runtime.subcall_configs,
            client=client,
            model=model,
            token_callback=callback,
            subcall_log=subcall_log,
            template=runtime.template,
        )
        for name, function in functions.items():
            _inject_protected(repl, scaffolds, name, function)
    _inject_protected(repl, scaffolds, "SUBCALL_LOG", subcall_log)


def _subcall_accounting_callback(
    *,
    model: str,
    guardrails: GuardrailState,
    token_tracker: TokenTracker,
) -> Callable[[int, int], None]:
    lock = threading.Lock()

    def record(input_tokens: int, output_tokens: int) -> None:
        with lock:
            cost = estimate_cost_usd(model, input_tokens=input_tokens, output_tokens=output_tokens) or 0.0
            token_tracker.record_subcall(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )
            guardrails.record_subcall_tokens(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
            )

    return record


def _inject_parallel_and_template(
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    runtime: RlmRuntimeConfig,
) -> None:
    default_workers = runtime.execution.max_parallel_workers

    def bound_parallel(
        callables: list[Callable[[], Any]],
        max_workers: int | None = None,
    ) -> list[Any]:
        return parallel(callables, max_workers=max_workers or default_workers)

    _inject_protected(repl, scaffolds, "parallel", bound_parallel)
    if runtime.template is None:
        return
    template = runtime.template
    repl.inject_object("report", template)

    def bound_fill_parallel(
        generator: SectionGenerator,
        section_ids: list[str] | None = None,
        max_workers: int | None = None,
    ) -> list[Any]:
        return fill_template_parallel(
            template=template,
            generator=generator,
            section_ids=section_ids,
            max_workers=max_workers or default_workers,
        )

    _inject_protected(repl, scaffolds, "fill_parallel", bound_fill_parallel)


def _inject_grep(
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
) -> None:
    def grep(text: str, pattern: str, context: int = 3) -> str:
        lines = text.split("\n")
        matches: list[str] = []
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
        except re.error as error:
            return f"Invalid regex: {error}"
        for index, line in enumerate(lines):
            if compiled.search(line):
                start = max(0, index - context)
                end = min(len(lines), index + context + 1)
                chunk = "\n".join(
                    f"{'>' if line_index == index else ' '} {line_index + 1:4d}: {lines[line_index]}"
                    for line_index in range(start, end)
                )
                matches.append(chunk)
        if not matches:
            return f"No matches for /{pattern}/"
        return f"{len(matches)} match(es) for /{pattern}/:\n" + "\n---\n".join(matches)

    _inject_protected(repl, scaffolds, "grep", grep)


def _inject_advisor(
    *,
    repl: ReplEnvironment,
    scaffolds: dict[str, object],
    runtime: RlmRuntimeConfig,
    transcript: list[TranscriptEntry],
    scratchpad: Scratchpad | None,
    usage: AdvisorUsageAccumulator | None,
) -> None:
    if not _advisor_enabled(runtime):
        if usage is not None:
            raise ValueError("disabled advisor cannot have a usage accumulator")
        return
    if usage is None:
        raise ValueError("enabled advisor requires a usage accumulator")
    command = AdvisorCommand(
        runtime=runtime,
        transcript=transcript,
        scratchpad=scratchpad,
        usage=usage,
    )
    _inject_protected(repl, scaffolds, "ADVISOR", command)


class AdvisorCommand:
    """Bound advisor command with an explicit per-execution call budget."""

    def __init__(
        self,
        *,
        runtime: RlmRuntimeConfig,
        transcript: list[TranscriptEntry],
        scratchpad: Scratchpad | None,
        usage: AdvisorUsageAccumulator,
    ) -> None:
        if runtime.advisor_client is None or runtime.advisor_config is None:
            raise ValueError("advisor command requires client and configuration")
        self._runtime = runtime
        self._transcript = transcript
        self._scratchpad = scratchpad
        self._usage = usage

    def __call__(
        self,
        *,
        goal: str,
        problem: str,
        attempt: str | None = None,
    ) -> AdvisorResult:
        config = self._runtime.advisor_config
        client = self._runtime.advisor_client
        if config is None or client is None:
            raise RuntimeError("advisor command lost its configured dependencies")
        if self._usage.calls >= config.max_uses:
            return _advisor_budget_exhausted(config.max_uses)
        from aec_bench.adapters.advisor import default_advise

        request = AdvisorRequest(goal=goal, problem=problem, attempt=attempt)
        self._usage.begin_call()
        try:
            result = default_advise(
                request=request,
                context_messages=self._context_messages(config.context_window),
                client=client,
                model=config.model,
                max_response_tokens=config.max_response_tokens,
                adapter_context=(
                    "The executor is using an RLM template with "
                    "REPL commands (FILL, SUBMIT, CONTEXT, etc.). "
                    "Guide it on which commands and approach to use next."
                ),
            )
        except Exception:
            self._usage.mark_tokens_unknown()
            raise
        self._usage.record_result(result)
        self._record_trajectory(request, result, config.max_uses)
        return result

    def _context_messages(self, window: int) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        template = self._runtime.template
        if template is not None:
            status = template.get_status()
            messages.append(
                {
                    "role": "system",
                    "content": (
                        f"Template progress: {status.completed_sections}/{status.total_sections} "
                        f"sections complete. Completed: {status.completed}. "
                        f"Unlocked: {status.unlocked}. Pending: {status.pending}."
                    ),
                }
            )
        if self._scratchpad is not None:
            keys = self._scratchpad.recall()
            if keys:
                messages.append({"role": "system", "content": f"Scratchpad keys: {keys}"})
        messages.extend(
            {"role": entry.role.value, "content": entry.content}
            for entry in self._transcript[-window:]
            if entry.content
        )
        return messages

    def _record_trajectory(
        self,
        request: AdvisorRequest,
        result: AdvisorResult,
        max_uses: int,
    ) -> None:
        trajectory = self._runtime.trajectory
        if trajectory is None:
            return
        response = result.response
        trajectory.tool_result(
            "advisor",
            stdout=response.advice if response else "",
            metadata={
                "advisor": True,
                "advisor_input": {
                    "goal": request.goal,
                    "problem": request.problem,
                    "attempt": request.attempt,
                },
                "advisor_output": {
                    "advice": response.advice if response else "",
                    "suggested_action": response.suggested_action if response else "",
                    "confidence": response.confidence if response else 0.0,
                    "reasoning": response.reasoning if response else "",
                },
                "advisor_tokens": {
                    "input": result.input_tokens,
                    "output": result.output_tokens,
                },
                "advisor_call_number": self._usage.calls,
                "advisor_calls_remaining": max_uses - self._usage.calls,
            },
        )


def _advisor_budget_exhausted(max_uses: int) -> AdvisorResult:
    from aec_bench.adapters.advisor import AdvisorResult

    budget_message = f"Advisor budget exhausted ({max_uses}/{max_uses} calls used). Proceed on your own."
    return AdvisorResult(
        response=AdvisorResponse(
            advice=budget_message,
            suggested_action="continue",
            confidence=0.0,
            reasoning="max_uses reached",
        ),
        input_tokens=0,
        output_tokens=0,
        error="max_uses_exhausted",
    )


def load_repl_commands(
    repl: ReplEnvironment,
    *,
    workspace_path: str,
    template: ReportTemplate | None,
) -> None:
    """Load a task-owned repl_commands.py module into the prepared REPL."""
    workspace = Path(workspace_path)
    commands_path = workspace / "repl_commands.py"
    if not commands_path.exists():
        return
    spec = importlib.util.spec_from_file_location("repl_commands", str(commands_path))
    if spec is None or spec.loader is None:
        logger.warning("Could not load repl_commands.py — spec creation failed")
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "init_commands"):
        logger.info("repl_commands.py has no init_commands — skipping")
        return
    template_data = _read_optional_toml(workspace / "report_template.toml")
    validation_data = _read_optional_toml(workspace / "validation_rules.toml")
    module.init_commands(
        repl_env=repl,
        template=template,
        template_data=template_data,
        validation_data=validation_data,
        workspace=workspace_path,
    )
    logger.info("REPL commands loaded from %s", commands_path)


def _read_optional_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text()) if path.exists() else {}
