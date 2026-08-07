# ABOUTME: Exercises the Prime ACP lifecycle against a deterministic protocol-speaking subprocess.
# ABOUTME: Proves strict framing, one session, raw metadata evidence, redaction, and validity labeling.

from __future__ import annotations

import json
import os
import subprocess
import sys
from decimal import Decimal
from pathlib import Path

import pytest

from aec_bench.prime_agent.acp import (
    PrimeAcpIsolation,
    PrimeAcpIsolationError,
    build_macos_sandbox_profile,
    build_prime_acp_command,
    run_prime_acp_session,
)
from aec_bench.prime_agent.batch import PRIME_AGENT_TESTED_VERSION
from aec_bench.prime_agent.session_evidence import PrimeAcpLimits
from aec_bench.prime_agent.world import (
    WORLD_ACTOR_CAPABILITY_ENV,
    WORLD_ACTOR_SOCKET_ENV,
    install_aec_world_skill,
    install_pump_station_guidance_skill,
)


def _fake_prime_agent(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-prime-agent"
    executable.write_text(
        f"""#!{Path(sys.executable).resolve()}
import json
import os
from pathlib import Path
import sys
import time

if "--version" in sys.argv:
    print("prime-agent {PRIME_AGENT_TESTED_VERSION}")
    raise SystemExit(0)

Path("observed-acp.json").write_text(json.dumps({{
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "home": os.environ.get("HOME"),
    "xdg_cache_home": os.environ.get("XDG_CACHE_HOME"),
    "xdg_config_home": os.environ.get("XDG_CONFIG_HOME"),
    "xdg_data_home": os.environ.get("XDG_DATA_HOME"),
}}))
scenario = os.environ.get("FAKE_ACP_SCENARIO", "success")
session_dir = Path(sys.argv[sys.argv.index("--session-dir") + 1])
session_file = session_dir / "root.jsonl"

def append_session(event):
    with session_file.open("a") as sink:
        sink.write(json.dumps(event) + "\\n")

def record_assistant():
    append_session({{
        "type": "message",
        "id": "fake-assistant-1",
        "message": {{
            "role": "assistant",
            "usage": {{
                "input": 10,
                "output": 5,
                "cacheRead": 2,
                "cacheWrite": 3,
                "totalTokens": 20,
                "cost": {{"total": 0.25000000000000003}},
            }},
        }},
    }})

sessions = 0
for line in sys.stdin:
    request = json.loads(line)
    method = request.get("method")
    if method == "initialize":
        version = 99 if scenario == "unsupported" else 1
        result = {{
            "protocolVersion": version,
            "agentCapabilities": None if scenario == "missing-capabilities" else {{"loadSession": False}},
            "agentInfo": {{"name": "prime-agent", "version": "{PRIME_AGENT_TESTED_VERSION}"}},
            "_meta": {{"futureInitializeMetadata": {{"preserve": True}}}},
        }}
        print(json.dumps({{"jsonrpc": "2.0", "id": request["id"], "result": result}}), flush=True)
    elif method == "session/new":
        sessions += 1
        append_session({{
            "type": "session", "version": 3, "id": "prime-root", "rlmDepth": 0
        }})
        print(json.dumps({{"jsonrpc": "2.0", "id": request["id"], "result": {{
            "sessionId": f"fake-session-{{sessions}}", "_meta": {{"unknownSessionKey": 7}}
        }}}}), flush=True)
    elif method == "session/prompt":
        if scenario == "process-exit":
            raise SystemExit(7)
        if scenario == "timeout":
            time.sleep(60)
        if scenario == "malformed":
            print("not-json", flush=True)
            continue
        record_assistant()
        if scenario == "malformed-session":
            with session_file.open("a") as sink:
                sink.write("not-json\\n")
        if scenario == "topology-refinement":
            child_file = session_dir / "child.jsonl"
            child_file.write_text(json.dumps({{
                "type": "session", "version": 3, "id": "prime-child", "rlmDepth": 1
            }}) + "\\n")
        if scenario == "world":
            import asyncio
            sys.path.insert(0, os.getcwd())
            import aec_world
            async def act():
                observation = await aec_world.observe()
                await aec_world.invoke(
                    "continue_operation",
                    {{"reason": "Advance the current world once."}},
                    decision_id=observation["decision_id"],
                    request_id="fake-prime-world-action",
                )
            asyncio.run(act())
        print(json.dumps({{
            "jsonrpc": "2.0",
            "method": "session/update",
            "params": {{
                "sessionId": f"fake-session-{{sessions}}",
                "update": {{
                    "sessionUpdate": "agent_message_chunk",
                    "content": {{"type": "text", "text": "Working"}},
                    "_meta": {{
                        "unknownUpdateKey": "kept",
                        **({{"ai.primeintellect.prime-agent": {{
                            "refinement": {{"status": "complete", "summary": "kept raw"}}
                        }}}} if scenario == "topology-refinement" else {{}}),
                    }},
                }},
                "_meta": {{"unknownNotificationKey": True}},
            }},
        }}), flush=True)
        if scenario == "budget":
            time.sleep(0.2)
        print(json.dumps({{"jsonrpc": "2.0", "id": request["id"], "result": {{
            "stopReason": "end_turn", "_meta": {{"futurePromptMetadata": [1, 2, 3]}}
        }}}}), flush=True)
        print("stderr " + os.environ.get("FAKE_SECRET_TOKEN", "none"), file=sys.stderr, flush=True)
    elif method == "session/close":
        print(json.dumps({{"jsonrpc": "2.0", "id": request["id"], "result": {{}}}}), flush=True)
    elif method == "session/cancel":
        pass
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    actor_workspace = tmp_path / "actor"
    actor_workspace.mkdir()
    skill = install_aec_world_skill(actor_workspace)
    evidence = tmp_path / "host-evidence"
    return actor_workspace, skill, evidence


def _limits(*, wall_seconds: float = 5) -> PrimeAcpLimits:
    return PrimeAcpLimits(
        max_model_calls=10,
        max_tokens=1_000,
        max_cost_usd=Decimal("10"),
        max_wall_seconds=wall_seconds,
    )


def test_builds_acp_command_with_only_the_explicit_skill(tmp_path: Path) -> None:
    actor_workspace, skill, _ = _workspace(tmp_path)

    command = build_prime_acp_command(
        executable=Path("/opt/prime/bin/prime-agent"),
        model="anthropic/test",
        actor_workspace=actor_workspace,
        session_dir=actor_workspace / "sessions",
        skill_directories=(skill,),
    )

    assert command == [
        "/opt/prime/bin/prime-agent",
        "--mode",
        "acp",
        "--model",
        "anthropic/test",
        "--cwd",
        str(actor_workspace),
        "--session-dir",
        str(actor_workspace / "sessions"),
        "--no-skills",
        "--skill",
        str(skill),
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--offline",
    ]


def test_builds_acp_command_with_ordered_explicit_skills(tmp_path: Path) -> None:
    actor_workspace, skill, _ = _workspace(tmp_path)
    guidance = install_pump_station_guidance_skill(actor_workspace)

    command = build_prime_acp_command(
        executable=Path("/opt/prime/bin/prime-agent"),
        model="anthropic/test",
        actor_workspace=actor_workspace,
        session_dir=actor_workspace / "sessions",
        skill_directories=(skill, guidance),
    )

    first_skill = command.index("--skill")
    second_skill = command.index("--skill", first_skill + 1)
    assert command[first_skill + 1] == str(skill)
    assert command[second_skill + 1] == str(guidance)
    assert command.count("--no-skills") == 1


@pytest.mark.asyncio
async def test_runs_one_acp_session_and_preserves_unknown_metadata(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    secret = "super-secret-provider-value"
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Use the current world actor until the task is complete.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_SECRET_TOKEN": secret},
    )

    assert result.session_state == "ended"
    assert result.stop_reason == "end_turn"
    assert result.session_id == "fake-session-1"
    assert result.exit_code == 0
    assert result.prime_version == PRIME_AGENT_TESTED_VERSION
    assert result.protocol_version == 1
    assert result.agent_name == "prime-agent"
    assert result.agent_capabilities is not None
    assert len(result.updates) == 1
    assert result.usage.complete
    assert result.usage.model_calls == 1
    assert result.usage.total_tokens == 20
    assert result.usage.cost_usd == Decimal("0.25")
    assert result.topology.root_sessions == 1
    assert result.topology.child_sessions == 0
    assert not result.benchmark_valid
    inbound = result.paths.inbound_file.read_text(encoding="utf-8")
    outbound = result.paths.outbound_file.read_text(encoding="utf-8")
    assert inbound.count('"method":"session/new"') == 1
    assert "futureInitializeMetadata" in outbound
    assert "unknownSessionKey" in outbound
    assert "futurePromptMetadata" in outbound
    assert "unknownUpdateKey" in outbound
    assert "unknownNotificationKey" in outbound
    assert secret not in result.paths.stderr_file.read_text(encoding="utf-8")
    provenance = json.loads(result.paths.run_file.read_text(encoding="utf-8"))
    assert provenance["actor_principal_scope"] == "prime-session-composite"
    assert provenance["isolation"] == "development_same_user"
    assert provenance["benchmark_valid"] is False
    assert provenance["runtime_home_scope"] == "actor-workspace"
    assert provenance["usage"]["cost_usd"] == "0.25"
    assert provenance["acp_sdk_version"]
    assert provenance["skills"] == [
        {
            "name": "aec-world",
            "order": 0,
            "sha256": provenance["skill_sha256"],
        }
    ]
    assert str(skill) not in json.dumps(provenance)
    assert "<skill:aec-world>" in provenance["command"]
    assert "environment" not in provenance
    assert (evidence / "prime-session.jsonl").is_file()
    assert "fake-assistant-1" in (evidence / "prime-session.jsonl").read_text(encoding="utf-8")
    observed = json.loads((actor_workspace / "observed-acp.json").read_text(encoding="utf-8"))
    runtime_root = actor_workspace / ".prime-runtime"
    assert observed["home"] == str(runtime_root / "home")
    assert observed["xdg_cache_home"] == str(runtime_root / "cache")
    assert observed["xdg_config_home"] == str(runtime_root / "config")
    assert observed["xdg_data_home"] == str(runtime_root / "data")


@pytest.mark.asyncio
async def test_rejects_missing_duplicate_external_and_overlapping_skills(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    duplicate = actor_workspace / ".alternate" / "aec-world"
    duplicate.mkdir(parents=True)
    (duplicate / "SKILL.md").write_text(
        "---\nname: aec-world\ndescription: Duplicate test skill.\n---\n",
        encoding="utf-8",
    )
    outer = actor_workspace / ".overlap" / "outer"
    inner = outer / "inner"
    inner.mkdir(parents=True)
    (outer / "SKILL.md").write_text(
        "---\nname: outer\ndescription: Outer test skill.\n---\n",
        encoding="utf-8",
    )
    (inner / "SKILL.md").write_text(
        "---\nname: inner\ndescription: Inner test skill.\n---\n",
        encoding="utf-8",
    )
    external = tmp_path / "external"
    external.mkdir()
    (external / "SKILL.md").write_text(
        "---\nname: external\ndescription: External test skill.\n---\n",
        encoding="utf-8",
    )
    executable = str(_fake_prime_agent(tmp_path))

    async def run_with(skills: tuple[Path, ...], evidence_name: str) -> None:
        await run_prime_acp_session(
            actor_workspace=actor_workspace,
            evidence_directory=evidence / evidence_name,
            skill_directories=skills,
            instruction="Act once.",
            model="anthropic/test",
            actor_environment={
                WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
                WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
            },
            isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
            limits=_limits(),
            executable=executable,
            environment=os.environ,
        )

    with pytest.raises(FileNotFoundError, match="does not exist"):
        await run_with((skill, actor_workspace / "missing"), "missing")
    with pytest.raises(ValueError, match="duplicated"):
        await run_with((skill, duplicate), "duplicate")
    with pytest.raises(PrimeAcpIsolationError, match="under the actor workspace"):
        await run_with((skill, external), "external")
    with pytest.raises(PrimeAcpIsolationError, match="must not overlap"):
        await run_with((outer, inner), "overlap")
    assert not (actor_workspace / "observed-acp.json").exists()


@pytest.mark.asyncio
async def test_normalizes_child_topology_and_refinement_metadata(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Record evidence.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "topology-refinement"},
    )

    assert result.topology.root_sessions == 1
    assert result.topology.child_sessions == 1
    assert result.refinement.events == 1
    assert result.refinement.completed == 1
    assert result.refinement.failed == 0
    assert "kept raw" in result.paths.outbound_file.read_text(encoding="utf-8")
    assert sorted(path.name for path in evidence.glob("prime-session*.jsonl")) == [
        "prime-session-2.jsonl",
        "prime-session.jsonl",
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("limits", "expected_reason"),
    [
        (PrimeAcpLimits(1, 1_000, Decimal("10"), 2), "max_model_calls"),
        (PrimeAcpLimits(10, 20, Decimal("10"), 2), "max_tokens"),
        (PrimeAcpLimits(10, 1_000, Decimal("0.25"), 2), "max_cost_usd"),
    ],
)
async def test_usage_limit_cancels_the_active_prime_prompt(
    tmp_path: Path,
    limits: PrimeAcpLimits,
    expected_reason: str,
) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Keep working.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=limits,
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "budget"},
    )

    assert result.limit_reason == expected_reason
    assert result.usage.model_calls == 1
    assert '"method":"session/cancel"' in result.paths.inbound_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_fails_closed_when_prime_session_accounting_is_malformed(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Act once.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "malformed-session"},
    )

    assert result.session_state == "failed"
    assert result.error is not None
    assert "malformed JSON" in result.error


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["malformed", "unsupported", "missing-capabilities"])
async def test_fails_closed_on_malformed_or_unsupported_acp(tmp_path: Path, scenario: str) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Act once.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(wall_seconds=2),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": scenario},
    )

    assert result.session_state == "failed"
    assert result.benchmark_valid is False
    assert result.error is not None


@pytest.mark.asyncio
async def test_timeout_cancels_then_reaps_the_prime_process(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Wait indefinitely.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(wall_seconds=0.5),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "timeout"},
    )

    assert result.session_state == "cancelled"
    assert result.timed_out
    assert result.exit_code is not None
    assert '"method":"session/cancel"' in result.paths.inbound_file.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_process_exit_during_prompt_is_a_failed_session(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="Act.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: "/private/tmp/scoped-actor.sock",
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        limits=_limits(wall_seconds=2),
        executable=str(_fake_prime_agent(tmp_path)),
        environment={**os.environ, "FAKE_ACP_SCENARIO": "process-exit"},
    )

    assert result.session_state == "failed"
    assert result.exit_code == 7
    assert result.stop_reason is None


def test_macos_profile_denies_repo_and_private_world_but_allows_scoped_actor(tmp_path: Path) -> None:
    actor_workspace, _skill, _evidence = _workspace(tmp_path)
    executable = tmp_path / "prime-install" / "bin" / "prime-agent"
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")
    world = tmp_path / "world-repository"
    socket_path = tmp_path / "socket" / "actor.sock"

    profile = build_macos_sandbox_profile(
        actor_workspace=actor_workspace,
        executable=executable,
        actor_socket=socket_path,
        private_paths=(world,),
    )

    assert str(Path(__file__).resolve().parents[2]) in profile
    assert str(world.resolve()) in profile
    assert str(actor_workspace.resolve()) in profile
    assert str(socket_path.parent.resolve()) in profile


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt boundary")
def test_macos_profile_enforces_the_filesystem_boundary(tmp_path: Path) -> None:
    actor_workspace, _skill, _evidence = _workspace(tmp_path)
    visible = actor_workspace / "visible.txt"
    visible.write_text("visible", encoding="utf-8")
    repository_file = Path(__file__).resolve().parents[2] / "README.md"
    executable = Path(sys.executable)
    profile_path = tmp_path / "profile.sb"
    profile_path.write_text(
        build_macos_sandbox_profile(
            actor_workspace=actor_workspace,
            executable=executable,
            actor_socket=tmp_path / "socket" / "actor.sock",
            private_paths=(),
        ),
        encoding="utf-8",
    )

    allowed = subprocess.run(
        ["/usr/bin/sandbox-exec", "-f", str(profile_path), "/bin/cat", str(visible)],
        check=False,
        capture_output=True,
        text=True,
    )
    denied = subprocess.run(
        ["/usr/bin/sandbox-exec", "-f", str(profile_path), "/bin/cat", str(repository_file)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert allowed.returncode == 0
    assert allowed.stdout == "visible"
    assert denied.returncode != 0


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "darwin", reason="macOS Seatbelt boundary")
async def test_macos_sandboxed_acp_run_is_benchmark_valid(tmp_path: Path) -> None:
    actor_workspace, skill, evidence = _workspace(tmp_path)
    result = await run_prime_acp_session(
        actor_workspace=actor_workspace,
        evidence_directory=evidence,
        skill_directories=(skill,),
        instruction="End the turn.",
        model="anthropic/test",
        actor_environment={
            WORLD_ACTOR_SOCKET_ENV: str(tmp_path / "socket" / "actor.sock"),
            WORLD_ACTOR_CAPABILITY_ENV: "scoped-capability-secret",
        },
        isolation=PrimeAcpIsolation.MACOS_SANDBOX,
        private_paths=(tmp_path / "private-world",),
        limits=_limits(wall_seconds=2),
        executable=str(_fake_prime_agent(tmp_path)),
        environment=os.environ,
    )

    assert result.session_state == "ended"
    assert result.exit_code == 0
    assert result.benchmark_valid
    assert not (evidence / ".prime-sandbox.sb").exists()
