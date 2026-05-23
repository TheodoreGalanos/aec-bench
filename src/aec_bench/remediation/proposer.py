# ABOUTME: LLM-driven patch proposer — turns verifier criterion + evidence into a surgical patch.
# ABOUTME: Returns PatchStatus.REVIEW when the LLM judges the defect unfixable from available sources.

from __future__ import annotations

import json
import re

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.remediation import (
    Patch,
    PatchProposal,
    PatchStatus,
)

_SYSTEM_PROMPT = """\
You are a technical editor fixing defects in an engineering Scope of Works.

You are given:
- A section excerpt from the document
- A criterion the section failed
- Evidence explaining why it failed

Your task: propose ONE surgical patch that addresses the criterion, using only
facts present in the section excerpt or commonly implied by the writing guidance.
Do NOT invent facts. If the defect cannot be fixed without additional source
information, respond with status="review" and explain what information is needed.

Respond with ONLY a JSON object of this shape:

{
  "status": "apply" | "review",
  "locator_phrase": "<exact substring from the excerpt to replace>",
  "replacement": "<replacement text>",
  "occurrence": <int, 1 if the phrase appears once in the excerpt>,
  "rationale": "<1-2 sentence explanation>",
  "confidence": "high" | "medium" | "low"
}

When status is "review", locator_phrase/replacement/occurrence may be omitted or empty.
Return ONLY the JSON object — no prose, no code fences.
"""


def _build_user_prompt(
    section_id: str,
    section_excerpt: str,
    criterion: str,
    evidence: str,
) -> str:
    return (
        f"Section: {section_id}\n"
        f"Criterion failed: {criterion}\n"
        f"Evidence: {evidence}\n\n"
        f"Section excerpt:\n---\n{section_excerpt}\n---\n\n"
        f"Propose one surgical patch that addresses the criterion."
    )


def _extract_json(text: str) -> dict | None:
    """Try plain json.loads; fall back to finding the first JSON object block."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def propose_patch(
    *,
    section_id: str,
    section_excerpt: str,
    criterion: str,
    evidence: str,
    client: RlmClient,
    model: str,
) -> PatchProposal:
    """Call the LLM to propose a surgical patch for a failed criterion.

    Returns a PatchProposal with status APPLY when the LLM provides a valid
    locator+replacement, or REVIEW when escalating or when the response
    cannot be parsed.
    """
    prompt = _build_user_prompt(section_id, section_excerpt, criterion, evidence)
    response = client.generate(
        model=model,
        messages=[RlmMessage(role="user", content=prompt)],
        system_prompt=_SYSTEM_PROMPT,
    )
    data = _extract_json(response.output_text)

    if data is None or "status" not in data:
        return PatchProposal(
            patch=Patch(section_id=section_id, locator_phrase="", replacement="", occurrence=1),
            criterion=criterion,
            evidence=evidence,
            rationale="Could not parse a patch from the model response (malformed JSON).",
            confidence="low",
            status=PatchStatus.REVIEW,
        )

    status_raw = data.get("status", "review")
    status = PatchStatus.APPLY if status_raw == "apply" else PatchStatus.REVIEW

    locator = data.get("locator_phrase", "") or ""
    replacement = data.get("replacement", "") or ""
    occurrence = int(data.get("occurrence", 1) or 1)

    # Guard: APPLY without a real locator/replacement collapses to REVIEW
    if status == PatchStatus.APPLY and (not locator or not replacement):
        status = PatchStatus.REVIEW

    confidence = data.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    return PatchProposal(
        patch=Patch(
            section_id=section_id,
            locator_phrase=locator,
            replacement=replacement,
            occurrence=occurrence,
        ),
        criterion=criterion,
        evidence=evidence,
        rationale=data.get("rationale", ""),
        confidence=confidence,
        status=status,
    )


_ANNOTATED_SYSTEM_PROMPT = """\
You are a technical editor fixing a specific defect in an engineering Scope of Works.

You are given:
- A section excerpt with the defective span marked by <<<REVIEW>>> ... <<<END_REVIEW>>>
- A criterion the section failed
- Evidence explaining why it failed

Your task: propose a replacement for ONLY the text between <<<REVIEW>>> and <<<END_REVIEW>>>.
Use only facts present elsewhere in the section or commonly implied by the writing guidance.
Do NOT invent facts. If the defect cannot be fixed without additional source information,
respond with status="review" and explain what information is needed.

Respond with ONLY a JSON object of this shape:

{
  "status": "apply" | "review",
  "replacement": "<replacement text to substitute between the markers>",
  "rationale": "<1-2 sentence explanation>",
  "confidence": "high" | "medium" | "low"
}

When status is "review", replacement may be omitted or empty.
Return ONLY the JSON object — no prose, no code fences.
"""


def _build_annotated_user_prompt(
    section_id: str,
    annotated_section: str,
    criterion: str,
    evidence: str,
) -> str:
    return (
        f"Section: {section_id}\n"
        f"Criterion failed: {criterion}\n"
        f"Evidence: {evidence}\n\n"
        "Section excerpt "
        f"(marked span is between <<<REVIEW>>> and <<<END_REVIEW>>>):\n---\n{annotated_section}\n---\n\n"
        f"Propose a replacement for the marked span."
    )


def propose_patch_annotated(
    *,
    section_id: str,
    annotated_section: str,
    span_to_replace: str,
    criterion: str,
    evidence: str,
    client: RlmClient,
    model: str,
) -> PatchProposal:
    """Propose a replacement for a pre-annotated span. LLM returns only the replacement text.

    The span is already marked with <<<REVIEW>>>...<<<END_REVIEW>>> in annotated_section.
    The returned PatchProposal carries span_to_replace in patch.locator_phrase for
    applier compatibility — the loop will convert to AnnotatedPatch on apply.
    """
    prompt = _build_annotated_user_prompt(section_id, annotated_section, criterion, evidence)
    response = client.generate(
        model=model,
        messages=[RlmMessage(role="user", content=prompt)],
        system_prompt=_ANNOTATED_SYSTEM_PROMPT,
    )
    data = _extract_json(response.output_text)

    if data is None or "status" not in data:
        return PatchProposal(
            patch=Patch(
                section_id=section_id,
                locator_phrase=span_to_replace,
                replacement="",
                occurrence=1,
            ),
            criterion=criterion,
            evidence=evidence,
            rationale="Could not parse a replacement from the model response (malformed JSON).",
            confidence="low",
            status=PatchStatus.REVIEW,
        )

    status_raw = data.get("status", "review")
    status = PatchStatus.APPLY if status_raw == "apply" else PatchStatus.REVIEW

    replacement = data.get("replacement", "") or ""
    if status == PatchStatus.APPLY and not replacement:
        status = PatchStatus.REVIEW

    confidence = data.get("confidence", "medium")
    if confidence not in ("high", "medium", "low"):
        confidence = "medium"

    return PatchProposal(
        patch=Patch(
            section_id=section_id,
            locator_phrase=span_to_replace,
            replacement=replacement,
            occurrence=1,
        ),
        criterion=criterion,
        evidence=evidence,
        rationale=data.get("rationale", ""),
        confidence=confidence,
        status=status,
    )
