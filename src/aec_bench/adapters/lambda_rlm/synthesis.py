# ABOUTME: Lambda-RLM ↔ synthesis-domain bridge — converts CriteriaBundle, handles fallback, emits trajectory event.
# ABOUTME: Called from PlanExecutor._generate_section when tournament_mode == "synthesis".

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aec_bench.adapters.lambda_rlm.criteria import CriteriaBundle
from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
    SynthesisInput,
    SynthesisOutput,
)
from aec_bench.providers.behavioral_llm import (
    BedrockBehavioralLLMClient,
    build_behavioral_llm_client,
    detect_behavioral_provider,
)
from aec_bench.synthesis.engine import (
    BehavioralLLMClient,
    SynthesisBudgetError,
    synthesise,
)

_log = logging.getLogger(__name__)

# Long read_timeout for the synthesiser Bedrock client. Synthesis prompts can
# push past the default 60s boto3 read timeout on large inputs.
_SYNTHESIS_READ_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class CandidateGeneration:
    """One K-parallel candidate produced by the normal section-generation path."""

    candidate_id: str
    content: str
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class SynthesisSectionResult:
    """Bridge return value: chosen content + trajectory event payload."""

    content: str
    trajectory_event: dict[str, Any]
    used_synthesiser: bool  # False if fallback kicked in


def _bundle_to_contract(bundle: CriteriaBundle) -> SynthesisCriteria:
    """Convert lambda-RLM's internal CriteriaBundle to the neutral contract shape."""
    rubric_criteria = tuple((c.category, c.text) for c in bundle.rubric_criteria)
    return SynthesisCriteria(
        section_title=bundle.section_title,
        writing_rules=tuple(bundle.writing_rules),
        rubric_criteria=rubric_criteria,
        expert_personas=tuple(bundle.expert_personas),
        summary=bundle.summary,
    )


def _build_synthesiser_client(config: SynthesisConfig) -> BehavioralLLMClient:
    """Build the provider-appropriate behavioural LLM client with a long read timeout."""
    model = config.synthesiser_model
    if detect_behavioral_provider(model) == "bedrock":
        return BedrockBehavioralLLMClient(
            model=model,
            read_timeout_seconds=_SYNTHESIS_READ_TIMEOUT_SECONDS,
        )
    # Anthropic direct client already has a 90s httpx timeout — sufficient.
    return build_behavioral_llm_client(model)


def _build_synthesiser_pydantic_model(config: SynthesisConfig):  # noqa: ANN202
    """Build a pydantic-ai compatible model for tool-loop synthesis.

    Mirrors the detection logic in ``_build_synthesiser_client`` — Bedrock
    model names route through BedrockConverseModel, everything else is
    handed to pydantic-ai as a raw model string.
    """
    model = config.synthesiser_model
    if detect_behavioral_provider(model) == "bedrock":
        import os

        from pydantic_ai.models.bedrock import BedrockConverseModel
        from pydantic_ai.providers.bedrock import BedrockProvider

        provider_kwargs: dict[str, str] = {}
        region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION")
        if region:
            provider_kwargs["region_name"] = region
        return BedrockConverseModel(model, provider=BedrockProvider(**provider_kwargs))
    return model


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _fallback_by_length(
    candidates: Sequence[CandidateGeneration],
) -> CandidateGeneration:
    """Pointwise-free fallback: longest candidate wins.

    We deliberately do NOT reuse the tournament pairwise judge for fallback —
    that would add K*(K-1)/2 LLM calls to recover from a synthesiser failure,
    which defeats the point. Longest-candidate is a cheap heuristic; callers
    can override by constructing their own fallback if needed.
    """
    return max(candidates, key=lambda c: len(c.content))


