# ABOUTME: Shared advisor call utility for all adapters.
# ABOUTME: Calls advisor model with structured output, handles errors, tracks tokens.

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.advisor import AdvisorRequest, AdvisorResponse

_ADVISOR_SYSTEM_PROMPT = """\
You are advising an AI agent working on AEC (Architecture, Engineering, Construction) tasks.

Give concise strategic guidance. Do not write the actual deliverable content. \
Keep responses under {max_tokens} tokens.

{adapter_context}

Respond with a JSON object containing exactly these fields:
- "advice": your core strategic guidance (string)
- "suggested_action": a concrete next step the agent should take (string)
- "confidence": how sure you are this advice is correct, 0.0 to 1.0 (number)
- "reasoning": brief explanation of why you suggest this (string)

Return ONLY the JSON object, no other text.
"""

_FALLBACK_RESPONSE = AdvisorResponse(
    advice="Advisor unavailable — proceed on your own judgement",
    suggested_action="continue",
    confidence=0.0,
    reasoning="advisor call failed",
)


@dataclass(frozen=True)
class AdvisorResult:
    """Result of an advisor call, following the subcall result pattern."""

    response: AdvisorResponse | None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "advice": "Use .response.advice to access the advisor's guidance",
            "suggested_action": "Use .response.suggested_action",
            "confidence": "Use .response.confidence",
            "reasoning": "Use .response.reasoning",
            "success": "Check .error is None instead — no .success attribute exists",
        }
        hint = hints.get(name, "Available: response, error, input_tokens, output_tokens")
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


def _parse_json_from_response(text: str) -> dict[str, Any] | None:
    """Extract a JSON object from a fenced code block or raw text."""
    pattern = r"```(?:json)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        try:
            parsed = json.loads(matches[-1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    return None


def default_advise(
    *,
    request: AdvisorRequest,
    context_messages: list[dict[str, str]],
    client: RlmClient,
    model: str,
    max_response_tokens: int = 500,
    adapter_context: str = "",
) -> AdvisorResult:
    """Call the advisor model and return a structured AdvisorResult.

    Follows the same pattern as default_extract, default_verify, etc.
    On client error or unparseable response, returns a safe fallback
    that tells the executor to continue on its own.
    """
    system = _ADVISOR_SYSTEM_PROMPT.format(
        max_tokens=max_response_tokens,
        adapter_context=adapter_context,
    )

    user_parts: list[str] = []
    for msg in context_messages:
        user_parts.append(f"[Context] {msg.get('content', '')}")

    if request.goal:
        user_parts.append(f"\n[Goal] {request.goal}")
    if request.problem:
        user_parts.append(f"[Problem] {request.problem}")
    if request.attempt:
        user_parts.append(f"[Attempted] {request.attempt}")

    messages = [RlmMessage(role="user", content="\n".join(user_parts))]

    response = client.generate(model=model, messages=messages, system_prompt=system)

    if response.error_message:
        return AdvisorResult(
            response=_FALLBACK_RESPONSE,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=response.error_message,
        )

    parsed = _parse_json_from_response(response.output_text)
    if parsed is not None:
        advisor_response = AdvisorResponse(
            advice=parsed.get("advice", response.output_text),
            suggested_action=parsed.get("suggested_action", "continue"),
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=parsed.get("reasoning", ""),
        )
    else:
        advisor_response = AdvisorResponse(
            advice=response.output_text,
            suggested_action="continue",
            confidence=0.0,
            reasoning="",
        )

    return AdvisorResult(
        response=advisor_response,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
