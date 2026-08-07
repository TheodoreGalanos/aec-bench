# ABOUTME: Exercises the Prime Agent subprocess boundary with a deterministic fake executable.
# ABOUTME: Proves command isolation, evidence capture, redaction, failures, and process-tree timeout cleanup.

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest

from aec_bench.prime_agent.batch import (
    PRIME_AGENT_TESTED_VERSION,
    PrimeExecutableNotFoundError,
    build_prime_command,
    prime_paths,
    run_prime_agent,
)


def _fake_prime_agent(tmp_path: Path) -> Path:
    executable = tmp_path / "prime agent; literal"
    executable.write_text(
        f"""#!{sys.executable}
import json
import os
from pathlib import Path
import subprocess
import sys
import time

if "--version" in sys.argv:
    print("prime-agent {PRIME_AGENT_TESTED_VERSION}")
    raise SystemExit(0)

scenario = os.environ.get("FAKE_PRIME_SCENARIO", "direct")
observed = {{
    "argv": sys.argv[1:],
    "cwd": os.getcwd(),
    "config_dir": os.environ.get("PRIME_AGENT_CODING_AGENT_DIR"),
    "session_dir": os.environ.get("PRIME_AGENT_SESSION_DIR"),
    "offline": os.environ.get("PI_OFFLINE"),
    "skip_version_check": os.environ.get("PI_SKIP_VERSION_CHECK"),
}}
Path("observed-prime.json").write_text(json.dumps(observed), encoding="utf-8")
session_dir = Path(os.environ["PRIME_AGENT_SESSION_DIR"])
session_dir.mkdir(parents=True, exist_ok=True)
(session_dir / "session-record.jsonl").write_text(
    json.dumps({{"type": "session", "diagnostic": os.environ.get("FAKE_SECRET_TOKEN", "none")}}) + "\\n",
    encoding="utf-8",
)

header = {{"type": "session", "version": 3, "id": "fake-session", "cwd": os.getcwd()}}
message = {{
    "role": "assistant",
    "content": [{{"type": "text", "text": "Fallback answer"}}],
    "provider": "anthropic",
    "model": "anthropic/requested",
    "responseModel": "anthropic/resolved",
    "responseId": "fake-response",
    "usage": {{"input": 12, "output": 4, "cacheRead": 2, "cacheWrite": 1}},
    "stopReason": "stop",
    "timestamp": 1786064524000,
}}

print(json.dumps(header), flush=True)
print(json.dumps({{"type": "agent_start"}}), flush=True)
if scenario == "timeout":
    marker = os.environ["FAKE_CHILD_MARKER"]
    child_code = f"import time; from pathlib import Path; time.sleep(0.5); Path({{marker!r}}).touch()"
    subprocess.Popen([sys.executable, "-c", child_code])
    time.sleep(60)
if scenario == "nonzero":
    print("fake non-zero diagnostic", file=sys.stderr, flush=True)
    raise SystemExit(7)
if scenario == "malformed":
    print("not-json", flush=True)
    raise SystemExit(0)
if scenario == "direct":
    Path("output.md").write_text("Direct artifact\\n", encoding="utf-8")
if scenario == "missing":
    message["content"] = []
print(json.dumps({{"type": "turn_start"}}), flush=True)
print(json.dumps({{"type": "message_end", "message": message}}), flush=True)
print(json.dumps({{"type": "turn_end", "message": message, "toolResults": []}}), flush=True)
print(json.dumps({{"type": "agent_end", "messages": [message]}}), flush=True)
print("diagnostic " + os.environ.get("FAKE_SECRET_TOKEN", "none"), file=sys.stderr, flush=True)
""",
        encoding="utf-8",
    )
    executable.chmod(0o755)
    return executable


def _environment(**values: str) -> dict[str, str]:
    return {**os.environ, **values}


