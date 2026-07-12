# ABOUTME: Real RlmClient implementations wrapping PydanticAI provider models.
# ABOUTME: Handles provider detection, caching flags, and message conversion.

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from typing import Any, TypedDict

from aec_bench.adapters.pydantic_ai_runtime import (
    agent_run_output,
    request_model_response,
    run_agent_sync_with_streaming_fallback,
)
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

# Together OpenAI-compatible model prefix
_TOGETHER_PREFIX = "together:"
_TOGETHER_BASE_URL = "https://api.together.ai/v1"
_BEDROCK_EXPLICIT_PREFIX = "bedrock:"


def detect_provider(model_name: str) -> str:
    """Detect the provider from the model name string.

    Returns one of: ``"bedrock"``, ``"azure"``, ``"anthropic"``,
    ``"together"``, ``"auto"``.
    """
    lower = model_name.lower()
    if lower.startswith(_BEDROCK_EXPLICIT_PREFIX):
        return "bedrock"
    if lower.startswith(_TOGETHER_PREFIX):
        return "together"
    if any(lower.startswith(p) for p in _BEDROCK_PREFIXES):
        return "bedrock"
    if any(lower.startswith(p) for p in _AZURE_PREFIXES):
        return "azure"
    if any(lower.startswith(p) for p in _ANTHROPIC_PREFIXES):
        return "anthropic"
    return "auto"


def resolve_pydantic_provider(model_name: str, env: Mapping[str, str] | None = None) -> str:
    """Resolve the PydanticAI provider, using Azure credentials for deployment names."""
    source = env if env is not None else os.environ
    provider = detect_provider(model_name)
    if provider == "auto" and ":" in model_name:
        return "auto"
    if provider == "auto" and _has_azure_credentials(source):
        return "azure"
    return provider


def preflight_pydantic_model_configuration(model_name: str) -> None:
    """Validate the routed provider configuration without making a model request."""
    provider = resolve_pydantic_provider(model_name)
    if provider == "bedrock":
        _strip_bedrock_prefix(model_name)
        _preflight_bedrock_configuration()
        return
    model = _build_pydantic_model(model_name, provider)
    if isinstance(model, str):
        from pydantic_ai.models import infer_model

        infer_model(model)


def _preflight_bedrock_configuration() -> None:
    """Check Bedrock's local configuration without creating a network-capable client."""
    if _resolve_aws_credential_source_configuration() is None:
        msg = (
            "AWS credential source is not configured; configure a Bedrock bearer token, "
            "static credentials, a profile or shared config, web identity, container "
            "credentials, or another resolvable AWS credential-chain source"
        )
        raise RuntimeError(msg)

    if not _resolve_aws_region_configuration():
        msg = "AWS region is not configured; set AWS_REGION or AWS_DEFAULT_REGION, or configure a profile region"
        raise RuntimeError(msg)


def _resolve_aws_credential_source_configuration() -> str | None:
    """Return the configured AWS credential source without using the credentials.

    Container credentials are recognized by their standard URI configuration so
    preflight never calls the container endpoint. Other supported sources use
    Botocore's credential resolver, with metadata retries bounded to prevent an
    unavailable instance-metadata endpoint from delaying local validation.
    """
    if os.environ.get("AWS_BEARER_TOKEN_BEDROCK", ""):
        return "bedrock-bearer-token"
    if os.environ.get("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI", "") or os.environ.get(
        "AWS_CONTAINER_CREDENTIALS_FULL_URI", ""
    ):
        return "container-role"

    try:
        session = _new_botocore_session()
        session.set_config_variable("metadata_service_timeout", 1)
        session.set_config_variable("metadata_service_num_attempts", 1)
        credentials = session.get_credentials()
    except Exception as exc:
        msg = "AWS credential source configuration could not be resolved"
        raise RuntimeError(msg) from exc

    if credentials is None:
        return None
    return str(getattr(credentials, "method", "aws-default-chain"))


