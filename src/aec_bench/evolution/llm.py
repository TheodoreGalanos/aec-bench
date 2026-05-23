# ABOUTME: Factory for building LLM clients used by the evolution engine.
# ABOUTME: Routes to Anthropic or Bedrock based on model name prefix.

from __future__ import annotations

from aec_bench.contracts.evolution import EvolverModelConfig
from aec_bench.providers.behavioral_llm import (
    AnthropicBehavioralLLMClient,
    BedrockBehavioralLLMClient,
    build_behavioral_llm_client,
)

# Union type for both client variants
BehavioralClient = AnthropicBehavioralLLMClient | BedrockBehavioralLLMClient


def build_evolution_llm_clients(
    config: EvolverModelConfig,
) -> tuple[BehavioralClient, BehavioralClient]:
    """Build classifier and evolver LLM clients from model configuration.

    Detects the provider from each model name — Bedrock prefixes
    (``us.anthropic.*``, ``anthropic.claude*``, etc.) route to the
    Bedrock Converse API, everything else uses the direct Anthropic API.
    """
    classifier = build_behavioral_llm_client(model=config.classifier)
    evolver = build_behavioral_llm_client(model=config.evolver)
    return classifier, evolver
