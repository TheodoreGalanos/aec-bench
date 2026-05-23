# ABOUTME: LLM-backed pairwise judge for the optional best-of-k tournament step.
# ABOUTME: Wraps an RlmClient with deterministic position-bias swap and verdict parsing.

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass

from aec_bench.adapters.lambda_rlm.criteria import CriteriaBundle
from aec_bench.adapters.lambda_rlm.tournament import (
    PairwiseOutcome,
    _should_swap_stable,
)
from aec_bench.adapters.rlm.client import RlmClient, RlmMessage

_log = logging.getLogger(__name__)

_JUDGE_SYSTEM_INSTRUCTION = (
    "You are an expert evaluator of professional engineering documents. You "
    "compare two candidate versions of a single section and pick the one that "
    "better satisfies the stated writing rules and evaluation criteria, with "
    "factual accuracy verified against any source documents provided. You are "
    "decisive and concise."
)

_VERDICT_RE = re.compile(r"VERDICT:\s*([AB])", re.IGNORECASE)
_REASONING_RE = re.compile(r"REASONING:\s*(.+?)(?:\n|$)", re.IGNORECASE)


def _format_references(reference_materials: Mapping[str, str] | None) -> str:
    """Render reference docs for the prompt the same way verify.py does."""
    if not reference_materials:
        return ""
    sections = [f"### {name}\n\n{content}" for name, content in reference_materials.items()]
    return "SOURCE DOCUMENTS (use these to verify factual claims):\n\n" + "\n\n".join(sections) + "\n\n---\n\n"


def _build_prompt(
    bundle: CriteriaBundle,
    completion_a: str,
    completion_b: str,
    reference_materials: Mapping[str, str] | None,
) -> str:
    """Build the full pairwise judge prompt.

    VERDICT comes before REASONING so a truncated response still parses.
    """
    criteria_block = bundle.format_for_judge()
    refs_block = _format_references(reference_materials)
    return (
        f"{_JUDGE_SYSTEM_INSTRUCTION}\n\n"
        f"{criteria_block}\n\n"
        "---\n\n"
        f"{refs_block}"
        "Read the two candidate versions of this section below and pick the "
        "one that better satisfies the writing rules and evaluation criteria. "
        "Focus on substance, coverage of mandatory items, fit with the rubric, "
        "and factual accuracy against the source documents. Do not reward "
        "length for its own sake. If both are roughly equivalent, pick the "
        "one with better coverage of ESSENTIAL criteria.\n\n"
        "---\n\n"
        "CANDIDATE A:\n"
        f"{completion_a}\n\n"
        "---\n\n"
        "CANDIDATE B:\n"
        f"{completion_b}\n\n"
        "---\n\n"
        "Output exactly two lines in this format. Start with VERDICT so your "
        "answer is not truncated:\n"
        "VERDICT: A  (or B)\n"
        "REASONING: <one sentence explaining your choice>\n"
    )


def _parse_verdict(raw: str) -> tuple[str | None, str]:
    """Extract verdict letter and reasoning from a judge response."""
    verdict_match = _VERDICT_RE.search(raw)
    reasoning_match = _REASONING_RE.search(raw)
    reasoning = reasoning_match.group(1).strip() if reasoning_match else ""
    if not verdict_match:
        return (None, reasoning)
    letter = verdict_match.group(1).upper()
    if letter not in ("A", "B"):
        return (None, reasoning)
    return (letter, reasoning)


@dataclass(frozen=True)
class LlmPairwiseJudge:
    """Pairwise judge implementation backed by an RlmClient.

    The bundle, model, and optional reference materials are bound at construction
    time. The ``compare()`` method runs a single comparison and returns a
    ``PairwiseOutcome`` with deterministic position-bias mitigation.
    """

    client: RlmClient
    model: str
    bundle: CriteriaBundle
    reference_materials: Mapping[str, str] | None = None

    def compare(
        self,
        *,
        a_id: str,
        b_id: str,
        completion_a: str,
        completion_b: str,
    ) -> PairwiseOutcome:
        """Run one pairwise comparison; returns who won (a_id or b_id)."""
        swap = _should_swap_stable(self.bundle.section_id, a_id, b_id)
        if swap:
            shown_a, shown_b = completion_b, completion_a
            shown_a_id, shown_b_id = b_id, a_id
        else:
            shown_a, shown_b = completion_a, completion_b
            shown_a_id, shown_b_id = a_id, b_id

        prompt = _build_prompt(self.bundle, shown_a, shown_b, self.reference_materials)
        response = self.client.generate(
            model=self.model,
            messages=[RlmMessage(role="user", content=prompt)],
            system_prompt=None,
        )
        verdict, reasoning = _parse_verdict(response.output_text or "")

        if verdict is None:
            _log.warning(
                "Pairwise judge returned unparsable verdict for %s vs %s in section %s; defaulting to A as winner",
                a_id,
                b_id,
                self.bundle.section_id,
            )
            # Fail-safe: default to A so we always make progress; the trajectory
            # will record the unparsable raw response for diagnostic review.
            verdict = "A"

        winner_shown = shown_a_id if verdict == "A" else shown_b_id
        a_won = winner_shown == a_id
        return PairwiseOutcome(
            a_id=a_id,
            b_id=b_id,
            a_won=a_won,
            reasoning=reasoning,
        )
