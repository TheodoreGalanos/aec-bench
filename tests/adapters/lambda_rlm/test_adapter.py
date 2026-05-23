# ABOUTME: Integration tests for the LambdaRlmAdapter.
# ABOUTME: Validates full pipeline: plan → extract → review → generate → output.

import json
from pathlib import Path

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import (
    ExtractConfig,
    LambdaRlmConfig,
    ReviewConfig,
)
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.template import ReportTemplate
from aec_bench.adapters.rlm.template_parser import parse_report_template
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.trajectory.writer import TrajectoryWriter

_TEMPLATE_TOML = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Carry language verbatim"]
input_mapping = ["brief:Description"]

[[sections.fields]]
name = "context"
dtype = "str"

[[sections]]
id = "design"
title = "Design"
depends_on = ["background"]
generation_mode = "transform"
writing_guidance = ["Commit to preferred option"]
input_mapping = ["brief:Scope"]

[[sections.fields]]
name = "features"
dtype = "str"
"""


def _extraction_resp(data: dict) -> RlmCompletionResponse:
    return RlmCompletionResponse(output_text=json.dumps(data), input_tokens=300, output_tokens=100)


def _review_pass() -> RlmCompletionResponse:
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


def _gen_resp(text: str) -> RlmCompletionResponse:
    return RlmCompletionResponse(output_text=text, input_tokens=500, output_tokens=200)


def test_adapter_produces_completed_result(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"location": "Princes Highway"}),
            _review_pass(),
            _gen_resp("# Background\nThe project is on Princes Highway."),
            _extraction_resp({"options": "CHR"}),
            _review_pass(),
            _gen_resp("# Design\nThe preferred option is CHR."),
        ]
    )

    template = parse_report_template(_TEMPLATE_TOML)
    source_docs = {
        "brief:Description": "Princes Highway project background.",
        "brief:Scope": "Scope includes CHR treatment.",
    }

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
        workspace=str(workspace),
    )

    result = adapter.execute(AdapterRequest(instruction="Write the proposal."))

    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.adapter_name == "lambda-rlm"
    assert result.resolved_model == "test-model"
    assert result.usage_input_tokens > 0
    assert result.usage_output_tokens > 0
    assert len(result.transcript) > 0


def test_adapter_writes_output_file(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"location": "Highway"}),
            _review_pass(),
            _gen_resp("Background content."),
            _extraction_resp({"options": "CHR"}),
            _review_pass(),
            _gen_resp("Design content."),
        ]
    )

    template = parse_report_template(_TEMPLATE_TOML)
    source_docs = {"brief:Description": "Bg.", "brief:Scope": "Scope."}

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
        workspace=str(workspace),
    )

    adapter.execute(AdapterRequest(instruction="Write it."))

    output_path = workspace / "output.md"
    assert output_path.exists()
    content = output_path.read_text()
    assert "Background" in content or "background" in content.lower()


def test_adapter_transcript_has_plan_entry(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"data": "value"}),
            _review_pass(),
            _gen_resp("Section content."),
        ]
    )

    single_toml = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Verbatim"]
input_mapping = ["brief:bg"]

[[sections.fields]]
name = "context"
dtype = "str"
"""
    template = parse_report_template(single_toml)
    source_docs = {"brief:bg": "Some background."}

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
        workspace=str(workspace),
    )

    result = adapter.execute(AdapterRequest(instruction="Go."))

    call_types = [e.call_type for e in result.transcript if hasattr(e, "call_type")]
    assert "plan" in call_types


def test_adapter_review_disabled(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"data": "value"}),
            _gen_resp("Section content."),
        ]
    )

    single_toml = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Verbatim"]
input_mapping = ["brief:bg"]

[[sections.fields]]
name = "context"
dtype = "str"
"""
    template = parse_report_template(single_toml)
    source_docs = {"brief:bg": "Some background."}

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(review=ReviewConfig(enabled=False)),
        workspace=str(workspace),
    )

    result = adapter.execute(AdapterRequest(instruction="Go."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


def test_adapter_writes_trajectory_entries(tmp_path: Path):
    """Adapter writes trajectory entries when writer provided."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    traj_path = workspace / "trajectory.jsonl"
    writer = TrajectoryWriter(path=str(traj_path))

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"location": "Highway"}),
            _review_pass(),
            _gen_resp("Background content."),
            _extraction_resp({"options": "CHR"}),
            _review_pass(),
            _gen_resp("Design content."),
        ]
    )
    template = parse_report_template(_TEMPLATE_TOML)
    source_docs = {"brief:Description": "Bg.", "brief:Scope": "Scope."}

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
        workspace=str(workspace),
        trajectory_writer=writer,
    )
    adapter.execute(AdapterRequest(instruction="Write it."))
    writer.close()

    entries = []
    for line in traj_path.read_text().splitlines():
        data = json.loads(line)
        if "version" in data:
            continue
        entries.append(data)

    # Should have entries for: plan, extract*2, review*2, generate*2, complete (at minimum)
    assert len(entries) >= 8
    plan_entries = [e for e in entries if e.get("tool_name") == "plan"]
    assert len(plan_entries) >= 1
    extract_entries = [e for e in entries if e.get("tool_name") == "extract"]
    assert len(extract_entries) >= 2
    result_entries = [e for e in entries if e.get("role") == "tool_result"]
    for entry in result_entries:
        assert "metadata" in entry
        assert "plan_state" in entry["metadata"]


