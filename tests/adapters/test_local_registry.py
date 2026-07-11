# ABOUTME: Tests for the local adapter registry that maps adapter_kind to builder functions.
# ABOUTME: Validates adapter instantiation, provider detection, and unknown adapter handling.

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from aec_bench.adapters.local_registry import (
    LocalAdapterRegistry,
    detect_direct_provider,
)


class TestDetectDirectProvider:
    """Tests for model-name-based provider detection for direct clients."""

    def test_anthropic_models(self) -> None:
        assert detect_direct_provider("claude-sonnet-4-6") == "anthropic"
        assert detect_direct_provider("claude-haiku-4-5-20251001") == "anthropic"

    def test_azure_models(self) -> None:
        assert detect_direct_provider("gpt-4.1-mini") == "azure"
        assert detect_direct_provider("o3-mini") == "azure"

    def test_together_models(self) -> None:
        assert detect_direct_provider("together:Qwen/Qwen3.7-Max") == "together"

    def test_bedrock_models(self) -> None:
        assert detect_direct_provider("us.anthropic.claude-sonnet-4-6") == "anthropic"
        # Bedrock models use the Anthropic API pattern through the prefix

    def test_unknown_model(self) -> None:
        assert detect_direct_provider("some-random-model") == "anthropic"


class TestLocalAdapterRegistry:
    """Tests for the registry itself."""

    def test_registered_adapter_kinds(self) -> None:
        """Registry should know about the local execution adapters."""
        registry = LocalAdapterRegistry()
        kinds = registry.available_adapters()
        assert "rlm" in kinds
        assert "direct" in kinds
        assert "lambda-rlm" in kinds
        assert "lambda_rlm" in kinds
        assert "tool_loop" in kinds
        assert "pydantic_ai" in kinds

    def test_unknown_adapter_raises(self) -> None:
        registry = LocalAdapterRegistry()
        with pytest.raises(ValueError, match="nonexistent"):
            registry.build(
                adapter_kind="nonexistent",
                model_name="test-model",
                workspace=MagicMock(),
            )


class TestBuildRlm:
    """Tests for building an RLM adapter via the registry."""

    def test_build_rlm_returns_adapter(self, tmp_path: Path) -> None:
        """RLM builder should return an object with execute()."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do something")
        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n[guardrails]\ntoken_budget = 10_000\nmax_iterations = 5\n'
        )

        registry = LocalAdapterRegistry()
        # Provide a mock client to avoid needing real credentials
        mock_client = MagicMock()
        adapter = registry.build(
            adapter_kind="rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=mock_client,
        )
        assert hasattr(adapter, "execute")
        assert adapter.adapter_name() == "rlm"
        assert adapter.resolved_model() == "test-model"

    def test_build_rlm_without_config(self, tmp_path: Path) -> None:
        """RLM builder should work even without rlm.toml."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        registry = LocalAdapterRegistry()
        mock_client = MagicMock()
        adapter = registry.build(
            adapter_kind="rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=mock_client,
        )
        assert hasattr(adapter, "execute")


