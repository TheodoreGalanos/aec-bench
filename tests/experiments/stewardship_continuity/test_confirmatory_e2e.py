# ABOUTME: Runs the complete ASW-4C path with the real world and scripted adapter.
# ABOUTME: Proves ordered resume, hidden endpoints, immutable evidence, and reload.

from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from aec_bench.adapters.base import (
    AdapterFailureKind,
    AdapterRequest,
    AdapterResult,
)
from aec_bench.adapters.transcript import initialize_transcript
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.experiments.stewardship_continuity import (
    ContinuityConclusion,
    ContinuityFailureKind,
    ContinuityStudyPhase,
    PairIneligibilityReason,
    calculate_asw4c_spend_microunits,
    confirmatory_execution,
    publish_asw4c_token_measurement_amendment,
    recover_asw4c_interrupted_count_tokens_permission,
    recover_asw4c_interrupted_endpoint_overshoot,
    recover_asw4c_interrupted_provider_fault,
    recover_asw4c_interrupted_token_guard,
    recover_asw4c_interrupted_world_terminal,
    reload_asw4c_confirmatory_result,
    run_asw4c_confirmatory,
)


class _ScriptedConfirmatoryAdapter:
    def __init__(
        self,
        native_tools: list[Any],
        *,
        token_measurement: bool = False,
    ) -> None:
        self._tools = {tool.__name__: tool for tool in native_tools}
        self._token_measurement = token_measurement

    def execute(self, request: AdapterRequest) -> AdapterResult:
        assert request.configuration["max_turns"] == 16
        assert request.configuration["max_tool_calls"] == 32
        if self._token_measurement:
            assert request.configuration["max_input_tokens"] > 40_000
            assert "max_total_tokens" not in request.configuration
            assert request.configuration["count_tokens_before_request"] is False
        else:
            assert request.configuration["max_input_tokens"] == 40_000
            assert request.configuration["max_total_tokens"] == 40_000
            assert request.configuration["count_tokens_before_request"] is False
        assert "evaluation window" not in request.instruction.lower()
        assert "future event" not in request.instruction.lower()
        current = json.loads(self._tools["observe_pump_station"]())
        obligations = current["current_state"]["obligations"]
        if obligations:
            self._tools["request_post_maintenance_verification"](
                "asw-4c-model-proposal-01",
                "Discharge the present independent verification duty.",
                obligations[0]["pump_id"],
            )
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="au.anthropic.claude-sonnet-4-6",
            configuration_record=dict(request.configuration),
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=initialize_transcript(request),
            turns_used=2,
            max_turns=16,
            raw_output_text="Present required follow-up is safely assigned.",
            usage_model_calls=2,
            usage_input_tokens=2_000,
            usage_output_tokens=200,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
            usage_advisor_calls=0,
            usage_advisor_input_tokens=0,
            usage_advisor_output_tokens=0,
            maximum_input_tokens_in_one_call=1_100,
            maximum_output_tokens_in_one_call=120,
        )


class _ScriptedRegistry:
    def __init__(self, *, token_measurement: bool = False) -> None:
        self.build_count = 0
        self._token_measurement = token_measurement

    def build(self, **kwargs: Any) -> _ScriptedConfirmatoryAdapter:
        self.build_count += 1
        assert kwargs["adapter_kind"] == "tool_loop"
        assert kwargs["model_name"] == "au.anthropic.claude-sonnet-4-6"
        assert kwargs["enable_bash"] is False
        assert kwargs["cache"] is False
        return _ScriptedConfirmatoryAdapter(
            kwargs["native_tools"],
            token_measurement=self._token_measurement,
        )


def test_token_measurement_spend_guard_fits_remaining_phase_authority() -> None:
    remaining_spend_microunits = 26_274_635

    maximum_input_tokens = confirmatory_execution._spend_guard_input_token_limit(
        remaining_spend_microunits,
    )
    maximum_input_tokens_after_one_response = maximum_input_tokens + 500_000
    reserved_output_tokens = 16 * 2_048

    assert maximum_input_tokens > 40_000
    assert (
        calculate_asw4c_spend_microunits(
            input_tokens=maximum_input_tokens_after_one_response,
            output_tokens=reserved_output_tokens,
        )
        <= remaining_spend_microunits
    )
    assert (
        calculate_asw4c_spend_microunits(
            input_tokens=maximum_input_tokens_after_one_response + 1,
            output_tokens=reserved_output_tokens,
        )
        > remaining_spend_microunits
    )