def test_adapter_writes_extraction_candidates_artifact(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"__confidence__": 0.9, "location": "Princes Highway"}),
            _extraction_resp({"__confidence__": 0.6, "location": "Princes Highway"}),
            _extraction_resp({"__confidence__": 0.3, "location": "Old Highway"}),
            _gen_resp("Background section."),
            _extraction_resp({"__confidence__": 0.8, "options": "CHR"}),
            _extraction_resp({"__confidence__": 0.7, "options": "CHR"}),
            _extraction_resp({"__confidence__": 0.4, "options": "BAR"}),
            _gen_resp("Design section."),
        ]
    )

    template = parse_report_template(_TEMPLATE_TOML)
    source_docs = {
        "brief:Description": "Princes Highway project background.",
        "brief:Scope": "Scope includes CHR treatment.",
    }

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(
            extract=ExtractConfig(k_candidates=3, keep_candidates_artifact=True),
            review=ReviewConfig(enabled=False),
            max_parallel_workers=1,
        ),
        workspace=str(workspace),
    )

    adapter.execute(AdapterRequest(instruction="Write the proposal."))

    candidates_path = workspace / "extraction_candidates.json"
    assert candidates_path.exists()
    candidates = json.loads(candidates_path.read_text())
    assert len(candidates["background"]["brief:Description"]) == 3
    assert len(candidates["design"]["brief:Scope"]) == 3


def test_adapter_trajectory_has_template_progress(tmp_path: Path):
    """Generate entries include template_progress metadata."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    traj_path = workspace / "trajectory.jsonl"
    writer = TrajectoryWriter(path=str(traj_path))

    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"data": "value"}),
            _review_pass(),
            _gen_resp("Section content."),
        ]
    )
    single_toml = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Verbatim"]
input_mapping = ["brief:bg"]

[[sections.fields]]
name = "context"
dtype = "str"
"""
    template = parse_report_template(single_toml)
    source_docs = {"brief:bg": "Some background."}

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
        workspace=str(workspace),
        trajectory_writer=writer,
    )
    adapter.execute(AdapterRequest(instruction="Go."))
    writer.close()

    entries = []
    for line in traj_path.read_text().splitlines():
        data = json.loads(line)
        if "version" in data:
            continue
        entries.append(data)

    gen_results = [e for e in entries if e.get("role") == "tool_result" and e.get("tool_name") == "generate"]
    assert len(gen_results) >= 1
    meta = gen_results[0]["metadata"]
    assert "template_progress" in meta
    assert "completed" in meta["template_progress"]
    assert "total" in meta["template_progress"]
    assert "section_list" in meta["template_progress"]


def test_adapter_works_without_trajectory_writer(tmp_path: Path):
    """Adapter works fine when no trajectory_writer is provided."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    client = ReplayRlmClient(
        responses=[
            _extraction_resp({"data": "value"}),
            _review_pass(),
            _gen_resp("Section content."),
        ]
    )
    single_toml = """
[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
writing_guidance = ["Verbatim"]
input_mapping = ["brief:bg"]

[[sections.fields]]
name = "context"
dtype = "str"
"""
    template = parse_report_template(single_toml)
    source_docs = {"brief:bg": "Some background."}

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportTemplate(template),
        source_docs=source_docs,
        config=LambdaRlmConfig(),
        workspace=str(workspace),
    )
    result = adapter.execute(AdapterRequest(instruction="Go."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


def test_adapter_callback_attaches_synthesis_event(tmp_path: Path):
    """When phase=='synthesise', the trajectory callback includes the
    latest synthesis event (including full candidate content) in metadata
    so offline reruns can reconstruct the synthesis input."""
    from aec_bench.adapters.lambda_rlm.state import PlanState

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    traj_path = workspace / "trajectory.jsonl"
    writer = TrajectoryWriter(path=str(traj_path))

    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=ReplayRlmClient(responses=[]),
        template=ReportTemplate(parse_report_template(_TEMPLATE_TOML)),
        source_docs={},
        config=LambdaRlmConfig(),
        workspace=str(workspace),
        trajectory_writer=writer,
    )

    cb = adapter._make_traj_callback()
    assert cb is not None

    state = PlanState()
    synth_event = {
        "step_type": "section_synthesis",
        "section_id": "background",
        "k": 2,
        "candidates": [
            {
                "id": "cand-0",
                "content": "first draft text",
                "content_hash": "h0",
                "tokens": 100,
            },
            {
                "id": "cand-1",
                "content": "second draft text",
                "content_hash": "h1",
                "tokens": 120,
            },
        ],
        "synthesiser_model": "m",
        "synthesiser_input_tokens": 300,
        "synthesiser_output_tokens": 80,
        "elapsed_s": 1.2,
        "synthesised_hash": "hs",
        "reason": "merged",
        "fallback_used": False,
        "fallback_reason": None,
    }
    state.synthesis_events.append(synth_event)

    cb("synthesise", "background", None, state)
    writer.close()

    entries = [json.loads(line) for line in traj_path.read_text().splitlines()]
    results = [e for e in entries if e.get("role") == "tool_result" and e.get("tool_name") == "synthesise"]
    assert len(results) == 1
    meta = results[0]["metadata"]
    assert "synthesis" in meta
    assert meta["synthesis"]["k"] == 2
    assert [c["content"] for c in meta["synthesis"]["candidates"]] == [
        "first draft text",
        "second draft text",
    ]
