# ABOUTME: Tests PlanExecutor passes per-source priority into extraction/generation/review builders.
# ABOUTME: Uses patch-level spies to capture builder kwargs at each call site.

from unittest.mock import patch

from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig
from aec_bench.adapters.lambda_rlm.executor import PlanExecutor
from aec_bench.adapters.lambda_rlm.state import (
    CompositionOp,
    ExecutionPlan,
    LeafOp,
    ReviewResult,
    SectionPlan,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection

_EXTRACT_PATH = "aec_bench.adapters.lambda_rlm.executor.build_extraction_prompt"
_GENERATE_PATH = "aec_bench.adapters.lambda_rlm.executor.build_generation_prompt"
_REVIEW_PATH = "aec_bench.adapters.lambda_rlm.executor.run_review"


def _template_with_priority() -> ReportTemplate:
    return ReportTemplate(
        DependencyTreeSchema(
            sections=(
                TreeSection(
                    id="scope",
                    title="Scope",
                    fields={"body": OutputField(name="body", dtype="str", description="")},
                    depends_on=(),
                    generation_mode="prose",
                    writing_guidance=("crisp",),
                    input_mapping=("design_report:d", "project_brief:p"),
                    source_priority={
                        "design_report:d": 1,
                        "project_brief:p": 4,
                    },
                ),
            )
        )
    )


def _plan_two_sources() -> ExecutionPlan:
    return ExecutionPlan(
        section_order=["scope"],
        section_plans={
            "scope": SectionPlan(
                section_id="scope",
                generation_mode="prose",
                sources=["design_report:d", "project_brief:p"],
                leaf_ops=[
                    LeafOp(source="design_report:d", chunk_index=0, total_chunks=1),
                    LeafOp(source="project_brief:p", chunk_index=0, total_chunks=1),
                ],
                reduce_ops=[],
                composition_op=CompositionOp.MERGE_EXTRACTIONS,
                estimated_leaf_calls=2,
                estimated_reduce_calls=0,
            ),
        },
        skipped_sections=[],
    )


def _stub_review():
    return (
        ReviewResult(
            status="pass",
            gaps=[],
            risks=[],
            reextract_sources=[],
            supplement_guidance=None,
        ),
        (10, 5),
    )


def _client(n: int = 10) -> ReplayRlmClient:
    return ReplayRlmClient(
        [
            RlmCompletionResponse(
                output_text='{"a": 1}',
                input_tokens=10,
                output_tokens=5,
                cache_read_tokens=0,
                cache_write_tokens=0,
            )
            for _ in range(n)
        ]
    )


def test_executor_passes_priority_1_to_extraction_for_design_report():
    captured = []

    def spy_extract(**kwargs):
        captured.append(
            {
                "source_label": kwargs.get("source_label"),
                "source_priority": kwargs.get("source_priority"),
            }
        )
        return "prompt"

    with patch(_EXTRACT_PATH, spy_extract):
        with patch(_GENERATE_PATH, return_value="gen"):
            with patch(_REVIEW_PATH, return_value=_stub_review()):
                executor = PlanExecutor(
                    client=_client(),
                    model="test-model",
                    template=_template_with_priority(),
                    source_docs={"design_report": "alpha", "project_brief": "bravo"},
                    config=LambdaRlmConfig(),
                    trajectory_callback=None,
                )
                executor.execute(_plan_two_sources())

    assert len(captured) == 2
    by_source = {c["source_label"]: c["source_priority"] for c in captured}
    assert by_source["design_report:d"] == 1
    assert by_source["project_brief:p"] == 4


def test_executor_passes_full_priority_map_to_generation():
    captured = {}

    def spy_generate(**kwargs):
        captured["source_priority"] = kwargs.get("source_priority")
        return "gen"

    with patch(_EXTRACT_PATH, return_value="ex"):
        with patch(_GENERATE_PATH, spy_generate):
            with patch(_REVIEW_PATH, return_value=_stub_review()):
                executor = PlanExecutor(
                    client=_client(),
                    model="test-model",
                    template=_template_with_priority(),
                    source_docs={"design_report": "alpha", "project_brief": "bravo"},
                    config=LambdaRlmConfig(),
                    trajectory_callback=None,
                )
                executor.execute(_plan_two_sources())

    assert captured["source_priority"] == {
        "design_report:d": 1,
        "project_brief:p": 4,
    }


def test_executor_passes_empty_priority_when_unconfigured():
    """Section without source_priority -> builders get source_priority={} (not None)."""
    captured = {}

    def spy_generate(**kwargs):
        captured["source_priority"] = kwargs.get("source_priority")
        return "gen"

    template = ReportTemplate(
        DependencyTreeSchema(
            sections=(
                TreeSection(
                    id="scope",
                    title="Scope",
                    fields={"body": OutputField(name="body", dtype="str", description="")},
                    depends_on=(),
                    generation_mode="prose",
                    writing_guidance=("crisp",),
                    input_mapping=("design_report:d",),
                ),
            )
        )
    )
    plan = ExecutionPlan(
        section_order=["scope"],
        section_plans={
            "scope": SectionPlan(
                section_id="scope",
                generation_mode="prose",
                sources=["design_report:d"],
                leaf_ops=[LeafOp(source="design_report:d", chunk_index=0, total_chunks=1)],
                reduce_ops=[],
                composition_op=CompositionOp.MERGE_EXTRACTIONS,
                estimated_leaf_calls=1,
                estimated_reduce_calls=0,
            ),
        },
        skipped_sections=[],
    )

    with patch(_EXTRACT_PATH, return_value="ex"):
        with patch(_GENERATE_PATH, spy_generate):
            with patch(_REVIEW_PATH, return_value=_stub_review()):
                executor = PlanExecutor(
                    client=_client(),
                    model="test-model",
                    template=template,
                    source_docs={"design_report": "alpha"},
                    config=LambdaRlmConfig(),
                    trajectory_callback=None,
                )
                executor.execute(plan)

    assert captured["source_priority"] == {}
