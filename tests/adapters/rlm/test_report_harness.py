# ABOUTME: Runs synthetic report packages through the public guided report command surface.
# ABOUTME: Checks artifact commitment, isolated state, compaction, rules, and condition overrides.

import json
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from aec_bench.adapters.base import AdapterRequest
from aec_bench.adapters.rlm.client import RlmCompletionResponse
from aec_bench.adapters.rlm.initialiser import build_rlm_adapter
from aec_bench.contracts.agent_output import AgentOutputStatus

FIXTURES = {
    "inspection": Path(__file__).parents[3] / "tasks/civil/report/synthetic-inspection/environment/workspace",
    "options": Path(__file__).parents[2] / "fixtures/report_harness/options",
}


class RecordingClient:
    def __init__(self, *responses: RlmCompletionResponse) -> None:
        self.responses = iter(responses)
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> RlmCompletionResponse:
        self.calls.append(kwargs)
        return next(self.responses)


def replay(code: str, *, input_tokens: int = 100) -> RlmCompletionResponse:
    return RlmCompletionResponse(output_text=f"```repl\n{code}\n```", input_tokens=input_tokens, output_tokens=100)


@pytest.mark.parametrize(
    "package,source,first,last",
    [
        ("inspection", "inspection", "findings", "summary"),
        ("options", "options", "comparison", "decision"),
    ],
)
def test_report_package_commands_and_commit(tmp_path: Path, package: str, source: str, first: str, last: str) -> None:
    shutil.copytree(FIXTURES[package], tmp_path, dirs_exist_ok=True)
    output = tmp_path / "deliverable.md"
    client = RecordingClient(
        replay(f"""
assert {source!r} in DOCS()
facts = READ({source!r})
assert "12" in facts
assert START({first!r})["fields"]["text"]["required"]
assert not FILL({first!r}, {{"text": ""}}).success
assert not SUBMIT().complete
assert FILL({first!r}, {{"text": "12 units, from " + {source!r}}}).success
assert FILL({last!r}, {{"text": "The recorded count is 12."}}).success
assert SUBMIT().complete
COMMIT_OUTPUT()
""")
    )
    adapter = build_rlm_adapter(
        rlm_config_path=tmp_path / "rlm.toml",
        workspace_path=str(tmp_path),
        client=client,
        adapter_name="rlm",
        model_name="recording",
    )
    result = adapter.execute(
        AdapterRequest(
            instruction="TASK_POLICY: Use only the public evidence.",
            system_prompt="SYSTEM_POLICY",
            output_path=str(output),
            output_format="markdown_final_fenced_json",
            configuration={
                "output_completion_contract": {
                    "schema_version": "aecbench.output-completion-contract.v1",
                    "output_path": str(output),
                    "format": "markdown_final_fenced_json",
                    "required_top_level_keys": [first, last],
                    "require_single_final_json_block": True,
                },
                "output_completion_commit": True,
            },
        )
    )
    assert result.agent_output.status == AgentOutputStatus.COMPLETED, result.agent_output.error_message
    assert result.completion_commit is not None
    assert "12" in output.read_text()
    assert "SYSTEM_POLICY" in client.calls[0]["system_prompt"]


def test_report_state_and_instruction_survive_compaction(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES["inspection"], tmp_path, dirs_exist_ok=True)
    client = RecordingClient(
        replay(
            'facts = READ("inspection")\nNOTE("count", 12)\nFILL("findings", {"text": "12 items"})\n#' + "x" * 6000,
            input_tokens=8700,
        ),
        replay(
            'assert "TASK_POLICY" in context\nassert RECALL("count") == 12\nassert "12" in facts\n'
            'assert STATUS().completed == ["findings"]\nFILL("summary", {"text": "12 items"})\n'
            'SUBMIT()\nanswer = "done"\nFINAL_VAR("answer")'
        ),
    )
    compactor = RecordingClient(
        RlmCompletionResponse(output_text="Findings accepted; write summary.", input_tokens=50, output_tokens=20)
    )
    adapter = build_rlm_adapter(
        rlm_config_path=tmp_path / "rlm.toml",
        workspace_path=str(tmp_path),
        client=client,
        compaction_client=compactor,
        adapter_name="rlm",
        model_name="recording",
        configuration={"execution": {"context_limit": 10000}, "guardrails": {"token_budget": 50000}},
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
    assert "TASK_POLICY" in client.calls[1]["messages"][0].content
    assert "SYSTEM_POLICY" in compactor.calls[0]["system_prompt"]
    assert compactor.calls[0]["max_output_tokens"] == 2000
    assert result.usage_input_tokens == 8850


def test_sessions_run_with_independent_report_state(tmp_path: Path) -> None:
    def run(index: int) -> str:
        root = tmp_path / str(index)
        shutil.copytree(FIXTURES["options"], root)
        client = RecordingClient(
            replay(
                f'assert not STATUS().completed\nFILL("comparison", {{"text": "{index}"}})\n'
                f'FILL("decision", {{"text": "{index}"}})\nSUBMIT()\nanswer="done"\nFINAL_VAR("answer")'
            )
        )
        adapter = build_rlm_adapter(
            rlm_config_path=root / "rlm.toml",
            workspace_path=str(root),
            client=client,
            adapter_name="rlm",
            model_name="recording",
        )
        result = adapter.execute(
            AdapterRequest(instruction=f"Run {index}", output_path=str(root / "report.json"), output_format="json")
        )
        assert result.agent_output.status == AgentOutputStatus.COMPLETED
        value = json.loads((root / "report.json").read_text())["decision"]["text"]
        assert isinstance(value, str)
        return value

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(run, [1, 2])) == ["1", "2"]


