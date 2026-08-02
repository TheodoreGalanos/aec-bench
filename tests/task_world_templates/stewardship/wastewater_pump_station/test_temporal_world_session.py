# ABOUTME: Tests temporal search and fetch through the real durable pump-station session.
# ABOUTME: Proves conditional tools, information binding, retry, and physical-state separation.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from aec_bench.contracts.world_interface import WorldActorActionRequest, WorldInterfaceError
from aec_bench.contracts.world_session import (
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_views import (
    create_structured_handover,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.temporal_evidence import (
    TemporalEvidenceAccessStatus,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_session import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationWorldSessionFactory,
)


def _start_request(*, identity: str) -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id=f"session-{identity}",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id=f"tenure-{identity}",
        run_id=f"run-{identity}",
        episode_id=f"episode-{identity}",
        world_branch_id=f"branch-{identity}",
    )


def test_temporal_tools_are_present_only_for_an_enabled_world(tmp_path: Path) -> None:
    enabled = PumpStationWorldSessionFactory(
        tmp_path / "enabled",
        temporal_evidence=True,
    ).open(_start_request(identity="enabled"))
    disabled = PumpStationWorldSessionFactory(tmp_path / "disabled").open(
        _start_request(identity="disabled")
    )

    assert {"search_evidence", "fetch_evidence"}.issubset(enabled.result.tool_names)
    assert {"search_evidence", "fetch_evidence"}.issubset(
        item.name for item in enabled.actor_capabilities.actions
    )
    assert "temporal-evidence" in {path.name for path in (tmp_path / "enabled").iterdir()}
    assert "search_evidence" not in disabled.result.tool_names
    assert "fetch_evidence" not in disabled.result.tool_names
    assert not (tmp_path / "disabled" / "temporal-evidence").exists()


def test_search_fetch_retry_and_actor_binding_do_not_change_world_state(
    tmp_path: Path,
) -> None:
    root = tmp_path / "world"
    start = _start_request(identity="temporal")
    session = PumpStationWorldSessionFactory(
        root,
        temporal_evidence=True,
    ).open(start)
    initial_snapshot = session.result.snapshot
    initial_state = session.run.state
    initial_information_set_id = session.result.information_set_id

    searched_payload = cast(
        dict[str, Any],
        json.loads(
            session.search_evidence(
                request_id="search-maintenance",
                query="pump obstruction procedure",
                scope="procedures",
                limit=5,
            )
        ),
    )
    searched = searched_payload["receipt"]
    reference = searched["references"][0]["opaque_reference"]

    assert searched["public_status"] == TemporalEvidenceAccessStatus.OK.value
    assert session.result.snapshot == initial_snapshot
    assert session.run.state == initial_state
    assert session.result.information_set_id != initial_information_set_id
    after_search_information_set_id = session.result.information_set_id

    resume = WorldSessionRequest(
        execution_kind=start.execution_kind,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id=start.session_id,
        task_world_id=start.task_world_id,
        agent_tenure_id=start.agent_tenure_id,
        run_id=start.run_id,
        episode_id=start.episode_id,
        world_branch_id=start.world_branch_id,
        start_snapshot=initial_snapshot,
    )
    restarted = PumpStationWorldSessionFactory(root).open(resume)
    repeated = cast(
        dict[str, Any],
        json.loads(
            restarted.search_evidence(
                request_id="search-maintenance",
                query="pump obstruction procedure",
                scope="procedures",
                limit=5,
            )
        ),
    )

    assert restarted.result.information_set_id == after_search_information_set_id
    assert repeated["receipt"] == searched
    assert restarted.result.snapshot == initial_snapshot

    fetched = restarted.invoke_actor_action(
        WorldActorActionRequest(
            request_id="fetch-maintenance",
            action_name="fetch_evidence",
            binding=restarted.current_actor_binding,
            arguments={"reference": reference},
        )
    )

    assert fetched.status == TemporalEvidenceAccessStatus.OK.value
    fetched_receipt = cast(dict[str, Any], fetched.task_receipt)
    fetched_content = cast(dict[str, Any], fetched_receipt["fetched_content"])
    assert fetched_content["opaque_reference"] == reference
    assert fetched.pre_binding.sequence == fetched.post_binding.sequence
    assert fetched.pre_binding.state_id == fetched.post_binding.state_id
    assert fetched.pre_binding.information_set_id != fetched.post_binding.information_set_id
    assert restarted.run.state == initial_state


def test_retrieval_handover_carries_visible_state_and_budget_only(
    tmp_path: Path,
) -> None:
    root = tmp_path / "world"
    start = _start_request(identity="source")
    source = PumpStationWorldSessionFactory(
        root,
        temporal_evidence=True,
    ).open(start)
    search = cast(
        dict[str, Any],
        json.loads(
            source.search_evidence(
                request_id="search-for-handover",
                query="pump obstruction procedure",
                scope="procedures",
            )
        )["receipt"],
    )
    reference = search["references"][0]["opaque_reference"]
    source_budget = source.retrieval_state.remaining_budget
    carrier = source.create_retrieval_handover(
        to_tenure_id="tenure-recipient",
        to_session_id="session-recipient",
        include_fetched_content=True,
    )

    encoded_carrier = carrier.model_dump_json()
    assert "private_reason" not in encoded_carrier
    assert "frontier" not in encoded_carrier
    assert "treatment" not in encoded_carrier

    recipient_request = WorldSessionRequest(
        execution_kind=start.execution_kind,
        open_mode=WorldSessionOpenMode.RESUME,
        session_id="session-recipient",
        task_world_id=start.task_world_id,
        agent_tenure_id="tenure-recipient",
        run_id=start.run_id,
        episode_id=start.episode_id,
        world_branch_id=start.world_branch_id,
        start_snapshot=source.result.snapshot,
    )
    recipient = PumpStationWorldSessionFactory(root).open(recipient_request)
    recipient.install_structured_handover(
        create_structured_handover(
            recipient.actor_view,
            from_tenure_id=start.agent_tenure_id,
            history=source.actor_history,
            maximum_history_entries=10,
        )
    )
    before_carrier_information_set_id = recipient.result.information_set_id
    recipient.install_retrieval_handover(carrier)

    assert recipient.result.information_set_id != before_carrier_information_set_id
    assert recipient.retrieval_state.remaining_budget == source_budget
    fetched = cast(
        dict[str, Any],
        json.loads(
            recipient.fetch_evidence(
                request_id="fetch-carried-reference",
                reference=reference,
            )
        )["receipt"],
    )
    assert fetched["public_status"] == TemporalEvidenceAccessStatus.OK.value


def test_world_action_records_explicit_reliance_on_supplied_evidence(
    tmp_path: Path,
) -> None:
    session = PumpStationWorldSessionFactory(
        tmp_path / "world",
        temporal_evidence=True,
    ).open(_start_request(identity="reliance"))
    search = cast(
        dict[str, Any],
        json.loads(
            session.search_evidence(
                request_id="search-reliance",
                query="pump obstruction procedure",
                scope="procedures",
            )
        )["receipt"],
    )
    reference = search["references"][0]["opaque_reference"]
    action = session.invoke_actor_action(
        WorldActorActionRequest(
            request_id="continue-with-evidence",
            action_name="continue_operation",
            binding=session.current_actor_binding,
            arguments={
                "reason": "Continue under the current restrictions and review the procedure.",
                "relied_on_evidence_refs": [reference],
            },
        )
    )

    assert action.task_receipt["evidence_reliance_id"]
    reliance = session.load_evidence_reliance("continue-with-evidence")
    assert reliance.information_set_id == action.pre_binding.information_set_id
    assert reliance.relied_on_evidence_refs == (reference,)
    assert reliance.accepted_evidence_refs == ()

    snapshot = session.result.snapshot
    try:
        session.invoke_actor_action(
            WorldActorActionRequest(
                request_id="continue-with-guessed-evidence",
                action_name="continue_operation",
                binding=session.current_actor_binding,
                arguments={
                    "reason": "Use a reference that was never supplied.",
                    "relied_on_evidence_refs": ["guessed-reference"],
                },
            )
        )
    except WorldInterfaceError as error:
        assert error.code == "actor-evidence-reliance-invalid"
    else:
        raise AssertionError("guessed reliance reference was accepted")
    assert session.result.snapshot == snapshot


def test_same_session_resume_restores_exact_temporal_information_set(
    tmp_path: Path,
) -> None:
    root = tmp_path / "world"
    start = _start_request(identity="exact-resume")
    session = PumpStationWorldSessionFactory(
        root,
        temporal_evidence=True,
    ).open(start)
    session.search_evidence(
        request_id="search-before-resume",
        query="pump obstruction procedure",
        scope="procedures",
    )
    session.invoke_actor_action(
        WorldActorActionRequest(
            request_id="continue-before-resume",
            action_name="continue_operation",
            binding=session.current_actor_binding,
            arguments={"reason": "Continue to the next scheduled station event."},
        )
    )
    expected = session.result

    resumed = PumpStationWorldSessionFactory(root).open(
        WorldSessionRequest(
            execution_kind=start.execution_kind,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id=start.session_id,
            task_world_id=start.task_world_id,
            agent_tenure_id=start.agent_tenure_id,
            run_id=start.run_id,
            episode_id=start.episode_id,
            world_branch_id=start.world_branch_id,
            start_snapshot=expected.snapshot,
        )
    )

    assert resumed.result.snapshot == expected.snapshot
    assert resumed.result.actor_view_id == expected.actor_view_id
    assert resumed.result.information_set_id == expected.information_set_id
