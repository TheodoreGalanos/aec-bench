# ABOUTME: Builds the fixed set of local in-process adapters without containers.
# ABOUTME: Keeps provider construction at the execution composition boundary.

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from aec_bench.adapters.deepseek_harness.native_world_tools import DeepSeekNativeWorldEvidence
    from aec_bench.adapters.deepseek_harness.tool_gateway import NativeToolDefinition

logger = logging.getLogger(__name__)

# Type alias for adapter builder functions.
# Each builder receives model_name, workspace path, and optional overrides
# (e.g. a pre-built client for testing). Returns an object satisfying the
# Adapter protocol (execute, adapter_name, resolved_model).
AdapterBuilder = Callable[..., Any]

# Provider detection prefixes — shared across adapter types
_AZURE_PREFIXES = ("gpt-", "gpt4", "o1-", "o3-", "o4-")
_ANTHROPIC_PREFIXES = ("claude-",)
_TOGETHER_PREFIX = "together:"


def detect_direct_provider(model_name: str) -> str:
    """Detect the direct client provider from the model name.

    Returns ``"anthropic"``, ``"azure"``, ``"bedrock"``, or ``"together"``.
    Defaults to ``"anthropic"`` for unknown models (Anthropic API is the
    most common local use case).
    """
    lower = model_name.lower()
    if lower.startswith(_TOGETHER_PREFIX):
        return "together"
    if any(lower.startswith(p) for p in _AZURE_PREFIXES):
        return "azure"
    from aec_bench.adapters.rlm.providers import detect_provider

    if detect_provider(model_name) == "bedrock":
        return "bedrock"
    return "anthropic"


def _build_rlm(
    *,
    model_name: str,
    workspace: str,
    client: Any | None = None,
    compaction_client: Any | None = None,
    trajectory_writer: Any | None = None,
    constitutional_model: str | None = None,
    **_kwargs: Any,
) -> Any:
    """Build an RLM adapter for local execution.

    If *client* is not provided, creates a ``PydanticAiRlmClient`` from
    the model name (requires pydantic-ai and provider credentials).

    Explicit constitutional parameters are loaded without model inference.
    """
    from aec_bench.adapters.config import report_configuration

    if constitutional_model is not None:
        raise ValueError("constitutional inference is unsupported in metered report execution")
    from aec_bench.adapters.rlm.initialiser import build_rlm_adapter

    if client is None:
        from aec_bench.adapters.rlm.providers import make_rlm_client

        client = make_rlm_client(model_name)

    if compaction_client is None and client is not None:
        try:
            from aec_bench.adapters.rlm.providers import make_rlm_client

            compaction_client = make_rlm_client(model_name, cache=False)
        except Exception:
            compaction_client = client

    rlm_toml = Path(workspace) / "rlm.toml"
    return build_rlm_adapter(
        rlm_config_path=rlm_toml if rlm_toml.exists() else None,
        client=client,
        adapter_name="rlm",
        model_name=model_name,
        subcall_client=compaction_client,
        compaction_client=compaction_client,
        trajectory_writer=trajectory_writer,
        workspace_path=workspace,
        configuration=report_configuration(_kwargs),
    )


def _build_direct(
    *,
    model_name: str,
    workspace: str,
    client: Any | None = None,
    **_kwargs: Any,
) -> Any:
    """Build a Direct adapter for local execution.

    If *client* is not provided, creates the appropriate DirectClient
    based on provider detection from the model name.
    """
    from aec_bench.adapters.direct import DirectAdapter

    if client is None:
        provider = detect_direct_provider(model_name)
        if provider == "azure":
            from aec_bench.adapters.direct_providers import AzureOpenAIChatDirectClient

            client = AzureOpenAIChatDirectClient()
        elif provider == "bedrock":
            from aec_bench.adapters.direct_providers import BedrockDirectClient

            client = BedrockDirectClient()
        elif provider == "together":
            from aec_bench.adapters.direct_providers import TogetherChatDirectClient

            client = TogetherChatDirectClient()
        else:
            from aec_bench.adapters.direct_providers import AnthropicDirectClient

            client = AnthropicDirectClient()

    return DirectAdapter(
        adapter_name="direct",
        model_name=model_name,
        client=client,
    )


