# ABOUTME: Local adapter registry for in-process execution without containers.
# ABOUTME: Maps adapter_kind strings to builder functions, reusing existing provider clients.

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Type alias for adapter builder functions.
# Each builder receives model_name, workspace path, and optional overrides
# (e.g. a pre-built client for testing). Returns an object satisfying the
# Adapter protocol (execute, adapter_name, resolved_model).
AdapterBuilder = Callable[..., Any]

# Provider detection prefixes — shared across adapter types
_AZURE_PREFIXES = ("gpt-", "gpt4", "o1-", "o3-", "o4-")
_ANTHROPIC_PREFIXES = ("claude-",)


def detect_direct_provider(model_name: str) -> str:
    """Detect the direct client provider from the model name.

    Returns ``"anthropic"`` or ``"azure"``.  Defaults to ``"anthropic"``
    for unknown models (Anthropic API is the most common local use case).
    """
    lower = model_name.lower()
    if any(lower.startswith(p) for p in _AZURE_PREFIXES):
        return "azure"
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

    When the workspace's rlm.toml has a [constitution] section, a
    constitutional_client is built and passed to build_rlm_adapter so
    that constitutional parameters are inferred from task metadata.
    The *constitutional_model* argument overrides the model from rlm.toml.

    Task metadata is extracted from task.toml when present, providing
    context (difficulty, tags, tools, timeout) to the inference call.
    """
    from aec_bench.adapters.rlm.adapter import RlmAdapter
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
    if rlm_toml.exists():
        from aec_bench.adapters.rlm.config import parse_rlm_config

        _rlm_cfg = parse_rlm_config(rlm_toml.read_text())

        # Build advisor client if config declares an [advisor] block
        advisor_client = None
        if _rlm_cfg.advisor and _rlm_cfg.advisor.enabled:
            from aec_bench.adapters.rlm.providers import make_rlm_client as _make

            advisor_client = _make(_rlm_cfg.advisor.model, cache=True)
            logger.info("Advisor client: model=%s", _rlm_cfg.advisor.model)

        # Build constitutional client if config declares a [constitution] block
        constitutional_client = None
        if _rlm_cfg.constitution_path or _rlm_cfg.constitution_inline:
            from aec_bench.adapters.rlm.providers import make_rlm_client as _make

            constitution_model_name = constitutional_model or _rlm_cfg.constitution_model or model_name
            constitutional_client = _make(constitution_model_name, cache=True)
            logger.info("Constitutional client: model=%s", constitution_model_name)

        # Extract task metadata from task.toml when present (graceful fallback to empty).
        # We read the TOML directly rather than load_task_definition() because the latter
        # validates task-directory layout. Here we only need hint context for inference,
        # so malformed metadata should not prevent local adapter construction.
        task_metadata: dict[str, object] = {}
        task_toml = rlm_toml.parent / "task.toml"
        if task_toml.exists():
            try:
                import tomllib as _tomllib
            except ModuleNotFoundError:
                import tomli as _tomllib  # type: ignore[no-redef]
            try:
                task_data = _tomllib.loads(task_toml.read_text())
                meta = task_data.get("metadata", {})
                agent = task_data.get("agent", {})
                task_metadata = {
                    "difficulty": meta.get("difficulty"),
                    "tags": list(meta.get("tags", [])),
                    "category": meta.get("category"),
                    "timeout_seconds": agent.get("timeout_sec"),
                    "is_template_based": bool(_rlm_cfg.template_definition),
                }
            except Exception as exc:
                logger.warning("Could not read task.toml for constitutional metadata: %s", exc)

        return build_rlm_adapter(
            rlm_config_path=rlm_toml,
            client=client,
            adapter_name="rlm",
            model_name=model_name,
            subcall_client=compaction_client,
            compaction_client=compaction_client,
            trajectory_writer=trajectory_writer,
            workspace_path=workspace,
            advisor_client=advisor_client,
            constitutional_client=constitutional_client,
            task_metadata=task_metadata,
        )

    return RlmAdapter(
        adapter_name="rlm",
        model_name=model_name,
        client=client,
        compaction_client=compaction_client,
        trajectory_writer=trajectory_writer,
        scratchpad_path=str(Path(workspace) / ".scratchpad.json"),
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

    When the workspace's lambda-rlm.toml has a [constitution] section, a
    constitutional_client is built and passed to build_lambda_rlm_adapter
    so that constitutional parameters are inferred from task metadata.
    The *constitutional_model* argument overrides the model from
    lambda-rlm.toml.

    Task metadata is extracted from task.toml when present, providing
    context (difficulty, tags, category, timeout) to the inference call.
    λ-RLM always uses templates, so ``is_template_based`` is always True.
    """
    from aec_bench.adapters.lambda_rlm.config import parse_lambda_rlm_config
    from aec_bench.adapters.lambda_rlm.initialiser import build_lambda_rlm_adapter
    from aec_bench.adapters.rlm.providers import make_rlm_client

    ws = Path(workspace)
    config_path = ws / "lambda-rlm.toml"
    if not config_path.exists():
        config_path = ws / "rlm.toml"
    if not config_path.exists():
        config_path = None

    if client is None:
        client = make_rlm_client(model_name)

    # Build constitutional client if config declares a [constitution] block.
    # Import make_rlm_client fresh inside the branch so tests that monkey-patch
    # aec_bench.adapters.rlm.providers.make_rlm_client are honoured.
    constitutional_client = None
    if config_path is not None:
        _cfg = parse_lambda_rlm_config(config_path.read_text())
        if _cfg.constitution_path or _cfg.constitution_inline:
            from aec_bench.adapters.rlm.providers import make_rlm_client as _make

            constitution_model_name = constitutional_model or _cfg.constitution_model or model_name
            constitutional_client = _make(constitution_model_name, cache=True)
            logger.info("Lambda-RLM constitutional client: model=%s", constitution_model_name)

    # Extract task metadata from task.toml when present (graceful fallback to empty).
    # We read the TOML directly rather than load_task_definition() because the latter
    # validates task-directory layout. Here we only need hint context for inference,
    # so malformed metadata should not prevent local adapter construction.
    task_metadata: dict[str, object] = {}
    task_toml = ws / "task.toml"
    if task_toml.exists():
        try:
            import tomllib as _tomllib
        except ModuleNotFoundError:
            import tomli as _tomllib  # type: ignore[no-redef]
        try:
            task_data = _tomllib.loads(task_toml.read_text())
            meta = task_data.get("metadata", {})
            agent = task_data.get("agent", {})
            task_metadata = {
                "difficulty": meta.get("difficulty"),
                "tags": list(meta.get("tags", [])),
                "category": meta.get("category"),
                "timeout_seconds": agent.get("timeout_sec"),
                # λ-RLM always uses templates
                "is_template_based": True,
            }
        except Exception as exc:
            logger.warning("Could not read task.toml for constitutional metadata: %s", exc)

    return build_lambda_rlm_adapter(
        config_path=config_path,
        client=client,
        adapter_name="lambda-rlm",
        model_name=model_name,
        workspace=workspace,
        trajectory_writer=trajectory_writer,
        constitutional_client=constitutional_client,
        task_metadata=task_metadata,
    )


