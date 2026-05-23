# ABOUTME: Tests for the lambda-rlm plan executor.
# ABOUTME: Validates leaf dispatch, reduce merging, review integration, and generation.

import json

import pytest

from aec_bench.adapters.lambda_rlm.config import (
    ExtractConfig,
    LambdaRlmConfig,
    PlannerConfig,
    ReviewConfig,
    UncertaintyConfig,
)
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.state import (
    CompositionOp,
    ExecutionPlan,
    LeafOp,
    PlanState,
    SectionPlan,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection


def _make_template() -> ReportTemplate:
    """Minimal two-section template."""
    schema = DependencyTreeSchema(
        sections=(
            TreeSection(
                id="background",
                title="Background",
                fields={"context": OutputField(name="context", dtype="str", description="")},
                depends_on=(),
                generation_mode="transform",
                writing_guidance=("Carry language verbatim",),
                input_mapping=("brief:Description",),
            ),
            TreeSection(
                id="design",
                title="Design",
                fields={"features": OutputField(name="features", dtype="str", description="")},
                depends_on=("background",),
                generation_mode="transform",
                writing_guidance=("Commit to preferred option",),
                input_mapping=("brief:Scope",),
            ),
        )
    )
    return ReportTemplate(schema)


def _make_plan() -> ExecutionPlan:
    """Plan matching the two-section template."""
    return ExecutionPlan(
        section_order=["background", "design"],
        section_plans={
            "background": SectionPlan(
                section_id="background",
                generation_mode="transform",
                sources=["brief:Description"],
                leaf_ops=[LeafOp(source="brief:Description", chunk_index=0, total_chunks=1)],
                reduce_ops=[],
                composition_op=CompositionOp.MERGE_EXTRACTIONS,
                estimated_leaf_calls=1,
                estimated_reduce_calls=0,
            ),
            "design": SectionPlan(
                section_id="design",
                generation_mode="transform",
                sources=["brief:Scope"],
                leaf_ops=[LeafOp(source="brief:Scope", chunk_index=0, total_chunks=1)],
                reduce_ops=[],
                composition_op=CompositionOp.MERGE_EXTRACTIONS,
                estimated_leaf_calls=1,
                estimated_reduce_calls=0,
            ),
        },
        skipped_sections=[],
    )


def _make_single_section_chunked_plan(total_chunks: int = 3) -> ExecutionPlan:
    return ExecutionPlan(
        section_order=["background"],
        section_plans={
            "background": SectionPlan(
                section_id="background",
                generation_mode="transform",
                sources=["brief:Description"],
                leaf_ops=[
                    LeafOp(
                        source="brief:Description",
                        chunk_index=index,
                        total_chunks=total_chunks,
                    )
                    for index in range(total_chunks)
                ],
                reduce_ops=[],
                composition_op=CompositionOp.MERGE_EXTRACTIONS,
                estimated_leaf_calls=total_chunks,
                estimated_reduce_calls=1,
            ),
        },
        skipped_sections=[],
    )


def _extraction_response(data: dict) -> RlmCompletionResponse:
    return RlmCompletionResponse(
        output_text=json.dumps(data),
        input_tokens=300,
        output_tokens=100,
    )


def _review_pass_response() -> RlmCompletionResponse:
    return RlmCompletionResponse(
        output_text=json.dumps(
            {
                "status": "pass",
                "gaps": [],
                "risks": [],
                "reextract_sources": [],
                "supplement_guidance": None,
            }
        ),
        input_tokens=400,
        output_tokens=80,
    )


def _generation_response(text: str) -> RlmCompletionResponse:
    return RlmCompletionResponse(
        output_text=text,
        input_tokens=500,
        output_tokens=200,
    )


class RecordingRlmClient:
    """Test double that records per-call temperatures and returns scripted responses."""

    def __init__(self, responses: list[RlmCompletionResponse]) -> None:
        import threading

        self._responses = list(responses)
        self._index = 0
        self._lock = threading.Lock()
        self.calls: list[dict[str, object]] = []

    def generate(
        self,
        *,
        model: str,
        messages: list,
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        with self._lock:
            response = self._responses[self._index]
            self._index += 1
            self.calls.append(
                {
                    "model": model,
                    "temperature": temperature,
                    "prompt": messages[-1].content,
                    "system_prompt": system_prompt,
                },
            )
        return response


def test_executor_runs_full_pipeline():
    """Execute a two-section plan end-to-end."""
    # Response sequence:
    # bg_extract, bg_review, bg_generate, design_extract, design_review, design_generate
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"location": "Princes Highway"}),
            _review_pass_response(),
            _generation_response("The project is on Princes Highway."),
            _extraction_response({"options": "CHR, BAR"}),
            _review_pass_response(),
            _generation_response("The preferred option is CHR treatment."),
        ]
    )

    source_docs = {
        "brief:Description": "Background about Princes Highway project.",
        "brief:Scope": "Scope includes CHR and BAR treatments.",
    }

    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
    )

    result = executor.execute(_make_plan())

    assert result.phase == "complete"
    assert "background" in result.sections
    assert "design" in result.sections
    assert result.llm_calls == 6
    assert result.tokens_used > 0


