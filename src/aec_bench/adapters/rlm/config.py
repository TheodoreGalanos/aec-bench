# ABOUTME: Schema and parser for rlm.toml task harness configuration.
# ABOUTME: Defines what inputs, output template, sub-calls, and guardrails a task declares.

from __future__ import annotations

from dataclasses import dataclass, field

from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.constitution import (
    ConstitutionManifest,
    parse_constitution,
)

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


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

    template_tier = data.get("template", {}).get("tier", "flat")
    template_definition: str | None = data.get("template", {}).get("definition")

    inputs: list[InputConfig] = []
    for name, input_data in data.get("inputs", {}).items():
        inputs.append(
            InputConfig(
                name=name,
                input_type=input_data.get("type", ""),
                source=input_data.get("source", ""),
                pre_parse=input_data.get("pre_parse", False),
                description=input_data.get("description", ""),
            )
        )

    hints_data = data.get("hints", {})
    hints = hints_data.get("phases", [])
    prohibited = hints_data.get("prohibited", [])

    subcalls: dict[str, SubcallConfig] = {}
    for name, sc_data in data.get("subcalls", {}).items():
        subcalls[name] = SubcallConfig(
            name=name,
            enabled=sc_data.get("enabled", True),
            custom_impl=sc_data.get("custom_impl"),
            description=sc_data.get("description", ""),
        )

    guardrail_data = data.get("guardrails", {})
    guardrails = GuardrailConfig(
        token_budget=guardrail_data.get("token_budget", 500_000),
        max_iterations=guardrail_data.get("max_iterations", 100),
        max_subcall_depth=guardrail_data.get("max_subcall_depth", 1),
        budget_warning_pct=guardrail_data.get("budget_warning_pct", 80.0),
        max_subcalls=guardrail_data.get("max_subcalls", 0),
        max_budget_usd=guardrail_data.get("max_budget_usd", 0.0),
        billable_input_budget=guardrail_data.get("billable_input_budget", 0),
    )

    execution_data = data.get("execution", {})
    execution = ExecutionConfig(
        scaffolding=execution_data.get("scaffolding", True),
        compaction_threshold_pct=execution_data.get("compaction_threshold_pct", 0.85),
        hard_ceiling_pct=execution_data.get("hard_ceiling_pct", 0.95),
        compaction_model=execution_data.get("compaction_model"),
        subcall_model=execution_data.get("subcall_model"),
        context_limit=execution_data.get("context_limit", 1_000_000),
        max_parallel_workers=execution_data.get("max_parallel_workers", 4),
    )

    advisor: AdvisorConfig | None = None
    advisor_data = data.get("advisor")
    if advisor_data:
        advisor = AdvisorConfig(
            model=advisor_data["model"],
            max_uses=advisor_data.get("max_uses", 5),
            max_response_tokens=advisor_data.get("max_response_tokens", 500),
            context_window=advisor_data.get("context_window", 10),
            enabled=advisor_data.get("enabled", True),
        )

    constitution_path: str | None = None
    constitution_inline: ConstitutionManifest | None = None
    constitution_model: str | None = None

    constitution_data = data.get("constitution")
    if constitution_data is not None:
        constitution_path = constitution_data.get("path")
        constitution_model = constitution_data.get("model")
        # If any inline parameter tables are present, re-serialise them as a
        # minimal TOML string and pass to parse_constitution().
        inline_keys = {
            "information_minimality",
            "state_persistence",
            "progress_obligation",
            "source_fidelity",
            "earned_autonomy",
            "principles",
            "version",
        }
        inline_fragment = {k: v for k, v in constitution_data.items() if k in inline_keys}
        if inline_fragment:
            toml_parts: list[str] = []
            if "version" in inline_fragment:
                toml_parts.append(f'version = "{inline_fragment["version"]}"')
            for section_key in (
                "information_minimality",
                "state_persistence",
                "progress_obligation",
                "source_fidelity",
                "earned_autonomy",
            ):
                section = inline_fragment.get(section_key)
                if isinstance(section, dict):
                    toml_parts.append(f"\n[{section_key}]")
                    for k, v in section.items():
                        if isinstance(v, str):
                            toml_parts.append(f'{k} = "{v}"')
                        elif isinstance(v, bool):
                            toml_parts.append(f"{k} = {str(v).lower()}")
                        else:
                            toml_parts.append(f"{k} = {v}")
            principles_list = inline_fragment.get("principles")
            if isinstance(principles_list, list):
                for principle_entry in principles_list:
                    toml_parts.append("\n[[principles]]")
                    for k, v in principle_entry.items():
                        if isinstance(v, str):
                            toml_parts.append(f'{k} = "{v}"')
                        elif isinstance(v, bool):
                            toml_parts.append(f"{k} = {str(v).lower()}")
                        else:
                            toml_parts.append(f"{k} = {v}")
            if "version" not in inline_fragment:
                toml_parts.insert(0, 'version = "0.1.0"')
            constitution_inline = parse_constitution("\n".join(toml_parts))

    return RlmConfig(
        template_tier=template_tier,
        template_definition=template_definition,
        inputs=inputs,
        hints=hints,
        prohibited=prohibited,
        subcalls=subcalls,
        guardrails=guardrails,
        execution=execution,
        advisor=advisor,
        constitution_path=constitution_path,
        constitution_inline=constitution_inline,
        constitution_model=constitution_model,
    )
