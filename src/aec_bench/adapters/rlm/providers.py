# ABOUTME: Real RlmClient implementations wrapping PydanticAI provider models.
# ABOUTME: Handles provider detection, caching flags, and message conversion.

from __future__ import annotations

import logging
import os
from typing import Any, TypedDict

from aec_bench.adapters.pydantic_ai_runtime import (
    agent_run_output,
    agent_run_usage,
    request_model_response,
    run_agent_sync_with_streaming_fallback,
)
from aec_bench.adapters.rlm.client import (
    RlmCompletionResponse,
    RlmMessage,
    ToolCall,
)
from aec_bench.model_routing import detect_provider as detect_provider
from aec_bench.model_routing import resolve_pydantic_provider as resolve_pydantic_provider

logger = logging.getLogger(__name__)

# Together OpenAI-compatible model prefix
_TOGETHER_PREFIX = "together:"
_TOGETHER_BASE_URL = "https://api.together.ai/v1"
_BEDROCK_EXPLICIT_PREFIX = "bedrock:"


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
    import botocore.session

    return botocore.session.Session()


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
            usage = agent_run_usage(result)
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
        from pydantic_ai.models import infer_model

        resolved_model = infer_model(self._model_obj)
        pydantic_messages = _build_tool_messages(
            messages,
            system_prompt=system_prompt,
            default_tool_name=tool_name,
        )
        request_params = _tool_request_parameters(
            tool_name=tool_name,
            tool_description=tool_description,
            tool_parameters_schema=tool_parameters_schema,
        )

        try:
            response = request_model_response(
                resolved_model,
                messages=pydantic_messages,
                model_settings=self._model_settings,
                model_request_parameters=request_params,
                stream_mode=self._stream_mode,
            )
            return _tool_completion_response(response)

        except Exception as exc:
            logger.warning("Provider error in generate_with_tools: %s", exc)
            return RlmCompletionResponse(
                error_message=str(exc),
            )


def _build_tool_messages(
    messages: list[RlmMessage],
    *,
    system_prompt: str | None,
    default_tool_name: str,
) -> list[Any]:
    from pydantic_ai.messages import (
        ModelRequest,
        ModelResponse,
        SystemPromptPart,
        TextPart,
        ToolReturnPart,
        UserPromptPart,
    )

    converted: list[Any] = []
    if system_prompt:
        converted.append(ModelRequest(parts=[SystemPromptPart(content=system_prompt)]))
    index = 0
    while index < len(messages):
        message = messages[index]
        if message.role == "user":
            converted.append(ModelRequest(parts=[UserPromptPart(content=message.content)]))
        elif message.role == "assistant":
            parts: list[Any] = [TextPart(content=message.content)]
            if index + 1 < len(messages) and messages[index + 1].role == "tool_call":
                index += 1
                parts.append(
                    _tool_call_part(
                        messages[index],
                        default_tool_name=default_tool_name,
                    )
                )
            converted.append(ModelResponse(parts=parts))
        elif message.role == "tool_call":
            converted.append(
                ModelResponse(
                    parts=[
                        _tool_call_part(
                            message,
                            default_tool_name=default_tool_name,
                        )
                    ]
                )
            )
        elif message.role == "tool_result":
            converted.append(
                ModelRequest(
                    parts=[
                        ToolReturnPart(
                            tool_name=(message.tool_name or default_tool_name),
                            content=message.content,
                            tool_call_id=message.tool_call_id or "",
                        )
                    ]
                )
            )
        index += 1
    return converted


def _tool_call_part(
    message: RlmMessage,
    *,
    default_tool_name: str,
) -> Any:
    from pydantic_ai.messages import ToolCallPart

    return ToolCallPart(
        tool_name=message.tool_name or default_tool_name,
        args={"code": message.content},
        tool_call_id=message.tool_call_id or "",
    )


def _tool_request_parameters(
    *,
    tool_name: str,
    tool_description: str,
    tool_parameters_schema: dict[str, Any],
) -> Any:
    from pydantic_ai.models import ModelRequestParameters
    from pydantic_ai.tools import ToolDefinition

    return ModelRequestParameters(
        function_tools=[
            ToolDefinition(
                name=tool_name,
                description=tool_description,
                parameters_json_schema=tool_parameters_schema,
            )
        ],
        allow_text_output=True,
    )


def _tool_completion_response(response: Any) -> RlmCompletionResponse:
    from pydantic_ai.messages import TextPart, ToolCallPart

    output_text = ""
    result_tool_call: ToolCall | None = None
    for part in response.parts:
        if isinstance(part, TextPart):
            output_text += part.content
        elif isinstance(part, ToolCallPart):
            result_tool_call = ToolCall(
                name=part.tool_name,
                code=part.args_as_dict().get("code", ""),
                call_id=part.tool_call_id,
            )
    usage = response.usage
    return RlmCompletionResponse(
        output_text=output_text,
        input_tokens=usage.input_tokens or 0,
        output_tokens=usage.output_tokens or 0,
        cache_read_tokens=(getattr(usage, "cache_read_tokens", 0) or 0),
        cache_write_tokens=(getattr(usage, "cache_write_tokens", 0) or 0),
        tool_call=result_tool_call,
    )


def _build_pydantic_model(
    model_name: str,
    provider: str,
    *,
    timeout_seconds: float | None = None,
) -> Any:
    """Build the PydanticAI model object for the detected provider."""
    if provider == "bedrock":
        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        region = os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")
        kwargs: dict[str, Any] = {}
        if region:
            kwargs["region_name"] = region
        if timeout_seconds is not None:
            if timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be positive")
            kwargs["aws_read_timeout"] = timeout_seconds
            kwargs["aws_connect_timeout"] = min(timeout_seconds, 30.0)
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
        from pydantic_ai.models.bedrock import BedrockModelSettings

        return BedrockModelSettings(
            bedrock_cache_instructions=True,
            bedrock_cache_tool_definitions=True,
            bedrock_cache_messages=True,
        )

    if provider in ("anthropic", "auto"):
        from pydantic_ai.models.anthropic import AnthropicModelSettings

        return AnthropicModelSettings(
            anthropic_cache_instructions=True,
            anthropic_cache_tool_definitions=True,
            anthropic_cache_messages=True,
        )

    return None


def make_rlm_client(
    model_name: str,
    *,
    cache: bool = True,
    max_tokens: int | None = None,
    stream_mode: str = "auto",
    timeout_seconds: float | None = None,
) -> PydanticAiRlmClient:
    """Create an RlmClient for the given model name.

    Detects the provider from the model name, builds the appropriate
    PydanticAI model object, and wraps it in a ``PydanticAiRlmClient``.

    Requires ``pydantic-ai`` to be installed.
    """
    provider = resolve_pydantic_provider(model_name)
    pydantic_model = _build_pydantic_model(
        model_name,
        provider,
        timeout_seconds=timeout_seconds,
    )
    settings = _build_model_settings(provider, cache)
    if max_tokens is not None:
        if max_tokens <= 0:
            raise ValueError("max_tokens must be a positive integer")
        settings = dict(settings or {})
        settings["max_tokens"] = max_tokens
    if timeout_seconds is not None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        settings = dict(settings or {})
        settings["timeout"] = timeout_seconds

    logger.info(
        "RlmClient: model=%s provider=%s cache=%s max_tokens=%s timeout_seconds=%s",
        model_name,
        provider,
        cache,
        max_tokens,
        timeout_seconds,
    )

    return PydanticAiRlmClient(
        model=pydantic_model,
        model_settings=settings,
        stream_mode=stream_mode,
    )
