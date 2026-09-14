# ABOUTME: Lambda-RLM ↔ synthesis-domain bridge — converts CriteriaBundle, handles fallback, emits trajectory event.
# ABOUTME: Called from PlanExecutor._generate_section when tournament_mode == "synthesis".

from __future__ import annotations

import hashlib
import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from aec_bench.adapters.rlm.client import RlmClient, RlmCompletionResponse, RlmMessage
from aec_bench.adapters.runtime_limits import AdapterRuntimeLimitError
from aec_bench.contracts.synthesis import (
    SynthesisCandidate,
    SynthesisConfig,
    SynthesisCriteria,
    SynthesisInput,
    SynthesisOutput,
)
from aec_bench.synthesis.engine import (
    SynthesisBudgetError,
    synthesise,
)
from aec_bench.templates.report.criteria import CriteriaBundle

_log = logging.getLogger(__name__)


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
        summary=bundle.format_for_judge(),
    )


class _SynthesisClient:
    def __init__(self, client: RlmClient, model: str) -> None:
        self.client = client
        self.model = model
        self.response: RlmCompletionResponse | None = None
        self.limit_error: AdapterRuntimeLimitError | None = None

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 4000) -> str:
        try:
            self.response = self.client.generate(
                model=self.model,
                messages=[RlmMessage(role="user", content=prompt)],
                system_prompt=None,
                temperature=temperature,
                max_output_tokens=max_tokens,
            )
        except AdapterRuntimeLimitError as exc:
            self.limit_error = exc
            raise
        return self.response.output_text


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
    client: RlmClient,
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
        if config.synthesis_mode != "plain":
            raise ValueError("lambda-RLM supports only plain synthesis with run accounting")
        bridge = _SynthesisClient(client, config.synthesiser_model)
        output = synthesise(synthesis_input, client=bridge)
        if bridge.limit_error is not None:
            raise bridge.limit_error
        if bridge.response is not None:
            from dataclasses import replace

            output = replace(
                output, input_tokens=bridge.response.input_tokens, output_tokens=bridge.response.output_tokens
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
