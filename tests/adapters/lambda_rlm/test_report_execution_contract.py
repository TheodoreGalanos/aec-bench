# ABOUTME: Exercises report instructions, observed budgets, and declared artifacts through lambda execution.
# ABOUTME: Uses synthetic templates and recording clients without provider access.

from pathlib import Path
from typing import Any

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter
from aec_bench.adapters.lambda_rlm.config import LambdaRlmConfig, ReviewConfig
from aec_bench.adapters.rlm.client import RlmCompletionResponse
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.repl import DependencyTreeSchema, TreeSection
from aec_bench.templates.report.session import ReportSession


class RecordingClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> RlmCompletionResponse:
        self.calls.append(kwargs)
        return RlmCompletionResponse(output_text="A synthetic report.", input_tokens=200, output_tokens=100)


def make_adapter(tmp_path: Path, client: RecordingClient, budget: int = 1000) -> LambdaRlmAdapter:
    return LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="test-model",
        client=client,
        template=ReportSession(DependencyTreeSchema([TreeSection("summary", "Summary", {})])),
        source_docs={},
        config=LambdaRlmConfig(token_budget=budget, review=ReviewConfig(enabled=False)),
        workspace=str(tmp_path),
    )


def test_instruction_policy_and_output_path_are_honoured(tmp_path: Path) -> None:
    client = RecordingClient()
    result = make_adapter(tmp_path, client).execute(
        AdapterRequest(
            instruction="TASK_MARKER",
            system_prompt="SYSTEM_MARKER",
            output_path=str(tmp_path / "report.json"),
            output_format="json",
        )
    )
    assert all("SYSTEM_MARKER" in c["system_prompt"] for c in client.calls)
    assert all(any(m.role == "user" and "TASK_MARKER" in m.content for m in c["messages"]) for c in client.calls)
    assert result.agent_output.output_path == str(tmp_path / "report.json")
    assert result.agent_output.output_format == "json"
    assert (tmp_path / "report.json").exists()


def test_one_token_budget_cannot_complete_after_300_tokens(tmp_path: Path) -> None:
    client = RecordingClient()
    result = make_adapter(tmp_path, client, budget=1).execute(
        AdapterRequest(
            instruction="Write a report",
            output_path=str(tmp_path / "report.md"),
            output_format="markdown",
        )
    )
    assert result.agent_output.status == AgentOutputStatus.PARTIAL
    assert result.usage_input_tokens == 200
    assert result.usage_output_tokens == 100
    assert len(client.calls) == 1


def test_synthesis_uses_run_policy_references_limits_and_real_usage(tmp_path: Path) -> None:
    import json

    from aec_bench.adapters.lambda_rlm.config import FillSectionConfig
    from aec_bench.contracts.repl import OutputField
    from aec_bench.contracts.rubric import Rubric, RubricCriterion, RubricDimension
    from aec_bench.contracts.synthesis import SynthesisConfig

    class Client(RecordingClient):
        def generate(self, **kwargs: Any) -> RlmCompletionResponse:
            self.calls.append(kwargs)
            return RlmCompletionResponse(
                output_text=json.dumps({"text": "12 inspected items"}), input_tokens=20, output_tokens=10
            )

    client = Client()
    schema = DependencyTreeSchema(
        [TreeSection("findings", "Findings", {"text": OutputField("text", "str", "")}, input_mapping=("allowed",))]
    )
    schema = DependencyTreeSchema(
        [*schema.sections, TreeSection("appendix", "Appendix", {"text": OutputField("text", "str", "")})]
    )
    rubric = Rubric(
        dimensions=[
            RubricDimension(
                id="evidence",
                name="Evidence",
                description="",
                weight=2,
                max_score=10,
                eval_method="llm_judge",
                eval_references=("allowed",),
                criteria=(RubricCriterion(text="Cite the count", category="essential"),),
            )
        ]
    )
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="writer",
        client=client,
        template=ReportSession(schema, rubric=rubric),
        rubric=rubric,
        source_docs={"allowed": "12 items", "excluded": "EXCLUDED_REFERENCE_MARKER"},
        config=LambdaRlmConfig(
            review=ReviewConfig(enabled=False),
            fill_section=FillSectionConfig(
                k_candidates=2,
                apply_to_sections=("findings",),
                temperature=0.37,
                tournament_mode="synthesis",
                synthesis=SynthesisConfig(synthesiser_model="synthesiser", max_output_tokens=321),
            ),
        ),
        workspace=str(tmp_path),
    )
    result = adapter.execute(
        AdapterRequest(
            instruction="TASK_POLICY",
            system_prompt="SYSTEM_POLICY",
            output_path=str(tmp_path / "report.json"),
            output_format="json",
        )
    )
    assert result.agent_output.status == AgentOutputStatus.COMPLETED, result.agent_output.error_message
    synth = next(c for c in client.calls if c["model"] == "synthesiser")
    assert synth["max_output_tokens"] == 321
    assert "EXCLUDED_REFERENCE_MARKER" not in str(synth["messages"])
    assert "evidence" in str(synth["messages"])
    assert [c["temperature"] for c in client.calls if c.get("temperature") == 0.37] == [0.37, 0.37]
    assert result.usage_input_tokens == 100
    assert result.usage_output_tokens == 50
    assert all("SYSTEM_POLICY" in c["system_prompt"] for c in client.calls)
    assert all(c["messages"][0].content == "TASK_POLICY" for c in client.calls)


