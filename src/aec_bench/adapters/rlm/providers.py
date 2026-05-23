# ABOUTME: Real RlmClient implementations wrapping PydanticAI provider models.
# ABOUTME: Handles provider detection, caching flags, and message conversion.

from __future__ import annotations

import logging
import os
from typing import Any

from aec_bench.adapters.rlm.client import (
    RlmCompletionResponse,
    RlmMessage,
    ToolCall,
)

logger = logging.getLogger(__name__)

# Bedrock model name prefixes (region-qualified and plain)
_BEDROCK_PREFIXES = (
    "anthropic.claude",
    "au.anthropic.",
    "us.anthropic.",
    "eu.anthropic.",
    "ap.anthropic.",
    "amazon.",
    "us.amazon.",
    "meta.llama",
    "us.meta.",
    "mistral.",
    "us.mistral.",
    "cohere.",
    "us.cohere.",
    "ai21.",
    "us.ai21.",
)

# Azure OpenAI model name prefixes
_AZURE_PREFIXES = ("gpt-", "gpt4", "o1-", "o3-", "o4-")

# Direct Anthropic model name prefixes
_ANTHROPIC_PREFIXES = ("claude-",)


def detect_provider(model_name: str) -> str:
    """Detect the provider from the model name string.

    Returns one of: ``"bedrock"``, ``"azure"``, ``"anthropic"``, ``"auto"``.
    """
    lower = model_name.lower()
    if any(lower.startswith(p) for p in _BEDROCK_PREFIXES):
        return "bedrock"
    if any(lower.startswith(p) for p in _AZURE_PREFIXES):
        return "azure"
    if any(lower.startswith(p) for p in _ANTHROPIC_PREFIXES):
        return "anthropic"
    return "auto"


class PydanticAiRlmClient:
    """RlmClient implementation backed by PydanticAI Agent.

    Uses PydanticAI's multi-provider support with optional prompt caching.
    Requires ``pydantic-ai`` to be installed (optional dependency).
    """

    def __init__(
        self,
        *,
        model: Any,
        model_settings: Any | None = None,
    ) -> None:
        from pydantic_ai import Agent

        self._model_obj = model
        self._model_settings = model_settings
        self._agent = Agent(
            model,
            system_prompt="",
            retries=2,
            model_settings=model_settings,
        )

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        """Run a single LLM call and return an RlmCompletionResponse."""
        # Build the user prompt from the last user message
        user_prompt = ""
        for msg in reversed(messages):
            if msg.role == "user":
                user_prompt = msg.content
                break

        # Build message history (all but the last user message)
        from pydantic_ai.messages import (
            ModelRequest,
            ModelResponse,
            TextPart,
            UserPromptPart,
        )

        history: list[ModelRequest | ModelResponse] = []
        for msg in messages[:-1] if len(messages) > 1 else []:
            if msg.role == "user":
                history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
            elif msg.role == "assistant":
                history.append(ModelResponse(parts=[TextPart(content=msg.content)]))

        # Override the system prompt for this call
        self._agent._system_prompts = (  # noqa: SLF001
            [system_prompt] if system_prompt else []
        )

        try:
            model_settings = self._model_settings
            if temperature is not None:
                base_settings = dict(self._model_settings or {})
                model_settings = base_settings | {"temperature": temperature}

            result = self._agent.run_sync(
                user_prompt,
                message_history=history if history else None,
                model_settings=model_settings,
            )

            usage = result.usage()
            return RlmCompletionResponse(
                output_text=result.output,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
            )

        except Exception as exc:
            logger.warning("Provider error: %s", exc)
            return RlmCompletionResponse(
                error_message=str(exc),
            )

    def generate_with_tools(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        tool_name: str,
        tool_description: str,
        tool_parameters_schema: dict[str, Any],
    ) -> RlmCompletionResponse:
        """Run a single LLM call with a tool definition and return the response.

        Uses PydanticAI's ``Model.request()`` directly (not Agent) so we can
        pass an explicit ``ToolDefinition`` and inspect the raw response parts
        for both text and tool-call content.
        """
        import asyncio

        from pydantic_ai.messages import (
            ModelRequest,
            SystemPromptPart,
            TextPart,
            ToolCallPart,
            ToolReturnPart,
            UserPromptPart,
        )
        from pydantic_ai.messages import (
            ModelResponse as PydanticModelResponse,
        )
        from pydantic_ai.models import ModelRequestParameters, infer_model
        from pydantic_ai.tools import ToolDefinition

        # Resolve the model object (handles both Model instances and strings)
        resolved_model = infer_model(self._model_obj)

        # Build the PydanticAI message list from RlmMessages
        pydantic_messages: list[ModelRequest | PydanticModelResponse] = []

        # Prepend system prompt as the first request
        if system_prompt:
            pydantic_messages.append(ModelRequest(parts=[SystemPromptPart(content=system_prompt)]))

        # Convert RlmMessages to PydanticAI message types, merging
        # consecutive assistant + tool_call into a single ModelResponse.
        i = 0
        while i < len(messages):
            msg = messages[i]

            if msg.role == "user":
                pydantic_messages.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))

            elif msg.role == "assistant":
                # Check if the next message is a tool_call — merge them
                parts: list[TextPart | ToolCallPart] = [TextPart(content=msg.content)]
                if i + 1 < len(messages) and messages[i + 1].role == "tool_call":
                    next_msg = messages[i + 1]
                    parts.append(
                        ToolCallPart(
                            tool_name=next_msg.tool_name or tool_name,
                            args={"code": next_msg.content},
                            tool_call_id=next_msg.tool_call_id or "",
                        )
                    )
                    i += 1  # skip the tool_call message
                pydantic_messages.append(PydanticModelResponse(parts=parts))

            elif msg.role == "tool_call":
                # Standalone tool_call without preceding assistant text
                pydantic_messages.append(
                    PydanticModelResponse(
                        parts=[
                            ToolCallPart(
                                tool_name=msg.tool_name or tool_name,
                                args={"code": msg.content},
                                tool_call_id=msg.tool_call_id or "",
                            )
                        ]
                    )
                )

            elif msg.role == "tool_result":
                pydantic_messages.append(
                    ModelRequest(
                        parts=[
                            ToolReturnPart(
                                tool_name=msg.tool_name or tool_name,
                                content=msg.content,
                                tool_call_id=msg.tool_call_id or "",
                            )
                        ]
                    )
                )

            i += 1

        # Build the tool definition
        tool_def = ToolDefinition(
            name=tool_name,
            description=tool_description,
            parameters_json_schema=tool_parameters_schema,
        )

        # Build request parameters with the tool
        request_params = ModelRequestParameters(
            function_tools=[tool_def],
            allow_text_output=True,
        )

        try:
            loop = asyncio.new_event_loop()
            try:
                response = loop.run_until_complete(
                    resolved_model.request(
                        pydantic_messages,
                        self._model_settings,
                        request_params,
                    )
                )
            finally:
                loop.close()

            # Extract text and tool call from the response parts
            output_text = ""
            result_tool_call: ToolCall | None = None

            for part in response.parts:
                if isinstance(part, TextPart):
                    output_text += part.content
                elif isinstance(part, ToolCallPart):
                    args_dict = part.args_as_dict()
                    code = args_dict.get("code", "")
                    result_tool_call = ToolCall(
                        name=part.tool_name,
                        code=code,
                        call_id=part.tool_call_id,
                    )

            usage = response.usage
            return RlmCompletionResponse(
                output_text=output_text,
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
                cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
                tool_call=result_tool_call,
            )

        except Exception as exc:
            logger.warning("Provider error in generate_with_tools: %s", exc)
            return RlmCompletionResponse(
                error_message=str(exc),
            )


