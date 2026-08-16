# ABOUTME: Tests registration and execution of the DeepSeek Harness bundle driver.
# ABOUTME: Proves the driver parses treatment config and returns only AdapterResult values.

from pathlib import Path

from aec_bench.adapters.base import SerializedAdapterExecution
from aec_bench.adapters.deepseek_harness.events import reduce_deepseek_notifications
from aec_bench.adapters.deepseek_harness.runtime import DeepSeekHarnessRun
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.harness.deepseek_harness_driver import DeepSeekHarnessExecutionDriver
from aec_bench.harness.execution_entrypoint import default_execution_driver_registry
from aec_bench.harness.execution_payload import AdapterRequestPayload, ExecutionBundle


class _Runtime:
    def __init__(self, run: DeepSeekHarnessRun) -> None:
        self._run = run

    def run(self, _request: object) -> DeepSeekHarnessRun:
        return self._run


def _runtime(tmp_path: Path) -> _Runtime:
    evidence = tmp_path / "logs" / "deepseek-harness"
    evidence.mkdir(parents=True)
    notifications = [
        {
            "method": "session.event",
            "params": {
                "sessionId": "root",
                "event": {"type": "step/start", "seq": 1, "time": 1, "data": {"turn": 1, "step": 1}},
            },
        },
        {
            "method": "session.event",
            "params": {
                "sessionId": "root",
                "event": {
                    "type": "turn/end",
                    "seq": 2,
                    "time": 2,
                    "data": {"turn": 1, "reason": {"kind": "completed"}},
                },
            },
        },
        {"method": "session.status", "params": {"sessionId": "root", "status": "idle"}},
    ]
    notifications_path = evidence / "notifications.all.jsonl"
    notifications_path.write_text("{}\n", encoding="utf-8")
    stderr_path = evidence / "stderr.log"
    stderr_path.write_text("", encoding="utf-8")
    return _Runtime(
        DeepSeekHarnessRun(
            session_id="root",
            final_response="done",
            finish_reason="completed",
            sdk_version="0.1.0rc6",
            runtime_distribution_version="fake-runtime",
            runtime_reported_version=None,
            timeout_seconds=1800,
            max_tokens=None,
            projection=reduce_deepseek_notifications("root", notifications),
            notifications_path=notifications_path,
            stderr_path=stderr_path,
        )
    )


def test_default_registry_contains_deepseek_harness(tmp_path: Path) -> None:
    driver = default_execution_driver_registry(workspace_dir=tmp_path).resolve("deepseek_harness")

    assert isinstance(driver, DeepSeekHarnessExecutionDriver)


def test_driver_maps_bundle_through_injected_runtime(tmp_path: Path) -> None:
    driver = DeepSeekHarnessExecutionDriver(
        workspace_dir=tmp_path,
        runtime_factory=lambda _settings, _workspace: _runtime(tmp_path),
    )
    bundle = ExecutionBundle(
        execution=SerializedAdapterExecution(
            adapter_kind="deepseek_harness",
            adapter_name="deepseek-treatment",
            resolved_model="azure:deepseek-v4-flash",
            payload={"provider": "azure"},
        ),
        request=AdapterRequestPayload(
            instruction="Do the work",
            system_prompt="Use the declared method.",
            tools=[],
            configuration={"timeout_sec": 5},
            output_path=str(tmp_path / "output.md"),
            output_format="markdown",
        ),
    )

    result = driver.execute(bundle)

    assert result.adapter_name == "deepseek-treatment"
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.transcript[0].content == "Use the declared method."
    assert result.transcript[1].content == "Do the work"
