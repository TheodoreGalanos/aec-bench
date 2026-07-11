# ABOUTME: Local tool-loop client and executor for running tool-using agents without containers.
# ABOUTME: PydanticAI-based ToolLoopClient (Bedrock/Azure/Anthropic/Together) + bash ToolExecutor.

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic_ai import RunContext

from aec_bench.adapters.advisor import default_advise
from aec_bench.adapters.pydantic_ai_runtime import (
    agent_run_output,
    run_agent_sync_with_streaming_fallback,
)
from aec_bench.adapters.rlm.client import RlmClient
from aec_bench.adapters.tool_loop import (
    ToolExecutionResult,
    ToolLoopCompletionResponse,
    ToolLoopRequest,
)
from aec_bench.contracts.advisor import AdvisorConfig, AdvisorRequest

logger = logging.getLogger(__name__)


def completion_from_workspace_output(workspace: str) -> ToolLoopCompletionResponse | None:
    """Recover a completed response when the agent wrote the requested output file."""
    if not workspace:
        return None
    output_path = Path(workspace) / "output.md"
    try:
        output_text = output_path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not output_text.strip():
        return None
    return ToolLoopCompletionResponse(output_text=output_text, done=True)


# ---------------------------------------------------------------------------
# PydanticAI-compatible advisor tool — routes advisor calls through default_advise
# ---------------------------------------------------------------------------


class PydanticAiAdvisorTool:
    """Callable advisor tool for registration as a PydanticAI native tool.

    Encapsulates the budget, stats tracking, and fallback logic required by the
    advisor contract. Invoking an instance dispatches to ``default_advise`` and
    returns the advisor's JSON response for the executor model to consume.
    Calls past ``config.max_uses`` return a graceful exhaustion message.
    """

    def __init__(self, *, client: RlmClient, config: AdvisorConfig) -> None:
        self._client = client
        self._config = config
        self._calls = 0
        self._input_tokens = 0
        self._output_tokens = 0

    def __call__(self, goal: str, problem: str) -> str:
        if self._calls >= self._config.max_uses:
            return json.dumps(
                {
                    "advice": (
                        f"Advisor budget exhausted ({self._config.max_uses}/"
                        f"{self._config.max_uses} calls used). Proceed on your own."
                    ),
                    "suggested_action": "continue",
                    "confidence": 0.0,
                    "reasoning": "max_uses reached",
                }
            )

        result = default_advise(
            request=AdvisorRequest(goal=goal, problem=problem),
            context_messages=[],
            client=self._client,
            model=self._config.model,
            max_response_tokens=self._config.max_response_tokens,
            adapter_context=("The executor is using a tool-loop adapter with bash and search tools."),
        )

        if result.error is None:
            self._calls += 1
            self._input_tokens += result.input_tokens
            self._output_tokens += result.output_tokens

        if result.response:
            return json.dumps(
                {
                    "advice": result.response.advice,
                    "suggested_action": result.response.suggested_action,
                    "confidence": result.response.confidence,
                    "reasoning": result.response.reasoning,
                }
            )
        return json.dumps(
            {
                "advice": "Advisor unavailable",
                "suggested_action": "continue",
                "confidence": 0.0,
                "reasoning": "",
            }
        )

    def usage(self) -> tuple[int, int, int]:
        """Return (calls_made, input_tokens, output_tokens)."""
        return (self._calls, self._input_tokens, self._output_tokens)

    def call_with_messages(self, context_messages: list[dict[str, str]]) -> str:
        """Invoke the advisor using an explicit transcript slice (Anthropic-style).

        Unlike ``__call__(goal, problem)``, this path mirrors Anthropic's native
        advisor tool: the executor just signals timing, and the full
        conversation history is handed over to the advisor model.
        """
        if self._calls >= self._config.max_uses:
            return json.dumps(
                {
                    "advice": (
                        f"Advisor budget exhausted ({self._config.max_uses}/"
                        f"{self._config.max_uses} calls used). Proceed on your own."
                    ),
                    "suggested_action": "continue",
                    "confidence": 0.0,
                    "reasoning": "max_uses reached",
                }
            )

        result = default_advise(
            request=AdvisorRequest(goal="", problem=""),
            context_messages=context_messages,
            client=self._client,
            model=self._config.model,
            max_response_tokens=self._config.max_response_tokens,
            adapter_context=(
                "You are the advisor for an AI agent using bash tool calls to solve "
                "an engineering task. Read the transcript above and give concise "
                "strategic guidance on what the agent should do next."
            ),
        )

        if result.error is None:
            self._calls += 1
            self._input_tokens += result.input_tokens
            self._output_tokens += result.output_tokens

        if result.response:
            return json.dumps(
                {
                    "advice": result.response.advice,
                    "suggested_action": result.response.suggested_action,
                    "confidence": result.response.confidence,
                    "reasoning": result.response.reasoning,
                }
            )
        return json.dumps(
            {
                "advice": "Advisor unavailable",
                "suggested_action": "continue",
                "confidence": 0.0,
                "reasoning": "",
            }
        )