def test_executor_review_disabled():
    """When review is disabled, skip review calls."""
    # Response sequence: bg_extract, bg_generate, design_extract, design_generate
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"location": "Princes Highway"}),
            _generation_response("Background section."),
            _extraction_response({"options": "CHR"}),
            _generation_response("Design section."),
        ]
    )

    source_docs = {
        "brief:Description": "Background text.",
        "brief:Scope": "Scope text.",
    }

    config = LambdaRlmConfig(review=ReviewConfig(enabled=False))
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs=source_docs,
        config=config,
    )

    result = executor.execute(_make_plan())

    assert result.phase == "complete"
    assert result.llm_calls == 4


def test_executor_tracks_extractions():
    """Extracted data should be stored in state and accessible."""
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"location": "Princes Highway", "road_designation": "MR123"}),
            _review_pass_response(),
            _generation_response("Background content."),
            _extraction_response({"options": "CHR"}),
            _review_pass_response(),
            _generation_response("Design content."),
        ]
    )

    source_docs = {
        "brief:Description": "Background about Princes Highway.",
        "brief:Scope": "Scope includes CHR.",
    }

    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
    )

    result = executor.execute(_make_plan())

    assert result.extractions["background"]["brief:Description"]["location"] == "Princes Highway"
    assert result.extractions["design"]["brief:Scope"]["options"] == "CHR"


def test_executor_fills_template():
    """Executor should fill the ReportTemplate and it should report sections as completed."""
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"location": "Highway"}),
            _review_pass_response(),
            _generation_response("Background text."),
            _extraction_response({"options": "CHR"}),
            _review_pass_response(),
            _generation_response("Design text."),
        ]
    )

    source_docs = {
        "brief:Description": "Bg.",
        "brief:Scope": "Scope.",
    }

    template = _make_template()
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=template,
        source_docs=source_docs,
        config=LambdaRlmConfig(),
    )

    executor.execute(_make_plan())

    status = template.get_status()
    assert status.completed_sections == 2
    assert "background" in status.completed
    assert "design" in status.completed


def test_coerce_confidence_clamps_and_warns(caplog: pytest.LogCaptureFixture) -> None:
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs={},
        config=LambdaRlmConfig(),
    )

    with caplog.at_level("WARNING"):
        assert executor._coerce_confidence(1.4) == 1.0

    assert any("confidence" in message.lower() for message in caplog.messages)


def test_coerce_confidence_missing_returns_none_without_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs={},
        config=LambdaRlmConfig(),
    )

    with caplog.at_level("WARNING"):
        assert executor._coerce_confidence(None) is None

    assert caplog.messages == []


def test_leaf_extract_strips_confidence_and_records_chunk() -> None:
    client = ReplayRlmClient(
        responses=[_extraction_response({"__confidence__": 0.77, "foo": "bar"})],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(),
    )
    state = PlanState()

    extracted = executor._leaf_extract(
        section_info=executor._get_section_info("background"),
        source_label="brief:Description",
        chunk_text="Background text.",
        dependency_context={},
        state=state,
    )

    assert extracted == {"foo": "bar"}
    assert state.extraction_confidence_chunks["background"]["brief:Description"] == [0.77]


def test_leaf_extract_records_output_tokens_and_updates_running_stats() -> None:
    client = ReplayRlmClient(
        responses=[_extraction_response({"__confidence__": 0.77, "foo": "bar"})],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(),
    )
    state = PlanState()

    executor._leaf_extract(
        section_info=executor._get_section_info("background"),
        source_label="brief:Description",
        chunk_text="Background text.",
        dependency_context={},
        state=state,
    )

    assert state.leaf_output_tokens["background"]["brief:Description"] == [100]
    assert executor._token_stats.n == 1
    assert executor._token_stats.mean == 100