def test_commit_rejects_report_artifact_changed_after_submit(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES["options"], tmp_path, dirs_exist_ok=True)
    output = tmp_path / "report.md"
    client = RecordingClient(
        replay(f"""
FILL("comparison", {{"text": "Accepted comparison"}})
FILL("decision", {{"text": "Accepted decision"}})
SUBMIT()
from pathlib import Path
Path({str(output)!r}).write_text('wrong artifact')
assert "rejected" in COMMIT_OUTPUT()
SUBMIT()
COMMIT_OUTPUT()
""")
    )
    adapter = build_rlm_adapter(
        rlm_config_path=tmp_path / "rlm.toml",
        workspace_path=str(tmp_path),
        client=client,
        adapter_name="rlm",
        model_name="recording",
    )
    result = adapter.execute(
        AdapterRequest(
            instruction="Report",
            output_path=str(output),
            output_format="markdown_final_fenced_json",
            configuration={
                "output_completion_commit": True,
                "output_completion_contract": {
                    "schema_version": "aecbench.output-completion-contract.v1",
                    "output_path": str(output),
                    "format": "markdown_final_fenced_json",
                    "required_top_level_keys": ["comparison", "decision"],
                    "require_single_final_json_block": True,
                },
            },
        )
    )
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert "Accepted decision" in output.read_text()


def test_condition_can_configure_report_without_rlm_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import tomllib

    from aec_bench.adapters.base import SerializedAdapterExecution
    from aec_bench.adapters.local_registry import build_local_adapter
    from aec_bench.harness.execution_entrypoint import RlmExecutionDriver
    from aec_bench.harness.execution_payload import AdapterRequestPayload, ExecutionBundle

    shutil.copytree(FIXTURES["options"], tmp_path, dirs_exist_ok=True)
    configuration = tomllib.loads((tmp_path / "rlm.toml").read_text())
    (tmp_path / "rlm.toml").unlink()
    code = """
assert "options" in DOCS()
FILL("comparison", {"text": "12 units"})
FILL("decision", {"text": "Choose 12 units"})
SUBMIT()
answer="done"
FINAL_VAR("answer")
"""
    for entrypoint in ("local", "bundle"):
        client = RecordingClient(replay(code))
        output = tmp_path / f"{entrypoint}.json"
        if entrypoint == "local":
            adapter = build_local_adapter(
                adapter_kind="rlm",
                model_name="recording",
                workspace=str(tmp_path),
                client=client,
                compaction_client=client,
                **configuration,
            )
            result = adapter.execute(
                AdapterRequest(instruction="Report", output_path=str(output), output_format="json")
            )
        else:
            monkeypatch.setattr(
                "aec_bench.harness.execution_entrypoint.make_rlm_client",
                lambda *args, _client=client, **kwargs: _client,
            )
            result = RlmExecutionDriver(workspace_dir=tmp_path).execute(
                ExecutionBundle(
                    execution=SerializedAdapterExecution(
                        adapter_kind="rlm", adapter_name="rlm", resolved_model="recording", payload={}
                    ),
                    request=AdapterRequestPayload(
                        instruction="Report",
                        system_prompt=None,
                        tools=[],
                        configuration=configuration,
                        output_path=str(output),
                        output_format="json",
                    ),
                )
            )
        assert result.agent_output.status == AgentOutputStatus.COMPLETED
        assert json.loads(output.read_text())["decision"]["text"] == "Choose 12 units"


def test_budget_stop_retains_accepted_sections_without_submit(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES["options"], tmp_path, dirs_exist_ok=True)
    client = RecordingClient(replay('FILL("comparison", {"text": "12 units"})'))
    output = tmp_path / "partial.json"
    adapter = build_rlm_adapter(
        rlm_config_path=tmp_path / "rlm.toml",
        workspace_path=str(tmp_path),
        client=client,
        adapter_name="rlm",
        model_name="recording",
        configuration={"guardrails": {"token_budget": 1}},
    )
    result = adapter.execute(AdapterRequest(instruction="Report", output_path=str(output), output_format="json"))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL
    assert json.loads(output.read_text()) == {"comparison": {"text": "12 units"}}
    assert result.raw_output_text == output.read_text()
    assert len(client.calls) == 1


def test_provider_exception_retains_partial_report_and_marks_usage_unknown(tmp_path: Path) -> None:
    shutil.copytree(FIXTURES["options"], tmp_path, dirs_exist_ok=True)

    class FailingClient(RecordingClient):
        def generate(self, **kwargs: Any) -> RlmCompletionResponse:
            if self.calls:
                raise RuntimeError("Synthetic provider interruption")
            return super().generate(**kwargs)

    client = FailingClient(replay('FILL("comparison", {"text": "12 units"})'))
    output = tmp_path / "partial.json"
    adapter = build_rlm_adapter(
        rlm_config_path=tmp_path / "rlm.toml",
        workspace_path=str(tmp_path),
        client=client,
        adapter_name="rlm",
        model_name="recording",
    )
    result = adapter.execute(AdapterRequest(instruction="Report", output_path=str(output), output_format="json"))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL
    assert "Synthetic provider interruption" in (result.provider_error or "")
    assert result.usage_input_tokens is None
    assert result.usage_output_tokens is None
    assert result.usage_model_calls == 2
    assert json.loads(output.read_text()) == {"comparison": {"text": "12 units"}}
