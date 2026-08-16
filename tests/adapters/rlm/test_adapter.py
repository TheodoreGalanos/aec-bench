# ABOUTME: Integration tests for the RlmAdapter — full REPL loop with replay client.
# ABOUTME: Validates that the adapter integrates engine, metadata, guardrails, and error tracking.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from aec_bench.adapters.base import (
    AdapterCompletionReason,
    AdapterFailureKind,
    AdapterRequest,
    AdapterStopReason,
)
from aec_bench.adapters.rlm.adapter import (
    _GUARDRAIL_FAILURE_KINDS,
    RlmAdapter,
    _build_repl_tool_description,
    _build_system_prompt,
)
from aec_bench.adapters.rlm.client import (
    ReplayRlmClient,
    RlmCompletionResponse,
    RlmMessage,
    ToolCall,
)
from aec_bench.adapters.rlm.config import ExecutionConfig, GuardrailConfig
from aec_bench.contracts.agent_output import AgentOutputStatus
from aec_bench.trajectory.writer import TrajectoryWriter


def _make_adapter(responses: list[RlmCompletionResponse], **kwargs) -> RlmAdapter:
    client = ReplayRlmClient(responses=responses)
    return RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=client,
        guardrails=GuardrailConfig(
            token_budget=100_000,
            max_iterations=kwargs.get("max_iterations", 50),
        ),
    )


def _output_completion_contract(output_path: Path, *required_keys: str) -> dict[str, object]:
    return {
        "schema_version": "aecbench.output-completion-contract.v1",
        "output_path": str(output_path),
        "format": "markdown_final_fenced_json",
        "required_top_level_keys": list(required_keys),
        "require_single_final_json_block": True,
    }


class _RecordingTextClient:
    def __init__(self, responses: list[RlmCompletionResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[list[RlmMessage], str | None]] = []

    def generate(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        temperature: float | None = None,
    ) -> RlmCompletionResponse:
        self.calls.append((list(messages), system_prompt))
        return next(self._responses)


class _RecordingToolClient:
    def __init__(self, responses: list[RlmCompletionResponse]) -> None:
        self._responses = iter(responses)
        self.calls: list[tuple[list[RlmMessage], str | None, str]] = []

    def generate_with_tools(
        self,
        *,
        model: str,
        messages: list[RlmMessage],
        system_prompt: str | None,
        tool_name: str,
        tool_description: str,
        tool_parameters_schema: dict[str, object],
    ) -> RlmCompletionResponse:
        self.calls.append((list(messages), system_prompt, tool_description))
        return next(self._responses)


def test_adapter_executes_code_and_returns_final_answer() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text='```repl\nresult = {"voltage_drop_v": 8.4}\n```',
                input_tokens=500,
                output_tokens=100,
            ),
            RlmCompletionResponse(
                output_text='FINAL\n```json\n{"voltage_drop_v": 8.4}\n```',
                input_tokens=400,
                output_tokens=80,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate the voltage drop."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.adapter_name == "rlm-test"
    assert result.usage_input_tokens == 900
    assert result.usage_output_tokens == 180
    assert result.usage_model_calls == 2
    assert result.turns_used == 2
    assert result.max_turns == 50


def test_adapter_stops_at_iteration_cap() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nx = 1\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="```repl\ny = 2\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ],
        max_iterations=2,
    )
    result = adapter.execute(AdapterRequest(instruction="Do something."))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL


def test_request_max_turns_tightens_rlm_iteration_cap() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nx = 1\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ],
        max_iterations=50,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Do one turn only.",
            configuration={"max_turns": 1},
        )
    )

    assert result.agent_output.status == AgentOutputStatus.PARTIAL
    assert result.usage_input_tokens == 100
    assert result.usage_output_tokens == 50
    assert result.agent_output.error_message == "Iteration cap reached (1/1)"
    assert result.failure_kind is AdapterFailureKind.TURN_LIMIT_REACHED
    assert result.stop_reason is AdapterStopReason.ITERATION_CAP
    assert result.turns_used == 1
    assert result.max_turns == 1


def test_adapter_distinguishes_token_budget_from_iteration_cap() -> None:
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text="```repl\nx = 1\n```",
                    input_tokens=80,
                    output_tokens=30,
                )
            ]
        ),
        guardrails=GuardrailConfig(token_budget=100, max_iterations=50),
    )

    result = adapter.execute(AdapterRequest(instruction="Consume the token budget."))

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.TOKEN_BUDGET_REACHED
    assert result.stop_reason is AdapterStopReason.TOKEN_BUDGET
    assert result.turns_used == 1
    assert result.max_turns == 50


