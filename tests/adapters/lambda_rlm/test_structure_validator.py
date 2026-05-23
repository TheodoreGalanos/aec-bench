# ABOUTME: Tests for the lambda-rlm structure validator (presence-only Haiku check).
# ABOUTME: Subsequent tasks (4-6) wire short-circuit, prompt builder, end-to-end LLM call.

"""Tests for structure validation data model and validator function."""

from __future__ import annotations

from aec_bench.adapters.lambda_rlm.structure_validator import (
    FieldGap,
    StructureValidationResult,
    _build_validator_prompt,
    validate_section_structure,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient
from aec_bench.contracts.repl import OutputField


def test_field_gap_is_frozen_dataclass() -> None:
    gap = FieldGap(field_name="revision", dtype="str", kind="missing", locator="not found")
    assert gap.field_name == "revision"
    assert gap.kind == "missing"


def test_structure_validation_result_passed_when_no_gaps() -> None:
    result = StructureValidationResult(
        section_id="drawing_register",
        passed=True,
        missing=(),
        malformed=(),
        validator_input_tokens=0,
        validator_output_tokens=0,
    )
    assert result.passed is True
    assert result.missing == ()


def test_validator_empty_required_list_short_circuits_without_llm_call() -> None:
    """No required fields → passed=True, no client invocation."""

    client = ReplayRlmClient(responses=[])  # would index-error if called
    result = validate_section_structure(
        section_id="drawing_register",
        section_title="Drawing Register",
        content="anything",
        required_fields=(),
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is True
    assert result.missing == ()
    assert result.malformed == ()
    assert result.validator_input_tokens == 0
    assert result.validator_output_tokens == 0


def test_validator_only_non_required_fields_short_circuits() -> None:
    """A field declared but with required=False is ignored."""
    from aec_bench.contracts.repl import OutputField

    client = ReplayRlmClient(responses=[])
    fields = (OutputField(name="discipline", dtype="str", description="", required=False),)
    result = validate_section_structure(
        section_id="reports_register",
        section_title="Reports Register",
        content="x",
        required_fields=fields,
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is True
    assert result.missing == ()
    assert result.malformed == ()
    assert result.validator_input_tokens == 0
    assert result.validator_output_tokens == 0


def test_build_validator_prompt_lists_each_required_field() -> None:
    """Prompt lists each required field by name, dtype, and description."""

    fields = (
        OutputField(name="number", dtype="str", description="drawing ref", required=True),
        OutputField(name="title", dtype="str", description="ALL CAPS", required=True),
        OutputField(name="discipline", dtype="str", description="", required=False),  # ignored
    )
    prompt = _build_validator_prompt(
        section_title="Drawing Register",
        content="| 11221-AUR-001 | COVER SHEET | A |",
        required_fields=fields,
    )
    # Section title surfaced
    assert "Drawing Register" in prompt
    # Required fields surfaced with name + description
    assert "number" in prompt and "drawing ref" in prompt
    assert "title" in prompt and "ALL CAPS" in prompt
    # Non-required field "discipline" must NOT appear in the field list
    # (it may legitimately appear in the description text of another field
    # or in the prompt boilerplate, so we make a tighter assertion: the
    # canonical "name [dtype]" listing is not present for discipline.)
    assert "discipline [str]" not in prompt
    # Section content embedded
    assert "11221-AUR-001" in prompt
    # Asks for structured output mentioning the three verdict states
    lower = prompt.lower()
    assert "present" in lower
    assert "missing" in lower
    assert "malformed" in lower


def _make_client(response_text: str, *, in_tokens: int = 200, out_tokens: int = 50) -> ReplayRlmClient:
    from aec_bench.adapters.rlm.client import RlmCompletionResponse

    return ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=response_text,
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
        ]
    )


_REQUIRED_THREE = (
    OutputField(name="number", dtype="str", description="ref", required=True),
    OutputField(name="title", dtype="str", description="title", required=True),
    OutputField(name="revision", dtype="str", description="rev", required=True),
)


def test_validator_passes_when_all_present() -> None:
    raw = """```json
{"fields": [
  {"name": "number", "verdict": "present", "locator": ""},
  {"name": "title", "verdict": "present", "locator": ""},
  {"name": "revision", "verdict": "present", "locator": ""}
]}
```"""
    client = _make_client(raw)
    result = validate_section_structure(
        section_id="drawing_register",
        section_title="Drawing Register",
        content="| 11221-AUR-001 | COVER SHEET | A |",
        required_fields=_REQUIRED_THREE,
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is True
    assert result.missing == ()
    assert result.malformed == ()
    assert result.validator_input_tokens == 200
    assert result.validator_output_tokens == 50


def test_validator_flags_missing_field() -> None:
    raw = """```json
{"fields": [
  {"name": "number", "verdict": "present", "locator": ""},
  {"name": "title", "verdict": "present", "locator": ""},
  {"name": "revision", "verdict": "missing", "locator": "no revision letter on any row"}
]}
```"""
    client = _make_client(raw)
    result = validate_section_structure(
        section_id="drawing_register",
        section_title="Drawing Register",
        content="...",
        required_fields=_REQUIRED_THREE,
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is False
    assert len(result.missing) == 1
    assert result.missing[0].field_name == "revision"
    assert result.missing[0].kind == "missing"
    assert "no revision letter" in result.missing[0].locator
    assert result.malformed == ()


def test_validator_flags_malformed_field() -> None:
    raw = """```json
{"fields": [
  {"name": "number", "verdict": "present", "locator": ""},
  {"name": "title", "verdict": "present", "locator": ""},
  {"name": "revision", "verdict": "malformed", "locator": "free prose, no letter"}
]}
```"""
    client = _make_client(raw)
    result = validate_section_structure(
        section_id="drawing_register",
        section_title="Drawing Register",
        content="...",
        required_fields=_REQUIRED_THREE,
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is False
    assert result.missing == ()
    assert len(result.malformed) == 1
    assert result.malformed[0].field_name == "revision"
    assert result.malformed[0].kind == "malformed"


def test_validator_parses_bare_json_without_fences() -> None:
    """When the validator response omits the fenced code block, the parser
    falls back to extracting the outermost {...} substring. Validates the
    fallback path in _parse_validator_response."""
    raw = """The validator found:
{"fields": [
  {"name": "number", "verdict": "present", "locator": ""},
  {"name": "title", "verdict": "present", "locator": ""},
  {"name": "revision", "verdict": "present", "locator": ""}
]}
Analysis complete."""
    client = _make_client(raw)
    result = validate_section_structure(
        section_id="drawing_register",
        section_title="Drawing Register",
        content="...",
        required_fields=_REQUIRED_THREE,
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is True
    assert result.missing == ()
    assert result.malformed == ()


def test_validator_treats_unparsable_response_as_all_missing() -> None:
    """If the validator response can't be parsed, fail safe: mark every
    required field missing so the retry loop fires rather than silently
    pass."""
    client = _make_client("not JSON")
    result = validate_section_structure(
        section_id="drawing_register",
        section_title="Drawing Register",
        content="...",
        required_fields=_REQUIRED_THREE,
        client=client,
        model="au.anthropic.claude-haiku-4-5",
    )
    assert result.passed is False
    assert len(result.missing) == 3