def test_review_retries_each_source_then_uses_bounded_advice(tmp_path: Path) -> None:
    import json

    from aec_bench.contracts.advisor import AdvisorConfig
    from aec_bench.contracts.repl import OutputField

    review = json.dumps(
        {"status": "needs_reextract", "gaps": ["Resolve conflicting counts"], "reextract_sources": ["a", "b"]}
    )
    responses = iter(
        [
            '{"count":12}',
            '{"count":12}',
            review,
            '{"count":12}',
            '{"count":12}',
            review,
            '{"advice":"State the uncertainty", "confidence":0.5}',
            '{"text":"12 items; uncertainty recorded"}',
        ]
    )

    class Client(RecordingClient):
        def generate(self, **kwargs: Any) -> RlmCompletionResponse:
            self.calls.append(kwargs)
            return RlmCompletionResponse(output_text=next(responses), input_tokens=20, output_tokens=10)

    client = Client()
    adapter = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="writer",
        client=client,
        template=ReportSession(
            DependencyTreeSchema(
                [TreeSection("summary", "Summary", {"text": OutputField("text", "str", "")}, input_mapping=("a", "b"))]
            )
        ),
        source_docs={"a": "12 items", "b": "12 items"},
        config=LambdaRlmConfig(
            max_parallel_workers=1,
            advisor=AdvisorConfig(model="advisor", max_uses=1, max_response_tokens=123, context_window=2),
        ),
        workspace=str(tmp_path),
    )
    result = adapter.execute(
        AdapterRequest(instruction="TASK_POLICY", output_path=str(tmp_path / "report.json"), output_format="json")
    )
    assert result.agent_output.status == AgentOutputStatus.COMPLETED, result.agent_output.error_message
    assert len(client.calls) == 8
    assert result.usage_model_calls == 7
    assert result.usage_advisor_calls == 1
    assert result.usage_advisor_input_tokens == 20
    assert client.calls[6]["model"] == "advisor"
    assert client.calls[6]["max_output_tokens"] == 123
    assert "State the uncertainty" in str(client.calls[7]["messages"])


def test_compose_calls_receive_public_rubric_and_writing_checks(tmp_path: Path) -> None:
    from aec_bench.contracts.repl import OutputField
    from aec_bench.contracts.report_rules import ReportRule
    from aec_bench.contracts.report_template import GeneratedBlock
    from aec_bench.contracts.rubric import Rubric, RubricCriterion, RubricDimension

    class Client(RecordingClient):
        def generate(self, **kwargs: Any) -> RlmCompletionResponse:
            self.calls.append(kwargs)
            return RlmCompletionResponse(output_text="12 inspected items", input_tokens=20, output_tokens=10)

    client = Client()
    template = ReportSession(
        DependencyTreeSchema(
            [
                TreeSection(
                    "findings",
                    "Findings",
                    {"text": OutputField("text", "str", "")},
                    generation_mode="compose",
                    blocks=(GeneratedBlock(prompt="State the count", sources=()),),
                )
            ]
        ),
        rubric=Rubric(
            dimensions=[
                RubricDimension(
                    id="public-evidence",
                    name="Evidence",
                    description="",
                    weight=2,
                    max_score=10,
                    eval_method="automated",
                    criteria=(RubricCriterion(text="PUBLIC_CRITERION", category="essential"),),
                )
            ]
        ),
        rules=(ReportRule(id="public-count", kind="required_pattern", pattern="12", message="PUBLIC_RULE"),),
    )
    result = LambdaRlmAdapter(
        adapter_name="lambda-rlm",
        model_name="writer",
        client=client,
        template=template,
        source_docs={},
        config=LambdaRlmConfig(review=ReviewConfig(enabled=False)),
        workspace=str(tmp_path),
    ).execute(
        AdapterRequest(
            instruction="TASK_POLICY",
            system_prompt="SYSTEM_POLICY",
            output_path=str(tmp_path / "report.json"),
            output_format="json",
        )
    )
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert len(client.calls) == 1
    policy = client.calls[0]["system_prompt"]
    for marker in ("SYSTEM_POLICY", "PUBLIC_CRITERION", "PUBLIC_RULE", "public-evidence"):
        assert marker in policy
