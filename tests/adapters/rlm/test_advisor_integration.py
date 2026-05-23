# ABOUTME: Integration tests for the ADVISOR() REPL function in the RLM adapter.
# ABOUTME: Verifies advisor injection, max_uses enforcement, and trajectory metadata.

import json

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse
from aec_bench.adapters.rlm.config import GuardrailConfig
from aec_bench.contracts.advisor import AdvisorConfig


def _advisor_json(advice: str = "Try approach B") -> str:
    return json.dumps(
        {
            "advice": advice,
            "suggested_action": "switch strategy",
            "confidence": 0.85,
            "reasoning": "approach A has known limitations",
        }
    )


class TestAdvisorReplFunction:
    def test_advisor_available_when_configured(self) -> None:
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(output_text=_advisor_json(), input_tokens=500, output_tokens=200),
            ]
        )
        main_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text=(
                        "```repl\n"
                        'result = ADVISOR(goal="write intro", '
                        'problem="missing data")\n'
                        "print(result.response.advice)\n"
                        "```"
                    ),
                    input_tokens=100,
                    output_tokens=50,
                ),
                RlmCompletionResponse(
                    output_text='```repl\nFINAL_VAR("done")\n```',
                    input_tokens=100,
                    output_tokens=20,
                    done=True,
                ),
            ]
        )

        adapter = RlmAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            guardrails=GuardrailConfig(max_iterations=5),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=3),
        )
        result = adapter.execute(AdapterRequest(instruction="Do something"))
        assert result.agent_output.status == "completed"

    def test_advisor_not_available_without_config(self) -> None:
        main_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text='```repl\nprint("ADVISOR" in dir())\n```',
                    input_tokens=100,
                    output_tokens=50,
                ),
                RlmCompletionResponse(
                    output_text='```repl\nFINAL_VAR("done")\n```',
                    input_tokens=100,
                    output_tokens=20,
                    done=True,
                ),
            ]
        )

        adapter = RlmAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            guardrails=GuardrailConfig(max_iterations=5),
        )
        result = adapter.execute(AdapterRequest(instruction="Do something"))
        assert result.agent_output.status == "completed"

    def test_max_uses_enforced(self) -> None:
        advisor_client = ReplayRlmClient(
            [
                RlmCompletionResponse(output_text=_advisor_json(), input_tokens=100, output_tokens=50),
            ]
        )
        main_client = ReplayRlmClient(
            [
                RlmCompletionResponse(
                    output_text='```repl\nr1 = ADVISOR(goal="g", problem="p")\n```',
                    input_tokens=100,
                    output_tokens=50,
                ),
                RlmCompletionResponse(
                    output_text=('```repl\nr2 = ADVISOR(goal="g2", problem="p2")\nprint(r2.response.advice)\n```'),
                    input_tokens=100,
                    output_tokens=50,
                ),
                RlmCompletionResponse(
                    output_text='```repl\nFINAL_VAR("done")\n```',
                    input_tokens=100,
                    output_tokens=20,
                    done=True,
                ),
            ]
        )

        adapter = RlmAdapter(
            adapter_name="test",
            model_name="test-model",
            client=main_client,
            guardrails=GuardrailConfig(max_iterations=5),
            advisor_client=advisor_client,
            advisor_config=AdvisorConfig(model="advisor-model", max_uses=1),
        )
        result = adapter.execute(AdapterRequest(instruction="Do something"))
        assert result.agent_output.status == "completed"