def pydantic_ai_messages_to_advisor_context(messages: list[Any]) -> list[dict[str, str]]:
    """Convert a pydantic-ai ``ModelMessage`` sequence into advisor context.

    System prompts are dropped — the advisor has its own. User prompts,
    assistant text, tool calls and tool results become labelled entries the
    advisor model can read directly.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )

    result: list[dict[str, str]] = []
    for msg in messages:
        if isinstance(msg, ModelRequest):
            for part in msg.parts:
                if isinstance(part, SystemPromptPart):
                    continue
                if isinstance(part, UserPromptPart):
                    result.append({"role": "user", "content": str(part.content)})
                elif isinstance(part, ToolReturnPart):
                    payload = "" if part.content is None else str(part.content)
                    result.append({"role": "tool", "content": f"[{part.tool_name}] {payload}"})
        elif isinstance(msg, ModelResponse):
            for part in msg.parts:
                if isinstance(part, TextPart):
                    if part.content:
                        result.append({"role": "assistant", "content": part.content})
                elif isinstance(part, ToolCallPart):
                    args = part.args if isinstance(part.args, dict) else {}
                    try:
                        args_repr = json.dumps(args, ensure_ascii=False)
                    except (TypeError, ValueError):
                        args_repr = str(args)
                    result.append(
                        {
                            "role": "assistant",
                            "content": f"Calling {part.tool_name}({args_repr})",
                        }
                    )
    return result


# ---------------------------------------------------------------------------
# Trajectory emission — walks pydantic-ai messages and writes JSONL entries
# ---------------------------------------------------------------------------


def emit_pydantic_ai_messages_to_trajectory(
    messages: list[Any],
    writer: Any,
) -> None:
    """Emit a sequence of pydantic-ai ``ModelMessage`` objects to a TrajectoryWriter.

    Step 0 holds the initial system/user prompts. Each subsequent
    ``ModelResponse`` begins a new step, during which assistant text
    and tool-call parts are recorded. ``ToolReturnPart`` entries in the
    following ``ModelRequest`` are attributed to the same step so the
    behavioral classifier groups call and result together.
    """
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ToolCallPart,
        ToolReturnPart,
        UserPromptPart,
    )

    for message in messages:
        if isinstance(message, ModelRequest):
            for part in message.parts:
                if isinstance(part, SystemPromptPart):
                    writer.system(str(part.content))
                elif isinstance(part, UserPromptPart):
                    writer.user(str(part.content))
                elif isinstance(part, ToolReturnPart):
                    output = "" if part.content is None else str(part.content)
                    writer.tool_result(tool_name=part.tool_name, stdout=output)
            continue
        if isinstance(message, ModelResponse):
            writer.new_step()
            for part in message.parts:
                if isinstance(part, TextPart):
                    if part.content:
                        writer.thinking(part.content)
                elif isinstance(part, ToolCallPart):
                    args = part.args if isinstance(part.args, dict) else {}
                    command = args.get("command", "") if args else ""
                    writer.tool_call(
                        tool_name=part.tool_name,
                        command=str(command),
                        arguments=args or None,
                    )


# ---------------------------------------------------------------------------
# Bash tool executor — runs commands in the workspace directory
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BashToolExecutor:
    """Executes bash commands in a workspace directory."""

    workspace: str
    timeout: int = 120

    def execute(self, tool_name: str, arguments: dict[str, Any]) -> ToolExecutionResult:
        """Run a bash command and return the output."""
        command = arguments.get("command", "")
        if not command:
            return ToolExecutionResult(output_text="", error_message="No command provided")

        try:
            result = subprocess.run(
                ["bash", "-c", command],
                cwd=self.workspace,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return ToolExecutionResult(output_text=output[:10000])
        except subprocess.TimeoutExpired:
            return ToolExecutionResult(
                output_text="",
                error_message=f"Command timed out after {self.timeout}s",
            )
        except Exception as exc:
            return ToolExecutionResult(
                output_text="",
                error_message=f"Command failed: {exc}",
            )


# ---------------------------------------------------------------------------
# PydanticAI-based ToolLoopClient — converts between our protocol and PydanticAI
# ---------------------------------------------------------------------------


class PydanticAiToolLoopClient:
    """ToolLoopClient backed by a real PydanticAI Agent with bash tool.

    The Agent has bash registered as a native tool and runs the full
    tool loop internally via run_sync(). Each next_turn() call runs
    the complete multi-turn conversation and returns the final result
    as done=True. The external ToolLoopAdapter loop exits after one call.

    Reuses the RLM provider's model building and cache configuration.
    """

    def __init__(
        self,
        model_name: str,
        workspace: str = "",
        *,
        advisor_client: RlmClient | None = None,
        advisor_config: AdvisorConfig | None = None,
        trajectory_writer: Any | None = None,
        stream_mode: str = "auto",
        native_tools: list[Callable[..., str]] | None = None,
        enable_bash: bool = True,
    ) -> None:
        from pydantic_ai import Agent

        from aec_bench.adapters.rlm.providers import (
            _build_model_settings,
            _build_pydantic_model,
            resolve_pydantic_provider,
        )

        self._model_name = model_name
        self._workspace = workspace
        self._trajectory_writer = trajectory_writer
        self._stream_mode = stream_mode

        provider = resolve_pydantic_provider(model_name)
        pydantic_model = _build_pydantic_model(model_name, provider)
        model_settings = _build_model_settings(provider, cache=True)

        # Build the agent with bash as a native tool
        self._agent = Agent(
            pydantic_model,
            system_prompt="",
            retries=2,
            model_settings=model_settings,
        )

        if enable_bash:
            executor = BashToolExecutor(workspace=workspace)

            @self._agent.tool_plain
            def bash(command: str) -> str:
                """Execute a bash command in the workspace and return stdout/stderr."""
                result = executor.execute("bash", {"command": command})
                if result.error_message:
                    return f"Error: {result.error_message}"
                return result.output_text

        for native_tool in native_tools or []:
            self._agent.tool_plain(native_tool)

        # Register advisor as a native tool when the advisor client + config are provided.
        # Mirrors Anthropic's native advisor tool shape: zero parameters, context is
        # the full running transcript. PydanticAI's RunContext gives us the messages
        # seen so far; we convert those to advisor context at call time.
        self._advisor_tool: PydanticAiAdvisorTool | None = None
        if advisor_client is not None and advisor_config is not None and advisor_config.enabled:
            self._advisor_tool = PydanticAiAdvisorTool(
                client=advisor_client,
                config=advisor_config,
            )

            @self._agent.tool
            def advisor(ctx: RunContext[None]) -> str:
                """Consult a stronger advisor model for strategic guidance.

                Takes NO parameters — your full conversation history is
                automatically shared with the advisor. Returns JSON with
                advice, suggested_action, confidence, reasoning.
                """
                assert self._advisor_tool is not None
                context = pydantic_ai_messages_to_advisor_context(list(ctx.messages))
                return self._advisor_tool.call_with_messages(context)

        logger.info(
            "PydanticAI tool loop client: model=%s provider=%s cache=True workspace=%s advisor=%s",
            model_name,
            provider,
            workspace,
            "on" if self._advisor_tool is not None else "off",
        )

    def advisor_usage(self) -> tuple[int, int, int] | None:
        """Return (calls, input_tokens, output_tokens), or None if advisor unwired."""
        if self._advisor_tool is None:
            return None
        return self._advisor_tool.usage()

    def next_turn(self, request: ToolLoopRequest) -> ToolLoopCompletionResponse:
        """Run the full tool loop via PydanticAI and return the final result.

        PydanticAI handles all tool calls internally. The ToolLoopAdapter's
        external loop sees done=True on the first call and exits.
        """
        try:
            return self._run_agent(request)
        except Exception as exc:
            fallback = completion_from_workspace_output(self._workspace)
            if fallback is not None:
                logger.warning(
                    "PydanticAI tool loop failed after writing output.md; recovering workspace output: %s",
                    exc,
                )
                return fallback
            logger.exception("PydanticAI tool loop client error: %s", exc)
            return ToolLoopCompletionResponse(
                error_message=str(exc),
                done=True,
            )

    def _run_agent(self, request: ToolLoopRequest) -> ToolLoopCompletionResponse:
        """Run the full agent loop — PydanticAI handles tool calls internally."""
        from pydantic_ai.usage import UsageLimits

        # Set system prompt
        self._agent._system_prompts = (  # noqa: SLF001
            [request.system_prompt] if request.system_prompt else []
        )

        # Run the full agent loop with a request limit to prevent runaway
        max_turns = int(request.configuration.get("max_turns", 30)) if request.configuration else 30
        result = run_agent_sync_with_streaming_fallback(
            self._agent,
            request.instruction,
            usage_limits=UsageLimits(request_limit=max_turns),
            stream_mode=self._stream_mode,
        )

        output = agent_run_output(result)
        usage = result.usage()
        output_text = output if isinstance(output, str) else str(output)

        if self._trajectory_writer is not None:
            try:
                emit_pydantic_ai_messages_to_trajectory(
                    list(result.all_messages()),
                    self._trajectory_writer,
                )
            except Exception:
                logger.warning("Failed to emit pydantic-ai messages to trajectory", exc_info=True)

        return ToolLoopCompletionResponse(
            output_text=output_text,
            done=True,
            usage_input_tokens=usage.input_tokens or 0,
            usage_output_tokens=usage.output_tokens or 0,
            usage_cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
            usage_cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
        )