def test_extract_section_single_chunk_missing_confidence_records_missing_reason(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = ReplayRlmClient(
        responses=[_extraction_response({"foo": "bar"})],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(review=ReviewConfig(enabled=False)),
    )
    state = PlanState()

    with caplog.at_level("WARNING"):
        executor._extract_section(_make_plan().section_plans["background"], state)

    assert state.extractions["background"]["brief:Description"] == {"foo": "bar"}
    assert "background" not in state.extraction_confidence
    assert state.extraction_confidence_missing["background"]["brief:Description"] == "missing_key"
    assert caplog.messages == []


def test_extract_section_chunked_confidence_aggregates_min_of_chunks() -> None:
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"__confidence__": 0.9, "value": "alpha"}),
            _extraction_response({"__confidence__": 0.7, "value": "beta"}),
            _extraction_response({"__confidence__": 0.5, "value": "gamma"}),
            _extraction_response({"merged": "ok"}),
        ],
    )
    source_text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": source_text},
        config=LambdaRlmConfig(
            planner=PlannerConfig(context_window_chars=20),
            review=ReviewConfig(enabled=False),
        ),
    )
    state = PlanState()

    executor._extract_section(
        _make_single_section_chunked_plan().section_plans["background"],
        state,
    )

    assert state.extraction_confidence_chunks["background"]["brief:Description"] == [
        0.9,
        0.7,
        0.5,
    ]
    assert state.extraction_confidence["background"]["brief:Description"] == 0.5
    assert "background" not in state.extraction_confidence_missing


def test_extract_section_chunked_partial_confidence_records_partial_missing() -> None:
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"__confidence__": 0.9, "value": "alpha"}),
            _extraction_response({"value": "beta"}),
            _extraction_response({"__confidence__": 0.5, "value": "gamma"}),
            _extraction_response({"merged": "ok"}),
        ],
    )
    source_text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": source_text},
        config=LambdaRlmConfig(
            planner=PlannerConfig(context_window_chars=20),
            review=ReviewConfig(enabled=False),
        ),
    )
    state = PlanState()

    executor._extract_section(
        _make_single_section_chunked_plan().section_plans["background"],
        state,
    )

    assert state.extraction_confidence_chunks["background"]["brief:Description"] == [
        0.9,
        0.5,
    ]
    assert "background" not in state.extraction_confidence
    assert state.extraction_confidence_missing["background"]["brief:Description"] == "partial_chunks_missing"


def test_extract_section_computes_uncertainty_scores_when_trigger_active() -> None:
    client = ReplayRlmClient(
        responses=[_extraction_response({"__confidence__": 0.8, "foo": "bar"})],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(
            review=ReviewConfig(enabled=False, trigger="uncertainty"),
            uncertainty=UncertaintyConfig(min_samples=1),
        ),
    )
    state = PlanState()

    executor._extract_section(_make_plan().section_plans["background"], state)

    assert state._uncertainty_scoring_active is True
    assert state.uncertainty_scores["background"]["brief:Description"] == pytest.approx(
        0.2231435513,
    )
    assert state.snapshot()["uncertainty"]["population_stats"] == {
        "mean": 100.0,
        "stdev": 0.0,
        "n": 1,
    }


def test_extract_section_does_not_compute_uncertainty_scores_when_trigger_inactive() -> None:
    client = ReplayRlmClient(
        responses=[_extraction_response({"__confidence__": 0.8, "foo": "bar"})],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(
            review=ReviewConfig(enabled=False, trigger="always"),
            uncertainty=UncertaintyConfig(min_samples=1),
        ),
    )
    state = PlanState()

    executor._extract_section(_make_plan().section_plans["background"], state)

    assert state._uncertainty_scoring_active is False
    assert state.uncertainty_scores == {}
    assert state.leaf_output_tokens["background"]["brief:Description"] == [100]


def test_leaf_extract_k_passes_temperature_to_client() -> None:
    client = RecordingRlmClient(
        responses=[
            _extraction_response({"__confidence__": 0.9, "tank_count": 4}),
            _extraction_response({"__confidence__": 0.7, "tank_count": 4}),
            _extraction_response({"__confidence__": 0.5, "tank_count": 3}),
        ],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(
            extract=ExtractConfig(k_candidates=3, temperature=0.2),
            review=ReviewConfig(enabled=False),
            max_parallel_workers=1,
        ),
    )
    state = PlanState()

    merged, consistency = executor._leaf_extract_k(
        section_info=executor._get_section_info("background"),
        source_label="brief:Description",
        chunk_text="Background text.",
        dependency_context={},
        state=state,
        k=3,
        temperature=0.2,
    )

    assert merged == {"tank_count": 4}
    assert consistency == pytest.approx(2 / 3)
    assert [call["temperature"] for call in client.calls] == [0.2, 0.2, 0.2]


