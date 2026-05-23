# ABOUTME: Integration tests for the lambda-RLM executor's synthesis dispatch.
# ABOUTME: Verifies K candidates are generated and the synthesiser is invoked correctly.

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import (
    FillSectionConfig,
    LambdaRlmConfig,
    ReviewConfig,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.template_parser import parse_report_template
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.synthesis import SynthesisConfig, SynthesisOutput

_SINGLE_SECTION_TEMPLATE = """
[[sections]]
id = "methodology"
title = "Methodology"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Be clear"]
input_mapping = ["brief:Scope"]

[[sections.fields]]
name = "approach"
dtype = "str"
"""


def _extraction_resp(data: dict) -> RlmCompletionResponse:
    return RlmCompletionResponse(
        output_text=json.dumps(data),
        input_tokens=300,
        output_tokens=100,
    )


def _gen_resp(text: str) -> RlmCompletionResponse:
    return RlmCompletionResponse(output_text=text, input_tokens=500, output_tokens=200)


def test_synthesis_dispatch_generates_k_candidates_and_invokes_synthesiser(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    k = 3
    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"approach": "staged delivery"}),
            # K generations, one per candidate. Review is disabled below.
            _gen_resp("# Methodology\nFirst draft: staged delivery of works."),
            _gen_resp("# Methodology\nSecond draft: phased approach."),
            _gen_resp("# Methodology\nThird draft: iterative rollout."),
        ],
    )

    template = parse_report_template(_SINGLE_SECTION_TEMPLATE)
    source_docs = {"brief:Scope": "Deliver the works in stages."}

    config = LambdaRlmConfig(
        review=ReviewConfig(enabled=False),
        fill_section=FillSectionConfig(
            k_candidates=k,
            tournament_mode="synthesis",
            synthesis=SynthesisConfig(),
        ),
    )

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=config,
        workspace=str(workspace),
    )

    # Stub the synthesiser so we don't hit the network. Returns a clear fixed
    # output so we can check the adapter uses it verbatim.
    fake_output = SynthesisOutput(
        content="# Methodology\nSynthesised: staged and iterative rollout.",
        reason="merged drafts 1 and 3",
        synthesiser_model="anthropic:claude-sonnet-4-6",
        input_tokens=2_500,
        output_tokens=800,
        elapsed_s=25.0,
    )
    with patch(
        "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
        return_value=fake_output,
    ):
        result = adapter.execute(AdapterRequest(instruction="Write methodology."))

    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # Final section content is the synthesiser's output, not any single candidate.
    output_file = Path(result.agent_output.output_path)
    assert "Synthesised: staged and iterative rollout." in output_file.read_text()


def test_synthesis_dispatch_respects_apply_to_sections(tmp_path: Path) -> None:
    """When apply_to_sections is set and current section isn't in it,
    executor must use the single-call path instead of K-candidate synthesis."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"approach": "staged"}),
            # Single generate call — synthesis is NOT triggered for this section.
            _gen_resp("# Methodology\nSingle-call output."),
        ],
    )

    template = parse_report_template(_SINGLE_SECTION_TEMPLATE)
    source_docs = {"brief:Scope": "stages"}

    config = LambdaRlmConfig(
        review=ReviewConfig(enabled=False),
        fill_section=FillSectionConfig(
            k_candidates=4,
            tournament_mode="synthesis",
            apply_to_sections=("other_section",),  # does NOT include methodology
        ),
    )

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=config,
        workspace=str(workspace),
    )

    # Patch synthesise — if it's called, test fails.
    with patch(
        "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
        side_effect=AssertionError("synthesis should not be invoked"),
    ):
        result = adapter.execute(AdapterRequest(instruction="Write methodology."))

    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    output_file = Path(result.agent_output.output_path)
    assert "Single-call output." in output_file.read_text()


def test_synthesis_falls_back_when_synthesiser_returns_fallback(
    tmp_path: Path,
) -> None:
    """If the synthesiser hits an error (fallback_used=True), executor uses
    the bridge's fallback (longest candidate)."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    # Three candidates of increasing length; longest is the third.
    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"approach": "staged"}),
            _gen_resp("# Methodology\nShort."),
            _gen_resp("# Methodology\nMedium length content here."),
            _gen_resp("# Methodology\nLongest candidate with the most detail."),
        ],
    )

    template = parse_report_template(_SINGLE_SECTION_TEMPLATE)
    source_docs = {"brief:Scope": "stages"}

    config = LambdaRlmConfig(
        review=ReviewConfig(enabled=False),
        fill_section=FillSectionConfig(
            k_candidates=3,
            tournament_mode="synthesis",
        ),
    )

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=config,
        workspace=str(workspace),
    )

    failed = SynthesisOutput(
        content="",
        reason="",
        synthesiser_model="anthropic:claude-sonnet-4-6",
        input_tokens=0,
        output_tokens=0,
        elapsed_s=5.0,
        fallback_used=True,
        fallback_reason="empty_output",
    )
    with patch(
        "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
        return_value=failed,
    ):
        result = adapter.execute(AdapterRequest(instruction="Write methodology."))

    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    output_file = Path(result.agent_output.output_path)
    assert "Longest candidate with the most detail." in output_file.read_text()