def _build_pydantic_model(
    model_name: str,
    provider: str,
) -> Any:
    """Build the PydanticAI model object for the detected provider."""
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
            provider=AzureProvider(
                azure_endpoint=endpoint,
                api_version=api_version,
                api_key=api_key,
            ),
        )

    # "anthropic" or "auto" — let PydanticAI infer from model string
    return model_name


def _build_model_settings(
    provider: str,
    cache: bool,
) -> Any | None:
    """Build provider-specific model settings (primarily for caching)."""
    if not cache:
        return None

    if provider == "bedrock":
        try:
            from pydantic_ai.models.bedrock import BedrockModelSettings

            return BedrockModelSettings(
                bedrock_cache_instructions=True,
                bedrock_cache_tool_definitions=True,
                bedrock_cache_messages=True,
            )
        except ImportError:
            return None

    if provider in ("anthropic", "auto"):
        try:
            from pydantic_ai.models.anthropic import AnthropicModelSettings

            return AnthropicModelSettings(
                anthropic_cache_instructions=True,
                anthropic_cache_tool_definitions=True,
                anthropic_cache_messages=True,
            )
        except ImportError:
            return None

    return None


def make_rlm_client(
    model_name: str,
    *,
    cache: bool = True,
) -> PydanticAiRlmClient:
    """Create an RlmClient for the given model name.

    Detects the provider from the model name, builds the appropriate
    PydanticAI model object, and wraps it in a ``PydanticAiRlmClient``.

    Requires ``pydantic-ai`` to be installed.
    """
    provider = detect_provider(model_name)
    pydantic_model = _build_pydantic_model(model_name, provider)
    settings = _build_model_settings(provider, cache)

    logger.info(
        "RlmClient: model=%s provider=%s cache=%s",
        model_name,
        provider,
        cache,
    )

    return PydanticAiRlmClient(
        model=pydantic_model,
        model_settings=settings,
    )
