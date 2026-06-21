# ABOUTME: Structured evolver that uses PydanticAI for validated JSON responses.
# ABOUTME: Eliminates free-text JSON parsing by using tool_use / structured output.

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aec_bench.evolution.mutation import ParsedMutationResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response schema — PydanticAI enforces this via tool_use
# ---------------------------------------------------------------------------


class SkillAction(BaseModel):
    """A mutation action that creates or modifies a skill."""

    type: Literal["write_skill", "modify_skill", "delete_skill"]
    name: str
    description: str = ""
    discipline: str = ""
    body: str = ""


class PromptAction(BaseModel):
    """A mutation action that replaces the system prompt."""

    type: Literal["modify_prompt"]
    content: str


class EvolverResponse(BaseModel):
    """Structured response from the evolver LLM."""

    actions: list[SkillAction | PromptAction] = Field(default_factory=list)
    reasoning: str = ""


# ---------------------------------------------------------------------------
# Conversion to existing MutationAction format
# ---------------------------------------------------------------------------


def evolver_response_to_parsed(response: EvolverResponse) -> ParsedMutationResponse:
    """Convert a structured EvolverResponse to the existing ParsedMutationResponse format."""
    from aec_bench.evolution.mutation import MutationAction, ParsedMutationResponse

    actions: list[MutationAction] = []
    for action in response.actions:
        if isinstance(action, PromptAction):
            actions.append(
                MutationAction(
                    action_type="modify_prompt",
                    prompt_content=action.content,
                )
            )
        else:
            actions.append(
                MutationAction(
                    action_type=action.type,
                    skill_name=action.name,
                    skill_description=action.description or None,
                    skill_discipline=action.discipline or None,
                    skill_body=action.body or None,
                )
            )

    return ParsedMutationResponse(
        actions=tuple(actions),
        reasoning=response.reasoning,
    )


# ---------------------------------------------------------------------------
# Structured evolver call
# ---------------------------------------------------------------------------


def call_structured_evolver(
    *,
    model_name: str,
    system_prompt: str,
    analysis_prompt: str,
) -> ParsedMutationResponse:
    """Call the evolver LLM with structured output via PydanticAI.

    Uses PydanticAI's ``output_type`` to get validated JSON by construction,
    eliminating free-text JSON parsing, repair, and extraction.
    """
    from pydantic_ai import Agent

    model = _build_pydantic_model(model_name)

    agent = Agent(
        model,
        system_prompt=system_prompt,
        output_type=EvolverResponse,
        retries=2,
    )

    result = agent.run_sync(analysis_prompt)
    logger.info(
        "Structured evolver: %d actions, reasoning=%d chars",
        len(result.output.actions),
        len(result.output.reasoning),
    )

    return evolver_response_to_parsed(result.output)


# ---------------------------------------------------------------------------
# Scope-based action limits for tool-loop evolver
# ---------------------------------------------------------------------------

_SCOPE_ACTION_LIMITS: dict[str, int] = {
    "SKIP": 0,
    "MINIMAL": 1,
    "TARGETED": 3,
    "COMPREHENSIVE": 5,
}


# ---------------------------------------------------------------------------
# Two-phase evolver: investigate (tools) → propose (structured output)
# ---------------------------------------------------------------------------


def _build_investigation_system(workspace_root: Path | None = None) -> str:
    """Build the investigation system prompt from the evolution program.

    Loads the program document (workspace-level or default) and extracts
    the investigation protocol section. Falls back to a minimal prompt
    if the program can't be loaded.
    """
    from aec_bench.evolution.prompts import load_evolution_program

    try:
        program = load_evolution_program(workspace_root)
    except Exception:
        program = ""

    if program:
        return (
            "You are a diagnostic agent. Follow the Investigation Protocol "
            "and Failure Taxonomy from the evolution program below.\n\n" + program
        )

    return (
        "You are a diagnostic agent investigating why an engineering benchmark agent "
        "is failing. Use the provided tools to examine traces, field details, skills, "
        "and history. Then write a concise investigation report.\n\n"
        "Your report MUST contain:\n"
        "1. **Root cause** — What specifically went wrong\n"
        "2. **Failure category** — Classify the failure type\n"
        "3. **Prior attempts** — What was tried before\n"
        "4. **Recommendations** — Concrete changes to fix the failures"
    )