@pytest.mark.parametrize(
    ("stop_reason", "failure_kind"),
    (
        (AdapterStopReason.ITERATION_CAP, AdapterFailureKind.TURN_LIMIT_REACHED),
        (AdapterStopReason.TOKEN_BUDGET, AdapterFailureKind.TOKEN_BUDGET_REACHED),
        (AdapterStopReason.SUBCALL_LIMIT, AdapterFailureKind.SUBCALL_LIMIT_REACHED),
        (AdapterStopReason.COST_BUDGET, AdapterFailureKind.COST_BUDGET_REACHED),
        (AdapterStopReason.BILLABLE_INPUT_BUDGET, AdapterFailureKind.BILLABLE_INPUT_BUDGET_REACHED),
    ),
)
def test_adapter_maps_each_guardrail_stop_to_its_exact_failure_kind(
    stop_reason: AdapterStopReason,
    failure_kind: AdapterFailureKind,
) -> None:
    assert _GUARDRAIL_FAILURE_KINDS[stop_reason] is failure_kind


def test_adapter_handles_repl_error_and_continues() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\n1/0\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="```repl\nresult = 42\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate something."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert len(result.transcript) >= 3


def test_adapter_provider_error_retains_actual_and_effective_turn_evidence() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="partial output",
                input_tokens=100,
                output_tokens=50,
                error_message="provider unavailable",
            )
        ],
        max_iterations=7,
    )

    result = adapter.execute(AdapterRequest(instruction="Attempt the task."))

    assert result.agent_output.status is AgentOutputStatus.FAILED
    assert result.failure_kind is AdapterFailureKind.PROVIDER_ERROR
    assert result.stop_reason is None
    assert result.turns_used == 1
    assert result.max_turns == 7


def test_adapter_records_transcript() -> None:
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nx = 1\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n1",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Test."))
    assert len(result.transcript) >= 2


def test_adapter_name_and_model() -> None:
    adapter = _make_adapter([])
    assert adapter.adapter_name() == "rlm-test"
    assert adapter.resolved_model() == "test-model"


