# ABOUTME: Reusable LLM-as-judge evaluation for rubric dimensions with binary criteria.
# ABOUTME: Builds prompts, calls LLM API, parses responses, computes category-weighted scores.

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from typing import Any

from aec_bench.contracts.rubric import (
    CATEGORY_WEIGHTS,
    DimensionScore,
    RubricCriterion,
    RubricDimension,
)

_log = logging.getLogger(__name__)

_JUDGE_SYSTEM = (
    "You are an expert evaluator for engineering proposals. "
    "Evaluate each criterion as pass or fail based on the provided output and reference materials. "
    "Be objective and specific in your evidence."
)

_API_URL = "https://api.anthropic.com/v1/messages"
_RETRY_BUDGET_SEC = 120
_INITIAL_BACKOFF_SEC = 2
_MAX_BACKOFF_SEC = 30

# Bedrock model name prefixes (shared with providers/behavioral_llm.py)
_BEDROCK_PREFIXES = (
    "anthropic.claude",
    "au.anthropic.",
    "us.anthropic.",
    "eu.anthropic.",
    "ap.anthropic.",
    "amazon.",
    "us.amazon.",
    "meta.llama",
    "us.meta.",
    "mistral.",
    "us.mistral.",
    "cohere.",
    "us.cohere.",
    "ai21.",
    "us.ai21.",
)


def _is_bedrock_model(model: str) -> bool:
    lower = model.lower()
    return any(lower.startswith(p) for p in _BEDROCK_PREFIXES)


def build_judge_prompt(
    *,
    dimension: RubricDimension,
    agent_output: str,
    reference_materials: dict[str, str],
) -> str:
    """Build the evaluation prompt for a single dimension."""
    criteria_lines = []
    for i, c in enumerate(dimension.criteria, 1):
        criteria_lines.append(f"{i}. [{c.category.upper()}] {c.text}")
    criteria_text = "\n".join(criteria_lines)

    ref_sections = []
    for name, content in reference_materials.items():
        ref_sections.append(f"### {name}\n\n{content}")
    ref_text = "\n\n".join(ref_sections) if ref_sections else "(none provided)"

    return f"""## Evaluation Dimension: {dimension.name}

{dimension.description}

## Criteria to Evaluate

For each criterion, determine if it is satisfied (pass) or not (fail).

{criteria_text}

## Reference Materials

{ref_text}

## Agent Output to Evaluate

{agent_output}

## Instructions

Evaluate each criterion against the agent output. For each:
- Compare against the reference materials where relevant
- Return pass (true) if the criterion is clearly satisfied
- Return fail (false) if the criterion is not satisfied or only partially met

Return your evaluation as a JSON code block:

```json
{{
  "criteria_results": [
    {{"criterion": "<criterion text>", "passed": true/false, "evidence": "<explanation>"}}
  ]
}}
```"""


def parse_judge_response(response: str) -> list[dict[str, Any]]:
    """Parse the judge's JSON response into a list of criterion results."""
    # Try code block first
    code_match = re.findall(r"```json\s*\n(.*?)```", response, re.DOTALL)
    json_text = code_match[-1].strip() if code_match else ""

    if not json_text:
        # Try raw JSON
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            json_text = response[start:end]

    if not json_text:
        return []

    try:
        data = json.loads(json_text)
        return data.get("criteria_results", [])
    except (json.JSONDecodeError, AttributeError):
        return []


def _strip_category_prefix(text: str) -> str:
    """Strip '[CATEGORY] ' prefix from criterion text returned by the judge.

    The prompt formats criteria as '[ESSENTIAL] criterion text' but the
    rubric stores just 'criterion text'.
    """
    match = re.match(r"^\[(?:ESSENTIAL|IMPORTANT|OPTIONAL)\]\s*", text, re.IGNORECASE)
    if match:
        return text[match.end() :]
    return text


