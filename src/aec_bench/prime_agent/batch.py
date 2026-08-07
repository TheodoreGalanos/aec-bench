# ABOUTME: Runs the separately installed Prime Agent executable for one staged artifact-task workspace.
# ABOUTME: Owns process isolation, timeout cleanup, secret-redacted evidence, and compact run provenance.

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO

from aec_bench.prime_agent.events import PrimeEvents, PrimeEventStreamError, parse_prime_events

PRIME_AGENT_TESTED_VERSION = "0.7.0"
_VERSION_PATTERN = re.compile(r"(?<!\d)(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)")
_SECRET_NAME_PARTS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "CREDENTIAL", "ACCESS_KEY", "PRIVATE_KEY")
_REDACTION = b"[REDACTED]"


class PrimeExecutableNotFoundError(FileNotFoundError):
    """Raised when the requested upstream Prime Agent executable is unavailable."""


@dataclass(frozen=True)
class PrimePaths:
    prime_dir: Path
    state_dir: Path
    session_dir: Path
    events_file: Path
    stderr_file: Path
    run_file: Path


@dataclass(frozen=True)
class PrimeRun:
    """Outcome and normalized evidence for one Prime process invocation."""

    command: tuple[str, ...]
    prime_version: str
    paths: PrimePaths
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    exit_code: int | None
    timed_out: bool
    events: PrimeEvents | None
    completion: str
    error: str | None


def prime_paths(workspace: Path) -> PrimePaths:
    workspace = workspace.resolve()
    prime_dir = workspace / "logs" / "prime"
    return PrimePaths(
        prime_dir=prime_dir,
        state_dir=prime_dir / "state",
        session_dir=prime_dir / "sessions",
        events_file=workspace / "prime-events.jsonl",
        stderr_file=workspace / "prime-stderr.log",
        run_file=workspace / "prime-run.json",
    )


def resolve_prime_executable(executable: str = "prime-agent") -> Path:
    """Resolve one executable without invoking a shell or importing Prime internals."""
    has_separator = os.sep in executable or (os.altsep is not None and os.altsep in executable)
    if has_separator:
        candidate = Path(executable).expanduser().resolve()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    else:
        resolved = shutil.which(executable)
        if resolved is not None:
            return Path(resolved).resolve()
    raise PrimeExecutableNotFoundError(
        f"Prime Agent executable '{executable}' was not found or is not executable. "
        "Install Prime Agent separately and ensure 'prime-agent' is on PATH."
    )


def build_prime_command(
    *,
    executable: Path,
    model: str,
    instruction: str,
    workspace: Path,
    session_dir: Path,
) -> list[str]:
    """Build the tested Prime v0.7.0 JSON command with ambient resources disabled."""
    return [
        str(executable),
        "--mode",
        "json",
        "--model",
        model,
        "--cwd",
        str(workspace),
        "--session-dir",
        str(session_dir),
        "--no-skills",
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--offline",
        "--",
        instruction,
    ]


def _prime_environment(paths: PrimePaths, environment: Mapping[str, str] | None) -> dict[str, str]:
    env = dict(os.environ if environment is None else environment)
    env.update(
        {
            "PRIME_AGENT_CODING_AGENT_DIR": str(paths.state_dir),
            "PRIME_AGENT_SESSION_DIR": str(paths.session_dir),
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
        }
    )
    return env


def _secret_values(environment: Mapping[str, str]) -> tuple[str, ...]:
    values: set[str] = set()
    for name, value in environment.items():
        if not any(part in name.upper() for part in _SECRET_NAME_PARTS):
            continue
        if len(value) >= 8:
            values.add(value)
        values.update(line for line in value.splitlines() if len(line) >= 8)
    return tuple(sorted(values, key=len, reverse=True))


