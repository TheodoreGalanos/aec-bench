# ABOUTME: Proves Prime receives only the scoped actor surface for one host-owned world episode.
# ABOUTME: Covers exact retries, stale decisions, forbidden selectors, evidence safety, and closure.

from __future__ import annotations

import importlib
import inspect
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from aec_bench.contracts.world_session import (
    StewardshipStateSnapshotRef,
    WorldSessionExecutionKind,
    WorldSessionOpenMode,
    WorldSessionRequest,
)
from aec_bench.harness.pump_station_prime.session import (
    PUMP_STATION_GUIDANCE_INSTRUCTION,
    PumpStationPrimeSessionLimits,
    install_pump_station_guidance_skill,
    run_pump_station_prime_session,
)
from aec_bench.harness.world_actor import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_SOCKET_ENV,
    ActorInvocationAuthority,
    ActorInvocationAuthorityConfig,
    WorldActorEndpoint,
    install_world_actor_client,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation
from aec_bench.prime_agent.refinement import PrimeRefinementMode
from aec_bench.prime_agent.skills import (
    ACTOR_LEDGER_PLAN_INSTRUCTION,
    PrimeSkillInstallError,
    install_aec_actor_ledger_skill,
    install_aec_world_skill,
    install_prime_bundled_skill,
    install_prime_skill,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
    PumpStationEpisodeHost,
)
from aec_bench.worlds.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)


def _session_request() -> WorldSessionRequest:
    return WorldSessionRequest(
        execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
        open_mode=WorldSessionOpenMode.START,
        session_id="prime-session",
        task_world_id=PUMP_STATION_TASK_WORLD_ID,
        agent_tenure_id="prime-composite-actor",
        run_id="prime-run",
        episode_id="prime-episode",
        world_branch_id="prime-branch",
    )


def _limits(*, max_world_actions: int = 20) -> PumpStationPrimeSessionLimits:
    return PumpStationPrimeSessionLimits(
        max_world_actions=max_world_actions,
        max_model_calls=10,
        max_tokens=1_000,
        max_cost_usd=Decimal("10"),
        max_wall_seconds=5,
    )


def _endpoint(
    *,
    world_directory: Path,
    socket_directory: Path,
    max_world_actions: int,
    evidence_file: Path,
) -> WorldActorEndpoint:
    host = PumpStationEpisodeHost(world_directory)
    host.open(_session_request())
    authority = ActorInvocationAuthority(
        host=host,
        config=ActorInvocationAuthorityConfig(
            actor_principal_id="actor.prime-process-composite",
            max_world_actions=max_world_actions,
            evidence_path=evidence_file.with_name("actor-authority.jsonl"),
        ),
    )
    return WorldActorEndpoint(
        authority=authority,
        socket_directory=socket_directory,
        evidence_file=evidence_file,
    )