def test_builds_documented_json_command_as_an_argument_list(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    paths = prime_paths(workspace)
    executable = Path("/opt/prime/bin/prime-agent")

    command = build_prime_command(
        executable=executable,
        model="anthropic/test-model",
        instruction="Write output.md; $(touch should-not-run)",
        workspace=workspace,
        session_dir=paths.session_dir,
    )

    assert command == [
        "/opt/prime/bin/prime-agent",
        "--mode",
        "json",
        "--model",
        "anthropic/test-model",
        "--cwd",
        str(workspace),
        "--session-dir",
        str(paths.session_dir),
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--offline",
        "--",
        "Write output.md; $(touch should-not-run)",
    ]


def test_runs_fake_executable_with_isolated_state_and_preserves_redacted_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    executable = _fake_prime_agent(tmp_path)

    result = run_prime_agent(
        workspace=workspace,
        instruction="Write output.md",
        model="anthropic/requested",
        timeout_seconds=5,
        executable=str(executable),
        environment=_environment(
            FAKE_PRIME_SCENARIO="direct",
            FAKE_SECRET_TOKEN="super-secret-value\nsecond-secret-line",
        ),
    )

    assert result.completion == "completed"
    assert result.exit_code == 0
    assert result.prime_version == PRIME_AGENT_TESTED_VERSION
    assert result.events is not None
    assert result.events.session_id == "fake-session"
    assert (workspace / "output.md").read_text(encoding="utf-8") == "Direct artifact\n"

    observed = json.loads((workspace / "observed-prime.json").read_text(encoding="utf-8"))
    paths = prime_paths(workspace)
    assert observed["cwd"] == str(workspace)
    assert observed["config_dir"] == str(paths.state_dir)
    assert observed["session_dir"] == str(paths.session_dir)
    assert observed["offline"] == "1"
    assert observed["skip_version_check"] == "1"
    assert observed["argv"] == list(result.command[1:])
    assert (paths.session_dir / "session-record.jsonl").exists()
    session_evidence = (paths.session_dir / "session-record.jsonl").read_text(encoding="utf-8")
    assert "super-secret-value" not in session_evidence
    assert "second-secret-line" not in session_evidence

    event_lines = (workspace / "prime-events.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(event_lines[0])["type"] == "session"
    stderr = (workspace / "prime-stderr.log").read_text(encoding="utf-8")
    assert stderr == "diagnostic [REDACTED]\n[REDACTED]\n"
    assert "super-secret-value" not in (workspace / "prime-run.json").read_text(encoding="utf-8")
    assert "second-secret-line" not in stderr

    provenance = json.loads((workspace / "prime-run.json").read_text(encoding="utf-8"))
    assert provenance["model_requested"] == "anthropic/requested"
    assert provenance["model_resolved"] == "anthropic/resolved"
    assert provenance["command"][-1] == "<instruction>"
    assert provenance["instruction_sha256"]
    assert "environment" not in provenance


def test_accepts_completed_final_text_when_agent_did_not_write_output(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = run_prime_agent(
        workspace=workspace,
        instruction="Answer",
        model="anthropic/requested",
        timeout_seconds=5,
        executable=str(_fake_prime_agent(tmp_path)),
        environment=_environment(FAKE_PRIME_SCENARIO="fallback"),
    )

    assert result.completion == "completed"
    assert not (workspace / "output.md").exists()
    assert result.events is not None
    assert result.events.final_assistant_text == "Fallback answer"


@pytest.mark.parametrize(
    ("scenario", "completion", "exit_code"),
    [
        ("nonzero", "process_failed", 7),
        ("malformed", "protocol_failed", 0),
        ("missing", "missing_output", 0),
    ],
)
def test_records_explicit_failed_outcomes(
    tmp_path: Path,
    scenario: str,
    completion: str,
    exit_code: int,
) -> None:
    workspace = tmp_path / scenario
    workspace.mkdir()

    result = run_prime_agent(
        workspace=workspace,
        instruction="Answer",
        model="anthropic/requested",
        timeout_seconds=5,
        executable=str(_fake_prime_agent(tmp_path)),
        environment=_environment(FAKE_PRIME_SCENARIO=scenario),
    )

    assert result.completion == completion
    assert result.exit_code == exit_code
    assert result.error
    provenance = json.loads((workspace / "prime-run.json").read_text(encoding="utf-8"))
    assert provenance["completion"] == completion
    assert provenance["error"] == result.error


def test_timeout_stops_the_prime_process_tree_and_preserves_partial_evidence(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    marker = tmp_path / "child-survived"

    result = run_prime_agent(
        workspace=workspace,
        instruction="Wait",
        model="anthropic/requested",
        timeout_seconds=0.05,
        executable=str(_fake_prime_agent(tmp_path)),
        environment=_environment(FAKE_PRIME_SCENARIO="timeout", FAKE_CHILD_MARKER=str(marker)),
    )
    time.sleep(0.7)

    assert result.completion == "timed_out"
    assert result.timed_out is True
    assert result.exit_code is not None
    assert not marker.exists()
    assert (workspace / "prime-events.jsonl").exists()
    assert (workspace / "prime-stderr.log").exists()
    assert json.loads((workspace / "prime-run.json").read_text(encoding="utf-8"))["completion"] == "timed_out"


def test_missing_executable_is_a_clear_setup_error(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(PrimeExecutableNotFoundError, match="prime-agent"):
        run_prime_agent(
            workspace=workspace,
            instruction="Answer",
            model="anthropic/requested",
            timeout_seconds=1,
            executable="definitely-not-installed-prime-agent",
        )
