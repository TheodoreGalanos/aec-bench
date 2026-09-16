# ABOUTME: Exercises real local tool-loop and RLM delegation through the shared trajectory producer.
# ABOUTME: Checks live parent links, budget refusals, and failed child evidence without provider access.

import json
from pathlib import Path

import pytest
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.rlm.adapter import RlmAdapter
from aec_bench.adapters.rlm.client import ReplayRlmClient, RlmCompletionResponse, RlmMessage
from aec_bench.adapters.rlm.config import GuardrailConfig, SubcallConfig
from aec_bench.adapters.tool_loop import ToolLoopRequest
from aec_bench.adapters.tool_loop_local import PydanticAiToolLoopClient
from aec_bench.contracts.advisor import AdvisorConfig
from aec_bench.contracts.trajectory import read_trajectory
from aec_bench.harness.atif import to_atif
from aec_bench.trajectory.writer import TrajectoryWriter


@pytest.mark.parametrize("failure", [False, True])
def test_tool_loop_advisor_records_child_before_call_and_preserves_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: bool,
) -> None:
    source = tmp_path / "trajectory.jsonl"

    class Advisor:
        calls = 0

        def generate(
            self,
            *,
            model: str,
            messages: list[RlmMessage],
            system_prompt: str | None,
            temperature: float | None = None,
            max_output_tokens: int | None = None,
        ) -> RlmCompletionResponse:
            self.calls += 1
            preview = to_atif(read_trajectory(source), agent_name="tool_loop", agent_version="1")
            assert preview.subagent_trajectories is not None
            child = preview.subagent_trajectories[0]
            assert child.steps[0].message == system_prompt
            assert child.steps[1].message == messages[0].content
            assert child.agent.model_name == model
            assert all(step.llm_call_count is None for step in child.steps)
            if failure:
                raise RuntimeError("sensitive transport details")
            return RlmCompletionResponse(
                output_text=json.dumps({"advice": "Check units"}), input_tokens=80, output_tokens=15
            )

    requests = 0

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        nonlocal requests
        requests += 1
        if requests <= 2:
            return ModelResponse(parts=[ToolCallPart(tool_name="advisor", args={}, tool_call_id=f"advisor-{requests}")])
        return ModelResponse(parts=[TextPart("Done.")])

    monkeypatch.setattr("aec_bench.adapters.rlm.providers._build_pydantic_model", lambda *args: FunctionModel(respond))
    monkeypatch.setattr("aec_bench.adapters.rlm.providers._build_model_settings", lambda *args, **kwargs: {})
    advisor = Advisor()
    writer = TrajectoryWriter(str(source))
    client = PydanticAiToolLoopClient(
        "openai/test",
        workspace=str(tmp_path),
        trajectory_writer=writer,
        advisor_client=advisor,
        advisor_config=AdvisorConfig(model="child-model", max_uses=1),
    )
    try:
        result = client.next_turn(ToolLoopRequest(model="openai/test", instruction="Check the design."))
    finally:
        writer.close()
    assert advisor.calls == 1
    exported = to_atif(read_trajectory(source), agent_name="tool_loop", agent_version="1")
    assert exported.subagent_trajectories is not None
    assert len(exported.subagent_trajectories) == 1
    child = exported.subagent_trajectories[0]
    assert exported.steps[1].observation is not None
    assert exported.steps[1].observation.results[0].subagent_trajectory_ref is not None
    assert exported.steps[1].observation.results[0].subagent_trajectory_ref[0].trajectory_id == child.trajectory_id
    if failure:
        assert result.error_message is not None
        assert child.steps[-1].extra is not None
        assert child.steps[-1].extra["aec_bench"]["errors"] == ["RuntimeError"]
        assert child.steps[-1].llm_call_count is None
        assert "sensitive transport details" not in source.read_text()
    else:
        assert result.output_text == "Done."
        assert child.steps[-1].metrics is not None
        assert child.steps[-1].metrics.prompt_tokens == 80
        assert child.steps[-1].metrics.completion_tokens == 15
        assert exported.steps[2].observation is not None
        assert exported.steps[2].observation.results[0].subagent_trajectory_ref is None


@pytest.mark.parametrize("advisor", [False, True])
@pytest.mark.parametrize("child_count", [1, 2])
def test_rlm_delegation_links_to_the_executing_repl_call(tmp_path: Path, advisor: bool, child_count: int) -> None:
    source = tmp_path / "trajectory.jsonl"
    command = 'ADVISOR(goal="g", problem="p")' if advisor else 'reason(question="Check units")'
    if child_count > 1:
        command = "parallel([" + ", ".join(f"lambda: {command}" for _ in range(child_count)) + "])"
    main = ReplayRlmClient(
        [
            RlmCompletionResponse(output_text=f"```repl\n{command}\n```"),
            RlmCompletionResponse(output_text='```repl\nFINAL_VAR("done")\n```', done=True),
        ]
    )
    child = ReplayRlmClient(
        [
            RlmCompletionResponse(
                output_text=json.dumps({"advice": "Check units", "conclusion": "Units match"}),
                input_tokens=80,
                output_tokens=15,
            )
            for _ in range(child_count)
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm",
        model_name="test",
        client=main,
        guardrails=GuardrailConfig(max_iterations=3),
        trajectory_writer=TrajectoryWriter(str(source)),
        subcall_client=child,
        subcall_model="child-model",
        subcall_configs={"reason": SubcallConfig(name="reason", enabled=True)},
        advisor_client=child if advisor else None,
        advisor_config=AdvisorConfig(model="child-model") if advisor else None,
    )
    result = adapter.execute(AdapterRequest(instruction="Check the design."))
    assert result.agent_output.status == "completed"
    exported = to_atif(read_trajectory(source), agent_name="rlm", agent_version="1")
    assert exported.subagent_trajectories is not None
    assert len(exported.subagent_trajectories) == child_count
    child_trace = exported.subagent_trajectories[0]
    assert child_trace.agent.name == ("rlm:advisor" if advisor else "rlm:subcall")
    observations = [result for step in exported.steps if step.observation for result in step.observation.results]
    linked = next(result for result in observations if result.subagent_trajectory_ref)
    call = next(
        call for step in exported.steps for call in step.tool_calls or [] if call.tool_call_id == linked.source_call_id
    )
    assert call.function_name == "repl"
    assert linked.subagent_trajectory_ref is not None
    assert linked.subagent_trajectory_ref[0].trajectory_id == child_trace.trajectory_id
    assert {reference.trajectory_id for reference in linked.subagent_trajectory_ref} == {
        child.trajectory_id for child in exported.subagent_trajectories
    }
