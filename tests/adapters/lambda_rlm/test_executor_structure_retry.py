# ABOUTME: Integration tests for the lambda-rlm structure-enforcement retry loop.
# ABOUTME: Uses ReplayRlmClient to script generate + validate sequences end-to-end.

"""Tests for _generate_section + structure-validation retry loop."""

from __future__ import annotations

from aec_bench.adapters.lambda_rlm.config import (
    LambdaRlmConfig,
    StructureEnforcementConfig,
)
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.state import PlanState
from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmCompletionResponse,
    RlmMessage,
)
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.template_parser import parse_report_template

_REGISTER_TOML = """
[[sections]]
id = "drawing_register"
title = "Drawing Register"
generation_mode = "transform"

[sections.fields]
number   = { dtype = "str", description = "ref", required = true }
revision = { dtype = "str", description = "rev", required = true }
"""


def _make_template() -> ReportTemplate:
    schema = parse_report_template(_REGISTER_TOML)
    return ReportTemplate(schema=schema)


def _resp(text: str, *, in_tokens: int = 100, out_tokens: int = 50) -> RlmCompletionResponse:
    return RlmCompletionResponse(
        output_text=text,
        input_tokens=in_tokens,
        output_tokens=out_tokens,
    )


_VALIDATOR_PASS = """```json
{"fields":[
  {"name":"number","verdict":"present","locator":""},
  {"name":"revision","verdict":"present","locator":""}
]}
```"""

_VALIDATOR_MISS_REVISION = """```json
{"fields":[
  {"name":"number","verdict":"present","locator":""},
  {"name":"revision","verdict":"missing","locator":"no rev letter"}
]}
```"""


def _make_executor(client: ReplayRlmClient, *, enabled: bool, max_retries: int = 2) -> PlanExecutor:
    cfg = LambdaRlmConfig(
        structure_enforcement=StructureEnforcementConfig(
            enabled=enabled,
            max_retries=max_retries,
        ),
    )
    return PlanExecutor(
        client=client,
        model="sonnet",
        template=_make_template(),
        source_docs={},
        config=cfg,
    )


def test_retry_disabled_by_default_uses_single_generate_call() -> None:
    """With enabled=False, no validator call and no retry."""
    client = ReplayRlmClient(responses=[_resp("section content goes here")])
    ex = _make_executor(client, enabled=False)
    state = PlanState()
    ex._generate_section("drawing_register", state)
    assert "drawing_register" in state.sections
    assert state.structure_retries.get("drawing_register", 0) == 0
    assert state.llm_calls == 1


def test_no_required_fields_skips_enforcement_when_enabled() -> None:
    """A section with no required=True fields runs through with one
    generate call even when enforcement is enabled."""
    toml = """
[[sections]]
id = "loose_section"
title = "Loose"
generation_mode = "transform"

[sections.fields]
notes = { dtype = "str", description = "", required = false }
"""
    schema = parse_report_template(toml)
    template = ReportTemplate(schema=schema)
    client = ReplayRlmClient(responses=[_resp("free prose")])
    cfg = LambdaRlmConfig(
        structure_enforcement=StructureEnforcementConfig(enabled=True),
    )
    ex = PlanExecutor(
        client=client,
        model="sonnet",
        template=template,
        source_docs={},
        config=cfg,
    )
    state = PlanState()
    ex._generate_section("loose_section", state)
    assert state.llm_calls == 1
    assert state.structure_retries.get("loose_section", 0) == 0


def test_retry_loop_passes_after_one_retry() -> None:
    """Validator fails first call, passes second; final content is the second attempt."""
    client = ReplayRlmClient(
        responses=[
            _resp("first attempt"),
            _resp(_VALIDATOR_MISS_REVISION),
            _resp("second attempt with revision A"),
            _resp(_VALIDATOR_PASS),
        ]
    )
    ex = _make_executor(client, enabled=True)
    state = PlanState()
    ex._generate_section("drawing_register", state)
    assert state.sections["drawing_register"] == "second attempt with revision A"
    assert state.structure_retries["drawing_register"] == 1
    assert "drawing_register" not in state.structure_unresolved


def test_retry_loop_gives_up_after_max_retries() -> None:
    """Validator always fails; state records max_retries+1 generates."""
    client = ReplayRlmClient(
        responses=[
            _resp("attempt 1"),
            _resp(_VALIDATOR_MISS_REVISION),
            _resp("attempt 2"),
            _resp(_VALIDATOR_MISS_REVISION),
            _resp("attempt 3"),
            _resp(_VALIDATOR_MISS_REVISION),
        ]
    )
    ex = _make_executor(client, enabled=True, max_retries=2)
    state = PlanState()
    ex._generate_section("drawing_register", state)
    # Final accepted content is the last attempt
    assert state.sections["drawing_register"] == "attempt 3"
    # 2 retries recorded (3 total attempts)
    assert state.structure_retries["drawing_register"] == 2
    # Unresolved entry populated
    assert "drawing_register" in state.structure_unresolved
    final = state.structure_unresolved["drawing_register"]
    assert final.passed is False
    assert any(g.field_name == "revision" for g in final.missing)


def test_retry_prompt_includes_gap_list() -> None:
    """The regeneration prompt for the retry call must contain the gap list."""
    captured_prompts: list[str] = []

    class _CapturingClient:
        def __init__(self, responses: list[RlmCompletionResponse]) -> None:
            self._inner = ReplayRlmClient(responses)

        def generate(
            self,
            *,
            model: str,
            messages: list[RlmMessage],
            system_prompt: str | None,
            temperature: float | None = None,
        ) -> RlmCompletionResponse:
            captured_prompts.append(messages[0].content)
            return self._inner.generate(
                model=model,
                messages=messages,
                system_prompt=system_prompt,
                temperature=temperature,
            )

    client = _CapturingClient(
        [
            _resp("first attempt"),
            _resp(_VALIDATOR_MISS_REVISION),
            _resp("second attempt"),
            _resp(_VALIDATOR_PASS),
        ]
    )
    ex = _make_executor(client, enabled=True)
    state = PlanState()
    ex._generate_section("drawing_register", state)
    # Prompt index: 0 = first generate, 1 = validator, 2 = retry generate, 3 = validator
    retry_prompt = captured_prompts[2]
    assert "missing or malformed" in retry_prompt.lower()
    assert "revision" in retry_prompt
    assert "no rev letter" in retry_prompt