def _resolve_aws_region_configuration() -> str | None:
    """Return the AWS region selected by environment or Botocore config."""
    region = os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")
    if region:
        return region
    try:
        configured_region = _new_botocore_session().get_config_variable("region")
    except Exception as exc:
        msg = "AWS region configuration could not be resolved"
        raise RuntimeError(msg) from exc
    return str(configured_region) if configured_region else None


def _new_botocore_session() -> Any:
    """Create Botocore lazily so non-Bedrock users do not require its dependency."""
    import botocore.session  # type: ignore[import-untyped]

    return botocore.session.Session()


def _has_azure_credentials(env: Mapping[str, str]) -> bool:
    return bool(env.get("AZURE_OPENAI_ENDPOINT", "") and env.get("AZURE_OPENAI_API_KEY", ""))


def _is_azure_v1_endpoint(endpoint: str) -> bool:
    return endpoint.rstrip("/").lower().endswith("/openai/v1")


def _strip_together_prefix(model_name: str) -> str:
    if model_name.lower().startswith(_TOGETHER_PREFIX):
        return model_name[len(_TOGETHER_PREFIX) :]
    return model_name


def _strip_bedrock_prefix(model_name: str) -> str:
    stripped = (
        model_name[len(_BEDROCK_EXPLICIT_PREFIX) :]
        if model_name.lower().startswith(_BEDROCK_EXPLICIT_PREFIX)
        else model_name
    )
    if not stripped.strip():
        raise ValueError("Bedrock model id must not be blank")
    return stripped


class _AzureProviderKwargs(TypedDict):
    azure_endpoint: str
    api_key: str
    api_version: str


def _azure_provider_kwargs(endpoint: str, api_key: str, api_version: str) -> _AzureProviderKwargs:
    return {
        "azure_endpoint": endpoint,
        "api_key": api_key,
        "api_version": api_version,
    }


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
        stream_mode: str = "auto",
    ) -> None:
        from pydantic_ai import Agent

        self._model_obj = model
        self._model_settings = model_settings
        self._stream_mode = stream_mode
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
        self._agent._system_prompts = (system_prompt,) if system_prompt else ()  # noqa: SLF001

        try:
            model_settings = self._model_settings
            if temperature is not None:
                base_settings = dict(self._model_settings or {})
                model_settings = base_settings | {"temperature": temperature}

            result = run_agent_sync_with_streaming_fallback(
                self._agent,
                user_prompt,
                message_history=history if history else None,
                model_settings=model_settings,
                stream_mode=self._stream_mode,
            )

            output = agent_run_output(result)
            usage = result.usage()
            return RlmCompletionResponse(
                output_text=str(output),
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
            response = request_model_response(
                resolved_model,
                messages=pydantic_messages,
                model_settings=self._model_settings,
                model_request_parameters=request_params,
                stream_mode=self._stream_mode,
            )

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
            _strip_bedrock_prefix(model_name),
            provider=BedrockProvider(**kwargs),
        )

    if provider == "azure":
        from pydantic_ai.models.openai import OpenAIChatModel

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY", "")
        api_version = os.environ.get(
            "AZURE_OPENAI_API_VERSION",
            os.environ.get("AGENT_API_VERSION", "2024-10-21"),
        )
        if _is_azure_v1_endpoint(endpoint):
            from pydantic_ai.providers.openai import OpenAIProvider

            return OpenAIChatModel(
                model_name,
                provider=OpenAIProvider(base_url=endpoint, api_key=api_key),
            )

        from pydantic_ai.providers.azure import AzureProvider

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
            provider=OpenAIProvider(base_url=_TOGETHER_BASE_URL, api_key=api_key),
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
    stream_mode: str = "auto",
) -> PydanticAiRlmClient:
    """Create an RlmClient for the given model name.

    Detects the provider from the model name, builds the appropriate
    PydanticAI model object, and wraps it in a ``PydanticAiRlmClient``.

    Requires ``pydantic-ai`` to be installed.
    """
    provider = resolve_pydantic_provider(model_name)
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
        stream_mode=stream_mode,
    )
