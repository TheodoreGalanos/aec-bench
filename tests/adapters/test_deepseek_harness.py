# ABOUTME: Tests DeepSeek Harness outcome mapping into the provider-neutral adapter result.
# ABOUTME: Keeps model stop, partial output, failure, transcript, and verifier authority separate.

from pathlib import Path

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterRequest,
    AdapterStopReason,
)
from aec_bench.adapters.deepseek_harness import DeepSeekHarnessAdapter
from aec_bench.adapters.deepseek_harness.config import DeepSeekHarnessSettings
from aec_bench.adapters.deepseek_harness.events import reduce_deepseek_notifications
from aec_bench.adapters.deepseek_harness.runtime import (
    DeepSeekHarnessRun,
    DeepSeekHarnessRuntimeError,
    DeepSeekHarnessRuntimeTimeout,
)
from aec_bench.adapters.deepseek_harness.tool_gateway import (
    NativeToolDefinition,
    NativeToolResponse,
)
from aec_bench.adapters.output_commit import build_output_commit_attestation
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.output_completion import OutputCommitAttestation, OutputCompletionContract
from aec_bench.contracts.task_definition import ToolSpec


class _Runtime:
    def __init__(self, run: DeepSeekHarnessRun) -> None:
        self._run = run
        self.calls = 0

    def run(self, request: AdapterRequest) -> DeepSeekHarnessRun:
        del request
        self.calls += 1
        return self._run


class _RaisingRuntime:
    def __init__(self, error: DeepSeekHarnessRuntimeError) -> None:
        self._error = error

    def run(self, request: AdapterRequest) -> DeepSeekHarnessRun:
        del request
        raise self._error


def _run(
    tmp_path: Path,
    *,
    finish_reason: str,
    final_response: str = "final text",
    output_commit_mode: str = "disabled",
    completion_commit: OutputCommitAttestation | None = None,
    commit_error: str | None = None,
) -> DeepSeekHarnessRun:
    notifications = [
        {
            "method": "session.event",
            "params": {"sessionId": "root", "event": {"type": "turn/start", "seq": 1, "time": 1, "data": {"turn": 1}}},
        },
        {
            "method": "session.event",
            "params": {
                "sessionId": "root",
                "event": {"type": "step/start", "seq": 2, "time": 2, "data": {"turn": 1, "step": 1}},
            },
        },
        {
            "method": "session.event",
            "params": {
                "sessionId": "root",
                "event": {
                    "type": "turn/end",
                    "seq": 3,
                    "time": 3,
                    "data": {"turn": 1, "reason": {"kind": finish_reason}},
                },
            },
        },
        {"method": "session.status", "params": {"sessionId": "root", "status": "idle"}},
    ]
    evidence = tmp_path / "logs" / "deepseek-harness"
    evidence.mkdir(parents=True)
    notifications_path = evidence / "notifications.all.jsonl"
    notifications_path.write_text("\n".join("{}" for _ in notifications) + "\n", encoding="utf-8")
    stderr_path = evidence / "stderr.log"
    stderr_path.write_text("", encoding="utf-8")
    return DeepSeekHarnessRun(
        session_id="root",
        final_response=final_response,
        finish_reason=finish_reason,
        sdk_version="0.1.0rc6",
        runtime_distribution_version="fake-runtime",
        runtime_reported_version=None,
        timeout_seconds=1800,
        max_tokens=None,
        projection=reduce_deepseek_notifications("root", notifications),
        notifications_path=notifications_path,
        stderr_path=stderr_path,
        output_commit_mode=output_commit_mode,
        completion_commit=completion_commit,
        commit_error=commit_error,
    )


def _settings(tmp_path: Path) -> DeepSeekHarnessSettings:
    del tmp_path
    return DeepSeekHarnessSettings.from_execution_payload(
        model_name="azure:deepseek-v4-flash",
        payload={"provider": "azure"},
    )


def _commit_configuration(output_path: Path) -> dict[str, object]:
    return {
        "output_completion_commit": True,
        "output_completion_contract": {
            "schema_version": "aecbench.output-completion-contract.v1",
            "output_path": str(output_path),
            "format": "markdown_final_fenced_json",
            "required_top_level_keys": ["findings", "summary"],
            "require_single_final_json_block": True,
        },
    }


def test_maps_normal_idle_without_claiming_verifier_success(tmp_path: Path) -> None:
    runtime = _Runtime(_run(tmp_path, finish_reason="completed"))
    adapter = DeepSeekHarnessAdapter(settings=_settings(tmp_path), workspace=tmp_path, runtime=runtime)

    result = adapter.execute(
        AdapterRequest(instruction="Do the task", output_path="output.md", output_format="markdown")
    )

    assert runtime.calls == 1
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.failure_kind is None
    assert result.raw_output_text == "final text"
    assert result.turns_used == 1
    assert result.configuration_record["provider"] == "azure"
    assert result.configuration_record["harness_route"] == "azure"
    assert result.configuration_record["output_commit_mode"] == "disabled"
    assert result.configuration_record["root_session_id"] == "root"


def test_maps_max_tokens_as_partial_budget_stop(tmp_path: Path) -> None:
    runtime = _Runtime(_run(tmp_path, finish_reason="max-tokens"))
    adapter = DeepSeekHarnessAdapter(settings=_settings(tmp_path), workspace=tmp_path, runtime=runtime)

    result = adapter.execute(AdapterRequest(instruction="Do the task"))

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TOKEN_BUDGET_REACHED
    assert result.stop_reason is AdapterStopReason.TOKEN_BUDGET
    assert result.completion_reason is None