def compute_criteria_score(
    *,
    criteria: Sequence[RubricCriterion],
    results: Sequence[dict[str, Any]],
    max_score: float,
) -> tuple[float, float, list[str], list[str]]:
    """Compute a dimension score from binary criteria results.

    Returns (score, max_score, satisfied_texts, unsatisfied_texts).
    Missing criteria results are treated as failures.
    """
    result_map = {_strip_category_prefix(r["criterion"]): r for r in results}

    total_weight = 0.0
    earned_weight = 0.0
    satisfied: list[str] = []
    unsatisfied: list[str] = []

    for c in criteria:
        weight = CATEGORY_WEIGHTS.get(c.category, 0.5)
        total_weight += weight

        matched = result_map.get(c.text)
        if matched and matched.get("passed"):
            earned_weight += weight
            satisfied.append(c.text)
        else:
            unsatisfied.append(c.text)

    if total_weight == 0:
        return 0.0, max_score, satisfied, unsatisfied

    score = (earned_weight / total_weight) * max_score
    return round(score, 2), max_score, satisfied, unsatisfied


def _send_judge_request(
    *,
    prompt: str,
    api_key: str,
    model: str,
    system_prompt: str | None = None,
) -> str:
    """Send a judge evaluation request via Bedrock or Anthropic API."""
    system = system_prompt or _JUDGE_SYSTEM
    if _is_bedrock_model(model):
        return _send_bedrock_judge_request(prompt=prompt, model=model, system=system)
    return _send_anthropic_judge_request(prompt=prompt, api_key=api_key, model=model, system=system)


def _send_bedrock_judge_request(*, prompt: str, model: str, system: str) -> str:
    """Send a judge request via the AWS Bedrock Converse API.

    Supports bearer token auth via AWS_BEARER_TOKEN_BEDROCK env var
    (same mechanism used by PydanticAI's BedrockProvider) as well as
    standard boto3 credential chain.
    """
    import boto3
    from botocore.config import Config

    region = os.environ.get("AWS_REGION", "") or os.environ.get("AWS_DEFAULT_REGION", "")
    bearer_token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK", "")

    session_kwargs: dict[str, Any] = {}
    if region:
        session_kwargs["region_name"] = region

    client_kwargs: dict[str, Any] = {}
    if bearer_token:
        # Use bearer token auth (same as PydanticAI BedrockProvider)
        from botocore.session import Session as BotocoreSession
        from botocore.tokens import FrozenAuthToken

        class _BearerSession(BotocoreSession):
            def __init__(self, token: str) -> None:
                super().__init__()
                self._token = token

            def get_auth_token(self, **_kwargs: Any) -> FrozenAuthToken:
                return FrozenAuthToken(self._token)

            def get_credentials(self) -> None:  # type: ignore[override]
                return None

        session = boto3.Session(
            botocore_session=_BearerSession(bearer_token),
            **session_kwargs,
        )
        client_kwargs["config"] = Config(signature_version="bearer")
    else:
        session = boto3.Session(**session_kwargs)

    client = session.client("bedrock-runtime", **client_kwargs)

    deadline = time.time() + _RETRY_BUDGET_SEC
    attempt = 0
    last_error = "retry budget exhausted"

    while time.time() < deadline:
        attempt += 1
        try:
            response = client.converse(
                modelId=model,
                system=[{"text": system}],
                messages=[
                    {
                        "role": "user",
                        "content": [{"text": prompt}],
                    }
                ],
                inferenceConfig={
                    "maxTokens": 4096,
                    "temperature": 0.0,
                },
            )
            output = response.get("output", {})
            message = output.get("message", {})
            content = message.get("content", [])
            parts = [b["text"] for b in content if isinstance(b, dict) and "text" in b]
            return "\n".join(parts)

        except client.exceptions.ThrottlingException:
            _log.debug("Bedrock throttled on attempt %d", attempt)
        except client.exceptions.ModelTimeoutException:
            _log.debug("Bedrock timeout on attempt %d", attempt)
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            error_code = ""
            if hasattr(exc, "response"):
                error_code = getattr(exc.response, "Error", {}).get("Code", "")
            if error_code in ("ValidationException", "AccessDeniedException", "ResourceNotFoundException"):
                raise RuntimeError(last_error) from exc

        time.sleep(min(_INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), _MAX_BACKOFF_SEC))

    raise RuntimeError(f"Bedrock judge failed after {attempt} attempts: {last_error}")


