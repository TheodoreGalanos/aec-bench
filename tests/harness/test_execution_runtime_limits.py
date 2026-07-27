# ABOUTME: Tests fail-closed validation of lowered runtime-budget declarations.
# ABOUTME: Proves unsupported limits stop before any execution driver can reach a model.

from dataclasses import dataclass
from pathlib import Path
from typing import NoReturn

import pytest

from aec_bench.adapters.base import SerializedAdapterExecution
from aec_bench.harness.execution_entrypoint import ExecutionDriverRegistry, run_execution_bundle
from aec_bench.harness.execution_payload import AdapterRequestPayload, ExecutionBundle, write_execution_bundle


class _DriverReached(RuntimeError):
    pass


@dataclass
class _RecordingDriver:
    calls: int = 0

    def execute(self, bundle: ExecutionBundle) -> NoReturn:
        del bundle
        self.calls += 1
        raise _DriverReached


def _run_with_recording_driver(
    *,
    tmp_path: Path,
    adapter_kind: str,
    configuration: dict[str, object],
) -> _RecordingDriver:
    bundle_path = write_execution_bundle(
        path=tmp_path / "bundle.json",
        bundle=ExecutionBundle(
            execution=SerializedAdapterExecution(
                adapter_kind=adapter_kind,
                adapter_name=adapter_kind,
                resolved_model="test-model",
            ),
            request=AdapterRequestPayload(
                instruction="Execute within the declared limits.",
                system_prompt=None,
                tools=[],
                configuration=configuration,
                output_path=str(tmp_path / "output.md"),
                output_format="markdown",
            ),
        ),
    )
    driver = _RecordingDriver()
    registry = ExecutionDriverRegistry(drivers={adapter_kind: driver})
    run_execution_bundle(
        bundle_path=bundle_path,
        result_path=tmp_path / "result.json",
        registry=registry,
    )
    return driver


@pytest.mark.parametrize(
    "adapter_kind",
    ["direct", "tool_loop", "pydantic_ai", "rlm", "lambda_rlm"],
)
def test_exact_context_limit_is_rejected_before_driver_execution(
    tmp_path: Path,
    adapter_kind: str,
) -> None:
    with pytest.raises(RuntimeError, match="max_context_tokens.*cannot be enforced exactly"):
        _run_with_recording_driver(
            tmp_path=tmp_path,
            adapter_kind=adapter_kind,
            configuration={"max_context_tokens": 4_000},
        )


@pytest.mark.parametrize("access_mode", ["read_only", "read_write"])
def test_tool_loop_rejects_access_modes_without_runtime_isolation(
    tmp_path: Path,
    access_mode: str,
) -> None:
    with pytest.raises(RuntimeError, match=f"tool_access_mode={access_mode!r} is not supported"):
        _run_with_recording_driver(
            tmp_path=tmp_path,
            adapter_kind="tool_loop",
            configuration={
                "tool_access_mode": access_mode,
                "max_tool_calls": 2,
            },
        )


def test_tool_loop_execute_access_mode_reaches_the_bounded_driver(tmp_path: Path) -> None:
    with pytest.raises(_DriverReached):
        _run_with_recording_driver(
            tmp_path=tmp_path,
            adapter_kind="tool_loop",
            configuration={
                "tool_access_mode": "execute",
                "max_tool_calls": 2,
            },
        )


@pytest.mark.parametrize("adapter_kind", ["direct", "rlm", "lambda_rlm"])
def test_adapters_without_task_tool_control_reject_tool_limits(
    tmp_path: Path,
    adapter_kind: str,
) -> None:
    with pytest.raises(RuntimeError, match="does not support lowered task-tool controls"):
        _run_with_recording_driver(
            tmp_path=tmp_path,
            adapter_kind=adapter_kind,
            configuration={
                "tool_access_mode": "execute",
                "max_tool_calls": 2,
            },
        )


@pytest.mark.parametrize("field", ["max_turns", "max_tool_calls", "max_context_tokens", "timeout_sec"])
def test_non_positive_runtime_limit_is_rejected_before_driver_execution(
    tmp_path: Path,
    field: str,
) -> None:
    with pytest.raises(ValueError, match=f"{field} must be a positive integer"):
        _run_with_recording_driver(
            tmp_path=tmp_path,
            adapter_kind="tool_loop",
            configuration={field: 0},
        )


def test_legacy_configuration_without_lowered_limits_reaches_driver(tmp_path: Path) -> None:
    with pytest.raises(_DriverReached):
        _run_with_recording_driver(
            tmp_path=tmp_path,
            adapter_kind="direct",
            configuration={"temperature": 0.0},
        )