def _load_skill(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    install_world_actor_client(workspace)
    install_aec_world_skill(workspace)
    monkeypatch.syspath_prepend(str(workspace))
    sys.modules.pop("aec_world", None)
    return importlib.import_module("aec_world")


def _load_actor_ledger_skill(workspace: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    install_aec_actor_ledger_skill(workspace)
    monkeypatch.syspath_prepend(str(workspace))
    sys.modules.pop("aec_actor_ledger", None)
    return importlib.import_module("aec_actor_ledger")


def _fake_prime_agent_with_bundled_skills(tmp_path: Path) -> Path:
    from tests.prime_agent.test_acp import _fake_prime_agent

    package_root = tmp_path / "fake-prime-package"
    bundle_directory = package_root / "dist" / "bundle"
    bundle_directory.mkdir(parents=True)
    executable = _fake_prime_agent(bundle_directory)
    (package_root / "package.json").write_text(json.dumps({"name": "prime-agent"}), encoding="utf-8")
    for skill_name in ("agent-message", "agent-observe"):
        skill_directory = package_root / "dist" / "skills" / skill_name
        skill_directory.mkdir(parents=True)
        (skill_directory / "SKILL.md").write_text(
            f"---\nname: {skill_name}\ndescription: Test {skill_name}.\n---\n",
            encoding="utf-8",
        )
    return executable


def test_prime_world_skill_contains_only_provider_instructions(tmp_path: Path) -> None:
    workspace = tmp_path / "actor-workspace"
    workspace.mkdir()
    skill = install_aec_world_skill(workspace)

    assert [path.relative_to(skill).as_posix() for path in skill.rglob("*") if path.is_file()] == ["SKILL.md"]
    assert not (workspace / "aec_world").exists()


def test_reused_skill_ignores_local_python_cache_files(tmp_path: Path) -> None:
    source = tmp_path / "source" / "test-skill"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: test-skill\n---\n", encoding="utf-8")
    installed = install_prime_skill(tmp_path / "actor", source)
    source_cache = source / "__pycache__"
    installed_cache = installed / "__pycache__"
    source_cache.mkdir()
    installed_cache.mkdir()
    (source_cache / "module.pyc").write_bytes(b"source cache")
    (installed_cache / "module.pyc").write_bytes(b"actor cache")

    assert install_prime_skill(tmp_path / "actor", source) == installed


@pytest.mark.asyncio
async def test_world_actor_authority_preserves_pump_semantics_and_redacts_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_directory = tmp_path / "private-world" / "do-not-expose"
    actor_workspace = tmp_path / "actor-workspace"
    actor_workspace.mkdir()
    evidence_file = tmp_path / "host-evidence" / "actor-transport.jsonl"
    client = _load_skill(actor_workspace, monkeypatch)
    endpoint = _endpoint(
        world_directory=world_directory,
        socket_directory=actor_workspace / ".actor",
        max_world_actions=20,
        evidence_file=evidence_file,
    )

    with endpoint:
        environment = endpoint.connection_environment()
        for name, value in environment.items():
            monkeypatch.setenv(name, value)

        catalogue = await client.capabilities()
        observation = await client.observe()
        with pytest.raises(client.ActorError, match="world-action-not-available"):
            await client.invoke(
                "not_a_world_action",
                {},
                decision_id=observation["decision_id"],
                request_id="prime-action-unknown",
            )
        request_id = "prime-action-1"
        first = await client.invoke(
            "continue_operation",
            {"reason": "Advance the current world once."},
            decision_id=observation["decision_id"],
            request_id=request_id,
        )
        retry = await client.invoke(
            "continue_operation",
            {"reason": "Advance the current world once."},
            decision_id=observation["decision_id"],
            request_id=request_id,
        )

        assert catalogue["task_world_id"] == PUMP_STATION_TASK_WORLD_ID
        assert retry == first
        with pytest.raises(client.ActorError, match="request-id-conflict"):
            await client.invoke(
                "continue_operation",
                {"reason": "Different content under one request identity."},
                decision_id=observation["decision_id"],
                request_id=request_id,
            )
        with pytest.raises(client.ActorError, match="decision-stale"):
            await client.invoke(
                "continue_operation",
                {"reason": "Use an expired decision."},
                decision_id=observation["decision_id"],
                request_id="prime-action-stale",
            )

    assert not Path(environment[WORLD_ACTOR_SOCKET_ENV]).exists()
    authority_file = evidence_file.with_name("actor-authority.jsonl")
    stored_evidence = evidence_file.read_text(encoding="utf-8") + authority_file.read_text(encoding="utf-8")
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in stored_evidence
    assert str(world_directory) not in stored_evidence
    assert endpoint.world_action_count == 2


@pytest.mark.asyncio
async def test_actor_ledger_records_exact_attempts_without_adding_world_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_directory = tmp_path / "private-world"
    actor_workspace = tmp_path / "actor-workspace"
    actor_workspace.mkdir()
    _load_skill(actor_workspace, monkeypatch)
    ledger = _load_actor_ledger_skill(actor_workspace, monkeypatch)
    endpoint = _endpoint(
        world_directory=world_directory,
        socket_directory=actor_workspace / ".actor",
        max_world_actions=20,
        evidence_file=tmp_path / "host-evidence" / "actor-transport.jsonl",
    )

    with endpoint:
        environment = endpoint.connection_environment()
        for name, value in environment.items():
            monkeypatch.setenv(name, value)
        monkeypatch.chdir(actor_workspace)

        observed = await ledger.observe()
        datetime_matches = ledger.search("current_datetime")
        backlog = ledger.window("view.ranked_backlog", limit=2)
        with pytest.raises(ValueError, match="between 1 and 10"):
            ledger.window("view.ranked_backlog", limit=11)
        applied = await ledger.invoke(
            "continue_operation",
            {"reason": "Advance to the next actor-visible event."},
            expected_result="The world advances or returns the current blocker.",
            request_id="planned-action-1",
        )
        failed = await ledger.invoke(
            "not_a_world_action",
            {},
            expected_result="The world rejects the unknown action.",
            request_id="planned-action-2",
        )

    entries = ledger.entries(limit=2)
    assert set(observed) == {"decision_id", "view"}
    assert len(json.dumps(observed)) <= 4_000
    assert datetime_matches["matches"][0]["path"] == "view.current_datetime"
    assert 1 <= backlog["returned"] <= 2
    assert backlog["items"][0]["index"] == 0
    assert len(json.dumps(backlog)) <= 4_000
    assert applied["status"] == "applied"
    assert set(applied["observation"]) == {"decision_id", "view"}
    assert len(json.dumps(applied)) <= 4_000
    assert failed["status"] == "failed"
    assert failed["error"] == {
        "code": "world-action-not-available",
        "detail": "The requested world action is not in the frozen catalogue.",
    }
    assert [entry["request_id"] for entry in entries["entries"]] == ["planned-action-1", "planned-action-2"]
    assert entries["entries"][1]["error"] == failed["error"]
    assert entries["truncated"] is False
    assert ledger.latest()["decision_id"] == applied["observation"]["decision_id"]
    stored = (actor_workspace / ".aec-actor-ledger" / "actions.jsonl").read_text(encoding="utf-8")
    stored_entries = [json.loads(line) for line in stored.splitlines()]
    assert stored_entries[0]["result"]["next_observation"]["view"]["ranked_backlog"]
    assert environment[WORLD_ACTOR_CAPABILITY_ENV] not in stored
    assert str(world_directory) not in stored


def test_actor_ledger_never_returns_one_large_saved_value(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    actor_workspace = tmp_path / "actor-workspace"
    actor_workspace.mkdir()
    _load_skill(actor_workspace, monkeypatch)
    ledger = _load_actor_ledger_skill(actor_workspace, monkeypatch)
    monkeypatch.chdir(actor_workspace)
    store = actor_workspace / ".aec-actor-ledger"
    store.mkdir()
    (store / "state.json").write_text(
        json.dumps(
            {
                "decision_id": "current-decision",
                "view": {
                    "large": [{"name": f"item-{index}", "text": "x" * 10_000} for index in range(20)],
                    "y" * 10_000: "z" * 10_000,
                },
            }
        ),
        encoding="utf-8",
    )

    latest = ledger.latest()
    search = ledger.search("item-", path="view.large", limit=10)
    long_key_search = ledger.search("yyyy", limit=1)
    window = ledger.window("view.large", limit=10)

    assert latest["view"]["values"][0] == {"key": "large", "value": {"type": "array", "items": 20}}
    assert search["returned"] == 10
    assert search["truncated"] is True
    assert long_key_search["matches"][0]["path"].endswith("...")
    assert window["returned"] == 10
    assert window["truncated"] is True
    assert all(len(json.dumps(result)) <= 4_000 for result in (latest, search, long_key_search, window))


@pytest.mark.asyncio
async def test_world_action_budget_preserves_exact_retry_and_blocks_a_new_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world_directory = tmp_path / "private-world"
    actor_workspace = tmp_path / "actor-workspace"
    actor_workspace.mkdir()
    evidence_file = tmp_path / "host-evidence" / "actor-transport.jsonl"
    client = _load_skill(actor_workspace, monkeypatch)
    endpoint = _endpoint(
        world_directory=world_directory,
        socket_directory=actor_workspace / ".actor",
        max_world_actions=1,
        evidence_file=evidence_file,
    )

    with endpoint:
        environment = endpoint.connection_environment()
        for name, value in environment.items():
            monkeypatch.setenv(name, value)
        observation = await client.observe()
        first = await client.invoke(
            "continue_operation",
            {"reason": "Advance once."},
            decision_id=observation["decision_id"],
            request_id="action-1",
        )
        retry = await client.invoke(
            "continue_operation",
            {"reason": "Advance once."},
            decision_id=observation["decision_id"],
            request_id="action-1",
        )
        assert retry == first
        with pytest.raises(client.ActorError, match="world-action-budget-exhausted"):
            await client.invoke(
                "continue_operation",
                {"reason": "Try another action."},
                decision_id=first["next_observation"]["decision_id"],
                request_id="action-2",
            )

    assert endpoint.world_action_count == 1
    assert endpoint.world_action_limit_reached
    authority_evidence = evidence_file.with_name("actor-authority.jsonl").read_text(encoding="utf-8")
    assert "world-action-budget-exhausted" in authority_evidence


def test_packaged_skill_has_only_the_three_actor_operations(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()
    client = _load_skill(workspace, monkeypatch)

    assert client.__all__ == ["ActorError", "capabilities", "invoke", "observe"]
    assert not hasattr(client, "run")
    assert not hasattr(client, "branch")
    assert not hasattr(client, "profile")
    assert not hasattr(client, "verify")
    assert not hasattr(client, "evaluate")
    assert not hasattr(client, "rollout")
    assert not hasattr(client, "host_control")


def test_packaged_pump_guidance_is_markdown_only_and_contains_no_instance_plan(tmp_path: Path) -> None:
    workspace = tmp_path / "actor"
    workspace.mkdir()

    guidance = install_pump_station_guidance_skill(workspace)
    files = sorted(path.relative_to(guidance).as_posix() for path in guidance.rglob("*") if path.is_file())
    text = "\n".join((guidance / relative).read_text(encoding="utf-8") for relative in files)

    assert files == ["SKILL.md", "references/compact-state.md", "references/decision-method.md"]
    assert "guidance_id: aecbench.pump-station-guidance" in text
    assert "two-reference-profiles" in text
    assert "NO_ACCESSIBLE_RESULT" in text
    assert "after a `planned-outage-capacity` rejection" in text
    assert "Run eligibility alone is" in text
    assert "exact ledger" in text
    assert "one IPython cell for each `invoke` attempt" in text
    assert "not an action-selection rule" in text
    assert "remaining action budget" not in text
    assert "model-call limit" not in text
    assert "closure threshold" not in text
    for forbidden in (
        "pump-a",
        "pump-b",
        "backlog-a",
        "restriction-a",
        "world_run_directory",
        "--run-dir",
        "host_control",
        "expected score",
    ):
        assert forbidden not in text.lower()

    parameters = inspect.signature(run_pump_station_prime_session).parameters
    assert parameters["pump_station_guidance"].default is False
    assert parameters["actor_ledger_plan"].default is False
    assert "skill_directory" not in parameters
    assert "skill_directories" not in parameters


@pytest.mark.asyncio
async def test_prime_end_turn_while_world_is_live_is_recorded_incomplete(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "active"
    assert result.completion == "incomplete"
    assert result.verification.valid
    assert result.evaluation.evaluation_scope == "bounded_continuation"
    assert result.evaluation.valid
    assert result.evaluation.metrics.terminal_liability.active_restriction_count == 2
    assert result.actor_transport_file.exists()
    assert result.run_file.exists()
    assert result.world_action_count == 1
    assert not result.prime.benchmark_valid
    run_evidence = json.loads(result.run_file.read_text(encoding="utf-8"))
    assert run_evidence["evaluation_scope"] == "bounded_continuation"
    assert run_evidence["evaluation_valid"] is True
    assert run_evidence["world_state"] == "active"
    assert run_evidence["completion"] == "incomplete"
    assert not (tmp_path / "actor" / ".prime-skills" / "pump-station-guidance").exists()
    inbound = result.prime.paths.inbound_file.read_text(encoding="utf-8")
    assert PUMP_STATION_GUIDANCE_INSTRUCTION not in inbound
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world"]


@pytest.mark.asyncio
async def test_explicit_guided_treatment_adds_only_the_ordered_skill_and_instruction(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    instruction = "Advance the current world, then end the turn."
    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction=instruction,
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        pump_station_guidance=True,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    observed = json.loads((tmp_path / "actor" / "observed-acp.json").read_text(encoding="utf-8"))
    skill_arguments = [
        observed["argv"][index + 1] for index, argument in enumerate(observed["argv"]) if argument == "--skill"
    ]
    assert [Path(argument).name for argument in skill_arguments] == ["aec-world", "pump-station-guidance"]
    inbound = result.prime.paths.inbound_file.read_text(encoding="utf-8")
    assert instruction in inbound
    assert PUMP_STATION_GUIDANCE_INSTRUCTION in inbound
    assert "host model-call limit" not in inbound
    assert "closure no later than" not in inbound
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world", "pump-station-guidance"]
    assert [skill["order"] for skill in provenance["skills"]] == [0, 1]
    assert provenance["skill_sha256"] == provenance["skills"][0]["sha256"]
    serialized_provenance = json.dumps(provenance)
    assert str(tmp_path / "actor") not in serialized_provenance
    assert all(argument not in serialized_provenance for argument in skill_arguments)
    assert result.verification.valid
    assert result.evaluation.evaluation_scope == "bounded_continuation"


@pytest.mark.asyncio
async def test_explicit_planned_treatment_adds_bounded_ledger_and_child_coordination(tmp_path: Path) -> None:
    executable = _fake_prime_agent_with_bundled_skills(tmp_path)
    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        actor_ledger_plan=True,
        executable=str(executable),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    observed = json.loads((tmp_path / "actor" / "observed-acp.json").read_text(encoding="utf-8"))
    skill_arguments = [
        observed["argv"][index + 1] for index, argument in enumerate(observed["argv"]) if argument == "--skill"
    ]
    assert [Path(argument).name for argument in skill_arguments] == [
        "aec-world",
        "aec-actor-ledger",
        "agent-message",
        "agent-observe",
    ]
    assert (tmp_path / "actor" / "aec_actor_ledger" / "__init__.py").is_file()
    assert (tmp_path / "actor" / ".prime-skills" / "agent-message" / "SKILL.md").is_file()
    assert (tmp_path / "actor" / ".prime-skills" / "agent-observe" / "SKILL.md").is_file()
    inbound = result.prime.paths.inbound_file.read_text(encoding="utf-8")
    assert ACTOR_LEDGER_PLAN_INSTRUCTION in inbound
    assert "bounded search and window" in inbound
    assert "one actor principal" in inbound
    assert PUMP_STATION_GUIDANCE_INSTRUCTION not in inbound
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == [
        "aec-world",
        "aec-actor-ledger",
        "agent-message",
        "agent-observe",
    ]
    assert not (tmp_path / "actor" / ".prime-skills" / "pump-station-guidance").exists()


def test_prime_bundled_skill_install_fails_closed_for_a_missing_skill(tmp_path: Path) -> None:
    package_root = tmp_path / "prime-package"
    executable_directory = package_root / "dist" / "bundle"
    executable_directory.mkdir(parents=True)
    executable = executable_directory / "prime-agent"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    executable.chmod(0o755)
    (package_root / "package.json").write_text(json.dumps({"name": "prime-agent"}), encoding="utf-8")

    with pytest.raises(PrimeSkillInstallError, match="does not contain its agent-message skill"):
        install_prime_bundled_skill(tmp_path / "actor", executable=str(executable), skill_name="agent-message")


@pytest.mark.asyncio
async def test_prime_session_rejects_combined_guided_and_planned_treatments(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="open, guided, or planned"):
        await run_pump_station_prime_session(
            actor_workspace=tmp_path / "actor",
            world_run_directory=tmp_path / "private-world",
            evidence_directory=tmp_path / "host-evidence",
            session_request=_session_request(),
            instruction="Do the task.",
            model="anthropic/test",
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            pump_station_guidance=True,
            actor_ledger_plan=True,
        )


@pytest.mark.asyncio
async def test_discovery_mode_adds_prime_refine_skill(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world and refine only an evidence-backed lesson.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        refinement_mode=PrimeRefinementMode.DISCOVER,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    observed = json.loads((tmp_path / "actor" / "observed-acp.json").read_text(encoding="utf-8"))
    skill_arguments = [
        observed["argv"][index + 1] for index, argument in enumerate(observed["argv"]) if argument == "--skill"
    ]
    assert [Path(argument).name for argument in skill_arguments] == ["aec-world", "refine"]
    provenance = json.loads(result.prime.paths.run_file.read_text(encoding="utf-8"))
    assert [skill["name"] for skill in provenance["skills"]] == ["aec-world", "refine"]


@pytest.mark.asyncio
async def test_repeated_prime_sessions_share_actor_files_but_not_prime_runtime(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    actor_workspace = tmp_path / "actor"
    world_directory = tmp_path / "private-world"
    executable = str(_fake_prime_agent(tmp_path))
    first_runtime = actor_workspace / ".prime-runtimes" / "segment-000"
    first = await run_pump_station_prime_session(
        actor_workspace=actor_workspace,
        world_run_directory=world_directory,
        evidence_directory=tmp_path / "host-evidence-000",
        prime_runtime_directory=first_runtime,
        session_request=_session_request(),
        instruction="Advance the current world, then save your actor-owned state.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=executable,
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world", "FAKE_WORLD_REQUEST_ID": "segment-000-action"},
    )
    (actor_workspace / "state.json").write_text('{"retained":true}\n', encoding="utf-8")
    first_observed = json.loads((actor_workspace / "observed-acp.json").read_text(encoding="utf-8"))

    snapshot = PumpStationWorldRunRepository(world_directory).current_snapshot()
    second_runtime = actor_workspace / ".prime-runtimes" / "segment-001"
    second = await run_pump_station_prime_session(
        actor_workspace=actor_workspace,
        world_run_directory=world_directory,
        evidence_directory=tmp_path / "host-evidence-001",
        prime_runtime_directory=second_runtime,
        session_request=WorldSessionRequest(
            execution_kind=WorldSessionExecutionKind.STEWARDSHIP,
            open_mode=WorldSessionOpenMode.RESUME,
            session_id="prime-session-001",
            task_world_id=PUMP_STATION_TASK_WORLD_ID,
            agent_tenure_id="prime-composite-actor",
            run_id=snapshot.run_id,
            episode_id=snapshot.episode_id,
            world_branch_id=snapshot.world_branch_id,
            start_snapshot=StewardshipStateSnapshotRef(
                run_id=snapshot.run_id,
                episode_id=snapshot.episode_id,
                world_branch_id=snapshot.world_branch_id,
                sequence=snapshot.sequence,
                state_id=snapshot.state_id,
                commit_id=snapshot.commit_id,
            ),
        ),
        instruction="Continue from the actor-owned files and current observation.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=executable,
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world", "FAKE_WORLD_REQUEST_ID": "segment-001-action"},
    )
    second_observed = json.loads((actor_workspace / "observed-acp.json").read_text(encoding="utf-8"))

    assert first.prime.session_state == second.prime.session_state == "ended"
    assert first_observed["actor_state_exists"] is False
    assert second_observed["actor_state_exists"] is True
    assert Path(first_observed["home"]).is_relative_to(first_runtime)
    assert Path(second_observed["home"]).is_relative_to(second_runtime)
    assert first.prime.paths.state_dir != second.prime.paths.state_dir
    assert first.prime.paths.session_dir != second.prime.paths.session_dir
    assert (actor_workspace / "state.json").read_text(encoding="utf-8") == '{"retained":true}\n'


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt boundary")
async def test_sandboxed_prime_reaches_world_only_through_the_scoped_endpoint(tmp_path: Path) -> None:
    from tests.prime_agent.test_acp import _fake_prime_agent

    result = await run_pump_station_prime_session(
        actor_workspace=tmp_path / "actor",
        world_run_directory=tmp_path / "private-world",
        evidence_directory=tmp_path / "host-evidence",
        session_request=_session_request(),
        instruction="Advance the current world, then end the turn.",
        model="anthropic/test",
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "world"},
    )

    assert result.prime.session_state == "ended"
    assert result.world_state == "active"
    assert result.completion == "incomplete"
    assert result.verification.valid
    assert result.evaluation.evaluation_scope == "bounded_continuation"
    assert result.evaluation.valid
    assert result.prime.benchmark_valid
    assert result.benchmark_valid
