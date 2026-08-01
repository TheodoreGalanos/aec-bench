# ABOUTME: Tests the provider authority and evidence contract for the ASW-6A-R agent run.
# ABOUTME: Keeps model limits, token accounting, and spend calculation provider-free.

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from aec_bench.contracts.task_definition import ToolSpec
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.harbor_export import (
    export_pump_station_harbor_task,
    load_pump_station_harbor_bridge,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_agent import (
    PumpStationReviewAgentAuthority,
    build_pump_station_review_adapter_request,
    calculate_pump_station_review_spend_microusd,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_harbor import (
    run_pump_station_review_model_session,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.maintenance_review_session import (
    PUMP_STATION_REVIEW_TOOL_NAMES,
)


def _authority(**changes: object) -> PumpStationReviewAgentAuthority:
    values: dict[str, object] = {
        "authorization_id": "asw-6a-r-test-authority",
        "approved_by": "Theo",
        "approved_on": "2026-08-01",
        "provider_id": "test-provider",
        "provider_route": "test-route",
        "model_id": "test-model",
        "adapter_id": "tool_loop",
        "execution_path": "direct_host_session",
        "maximum_provider_calls": 4,
        "maximum_model_turns": 4,
        "maximum_tool_calls": 3,
        "maximum_output_tokens_per_call": 2_048,
        "maximum_total_tokens": 100_000,
        "maximum_estimated_spend_microusd": 1_000_000,
        "input_price_microusd_per_million_tokens": 3_300_000,
        "output_price_microusd_per_million_tokens": 16_500_000,
        "cache_read_price_microusd_per_million_tokens": 330_000,
        "cache_write_price_microusd_per_million_tokens": 4_125_000,
        "spend_currency": "USD",
        "cache_enabled": False,
        "bash_enabled": False,
        "advisor_enabled": False,
        "count_tokens_before_request": False,
    }
    values.update(changes)
    return PumpStationReviewAgentAuthority(**values)  # type: ignore[arg-type]


def test_agent_authority_is_phase_bound_and_cost_calculation_is_exact() -> None:
    authority = _authority()

    spend = calculate_pump_station_review_spend_microusd(
        authority,
        input_tokens=10_000,
        output_tokens=1_000,
        cache_read_tokens=2_000,
        cache_write_tokens=500,
    )

    assert authority.adapter_id == "tool_loop"
    assert authority.execution_path == "direct_host_session"
    assert authority.cache_enabled is False
    assert authority.bash_enabled is False
    assert authority.advisor_enabled is False
    assert authority.count_tokens_before_request is False
    assert spend == 43_973


def test_agent_authority_rejects_unsafe_or_incomplete_values() -> None:
    with pytest.raises(ValidationError, match="Input should be False"):
        _authority(bash_enabled=True)
    with pytest.raises(ValidationError, match="Input should be False"):
        _authority(cache_enabled=True)
    with pytest.raises(ValidationError, match="greater than or equal to 1"):
        _authority(maximum_provider_calls=0)
    with pytest.raises(ValidationError, match="maximum total tokens"):
        _authority(maximum_total_tokens=1_000)
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PumpStationReviewAgentAuthority.model_validate(
            {
                **_authority().model_dump(mode="json"),
                "provider_secret": "must-not-be-serialized",
            }
        )


def test_agent_request_uses_only_review_tools_and_approved_limits() -> None:
    authority = _authority()
    tools = tuple(
        ToolSpec(
            name=name,
            source="builtin",
            description=f"Review action {name}",
        )
        for name in PUMP_STATION_REVIEW_TOOL_NAMES
    )

    request = build_pump_station_review_adapter_request(
        authority,
        tool_specs=tools,
        output_path="/tmp/review-agent-output.md",
    )

    assert tuple(tool.name for tool in request.tools) == (PUMP_STATION_REVIEW_TOOL_NAMES)
    assert request.configuration == {
        "max_turns": 4,
        "max_tool_calls": 3,
        "max_output_tokens_per_call": 2_048,
        "max_total_tokens": 100_000,
        "count_tokens_before_request": False,
    }
    assert request.output_format == "markdown"
    assert request.system_prompt is not None
    assert request.instruction is not None
    assert "submit_closeout_review" in request.system_prompt
    assert "pump-b" not in (request.system_prompt + request.instruction).lower()
    assert "wrong_component_evidence_citation" not in (request.system_prompt + request.instruction)

    with pytest.raises(ValueError, match="review agent tool catalogue differs"):
        build_pump_station_review_adapter_request(
            authority,
            tool_specs=tools[:1],
            output_path="/tmp/review-agent-output.md",
        )


def test_agent_runner_rejects_a_non_review_bridge_before_provider_use(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "ordinary-world-task"
    export_pump_station_harbor_task(
        task_dir,
        project_root=Path(__file__).resolve().parents[4],
    )
    bridge = load_pump_station_harbor_bridge(task_dir / "environment")
    output_dir = tmp_path / "review-agent-output"

    with pytest.raises(
        ValueError,
        match="Harbor bridge does not enable review",
    ):
        run_pump_station_review_model_session(
            bridge=bridge,
            output_dir=output_dir,
            session_identity="must-stop-before-provider",
            authority=_authority(),
        )

    assert not output_dir.exists()
