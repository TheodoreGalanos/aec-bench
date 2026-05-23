# ABOUTME: Contract review phase for the lambda-rlm adapter.
# ABOUTME: Checks alignment between extracted data and template requirements before generation.

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

from aec_bench.adapters.lambda_rlm.prompts import build_review_prompt
from aec_bench.adapters.lambda_rlm.state import ReviewResult
from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.constitution import SourceFidelityParams

_log = logging.getLogger(__name__)


def parse_review_response(raw_text: str) -> ReviewResult:
    """Parse a review LLM response into a ReviewResult.

    Falls back to 'pass' if the response is malformed — we don't want a
    parsing failure in review to block generation.
    """
    try:
        text = raw_text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [ln for ln in lines if not ln.strip().startswith("```")]
            text = "\n".join(lines)

        data = json.loads(text)
        return ReviewResult(
            status=data.get("status", "pass"),
            gaps=data.get("gaps", []),
            risks=data.get("risks", []),
            reextract_sources=data.get("reextract_sources", []),
            supplement_guidance=data.get("supplement_guidance"),
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        _log.warning("Failed to parse review response, defaulting to pass")
        return ReviewResult(
            status="pass",
            gaps=[],
            risks=[],
            reextract_sources=[],
            supplement_guidance=None,
        )


def run_review(
    *,
    client: RlmClient,
    model: str,
    section_title: str,
    writing_guidance: list[str],
    input_sources: list[str],
    extracted_data: dict[str, Any],
    dependency_summaries: dict[str, str],
    source_fidelity: SourceFidelityParams | None = None,
    source_priority: Mapping[str, int] | None = None,
) -> tuple[ReviewResult, tuple[int, int]]:
    """Run the contract review for a section.

    Returns (ReviewResult, (input_tokens, output_tokens)).
    """
    prompt = build_review_prompt(
        section_title=section_title,
        writing_guidance=list(writing_guidance),
        input_sources=list(input_sources),
        extracted_data=extracted_data,
        dependency_summaries=dependency_summaries,
        source_fidelity=source_fidelity,
        source_priority=source_priority,
    )

    response = client.generate(
        model=model,
        messages=[RlmMessage(role="user", content=prompt)],
        system_prompt=None,
    )

    result = parse_review_response(response.output_text)
    tokens = (response.input_tokens, response.output_tokens)

    _log.info(
        "Review for %r: status=%s, gaps=%d, risks=%d",
        section_title,
        result.status,
        len(result.gaps),
        len(result.risks),
    )

    return result, tokens
