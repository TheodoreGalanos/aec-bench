# ABOUTME: Tests for env: prefix resolution in Pydantic contract validators.
# ABOUTME: Validates that model fields with env:VAR_NAME resolve from os.environ.

from __future__ import annotations

import pytest

from aec_bench.contracts.validators import resolve_env_ref


class TestResolveEnvRef:
    """Tests for the resolve_env_ref validator function."""

    def test_env_prefix_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_MODEL", "us.anthropic.claude-haiku")
        assert resolve_env_ref("env:MY_MODEL") == "us.anthropic.claude-haiku"

    def test_plain_string_passthrough(self) -> None:
        assert resolve_env_ref("claude-sonnet-4-6") == "claude-sonnet-4-6"

    def test_missing_env_var_raises(self) -> None:
        with pytest.raises(ValueError, match="NONEXISTENT_VAR"):
            resolve_env_ref("env:NONEXISTENT_VAR")

    def test_empty_env_var_resolves(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EMPTY_VAR", "")
        assert resolve_env_ref("env:EMPTY_VAR") == ""

    def test_env_prefix_case_sensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Only lowercase 'env:' triggers resolution."""
        assert resolve_env_ref("ENV:SOMETHING") == "ENV:SOMETHING"
        assert resolve_env_ref("Env:SOMETHING") == "Env:SOMETHING"


class TestEvolverModelConfigEnvResolution:
    """Tests that EvolverModelConfig resolves env: prefixes."""

    def test_classifier_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from aec_bench.contracts.evolution import EvolverModelConfig

        monkeypatch.setenv("AWS_HAIKU_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        config = EvolverModelConfig(
            classifier="env:AWS_HAIKU_MODEL_ID",
            evolver="claude-sonnet-4-6",
        )
        assert config.classifier == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        assert config.evolver == "claude-sonnet-4-6"

    def test_both_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from aec_bench.contracts.evolution import EvolverModelConfig

        monkeypatch.setenv("CLASSIFIER", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
        monkeypatch.setenv("EVOLVER", "us.anthropic.claude-sonnet-4-20250514-v2:0")
        config = EvolverModelConfig(
            classifier="env:CLASSIFIER",
            evolver="env:EVOLVER",
        )
        assert "claude-haiku" in config.classifier
        assert "claude-sonnet" in config.evolver

    def test_missing_env_var_raises_validation_error(self) -> None:
        from pydantic import ValidationError

        from aec_bench.contracts.evolution import EvolverModelConfig

        with pytest.raises(ValidationError, match="MISSING_MODEL"):
            EvolverModelConfig(
                classifier="env:MISSING_MODEL",
                evolver="claude-sonnet-4-6",
            )

    def test_plain_strings_still_work(self) -> None:
        from aec_bench.contracts.evolution import EvolverModelConfig

        config = EvolverModelConfig(
            classifier="claude-haiku-4-5-20251001",
            evolver="claude-sonnet-4-6",
        )
        assert config.classifier == "claude-haiku-4-5-20251001"


class TestAgentConfigEnvResolution:
    """Tests that AgentConfig.model resolves env: prefixes."""

    def test_model_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from aec_bench.contracts.experiment_manifest import AgentConfig

        monkeypatch.setenv("AGENT_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
        config = AgentConfig(
            name="my-agent",
            adapter="rlm",
            model="env:AGENT_MODEL_ID",
        )
        assert config.model == "us.anthropic.claude-sonnet-4-6"

    def test_plain_model_still_works(self) -> None:
        from aec_bench.contracts.experiment_manifest import AgentConfig

        config = AgentConfig(
            name="my-agent",
            adapter="rlm",
            model="claude-sonnet-4-6",
        )
        assert config.model == "claude-sonnet-4-6"