class TestBuildDirect:
    """Tests for building a Direct adapter via the registry."""

    def test_build_direct_returns_adapter(self, tmp_path: Path) -> None:
        """Direct builder should return an object with execute()."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        registry = LocalAdapterRegistry()
        mock_client = MagicMock()
        adapter = registry.build(
            adapter_kind="direct",
            model_name="test-model",
            workspace=str(workspace),
            client=mock_client,
        )
        assert hasattr(adapter, "execute")
        assert adapter.adapter_name() == "direct"
        assert adapter.resolved_model() == "test-model"


class TestBuildAdapterAliases:
    """Tests for compatibility aliases advertised by skills and CLI help."""

    def test_build_lambda_rlm_accepts_underscore_alias(self, tmp_path: Path) -> None:
        """lambda_rlm should build the same canonical lambda-rlm adapter."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "report_template.toml").write_text(
            """
[[sections]]
id = "intro"
title = "Intro"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = []
"""
        )
        (workspace / "lambda-rlm.toml").write_text(
            """
[template]
tier = "dependency_tree"
definition = "report_template.toml"
"""
        )

        registry = LocalAdapterRegistry()
        adapter = registry.build(
            adapter_kind="lambda_rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=MagicMock(),
        )

        assert hasattr(adapter, "execute")
        assert adapter.adapter_name() == "lambda-rlm"
        assert adapter.resolved_model() == "test-model"

    def test_build_pydantic_ai_alias_uses_tool_loop_runtime(self, tmp_path: Path) -> None:
        """pydantic_ai should be a working local alias for the Pydantic-backed tool loop."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        registry = LocalAdapterRegistry()
        adapter = registry.build(
            adapter_kind="pydantic_ai",
            model_name="test-model",
            workspace=str(workspace),
            client=MagicMock(),
        )

        assert hasattr(adapter, "execute")
        assert adapter.adapter_name() == "pydantic_ai"
        assert adapter.resolved_model() == "test-model"


class TestBuildLambdaRlmConstitutional:
    """Tests for constitutional wiring through _build_lambda_rlm."""

    def test_build_lambda_rlm_builds_constitutional_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A [constitution] block in lambda-rlm.toml wires a constitutional_client."""
        import json

        from aec_bench.adapters.local_registry import _build_lambda_rlm
        from aec_bench.adapters.rlm.client import RlmCompletionResponse

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "documents").mkdir()
        (workspace / "documents" / "brief.md").write_text("Alpha bravo.")

        (workspace / "report_template.toml").write_text(
            """
[[sections]]
id = "intro"
title = "Intro"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = ["brief"]
"""
        )

        (workspace / "constitution.toml").write_text(
            """
version = "0.1.0"

[[principles]]
name = "source_fidelity"
description = "Never fabricate."
evaluation_criteria = "All claims trace to sources."
"""
        )

        (workspace / "lambda-rlm.toml").write_text(
            """
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[constitution]
path = "constitution.toml"
model = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
"""
        )

        (workspace / "task.toml").write_text(
            """
[metadata]
difficulty = "hard"
tags = ["public-works", "sow"]
category = "report"

[agent]
timeout_sec = 600
"""
        )

        called_models: list[str] = []

        class _StubClient:
            def generate(self, *, model, messages, system_prompt=None):  # noqa: ANN001
                return RlmCompletionResponse(
                    output_text=json.dumps(
                        {
                            "source_fidelity": {
                                "require_source_tracing": True,
                                "tbd_placeholder": "[TBD]",
                                "gap_framing": "exclude",
                            }
                        }
                    ),
                    input_tokens=100,
                    output_tokens=50,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                )

            def generate_with_tools(self, **kwargs):  # pragma: no cover
                raise NotImplementedError

        def fake_make_rlm_client(model_name: str, cache: bool = True) -> _StubClient:
            called_models.append(model_name)
            return _StubClient()

        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        adapter = _build_lambda_rlm(
            model_name="test-main-model",
            workspace=str(workspace),
        )

        # Main client and constitutional client both requested
        assert "test-main-model" in called_models
        assert "au.anthropic.claude-haiku-4-5-20251001-v1:0" in called_models

        # Adapter has the resolved manifest with inferred params
        assert adapter._constitution is not None
        assert adapter._constitution.source_fidelity is not None
        assert adapter._constitution.source_fidelity.gap_framing == "exclude"

    def test_build_lambda_rlm_without_constitution_is_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without [constitution] block, no constitutional_client is built."""
        from aec_bench.adapters.local_registry import _build_lambda_rlm

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "documents").mkdir()
        (workspace / "documents" / "brief.md").write_text("Alpha.")

        (workspace / "report_template.toml").write_text(
            """
[[sections]]
id = "intro"
title = "Intro"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = ["brief"]
"""
        )

        (workspace / "lambda-rlm.toml").write_text(
            """
[template]
tier = "dependency_tree"
definition = "report_template.toml"
"""
        )

        called_models: list[str] = []

        class _StubClient:
            def generate(self, **_kw):
                raise AssertionError("inference must not fire when no [constitution] block")

            def generate_with_tools(self, **kwargs):  # pragma: no cover
                raise NotImplementedError

        def fake_make_rlm_client(model_name: str, cache: bool = True) -> _StubClient:
            called_models.append(model_name)
            return _StubClient()

        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        adapter = _build_lambda_rlm(
            model_name="test-main-model",
            workspace=str(workspace),
        )

        # Only the main client is built
        assert called_models == ["test-main-model"]
        assert adapter._constitution is None

    def test_cli_constitutional_model_override_wins_over_toml(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--constitutional-model CLI flag must override [constitution].model in the TOML."""
        import json

        from aec_bench.adapters.local_registry import _build_lambda_rlm
        from aec_bench.adapters.rlm.client import RlmCompletionResponse

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "documents").mkdir()
        (workspace / "documents" / "brief.md").write_text("Alpha.")

        (workspace / "report_template.toml").write_text(
            """
[[sections]]
id = "intro"
title = "Intro"
writing_guidance = ["one line"]
generation_mode = "prose"
input_mapping = ["brief"]
"""
        )

        (workspace / "constitution.toml").write_text(
            """
version = "0.1.0"

[[principles]]
name = "source_fidelity"
description = "Never fabricate."
evaluation_criteria = "All claims trace to sources."
"""
        )

        (workspace / "lambda-rlm.toml").write_text(
            """
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[constitution]
path = "constitution.toml"
model = "model-from-toml"
"""
        )

        called_models: list[str] = []

        class _StubClient:
            def generate(self, **_kw):  # type: ignore[no-untyped-def]
                return RlmCompletionResponse(
                    output_text=json.dumps(
                        {
                            "source_fidelity": {
                                "require_source_tracing": True,
                                "tbd_placeholder": "[TBD]",
                                "gap_framing": "exclude",
                            }
                        }
                    ),
                    input_tokens=10,
                    output_tokens=5,
                    cache_read_tokens=0,
                    cache_write_tokens=0,
                )

        def fake_make_rlm_client(model_name, cache=True):  # type: ignore[no-untyped-def]
            called_models.append(model_name)
            return _StubClient()

        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.make_rlm_client",
            fake_make_rlm_client,
        )

        _build_lambda_rlm(
            model_name="test-main-model",
            workspace=str(workspace),
            constitutional_model="cli-override-model",
        )

        # The CLI override must win; the TOML value "model-from-toml" must NOT appear
        assert "cli-override-model" in called_models
        assert "model-from-toml" not in called_models


