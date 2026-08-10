# ABOUTME: Proves Prime pump journeys alternate isolated actor sessions with host-owned controls.
# ABOUTME: Covers actor-workspace continuity, exact resume snapshots, replay, and final evidence.

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue

from aec_bench.contracts.world_interface import WorldActorActionRequest
from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.pump_station_prime import evidence as journey_evidence
from aec_bench.harness.pump_station_prime.journey import (
    PumpStationPrimeJourneyLimits,
    PumpStationPrimeJourneyRecoveryError,
    run_pump_station_prime_journey,
)
from aec_bench.harness.pump_station_prime.session import (
    PumpStationPrimeSessionLimits,
    PumpStationPrimeSessionRun,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation, PrimeAcpPaths, PrimeAcpRun
from aec_bench.prime_agent.refinement import (
    PrimeRefinementCandidate,
    PrimeRefinementEntry,
    PrimeRefinementEvidence,
    PrimeRefinementKind,
    PrimeRefinementMode,
    PrimeRefinementScope,
    empty_refinement_candidate,
)
from aec_bench.prime_agent.session_evidence import PrimeAcpRefinement, PrimeAcpTopology, PrimeAcpUsage
from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_work import (
    PumpStationBacklogStatus,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.reference_system import (
    PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)
from tests.support.pump_station_prime import pump_station_prime_session_request

_session_request = pump_station_prime_session_request


def _journey_limits(**overrides: object) -> PumpStationPrimeJourneyLimits:
    values: dict[str, object] = {
        "max_sessions": 4,
        "max_host_controls": 4,
        "max_world_actions": 100,
        "max_model_calls": 10,
        "max_tokens": 1_000,
        "max_cost_usd": Decimal("10"),
        "max_wall_seconds": 300.0,
    }
    values.update(overrides)
    return PumpStationPrimeJourneyLimits(**values)  # type: ignore[arg-type]


def _refinement_entry(
    kind: PrimeRefinementKind,
    entry_id: str,
    scope: PrimeRefinementScope,
) -> PrimeRefinementEntry:
    reference: dict[str, JsonValue] = {}
    if kind is PrimeRefinementKind.SKILL:
        reference = {
            "type": "python",
            "import": "aec_world",
            "callable": "observe",
            "call_pattern": "await aec_world.observe()",
        }
    return PrimeRefinementEntry(
        id=entry_id,
        kind=kind,
        title=f"{kind.value} title",
        content=f"Use the {kind.value} refinement.",
        path="pump/stewardship",
        scope=scope,
        reference=reference,
        arguments={},
        metadata={"scope": scope.value},
        source="refine",
        created_at="2026-08-09T00:00:00Z",
        updated_at="2026-08-09T00:00:00Z",
        version=1,
    )


def _shared_snapshot(run: PumpStationWorldRun) -> StewardshipStateSnapshotRef:
    snapshot = run.snapshot()
    return StewardshipStateSnapshotRef(
        run_id=snapshot.run_id,
        episode_id=snapshot.episode_id,
        world_branch_id=snapshot.world_branch_id,
        sequence=snapshot.sequence,
        state_id=snapshot.state_id,
        commit_id=snapshot.commit_id,
    )


def _act(host: PumpStationEpisodeHost, request_id: str, action_name: str, **arguments: object) -> None:
    observation = host.observe()
    result = host.invoke(
        WorldActorActionRequest(
            request_id=request_id,
            decision_id=observation.decision_id,
            action_name=action_name,
            arguments=cast(
                dict[str, JsonValue],
                {"reason": f"Complete {request_id} under the visible service plan.", **arguments},
            ),
        )
    )
    assert result.status == "applied"


def _continue_to(host: PumpStationEpisodeHost, run: PumpStationWorldRun, target: int) -> None:
    while run.state.calendar_seconds < target:
        _act(host, f"continue-{run.snapshot().sequence + 1}", "continue_operation")
    assert run.state.calendar_seconds == target


def _item_id(run: PumpStationWorldRun, rule_id: str, target_id: str) -> str:
    matching = tuple(
        item.item_id
        for item in run.state.backlog
        if item.generation_rule_id == rule_id
        and item.target_id == target_id
        and item.status in {PumpStationBacklogStatus.OPEN, PumpStationBacklogStatus.PLANNED}
    )
    assert len(matching) == 1
    return matching[0]


def _run_actor_segment(repository_root: Path, index: int) -> int:
    repository = PumpStationWorldRunRepository(repository_root)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    host = PumpStationEpisodeHost(repository_root)
    before = run.snapshot().sequence
    if index == 0:
        _act(
            host,
            "a-verification",
            "request_post_maintenance_verification",
            pump_id="pump-a",
            backlog_item_id="backlog-a-verification-001",
        )
        _continue_to(host, run, 50_400)
    elif index == 1:
        _continue_to(host, run, 64_800)
        _act(host, "assign-a-c", "request_duty_assignment", ordered_pump_ids=["pump-a", "pump-c"])
        _continue_to(host, run, 108_000)
        _act(
            host,
            "b-clearance",
            "request_obstruction_clearance",
            pump_id="pump-b",
            backlog_item_id="backlog-b-clearance-001",
            inspection_evidence_id="initial-b-inspection-accepted",
        )
        _continue_to(host, run, 122_400)
        _act(
            host,
            "b-functional",
            "request_functional_check",
            pump_id="pump-b",
            backlog_item_id=_item_id(run, "WG-03", "pump-b"),
        )
        _continue_to(host, run, 126_000)
        _act(
            host,
            "b-provisional-return",
            "request_provisional_return",
            pump_id="pump-b",
            functional_check_evidence_id="evidence-b-functional-check-pass-001",
        )
        _act(host, "b-provisional-closure", "request_provisional_closure", work_order_id="work-order-b-001")
        _act(
            host,
            "b-verification",
            "request_post_maintenance_verification",
            pump_id="pump-b",
            backlog_item_id=_item_id(run, "WG-04", "pump-b"),
        )
        _continue_to(host, run, 154_800)
    elif index == 2:
        _continue_to(host, run, 194_400)
        _act(host, "assign-a-b", "request_duty_assignment", ordered_pump_ids=["pump-a", "pump-b"])
        _act(
            host,
            "c-inspection",
            "request_inspection",
            pump_id="pump-c",
            backlog_item_id=_item_id(run, "WG-07", "pump-c"),
        )
        _continue_to(host, run, 223_200)
    else:
        raise AssertionError(f"unexpected actor segment {index}")
    return run.snapshot().sequence - before


def _fake_prime_run(
    *,
    evidence_directory: Path,
    runtime_directory: Path,
    isolation: PrimeAcpIsolation,
    limits: PumpStationPrimeSessionLimits,
    index: int,
    refinement_mode: PrimeRefinementMode,
    refinement_candidate: PrimeRefinementCandidate | None,
    session_state: str = "ended",
    stop_reason: str = "end_turn",
    limit_reason: str | None = None,
) -> PrimeAcpRun:
    evidence_directory.mkdir(parents=True, exist_ok=True)
    runtime_directory.mkdir(parents=True, exist_ok=True)
    paths = PrimeAcpPaths(
        state_dir=runtime_directory / "state",
        session_dir=runtime_directory / "sessions",
        inbound_file=evidence_directory / "prime-acp-in.jsonl",
        outbound_file=evidence_directory / "prime-acp-out.jsonl",
        stderr_file=evidence_directory / "prime-stderr.log",
        run_file=evidence_directory / "prime-run.json",
    )
    for path in (paths.inbound_file, paths.outbound_file, paths.stderr_file):
        path.write_text("", encoding="utf-8")
    paths.run_file.write_text("{}\n", encoding="utf-8")
    now = datetime.now(UTC)
    candidate = refinement_candidate or empty_refinement_candidate()
    return PrimeAcpRun(
        command=("fake-prime",),
        prime_version="0.7.0",
        paths=paths,
        started_at=now,
        finished_at=now,
        elapsed_seconds=1.0,
        exit_code=0,
        session_id=f"fake-prime-{index}",
        protocol_version=1,
        agent_name="prime-agent",
        agent_version="0.7.0",
        agent_capabilities={},
        limits=limits.acp_limits(),
        usage=PrimeAcpUsage(
            complete=True,
            model_calls=1,
            input_tokens=10,
            output_tokens=5,
            cache_read_tokens=2,
            cache_write_tokens=3,
            total_tokens=20,
            cost_usd=Decimal("0.25"),
        ),
        topology=PrimeAcpTopology(root_sessions=1, child_sessions=0),
        refinement=PrimeAcpRefinement(events=0, completed=0, failed=0, unknown=0),
        refinement_harness=PrimeRefinementEvidence(
            mode=refinement_mode,
            candidate=candidate,
            global_candidate=candidate,
            sources=(),
            portable=True,
            issues=(),
            changed=False,
            drifted=False,
        ),
        limit_reason=limit_reason,
        session_state=session_state,
        stop_reason=stop_reason,
        timed_out=False,
        benchmark_valid=True,
        isolation=isolation,
        updates=(),
        error=None,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("world_path", "evidence_path"),
    [
        ("host", "host/evidence"),
        ("host/world", "host"),
    ],
)
async def test_journey_keeps_world_repository_and_evidence_separate(
    tmp_path: Path,
    world_path: str,
    evidence_path: str,
) -> None:
    with pytest.raises(ValueError, match="world run and journey evidence paths must be separate"):
        await run_pump_station_prime_journey(
            actor_workspace=tmp_path / "actor",
            world_run_directory=tmp_path / world_path,
            evidence_directory=tmp_path / evidence_path,
            session_request=_session_request(),
            instruction="Complete the pump-station stewardship task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_journey_limits(),
        )


def _fake_segment_result(
    kwargs: dict[str, Any],
    *,
    index: int,
    make_progress: bool,
    session_state: str = "ended",
    stop_reason: str = "end_turn",
    limit_reason: str | None = None,
    world_action_limit_reached: bool = False,
) -> PumpStationPrimeSessionRun:
    actor_workspace = Path(kwargs["actor_workspace"])
    session_request = cast(WorldSessionRequest, kwargs["session_request"])
    repository_root = Path(kwargs["world_run_directory"])
    world_session = PumpStationEpisodeHost(repository_root).open(session_request)
    action_count = _run_actor_segment(repository_root, index) if make_progress else 0
    repository = PumpStationWorldRunRepository(repository_root)
    run = PumpStationWorldRun.resume_reference_system(repository=repository, snapshot=repository.current_snapshot())
    verification = run.verify()
    evidence_directory = Path(kwargs["evidence_directory"])
    evidence_directory.mkdir(parents=True, exist_ok=True)
    actor_transport = evidence_directory / "world-actor-transport.jsonl"
    actor_transport.write_text("", encoding="utf-8")
    run_file = evidence_directory / "prime-world-run.json"
    run_file.write_text("{}\n", encoding="utf-8")
    prime = _fake_prime_run(
        evidence_directory=evidence_directory,
        runtime_directory=Path(kwargs["prime_runtime_directory"]),
        isolation=cast(PrimeAcpIsolation, kwargs["isolation"]),
        limits=cast(PumpStationPrimeSessionLimits, kwargs["limits"]),
        index=index,
        refinement_mode=cast(PrimeRefinementMode, kwargs["refinement_mode"]),
        refinement_candidate=cast(PrimeRefinementCandidate | None, kwargs["refinement_candidate"]),
        session_state=session_state,
        stop_reason=stop_reason,
        limit_reason=limit_reason,
    )
    assert actor_workspace.is_dir()
    return PumpStationPrimeSessionRun(
        prime=prime,
        world_session=world_session,
        world_state="active",
        completion="incomplete",
        verification=verification,
        evaluation=evaluate_pump_station_reference_run(run, evaluation_scope="bounded_continuation"),
        actor_transport_file=actor_transport,
        run_file=run_file,
        world_action_attempts=action_count,
        world_action_limit_reached=world_action_limit_reached,
        benchmark_valid=True,
    )


@pytest.mark.asyncio
async def test_journey_resumes_a_host_selected_rs2_run_without_an_actor_profile_selector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    world_root = tmp_path / "private-world"
    initial_request = _session_request()
    run = PumpStationWorldRun.create_reference_system(
        repository=PumpStationWorldRunRepository(world_root),
        run_id=initial_request.run_id,
        episode_id=initial_request.episode_id,
        world_branch_id=initial_request.world_branch_id,
        reference_system_id=PUMP_STATION_REFERENCE_SYSTEM_RS2_ID,
    )
    resume_request = initial_request.model_copy(
        update={
            "open_mode": WorldSessionOpenMode.RESUME,
            "start_snapshot": _shared_snapshot(run),
        }
    )

    async def no_progress_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        request = cast(WorldSessionRequest, kwargs["session_request"])
        assert request.open_mode is WorldSessionOpenMode.RESUME
        assert request.start_snapshot == _shared_snapshot(run)
        return _fake_segment_result(kwargs, index=0, make_progress=False)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", no_progress_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=world_root,
        evidence_directory=tmp_path / "host-evidence",
        session_request=resume_request,
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(),
    )
    selected = PumpStationWorldRun.resume_reference_system(
        repository=PumpStationWorldRunRepository(world_root),
        snapshot=PumpStationWorldRunRepository(world_root).current_snapshot(),
    )

    assert selected.manifest.reference_system_id == PUMP_STATION_REFERENCE_SYSTEM_RS2_ID
    assert result.segments[0].open_mode is WorldSessionOpenMode.RESUME
    assert result.completion == "incomplete"
    assert result.verification.valid


@pytest.mark.asyncio
async def test_complete_journey_preserves_actor_workspace_and_keeps_host_controls_outside_prime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    calls: list[dict[str, Any]] = []

    async def fake_session_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        index = len(calls)
        calls.append(kwargs)
        actor_workspace = Path(kwargs["actor_workspace"])
        runtime_directory = Path(kwargs["prime_runtime_directory"])
        if index > 0:
            previous_runtime = actor_workspace / ".prime-runtimes" / f"segment-{index - 1:03d}"
            assert not previous_runtime.exists()
        runtime_directory.mkdir(parents=True)
        runtime_target = runtime_directory / "python-runtime"
        runtime_target.write_text("runtime\n", encoding="utf-8")
        (runtime_directory / "python").symlink_to(runtime_target)
        if index == 0:
            (actor_workspace / "state.json").write_text('{"segment":0}\n', encoding="utf-8")
        else:
            assert (actor_workspace / "state.json").read_text(encoding="utf-8") == '{"segment":0}\n'
            assert "continuation segment" in str(kwargs["instruction"]).lower()
        return _fake_segment_result(kwargs, index=index, make_progress=True)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", fake_session_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(),
    )

    assert result.completion == "completed"
    assert result.world_state == "completed"
    assert len(result.segments) == 3
    assert len(result.host_controls) == 3
    assert result.verification.valid
    assert result.evaluation.valid
    assert result.evaluation.evaluation_scope == "complete_journey"
    assert result.usage.complete
    assert result.usage.model_calls == 3
    assert result.usage.total_tokens == 60
    assert result.usage.cost_usd == Decimal("0.75")
    assert result.benchmark_valid
    assert all(call["actor_workspace"] == tmp_path / "actor" for call in calls)
    assert len({call["prime_runtime_directory"] for call in calls}) == 3
    requests = [cast(WorldSessionRequest, call["session_request"]) for call in calls]
    assert requests[0].open_mode.value == "start"
    assert [request.open_mode.value for request in requests[1:]] == ["resume", "resume"]
    assert len({request.session_id for request in requests}) == 3
    assert {request.agent_tenure_id for request in requests} == {"prime-composite-actor"}
    assert all(request.start_snapshot is not None for request in requests[1:])
    assert (tmp_path / "actor" / "state.json").read_text(encoding="utf-8") == '{"segment":0}\n'
    assert not any(Path(call["prime_runtime_directory"]).exists() for call in calls)
    session_limits = [cast(PumpStationPrimeSessionLimits, call["limits"]) for call in calls]
    assert [limit.max_model_calls for limit in session_limits] == [10, 9, 8]
    assert [limit.max_tokens for limit in session_limits] == [1_000, 980, 960]
    assert [limit.max_cost_usd for limit in session_limits] == [Decimal("10"), Decimal("9.75"), Decimal("9.50")]
    assert (
        session_limits[0].max_world_actions > session_limits[1].max_world_actions > session_limits[2].max_world_actions
    )
    evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
    serialized = json.dumps(evidence)
    assert evidence["schema"] == "aecbench.prime-world-journey.v1"
    assert evidence["actor_principal_scope"] == "prime-journey-composite"
    assert len(evidence["segments"]) == 3
    assert len(evidence["host_controls"]) == 3
    assert evidence["host_policy_sha256"]
    assert evidence["segments"][0]["end_snapshot"]
    assert evidence["host_controls"][0]["parent_snapshot"]
    assert str(tmp_path) not in serialized
    assert "operations-controller" not in serialized
    checkpoint = (tmp_path / "host-evidence" / "prime-world-journey-checkpoint.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in checkpoint
    assert "operations-controller" not in checkpoint


@pytest.mark.asyncio
async def test_discovery_carries_only_global_refinement_across_fresh_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    local_entry = _refinement_entry(
        PrimeRefinementKind.PROMPT,
        "session-ledger",
        PrimeRefinementScope.LOCAL,
    )
    global_entry = _refinement_entry(
        PrimeRefinementKind.SKILL,
        "observe-current-world",
        PrimeRefinementScope.GLOBAL,
    )
    full_candidate = PrimeRefinementCandidate(prime_harness_schema=1, entries=(local_entry, global_entry))
    global_candidate = PrimeRefinementCandidate(prime_harness_schema=1, entries=(global_entry,))
    calls: list[dict[str, Any]] = []

    async def fake_session_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        index = len(calls)
        calls.append(kwargs)
        if index == 0:
            assert kwargs["refinement_candidate"] is None
        else:
            assert kwargs["refinement_candidate"] == global_candidate
        segment = _fake_segment_result(kwargs, index=index, make_progress=True)
        harness = PrimeRefinementEvidence(
            mode=PrimeRefinementMode.DISCOVER,
            candidate=full_candidate if index == 0 else global_candidate,
            global_candidate=global_candidate,
            sources=(),
            portable=True,
            issues=(),
            changed=index == 0,
            drifted=False,
        )
        return replace(segment, prime=replace(segment.prime, refinement_harness=harness))

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", fake_session_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(),
        refinement_mode=PrimeRefinementMode.DISCOVER,
    )

    assert result.completion == "completed"
    assert len(calls) == 3
    assert result.refinement_candidate == global_candidate
    assert result.segments[0].refinement_candidate_sha256 == full_candidate.content_sha256
    assert all(
        segment.refinement_global_candidate_sha256 == global_candidate.content_sha256 for segment in result.segments
    )


