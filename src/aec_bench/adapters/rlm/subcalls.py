# ABOUTME: Typed sub-call framework for the RLM adapter.
# ABOUTME: Sub-call implementations: extract, calculate, retrieve, verify, summarise, reason.

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from aec_bench.adapters.rlm.client import RlmClient, RlmMessage


@dataclass(frozen=True)
class ExtractResult:
    """Result of an extract() sub-call."""

    values: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Check .error is None instead — no .success attribute exists",
            "data": "Use .values to access extracted data",
            "result": "Use .values to access extracted results",
            "output": "Use .values to access the output dict",
            "text": "Use .values to access extracted fields",
        }
        hint = hints.get(name, "Available: values, error, input_tokens, output_tokens")
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


@dataclass(frozen=True)
class CalculateResult:
    """Result of a calculate() sub-call."""

    values: dict[str, Any]
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Check .error is None instead — no .success attribute exists",
            "data": "Use .values to access computed data",
            "result": "Use .values to access computed results",
            "output": "Use .values to access the output dict",
            "text": "Use .values to access computed fields",
        }
        hint = hints.get(name, "Available: values, error, input_tokens, output_tokens")
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


@dataclass(frozen=True)
class RetrieveResult:
    """Result of a retrieve() sub-call."""

    results: list[dict[str, str]]
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Check .error is None instead — no .success attribute exists",
            "data": "Use .results to access retrieved items (list of dicts)",
            "values": "Use .results for RetrieveResult — it holds a list of dicts, not a dict",
            "output": "Use .results to access retrieved items",
            "text": "Use .results to access retrieved items",
        }
        hint = hints.get(name, "Available: results, error, input_tokens, output_tokens")
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


@dataclass(frozen=True)
class VerificationResult:
    """Result of a verify() sub-call."""

    passed: bool | None = None
    confidence: float = 0.0
    explanation: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Use .passed (bool) to check if verification passed — not .success",
            "data": "Use .passed, .confidence, .explanation to access verification results",
            "result": "Use .passed (bool) and .explanation (str)",
            "values": "Use .passed, .confidence, .explanation for verification results",
            "output": "Use .passed, .confidence, .explanation",
        }
        hint = hints.get(
            name,
            "Available: passed, confidence, explanation, error, input_tokens, output_tokens",
        )
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


@dataclass(frozen=True)
class SummariseResult:
    """Result of a summarise() sub-call."""

    summary: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Check .error is None instead — no .success attribute exists",
            "data": "Use .summary to access the summarised text",
            "values": "Use .summary for SummariseResult — it holds a string, not a dict",
            "text": "Use .summary to access the summarised text",
            "output": "Use .summary to access the summarised text",
        }
        hint = hints.get(name, "Available: summary, error, input_tokens, output_tokens")
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


@dataclass(frozen=True)
class ReasoningResult:
    """Result of a reason() sub-call."""

    conclusion: str = ""
    confidence: float = 0.0
    rationale: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Check .error is None instead — no .success attribute exists",
            "data": "Use .conclusion, .confidence, .rationale to access reasoning results",
            "result": "Use .conclusion (str) for the reasoned answer",
            "values": "Use .conclusion, .confidence, .rationale for reasoning results",
            "output": "Use .conclusion (str) for the reasoned answer",
            "text": "Use .conclusion (str) or .rationale (str)",
            "explanation": "Use .rationale (str) for the reasoning explanation",
        }
        hint = hints.get(
            name,
            "Available: conclusion, confidence, rationale, error, input_tokens, output_tokens",
        )
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


@dataclass(frozen=True)
class SectionReviewResult:
    """Result of a review() sub-call checking a filled section for quality."""

    status: str = "pass"
    gaps: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None

    def __getattr__(self, name: str) -> Any:
        hints: dict[str, str] = {
            "success": "Check .status == 'pass' or .error is None",
            "data": "Use .gaps, .risks, .status to access review findings",
            "values": "Use .gaps (list), .risks (list), .status (str)",
            "passed": "Use .status == 'pass' to check if review passed",
        }
        hint = hints.get(name, "Available: status, gaps, risks, error, input_tokens, output_tokens")
        raise AttributeError(f"'{type(self).__name__}' has no '{name}'. {hint}")