def redact_prime_bytes(
    data: bytes,
    environment: Mapping[str, str],
    *,
    additional_values: tuple[str, ...] = (),
) -> bytes:
    """Redact credential-like environment values and explicit transport secrets."""
    redacted = data
    values = tuple(sorted({*_secret_values(environment), *additional_values}, key=len, reverse=True))
    for value in values:
        literal = value.encode("utf-8", errors="ignore")
        escaped = json.dumps(value, ensure_ascii=False)[1:-1].encode("utf-8")
        if literal:
            redacted = redacted.replace(literal, _REDACTION)
        if escaped and escaped != literal:
            redacted = redacted.replace(escaped, _REDACTION)
    return redacted


def _capture_stream(
    source: BinaryIO,
    destination: Path,
    *,
    environment: Mapping[str, str],
    errors: list[str],
) -> None:
    """Drain one process pipe into a durable artifact while preserving line order."""
    try:
        with destination.open("wb") as sink:
            while line := source.readline():
                sink.write(redact_prime_bytes(line, environment))
                sink.flush()
    except OSError:
        errors.append(f"could not preserve {destination.name}")
        while source.read(65536):
            pass
    finally:
        source.close()


def _stop_process_tree(process: subprocess.Popen[bytes], *, grace_seconds: float = 0.25) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=grace_seconds)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        return
    process.wait()