def test_adapter_injects_subcalls_into_repl() -> None:
    """Agent can call extract() from REPL code."""
    from aec_bench.adapters.rlm.config import SubcallConfig

    sub_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text='```json\n{"speed": 45}\n```',
                input_tokens=50,
                output_tokens=20,
            ),
        ]
    )
    main_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=('```repl\ndata = extract(text="wind speed is 45", fields=["speed"])\n```'),
                input_tokens=200,
                output_tokens=80,
            ),
            RlmCompletionResponse(
                output_text="FINAL\n45",
                input_tokens=100,
                output_tokens=20,
                done=True,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="main-model",
        client=main_client,
        subcall_client=sub_client,
        subcall_model="sub-model",
        subcall_configs={"extract": SubcallConfig(name="extract", enabled=True)},
    )
    result = adapter.execute(AdapterRequest(instruction="Find wind speed."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.usage_model_calls == 3
    assert result.usage_input_tokens == 350
    assert result.usage_output_tokens == 120


def test_adapter_injects_template_into_repl() -> None:
    """Agent can interact with report template from REPL code."""
    from aec_bench.adapters.rlm.template import ReportTemplate
    from aec_bench.contracts.repl import DependencyTreeSchema, OutputField, TreeSection

    schema = DependencyTreeSchema(
        sections=[
            TreeSection(
                id="intro",
                title="Introduction",
                fields={
                    "summary": OutputField(
                        name="summary",
                        dtype="str",
                        description="Summary",
                    )
                },
                depends_on=[],
            ),
        ]
    )
    template = ReportTemplate(schema)

    main_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text=('```repl\nresult = report.fill_section("intro", {"summary": "Hello"})\n```'),
                input_tokens=200,
                output_tokens=80,
            ),
            RlmCompletionResponse(
                output_text="FINAL\nDone",
                input_tokens=100,
                output_tokens=20,
                done=True,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="main-model",
        client=main_client,
        template=template,
    )
    result = adapter.execute(AdapterRequest(instruction="Fill the template."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert template.get_status().completed_sections == 1


# ---- FINAL_VAR mechanism ----


def test_adapter_final_var_triggers_completion() -> None:
    """Calling FINAL_VAR in REPL should trigger completion."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text='```repl\nresult = FINAL_VAR({"answer": 42})\nprint(result)\n```',
                input_tokens=500,
                output_tokens=100,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute something."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


def test_output_contract_requires_final_var_after_complete_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR("should not be reached")\n```',
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED
    assert result.stop_reason is None
    assert result.failure_kind is None
    assert result.turns_used == 2
    assert result.completion_assistance is not None
    assert result.completion_assistance.contract_satisfied is True
    assert result.completion_assistance.reminder_sent is True
    assert result.completion_assistance.reminder_turn == 1
    assert result.completion_assistance.explicit_final_turn == 2


def test_output_commit_finishes_in_the_same_turn_and_attests_the_exact_artifact(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\nCOMMIT_OUTPUT()\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce and explicitly commit the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
    assert result.completion_assistance is None
    assert result.completion_commit is not None
    assert result.completion_commit.schema_version == "aecbench.output-commit-attestation.v1"
    assert result.completion_commit.mechanism == "agent_explicit_output_commit"
    assert result.completion_commit.output_path == str(output_path)
    assert result.completion_commit.output_sha256 == hashlib.sha256(complete_output.encode()).hexdigest()
    assert result.completion_commit.output_size_bytes == len(complete_output.encode())
    assert result.completion_commit.completion_evaluation.complete is True
    assert result.completion_commit.initial_output_sha256 is None
    assert result.completion_commit.commit_turn == 1
    assert result.failure_kind is None
    assert result.stop_reason is None
    assert result.turns_used == 1


def test_output_commit_rejects_an_unchanged_preexisting_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    initial_output = 'Initial\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    committed_output = 'Reviewed\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    output_path.write_text(initial_output, encoding="utf-8")
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nprint(COMMIT_OUTPUT())\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({committed_output!r})\nprint(COMMIT_OUTPUT())\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Commit only an artifact produced in this run.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.turns_used == 2
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 2
    assert result.completion_commit.output_sha256 == hashlib.sha256(committed_output.encode()).hexdigest()
    first_tool_result = next(
        entry.content for entry in result.transcript if entry.tool_name == "repl" and "unchanged" in entry.content
    )
    assert "COMMIT_OUTPUT rejected: output is unchanged from the start of this run." in first_tool_result


def test_output_commit_revalidates_the_artifact_after_the_repl_block(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    first_output = 'First\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    incomplete_output = 'Mutated\n```json\n{"review_matrix": []}\n```\n'
    final_output = 'Final\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({first_output!r})\n"
                    "COMMIT_OUTPUT()\n"
                    f"open({str(output_path)!r}, 'w').write({incomplete_output!r})\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text=(f"```repl\nopen({str(output_path)!r}, 'w').write({final_output!r})\nCOMMIT_OUTPUT()\n```"),
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Commit the final stable artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.turns_used == 2
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 2
    assert result.completion_commit.output_sha256 == hashlib.sha256(final_output.encode()).hexdigest()
    assert output_path.read_text(encoding="utf-8") == final_output


def test_output_commit_rejected_after_an_earlier_valid_commit_fails_closed(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'First\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    incomplete_output = 'Mutated\n```json\n{"review_matrix": []}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\n"
                    "COMMIT_OUTPUT()\n"
                    f"open({str(output_path)!r}, 'w').write({incomplete_output!r})\n"
                    "COMMIT_OUTPUT()\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
        ],
        max_iterations=1,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Commit only the final stable artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.completion_reason is None
    assert result.completion_commit is None
    assert result.failure_kind is AdapterFailureKind.TURN_LIMIT_REACHED
    assert result.stop_reason is AdapterStopReason.ITERATION_CAP
    assert output_path.read_text(encoding="utf-8") == incomplete_output


def test_output_commit_mode_ignores_final_var_until_the_artifact_is_committed(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\nFINAL_VAR(\"done\")\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="```repl\nCOMMIT_OUTPUT()\n```",
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Commit the artifact through the declared harness primitive.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.turns_used == 2
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
    assert result.completion_assistance is None
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 2


@pytest.mark.parametrize("commit_value", [1, "true", None])
def test_output_commit_configuration_requires_a_boolean_and_contract(
    commit_value: object,
) -> None:
    adapter = _make_adapter([])
    configuration = (
        {"output_completion_commit": True} if commit_value is None else {"output_completion_commit": commit_value}
    )

    with pytest.raises(ValueError, match="output_completion_commit"):
        adapter.execute(
            AdapterRequest(
                instruction="Invalid commit configuration.",
                configuration=configuration,
            )
        )


def test_output_contract_same_turn_write_and_final_is_not_assisted(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\nFINAL_VAR(\"done\")\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.completion_assistance is not None
    assert result.completion_assistance.contract_satisfied is True
    assert result.completion_assistance.reminder_sent is False
    assert result.completion_assistance.reminder_turn is None
    assert result.completion_assistance.explicit_final_turn == 1


def test_output_contract_does_not_accept_preexisting_complete_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    output_path.write_text(complete_output, encoding="utf-8")
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="```repl\nx = 1\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR("done")\n```',
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.turns_used == 2
    assert result.completion_assistance is not None
    assert result.completion_assistance.contract_satisfied is False
    assert result.completion_assistance.reminder_sent is False
    assert result.completion_assistance.reminder_turn is None
    assert result.completion_assistance.explicit_final_turn == 2


def test_output_contract_does_not_read_symlink(tmp_path: Path) -> None:
    target_path = tmp_path / "target.md"
    target_path.write_text('Draft\n```json\n{"review_matrix": []}\n```\n', encoding="utf-8")
    output_path = tmp_path / "output.md"
    output_path.symlink_to(target_path)
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=f"```repl\nopen({str(target_path)!r}, 'w').write({complete_output!r})\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR("done")\n```',
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.turns_used == 2


def test_output_contract_does_not_read_oversized_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    final_block = '\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write('x' * (2 * 1024 * 1024) + {final_block!r})\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR("done")\n```',
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.turns_used == 2


def test_output_contract_does_not_silently_finalize_structural_draft(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    structural_draft = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    reviewed_output = (
        "Drainage review\n```json\n"
        '{"review_matrix": [{"item": "D-01", "status": "hold"}], '
        '"summary": {"decision": "not_ready"}}\n```\n'
    )
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=f"```repl\nopen({str(output_path)!r}, 'w').write({structural_draft!r})\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text="FINAL\nThe artifact exists.",
                input_tokens=100,
                output_tokens=50,
                done=True,
            ),
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({reviewed_output!r})\nFINAL_VAR(\"reviewed\")\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED
    assert result.turns_used == 3
    assert result.completion_assistance is not None
    assert result.completion_assistance.reminder_sent is True
    assert result.completion_assistance.reminder_turn == 1
    assert result.completion_assistance.explicit_final_turn == 3
    assert output_path.read_text(encoding="utf-8") == reviewed_output


def test_output_contract_does_not_stop_for_structurally_incomplete_artifact(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    incomplete_output = 'Draft\n```json\n{"review_matrix": []}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=f"```repl\nopen({str(output_path)!r}, 'w').write({incomplete_output!r})\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR("done")\n```',
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.turns_used == 2


def test_complete_artifact_does_not_change_explicit_final_default(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text=f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\n```",
                input_tokens=100,
                output_tokens=50,
            ),
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR("done")\n```',
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is None
    assert result.turns_used == 2


def test_output_contract_rejects_path_different_from_adapter_request(tmp_path: Path) -> None:
    requested_path = tmp_path / "output.md"
    contract_path = tmp_path / "other.md"
    adapter = _make_adapter([])

    with pytest.raises(ValueError, match="output_path must match"):
        adapter.execute(
            AdapterRequest(
                instruction="Produce the review artifact.",
                configuration={
                    "output_completion_contract": _output_completion_contract(
                        contract_path,
                        "review_matrix",
                    )
                },
                output_path=str(requested_path),
                output_format="markdown",
            )
        )


# ---- Scratchpad integration ----


def test_adapter_scratchpad_note_recall(tmp_path: Path) -> None:
    """NOTE/RECALL should work in REPL when scratchpad is configured."""
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text=('```repl\nNOTE("speed", 45)\nresult = RECALL("speed")\nprint(result)\n```'),
                    input_tokens=300,
                    output_tokens=80,
                ),
                RlmCompletionResponse(
                    output_text="FINAL\n45",
                    input_tokens=200,
                    output_tokens=30,
                    done=True,
                ),
            ]
        ),
        scratchpad_path=str(tmp_path / ".scratchpad.json"),
    )
    result = adapter.execute(AdapterRequest(instruction="Test scratchpad."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Compaction ----


def test_adapter_compaction_resets_conversation(tmp_path: Path) -> None:
    """When input tokens exceed threshold, adapter should compact and continue."""
    trajectory_path = tmp_path / "trajectory.jsonl"
    compaction_client = ReplayRlmClient(
        responses=[
            RlmCompletionResponse(
                output_text="Agent extracted wind speed data and computed results.",
                input_tokens=200,
                output_tokens=50,
            ),
        ]
    )
    main_client = ReplayRlmClient(
        responses=[
            # Turn 1: normal — low tokens
            RlmCompletionResponse(
                output_text="```repl\nx = 42\n```",
                input_tokens=500,
                output_tokens=100,
            ),
            # Turn 2: HIGH tokens — triggers compaction (>85% of 10k limit)
            RlmCompletionResponse(
                output_text="```repl\ny = 99\n```",
                input_tokens=9000,
                output_tokens=200,
            ),
            # Turn 3: after compaction, finish
            RlmCompletionResponse(
                output_text="FINAL\n42",
                input_tokens=500,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=main_client,
        compaction_client=compaction_client,
        trajectory_writer=TrajectoryWriter(path=str(trajectory_path)),
        execution=ExecutionConfig(
            context_limit=10_000,
            compaction_threshold_pct=0.85,
            hard_ceiling_pct=0.95,
        ),
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.usage_model_calls == 4
    assert result.usage_input_tokens == 10_200
    assert result.usage_output_tokens == 400
    entries = [json.loads(line) for line in trajectory_path.read_text(encoding="utf-8").splitlines()]
    compaction_entries = [entry for entry in entries if entry.get("tool_name") == "compaction"]
    assert compaction_entries[0]["metadata"]["compaction"]["number"] == 1


# ---- Hard ceiling ----


def test_adapter_hard_ceiling_forces_partial() -> None:
    """When per-call context exceeds hard ceiling, adapter should stop.

    Set compaction threshold very high (0.99) so the hard ceiling (0.95)
    check fires first.
    """
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=ReplayRlmClient(
            responses=[
                RlmCompletionResponse(
                    output_text="```repl\nx = 1\n```",
                    input_tokens=9600,  # >95% of 10k
                    output_tokens=100,
                ),
            ]
        ),
        execution=ExecutionConfig(
            context_limit=10_000,
            compaction_threshold_pct=0.99,
            hard_ceiling_pct=0.95,
        ),
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL
    assert result.failure_kind is AdapterFailureKind.CONTEXT_LIMIT_REACHED
    assert result.stop_reason is AdapterStopReason.CONTEXT_LIMIT
    assert result.turns_used == 1
    assert result.max_turns == 100


# ---- Protected vars survive agent code ----


def test_adapter_protects_scaffolding_from_overwrite() -> None:
    """Agent code that overwrites FINAL_VAR should be restored."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR = "oops"\n```',
                input_tokens=300,
                output_tokens=80,
            ),
            # FINAL_VAR should still work after restoration
            RlmCompletionResponse(
                output_text='```repl\nresult = FINAL_VAR({"answer": 1})\nprint(result)\n```',
                input_tokens=300,
                output_tokens=80,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Test."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Dynamic HELP ----


def test_help_only_lists_enabled_subcalls() -> None:
    """HELP() should only list sub-calls that are actually enabled."""
    from aec_bench.adapters.rlm.adapter import _make_help

    help_fn = _make_help(
        enabled_subcalls={"extract", "summarise"},
        max_iterations=32,
    )
    output = help_fn()
    assert "32 model turns" in output
    assert "print(HELP())" in output
    assert "extract(" in output
    assert "summarise(" in output
    assert "calculate(" not in output
    assert "verify(" not in output
    assert "retrieve(" not in output
    assert "llm_query(" not in output


def test_help_with_no_optional_capabilities_lists_only_core_commands() -> None:
    """HELP() must not advertise optional commands that were not injected."""
    from aec_bench.adapters.rlm.adapter import _make_help

    help_fn = _make_help(
        enabled_subcalls=set(),
        scratchpad_enabled=False,
        template_enabled=False,
        max_iterations=32,
    )
    output = help_fn()
    assert "print(HELP())" in output
    assert "SHOW_VARS(" in output
    assert "FINAL_VAR(" in output
    assert "parallel(" in output
    assert "NOTE(" not in output
    assert "RECALL(" not in output
    assert "SUB-CALLS" not in output
    assert "fill_parallel(" not in output
    assert "report." not in output


def test_help_lists_scratchpad_and_template_commands_only_when_enabled() -> None:
    """HELP() should expose optional scratchpad and report surfaces when present."""
    from aec_bench.adapters.rlm.adapter import _make_help

    help_fn = _make_help(
        enabled_subcalls=set(),
        scratchpad_enabled=True,
        template_enabled=True,
    )
    output = help_fn()
    assert "NOTE(" in output
    assert "RECALL(" in output
    assert "fill_parallel(" in output
    assert "report.fill_section(" in output


def test_flat_system_prompt_describes_only_the_default_runtime_surface() -> None:
    prompt = _build_system_prompt(
        max_iterations=32,
        scratchpad_enabled=False,
        enabled_subcalls=set(),
        template_enabled=False,
    )

    assert "32 model turns" in prompt
    assert "print(HELP())" in prompt
    assert 'Path("/workspace/sources")' in prompt
    assert "one REPL block" in prompt
    assert "DOCS()" not in prompt
    assert "READ(" not in prompt
    assert "START(" not in prompt
    assert "FILL(" not in prompt
    assert "extract(" not in prompt
    assert "NOTE(" not in prompt
    assert "report." not in prompt


def test_system_prompt_adds_only_enabled_optional_guidance() -> None:
    prompt = _build_system_prompt(
        max_iterations=32,
        scratchpad_enabled=True,
        enabled_subcalls={"extract"},
        template_enabled=True,
    )

    assert "NOTE(" in prompt
    assert "RECALL(" in prompt
    assert "extract(" in prompt
    assert "report.fill_section(" in prompt
    assert "summarise(" not in prompt
    assert "DOCS()" not in prompt
    assert "READ(" not in prompt
    assert "START(" not in prompt
    assert "FILL(" not in prompt


def test_repl_tool_description_matches_the_injected_surface() -> None:
    flat = _build_repl_tool_description(
        max_iterations=32,
        scratchpad_enabled=False,
        enabled_subcalls=set(),
        template_enabled=False,
        output_commit_enabled=True,
    )
    configured = _build_repl_tool_description(
        max_iterations=32,
        scratchpad_enabled=True,
        enabled_subcalls={"extract"},
        template_enabled=True,
        output_commit_enabled=True,
    )

    assert "print(HELP())" in flat
    assert "32 model turns" in flat
    assert "COMMIT_OUTPUT()" in flat
    assert "DOCS()" not in flat
    assert "READ(" not in flat
    assert "extract(" not in flat
    assert "NOTE(" not in flat
    assert "report." not in flat
    assert "NOTE(" in configured
    assert "extract(" in configured
    assert "report.fill_section(" in configured


# ---- Prohibited constraints ----


def test_prohibited_constraints_appear_in_system_prompt() -> None:
    """Prohibited constraints should render as MUST NOT rules in system prompt."""
    from aec_bench.adapters.rlm.adapter import _build_system_prompt

    prompt = _build_system_prompt(
        prohibited=["Skip the codes search sub-call", "Write output from memory"],
    )
    assert "You MUST NOT:" in prompt
    assert "Skip the codes search sub-call" in prompt
    assert "Write output from memory" in prompt


# ---- First-block-only execution (tool_use stop behaviour) ----


def test_adapter_executes_first_block_only_when_multiple() -> None:
    """When model generates multiple ```repl blocks, only the first executes.

    The adapter truncates the response and lets the model re-plan after
    seeing the result — like tool_use stop behaviour.
    """
    adapter = _make_adapter(
        [
            # Turn 1: model generates 3 blocks, only first executes
            RlmCompletionResponse(
                output_text=(
                    "Let me set up the data.\n\n"
                    "```repl\nx = 10\nprint(x)\n```\n\n"
                    "Now compute.\n\n"
                    "```repl\ny = x * 2\n```\n\n"
                    "And store the result.\n\n"
                    "```repl\nresult = x + y\nprint(result)\n```"
                ),
                input_tokens=500,
                output_tokens=200,
            ),
            # Turn 2: model sees x=10 output, continues properly
            RlmCompletionResponse(
                output_text="```repl\ny = x * 2\nprint(y)\n```",
                input_tokens=600,
                output_tokens=50,
            ),
            # Turn 3: finish
            RlmCompletionResponse(
                output_text="FINAL\n20",
                input_tokens=400,
                output_tokens=50,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # First tool result should be from x=10 only (first block)
    tool_entries = [e for e in result.transcript if e.role.value == "tool"]
    assert len(tool_entries) >= 1
    assert "10" in tool_entries[0].content


def test_adapter_multi_block_final_var_not_reached() -> None:
    """FINAL_VAR in a later block is NOT executed — model must re-plan.

    Previously FINAL_VAR (last block) was the only block that ran,
    causing immediate exit with no real work done.
    """
    adapter = _make_adapter(
        [
            # Turn 1: model dumps everything including FINAL_VAR in block 3.
            # Only block 1 (data assignment) executes; FINAL_VAR is discarded.
            RlmCompletionResponse(
                output_text=(
                    "Let me do all the work.\n\n"
                    "```repl\ndata = {'voltage': 230}\n```\n\n"
                    "Store it.\n\n"
                    "```repl\nresult = data['voltage'] * 2\n```\n\n"
                    "Done.\n\n"
                    '```repl\nFINAL_VAR({"answer": result})\n```'
                ),
                input_tokens=500,
                output_tokens=200,
            ),
            # Turn 2: model re-plans, does the multiply
            RlmCompletionResponse(
                output_text="```repl\nresult = data['voltage'] * 2\nprint(result)\n```",
                input_tokens=600,
                output_tokens=50,
            ),
            # Turn 3: model finishes properly
            RlmCompletionResponse(
                output_text='```repl\nFINAL_VAR({"answer": result})\n```',
                input_tokens=400,
                output_tokens=50,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute voltage."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


# ---- Early return interception ----


def test_adapter_intercepts_early_return_on_first_iteration() -> None:
    """If agent tries to FINAL on iteration 0, force a verification step."""
    adapter = _make_adapter(
        [
            # Iteration 0: agent immediately says FINAL — should be intercepted
            RlmCompletionResponse(
                output_text="FINAL\nThe answer is 42",
                input_tokens=500,
                output_tokens=100,
                done=True,
            ),
            # Iteration 1: agent verifies and re-submits — should be accepted
            RlmCompletionResponse(
                output_text="FINAL\nThe verified answer is 42",
                input_tokens=400,
                output_tokens=80,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate something."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    # Should have consumed both responses (intercepted first, accepted second)
    assert result.usage_input_tokens == 900
    assert result.usage_output_tokens == 180


# ---- System prompt identity ----


def test_system_prompt_contains_rlm_identity() -> None:
    """System prompt should frame the REPL as extended cognition, not a tool."""
    from aec_bench.adapters.rlm.adapter import _build_system_prompt

    prompt = _build_system_prompt()
    assert "extended cognition" in prompt.lower() or "how you think" in prompt.lower()
    assert "NO knowledge" in prompt or "no knowledge" in prompt
    assert "hallucination" in prompt.lower()
    assert "read" in prompt.lower() and "extract" in prompt.lower()


def test_system_prompt_no_repl_block_instructions() -> None:
    """Tool_use handles code blocks structurally — no ```repl instructions needed."""
    from aec_bench.adapters.rlm.adapter import _build_system_prompt

    prompt = _build_system_prompt()
    assert "```repl" not in prompt


# ---- Tool-use path ----


def test_adapter_tool_use_completes_with_tool_calls() -> None:
    """Adapter should handle tool_call responses, execute code, and loop."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="Let me check.",
                input_tokens=500,
                output_tokens=100,
                tool_call=ToolCall(name="repl", code="x = 42\nprint(x)", call_id="c1"),
            ),
            RlmCompletionResponse(
                output_text="Done.",
                input_tokens=600,
                output_tokens=80,
                tool_call=ToolCall(name="repl", code='FINAL_VAR({"answer": 42})', call_id="c2"),
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Calculate."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED
    assert result.usage_input_tokens == 1100
    assert result.usage_output_tokens == 180


def test_adapter_tool_use_requires_final_var_after_output_contract_is_satisfied(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="Writing the final review artifact.",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(
                    name="repl",
                    code=f"open({str(output_path)!r}, 'w').write({complete_output!r})",
                    call_id="write-output",
                ),
            ),
            RlmCompletionResponse(
                output_text="Finalizing after reviewing the artifact.",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code='FINAL_VAR("late")', call_id="late-final"),
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                )
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_SATISFIED
    assert result.turns_used == 2
    assert result.completion_assistance is not None
    assert result.completion_assistance.reminder_sent is True
    assert result.completion_assistance.reminder_turn == 1
    assert result.completion_assistance.explicit_final_turn == 2


def test_adapter_tool_use_can_commit_a_complete_output_in_one_turn(tmp_path: Path) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="Writing and committing the final review artifact.",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(
                    name="repl",
                    code=(f"open({str(output_path)!r}, 'w').write({complete_output!r})\nCOMMIT_OUTPUT()"),
                    call_id="write-and-commit",
                ),
            ),
        ]
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce and explicitly commit the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.COMPLETED
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 1


def test_text_path_warns_at_eighty_percent_and_preserves_explicit_commit(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    client = _RecordingTextClient(
        [
            *[
                RlmCompletionResponse(
                    output_text=f"```repl\nstep_{turn} = {turn}\n```",
                    input_tokens=100,
                    output_tokens=50,
                )
                for turn in range(1, 5)
            ],
            RlmCompletionResponse(
                output_text=(
                    f"```repl\nopen({str(output_path)!r}, 'w').write({complete_output!r})\nCOMMIT_OUTPUT()\n```"
                ),
                input_tokens=100,
                output_tokens=50,
            ),
        ]
    )
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=client,
        guardrails=GuardrailConfig(token_budget=100_000, max_iterations=5),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce and explicitly commit the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    messages_before_final_turn = client.calls[4][0]
    warning_context = "\n".join(message.content for message in messages_before_final_turn)
    earlier_context = "\n".join(message.content for call, _ in client.calls[:4] for message in call)
    assert "4/5 model turns consumed (80%)" in warning_context
    assert "1 turn remains" in warning_context
    assert "COMMIT_OUTPUT()" in warning_context
    assert "Iteration budget warning" not in earlier_context
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 5
    assert result.max_turns == 5


def test_tool_path_warns_at_eighty_percent_and_preserves_explicit_commit(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'Drainage review\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    responses = [
        RlmCompletionResponse(
            output_text=f"Working turn {turn}.",
            input_tokens=100,
            output_tokens=50,
            tool_call=ToolCall(
                name="repl",
                code=f"step_{turn} = {turn}",
                call_id=f"step-{turn}",
            ),
        )
        for turn in range(1, 5)
    ]
    responses.append(
        RlmCompletionResponse(
            output_text="Writing and committing the final review artifact.",
            input_tokens=100,
            output_tokens=50,
            tool_call=ToolCall(
                name="repl",
                code=(f"open({str(output_path)!r}, 'w').write({complete_output!r})\nCOMMIT_OUTPUT()"),
                call_id="commit-output",
            ),
        )
    )
    client = _RecordingToolClient(responses)
    adapter = RlmAdapter(
        adapter_name="rlm-test",
        model_name="test-model",
        client=client,
        guardrails=GuardrailConfig(token_budget=100_000, max_iterations=5),
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Produce and explicitly commit the review artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    messages_before_final_turn = client.calls[4][0]
    warning_context = "\n".join(message.content for message in messages_before_final_turn)
    earlier_context = "\n".join(message.content for call, _, _ in client.calls[:4] for message in call)
    assert "4/5 model turns consumed (80%)" in warning_context
    assert "1 turn remains" in warning_context
    assert "COMMIT_OUTPUT()" in warning_context
    assert "Iteration budget warning" not in earlier_context
    assert "DOCS()" not in client.calls[0][2]
    assert "READ(" not in client.calls[0][2]
    assert result.completion_reason is AdapterCompletionReason.OUTPUT_CONTRACT_COMMITTED
    assert result.completion_commit is not None
    assert result.completion_commit.commit_turn == 5
    assert result.max_turns == 5


def test_adapter_tool_use_rejected_after_an_earlier_valid_commit_fails_closed(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "output.md"
    complete_output = 'First\n```json\n{"review_matrix": [], "summary": {}}\n```\n'
    incomplete_output = 'Mutated\n```json\n{"review_matrix": []}\n```\n'
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="Attempting to commit the final review artifact.",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(
                    name="repl",
                    code=(
                        f"open({str(output_path)!r}, 'w').write({complete_output!r})\n"
                        "COMMIT_OUTPUT()\n"
                        f"open({str(output_path)!r}, 'w').write({incomplete_output!r})\n"
                        "COMMIT_OUTPUT()"
                    ),
                    call_id="commit-then-reject",
                ),
            ),
        ],
        max_iterations=1,
    )

    result = adapter.execute(
        AdapterRequest(
            instruction="Commit only the final stable artifact.",
            configuration={
                "output_completion_contract": _output_completion_contract(
                    output_path,
                    "review_matrix",
                    "summary",
                ),
                "output_completion_commit": True,
            },
            output_path=str(output_path),
            output_format="markdown",
        )
    )

    assert result.agent_output.status is AgentOutputStatus.PARTIAL
    assert result.completion_reason is None
    assert result.completion_commit is None
    assert result.failure_kind is AdapterFailureKind.TURN_LIMIT_REACHED
    assert result.stop_reason is AdapterStopReason.ITERATION_CAP
    assert output_path.read_text(encoding="utf-8") == incomplete_output


def test_adapter_tool_use_stops_when_model_done() -> None:
    """When model responds without a tool_call (done=True), adapter completes.

    The first done=True on iteration 1 is intercepted by early-return
    interception (no code executed yet). The second response is accepted.
    """
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="The answer is 42.",
                input_tokens=500,
                output_tokens=100,
                done=True,
            ),
            RlmCompletionResponse(
                output_text="Verified: the answer is 42.",
                input_tokens=400,
                output_tokens=80,
                done=True,
            ),
        ]
    )
    result = adapter.execute(AdapterRequest(instruction="Compute."))
    assert result.agent_output.status == AgentOutputStatus.COMPLETED


def test_adapter_tool_use_guardrails_stop_loop() -> None:
    """Guardrails should stop the tool-use loop."""
    adapter = _make_adapter(
        [
            RlmCompletionResponse(
                output_text="",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code="x = 1", call_id="c1"),
            ),
            RlmCompletionResponse(
                output_text="",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code="y = 2", call_id="c2"),
            ),
            RlmCompletionResponse(
                output_text="",
                input_tokens=100,
                output_tokens=50,
                tool_call=ToolCall(name="repl", code="z = 3", call_id="c3"),
            ),
        ],
        max_iterations=2,
    )
    result = adapter.execute(AdapterRequest(instruction="Do it."))
    assert result.agent_output.status == AgentOutputStatus.PARTIAL