def test_extract_section_with_k_candidates_records_consistency_and_candidates() -> None:
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"__confidence__": 0.9, "tank_count": 4}),
            _extraction_response({"__confidence__": 0.6, "tank_count": 4}),
            _extraction_response({"__confidence__": 0.3, "tank_count": 3}),
        ],
    )
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": "Background text."},
        config=LambdaRlmConfig(
            extract=ExtractConfig(k_candidates=3, keep_candidates_artifact=True),
            review=ReviewConfig(enabled=False),
            max_parallel_workers=1,
        ),
    )
    state = PlanState()

    executor._extract_section(_make_plan().section_plans["background"], state)

    assert state.extractions["background"]["brief:Description"] == {"tank_count": 4}
    assert state.extraction_consistency["background"]["brief:Description"] == pytest.approx(
        2 / 3,
    )
    assert state.extraction_confidence_chunks["background"]["brief:Description"] == [
        pytest.approx(0.6),
    ]
    assert state.extraction_confidence["background"]["brief:Description"] == pytest.approx(0.6)
    assert state.extraction_candidates == {
        "background": {
            "brief:Description": [
                {"tank_count": 4},
                {"tank_count": 4},
                {"tank_count": 3},
            ],
        },
    }


def test_extract_section_chunked_k_uses_min_of_chunk_means_for_confidence() -> None:
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"__confidence__": 0.9, "value": "alpha"}),
            _extraction_response({"__confidence__": 0.6, "value": "alpha"}),
            _extraction_response({"__confidence__": 0.3, "value": "beta"}),
            _extraction_response({"__confidence__": 0.8, "value": "gamma"}),
            _extraction_response({"__confidence__": 0.7, "value": "gamma"}),
            _extraction_response({"__confidence__": 0.6, "value": "gamma"}),
            _extraction_response({"merged": "ok"}),
        ],
    )
    source_text = "alpha bravo charlie delta echo foxtrot golf hotel india juliet"
    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={"brief:Description": source_text},
        config=LambdaRlmConfig(
            planner=PlannerConfig(context_window_chars=20),
            extract=ExtractConfig(k_candidates=3),
            review=ReviewConfig(enabled=False),
            max_parallel_workers=1,
        ),
    )
    state = PlanState()

    executor._extract_section(
        _make_single_section_chunked_plan(total_chunks=2).section_plans["background"],
        state,
    )

    assert state.extraction_confidence_chunks["background"]["brief:Description"] == [
        pytest.approx(0.6),
        pytest.approx(0.7),
    ]
    assert state.extraction_confidence["background"]["brief:Description"] == pytest.approx(0.6)


def test_should_run_review_respects_never_trigger() -> None:
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs={},
        config=LambdaRlmConfig(review=ReviewConfig(trigger="never")),
    )

    should_run, reason = executor._should_run_review("background", PlanState())

    assert should_run is False
    assert "never" in reason


def test_should_run_review_consistency_falls_back_without_data() -> None:
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs={},
        config=LambdaRlmConfig(review=ReviewConfig(trigger="consistency")),
    )

    should_run, reason = executor._should_run_review("background", PlanState())

    assert should_run is True
    assert "no consistency data" in reason
    assert "falling back" in reason


def test_should_run_review_uncertainty_uses_max_source_score() -> None:
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs={},
        config=LambdaRlmConfig(
            review=ReviewConfig(trigger="uncertainty"),
            uncertainty=UncertaintyConfig(review_joint_threshold=1.0),
        ),
    )
    state = PlanState(
        uncertainty_scores={"background": {"brief:Description": 0.4, "brief:Scope": 1.2}},
    )

    should_run, reason = executor._should_run_review("background", state)

    assert should_run is True
    assert "1.20" in reason


