# ABOUTME: Tests for [constitution] block parsing in lambda-rlm.toml.
# ABOUTME: Verifies path, inline, and model fields flow through parse_lambda_rlm_config.

from aec_bench.adapters.lambda_rlm.config import (
    LambdaRlmConfig,
    parse_lambda_rlm_config,
)


def test_config_defaults_have_no_constitution():
    config = LambdaRlmConfig()
    assert config.constitution_path is None
    assert config.constitution_inline is None
    assert config.constitution_model is None


def test_parse_constitution_path():
    toml = """
[constitution]
path = "src/aec_bench/adapters/constitution_default.toml"
model = "au.anthropic.claude-haiku-4-5-20251001-v1:0"
"""
    config = parse_lambda_rlm_config(toml)
    assert config.constitution_path == "src/aec_bench/adapters/constitution_default.toml"
    assert config.constitution_model == "au.anthropic.claude-haiku-4-5-20251001-v1:0"
    assert config.constitution_inline is None


def test_parse_constitution_inline():
    toml = """
[constitution.inline]
version = "0.1.0"

[[constitution.inline.principles]]
name = "source_fidelity"
description = "Never fabricate."
evaluation_criteria = "All claims trace to sources."
"""
    config = parse_lambda_rlm_config(toml)
    assert config.constitution_path is None
    assert config.constitution_inline is not None
    assert config.constitution_inline["version"] == "0.1.0"
    assert len(config.constitution_inline["principles"]) == 1


def test_parse_without_constitution_block():
    toml = """
[guardrails]
token_budget = 500000
"""
    config = parse_lambda_rlm_config(toml)
    assert config.constitution_path is None
    assert config.constitution_inline is None
    assert config.constitution_model is None
