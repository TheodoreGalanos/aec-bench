# ABOUTME: Boundary contracts for the synthesis domain — aggregation of K candidate outputs.
# ABOUTME: Adapter-agnostic shapes used by synthesis.engine and adapter-specific bridges.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class SynthesisCandidate:
    """One candidate draft to be considered by the synthesiser."""

    candidate_id: str
    content: str


# Tool-call trace entries use plain mappings for straightforward trajectory
# serialisation; the contract below re-exports the type alias so callers can
# name it without redefining.
ToolCallTrace = tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class SynthesisCriteria:
    """Neutral criteria contract.

    Adapters with richer internal representations (e.g. lambda-RLM's
    CriteriaBundle) convert to this shape at the domain boundary. Keeps
    the synthesis engine free of adapter-specific imports.
    """

    section_title: str
    writing_rules: tuple[str, ...]
    # (category, text) pairs — category is "essential" / "important" / "optional".
    rubric_criteria: tuple[tuple[str, str], ...]
    expert_personas: tuple[str, ...]
    summary: str = ""


@dataclass(frozen=True)
class SynthesisConfig:
    """Configuration snapshot — serialised into TrialRecord.configuration.

    Defaults match the decisions locked in on 2026-04-19 (see amendment §7):
    Sonnet synthesiser, 80K input cap, 16K output cap, source verification on,
    fallback to pointwise winner on failure.
    """

    synthesiser_model: str = "anthropic:claude-sonnet-4-6"
    max_input_tokens: int = 80_000
    max_output_tokens: int = 16_000
    verify_sources: bool = True
    fallback_on_failure: bool = True
    # Task-domain hint rendered into the prompt. Default suits AEC engineering
    # proposals; override per-task for other domains.
    domain_hint: str = "engineering proposal"
    # "plain" = single LLM call with all K candidates in the prompt.
    # "tool_loop" = AggAgent-style agent with get_candidate / get_source /
    # search_* / get_criteria_bundle / finish tools. See amendment §3.
    synthesis_mode: Literal["plain", "tool_loop"] = "plain"
    # Turn cap for the tool-loop driver. Ignored when synthesis_mode == "plain".
    tool_loop_max_turns: int = 20


@dataclass(frozen=True)
class SynthesisInput:
    """Complete input to synthesis.engine.synthesise()."""

    candidates: tuple[SynthesisCandidate, ...]
    criteria: SynthesisCriteria
    # source_label → extracted content. Mapping rather than dict so callers
    # know the value isn't meant to be mutated.
    references: Mapping[str, str]
    config: SynthesisConfig = field(default_factory=SynthesisConfig)


@dataclass(frozen=True)
class SynthesisOutput:
    """Result of a synthesis call.

    On model-side failure (error, budget exhaustion, empty/malformed output)
    ``fallback_used`` is True and ``fallback_reason`` explains why — the caller
    decides whether to apply its own fallback or surface the error.
    """

    content: str
    reason: str
    synthesiser_model: str
    input_tokens: int
    output_tokens: int
    elapsed_s: float
    fallback_used: bool = False
    fallback_reason: str | None = None
    # Populated only by the tool-loop driver. Plain synthesis leaves defaults.
    synthesiser_turns: int = 0
    tool_calls: ToolCallTrace = ()
