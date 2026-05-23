# ABOUTME: Tests for minimal rlm.toml config parsing.
# ABOUTME: Covers default values, hints, subcalls, and guardrail fields.
"""Tests for minimal rlm.toml config parsing."""

from aec_bench.adapters.rlm.config import ExecutionConfig, RlmConfig, parse_rlm_config

_MINIMAL_TOML = """\
[template]
tier = "flat"

[inputs.instruction]
type = "instruction"
source = "instruction.md"

[inputs.params]
type = "parameter_table"
source = "params.json"

[guardrails]
token_budget = 100_000
max_iterations = 50
max_subcall_depth = 1
"""


def test_parse_minimal_config() -> None:
    config = parse_rlm_config(_MINIMAL_TOML)
    assert isinstance(config, RlmConfig)
    assert config.template_tier == "flat"
    assert len(config.inputs) == 2
    assert config.guardrails.token_budget == 100_000
    assert config.guardrails.max_iterations == 50


def test_parse_config_with_defaults() -> None:
    minimal = """\
[template]
tier = "flat"
"""
    config = parse_rlm_config(minimal)
    assert config.guardrails.token_budget == 500_000
    assert config.guardrails.max_iterations == 100
    assert config.guardrails.max_subcall_depth == 1


def test_parse_config_with_hints() -> None:
    toml_str = """\
[template]
tier = "flat"

[hints]
phases = [
    "Read the instruction",
    "Calculate the result",
    "Submit the answer",
]
"""
    config = parse_rlm_config(toml_str)
    assert len(config.hints) == 3
    assert "Read the instruction" in config.hints


def test_parse_config_with_subcalls() -> None:
    toml_str = """\
[template]
tier = "flat"

[subcalls.extract]
enabled = true

[subcalls.calculate]
enabled = false
"""
    config = parse_rlm_config(toml_str)
    assert config.subcalls["extract"].enabled
    assert not config.subcalls["calculate"].enabled


def test_parse_config_with_template_definition() -> None:
    toml_str = """\
[template]
tier = "dependency_tree"
definition = "report_template.toml"
"""
    config = parse_rlm_config(toml_str)
    assert config.template_tier == "dependency_tree"
    assert config.template_definition == "report_template.toml"


def test_parse_config_template_definition_defaults_to_none() -> None:
    toml_str = """\
[template]
tier = "flat"
"""
    config = parse_rlm_config(toml_str)
    assert config.template_definition is None


def test_parse_execution_config_defaults() -> None:
    toml_str = """\
[template]
tier = "flat"
"""
    config = parse_rlm_config(toml_str)
    assert config.execution.scaffolding is True
    assert config.execution.compaction_threshold_pct == 0.85
    assert config.execution.hard_ceiling_pct == 0.95
    assert config.execution.compaction_model is None
    assert config.execution.context_limit == 1_000_000


def test_parse_execution_config_explicit() -> None:
    toml_str = """\
[template]
tier = "flat"

[execution]
scaffolding = false
compaction_threshold_pct = 0.80
context_limit = 200_000
"""
    config = parse_rlm_config(toml_str)
    assert config.execution.scaffolding is False
    assert config.execution.compaction_threshold_pct == 0.80
    assert config.execution.context_limit == 200_000


def test_execution_config_compaction_defaults() -> None:
    config = ExecutionConfig()
    assert config.scaffolding is True
    assert config.compaction_threshold_pct == 0.85
    assert config.hard_ceiling_pct == 0.95
    assert config.compaction_model is None
    assert config.context_limit == 1_000_000


def test_parse_execution_config_with_compaction() -> None:
    toml_str = """\
[template]
tier = "flat"

[execution]
scaffolding = true
compaction_threshold_pct = 0.80
hard_ceiling_pct = 0.90
compaction_model = "anthropic.claude-haiku-4-5"
context_limit = 200_000
"""
    config = parse_rlm_config(toml_str)
    assert config.execution.compaction_threshold_pct == 0.80
    assert config.execution.hard_ceiling_pct == 0.90
    assert config.execution.compaction_model == "anthropic.claude-haiku-4-5"
    assert config.execution.context_limit == 200_000


def test_parse_execution_config_backwards_compatible() -> None:
    """Old configs without compaction fields still parse with defaults."""
    toml_str = """\
[template]
tier = "flat"

[execution]
scaffolding = false
"""
    config = parse_rlm_config(toml_str)
    assert config.execution.scaffolding is False
    assert config.execution.compaction_threshold_pct == 0.85
    assert config.execution.compaction_model is None


