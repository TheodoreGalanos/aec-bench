# ABOUTME: Smoke tests for constitutional inference wiring through the local adapter registry.
# ABOUTME: Verifies _build_rlm constructs a constitutional_client when rlm.toml has [constitution].

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.adapters.local_registry import LocalAdapterRegistry


class StubRlmClient:
    """Minimal RlmClient stub that satisfies the protocol without hitting an LLM."""

    def generate(self, *, model, messages, system_prompt=None):
        from aec_bench.adapters.rlm.client import RlmCompletionResponse

        return RlmCompletionResponse(output_text="STUB", input_tokens=1, output_tokens=1)

    def generate_with_tools(self, **kwargs):  # pragma: no cover
        raise NotImplementedError


class StubConstitutionalClient(StubRlmClient):
    """Constitutional inference stub: returns a no-op JSON payload so inference completes."""

    def generate(self, *, model, messages, system_prompt=None):
        from aec_bench.adapters.rlm.client import RlmCompletionResponse

        # Return an empty JSON object — inference merges with user overrides
        return RlmCompletionResponse(output_text="{}", input_tokens=5, output_tokens=5)


class TestConstitutionalWiringPresent:
    """When rlm.toml has [constitution], the adapter must have a non-None constitution."""

    def test_adapter_gets_constitution_from_inline_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Registry wires constitutional_client; constitution resolved from inline config."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do the thing")

        # rlm.toml with inline constitution (no external file lookup needed)
        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n[constitution.information_minimality]\ndefault_threshold = 3000\n'
        )

        def fake_make_rlm_client(model: str, *, cache: bool = True) -> StubConstitutionalClient:
            return StubConstitutionalClient()

        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        registry = LocalAdapterRegistry()
        adapter = registry.build(
            adapter_kind="rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=StubRlmClient(),
        )
        # Constitution is resolved from inline config
        assert adapter.constitution is not None
        assert hasattr(adapter, "execute")
        assert adapter.adapter_name() == "rlm"

    def test_adapter_constitution_none_when_no_config_section(self, tmp_path: Path) -> None:
        """When rlm.toml has no [constitution], adapter.constitution must be None."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do the thing")
        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n[guardrails]\ntoken_budget = 10_000\nmax_iterations = 5\n'
        )

        registry = LocalAdapterRegistry()
        adapter = registry.build(
            adapter_kind="rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=StubRlmClient(),
        )
        assert adapter.constitution is None

    def test_constitutional_model_override_used_when_provided(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """constitutional_model kwarg overrides the model used for constitutional inference."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do the thing")

        # rlm.toml with inline constitution (no external file needed)
        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n'
            '[constitution]\nmodel = "original-model"\n'
            "[constitution.information_minimality]\ndefault_threshold = 1000\n"
        )

        captured_models: list[str] = []

        def fake_make_rlm_client(model: str, *, cache: bool = True) -> StubConstitutionalClient:
            captured_models.append(model)
            return StubConstitutionalClient()

        monkeypatch.setattr(
            "aec_bench.adapters.local_registry.make_rlm_client",
            fake_make_rlm_client,
            raising=False,
        )

        # Patch the import inside _build_rlm
        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        registry = LocalAdapterRegistry()
        adapter = registry.build(
            adapter_kind="rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=StubRlmClient(),
            constitutional_model="override-model",
        )

        assert hasattr(adapter, "execute")
        # The override model should be used for the constitutional client
        assert "override-model" in captured_models

    def test_constitutional_model_falls_back_to_rlm_config_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When no CLI override, uses the model from rlm.toml [constitution].model."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do the thing")

        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n'
            '[constitution]\nmodel = "config-model"\n'
            "[constitution.information_minimality]\ndefault_threshold = 1000\n"
        )

        captured_models: list[str] = []

        def fake_make_rlm_client(model: str, *, cache: bool = True) -> StubConstitutionalClient:
            captured_models.append(model)
            return StubConstitutionalClient()

        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        registry = LocalAdapterRegistry()
        registry.build(
            adapter_kind="rlm",
            model_name="main-model",
            workspace=str(workspace),
            client=StubRlmClient(),
            # No constitutional_model override
        )

        # The config model ("config-model") should be used, not "main-model"
        assert "config-model" in captured_models

    def test_constitutional_model_falls_back_to_main_model(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When neither CLI override nor rlm.toml model, falls back to main model."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do the thing")

        # [constitution] section present but no model key
        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n[constitution.information_minimality]\ndefault_threshold = 1000\n'
        )

        captured_models: list[str] = []

        def fake_make_rlm_client(model: str, *, cache: bool = True) -> StubConstitutionalClient:
            captured_models.append(model)
            return StubConstitutionalClient()

        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        registry = LocalAdapterRegistry()
        registry.build(
            adapter_kind="rlm",
            model_name="main-model",
            workspace=str(workspace),
            client=StubRlmClient(),
        )

        # Falls back to main model
        assert "main-model" in captured_models


class TestTaskMetadataExtraction:
    """Verifies task.toml metadata is extracted and passed through gracefully."""

    def test_task_toml_missing_falls_back_to_empty_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing task.toml must not crash; empty task_metadata is used instead."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "instruction.md").write_text("Do the thing")
        (workspace / "rlm.toml").write_text(
            '[template]\ntier = "flat"\n\n[constitution.information_minimality]\ndefault_threshold = 1000\n'
        )
        # No task.toml present

        def fake_make_rlm_client(model: str, *, cache: bool = True) -> StubConstitutionalClient:
            return StubConstitutionalClient()

        import aec_bench.adapters.rlm.providers as rlm_providers

        monkeypatch.setattr(rlm_providers, "make_rlm_client", fake_make_rlm_client)

        registry = LocalAdapterRegistry()
        # Must not raise
        adapter = registry.build(
            adapter_kind="rlm",
            model_name="test-model",
            workspace=str(workspace),
            client=StubRlmClient(),
        )
        assert hasattr(adapter, "execute")