def _build_lambda_rlm(
    *,
    model_name: str,
    workspace: str,
    client: Any | None = None,
    trajectory_writer: Any | None = None,
    constitutional_model: str | None = None,
    **_kwargs: Any,
) -> Any:
    """Build a lambda-rlm adapter from workspace config.

    If *client* is not provided, creates a ``PydanticAiRlmClient`` from
    the model name (requires pydantic-ai and provider credentials).

    Explicit constitutional parameters are loaded without model inference.
    """
    from aec_bench.adapters.config import report_configuration

    if constitutional_model is not None:
        raise ValueError("constitutional inference is unsupported in metered report execution")
    from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter
    from aec_bench.adapters.rlm.providers import make_rlm_client

    ws = Path(workspace)
    lambda_config_path = ws / "lambda-rlm.toml"
    fallback_config_path = ws / "rlm.toml"
    config_path = (
        lambda_config_path
        if lambda_config_path.exists()
        else fallback_config_path
        if fallback_config_path.exists()
        else None
    )

    if client is None:
        client = make_rlm_client(model_name)

    return build_lambda_rlm_adapter(
        config_path=config_path,
        client=client,
        adapter_name="lambda-rlm",
        model_name=model_name,
        workspace=workspace,
        trajectory_writer=trajectory_writer,
        configuration=report_configuration(_kwargs),
    )


def _build_tool_loop(
    *,
    model_name: str,
    workspace: str,
    client: Any | None = None,
    trajectory_writer: Any | None = None,
    native_tools: Sequence[Any] | None = None,
    enable_bash: bool = True,
    cache: bool = True,
    adapter_name: str = "tool_loop",
    **_kwargs: Any,
) -> Any:
    """Build a tool-loop adapter for local execution with bash tool.

    Uses the Bedrock Converse API (or Azure/Anthropic) for multi-turn
    tool use. The model gets a ``bash`` tool to run commands in the workspace.

    When the workspace contains a ``tool_loop.toml`` with an ``[advisor]`` block,
    an advisor client is built and wired into the adapter so the model can
    escalate strategic questions via the ``advisor`` tool.
    """
    from aec_bench.adapters.tool_loop import ToolLoopAdapter
    from aec_bench.adapters.tool_loop_local import BashToolExecutor
    from aec_bench.contracts.advisor import AdvisorConfig

    # Parse advisor config from workspace-level tool_loop.toml before building the client,
    # so the PydanticAI client can register `advisor` as a native tool. Without this, the
    # underlying pydantic-ai Agent never declares the advisor tool to the executor model.
    advisor_client = None
    advisor_config: AdvisorConfig | None = None
    config_path = Path(workspace) / "tool_loop.toml"
    if config_path.exists():
        import tomllib as _tomllib

        from aec_bench.contracts.validators import resolve_env_ref

        data = _tomllib.loads(config_path.read_text())
        advisor_data = data.get("advisor")
        if advisor_data:
            advisor_config = AdvisorConfig(
                model=resolve_env_ref(advisor_data["model"]),
                max_uses=advisor_data.get("max_uses", 5),
                max_response_tokens=advisor_data.get("max_response_tokens", 500),
                context_window=advisor_data.get("context_window", 10),
                enabled=advisor_data.get("enabled", True),
            )
            if advisor_config.enabled:
                from aec_bench.adapters.rlm.providers import make_rlm_client

                advisor_client = make_rlm_client(advisor_config.model, cache=True)
                logger.info("Tool-loop advisor client: model=%s", advisor_config.model)

    if client is not None and (native_tools or not enable_bash):
        raise ValueError("prebuilt tool-loop clients cannot accept native tool configuration")
    if client is None:
        # Import lazily so tests can monkeypatch the symbol on the module.
        from aec_bench.adapters import tool_loop_local as _tll

        client = _tll.PydanticAiToolLoopClient(
            model_name,
            workspace=workspace,
            advisor_client=advisor_client,
            advisor_config=advisor_config,
            trajectory_writer=trajectory_writer,
            native_tools=native_tools,
            enable_bash=enable_bash,
            cache=cache,
        )
    executor = BashToolExecutor(workspace=workspace)

    return ToolLoopAdapter(
        adapter_name=adapter_name,
        model_name=model_name,
        client=client,
        tool_executor=executor,
        advisor_client=advisor_client,
        advisor_config=advisor_config,
    )