def call_structured_evolver_with_tools(
    *,
    model_name: str,
    system_prompt: str,
    analysis_brief: str,
    toolset: dict[str, Callable[..., str]],
    scope: str = "COMPREHENSIVE",
    workspace_root: Path | None = None,
) -> ParsedMutationResponse:
    """Two-phase evolver: investigate with tools, then propose structured mutations.

    Phase 1 (Investigate): A tool-using agent browses traces, skills, and history
    to produce a text diagnosis. No structured output required — just free text.

    Phase 2 (Propose): A single-shot structured agent takes the diagnosis + brief
    and produces an EvolverResponse with concrete actions.

    Actions are hard-clipped to the scope limit after Phase 2.
    """
    from pydantic_ai import Agent
    from pydantic_ai.tools import Tool
    from pydantic_ai.usage import UsageLimitExceeded, UsageLimits

    model = _build_pydantic_model(model_name)

    # --- Phase 1: Investigate (tool loop, free text output) ---
    # Wrap each tool to capture results in a log, so even if the budget is
    # hit before the model writes its summary, we have the raw findings.
    investigation_log: list[str] = []

    def _wrap_tool(name: str, fn: Callable[..., str]) -> Callable[..., str]:
        def wrapper(*args: object, **kwargs: object) -> str:
            result = fn(*args, **kwargs)
            investigation_log.append(f"## {name}({', '.join(str(a) for a in args)})\n{result}")
            return result

        wrapper.__name__ = fn.__name__ if hasattr(fn, "__name__") else name
        wrapper.__doc__ = fn.__doc__
        return wrapper

    tools = [Tool(_wrap_tool(name, fn), name=name) for name, fn in toolset.items()]

    investigation_system = _build_investigation_system(workspace_root)

    investigator: Agent[None, str] = Agent(
        model,
        system_prompt=investigation_system,
        output_type=str,
        tools=tools,
    )

    summary = ""
    try:
        investigation = investigator.run_sync(
            analysis_brief,
            usage_limits=UsageLimits(request_limit=15),
        )
        summary = investigation.output
    except UsageLimitExceeded:
        logger.warning(
            "Investigation hit request limit — %d tool calls captured",
            len(investigation_log),
        )

    logger.info(
        "Phase 1 (investigate): %d tool calls, summary=%d chars",
        len(investigation_log),
        len(summary),
    )

    # --- Phase 2: Propose (single-shot, structured output) ---
    # Always pass the raw investigation log — this is the real signal.
    # The model summary (if produced) is a bonus, not a replacement.
    raw_findings = "\n\n---\n\n".join(investigation_log) if investigation_log else "(no tool calls made)"

    proposal_parts = [
        "## Analysis Brief\n",
        analysis_brief,
        "\n\n## Raw Investigation Data\n",
        "The following are the actual tool call results from the investigation phase.\n",
        raw_findings,
    ]
    if summary:
        proposal_parts.extend(
            [
                "\n\n## Investigator Summary\n",
                summary,
            ]
        )
    proposal_parts.extend(
        [
            "\n\n## Your Task\n",
            "Based on the investigation data above, propose concrete mutations.\n"
            "Focus on the root cause. Quality over quantity.",
        ]
    )
    proposal_prompt = "\n".join(proposal_parts)

    proposer: Agent[None, EvolverResponse] = Agent(
        model,
        system_prompt=system_prompt,
        output_type=EvolverResponse,
        retries=2,
    )

    try:
        result = proposer.run_sync(proposal_prompt)
        output = result.output
    except Exception:
        logger.exception("Phase 2 (propose) failed — returning empty actions")
        output = EvolverResponse(actions=[], reasoning="Proposal phase failed")

    # Hard-clip actions to scope limit
    max_actions = _SCOPE_ACTION_LIMITS.get(scope, _SCOPE_ACTION_LIMITS["COMPREHENSIVE"])
    if len(output.actions) > max_actions:
        logger.info(
            "Clipping %d actions to scope limit %d (%s)",
            len(output.actions),
            max_actions,
            scope,
        )
        output = EvolverResponse(
            actions=output.actions[:max_actions],
            reasoning=output.reasoning,
        )

    logger.info(
        "Two-phase evolver (%s): %d actions (scope=%s, limit=%d), reasoning=%d chars",
        model_name,
        len(output.actions),
        scope,
        max_actions,
        len(output.reasoning),
    )

    return evolver_response_to_parsed(output)


# ---------------------------------------------------------------------------
# Model construction — reuses provider detection from RLM providers
# ---------------------------------------------------------------------------


def _build_pydantic_model(model_name: str) -> object:
    """Build a PydanticAI model object from the model name.

    Detects provider from the model name (Bedrock, Azure, Anthropic, Together) and
    constructs the appropriate PydanticAI model. Mirrors the logic in
    ``adapters.rlm.providers`` but without RLM-specific concerns.
    """
    from aec_bench.adapters.rlm.providers import resolve_pydantic_provider

    provider = resolve_pydantic_provider(model_name)

    if provider == "bedrock":
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        region = os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")
        kwargs: dict[str, str] = {}
        if region:
            kwargs["region_name"] = region
        return BedrockConverseModel(
            model_name,
            provider=BedrockProvider(**kwargs),
        )

    if provider == "azure":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.azure import AzureProvider

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        api_version = os.environ.get(
            "AZURE_OPENAI_API_VERSION",
            os.environ.get("AGENT_API_VERSION", "2024-10-21"),
        )
        return OpenAIChatModel(
            model_name,
            provider=AzureProvider(**_azure_provider_kwargs(endpoint, api_key, api_version)),
        )

    if provider == "together":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = os.environ.get("TOGETHER_API_KEY", "")
        if not api_key:
            msg = "required environment variable is not set: TOGETHER_API_KEY"
            raise RuntimeError(msg)
        return OpenAIChatModel(
            _strip_together_prefix(model_name),
            provider=OpenAIProvider(base_url="https://api.together.ai/v1", api_key=api_key),
        )

    # "anthropic" or "auto" — let PydanticAI infer from model string
    return model_name


def _strip_together_prefix(model_name: str) -> str:
    prefix = "together:"
    if model_name.lower().startswith(prefix):
        return model_name[len(prefix) :]
    return model_name


def _azure_provider_kwargs(endpoint: str, api_key: str, api_version: str) -> dict[str, str]:
    kwargs = {
        "azure_endpoint": endpoint,
        "api_key": api_key,
    }
    if api_version and not endpoint.rstrip("/").lower().endswith("/openai/v1"):
        kwargs["api_version"] = api_version
    return kwargs