class _ExpiredCredentialAdapter:
    def execute(self, request: AdapterRequest) -> AdapterResult:
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="au.anthropic.claude-sonnet-4-6",
            configuration_record=dict(request.configuration),
            agent_output=AgentOutput(
                status=AgentOutputStatus.FAILED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=initialize_transcript(request),
            failure_kind=AdapterFailureKind.PROVIDER_ERROR,
            max_turns=16,
            raw_output_text="",
            provider_error=(
                "status_code: 403; ExpiredTokenException; the security token included in the request is expired"
            ),
        )


class _ExpiredCredentialRegistry:
    def __init__(self) -> None:
        self.build_count = 0

    def build(self, **kwargs: Any) -> _ExpiredCredentialAdapter:
        self.build_count += 1
        return _ExpiredCredentialAdapter()


class _CountTokensPermissionAdapter:
    def execute(self, request: AdapterRequest) -> AdapterResult:
        configuration_record = dict(request.configuration)
        configuration_record["count_tokens_before_request"] = True
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="au.anthropic.claude-sonnet-4-6",
            configuration_record=configuration_record,
            agent_output=AgentOutput(
                status=AgentOutputStatus.FAILED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=initialize_transcript(request),
            failure_kind=AdapterFailureKind.PROVIDER_ERROR,
            max_turns=16,
            raw_output_text="",
            provider_error=("status_code: 403; AccessDeniedException; not authorized to perform: bedrock:CountTokens"),
            usage_input_tokens=0,
            usage_output_tokens=0,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
        )


class _CountTokensPermissionRegistry:
    def __init__(self) -> None:
        self.build_count = 0

    def build(self, **kwargs: Any) -> _CountTokensPermissionAdapter:
        self.build_count += 1
        return _CountTokensPermissionAdapter()


class _TokenGuardAdapter:
    def __init__(self, native_tools: list[Any]) -> None:
        self._tools = {tool.__name__: tool for tool in native_tools}

    def execute(self, request: AdapterRequest) -> AdapterResult:
        self._tools["transfer_duty"](
            "asw-4c-token-guard-proposal",
            "Create one durable action before the measured token stop.",
        )
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="au.anthropic.claude-sonnet-4-6",
            configuration_record=dict(request.configuration),
            agent_output=AgentOutput(
                status=AgentOutputStatus.FAILED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=initialize_transcript(request),
            failure_kind=AdapterFailureKind.TOKEN_BUDGET_REACHED,
            turns_used=7,
            max_turns=16,
            raw_output_text="",
            usage_model_calls=7,
            usage_input_tokens=44_223,
            usage_output_tokens=2_820,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
        )


class _TokenGuardRegistry:
    def __init__(self) -> None:
        self.build_count = 0

    def build(self, **kwargs: Any) -> _TokenGuardAdapter:
        self.build_count += 1
        return _TokenGuardAdapter(kwargs["native_tools"])


class _WorldTerminalAdapter:
    def __init__(
        self,
        native_tools: list[Any],
        trajectory_writer: Any,
    ) -> None:
        self._tools = {tool.__name__: tool for tool in native_tools}
        self._trajectory = trajectory_writer

    def execute(self, request: AdapterRequest) -> AdapterResult:
        arguments = {
            "proposal_id": "asw-4c-model-deferral",
            "reason": "Create the declared transfer-then-isolate restriction.",
            "pump_id": "pump-b",
        }
        self._trajectory.new_step()
        self._trajectory.tool_call(
            "request_conditional_deferral",
            "",
            arguments,
        )
        result = self._tools["request_conditional_deferral"](**arguments)
        self._trajectory.tool_result(
            "request_conditional_deferral",
            result,
        )
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="au.anthropic.claude-sonnet-4-6",
            configuration_record=dict(request.configuration),
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=initialize_transcript(request),
            turns_used=2,
            max_turns=16,
            raw_output_text="The deferral is recorded.",
            usage_model_calls=2,
            usage_input_tokens=2_000,
            usage_output_tokens=200,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
            usage_advisor_calls=0,
            usage_advisor_input_tokens=0,
            usage_advisor_output_tokens=0,
            maximum_input_tokens_in_one_call=1_100,
            maximum_output_tokens_in_one_call=120,
        )