def _build_pydantic_ai(
    *,
    model_name: str,
    workspace: str,
    **kwargs: Any,
) -> Any:
    """Build the PydanticAI-backed tool-loop adapter through its public alias."""
    return _build_tool_loop(
        model_name=model_name,
        workspace=workspace,
        adapter_name="pydantic_ai",
        **kwargs,
    )


def _build_prime_agent(
    *,
    model_name: str,
    workspace: str,
    executable: str = "prime-agent",
    **_kwargs: Any,
) -> Any:
    """Build the external-process Prime Agent adapter without provider SDK imports."""
    from aec_bench.adapters.prime_agent import PrimeAgentAdapter

    return PrimeAgentAdapter(
        model_name=model_name,
        workspace=workspace,
        executable=executable,
    )


def _build_deepseek_harness(
    *,
    model_name: str,
    workspace: str,
    native_tools: list[Callable[..., str]] | None = None,
    native_tool_definitions: Sequence[NativeToolDefinition] | None = None,
    native_world_evidence: DeepSeekNativeWorldEvidence | None = None,
    **_kwargs: Any,
) -> Any:
    """Build the official DeepSeek Harness adapter through its shared runtime."""
    from aec_bench.adapters.deepseek_harness import DeepSeekHarnessAdapter
    from aec_bench.adapters.deepseek_harness.config import DeepSeekHarnessSettings
    from aec_bench.adapters.deepseek_harness.tool_gateway import NativeToolDefinition

    provider = model_name.partition(":")[0].strip().lower()
    settings = DeepSeekHarnessSettings.from_execution_payload(
        model_name=model_name,
        payload={"provider": provider},
    )
    definitions = tuple(native_tool_definitions or ())
    if native_tools and not definitions:
        raise ValueError("DeepSeek native tools require explicit NativeToolDefinition values")
    if not all(isinstance(definition, NativeToolDefinition) for definition in definitions):
        raise TypeError("DeepSeek native tool definitions must be NativeToolDefinition values")
    names = [definition.name for definition in definitions]
    if len(names) != len(set(names)):
        duplicate = next(name for name in names if names.count(name) > 1)
        raise ValueError(f"duplicate DeepSeek native tool: {duplicate}")
    return DeepSeekHarnessAdapter(
        settings=settings,
        workspace=workspace,
        native_tools=definitions,
        native_world_evidence=native_world_evidence,
    )


# Default builder registry
_DEFAULT_BUILDERS: dict[str, AdapterBuilder] = {
    "deepseek_harness": _build_deepseek_harness,
    "rlm": _build_rlm,
    "direct": _build_direct,
    "lambda-rlm": _build_lambda_rlm,
    "lambda_rlm": _build_lambda_rlm,
    "tool_loop": _build_tool_loop,
    "pydantic_ai": _build_pydantic_ai,
    "prime-agent": _build_prime_agent,
}


def available_local_adapters() -> tuple[str, ...]:
    """Return the fixed local adapter names accepted by the current runtime."""
    return tuple(sorted(_DEFAULT_BUILDERS))


def build_local_adapter(
    *,
    adapter_kind: str,
    model_name: str,
    workspace: str,
    **kwargs: Any,
) -> Any:
    """Build one of the package's current local adapters."""
    builder = _DEFAULT_BUILDERS.get(adapter_kind)
    if builder is None:
        available = ", ".join(available_local_adapters())
        raise ValueError(f"Unknown adapter kind: '{adapter_kind}'. Available: {available}")

    logger.info(
        "Building %s adapter: model=%s workspace=%s",
        adapter_kind,
        model_name,
        workspace,
    )
    return builder(model_name=model_name, workspace=workspace, **kwargs)
