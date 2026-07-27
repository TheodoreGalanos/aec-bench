# ABOUTME: Schema and parser for rlm.toml task harness configuration.
# ABOUTME: Defines what inputs, output template, sub-calls, and guardrails a task declares.

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import Any

from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.constitution import (
    ConstitutionManifest,
    parse_constitution,
)


@dataclass(frozen=True)
class InputConfig:
    """Declaration of a single task input handle."""

    name: str
    input_type: str
    source: str
    pre_parse: bool = False
    description: str = ""


@dataclass(frozen=True)
class SubcallConfig:
    """Declaration of a typed sub-call availability."""

    name: str
    enabled: bool = True
    custom_impl: str | None = None
    description: str = ""


@dataclass(frozen=True)
class GuardrailConfig:
    """Guardrail settings for the RLM adapter."""

    token_budget: int = 500_000
    max_iterations: int = 100
    max_subcall_depth: int = 1
    budget_warning_pct: float = 80.0
    max_subcalls: int = 0  # 0 = unlimited
    max_budget_usd: float = 0.0  # 0 = unlimited
    billable_input_budget: int = 0  # 0 = unlimited; input tokens minus cache reads


@dataclass(frozen=True)
class ExecutionConfig:
    """Controls how the RLM agent interacts with the task at runtime."""

    scaffolding: bool = True  # inject REPL commands (FILL, SUBMIT, etc.)
    compaction_threshold_pct: float = 0.85  # trigger compaction at this % of context_limit
    hard_ceiling_pct: float = 0.95  # force finalisation at this %
    compaction_model: str | None = None  # None = use agent's model
    subcall_model: str | None = None  # None = use agent's model for sub-calls
    context_limit: int = 1_000_000  # model's context window in tokens
    max_parallel_workers: int = 4  # concurrency for parallel() and fill_parallel()


@dataclass(frozen=True)
class RlmConfig:
    """Parsed rlm.toml configuration for a task."""

    template_tier: str
    template_definition: str | None = None
    inputs: list[InputConfig] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)
    prohibited: list[str] = field(default_factory=list)
    subcalls: dict[str, SubcallConfig] = field(default_factory=dict)
    guardrails: GuardrailConfig = field(default_factory=GuardrailConfig)
    execution: ExecutionConfig = field(default_factory=ExecutionConfig)
    advisor: AdvisorConfig | None = None
    constitution_path: str | None = None
    constitution_inline: ConstitutionManifest | None = None
    constitution_model: str | None = None


def parse_rlm_config(toml_str: str) -> RlmConfig:
    """Parse an rlm.toml string into an RlmConfig."""
    data = tomllib.loads(toml_str)
    template_data = data.get("template", {})
    hints_data = data.get("hints", {})
    constitution_path, constitution_inline, constitution_model = _parse_constitution(data.get("constitution"))

    return RlmConfig(
        template_tier=template_data.get("tier", "flat"),
        template_definition=template_data.get("definition"),
        inputs=_parse_inputs(data.get("inputs", {})),
        hints=hints_data.get("phases", []),
        prohibited=hints_data.get("prohibited", []),
        subcalls=_parse_subcalls(data.get("subcalls", {})),
        guardrails=_parse_guardrails(data.get("guardrails", {})),
        execution=_parse_execution(data.get("execution", {})),
        advisor=_parse_advisor(data.get("advisor")),
        constitution_path=constitution_path,
        constitution_inline=constitution_inline,
        constitution_model=constitution_model,
    )


def _parse_inputs(data: dict[str, Any]) -> list[InputConfig]:
    return [
        InputConfig(
            name=name,
            input_type=input_data.get("type", ""),
            source=input_data.get("source", ""),
            pre_parse=input_data.get("pre_parse", False),
            description=input_data.get("description", ""),
        )
        for name, input_data in data.items()
    ]


def _parse_subcalls(data: dict[str, Any]) -> dict[str, SubcallConfig]:
    return {
        name: SubcallConfig(
            name=name,
            enabled=subcall_data.get("enabled", True),
            custom_impl=subcall_data.get("custom_impl"),
            description=subcall_data.get("description", ""),
        )
        for name, subcall_data in data.items()
    }


def _parse_guardrails(data: dict[str, Any]) -> GuardrailConfig:
    return GuardrailConfig(
        token_budget=data.get("token_budget", 500_000),
        max_iterations=data.get("max_iterations", 100),
        max_subcall_depth=data.get("max_subcall_depth", 1),
        budget_warning_pct=data.get("budget_warning_pct", 80.0),
        max_subcalls=data.get("max_subcalls", 0),
        max_budget_usd=data.get("max_budget_usd", 0.0),
        billable_input_budget=data.get("billable_input_budget", 0),
    )


def _parse_execution(data: dict[str, Any]) -> ExecutionConfig:
    return ExecutionConfig(
        scaffolding=data.get("scaffolding", True),
        compaction_threshold_pct=data.get("compaction_threshold_pct", 0.85),
        hard_ceiling_pct=data.get("hard_ceiling_pct", 0.95),
        compaction_model=data.get("compaction_model"),
        subcall_model=data.get("subcall_model"),
        context_limit=data.get("context_limit", 1_000_000),
        max_parallel_workers=data.get("max_parallel_workers", 4),
    )


def _parse_advisor(data: dict[str, Any] | None) -> AdvisorConfig | None:
    if not data:
        return None
    return AdvisorConfig(
        model=data["model"],
        max_uses=data.get("max_uses", 5),
        max_response_tokens=data.get("max_response_tokens", 500),
        context_window=data.get("context_window", 10),
        enabled=data.get("enabled", True),
    )


def _parse_constitution(
    data: dict[str, Any] | None,
) -> tuple[str | None, ConstitutionManifest | None, str | None]:
    if data is None:
        return None, None, None
    inline_fragment = {key: value for key, value in data.items() if key in _CONSTITUTION_INLINE_KEYS}
    inline = parse_constitution(_inline_constitution_toml(inline_fragment)) if inline_fragment else None
    return data.get("path"), inline, data.get("model")


_CONSTITUTION_SECTIONS = (
    "information_minimality",
    "state_persistence",
    "progress_obligation",
    "source_fidelity",
    "earned_autonomy",
)
_CONSTITUTION_INLINE_KEYS = frozenset((*_CONSTITUTION_SECTIONS, "principles", "version"))


def _inline_constitution_toml(data: dict[str, Any]) -> str:
    parts = [f'version = "{data.get("version", "0.1.0")}"']
    for section_key in _CONSTITUTION_SECTIONS:
        section = data.get(section_key)
        if isinstance(section, dict):
            parts.append(f"\n[{section_key}]")
            parts.extend(_toml_assignment(key, value) for key, value in section.items())
    principles = data.get("principles")
    if isinstance(principles, list):
        for principle in principles:
            parts.append("\n[[principles]]")
            parts.extend(_toml_assignment(key, value) for key, value in principle.items())
    return "\n".join(parts)


def _toml_assignment(key: str, value: Any) -> str:
    if isinstance(value, str):
        return f'{key} = "{value}"'
    if isinstance(value, bool):
        return f"{key} = {str(value).lower()}"
    return f"{key} = {value}"
