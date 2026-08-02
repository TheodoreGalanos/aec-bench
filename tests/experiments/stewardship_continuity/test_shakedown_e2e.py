# ABOUTME: Runs the complete shakedown path with a test-only scripted model adapter.
# ABOUTME: Proves real tools, budgets, immutable evidence, and reload without network use.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.adapters.transcript import initialize_transcript
from aec_bench.contracts.agent_output import AgentOutput, AgentOutputStatus
from aec_bench.experiments.stewardship_continuity import (
    ContinuityConclusion,
    ContinuityStudyPhase,
    ContinuityTreatment,
    calculate_asw4b_spend_microunits,
    reload_and_verify_study_report,
    run_asw4b_shakedown,
)


class _ScriptedStewardAdapter:
    def __init__(self, native_tools: list[Any]) -> None:
        self._tools = {tool.__name__: tool for tool in native_tools}

    def execute(self, request: AdapterRequest) -> AdapterResult:
        assert request.configuration["max_turns"] == 15
        assert request.configuration["count_tokens_before_request"] is False
        current = json.loads(self._tools["observe_pump_station"]())
        obligation = current["current_state"]["obligations"][0]
        pump_id = obligation["pump_id"]
        self._tools["request_post_maintenance_verification"](
            "asw-4b-model-proposal-01",
            "Complete the carried independent verification duty.",
            pump_id,
        )
        self._tools["continue_operation"](
            "asw-4b-model-proposal-02",
            "Continue to the next declared station event.",
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
            turns_used=3,
            max_turns=16,
            raw_output_text="The verification duty is complete.",
            usage_model_calls=3,
            usage_input_tokens=6_000,
            usage_output_tokens=450,
            usage_cache_read_tokens=0,
            usage_cache_write_tokens=0,
            usage_advisor_calls=0,
            usage_advisor_input_tokens=0,
            usage_advisor_output_tokens=0,
            maximum_input_tokens_in_one_call=2_500,
            maximum_output_tokens_in_one_call=200,
        )


class _ScriptedRegistry:
    def build(self, **kwargs: Any) -> _ScriptedStewardAdapter:
        assert kwargs["adapter_kind"] == "tool_loop"
        assert kwargs["model_name"] == "au.anthropic.claude-sonnet-4-6"
        assert kwargs["enable_bash"] is False
        assert kwargs["cache"] is False
        return _ScriptedStewardAdapter(kwargs["native_tools"])


def test_shakedown_publishes_ineligible_verified_evidence(
    tmp_path: Path,
) -> None:
    root = tmp_path / "asw-4b"
    published = run_asw4b_shakedown(
        root,
        registry=_ScriptedRegistry(),
        prior_provider_call_count=1,
    )
    replayed = reload_and_verify_study_report(
        root=root,
        report_content_sha256=published.report.content_sha256,
    )

    assert replayed == published.report
    assert replayed.phase is ContinuityStudyPhase.SHAKEDOWN
    assert replayed.conclusion is ContinuityConclusion.SHAKEDOWN
    assert replayed.fixture_rule_result is None
    assert replayed.coverage.observed_trial_count == 1
    assert replayed.provider_call_count == 4
    assert replayed.input_token_count == 6_000
    assert replayed.output_token_count == 450
    assert replayed.maximum_input_tokens_in_one_call == 2_500
    assert replayed.maximum_output_tokens_in_one_call == 200
    assert replayed.spend_microunits == calculate_asw4b_spend_microunits(
        input_tokens=6_000,
        output_tokens=450,
    )
    assert replayed.study_outcome_count == 0
    assert replayed.task_reward_mutation_count == 0
    assert published.trial.treatment is ContinuityTreatment.STRUCTURED_HANDOVER
    assert published.execution.fresh_agent_handovers == 1
    assert published.execution.preflight_provider_call_count == 1
    assert published.execution.trajectory_provider_call_count == 3
    assert published.execution.host_command_count == 3
    assert published.execution.agent_proposal_count == 2
    assert published.execution.cache_enabled is False
    assert published.execution.bash_enabled is False
    assert published.execution.advisor_enabled is False
    assert published.execution.cache_read_tokens == 0
    assert published.execution.cache_write_tokens == 0
    assert published.execution.advisor_call_count == 0
    assert published.execution.world_verification_valid
    assert published.execution.final_open_obligation_count == 0
    assert published.execution.final_active_restriction_count == 1
    assert published.execution.secret_scan_passed
    assert published.execution_reference.path.is_file()
    assert published.report_reference.path.is_file()