def _prime_version(executable: Path, *, workspace: Path, environment: Mapping[str, str]) -> str:
    try:
        process = subprocess.Popen(
            [str(executable), "--version"],
            cwd=workspace,
            env=dict(environment),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError:
        return "unknown"
    try:
        stdout, _stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        _stop_process_tree(process)
        process.communicate()
        return "unknown"
    if process.returncode != 0:
        return "unknown"
    match = _VERSION_PATTERN.search(stdout.decode("utf-8", errors="replace"))
    return match.group(1) if match is not None else "unknown"


def _workspace_has_output(workspace: Path) -> bool:
    output = workspace / "output.md"
    if not output.is_file():
        return False
    try:
        return bool(output.read_text(encoding="utf-8", errors="replace").strip())
    except OSError:
        return False


def redact_prime_session_artifacts(paths: PrimePaths, environment: Mapping[str, str]) -> None:
    """Remove inherited credential values before Prime session files become durable run artifacts."""
    for session_artifact in paths.session_dir.rglob("*"):
        if not session_artifact.is_file():
            continue
        try:
            original = session_artifact.read_bytes()
            redacted = redact_prime_bytes(original, environment)
            if redacted != original:
                session_artifact.write_bytes(redacted)
        except OSError:
            continue


def _completion(
    *,
    timed_out: bool,
    exit_code: int | None,
    events: PrimeEvents | None,
    parser_error: str | None,
    workspace: Path,
) -> tuple[str, str | None]:
    if timed_out:
        return "timed_out", "Prime Agent exceeded the configured timeout"
    if exit_code != 0:
        return "process_failed", f"Prime Agent exited with code {exit_code}"
    if parser_error is not None:
        return "protocol_failed", parser_error
    if events is None:
        return "protocol_failed", "Prime Agent produced no usable event stream"
    if events.assistant_error is not None:
        return "provider_failed", events.assistant_error
    if not _workspace_has_output(workspace) and not events.final_assistant_text:
        return "missing_output", "Prime Agent completed without a non-empty output.md or final assistant text"
    return "completed", None


def _write_run_artifact(run: PrimeRun, *, model_requested: str, instruction: str, parser_error: str | None) -> None:
    events = run.events
    sanitized_command = list(run.command)
    if sanitized_command:
        sanitized_command[-1] = "<instruction>"
    payload = {
        "prime_version": run.prime_version,
        "prime_version_tested": PRIME_AGENT_TESTED_VERSION,
        "event_stream_version": events.stream_version if events is not None else None,
        "session_id": events.session_id if events is not None else None,
        "model_requested": model_requested,
        "model_resolved": events.resolved_model if events is not None else None,
        "command": sanitized_command,
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "state_directory": "logs/prime/state",
        "session_directory": "logs/prime/sessions",
        "ambient_resources_disabled": True,
        "exit_code": run.exit_code,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat(),
        "elapsed_seconds": run.elapsed_seconds,
        "event_count": len(events.events) if events is not None else 0,
        "compaction_count": events.compaction_count if events is not None else 0,
        "provider": events.provider if events is not None else None,
        "terminal_event": events.terminal_event if events is not None else None,
        "parser_error": parser_error,
        "timed_out": run.timed_out,
        "completion": run.completion,
        "error": run.error,
    }
    run.paths.run_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_prime_agent(
    *,
    workspace: Path,
    instruction: str,
    model: str,
    timeout_seconds: float,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
) -> PrimeRun:
    """Run Prime once in JSON mode and preserve non-secret process/protocol evidence."""
    resolved_workspace = workspace.resolve()
    resolved_executable = resolve_prime_executable(executable)
    paths = prime_paths(resolved_workspace)
    paths.state_dir.mkdir(parents=True, exist_ok=True)
    paths.session_dir.mkdir(parents=True, exist_ok=True)
    env = _prime_environment(paths, environment)
    prime_version = _prime_version(resolved_executable, workspace=resolved_workspace, environment=env)
    command = build_prime_command(
        executable=resolved_executable,
        model=model,
        instruction=instruction,
        workspace=resolved_workspace,
        session_dir=paths.session_dir,
    )

    started_at = datetime.now(UTC)
    started_monotonic = time.monotonic()
    try:
        process = subprocess.Popen(
            command,
            cwd=resolved_workspace,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name == "posix",
        )
    except OSError as exc:
        finished_at = datetime.now(UTC)
        error_detail = exc.strerror or type(exc).__name__
        start_error = f"Prime Agent could not be started: {error_detail}"
        paths.events_file.write_bytes(b"")
        paths.stderr_file.write_bytes(redact_prime_bytes((start_error + "\n").encode(), env))
        run = PrimeRun(
            command=tuple(command),
            prime_version=prime_version,
            paths=paths,
            started_at=started_at,
            finished_at=finished_at,
            elapsed_seconds=time.monotonic() - started_monotonic,
            exit_code=None,
            timed_out=False,
            events=None,
            completion="process_failed",
            error=start_error,
        )
        _write_run_artifact(run, model_requested=model, instruction=instruction, parser_error=None)
        return run
    assert process.stdout is not None
    assert process.stderr is not None
    capture_errors: list[str] = []
    capture_threads = [
        threading.Thread(
            target=_capture_stream,
            args=(process.stdout, paths.events_file),
            kwargs={"environment": env, "errors": capture_errors},
            name="prime-agent-stdout",
        ),
        threading.Thread(
            target=_capture_stream,
            args=(process.stderr, paths.stderr_file),
            kwargs={"environment": env, "errors": capture_errors},
            name="prime-agent-stderr",
        ),
    ]
    for capture_thread in capture_threads:
        capture_thread.start()
    timed_out = False
    interrupted = False
    try:
        process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_process_tree(process)
    except KeyboardInterrupt:
        interrupted = True
        _stop_process_tree(process)
    finally:
        for capture_thread in capture_threads:
            capture_thread.join()

    finished_at = datetime.now(UTC)
    elapsed_seconds = time.monotonic() - started_monotonic
    redact_prime_session_artifacts(paths, env)

    parsed_events: PrimeEvents | None = None
    parser_error: str | None = None
    try:
        parsed_events = parse_prime_events(paths.events_file.read_bytes())
    except PrimeEventStreamError as exc:
        parser_error = str(exc)
    if capture_errors:
        parser_error = "; ".join(capture_errors)

    completion: str
    error: str | None
    if interrupted:
        completion, error = "interrupted", "Prime Agent was interrupted"
    else:
        completion, error = _completion(
            timed_out=timed_out,
            exit_code=process.returncode,
            events=parsed_events,
            parser_error=parser_error,
            workspace=resolved_workspace,
        )
    run = PrimeRun(
        command=tuple(command),
        prime_version=prime_version,
        paths=paths,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=elapsed_seconds,
        exit_code=process.returncode,
        timed_out=timed_out,
        events=parsed_events,
        completion=completion,
        error=error,
    )
    _write_run_artifact(run, model_requested=model, instruction=instruction, parser_error=parser_error)
    if interrupted:
        raise KeyboardInterrupt
    return run