class _WorldTerminalRegistry:
    def __init__(self) -> None:
        self.build_count = 0

    def build(self, **kwargs: Any) -> Any:
        self.build_count += 1
        if self.build_count == 1:
            return _ScriptedConfirmatoryAdapter(kwargs["native_tools"])
        return _WorldTerminalAdapter(
            kwargs["native_tools"],
            kwargs["trajectory_writer"],
        )


class _EndpointOvershootAdapter:
    def __init__(
        self,
        native_tools: list[Any],
        trajectory_writer: Any,
    ) -> None:
        self._tools = {tool.__name__: tool for tool in native_tools}
        self._trajectory = trajectory_writer

    def _call(self, name: str, arguments: dict[str, str]) -> None:
        self._trajectory.new_step()
        self._trajectory.tool_call(name, "", arguments)
        result = self._tools[name](**arguments)
        self._trajectory.tool_result(name, result)

    def execute(self, request: AdapterRequest) -> AdapterResult:
        self._call(
            "continue_operation",
            {
                "proposal_id": "asw-4c-reach-endpoint",
                "reason": "Continue to the next declared station event.",
            },
        )
        self._call(
            "request_inspection",
            {
                "proposal_id": "asw-4c-after-endpoint-inspection",
                "reason": "Request one inspection at the present station time.",
                "pump_id": "pump-b",
            },
        )
        self._call(
            "continue_operation",
            {
                "proposal_id": "asw-4c-pass-endpoint",
                "reason": "Continue to the scheduled inspection completion.",
            },
        )
        return AdapterResult(
            adapter_name="tool_loop",
            resolved_model="au.anthropic.claude-sonnet-4-6",
            configuration_record=dict(request.configuration),
            agent_output=AgentOutput(
                status=AgentOutputStatus.COMPLETED,
                output_path=request.output_path,
                output_format=request.output_format,
            ),
            transcript=initialize_transcript(request),
            turns_used=4,
            max_turns=16,
            raw_output_text="The inspection completed.",
            usage_model_calls=4,
            usage_input_tokens=5_000,
            usage_output_tokens=500,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
            usage_advisor_calls=0,
            usage_advisor_input_tokens=0,
            usage_advisor_output_tokens=0,
            maximum_input_tokens_in_one_call=1_500,
            maximum_output_tokens_in_one_call=150,
        )


class _EndpointOvershootRegistry:
    def build(self, **kwargs: Any) -> _EndpointOvershootAdapter:
        return _EndpointOvershootAdapter(
            kwargs["native_tools"],
            kwargs["trajectory_writer"],
        )


class _ConcurrencyProbeSession:
    def __init__(self) -> None:
        self._guard = threading.Lock()
        self.active_count = 0
        self.maximum_active_count = 0

    def _mutate(self) -> str:
        with self._guard:
            self.active_count += 1
            self.maximum_active_count = max(
                self.maximum_active_count,
                self.active_count,
            )
        time.sleep(0.05)
        with self._guard:
            self.active_count -= 1
        return "{}"

    def transfer_duty(self, _proposal_id: str, _reason: str) -> str:
        return self._mutate()

    def request_inspection(
        self,
        _proposal_id: str,
        _reason: str,
        _pump_id: str,
    ) -> str:
        return self._mutate()