class TestBuildToolLoopAdvisor:
    """Tests for advisor wiring in _build_tool_loop via tool_loop.toml."""

    def test_build_tool_loop_without_toml_has_no_advisor(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Without tool_loop.toml, the adapter is built without advisor wiring."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()

        client_stub = MagicMock()
        adapter = _build_tool_loop(
            model_name="claude-sonnet-4-6",
            workspace=str(workspace),
            client=client_stub,
        )

        assert adapter._advisor_client is None
        assert adapter._advisor_config is None

    def test_build_tool_loop_with_advisor_block_wires_advisor(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A [advisor] block in tool_loop.toml wires advisor_client and advisor_config."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "tool_loop.toml").write_text(
            """
[advisor]
model = "claude-sonnet-4-6"
max_uses = 3
max_response_tokens = 400
context_window = 8
"""
        )

        called_models: list[str] = []

        def fake_make_rlm_client(model_name: str, cache: bool = True) -> MagicMock:
            called_models.append(model_name)
            return MagicMock()

        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.make_rlm_client",
            fake_make_rlm_client,
        )

        client_stub = MagicMock()
        adapter = _build_tool_loop(
            model_name="gpt-4.1-mini",
            workspace=str(workspace),
            client=client_stub,
        )

        assert called_models == ["claude-sonnet-4-6"]
        assert adapter._advisor_client is not None
        assert adapter._advisor_config is not None
        assert adapter._advisor_config.model == "claude-sonnet-4-6"
        assert adapter._advisor_config.max_uses == 3
        assert adapter._advisor_config.max_response_tokens == 400
        assert adapter._advisor_config.context_window == 8

    def test_build_tool_loop_resolves_env_ref_in_advisor_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An ``env:VAR`` advisor.model reference is resolved against the environment."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "tool_loop.toml").write_text(
            """
[advisor]
model = "env:TEST_SONNET_MODEL_ID"
max_uses = 5
"""
        )

        monkeypatch.setenv("TEST_SONNET_MODEL_ID", "us.anthropic.claude-sonnet-4-6")

        called_models: list[str] = []

        def fake_make_rlm_client(model_name: str, cache: bool = True) -> MagicMock:
            called_models.append(model_name)
            return MagicMock()

        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.make_rlm_client",
            fake_make_rlm_client,
        )

        client_stub = MagicMock()
        adapter = _build_tool_loop(
            model_name="gpt-4.1-mini",
            workspace=str(workspace),
            client=client_stub,
        )

        assert called_models == ["us.anthropic.claude-sonnet-4-6"]
        assert adapter._advisor_config.model == "us.anthropic.claude-sonnet-4-6"

    def test_build_tool_loop_passes_advisor_to_pydantic_ai_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When tool_loop.toml has [advisor], the PydanticAI client is constructed
        with advisor_client + advisor_config so the executor model sees the tool."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "tool_loop.toml").write_text(
            """
[advisor]
model = "claude-sonnet-4-6"
max_uses = 4
"""
        )

        def fake_make_rlm_client(model_name: str, cache: bool = True) -> MagicMock:
            return MagicMock(name=f"rlm-{model_name}")

        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.make_rlm_client",
            fake_make_rlm_client,
        )

        captured: dict[str, object] = {}

        def fake_client_ctor(model_name: str, **kwargs) -> MagicMock:
            captured["model_name"] = model_name
            captured.update(kwargs)
            return MagicMock(name="pydantic-ai-client")

        monkeypatch.setattr(
            "aec_bench.adapters.tool_loop_local.PydanticAiToolLoopClient",
            fake_client_ctor,
        )

        _build_tool_loop(
            model_name="gpt-4.1-mini",
            workspace=str(workspace),
        )

        assert captured["model_name"] == "gpt-4.1-mini"
        assert captured["workspace"] == str(workspace)
        assert captured["advisor_client"] is not None
        advisor_config = captured["advisor_config"]
        assert advisor_config is not None
        assert advisor_config.model == "claude-sonnet-4-6"
        assert advisor_config.max_uses == 4

    def test_build_tool_loop_forwards_trajectory_writer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The trajectory_writer kwarg reaches PydanticAiToolLoopClient so the
        pydantic-ai message history is emitted as structured trajectory entries."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()

        captured: dict[str, object] = {}

        def fake_client_ctor(model_name: str, **kwargs) -> MagicMock:
            captured.update(kwargs)
            return MagicMock(name="pydantic-ai-client")

        monkeypatch.setattr(
            "aec_bench.adapters.tool_loop_local.PydanticAiToolLoopClient",
            fake_client_ctor,
        )

        sentinel_writer = MagicMock(name="traj-writer")
        _build_tool_loop(
            model_name="gpt-4.1-mini",
            workspace=str(workspace),
            trajectory_writer=sentinel_writer,
        )

        assert captured["trajectory_writer"] is sentinel_writer

    def test_build_tool_loop_forwards_native_tools(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Host-controlled tools reach the native PydanticAI loop."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()
        captured: dict[str, object] = {}

        def fake_client_ctor(model_name: str, **kwargs) -> MagicMock:
            del model_name
            captured.update(kwargs)
            return MagicMock(name="pydantic-ai-client")

        def submit_checkpoint(checkpoint_id: str) -> str:
            return checkpoint_id

        monkeypatch.setattr(
            "aec_bench.adapters.tool_loop_local.PydanticAiToolLoopClient",
            fake_client_ctor,
        )

        _build_tool_loop(
            model_name="gpt-4.1-mini",
            workspace=str(workspace),
            native_tools=[submit_checkpoint],
            enable_bash=False,
        )

        assert captured["native_tools"] == [submit_checkpoint]
        assert captured["enable_bash"] is False

    def test_build_tool_loop_rejects_confined_tools_with_prebuilt_client(self, tmp_path: Path) -> None:
        from aec_bench.adapters.local_registry import _build_tool_loop

        def read_workspace_file(path: str) -> str:
            return path

        with pytest.raises(ValueError, match="prebuilt tool-loop clients cannot accept native tool configuration"):
            _build_tool_loop(
                model_name="gpt-4.1-mini",
                workspace=str(tmp_path),
                client=MagicMock(),
                native_tools=[read_workspace_file],
                enable_bash=False,
            )

    def test_build_tool_loop_with_disabled_advisor_skips_client(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When enabled=false, the advisor client is not built."""
        from aec_bench.adapters.local_registry import _build_tool_loop

        workspace = tmp_path / "ws"
        workspace.mkdir()
        (workspace / "tool_loop.toml").write_text(
            """
[advisor]
model = "claude-sonnet-4-6"
enabled = false
"""
        )

        called_models: list[str] = []

        def fake_make_rlm_client(model_name: str, cache: bool = True) -> MagicMock:
            called_models.append(model_name)
            return MagicMock()

        monkeypatch.setattr(
            "aec_bench.adapters.rlm.providers.make_rlm_client",
            fake_make_rlm_client,
        )

        client_stub = MagicMock()
        adapter = _build_tool_loop(
            model_name="gpt-4.1-mini",
            workspace=str(workspace),
            client=client_stub,
        )

        assert called_models == []
        assert adapter._advisor_client is None


class TestCustomBuilder:
    """Tests for registering custom adapter builders."""

    def test_register_custom_builder(self) -> None:
        """Should be able to register a custom adapter kind."""
        registry = LocalAdapterRegistry()

        def my_builder(
            *,
            model_name: str,
            workspace: str,
            **kwargs,
        ) -> MagicMock:
            adapter = MagicMock()
            adapter.adapter_name.return_value = "custom"
            adapter.resolved_model.return_value = model_name
            return adapter

        registry.register("custom", my_builder)
        assert "custom" in registry.available_adapters()

        adapter = registry.build(
            adapter_kind="custom",
            model_name="test-model",
            workspace="/tmp/test",
        )
        assert adapter.adapter_name() == "custom"