def test_synthesis_uses_rubric_criteria_when_rubric_provided(tmp_path: Path) -> None:
    """With a Rubric passed to the adapter, the synthesiser should receive
    non-empty rubric_criteria in its SynthesisCriteria. Default path (no
    rubric) keeps backward compatibility — bundle.rubric_criteria empty."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"approach": "staged"}),
            _gen_resp("# Methodology\nCandidate one."),
            _gen_resp("# Methodology\nCandidate two."),
        ],
    )

    template = parse_report_template(_SINGLE_SECTION_TEMPLATE)
    source_docs = {"brief:Scope": "stages"}

    from aec_bench.contracts.rubric import (
        Rubric,
        RubricCriterion,
        RubricDimension,
    )

    rubric = Rubric(
        dimensions=(
            RubricDimension(
                id="methodology_quality",
                name="Methodology Quality",
                description="",
                weight=1.0,
                max_score=10.0,
                eval_method="llm_judge",
                criteria=(
                    RubricCriterion(text="covers staged delivery", category="essential"),
                    RubricCriterion(text="mentions risk mitigation", category="important"),
                ),
                eval_sections=("methodology",),
                eval_references=(),
                expert_persona="Senior engineer",
            ),
        ),
        rollup_strategy="weighted_mean",
    )

    config = LambdaRlmConfig(
        review=ReviewConfig(enabled=False),
        fill_section=FillSectionConfig(
            k_candidates=2,
            tournament_mode="synthesis",
        ),
    )

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=config,
        workspace=str(workspace),
        rubric=rubric,
    )

    captured: dict = {}

    def _capture(synthesis_input, *, client):  # noqa: ARG001
        captured["input"] = synthesis_input
        return SynthesisOutput(
            content="# Methodology\nSynthesised output.",
            reason="",
            synthesiser_model="m",
            input_tokens=1,
            output_tokens=1,
            elapsed_s=0.1,
        )

    with patch(
        "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
        side_effect=_capture,
    ):
        adapter.execute(AdapterRequest(instruction="Write methodology."))

    criteria = captured["input"].criteria
    assert criteria.rubric_criteria == (
        ("essential", "covers staged delivery"),
        ("important", "mentions risk mitigation"),
    )
    assert "Senior engineer" in criteria.expert_personas


def test_k_candidate_generation_runs_in_parallel(tmp_path: Path) -> None:
    """K candidate generate() calls should overlap in time, not serialise.

    Uses a client that sleeps 150ms per call. K=4 sequential would take ~600ms;
    K=4 parallel takes ~150–200ms. Assert well below the sequential bound.
    """
    import time

    workspace = tmp_path / "workspace"
    workspace.mkdir()

    class _SleepingClient:
        """Thread-safe client that sleeps per call; returns unique content per invocation."""

        def __init__(self, extraction_response: RlmCompletionResponse) -> None:
            import threading

            self._counter = 0
            self._lock = threading.Lock()
            self._extraction = extraction_response

        def generate(self, *, model, messages, system_prompt, temperature=None):  # noqa: ARG002
            with self._lock:
                i = self._counter
                self._counter += 1
            # First call is the extraction response; later calls are candidate
            # generations (the sleep gives us the parallelism window to measure).
            if i == 0:
                return self._extraction
            time.sleep(0.15)
            return _gen_resp(f"# Methodology\nCandidate {i}.")

    client = _SleepingClient(_extraction_resp({"approach": "staged"}))
    template = parse_report_template(_SINGLE_SECTION_TEMPLATE)
    k = 4
    config = LambdaRlmConfig(
        review=ReviewConfig(enabled=False),
        max_parallel_workers=k,
        fill_section=FillSectionConfig(
            k_candidates=k,
            tournament_mode="synthesis",
        ),
    )

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs={"brief:Scope": "s"},
        config=config,
        workspace=str(workspace),
    )

    fake_output = SynthesisOutput(
        content="# Methodology\nSynthesised.",
        reason="",
        synthesiser_model="m",
        input_tokens=1,
        output_tokens=1,
        elapsed_s=0.1,
    )
    with patch(
        "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
        return_value=fake_output,
    ):
        t0 = time.monotonic()
        result = adapter.execute(AdapterRequest(instruction="Write methodology."))
        elapsed = time.monotonic() - t0

    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # Sequential would take >= k * 0.15s = 0.6s. Parallel hits ~0.15–0.2s.
    # Use a generous 0.45s bound to avoid flakes under load.
    assert elapsed < 0.45, f"K={k} candidates took {elapsed:.2f}s — looks sequential (bound 0.45s)"


def test_synthesis_with_no_rubric_keeps_backward_compat(tmp_path: Path) -> None:
    """When no rubric is provided, rubric_criteria is empty — matches v1 behaviour."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"approach": "staged"}),
            _gen_resp("# Methodology\nOne."),
            _gen_resp("# Methodology\nTwo."),
        ],
    )

    template = parse_report_template(_SINGLE_SECTION_TEMPLATE)
    config = LambdaRlmConfig(
        review=ReviewConfig(enabled=False),
        fill_section=FillSectionConfig(
            k_candidates=2,
            tournament_mode="synthesis",
        ),
    )

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs={"brief:Scope": "s"},
        config=config,
        workspace=str(workspace),
        rubric=None,
    )

    captured: dict = {}

    def _capture(synthesis_input, *, client):  # noqa: ARG001
        captured["input"] = synthesis_input
        return SynthesisOutput(
            content="x",
            reason="",
            synthesiser_model="m",
            input_tokens=1,
            output_tokens=1,
            elapsed_s=0.1,
        )

    with patch(
        "aec_bench.adapters.lambda_rlm.synthesis.synthesise",
        side_effect=_capture,
    ):
        adapter.execute(AdapterRequest(instruction="Write methodology."))

    criteria = captured["input"].criteria
    assert criteria.rubric_criteria == ()
    assert criteria.expert_personas == ()