def test_asw4c_executes_all_frozen_trials_once_and_resumes_in_order(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4c"
    registry = _ScriptedRegistry()

    paused = run_asw4c_confirmatory(
        root,
        authorization_id="asw-4c-test-approval",
        approved_by="Theo",
        registry=registry,
        maximum_new_trials=1,
    )
    completed = run_asw4c_confirmatory(
        root,
        authorization_id="asw-4c-test-approval",
        approved_by="Theo",
        registry=registry,
    )
    reloaded = reload_asw4c_confirmatory_result(root)

    assert paused.completed_trial_count == 1
    assert paused.report is None
    assert not paused.complete
    assert completed.complete
    assert completed.completed_trial_count == 64
    assert completed.report is not None
    assert reloaded.report == completed.report
    assert registry.build_count == 64
    assert completed.report.phase is ContinuityStudyPhase.CONFIRMATORY
    assert completed.report.conclusion is ContinuityConclusion.INCONCLUSIVE
    assert completed.report.coverage.exact
    assert completed.report.coverage.analyzable_block_count == 32
    assert completed.report.provider_call_count == 128
    assert completed.report.input_token_count == 128_000
    assert completed.report.output_token_count == 12_800
    assert completed.report.spend_microunits == (
        64
        * calculate_asw4c_spend_microunits(
            input_tokens=2_000,
            output_tokens=200,
        )
    )
    assert completed.report.study_outcome_count == 64
    assert completed.report.task_reward_mutation_count == 0
    assert completed.report.point_estimate == 0.0
    assert all(observation.continuity_failure is False for observation in completed.observations)
    assert all(execution.world_verification_valid for execution in completed.executions)
    assert all(execution.secret_scan_passed for execution in completed.executions)


def test_asw4c_tool_budget_serializes_parallel_station_mutations() -> None:
    session = _ConcurrencyProbeSession()
    budget = confirmatory_execution._Asw4cToolBudget(session)

    with ThreadPoolExecutor(max_workers=2) as executor:
        transfer = executor.submit(
            budget.transfer_duty,
            "parallel-transfer",
            "Test one parallel station mutation.",
        )
        inspection = executor.submit(
            budget.request_inspection,
            "parallel-inspection",
            "Test another parallel station mutation.",
            "pump-a",
        )
        transfer.result()
        inspection.result()

    assert session.maximum_active_count == 1
    assert budget.host_command_count == 2
    assert budget.agent_proposal_count == 2


def test_asw4c_recovers_expired_host_credentials_without_repeating_the_trial(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4c"
    expired_registry = _ExpiredCredentialRegistry()

    with pytest.raises(ValueError, match="provider usage is incomplete"):
        run_asw4c_confirmatory(
            root,
            authorization_id="asw-4c-test-approval",
            approved_by="Theo",
            registry=expired_registry,
            maximum_new_trials=1,
        )

    recovered = recover_asw4c_interrupted_provider_fault(root)
    first_completion_sha256 = recovered.completions[0].content_sha256
    resumed_registry = _ScriptedRegistry()
    resumed = run_asw4c_confirmatory(
        root,
        authorization_id="asw-4c-test-approval",
        approved_by="Theo",
        registry=resumed_registry,
        maximum_new_trials=1,
    )

    assert recovered.completed_trial_count == 1
    assert not recovered.complete
    assert recovered.report is None
    assert expired_registry.build_count == 1
    assert resumed.completed_trial_count == 2
    assert resumed_registry.build_count == 1
    assert resumed.completions[0].content_sha256 == first_completion_sha256
    assert recovered.observations[0].failure_kind is ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY
    assert recovered.observations[0].ineligibility_reason is PairIneligibilityReason.HOST_FAILURE
    assert not recovered.observations[0].study_outcome_eligible
    assert recovered.observations[0].provider_call_count == 1
    assert recovered.observations[0].input_token_count == 0
    assert recovered.observations[0].output_token_count == 0
    assert recovered.observations[0].spend_microunits == 0


def test_asw4c_recovers_count_tokens_permission_without_model_inference(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4c"
    registry = _CountTokensPermissionRegistry()

    with pytest.raises(ValueError, match="provider usage is incomplete"):
        run_asw4c_confirmatory(
            root,
            authorization_id="asw-4c-test-approval",
            approved_by="Theo",
            registry=registry,
            maximum_new_trials=1,
        )

    recovered = recover_asw4c_interrupted_count_tokens_permission(root)

    assert registry.build_count == 1
    assert recovered.completed_trial_count == 1
    assert recovered.observations[0].failure_kind is ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY
    assert recovered.observations[0].ineligibility_reason is PairIneligibilityReason.HOST_FAILURE
    assert recovered.observations[0].provider_call_count == 1
    assert recovered.observations[0].input_token_count == 0
    assert recovered.observations[0].output_token_count == 0
    assert recovered.observations[0].spend_microunits == 0


def test_asw4c_measures_tokens_and_recovers_the_initial_token_guard(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4c"
    token_guard_registry = _TokenGuardRegistry()

    with pytest.raises(ValueError, match="provider usage is incomplete"):
        run_asw4c_confirmatory(
            root,
            authorization_id="asw-4c-test-approval",
            approved_by="Theo",
            registry=token_guard_registry,
            maximum_new_trials=1,
        )

    amendment = publish_asw4c_token_measurement_amendment(
        root,
        authorization_id="asw-4c-test-token-measurement",
        approved_by="Theo",
    )
    recovered = recover_asw4c_interrupted_token_guard(root)
    first_completion_sha256 = recovered.completions[0].content_sha256
    resumed_registry = _ScriptedRegistry(token_measurement=True)
    resumed = run_asw4c_confirmatory(
        root,
        authorization_id="asw-4c-test-approval",
        approved_by="Theo",
        registry=resumed_registry,
        maximum_new_trials=1,
    )

    assert amendment.tokens_are_measurements
    assert amendment.hard_provider_call_limit == 1_024
    assert amendment.hard_spend_microunits == 37_000_000
    assert amendment.cumulative_provider_calls_before == 7
    assert amendment.cumulative_input_tokens_before == 44_223
    assert amendment.cumulative_output_tokens_before == 2_820
    assert token_guard_registry.build_count == 1
    assert recovered.completed_trial_count == 1
    assert resumed.completed_trial_count == 2
    assert resumed_registry.build_count == 1
    assert resumed.completions[0].content_sha256 == first_completion_sha256
    assert recovered.observations[0].failure_kind is ContinuityFailureKind.HOST_FAILURE_AFTER_DELIVERY
    assert recovered.observations[0].ineligibility_reason is PairIneligibilityReason.HOST_FAILURE
    assert recovered.observations[0].provider_call_count == 7
    assert recovered.observations[0].input_token_count == 44_223
    assert recovered.observations[0].output_token_count == 2_820
    assert recovered.observations[0].spend_microunits == (
        calculate_asw4c_spend_microunits(
            input_tokens=44_223,
            output_tokens=2_820,
        )
    )


def test_asw4c_recovers_a_world_owned_early_terminal_without_repeating(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "asw-4c"
    registry = _WorldTerminalRegistry()
    advance = confirmatory_execution.advance_asw4c_to_evaluation_end

    def interrupt_after_terminal(prepared: Any) -> None:
        advance(prepared)
        if prepared.session.actor_view.current_state.calendar_seconds < prepared.evaluation_end_seconds:
            raise ValueError("simulated process interruption after early terminal")

    monkeypatch.setattr(
        confirmatory_execution,
        "advance_asw4c_to_evaluation_end",
        interrupt_after_terminal,
    )
    with pytest.raises(
        ValueError,
        match="simulated process interruption after early terminal",
    ):
        run_asw4c_confirmatory(
            root,
            authorization_id="asw-4c-test-approval",
            approved_by="Theo",
            registry=registry,
            maximum_new_trials=2,
        )
    monkeypatch.setattr(
        confirmatory_execution,
        "advance_asw4c_to_evaluation_end",
        advance,
    )

    recovered = recover_asw4c_interrupted_world_terminal(root)

    observation = recovered.observations[-1]
    execution = recovered.executions[-1]
    assert registry.build_count == 2
    assert recovered.completed_trial_count == 2
    assert observation.failure_kind is ContinuityFailureKind.NONE
    assert observation.continuity_failure is True
    assert observation.ineligibility_reason is None
    assert observation.study_outcome_eligible
    assert observation.provider_call_count == 2
    assert observation.input_token_count == 2_000
    assert observation.output_token_count == 200
    assert execution.host_command_count == 1
    assert execution.agent_proposal_count == 1
    assert execution.endpoint_host_advancement_count == 1


def test_asw4c_recovers_exact_prefix_after_agent_passes_endpoint(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4c"

    with pytest.raises(
        ValueError,
        match="station did not reach the frozen endpoint",
    ):
        run_asw4c_confirmatory(
            root,
            authorization_id="asw-4c-test-approval",
            approved_by="Theo",
            registry=_EndpointOvershootRegistry(),
            maximum_new_trials=1,
        )

    recovered = recover_asw4c_interrupted_endpoint_overshoot(root)

    observation = recovered.observations[0]
    execution = recovered.executions[0]
    assert recovered.completed_trial_count == 1
    assert observation.failure_kind is ContinuityFailureKind.NONE
    assert observation.continuity_failure is False
    assert observation.ineligibility_reason is None
    assert observation.study_outcome_eligible
    assert execution.endpoint_state_sha256 != execution.final_state_sha256
    assert execution.endpoint_host_advancement_count == 0