def _parse_json_from_response(text: str) -> dict[str, Any] | list | None:
    """Extract a JSON value (dict or list) from a fenced code block or raw text."""
    pattern = r"```(?:json)?\s*\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    if matches:
        try:
            return json.loads(matches[-1])
        except json.JSONDecodeError:
            return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    return None


def default_extract(
    *,
    text: str,
    fields: list[str] | None = None,
    client: RlmClient,
    model: str,
    context: str | None = None,
    section_context: dict[str, Any] | None = None,
) -> ExtractResult:
    """Default extract sub-call: asks a sub-LLM to extract structured fields from text.

    When *section_context* is provided (from ``ReportTemplate.get_extraction_context``),
    uses a goal-directed prompt that includes writing guidance, generation mode,
    and dependency context — matching lambda-RLM's extraction quality.

    Uses structured output (tool_use) for clean identifier fields when
    supported; falls back to text + JSON parsing otherwise.
    """
    # Goal-directed extraction when section context is available
    if section_context is not None:
        return _extract_goal_directed(
            text=text,
            fields=fields,
            client=client,
            model=model,
            section_context=section_context,
        )

    # Use structured output only when all fields are clean identifiers.
    if hasattr(client, "generate_with_tools") and all(re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", f) for f in fields):
        return _extract_structured(
            text=text,
            fields=fields,
            client=client,
            model=model,
            context=context,
        )

    return _extract_text(
        text=text,
        fields=fields,
        client=client,
        model=model,
        context=context,
    )


def _extract_goal_directed(
    *,
    text: str,
    fields: list[str] | None,
    client: RlmClient,
    model: str,
    section_context: dict[str, Any],
) -> ExtractResult:
    """Goal-directed extraction using section context from the template.

    Builds a prompt matching lambda-RLM's extraction: includes section title,
    writing guidance, generation mode, and dependency context so the LLM
    extracts what the section actually needs.

    When *fields* is provided, they serve as additional hints. When omitted,
    the LLM decides what to extract based on writing guidance alone.
    """
    section_title = section_context.get("section_title", "")
    generation_mode = section_context.get("generation_mode", "transform")
    writing_guidance = section_context.get("writing_guidance", [])
    dependency_context = section_context.get("dependency_context", {})

    guidance_lines = "\n".join(f"- {rule}" for rule in writing_guidance)

    parts = [
        "You are extracting information from a document section.",
        "",
        f"Target section: {section_title}",
        f"Generation mode: {generation_mode}",
        "",
        "Writing guidance:",
        guidance_lines,
    ]

    if dependency_context:
        parts.append("")
        parts.append("Previously written sections for context:")
        for sec_id, content in dependency_context.items():
            parts.append(f"### {sec_id}")
            parts.append(str(content)[:500])

    if fields:
        field_list = ", ".join(fields)
        parts.append("")
        parts.append(f"Also extract these specific fields: {field_list}")

    parts.extend(
        [
            "",
            "---",
            text,
            "---",
            "",
            "Return a JSON object with keys you consider relevant for writing this section.",
            ("Each key should be a descriptive snake_case name. Each value should be the extracted fact or text."),
            ("Extract specific values (names, numbers, dates, abbreviations) rather than vague summaries."),
            (
                "IMPORTANT: Extract only what is explicitly stated in the source text. "
                "Do not expand acronyms unless the source text provides the expansion. "
                "Do not infer or fabricate values that are not present in the text."
            ),
        ]
    )

    prompt = "\n".join(parts)

    messages = [RlmMessage(role="user", content=prompt)]
    response = client.generate(
        model=model,
        messages=messages,
        system_prompt=None,
    )

    parsed = _parse_json_from_response(response.output_text)
    if parsed is None or not isinstance(parsed, dict):
        return ExtractResult(
            values={},
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse JSON from response: {response.output_text[:200]}",
        )

    return ExtractResult(
        values=parsed,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


def _extract_structured(
    *,
    text: str,
    fields: list[str],
    client: Any,
    model: str,
    context: str | None = None,
) -> ExtractResult:
    """Extract using structured output via generate_with_tools."""
    field_list = ", ".join(fields)
    context_line = f"\nContext: {context}" if context else ""

    messages = [
        RlmMessage(
            role="user",
            content=(
                "Extract the following fields from the text below.\n"
                f"Fields to extract: {field_list}{context_line}\n\n"
                f"Text:\n{text}"
            ),
        )
    ]

    # Build a dynamic schema with each field as a property.
    # Only called when all fields are clean identifiers (validated by caller).
    properties = {f: {"type": "string", "description": f"Extracted value for '{f}'"} for f in fields}
    tool_schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }

    response = client.generate_with_tools(
        model=model,
        messages=messages,
        system_prompt="You are a precise data extraction assistant.",
        tool_name="extraction_result",
        tool_description="Return the extracted data as structured fields.",
        tool_parameters_schema=tool_schema,
    )

    # Parse from tool call
    if response.tool_call is not None:
        try:
            parsed = json.loads(response.tool_call.code)
            if isinstance(parsed, dict):
                return ExtractResult(
                    values=parsed,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                )
        except (json.JSONDecodeError, TypeError):
            pass
        return ExtractResult(
            values={},
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse tool call: {response.tool_call.code[:200]}",
        )

    # Model responded with text instead of tool call — try parsing
    parsed = _parse_json_from_response(response.output_text)
    if parsed is not None and isinstance(parsed, dict):
        return ExtractResult(
            values=parsed,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )

    return ExtractResult(
        values={},
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        error=f"No tool call and no parseable JSON: {response.output_text[:200]}",
    )


def _extract_text(
    *,
    text: str,
    fields: list[str],
    client: RlmClient,
    model: str,
    context: str | None = None,
) -> ExtractResult:
    """Extract using text generation + JSON parsing (fallback path)."""
    field_list = ", ".join(fields)
    context_line = f"\nContext: {context}" if context else ""

    messages = [
        RlmMessage(
            role="user",
            content=(
                "Extract the following fields from the text below"
                " and return them as a JSON object.\n"
                f"Fields to extract: {field_list}{context_line}\n\n"
                f"Text:\n{text}\n\n"
                f"Return ONLY a JSON code block with the extracted values."
            ),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a precise data extraction assistant. Return only JSON.",
    )

    parsed = _parse_json_from_response(response.output_text)
    if parsed is None or not isinstance(parsed, dict):
        return ExtractResult(
            values={},
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse JSON from response: {response.output_text[:200]}",
        )

    return ExtractResult(
        values=parsed,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


def default_calculate(
    *,
    expression: str,
    parameters: dict[str, Any],
    client: RlmClient,
    model: str,
    tool: str | None = None,
) -> CalculateResult:
    """Default calculate sub-call: asks a sub-LLM to perform a calculation."""
    param_text = "\n".join(f"  {k} = {v}" for k, v in parameters.items())
    tool_line = f"\nTool available: {tool}" if tool else ""

    messages = [
        RlmMessage(
            role="user",
            content=(
                f"Perform the following calculation and return results as JSON.\n"
                f"Calculation: {expression}\n"
                f"Parameters:\n{param_text}{tool_line}\n\n"
                "Return ONLY a JSON code block with the computed values."
            ),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a precise engineering calculator. Return only JSON.",
    )
    parsed = _parse_json_from_response(response.output_text)
    if parsed is None or not isinstance(parsed, dict):
        return CalculateResult(
            values={},
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse: {response.output_text[:200]}",
        )
    return CalculateResult(
        values=parsed,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


def default_retrieve(
    *,
    query: str,
    client: RlmClient,
    model: str,
    source: str | None = None,
    max_results: int = 5,
) -> RetrieveResult:
    """Default retrieve sub-call: searches for relevant information."""
    source_line = f"\nSearch in: {source}" if source else ""

    messages = [
        RlmMessage(
            role="user",
            content=(
                "Search for relevant information and return results "
                "as a JSON array of objects with 'text', 'source', "
                "and 'relevance' keys.\n"
                f"Query: {query}{source_line}\n"
                f"Max results: {max_results}\n\n"
                "Return ONLY a JSON code block."
            ),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a precise information retrieval assistant.",
    )
    parsed = _parse_json_from_response(response.output_text)
    if isinstance(parsed, list):
        return RetrieveResult(
            results=parsed,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
        )
    return RetrieveResult(
        results=[],
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        error=f"Failed to parse array: {response.output_text[:200]}",
    )


def default_verify(
    *,
    value: Any,
    criterion: str,
    client: RlmClient,
    model: str,
    standard: str | None = None,
) -> VerificationResult:
    """Default verify sub-call: checks a value against a criterion."""
    standard_line = f"\nReference standard: {standard}" if standard else ""

    messages = [
        RlmMessage(
            role="user",
            content=(
                "Verify whether the value satisfies the criterion. "
                "Return JSON with 'passed' (bool), 'confidence' "
                "(0-1), and 'explanation'.\n"
                f"Value: {value}\n"
                f"Criterion: {criterion}{standard_line}\n\n"
                "Return ONLY a JSON code block."
            ),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a precise verification assistant.",
    )
    parsed = _parse_json_from_response(response.output_text)
    if parsed is None or not isinstance(parsed, dict):
        return VerificationResult(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse: {response.output_text[:200]}",
        )
    return VerificationResult(
        passed=parsed.get("passed"),
        confidence=float(parsed.get("confidence", 0)),
        explanation=parsed.get("explanation", ""),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


def default_summarise(
    *,
    content: str | list[str],
    client: RlmClient,
    model: str,
    focus: str | None = None,
    max_length: int = 500,
) -> SummariseResult:
    """Default summarise sub-call: condenses content into a focused summary."""
    if isinstance(content, list):
        content = "\n\n".join(content)
    focus_line = f"\nFocus on: {focus}" if focus else ""

    messages = [
        RlmMessage(
            role="user",
            content=(f"Summarise the following in {max_length} characters or fewer.{focus_line}\n\n{content}"),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a precise summarisation assistant.",
    )
    return SummariseResult(
        summary=response.output_text.strip(),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


def default_reason(
    *,
    question: str,
    client: RlmClient,
    model: str,
    context: str | None = None,
    options: list[str] | None = None,
) -> ReasoningResult:
    """Default reason sub-call: domain judgment with explanation."""
    context_line = f"\nContext: {context}" if context else ""
    options_line = ""
    if options:
        options_line = "\nOptions: " + ", ".join(options)

    messages = [
        RlmMessage(
            role="user",
            content=(
                "Answer the following question with a JSON object "
                "containing 'conclusion', 'confidence' (0-1), "
                "and 'rationale'.\n"
                f"Question: {question}{context_line}{options_line}\n\n"
                "Return ONLY a JSON code block."
            ),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a domain reasoning expert.",
    )
    parsed = _parse_json_from_response(response.output_text)
    if parsed is None or not isinstance(parsed, dict):
        return ReasoningResult(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse: {response.output_text[:200]}",
        )
    return ReasoningResult(
        conclusion=parsed.get("conclusion", ""),
        confidence=float(parsed.get("confidence", 0)),
        rationale=parsed.get("rationale", ""),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )


def default_review(
    *,
    section_content: str,
    writing_guidance: list[str],
    extracted_data: dict[str, Any] | None = None,
    client: RlmClient,
    model: str,
) -> SectionReviewResult:
    """Review a filled section for gaps and risks against writing guidance.

    Checks whether the section content satisfies the writing guidance rules
    and flags any gaps (missing requirements) or risks (potential issues).
    """
    guidance_lines = "\n".join(f"- {rule}" for rule in writing_guidance)
    data_section = ""
    if extracted_data:
        data_section = (
            "\n\nExtracted source data (what was available):\n"
            + json.dumps(extracted_data, indent=2, default=str)[:3000]
        )

    messages = [
        RlmMessage(
            role="user",
            content=(
                "Review the following section content against the writing guidance rules.\n\n"
                f"Writing guidance rules:\n{guidance_lines}\n\n"
                f"Section content:\n{section_content}\n"
                f"{data_section}\n\n"
                "Check each writing rule and classify as COVERED, GAP, or RISK.\n"
                "Return a JSON object:\n"
                '{\n  "status": "pass" or "needs_work",\n'
                '  "gaps": ["list of unmet writing guidance rules"],\n'
                '  "risks": ["list of potential issues or inaccuracies"]\n'
                "}"
            ),
        )
    ]

    response = client.generate(
        model=model,
        messages=messages,
        system_prompt="You are a technical document quality reviewer. Return only JSON.",
    )

    parsed = _parse_json_from_response(response.output_text)
    if parsed is None or not isinstance(parsed, dict):
        return SectionReviewResult(
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            error=f"Failed to parse review: {response.output_text[:200]}",
        )

    return SectionReviewResult(
        status=parsed.get("status", "pass"),
        gaps=parsed.get("gaps", []),
        risks=parsed.get("risks", []),
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
    )
