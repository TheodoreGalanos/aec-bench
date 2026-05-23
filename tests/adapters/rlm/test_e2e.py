# ABOUTME: End-to-end local pipeline test for the RLM adapter.
# ABOUTME: Exercises config files → adapter init → REPL loop with template → rubric scoring.

from pathlib import Path

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.initialiser import build_rlm_adapter
from aec_bench.adapters.rlm.template_parser import parse_report_template_with_rubric
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.rubric import DimensionScore
from aec_bench.evaluation.rubric_scorer import score_rubric


def test_e2e_config_to_template_to_rubric(tmp_path: Path) -> None:
    """Full pipeline: load config, run adapter with template, score with rubric."""

    # 1. Write config files
    rlm_toml = tmp_path / "rlm.toml"
    rlm_toml.write_text("""\
[template]
tier = "dependency_tree"
definition = "report_template.toml"

[guardrails]
token_budget = 100_000
max_iterations = 20

[subcalls.extract]
enabled = true
""")

    template_toml = tmp_path / "report_template.toml"
    template_toml.write_text("""\
[meta]
name = "Test Report"

[[sections]]
id = "background"
title = "Background"
depends_on = []
generation_mode = "transform"
fields = [
    { name = "context", dtype = "str", description = "Project context" },
]
writing_guidance = ["Describe the project"]

[[sections]]
id = "analysis"
title = "Analysis"
depends_on = ["background"]
generation_mode = "guided"
fields = [
    { name = "findings", dtype = "str", description = "Key findings" },
]

[rubric]
rollup_strategy = "weighted_mean"

[[rubric.dimensions]]
id = "completeness"
name = "Completeness"
description = "All sections filled"
weight = 1.0
max_score = 10.0
eval_method = "automated"
criteria = ["All sections present"]

[[rubric.dimensions]]
id = "quality"
name = "Content Quality"
description = "Technical soundness"
weight = 2.0
max_score = 10.0
eval_method = "llm_judge"
criteria = ["Sound reasoning"]
""")

    # 2. Build adapter from config
    client = ReplayRlmClient(
        responses=[
            # Agent fills background
            RlmCompletionResponse(
                output_text=('```repl\nreport.fill_section("background", {"context": "Sydney road project"})\n```'),
                input_tokens=300,
                output_tokens=100,
            ),
            # Agent fills analysis
            RlmCompletionResponse(
                output_text=('```repl\nreport.fill_section("analysis", {"findings": "Traffic improved"})\n```'),
                input_tokens=300,
                output_tokens=100,
            ),
            # Agent submits
            RlmCompletionResponse(
                output_text="FINAL\nReport complete.",
                input_tokens=200,
                output_tokens=50,
                done=True,
            ),
        ]
    )

    adapter = build_rlm_adapter(
        rlm_config_path=rlm_toml,
        client=client,
        adapter_name="rlm-e2e",
        model_name="test-model",
    )

    # 3. Run the adapter
    result = adapter.execute(AdapterRequest(instruction="Write a report about the project."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED

    # 4. Verify template was filled
    template = adapter._template
    assert template is not None
    status = template.get_status()
    assert status.completed_sections == 2
    assert status.total_sections == 2

    # 5. Score with rubric
    _, rubric = parse_report_template_with_rubric(template_toml.read_text())
    assert rubric is not None

    # Simulate scoring: completeness = 10/10 (all filled), quality = 7/10
    dimension_scores = [
        DimensionScore(
            dimension_id="completeness",
            score=10.0,
            max_score=10.0,
            evidence=f"{status.completed_sections}/{status.total_sections} sections",
            eval_method_used="automated",
        ),
        DimensionScore(
            dimension_id="quality",
            score=7.0,
            max_score=10.0,
            evidence="Good but could be more detailed",
            eval_method_used="llm_judge",
        ),
    ]
    rubric_result = score_rubric(rubric=rubric, scores=dimension_scores)

    # weighted_mean: (1.0 * 1.0 + 0.7 * 2.0) / 3.0 = 2.4 / 3.0 = 0.8
    assert abs(rubric_result.reward - 0.8) < 0.01
    assert len(rubric_result.dimension_scores) == 2

    # 6. Verify details format
    details = rubric_result.to_details()
    assert details["completeness"]["score"] == 10.0
    assert details["quality"]["score"] == 7.0
    assert "reward" in details