def _send_anthropic_judge_request(*, prompt: str, api_key: str, model: str, system: str) -> str:
    """Send a judge request via the direct Anthropic HTTP API."""
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = json.dumps(
        {
            "model": model,
            "max_tokens": 4096,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()

    deadline = time.time() + _RETRY_BUDGET_SEC
    attempt = 0
    last_error = ""

    while time.time() < deadline:
        attempt += 1
        req = urllib.request.Request(
            _API_URL,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode())
                text_parts = []
                for block in body.get("content", []):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                return "\n".join(text_parts)
        except urllib.error.HTTPError as e:
            code = e.code
            try:
                error_body = e.read().decode()
            except Exception:
                error_body = ""
            last_error = f"HTTP {code}: {error_body[:300]}"
            if code in (400, 401, 403, 404):
                break
            if code == 429:
                ra = e.headers.get("retry-after")
                wait = (
                    min(float(ra), _MAX_BACKOFF_SEC)
                    if ra
                    else min(_INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), _MAX_BACKOFF_SEC)
                )
                time.sleep(wait)
                continue
            if code >= 500:
                time.sleep(min(_INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), _MAX_BACKOFF_SEC))
                continue
            break
        except (urllib.error.URLError, ConnectionResetError, TimeoutError, OSError) as e:
            last_error = f"{type(e).__name__}: {e}"
            time.sleep(min(_INITIAL_BACKOFF_SEC * (2 ** (attempt - 1)), _MAX_BACKOFF_SEC))
            continue

    raise RuntimeError(f"Judge API failed after {attempt} attempts: {last_error}")


def focus_output(
    agent_output: str,
    output_sections: dict[str, str] | None,
    dimension: RubricDimension,
) -> str:
    """Slice agent output to the sections this dimension evaluates."""
    if not dimension.eval_sections or not output_sections:
        return agent_output
    focused = {sid: content for sid in dimension.eval_sections if (content := output_sections.get(sid))}
    if not focused:
        return agent_output
    return "\n\n---\n\n".join(f"## {sid}\n\n{content}" for sid, content in focused.items())


def focus_references(
    reference_materials: dict[str, str],
    dimension: RubricDimension,
) -> dict[str, str]:
    """Slice reference materials to what this dimension needs."""
    if not dimension.eval_references:
        return reference_materials
    focused = {}
    for ref_key in dimension.eval_references:
        for full_key, content in reference_materials.items():
            if ref_key in full_key:
                focused[full_key] = content
    return focused if focused else reference_materials


def judge_dimension(
    *,
    dimension: RubricDimension,
    agent_output: str,
    reference_materials: dict[str, str],
    api_key: str = "",
    model: str = "claude-sonnet-4-20250514",
    output_sections: dict[str, str] | None = None,
) -> DimensionScore:
    """Judge a single dimension using binary criteria evaluation.

    When the dimension specifies eval_sections, only those sections of
    the output are sent to the judge. Similarly for eval_references.
    If expert_persona is set, it replaces the default judge system prompt.
    """
    focused_output = focus_output(agent_output, output_sections, dimension)
    focused_refs = focus_references(reference_materials, dimension)

    prompt = build_judge_prompt(
        dimension=dimension,
        agent_output=focused_output,
        reference_materials=focused_refs,
    )
    system_prompt = dimension.expert_persona or None
    response_text = _send_judge_request(
        prompt=prompt,
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
    )
    results = parse_judge_response(response_text)
    score, max_score, satisfied, unsatisfied = compute_criteria_score(
        criteria=dimension.criteria,
        results=results,
        max_score=dimension.max_score,
    )

    evidence_parts = []
    for r in results:
        status = "PASS" if r.get("passed") else "FAIL"
        evidence_parts.append(f"[{status}] {r.get('criterion', '?')}: {r.get('evidence', '')}")
    evidence = "\n".join(evidence_parts) if evidence_parts else response_text[:500]

    return DimensionScore(
        dimension_id=dimension.id,
        score=score,
        max_score=max_score,
        evidence=evidence,
        eval_method_used="llm_judge",
        satisfied=tuple(satisfied),
        unsatisfied=tuple(unsatisfied),
    )


def judge_dimensions(
    *,
    dimensions: Sequence[RubricDimension],
    agent_output: str,
    reference_materials: dict[str, str],
    api_key: str = "",
    model: str = "claude-sonnet-4-20250514",
    output_sections: dict[str, str] | None = None,
) -> list[DimensionScore]:
    """Judge multiple dimensions sequentially."""
    return [
        judge_dimension(
            dimension=dim,
            agent_output=agent_output,
            reference_materials=reference_materials,
            api_key=api_key,
            model=model,
            output_sections=output_sections,
        )
        for dim in dimensions
    ]