@pytest.mark.asyncio
async def test_fixed_candidate_is_loaded_into_every_fresh_journey_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    candidate = PrimeRefinementCandidate(
        prime_harness_schema=1,
        entries=(
            _refinement_entry(
                PrimeRefinementKind.SUBAGENT,
                "evidence-reviewer",
                PrimeRefinementScope.LOCAL,
            ),
        ),
    )
    calls: list[dict[str, Any]] = []

    async def fake_session_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        calls.append(kwargs)
        assert kwargs["refinement_mode"] is PrimeRefinementMode.CANDIDATE
        assert kwargs["refinement_candidate"] == candidate
        return _fake_segment_result(kwargs, index=len(calls) - 1, make_progress=True)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", fake_session_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(),
        refinement_mode=PrimeRefinementMode.CANDIDATE,
        refinement_candidate=candidate,
    )

    assert result.completion == "completed"
    assert len(calls) == 3
    assert result.refinement_candidate == candidate
    assert all(segment.refinement_candidate_sha256 == candidate.content_sha256 for segment in result.segments)

    evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
    assert evidence["refinement"] == {
        "mode": "candidate",
        "candidate_sha256": candidate.content_sha256,
    }


@pytest.mark.asyncio
async def test_journey_stops_incomplete_when_no_deterministic_host_control_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    async def no_progress_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        return _fake_segment_result(kwargs, index=0, make_progress=False)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", no_progress_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(),
    )

    assert result.completion == "incomplete"
    assert result.world_state == "active"
    assert len(result.segments) == 1
    assert result.host_controls == ()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stop_reason", "limit_reason", "session_state", "world_action_limit_reached", "expected_reason"),
    [
        ("max_tokens", None, "ended", False, "max_tokens"),
        ("max_turn_requests", None, "ended", False, "max_turn_requests"),
        ("end_turn", "max_tokens", "ended", False, "max_tokens"),
        ("end_turn", None, "ended", True, "max_world_actions"),
        ("cancelled", None, "cancelled", False, "cancelled"),
    ],
)
async def test_host_control_requires_a_clean_prime_end(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stop_reason: str,
    limit_reason: str | None,
    session_state: str,
    world_action_limit_reached: bool,
    expected_reason: str,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    async def stopped_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        return _fake_segment_result(
            kwargs,
            index=0,
            make_progress=True,
            stop_reason=stop_reason,
            limit_reason=limit_reason,
            session_state=session_state,
            world_action_limit_reached=world_action_limit_reached,
        )

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", stopped_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(),
    )

    assert result.completion == "interrupted"
    assert result.stop_reason == expected_reason
    assert result.host_controls == ()
    restrictions = PumpStationEpisodeHost(tmp_path / "private-world").observe().view["active_restriction_ids"]
    assert isinstance(restrictions, list)
    assert "restriction-a-run-in-001" in restrictions