def test_noncompleted_runtime_outcome_cannot_publish_an_accepted_commit(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    output_path.write_text(
        'Report\n```json\n{"findings": [], "summary": {}}\n```\n',
        encoding="utf-8",
    )
    contract = OutputCompletionContract.model_validate(_commit_configuration(output_path)["output_completion_contract"])
    attestation, _diagnostic = build_output_commit_attestation(contract, initial_content=None, commit_turn=1)
    assert attestation is not None
    runtime = _Runtime(
        _run(
            tmp_path,
            finish_reason="max-tokens",
            final_response="",
            output_commit_mode="required",
            completion_commit=attestation,
        )
    )
    adapter = DeepSeekHarnessAdapter(settings=_settings(tmp_path), workspace=tmp_path, runtime=runtime)

    result = adapter.execute(
        AdapterRequest(
            instruction="Do the task",
            output_path=str(output_path),
            output_format="markdown",
            configuration=_commit_configuration(output_path),
        )
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TOKEN_BUDGET_REACHED
    assert result.completion_reason is None
    assert result.completion_commit is None


def test_normal_idle_without_a_candidate_is_missing_output(tmp_path: Path) -> None:
    runtime = _Runtime(_run(tmp_path, finish_reason="completed", final_response=""))
    adapter = DeepSeekHarnessAdapter(settings=_settings(tmp_path), workspace=tmp_path, runtime=runtime)

    result = adapter.execute(AdapterRequest(instruction="Do the task"))

    assert result.agent_output.status is AgentOutputStatus.EMPTY
    assert result.failure_kind is AdapterFailureKind.MISSING_OUTPUT
    assert result.completion_reason is None
    assert result.transcript[0].content == "You are a software engineering agent."


def test_native_tool_catalogue_does_not_create_candidate_output(tmp_path: Path) -> None:
    runtime = _Runtime(_run(tmp_path, finish_reason="completed", final_response=""))

    adapter = DeepSeekHarnessAdapter(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        runtime=runtime,
        native_tools=(
            NativeToolDefinition(
                name="observe_state",
                description="Observe state",
                parameters_schema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                    "additionalProperties": False,
                },
                handler=lambda _invocation, _arguments: NativeToolResponse(result={"status": "observed"}),
            ),
        ),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Observe the task",
            tools=[ToolSpec(name="observe_state", source="builtin", description="Observe state")],
        )
    )

    assert result.agent_output.status is AgentOutputStatus.EMPTY
    assert result.failure_kind is AdapterFailureKind.MISSING_OUTPUT


def test_only_an_accepted_commit_maps_to_output_contract_committed(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    output_path.write_text(
        'Report\n```json\n{"findings": [], "summary": {}}\n```\n',
        encoding="utf-8",
    )
    contract = OutputCompletionContract.model_validate(_commit_configuration(output_path)["output_completion_contract"])
    attestation, _diagnostic = build_output_commit_attestation(contract, initial_content=None, commit_turn=1)
    assert attestation is not None
    runtime = _Runtime(
        _run(
            tmp_path,
            finish_reason="completed",
            final_response="",
            output_commit_mode="required",
            completion_commit=attestation,
        )
    )
    adapter = DeepSeekHarnessAdapter(settings=_settings(tmp_path), workspace=tmp_path, runtime=runtime)

    result = adapter.execute(
        AdapterRequest(
            instruction="Do the task",
            output_path=str(output_path),
            output_format="markdown",
            configuration=_commit_configuration(output_path),
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
    assert result.completion_commit == attestation
    assert result.configuration_record["output_commit_mode"] == "required"
    assert result.configuration_record["plugin_free_baseline"] is False


def test_required_commit_without_acceptance_is_partial_missing_output(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    output_path.write_text("Uncommitted candidate\n", encoding="utf-8")
    runtime = _Runtime(
        _run(
            tmp_path,
            finish_reason="completed",
            final_response="",
            output_commit_mode="required",
        )
    )
    adapter = DeepSeekHarnessAdapter(settings=_settings(tmp_path), workspace=tmp_path, runtime=runtime)

    result = adapter.execute(
        AdapterRequest(
            instruction="Do the task",
            output_path=str(output_path),
            output_format="markdown",
            configuration=_commit_configuration(output_path),
        )
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.MISSING_OUTPUT
    assert result.completion_reason is None
    assert result.completion_commit is None
    assert result.agent_output.error_message == "DeepSeek Harness completed without an accepted output commit"


def test_maps_runtime_error_as_provider_failure(tmp_path: Path) -> None:
    adapter = DeepSeekHarnessAdapter(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        runtime=_RaisingRuntime(DeepSeekHarnessRuntimeError("protocol failed")),
    )

    result = adapter.execute(AdapterRequest(instruction="Do the task"))

    assert result.agent_output.status is AgentOutputStatus.FAILED
    assert result.failure_kind is AdapterFailureKind.PROVIDER_ERROR
    assert result.provider_error == "protocol failed"


def test_maps_timeout_with_a_candidate_as_partial(tmp_path: Path) -> None:
    (tmp_path / "output.md").write_text("partial candidate", encoding="utf-8")
    adapter = DeepSeekHarnessAdapter(
        settings=_settings(tmp_path),
        workspace=tmp_path,
        runtime=_RaisingRuntime(DeepSeekHarnessRuntimeTimeout("trial timed out")),
    )

    result = adapter.execute(
        AdapterRequest(instruction="Do the task", output_path="output.md", output_format="markdown")
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TIMEOUT
    assert result.provider_error is None
