# ABOUTME: Tests for the direct single-turn adapter path in aec-bench Python.
# ABOUTME: Covers request translation, transcript capture, and honest completion metadata.

from dataclasses import dataclass

from aec_bench.adapters.base import AdapterFailureKind, AdapterRequest
from aec_bench.adapters.direct import (
    DirectAdapter,
    DirectCompletionRequest,
    DirectCompletionResponse,
    ReplayDirectClient,
)
from aec_bench.adapters.transcript import TranscriptRole
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.contracts.trial_record import AgentReference


@dataclass
class RecordingDirectClient:
    response: DirectCompletionResponse
    last_request: DirectCompletionRequest | None = None

    def complete(self, request: DirectCompletionRequest) -> DirectCompletionResponse:
        self.last_request = request
        return self.response


def test_direct_adapter_executes_single_turn_and_captures_transcript() -> None:
    client = RecordingDirectClient(
        response=DirectCompletionResponse(
            output_text="Final answer in markdown.",
            usage_input_tokens=110,
            usage_output_tokens=55,
        )
    )
    adapter = DirectAdapter(
        adapter_name="direct-test",
        model_name="gpt-5.4",
        client=client,
        aliases={"fast": "gpt-5.4-mini"},
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Solve the task and write /workspace/output.md.",
            system_prompt="You are a precise engineering assistant.",
            output_path="/workspace/output.md",
            output_format="markdown",
            configuration={"temperature": 0.1},
        )
    )

    assert client.last_request is not None
    assert client.last_request.model == "gpt-5.4"
    assert result.adapter_name == "direct-test"
    assert result.resolved_model == "gpt-5.4"
    assert result.configuration_record == {"model": "gpt-5.4", "temperature": 0.1}
    assert result.failure_kind is None
    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.raw_output_text == "Final answer in markdown."
    assert [entry.role for entry in result.transcript] == [
        TranscriptRole.SYSTEM,
        TranscriptRole.USER,
        TranscriptRole.ASSISTANT,
    ]


def test_direct_adapter_reports_provider_failure_honestly() -> None:
    client = RecordingDirectClient(
        response=DirectCompletionResponse(
            output_text="",
            error_message="provider timeout",
        )
    )
    adapter = DirectAdapter(
        adapter_name="direct-test",
        model_name="fast",
        client=client,
        aliases={"fast": "gpt-5.4-mini"},
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Solve the task and write /workspace/output.md.",
            output_path="/workspace/output.md",
            output_format="markdown",
        )
    )

    assert client.last_request is not None
    assert client.last_request.model == "gpt-5.4-mini"
    assert result.configuration_record == {"model": "gpt-5.4-mini"}
    assert result.failure_kind is AdapterFailureKind.PROVIDER_ERROR
    assert result.agent_output.status is AgentOutputStatus.FAILED
    assert result.agent_output.error_message == "provider timeout"
    assert [entry.role for entry in result.transcript] == [TranscriptRole.USER]


def test_direct_adapter_classifies_empty_output() -> None:
    client = RecordingDirectClient(
        response=DirectCompletionResponse(
            output_text="",
        )
    )
    adapter = DirectAdapter(
        adapter_name="direct-test",
        model_name="gpt-5.4",
        client=client,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Solve the task and write /workspace/output.md.",
            output_path="/workspace/output.md",
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.EMPTY
    assert result.failure_kind is AdapterFailureKind.MISSING_OUTPUT


def test_direct_adapter_configuration_record_flows_into_agent_reference() -> None:
    client = RecordingDirectClient(
        response=DirectCompletionResponse(
            output_text="Final answer in markdown.",
        )
    )
    adapter = DirectAdapter(
        adapter_name="direct-test",
        model_name="fast",
        client=client,
        aliases={"fast": "gpt-5.4-mini"},
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Solve the task and write /workspace/output.md.",
            output_path="/workspace/output.md",
            output_format="markdown",
            configuration={"temperature": 0.1},
        )
    )

    reference = AgentReference(
        adapter=result.adapter_name,
        model=result.resolved_model,
        adapter_revision="git-sha-adapter",
        configuration=result.configuration_record,
    )

    assert reference.configuration == {"model": "gpt-5.4-mini", "temperature": 0.1}


def test_direct_adapter_serializes_remote_execution_spec() -> None:
    adapter = DirectAdapter(
        adapter_name="direct-test",
        model_name="fast",
        client=ReplayDirectClient(
            response=DirectCompletionResponse(
                output_text="Final answer in markdown.",
                usage_input_tokens=110,
                usage_output_tokens=55,
            )
        ),
        aliases={"fast": "gpt-5.4-mini"},
    )

    execution = adapter.serialize_execution()

    assert execution.adapter_kind == "direct"
    assert execution.adapter_name == "direct-test"
    assert execution.resolved_model == "gpt-5.4-mini"
    assert execution.payload == {
        "client": {
            "client_kind": "replay",
            "payload": {
                "output_text": "Final answer in markdown.",
                "error_message": None,
                "usage_input_tokens": 110,
                "usage_output_tokens": 55,
                "timed_out": False,
            },
        }
    }
