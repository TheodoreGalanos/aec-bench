# ABOUTME: Tests for the evolution LLM client factory.
# ABOUTME: Verifies classifier and evolver clients are configured correctly from model config.

from aec_bench.contracts.evolution import EvolverModelConfig
from aec_bench.evolution.llm import build_evolution_llm_clients


class TestBuildEvolutionLLMClients:
    def test_returns_two_clients(self) -> None:
        config = EvolverModelConfig(
            classifier="claude-haiku-4-5-20251001",
            evolver="claude-sonnet-4-20250514",
        )
        classifier, evolver = build_evolution_llm_clients(config)
        assert classifier.model == "claude-haiku-4-5-20251001"
        assert evolver.model == "claude-sonnet-4-20250514"

    def test_different_models(self) -> None:
        config = EvolverModelConfig(classifier="haiku", evolver="opus")
        classifier, evolver = build_evolution_llm_clients(config)
        assert classifier.model == "haiku"
        assert evolver.model == "opus"
        assert classifier.model != evolver.model
