# ABOUTME: Configuration parsing for the lambda-rlm adapter.
# ABOUTME: Reads lambda-rlm.toml into typed, frozen dataclasses.

from __future__ import annotations

import re
import warnings
from dataclasses import dataclass, field
from typing import Any, Literal

from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.synthesis import SynthesisConfig

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]


@dataclass(frozen=True)
class ToolUseCapsConfig:
    """Rate-limit caps for sandbox tool_use mode."""

    max_fetches_per_block: int = 5
    max_total_fetches: int = 30


@dataclass(frozen=True)
class SandboxConfig:
    """Configuration for DocumentSandbox integration."""

    enabled: bool = False
    tool_use: bool = False
    tool_use_caps: ToolUseCapsConfig = field(default_factory=ToolUseCapsConfig)
    extractor_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class GroundingConfig:
    """Config for the post-hoc grounding check (Idea B Layer 3)."""

    check: Literal["default", "off"] = "default"
    custom_facts: dict[str, re.Pattern[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class PlannerConfig:
    """Parameters for the λ-RLM cost-optimal decomposition planner."""

    context_window_chars: int = 100_000
    accuracy_target: float = 0.80
    leaf_accuracy: float = 0.95
    compose_accuracy: float = 0.90
    max_branching_factor: int = 20


@dataclass(frozen=True)
class ReviewConfig:
    """Parameters for the contract review phase."""

    enabled: bool = True
    trigger: str = "always"  # "always" | "uncertainty" | "consistency" | "both" | "never"
    confidence_threshold: float = 0.6
    consistency_threshold: float = 0.7
    max_retries_per_source: int = 1
    max_supplements_per_section: int = 1


@dataclass(frozen=True)
class ExtractConfig:
    """K-fan-out settings for extraction (Idea 3b)."""

    k_candidates: int = 1
    temperature: float = 0.7
    keep_candidates_artifact: bool = False


@dataclass(frozen=True)
class UncertaintyConfig:
    """Formula parameters for joint uncertainty scoring (Idea 3c)."""

    lambda_: float = 0.5
    min_confidence_eps: float = 0.01
    min_samples: int = 3
    review_joint_threshold: float = 1.0


# Tournament modes for best-of-K generation. Only the modes implemented on
# this branch are listed; TournO selection modes (round_robin, etc.) will be
# added alongside the selection-mode implementation.
FillSectionTournamentMode = Literal["pointwise_only", "synthesis"]


@dataclass(frozen=True)
class FillSectionConfig:
    """Best-of-K generation settings. Opt-in per section via apply_to_sections."""

    k_candidates: int = 1
    temperature: float = 1.0
    tournament_mode: FillSectionTournamentMode = "pointwise_only"
    # Empty tuple means "apply to all sections when k_candidates>1".
    apply_to_sections: tuple[str, ...] = ()
    synthesis: SynthesisConfig = field(default_factory=SynthesisConfig)


ComposeMode = Literal["orchestrated", "agentic"]


@dataclass(frozen=True)
class ComposeConfig:
    """Compose-mode rendering config.

    orchestrated (default): F/G blocks make direct LLM calls bundling
    source content. Scratchpad is ignored.
    agentic: F/G blocks consult a shared scratchpad first and fall back
    to LLM calls for missing slots; values are written back so later
    blocks resolve without re-extraction.

    The `planning_phase` config is orthogonal: agentic mode works with
    or without an upfront planning turn. When `planning_phase.enabled`
    is True and `mode == "orchestrated"`, the planning turn is a no-op.
    """

    mode: ComposeMode = "orchestrated"
    planning_phase_blocking: bool = True


@dataclass(frozen=True)
class BackBriefConfig:
    """Second planning-phase pass that summarises reference docs into a
    per-topic digest stored on the scratchpad under the reserved key
    `_back_brief`. Consumed by `_format_sources` when it sees a label of the
    form `references/*:<topic>`.

    A no-op when `ComposeConfig.mode != "agentic"` or `enabled = False`.
    """

    enabled: bool = False
    sources: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    model: str | None = None
    max_output_tokens: int = 2000


@dataclass(frozen=True)
class ScopeEvolutionConfig:
    """Planning-phase pass that reads the primary source (typically an email
    thread) and produces an authoritative summary of how the client's ask
    evolved across the thread: initial ask, narrowing moments, final agreed
    scope, and explicit exclusion signals. Stored on the scratchpad under the
    reserved key `_scope_evolution` as a single multi-line string. Surfaced
    at the top of compose-mode block generation prompts as the authority on
    what is in/out of scope when the raw thread contains a negotiation.

    A no-op when `ComposeConfig.mode != "agentic"` or `enabled = False`.
    """

    enabled: bool = False
    sources: tuple[str, ...] = ()
    model: str | None = None
    max_output_tokens: int = 2000


@dataclass(frozen=True)
class PlanningPhaseConfig:
    """Upfront scratchpad-seeding turn for agentic compose-mode.

    When enabled, the executor makes one LLM call before the first
    compose section to extract `extract_slots` values from `sources`
    into `PlanState.compose_scratchpad`. Subsequent F blocks then
    resolve those slots via zero-LLM scratchpad reads.

    Only runs when `ComposeConfig.mode == "agentic"`; a no-op in
    orchestrated mode regardless of `enabled`.
    """

    enabled: bool = False
    extract_slots: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    back_brief: BackBriefConfig = field(default_factory=BackBriefConfig)
    scope_evolution: ScopeEvolutionConfig = field(default_factory=ScopeEvolutionConfig)


@dataclass(frozen=True)
class TemplateMeta:
    """Optional `[meta]` block on report_template.toml that overrides the
    adapter's hardcoded prompt strings. All fields default to None; the
    adapter falls back to its built-in defaults when a field is absent.
    """

    voice: str | None = None
    domain: str | None = None
    planning_guidance: str | None = None


@dataclass(frozen=True)
class StructureEnforcementConfig:
    """Per-section structure validation with bounded retries.

    When enabled, the executor calls a presence-only Haiku validator
    after each `_generate_section`. On miss, the section is regenerated
    with a gap-list addendum up to `max_retries` times. Default is
    Haiku 4.5 — presence-only checks are well within its band, and
    per-call cost is rounding error against Sonnet generation spend.
    """

    enabled: bool = False
    max_retries: int = 2
    validator_model: str = "au.anthropic.claude-haiku-4-5"


@dataclass(frozen=True)
class LambdaRlmConfig:
    """Complete lambda-rlm adapter configuration."""

    template_tier: str = "dependency_tree"
    template_definition: str | None = None
    planner: PlannerConfig = PlannerConfig()
    review: ReviewConfig = ReviewConfig()
    extract: ExtractConfig = field(default_factory=ExtractConfig)
    uncertainty: UncertaintyConfig = field(default_factory=UncertaintyConfig)
    token_budget: int = 500_000
    max_parallel_workers: int = 4
    advisor: AdvisorConfig | None = None
    constitution_path: str | None = None
    constitution_inline: dict[str, Any] | None = None
    constitution_model: str | None = None
    fill_section: FillSectionConfig = field(default_factory=FillSectionConfig)
    compose: ComposeConfig = field(default_factory=ComposeConfig)
    planning_phase: PlanningPhaseConfig = field(default_factory=PlanningPhaseConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    grounding: GroundingConfig = field(default_factory=GroundingConfig)
    structure_enforcement: StructureEnforcementConfig = field(
        default_factory=StructureEnforcementConfig,
    )

    @property
    def uncertainty_scoring_active(self) -> bool:
        """Whether uncertainty scoring is active, derived from review.trigger."""
        return self.review.trigger in ("uncertainty", "both")


def parse_lambda_rlm_config(toml_str: str) -> LambdaRlmConfig:
    """Parse a lambda-rlm.toml string into a LambdaRlmConfig."""
    raw = tomllib.loads(toml_str)

    template = raw.get("template", {})
    planner_raw = raw.get("planner", {})
    review_raw = raw.get("review", {})
    guardrails_raw = raw.get("guardrails", {})

    planner = PlannerConfig(
        context_window_chars=planner_raw.get("context_window_chars", 100_000),
        accuracy_target=planner_raw.get("accuracy_target", 0.80),
        leaf_accuracy=planner_raw.get("leaf_accuracy", 0.95),
        compose_accuracy=planner_raw.get("compose_accuracy", 0.90),
        max_branching_factor=planner_raw.get("max_branching_factor", 20),
    )

    review = ReviewConfig(
        enabled=review_raw.get("enabled", True),
        trigger=review_raw.get("trigger", "always"),
        confidence_threshold=review_raw.get("confidence_threshold", 0.6),
        consistency_threshold=review_raw.get("consistency_threshold", 0.7),
        max_retries_per_source=review_raw.get("max_retries_per_source", 1),
        max_supplements_per_section=review_raw.get("max_supplements_per_section", 1),
    )

    execution_raw = raw.get("execution", {})

    advisor: AdvisorConfig | None = None
    advisor_data = raw.get("advisor")
    if advisor_data:
        advisor = AdvisorConfig(
            model=advisor_data["model"],
            max_uses=advisor_data.get("max_uses", 5),
            max_response_tokens=advisor_data.get("max_response_tokens", 500),
            context_window=advisor_data.get("context_window", 10),
            enabled=advisor_data.get("enabled", True),
        )

    constitution_raw = raw.get("constitution", {})
    constitution_path: str | None = None
    constitution_inline: dict[str, Any] | None = None
    constitution_model: str | None = None
    if constitution_raw:
        constitution_path = constitution_raw.get("path")
        constitution_model = constitution_raw.get("model")
        inline_data = constitution_raw.get("inline")
        if inline_data is not None:
            constitution_inline = inline_data

    fill_section = _parse_fill_section(raw.get("fill_section", {}))

    # Top-level k_candidates is a shared default for [extract] and [fill_section].
    # Keep a fallback to [template].k_candidates for local backward compatibility.
    top_level_k = raw.get("k_candidates", template.get("k_candidates", 1))

    extract = _parse_extract_config(raw.get("extract", {}), top_level_k)
    uncertainty = _parse_uncertainty_config(raw.get("uncertainty", {}))
    compose = _parse_compose_config(raw.get("compose", {}))
    planning_phase = _parse_planning_phase_config(raw.get("planning_phase", {}))
    sandbox = _parse_sandbox(raw)
    grounding = _parse_grounding(raw)
    structure_enforcement = _parse_structure_enforcement(raw)

    # Propagate top-level k_candidates to fill_section if not overridden.
    if "fill_section" not in raw or "k_candidates" not in raw.get("fill_section", {}):
        from dataclasses import replace

        fill_section = replace(fill_section, k_candidates=top_level_k)

    # Validation.
    _validate_config(extract, review, uncertainty)

    return LambdaRlmConfig(
        template_tier=template.get("tier", "dependency_tree"),
        template_definition=template.get("definition"),
        planner=planner,
        review=review,
        extract=extract,
        uncertainty=uncertainty,
        token_budget=guardrails_raw.get("token_budget", 500_000),
        max_parallel_workers=execution_raw.get("max_parallel_workers", 4),
        advisor=advisor,
        constitution_path=constitution_path,
        constitution_inline=constitution_inline,
        constitution_model=constitution_model,
        fill_section=fill_section,
        compose=compose,
        planning_phase=planning_phase,
        sandbox=sandbox,
        grounding=grounding,
        structure_enforcement=structure_enforcement,
    )


def _parse_fill_section(raw: dict[str, Any]) -> FillSectionConfig:
    if not raw:
        return FillSectionConfig()

    mode = raw.get("tournament_mode", "pointwise_only")
    if mode not in ("pointwise_only", "synthesis"):
        raise ValueError(
            f"unsupported tournament_mode {mode!r}; currently implemented: pointwise_only, synthesis",
        )

    synthesis_raw = raw.get("synthesis", {})
    synthesis = SynthesisConfig(
        synthesiser_model=synthesis_raw.get(
            "synthesiser_model",
            SynthesisConfig().synthesiser_model,
        ),
        max_input_tokens=synthesis_raw.get(
            "max_input_tokens",
            SynthesisConfig().max_input_tokens,
        ),
        max_output_tokens=synthesis_raw.get(
            "max_output_tokens",
            SynthesisConfig().max_output_tokens,
        ),
        verify_sources=synthesis_raw.get(
            "verify_sources",
            SynthesisConfig().verify_sources,
        ),
        fallback_on_failure=synthesis_raw.get(
            "fallback_on_failure",
            SynthesisConfig().fallback_on_failure,
        ),
        domain_hint=synthesis_raw.get(
            "domain_hint",
            SynthesisConfig().domain_hint,
        ),
        synthesis_mode=synthesis_raw.get(
            "synthesis_mode",
            SynthesisConfig().synthesis_mode,
        ),
        tool_loop_max_turns=synthesis_raw.get(
            "tool_loop_max_turns",
            SynthesisConfig().tool_loop_max_turns,
        ),
    )

    apply_to = tuple(raw.get("apply_to_sections", ()))

    return FillSectionConfig(
        k_candidates=raw.get("k_candidates", 1),
        temperature=raw.get("temperature", 1.0),
        tournament_mode=mode,
        apply_to_sections=apply_to,
        synthesis=synthesis,
    )


def _parse_compose_config(raw: dict[str, Any]) -> ComposeConfig:
    if not raw:
        return ComposeConfig()
    mode = raw.get("mode", "orchestrated")
    if mode not in ("orchestrated", "agentic"):
        raise ValueError(
            f"unsupported compose mode {mode!r}; expected 'orchestrated' or 'agentic'",
        )
    return ComposeConfig(
        mode=mode,
        planning_phase_blocking=raw.get("planning_phase_blocking", True),
    )


def _parse_back_brief_config(raw: dict[str, Any]) -> BackBriefConfig:
    return BackBriefConfig(
        enabled=raw.get("enabled", False),
        sources=tuple(raw.get("sources", [])),
        topics=tuple(raw.get("topics", [])),
        model=raw.get("model"),
        max_output_tokens=raw.get("max_output_tokens", 2000),
    )


def _parse_scope_evolution_config(raw: dict[str, Any]) -> ScopeEvolutionConfig:
    return ScopeEvolutionConfig(
        enabled=raw.get("enabled", False),
        sources=tuple(raw.get("sources", [])),
        model=raw.get("model"),
        max_output_tokens=raw.get("max_output_tokens", 2000),
    )


def _parse_planning_phase_config(raw: dict[str, Any]) -> PlanningPhaseConfig:
    if not raw:
        return PlanningPhaseConfig()
    back_brief = _parse_back_brief_config(raw.get("back_brief", {}))
    scope_evolution = _parse_scope_evolution_config(raw.get("scope_evolution", {}))
    return PlanningPhaseConfig(
        enabled=raw.get("enabled", False),
        extract_slots=tuple(raw.get("extract_slots", ())),
        sources=tuple(raw.get("sources", ())),
        back_brief=back_brief,
        scope_evolution=scope_evolution,
    )


def _parse_sandbox(raw: dict[str, Any]) -> SandboxConfig:
    section = raw.get("sandbox", {})
    caps_raw = section.get("tool_use_caps", {})
    caps = ToolUseCapsConfig(
        max_fetches_per_block=int(caps_raw.get("max_fetches_per_block", 5)),
        max_total_fetches=int(caps_raw.get("max_total_fetches", 30)),
    )
    return SandboxConfig(
        enabled=bool(section.get("enabled", False)),
        tool_use=bool(section.get("tool_use", False)),
        tool_use_caps=caps,
        extractor_overrides=dict(section.get("extractor_overrides", {})),
    )


def _parse_grounding(raw: dict[str, Any]) -> GroundingConfig:
    section = raw.get("grounding", {})
    custom_raw = section.get("custom_facts", {})
    compiled = {name: re.compile(pat) for name, pat in custom_raw.items()}
    check = section.get("check", "default")
    if check not in ("default", "off"):
        msg = f"grounding.check must be 'default' or 'off', got {check!r}"
        raise ValueError(msg)
    return GroundingConfig(check=check, custom_facts=compiled)


def _parse_structure_enforcement(raw: dict[str, Any]) -> StructureEnforcementConfig:
    section = raw.get("structure_enforcement", {})
    if not section:
        return StructureEnforcementConfig()
    return StructureEnforcementConfig(
        enabled=bool(section.get("enabled", False)),
        max_retries=int(section.get("max_retries", 2)),
        validator_model=section.get(
            "validator_model",
            "au.anthropic.claude-haiku-4-5",
        ),
    )


def _parse_extract_config(
    raw: dict[str, Any],
    top_level_k: int,
) -> ExtractConfig:
    if not raw:
        return ExtractConfig(k_candidates=top_level_k)

    return ExtractConfig(
        k_candidates=raw.get("k_candidates", top_level_k),
        temperature=raw.get("temperature", 0.7),
        keep_candidates_artifact=raw.get("keep_candidates_artifact", False),
    )


def _parse_uncertainty_config(raw: dict[str, Any]) -> UncertaintyConfig:
    if not raw:
        return UncertaintyConfig()

    return UncertaintyConfig(
        lambda_=raw.get("lambda", 0.5),
        min_confidence_eps=raw.get("min_confidence_eps", 0.01),
        min_samples=raw.get("min_samples", 3),
        review_joint_threshold=raw.get("review_joint_threshold", 1.0),
    )


def _validate_config(
    extract: ExtractConfig,
    review: ReviewConfig,
    uncertainty: UncertaintyConfig,  # noqa: ARG001
) -> None:
    """Validate cross-cutting config rules."""
    if extract.k_candidates < 1:
        msg = f"extract.k_candidates must be >= 1, got {extract.k_candidates}"
        raise ValueError(msg)

    if extract.k_candidates > 1 and extract.temperature == 0.0:
        warnings.warn(
            "extract.temperature is 0.0 with k_candidates > 1; "
            "all K candidates will be identical, yielding no consistency signal",
            stacklevel=2,
        )

    if extract.k_candidates == 1 and extract.temperature != ExtractConfig().temperature:
        warnings.warn(
            "extract.temperature is set but k_candidates is 1; temperature has no effect on single-call extraction",
            stacklevel=2,
        )

    if review.trigger in ("consistency", "both") and extract.k_candidates == 1:
        warnings.warn(
            f"review.trigger={review.trigger!r} requires k_candidates > 1 "
            "to produce consistency data; review will fall back to 'always'",
            stacklevel=2,
        )


def parse_template_meta(template_toml: str) -> TemplateMeta:
    """Parse the optional `[meta]` block from a report_template.toml string."""
    raw = tomllib.loads(template_toml).get("meta", {})
    return TemplateMeta(
        voice=raw.get("voice"),
        domain=raw.get("domain"),
        planning_guidance=raw.get("planning_guidance"),
    )