@pytest.mark.asyncio
async def test_session_limit_stops_before_host_control(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    async def clean_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        return _fake_segment_result(kwargs, index=0, make_progress=True)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", clean_runner)
    result = await run_pump_station_prime_journey(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Complete the pump-station stewardship task.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_journey_limits(max_sessions=1),
    )

    assert result.completion == "interrupted"
    assert result.stop_reason == "max_sessions"
    assert result.host_controls == ()


@pytest.mark.asyncio
async def test_open_guided_and_planned_journeys_use_the_same_host_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    calls: list[dict[str, Any]] = []

    async def no_progress_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        calls.append(kwargs)
        return _fake_segment_result(kwargs, index=0, make_progress=False)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", no_progress_runner)
    digests: list[str] = []
    for name, guided, planned in (
        ("open", False, False),
        ("guided", True, False),
        ("planned", False, True),
    ):
        result = await run_pump_station_prime_journey(
            actor_workspace=tmp_path / f"actor-{name}",
            world_run_directory=tmp_path / f"world-{name}",
            evidence_directory=tmp_path / f"evidence-{name}",
            session_request=_session_request(),
            instruction="Complete the pump-station stewardship task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_journey_limits(),
            pump_station_guidance=guided,
            actor_ledger_plan=planned,
        )
        evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
        assert evidence["treatment"] == name
        digests.append(str(evidence["host_policy_sha256"]))

    assert [call["pump_station_guidance"] for call in calls] == [False, True, False]
    assert [call["actor_ledger_plan"] for call in calls] == [False, False, True]
    assert len(set(digests)) == 1


@pytest.mark.asyncio
async def test_resume_rejects_a_prime_session_without_a_terminal_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    async def crashed_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        raise RuntimeError("simulated Prime process crash")

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", crashed_runner)

    async def run(*, resume: bool = False) -> Any:
        return await run_pump_station_prime_journey(
            actor_workspace=tmp_path / "actor",
            world_run_directory=tmp_path / "private-world",
            evidence_directory=tmp_path / "host-evidence",
            session_request=_session_request(),
            instruction="Complete the pump-station stewardship task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_journey_limits(),
            resume=resume,
        )

    with pytest.raises(RuntimeError, match="simulated Prime process crash"):
        await run()
    with pytest.raises(PumpStationPrimeJourneyRecoveryError, match="without a terminal checkpoint"):
        await run(resume=True)


@pytest.mark.asyncio
async def test_resume_recovers_one_applied_host_control_without_repeating_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import aec_bench.harness.pump_station_prime.journey as journey_module

    calls: list[dict[str, Any]] = []

    async def fake_session_runner(**kwargs: Any) -> PumpStationPrimeSessionRun:
        index = len(calls)
        calls.append(kwargs)
        return _fake_segment_result(kwargs, index=index, make_progress=True)

    monkeypatch.setattr(journey_module, "run_pump_station_prime_session", fake_session_runner)
    real_write = journey_evidence.write_checkpoint
    crashed = False

    def crash_after_control(path: Path, checkpoint: Any) -> None:
        nonlocal crashed
        if not crashed and checkpoint.phase == "ready" and len(checkpoint.host_controls) == 1:
            crashed = True
            raise RuntimeError("simulated process crash after durable host control")
        real_write(path, checkpoint)

    monkeypatch.setattr(journey_evidence, "write_checkpoint", crash_after_control)

    async def run(*, resume: bool = False) -> Any:
        return await run_pump_station_prime_journey(
            actor_workspace=tmp_path / "actor",
            world_run_directory=tmp_path / "private-world",
            evidence_directory=tmp_path / "host-evidence",
            session_request=_session_request(),
            instruction="Complete the pump-station stewardship task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.MACOS_SANDBOX,
            limits=_journey_limits(),
            resume=resume,
        )

    with pytest.raises(RuntimeError, match="simulated process crash"):
        await run()

    repository = PumpStationWorldRunRepository(tmp_path / "private-world")
    applied_request_id = repository.command_steps()[-1].command.request_id
    assert applied_request_id.startswith("operations-review-")
    assert sum(step.command.request_id == applied_request_id for step in repository.command_steps()) == 1

    monkeypatch.setattr(journey_evidence, "write_checkpoint", real_write)
    result = await run(resume=True)

    assert result.completion == "completed"
    assert len(result.host_controls) == 3
    assert result.host_controls[0].request_id == applied_request_id
    assert sum(step.command.request_id == applied_request_id for step in repository.command_steps()) == 1
