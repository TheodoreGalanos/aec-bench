# ABOUTME: Presence-only structure validator for lambda-rlm generated sections.
# ABOUTME: One Haiku call per section asserts each required field is detectable.

"""Structure validator for the lambda-rlm structure-enforcement loop.

Asserts presence of every `required=True` field declared on a section's
schema. Quality, tone, and sufficiency are out of scope — those live in
the rubric judge. Variance on "is X present" is far lower than variance
on "is this section well-written".
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage
from aec_bench.contracts.repl import OutputField

_JSON_BLOCK_RE = re.compile(r"```json\s*\n(.*?)```", re.DOTALL)


@dataclass(frozen=True)
class FieldGap:
    """One required field that was either missing or malformed in section content."""

    field_name: str
    dtype: str
    kind: Literal["missing", "malformed"]
    locator: str  # free-text hint for the retry prompt ("no mention of revision")


@dataclass(frozen=True)
class StructureValidationResult:
    """Outcome of a structure validation pass over one section."""

    section_id: str
    passed: bool
    missing: tuple[FieldGap, ...]
    malformed: tuple[FieldGap, ...]
    validator_input_tokens: int
    validator_output_tokens: int


def _build_validator_prompt(
    *,
    section_title: str,
    content: str,
    required_fields: Sequence[OutputField],
) -> str:
    """Build the presence-only validator prompt.

    The prompt asks for a per-field verdict from {present, missing,
    malformed}. Quality, tone, and sufficiency are explicitly out of
    scope — the prompt accepts paraphrased and structured forms.
    Non-required fields are filtered out before listing.
    """
    enforced = [f for f in required_fields if f.required]
    field_lines = "\n".join(f"- {f.name} [{f.dtype}] — {f.description}" for f in enforced)
    return f"""You are a structure validator. Your only job is to check whether each
required field is detectable in the section content below. Do NOT judge
quality, tone, sufficiency, or accuracy — only presence.

Section: {section_title}

Required fields:
{field_lines}

Section content:
\"\"\"
{content}
\"\"\"

For each required field, return one of:
- "present" — the field is clearly populated (paraphrased or structured forms count)
- "missing" — no recognisable value for this field anywhere in the content
- "malformed" — a value exists but in an unrecognisable format for the declared dtype

Respond with ONLY a JSON object inside a ```json code block:

```json
{{
  "fields": [
    {{"name": "<field_name>", "verdict": "present" | "missing" | "malformed",
     "locator": "<short hint>"}}
  ]
}}
```

`locator` is a brief free-text hint (≤80 chars) for missing/malformed
verdicts, e.g. "no revision letter on any row" or "found prose where a
list was expected". Use empty string for `present`."""


def _parse_validator_response(
    response_text: str,
    required_fields: Sequence[OutputField],
) -> tuple[tuple[FieldGap, ...], tuple[FieldGap, ...]] | None:
    """Parse validator JSON into (missing, malformed) tuples.

    Returns None when the response can't be parsed; the caller treats
    that as a fail-safe (all required fields go to `missing`)."""
    code_match = _JSON_BLOCK_RE.findall(response_text)
    if code_match:
        json_text = code_match[-1].strip()
    else:
        start = response_text.find("{")
        end = response_text.rfind("}") + 1
        if start < 0 or end <= start:
            return None
        json_text = response_text[start:end]

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError:
        return None

    verdicts = {item.get("name"): item for item in data.get("fields", []) if isinstance(item, dict)}
    missing: list[FieldGap] = []
    malformed: list[FieldGap] = []
    for f in required_fields:
        if not f.required:
            continue
        verdict_data = verdicts.get(f.name)
        if verdict_data is None:
            missing.append(
                FieldGap(
                    field_name=f.name,
                    dtype=f.dtype,
                    kind="missing",
                    locator="no verdict returned",
                )
            )
            continue
        verdict = verdict_data.get("verdict", "missing")
        locator = str(verdict_data.get("locator", ""))[:200]
        if verdict == "present":
            continue
        if verdict == "malformed":
            malformed.append(
                FieldGap(
                    field_name=f.name,
                    dtype=f.dtype,
                    kind="malformed",
                    locator=locator,
                )
            )
        else:
            missing.append(
                FieldGap(
                    field_name=f.name,
                    dtype=f.dtype,
                    kind="missing",
                    locator=locator,
                )
            )
    return tuple(missing), tuple(malformed)


def validate_section_structure(
    *,
    section_id: str,
    section_title: str,
    content: str,
    required_fields: Sequence[OutputField],
    client: RlmClient,
    model: str,
) -> StructureValidationResult:
    """Run a presence-only check over a section's required fields.

    Empty/all-non-required input short-circuits with `passed=True` and
    no LLM call. Otherwise calls the validator model once with structured
    JSON output and parses the per-field verdict.
    """
    enforced = tuple(f for f in required_fields if f.required)
    if not enforced:
        return StructureValidationResult(
            section_id=section_id,
            passed=True,
            missing=(),
            malformed=(),
            validator_input_tokens=0,
            validator_output_tokens=0,
        )

    prompt = _build_validator_prompt(
        section_title=section_title,
        content=content,
        required_fields=enforced,
    )
    response = client.generate(
        model=model,
        messages=[RlmMessage(role="user", content=prompt)],
        system_prompt=None,
    )
    parsed = _parse_validator_response(response.output_text, enforced)
    if parsed is None:
        # Fail safe: every required field treated as missing so the retry
        # loop fires. Locator records the parse failure for diagnostics.
        missing: tuple[FieldGap, ...] = tuple(
            FieldGap(
                field_name=f.name,
                dtype=f.dtype,
                kind="missing",
                locator="validator response unparsable",
            )
            for f in enforced
        )
        malformed: tuple[FieldGap, ...] = ()
    else:
        missing, malformed = parsed

    return StructureValidationResult(
        section_id=section_id,
        passed=not (missing or malformed),
        missing=missing,
        malformed=malformed,
        validator_input_tokens=response.input_tokens,
        validator_output_tokens=response.output_tokens,
    )