def synthesise_section(
    *,
    section_id: str,
    candidates: Sequence[CandidateGeneration],
    bundle: CriteriaBundle,
    references: Mapping[str, str],
    config: SynthesisConfig,
) -> SynthesisSectionResult:
    """Run synthesis for one section and return content + trajectory event.

    The caller generates K candidates via the normal section-generation path
    and passes them in. On synthesiser failure or budget violation, falls back
    to the longest candidate (cheap heuristic — see `_fallback_by_length`).
    """
    if not candidates:
        raise ValueError("synthesise_section requires at least one candidate")

    # K=1 shortcut — no synthesis needed, return the single candidate.
    if len(candidates) == 1:
        only = candidates[0]
        return SynthesisSectionResult(
            content=only.content,
            trajectory_event={
                "step_type": "section_synthesis",
                "section_id": section_id,
                "k": 1,
                "candidates": [
                    {
                        "id": only.candidate_id,
                        "content": only.content,
                        "content_hash": _content_hash(only.content),
                        "tokens": only.input_tokens + only.output_tokens,
                    },
                ],
                "synthesiser_model": config.synthesiser_model,
                "synthesiser_input_tokens": 0,
                "synthesiser_output_tokens": 0,
                "elapsed_s": 0.0,
                "synthesised_hash": _content_hash(only.content),
                "reason": "single_candidate_pass_through",
                "fallback_used": False,
                "fallback_reason": None,
            },
            used_synthesiser=False,
        )

    synthesis_input = SynthesisInput(
        candidates=tuple(SynthesisCandidate(candidate_id=c.candidate_id, content=c.content) for c in candidates),
        criteria=_bundle_to_contract(bundle),
        references=references,
        config=config,
    )

    fallback_reason: str | None = None
    output: SynthesisOutput | None = None
    try:
        if config.synthesis_mode == "tool_loop":
            output = synthesise(
                synthesis_input,
                model=_build_synthesiser_pydantic_model(config),
            )
        else:
            output = synthesise(
                synthesis_input,
                client=_build_synthesiser_client(config),
            )
    except SynthesisBudgetError as exc:
        fallback_reason = f"budget_exceeded: {exc}"
        _log.warning("synthesis budget exceeded for %s: %s", section_id, exc)

    if output is None or output.fallback_used:
        # Fallback path
        if output is not None:
            fallback_reason = output.fallback_reason
        if not config.fallback_on_failure:
            raise RuntimeError(
                f"synthesis failed for {section_id} and fallback_on_failure is False: {fallback_reason}",
            )
        chosen = _fallback_by_length(candidates)
        _log.warning(
            "synthesis falling back to candidate %s for section %s (reason=%s)",
            chosen.candidate_id,
            section_id,
            fallback_reason,
        )
        return SynthesisSectionResult(
            content=chosen.content,
            trajectory_event=_build_event(
                section_id=section_id,
                candidates=candidates,
                config=config,
                chosen_hash=_content_hash(chosen.content),
                synthesis_output=output,  # may be None for budget errors
                fallback_used=True,
                fallback_reason=fallback_reason,
            ),
            used_synthesiser=False,
        )

    return SynthesisSectionResult(
        content=output.content,
        trajectory_event=_build_event(
            section_id=section_id,
            candidates=candidates,
            config=config,
            chosen_hash=_content_hash(output.content),
            synthesis_output=output,
            fallback_used=False,
            fallback_reason=None,
        ),
        used_synthesiser=True,
    )


def _build_event(
    *,
    section_id: str,
    candidates: Sequence[CandidateGeneration],
    config: SynthesisConfig,
    chosen_hash: str,
    synthesis_output: SynthesisOutput | None,
    fallback_used: bool,
    fallback_reason: str | None,
) -> dict[str, Any]:
    return {
        "step_type": "section_synthesis",
        "section_id": section_id,
        "k": len(candidates),
        "candidates": [
            {
                "id": c.candidate_id,
                "content": c.content,
                "content_hash": _content_hash(c.content),
                "tokens": c.input_tokens + c.output_tokens,
            }
            for c in candidates
        ],
        "synthesiser_model": config.synthesiser_model,
        "synthesiser_input_tokens": synthesis_output.input_tokens if synthesis_output else 0,
        "synthesiser_output_tokens": synthesis_output.output_tokens if synthesis_output else 0,
        "elapsed_s": synthesis_output.elapsed_s if synthesis_output else 0.0,
        "synthesised_hash": chosen_hash,
        "reason": synthesis_output.reason if synthesis_output else "",
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
    }
