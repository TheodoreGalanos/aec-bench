# ABOUTME: Maps one upstream Prime Agent JSON-mode process run into the existing local AdapterResult contract.
# ABOUTME: Leaves task staging, output handling, verification, evaluation, and trial import with current owners.

from __future__ import annotations

from pathlib import Path

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest, AdapterResult
from aec_bench.adapters.transcript import initialize_transcript
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.prime_agent.batch import PrimeExecutableNotFoundError, PrimeRun, run_prime_agent


class PrimeAgentAdapter:
    """Process-backed adapter for an explicitly selected Prime Agent executable."""

    def __init__(
        self,
        *,
        model_name: str,
        workspace: str | Path,
        executable: str = "prime-agent",
    ) -> None:
        self._requested_model = model_name
        self._workspace = Path(workspace).resolve()
        self._executable = executable

    def execute(self, request: AdapterRequest) -> AdapterResult:
        timeout_seconds = _timeout_seconds(request)
        try:
            run = run_prime_agent(
                workspace=self._workspace,
                instruction=request.instruction,
                model=self._requested_model,
                timeout_seconds=timeout_seconds,
                executable=self._executable,
            )
        except PrimeExecutableNotFoundError as exc:
            return _missing_executable_result(request, requested_model=self._requested_model, error=str(exc))

        events = run.events
        resolved_model = (
            events.resolved_model if events is not None and events.resolved_model is not None else self._requested_model
        )
        transcript = initialize_transcript(request)
        if events is not None:
            transcript.extend(events.transcript)

        direct_output = _has_direct_output(self._workspace)
        raw_output_text = (
            events.final_assistant_text
            if run.completion == "completed" and not direct_output and events is not None
            else None
        )
        status = _status(run)
        failure_kind = _failure_kind(run)
        configuration_record: dict[str, object] = {
            "model": resolved_model,
            "prime_version": run.prime_version,
            "event_stream_version": events.stream_version if events is not None else None,
            "session_id": events.session_id if events is not None else None,
            "state_isolated": True,
            "ambient_resources_disabled": True,
        }

        return AdapterResult(
            adapter_name="prime-agent",
            resolved_model=resolved_model,
            configuration_record=configuration_record,
            agent_output=AgentOutput(
                status=status,
                output_path=request.output_path,
                output_format=request.output_format,
                error_message=run.error,
            ),
            transcript=transcript,
            failure_kind=failure_kind,
            turns_used=events.turn_count if events is not None else None,
            raw_output_text=raw_output_text,
            provider_error=run.error if failure_kind is not None else None,
            usage_model_calls=events.usage_model_calls if events is not None else None,
            usage_input_tokens=events.usage_input_tokens if events is not None else None,
            usage_output_tokens=events.usage_output_tokens if events is not None else None,
            usage_cache_read_tokens=events.usage_cache_read_tokens if events is not None else None,
            usage_cache_write_tokens=events.usage_cache_write_tokens if events is not None else None,
        )

    def adapter_name(self) -> str:
        return "prime-agent"

    def resolved_model(self) -> str:
        return self._requested_model


def _timeout_seconds(request: AdapterRequest) -> float:
    value = request.configuration.get("timeout_seconds", 1800)
    if isinstance(value, bool) or not isinstance(value, int | float) or value <= 0:
        raise ValueError("Prime Agent timeout_seconds must be a positive number")
    return float(value)


def _has_direct_output(workspace: Path) -> bool:
    output_path = workspace / "output.md"
    return output_path.is_file() and bool(output_path.read_text(encoding="utf-8", errors="replace").strip())


def _status(run: PrimeRun) -> AgentOutputStatus:
    if run.completion == "completed":
        return AgentOutputStatus.COMPLETED
    if run.completion == "missing_output":
        return AgentOutputStatus.EMPTY
    return AgentOutputStatus.FAILED


def _failure_kind(run: PrimeRun) -> AdapterFailureKind | None:
    if run.completion == "completed":
        return None
    if run.completion == "timed_out":
        return AdapterFailureKind.TIMEOUT
    if run.completion == "missing_output":
        return AdapterFailureKind.MISSING_OUTPUT
    return AdapterFailureKind.PROVIDER_ERROR


def _missing_executable_result(request: AdapterRequest, *, requested_model: str, error: str) -> AdapterResult:
    return AdapterResult(
        adapter_name="prime-agent",
        resolved_model=requested_model,
        configuration_record={
            "model": requested_model,
            "prime_version": None,
            "event_stream_version": None,
            "session_id": None,
            "state_isolated": True,
            "ambient_resources_disabled": True,
        },
        agent_output=AgentOutput(
            status=AgentOutputStatus.FAILED,
            output_path=request.output_path,
            output_format=request.output_format,
            error_message=error,
        ),
        transcript=initialize_transcript(request),
        failure_kind=AdapterFailureKind.PROVIDER_ERROR,
        provider_error=error,
    )