# ---- Per-depth model routing ----


def test_parse_subcall_model_from_execution() -> None:
    toml_str = """\
[template]
tier = "flat"

[execution]
subcall_model = "anthropic.claude-haiku-4-5"
"""
    config = parse_rlm_config(toml_str)
    assert config.execution.subcall_model == "anthropic.claude-haiku-4-5"


def test_subcall_model_defaults_to_none() -> None:
    config = ExecutionConfig()
    assert config.subcall_model is None


# ---- Prohibited constraints ----


def test_parse_prohibited_constraints() -> None:
    toml_str = """\
[template]
tier = "flat"

[hints]
prohibited = [
    "Skip the codes search sub-call",
    "Write output from memory",
]
"""
    config = parse_rlm_config(toml_str)
    assert len(config.prohibited) == 2
    assert "Skip the codes search sub-call" in config.prohibited


def test_prohibited_defaults_to_empty() -> None:
    toml_str = """\
[template]
tier = "flat"
"""
    config = parse_rlm_config(toml_str)
    assert config.prohibited == []


# ---- Max subcalls guardrail ----


def test_parse_max_subcalls() -> None:
    toml_str = """\
[template]
tier = "flat"

[guardrails]
max_subcalls = 50
"""
    config = parse_rlm_config(toml_str)
    assert config.guardrails.max_subcalls == 50


def test_max_subcalls_defaults_to_zero() -> None:
    toml_str = """\
[template]
tier = "flat"
"""
    config = parse_rlm_config(toml_str)
    assert config.guardrails.max_subcalls == 0


# ---- Parallel workers ----


def test_parse_max_parallel_workers() -> None:
    toml_str = """\
[template]
tier = "flat"

[execution]
max_parallel_workers = 8
"""
    config = parse_rlm_config(toml_str)
    assert config.execution.max_parallel_workers == 8


def test_max_parallel_workers_defaults_to_four() -> None:
    config = ExecutionConfig()
    assert config.max_parallel_workers == 4


# ---- Advisor config parsing ----


class TestAdvisorConfigParsing:
    def test_no_advisor_block(self) -> None:
        toml = '[template]\ntier = "flat"\n'
        config = parse_rlm_config(toml)
        assert config.advisor is None

    def test_advisor_block_parsed(self) -> None:
        toml = """
[template]
tier = "flat"

[advisor]
model = "claude-opus-4-6"
max_uses = 8
max_response_tokens = 600
context_window = 15
"""
        config = parse_rlm_config(toml)
        assert config.advisor is not None
        assert config.advisor.model == "claude-opus-4-6"
        assert config.advisor.max_uses == 8
        assert config.advisor.max_response_tokens == 600
        assert config.advisor.context_window == 15
        assert config.advisor.enabled is True

    def test_advisor_disabled(self) -> None:
        toml = """
[template]
tier = "flat"

[advisor]
model = "claude-opus-4-6"
enabled = false
"""
        config = parse_rlm_config(toml)
        assert config.advisor is not None
        assert config.advisor.enabled is False


class TestRlmConfigConstitutional:
    def test_no_constitution_key(self) -> None:
        from aec_bench.adapters.rlm.config import parse_rlm_config

        toml = """
[template]
tier = "flat"
"""
        cfg = parse_rlm_config(toml)
        assert cfg.constitution_path is None
        assert cfg.constitution_inline is None
        assert cfg.constitution_model is None

    def test_constitution_path(self) -> None:
        from aec_bench.adapters.rlm.config import parse_rlm_config

        toml = """
[template]
tier = "flat"

[constitution]
path = "src/aec_bench/adapters/constitution_default.toml"
model = "claude-opus-4-6"
"""
        cfg = parse_rlm_config(toml)
        assert cfg.constitution_path == "src/aec_bench/adapters/constitution_default.toml"
        assert cfg.constitution_model == "claude-opus-4-6"
        assert cfg.constitution_inline is None

    def test_constitution_inline(self) -> None:
        from aec_bench.adapters.rlm.config import parse_rlm_config

        toml = """
[template]
tier = "flat"

[constitution]
model = "claude-opus-4-6"

[constitution.information_minimality]
default_threshold = 3500
"""
        cfg = parse_rlm_config(toml)
        assert cfg.constitution_path is None
        assert cfg.constitution_model == "claude-opus-4-6"
        assert cfg.constitution_inline is not None
        assert cfg.constitution_inline.information_minimality is not None
        assert cfg.constitution_inline.information_minimality.default_threshold == 3500