def _build_tool_loop(
    *,
    model_name: str,
    workspace: str,
    client: Any | None = None,
    trajectory_writer: Any | None = None,
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
        try:
            import tomllib as _tomllib
        except ModuleNotFoundError:
            import tomli as _tomllib  # type: ignore[no-redef]

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

    if client is None:
        # Import lazily so tests can monkeypatch the symbol on the module.
        from aec_bench.adapters import tool_loop_local as _tll

        client = _tll.PydanticAiToolLoopClient(
            model_name,
            workspace=workspace,
            advisor_client=advisor_client,
            advisor_config=advisor_config,
            trajectory_writer=trajectory_writer,
        )
    executor = BashToolExecutor(workspace=workspace)

    return ToolLoopAdapter(
        adapter_name="tool_loop",
        model_name=model_name,
        client=client,
        tool_executor=executor,
        advisor_client=advisor_client,
        advisor_config=advisor_config,
    )


# Default builder registry
_DEFAULT_BUILDERS: dict[str, AdapterBuilder] = {
    "rlm": _build_rlm,
    "direct": _build_direct,
    "lambda-rlm": _build_lambda_rlm,
    "tool_loop": _build_tool_loop,
}


class LocalAdapterRegistry:
    """Registry that maps adapter kind strings to builder functions.

    Each builder creates a fully-wired adapter for in-process local
    execution.  Provider credentials are read from environment variables.

    The registry ships with builders for ``"rlm"`` and ``"direct"``.
    Additional builders can be registered via :meth:`register`.
    """

    def __init__(self) -> None:
        self._builders: dict[str, AdapterBuilder] = dict(_DEFAULT_BUILDERS)

    def register(self, adapter_kind: str, builder: AdapterBuilder) -> None:
        """Register a new adapter builder (or override an existing one)."""
        self._builders[adapter_kind] = builder

    def available_adapters(self) -> list[str]:
        """Return sorted list of registered adapter kinds."""
        return sorted(self._builders.keys())

    def build(
        self,
        *,
        adapter_kind: str,
        model_name: str,
        workspace: str,
        **kwargs: Any,
    ) -> Any:
        """Build an adapter instance for local execution.

        Looks up the builder for *adapter_kind* and calls it with the
        model name, workspace path, and any additional keyword arguments.

        Raises ``ValueError`` if *adapter_kind* is not registered.
        """
        builder = self._builders.get(adapter_kind)
        if builder is None:
            available = ", ".join(self.available_adapters())
            msg = f"Unknown adapter kind: '{adapter_kind}'. Available: {available}"
            raise ValueError(msg)

        logger.info(
            "Building %s adapter: model=%s workspace=%s",
            adapter_kind,
            model_name,
            workspace,
        )
        return builder(
            model_name=model_name,
            workspace=workspace,
            **kwargs,
        )