def test_should_run_review_both_requires_low_consistency_and_high_uncertainty() -> None:
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs={},
        config=LambdaRlmConfig(
            review=ReviewConfig(trigger="both", consistency_threshold=0.7),
            uncertainty=UncertaintyConfig(review_joint_threshold=1.0),
        ),
    )
    triggered_state = PlanState(
        extraction_consistency={"background": {"brief:Description": 0.6}},
        uncertainty_scores={"background": {"brief:Description": 1.2}},
    )
    skipped_state = PlanState(
        extraction_consistency={"background": {"brief:Description": 0.9}},
        uncertainty_scores={"background": {"brief:Description": 1.2}},
    )

    should_run, trigger_reason = executor._should_run_review("background", triggered_state)
    should_skip, skip_reason = executor._should_run_review("background", skipped_state)

    assert should_run is True
    assert "consistency" in trigger_reason
    assert should_skip is False
    assert "skip" in skip_reason


def test_executor_skips_review_when_trigger_policy_says_never() -> None:
    client = ReplayRlmClient(
        responses=[
            _extraction_response({"location": "Princes Highway"}),
            _generation_response("Background section."),
            _extraction_response({"options": "CHR"}),
            _generation_response("Design section."),
        ]
    )

    executor = PlanExecutor(
        client=client,
        model="test-model",
        template=_make_template(),
        source_docs={
            "brief:Description": "Background text.",
            "brief:Scope": "Scope text.",
        },
        config=LambdaRlmConfig(review=ReviewConfig(trigger="never")),
    )

    result = executor.execute(_make_plan())

    assert result.llm_calls == 4
    assert result.reviews == {}


# ─── Task 15: sandbox plumbing through PlanExecutor ─────────────────────────


def test_executor_resolve_source_uses_sandbox_when_provided():
    """When sandbox is provided, _resolve_source fetches via sandbox.slice(label, None)."""
    from unittest.mock import MagicMock

    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    docs = {"brief.md": "# T\n\n## Scope\nbody"}
    sandbox = DocumentSandbox.from_documents(docs, extractor_overrides={})

    executor = PlanExecutor(
        client=MagicMock(),
        model="m",
        template=_make_template(),
        source_docs=docs,
        config=LambdaRlmConfig(),
        sandbox=sandbox,
    )
    # Bare label fetches whole-doc text via the sandbox; same content as source_docs.
    assert executor._resolve_source("brief.md") == docs["brief.md"]


def test_executor_resolve_source_falls_back_to_source_docs_when_no_sandbox():
    """Back-compat: sandbox=None uses source_docs[label] directly."""
    docs = {"brief.md": "Brief text"}
    executor = PlanExecutor(
        client=ReplayRlmClient([]),
        model="test-model",
        template=_make_template(),
        source_docs=docs,
        config=LambdaRlmConfig(),
        sandbox=None,
    )
    assert executor._resolve_source("brief.md") == "Brief text"


def test_executor_resolve_source_unknown_label_returns_empty_when_sandbox():
    """Sandbox raises KeyError on unknown label; executor catches and returns empty
    to preserve today's behaviour where _resolve_source returns '' for misses."""
    from unittest.mock import MagicMock

    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    sandbox = DocumentSandbox.from_documents({"brief.md": "Brief"}, extractor_overrides={})
    executor = PlanExecutor(
        client=MagicMock(),
        model="m",
        template=_make_template(),
        source_docs={"brief.md": "Brief"},
        config=LambdaRlmConfig(),
        sandbox=sandbox,
    )
    assert executor._resolve_source("nonexistent.md") == ""


def test_get_section_info_includes_fields() -> None:
    """_get_section_info must surface declared fields so the executor can
    pass them to build_generation_prompt and the structure validator."""
    from unittest.mock import MagicMock

    from aec_bench.adapters.lambda_rlm.sandbox import DocumentSandbox

    executor = PlanExecutor(
        client=MagicMock(),
        model="m",
        template=_make_template(),
        source_docs={"brief.md": "Brief"},
        config=LambdaRlmConfig(),
        sandbox=DocumentSandbox.from_documents({"brief.md": "Brief"}, extractor_overrides={}),
    )

    # Test matching section includes its fields
    info = executor._get_section_info("background")
    assert info["id"] == "background"
    assert "fields" in info
    assert "context" in info["fields"]
    assert info["fields"]["context"].dtype == "str"

    # Test another section
    info = executor._get_section_info("design")
    assert info["id"] == "design"
    assert "fields" in info
    assert "features" in info["fields"]
    assert info["fields"]["features"].dtype == "str"

    # Test fallback (nonexistent section) includes empty fields dict
    info = executor._get_section_info("nonexistent")
    assert info["id"] == "nonexistent"
    assert "fields" in info
    assert info["fields"] == {}
