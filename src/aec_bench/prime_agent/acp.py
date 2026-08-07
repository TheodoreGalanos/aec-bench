# ABOUTME: Drives one externally controlled Prime Agent session over strict ACP/NDJSON.
# ABOUTME: Owns process cleanup, raw evidence, optional macOS isolation, and fail-closed protocol handling.

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib
import json
import os
import re
import signal
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, NoReturn

from aec_bench.prime_agent.batch import (
    PRIME_AGENT_TESTED_VERSION,
    redact_prime_bytes,
    resolve_prime_executable,
)
from aec_bench.prime_agent.session_evidence import (
    PrimeAcpLimits,
    PrimeAcpRefinement,
    PrimeAcpTopology,
    PrimeAcpUsage,
    PrimeSessionEvidenceError,
    empty_usage,
    read_session_evidence,
    refinement_evidence,
    usage_limit_reason,
    wait_for_usage_limit,
)

_VERSION_PATTERN = re.compile(r"(?<!\d)(\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?)")
_MAX_ACP_MESSAGE_BYTES = 16 * 1024 * 1024
_CANCEL_GRACE_SECONDS = 0.5


class PrimeAcpError(RuntimeError):
    """Base error for a failed Prime ACP session boundary."""


class PrimeAcpDependencyError(PrimeAcpError):
    """Raised when the optional ACP SDK is unavailable."""


class PrimeAcpProtocolError(PrimeAcpError):
    """Raised for malformed, unsupported, or incomplete ACP streams."""


class PrimeAcpIsolationError(PrimeAcpError):
    """Raised when a benchmark-valid process boundary cannot be enforced."""


class PrimeAcpIsolation(StrEnum):
    DEVELOPMENT_SAME_USER = "development_same_user"
    MACOS_SANDBOX = "macos_sandbox"


@dataclass(frozen=True, slots=True)
class PrimeAcpPaths:
    state_dir: Path
    session_dir: Path
    inbound_file: Path
    outbound_file: Path
    stderr_file: Path
    run_file: Path


@dataclass(frozen=True, slots=True)
class PrimeAcpRun:
    """One completed, cancelled, or failed ACP process and its preserved evidence."""

    command: tuple[str, ...]
    prime_version: str
    paths: PrimeAcpPaths
    started_at: datetime
    finished_at: datetime
    elapsed_seconds: float
    exit_code: int | None
    session_id: str | None
    protocol_version: int | None
    agent_name: str | None
    agent_version: str | None
    agent_capabilities: dict[str, Any] | None
    limits: PrimeAcpLimits
    usage: PrimeAcpUsage
    topology: PrimeAcpTopology
    refinement: PrimeAcpRefinement
    limit_reason: str | None
    session_state: str
    stop_reason: str | None
    timed_out: bool
    benchmark_valid: bool
    isolation: PrimeAcpIsolation
    updates: tuple[dict[str, Any], ...]
    error: str | None


def prime_acp_paths(actor_workspace: Path, evidence_directory: Path) -> PrimeAcpPaths:
    actor_workspace = actor_workspace.resolve()
    evidence_directory = evidence_directory.resolve()
    prime_directory = actor_workspace / "logs" / "prime"
    return PrimeAcpPaths(
        state_dir=prime_directory / "state",
        session_dir=prime_directory / "sessions",
        inbound_file=evidence_directory / "prime-acp-in.jsonl",
        outbound_file=evidence_directory / "prime-acp-out.jsonl",
        stderr_file=evidence_directory / "prime-stderr.log",
        run_file=evidence_directory / "prime-run.json",
    )


def build_prime_acp_command(
    *,
    executable: Path,
    model: str,
    actor_workspace: Path,
    session_dir: Path,
    skill_directory: Path,
) -> list[str]:
    """Build Prime's one-session ACP command without using a shell."""
    return [
        str(executable),
        "--mode",
        "acp",
        "--model",
        model,
        "--cwd",
        str(actor_workspace),
        "--session-dir",
        str(session_dir),
        "--no-skills",
        "--skill",
        str(skill_directory),
        "--no-extensions",
        "--no-prompt-templates",
        "--no-themes",
        "--no-context-files",
        "--offline",
    ]


def build_macos_sandbox_profile(
    *,
    actor_workspace: Path,
    executable: Path,
    actor_socket: Path,
    private_paths: Sequence[Path],
) -> str:
    """Create the narrow local macOS profile used for benchmark-valid Prime execution."""
    actor_workspace = actor_workspace.resolve()
    executable = executable.resolve()
    actor_socket = actor_socket.resolve()
    repository_root = Path(__file__).resolve().parents[3]
    protected = {repository_root, *(path.resolve() for path in private_paths)}
    if any(_paths_overlap(actor_workspace, path) for path in protected):
        raise PrimeAcpIsolationError("actor workspace overlaps a protected host path")
    if any(path.is_symlink() for path in actor_workspace.rglob("*")):
        raise PrimeAcpIsolationError("actor workspace must not contain symbolic links")
    install_root = executable.parents[1]
    home = Path.home().resolve()
    rules = [
        "(version 1)",
        "(allow default)",
        f"(deny file-read* file-write* (subpath {_sandbox_quote(home)}))",
        f"(deny file-read* file-write* (subpath {_sandbox_quote(repository_root)}))",
    ]
    rules.extend(f"(deny file-read* file-write* (subpath {_sandbox_quote(path)}))" for path in sorted(protected))
    rules.extend(
        [
            f"(allow file-read* file-write* (subpath {_sandbox_quote(actor_workspace)}))",
            f"(allow file-read* (subpath {_sandbox_quote(install_root)}))",
            f"(allow file-read* file-write* (subpath {_sandbox_quote(actor_socket.parent)}))",
        ]
    )
    return "\n".join(rules) + "\n"


async def run_prime_acp_session(
    *,
    actor_workspace: Path,
    evidence_directory: Path,
    skill_directory: Path,
    instruction: str,
    model: str,
    actor_environment: Mapping[str, str],
    isolation: PrimeAcpIsolation,
    limits: PrimeAcpLimits,
    private_paths: Sequence[Path] = (),
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
) -> PrimeAcpRun:
    """Run one Prime root session and its descendants as one composite actor principal."""
    acp = _load_acp()
    acp_schema = importlib.import_module("acp.schema")
    actor_workspace = actor_workspace.resolve()
    evidence_directory = evidence_directory.resolve()
    skill_directory = skill_directory.resolve()
    if not instruction.strip():
        raise ValueError("Prime ACP instruction must be non-empty")
    if not actor_workspace.is_dir() or not skill_directory.is_dir():
        raise FileNotFoundError("Prime actor workspace and explicit skill must exist")
    if _paths_overlap(actor_workspace, evidence_directory):
        raise PrimeAcpIsolationError("host evidence directory must be outside the actor workspace")

    resolved_executable = resolve_prime_executable(executable)
    paths = prime_acp_paths(actor_workspace, evidence_directory)
    paths.state_dir.mkdir(parents=True, exist_ok=False)
    paths.session_dir.mkdir(parents=True, exist_ok=False)
    evidence_directory.mkdir(parents=True, exist_ok=True)
    for evidence_file in (paths.inbound_file, paths.outbound_file, paths.stderr_file):
        evidence_file.write_bytes(b"")

    env = dict(os.environ if environment is None else environment)
    env.update(actor_environment)
    runtime_home = actor_workspace / ".prime-runtime"
    env.update(
        {
            "HOME": str(runtime_home / "home"),
            "XDG_CACHE_HOME": str(runtime_home / "cache"),
            "XDG_CONFIG_HOME": str(runtime_home / "config"),
            "XDG_DATA_HOME": str(runtime_home / "data"),
            "PRIME_AGENT_CODING_AGENT_DIR": str(paths.state_dir),
            "PRIME_AGENT_SESSION_DIR": str(paths.session_dir),
            "PI_OFFLINE": "1",
            "PI_SKIP_VERSION_CHECK": "1",
        }
    )
    base_command = build_prime_acp_command(
        executable=resolved_executable,
        model=model,
        actor_workspace=actor_workspace,
        session_dir=paths.session_dir,
        skill_directory=skill_directory,
    )
    command = list(base_command)
    sandbox_profile: Path | None = None
    if isolation is PrimeAcpIsolation.MACOS_SANDBOX:
        if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
            raise PrimeAcpIsolationError("benchmark-valid Prime execution requires macOS sandbox-exec")
        socket_value = actor_environment.get("AEC_BENCH_WORLD_ACTOR_SOCKET")
        if not socket_value:
            raise PrimeAcpIsolationError("benchmark-valid Prime execution requires the scoped actor socket")
        profile = build_macos_sandbox_profile(
            actor_workspace=actor_workspace,
            executable=resolved_executable,
            actor_socket=Path(socket_value),
            private_paths=private_paths,
        )
        sandbox_profile = evidence_directory / ".prime-sandbox.sb"
        sandbox_profile.write_text(profile, encoding="utf-8")
        command = ["/usr/bin/sandbox-exec", "-f", str(sandbox_profile), *base_command]
    elif isolation is not PrimeAcpIsolation.DEVELOPMENT_SAME_USER:
        raise PrimeAcpIsolationError(f"unsupported Prime isolation mode: {isolation}")

    redact_values = tuple(value for key, value in actor_environment.items() if "CAPABILITY" in key or "SOCKET" in key)
    started_at = datetime.now(UTC)
    started = time.monotonic()
    deadline = started + limits.max_wall_seconds
    process: asyncio.subprocess.Process | None = None
    connection: Any = None
    stderr_task: asyncio.Task[None] | None = None
    prompt_task: asyncio.Task[Any] | None = None
    limit_task: asyncio.Task[str] | None = None
    session_id: str | None = None
    protocol_version: int | None = None
    agent_name: str | None = None
    agent_version: str | None = None
    agent_capabilities: dict[str, Any] | None = None
    stop_reason: str | None = None
    updates: list[dict[str, Any]] = []
    timed_out = False
    limit_reason: str | None = None
    error: str | None = None
    session_state = "failed"
    prime_version = "unknown"
    try:
        prime_version = await _prime_version(
            command[: -len(base_command)],
            resolved_executable,
            actor_workspace,
            env,
            timeout_seconds=min(_remaining_seconds(deadline), 10),
        )
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=actor_workspace,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=os.name == "posix",
            limit=_MAX_ACP_MESSAGE_BYTES + 1,
        )
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise PrimeAcpProtocolError("Prime ACP process did not expose all stdio streams")
        stderr_task = asyncio.create_task(
            _capture_stderr(process.stderr, paths.stderr_file, env, redact_values),
            name="prime-acp-stderr",
        )
        transport = _StrictNdjsonTransport(
            reader=process.stdout,
            writer=process.stdin,
            inbound_file=paths.inbound_file,
            outbound_file=paths.outbound_file,
            environment=env,
            redact_values=redact_values,
        )
        client = _AecBenchAcpClient(updates)
        connection = acp.connect_to_agent(client, transport)
        initialize_timeout = min(_remaining_seconds(deadline), 30)
        initialized = await asyncio.wait_for(
            connection.initialize(
                protocol_version=acp.PROTOCOL_VERSION,
                client_info=acp_schema.Implementation(name="aec-bench", version="0.1.0"),
            ),
            timeout=initialize_timeout,
        )
        _validate_raw_initialize(transport.received_messages)
        _validate_initialize(initialized, acp.PROTOCOL_VERSION)
        protocol_version = initialized.protocol_version
        agent_name = initialized.agent_info.name
        agent_version = initialized.agent_info.version
        agent_capabilities = initialized.agent_capabilities.model_dump(
            mode="json", by_alias=True, exclude_none=True, warnings=False
        )
        new_session_timeout = min(_remaining_seconds(deadline), 30)
        session = await asyncio.wait_for(
            connection.new_session(cwd=str(actor_workspace), additional_directories=[], mcp_servers=[]),
            timeout=new_session_timeout,
        )
        if not isinstance(session.session_id, str) or not session.session_id.strip():
            raise PrimeAcpProtocolError("Prime ACP returned an empty session ID")
        session_id = session.session_id
        prompt_task = asyncio.create_task(
            connection.prompt(session_id=session_id, prompt=[acp.text_block(instruction)]),
            name="prime-acp-prompt",
        )
        limit_task = asyncio.create_task(
            wait_for_usage_limit(paths.session_dir, limits),
            name="prime-acp-usage-limits",
        )
        done, _pending = await asyncio.wait(
            {prompt_task, limit_task},
            timeout=_remaining_seconds(deadline),
            return_when=asyncio.FIRST_COMPLETED,
        )
        if prompt_task in done:
            prompt = prompt_task.result()
        elif limit_task in done:
            limit_reason = limit_task.result()
            await connection.cancel(session_id=session_id)
            try:
                prompt = await asyncio.wait_for(prompt_task, timeout=_CANCEL_GRACE_SECONDS)
            except TimeoutError:
                prompt_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await prompt_task
                raise PrimeAcpProtocolError("Prime ACP prompt did not stop after limit cancellation") from None
        else:
            timed_out = True
            limit_reason = "max_wall_seconds"
            await connection.cancel(session_id=session_id)
            try:
                prompt = await asyncio.wait_for(prompt_task, timeout=_CANCEL_GRACE_SECONDS)
            except TimeoutError:
                prompt_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await prompt_task
                raise PrimeAcpProtocolError("Prime ACP prompt did not stop after cancellation") from None
        limit_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await limit_task
        stop_reason = str(prompt.stop_reason)
        if client.protocol_error is not None:
            raise client.protocol_error
        session_state = "cancelled" if stop_reason == "cancelled" or timed_out else "ended"
        await asyncio.wait_for(connection.close_session(session_id=session_id), timeout=10)
    except TimeoutError as exc:
        timed_out = True
        limit_reason = "max_wall_seconds"
        error = f"{type(exc).__name__}: Prime ACP wall-clock budget expired"
        session_state = "cancelled" if session_id is not None else "failed"
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        session_state = "cancelled" if timed_out else "failed"
    finally:
        for task in (prompt_task, limit_task):
            if task is not None and not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        if connection is not None:
            with contextlib.suppress(Exception):
                await connection.close()
        if process is not None:
            await _reap_process(process)
        if stderr_task is not None:
            with contextlib.suppress(Exception):
                await stderr_task
        _redact_session_artifacts(paths.session_dir, env, redact_values)
        if sandbox_profile is not None:
            sandbox_profile.unlink(missing_ok=True)

    usage = empty_usage()
    topology = PrimeAcpTopology(root_sessions=0, child_sessions=0)
    if session_id is not None:
        try:
            session_evidence = read_session_evidence(paths.session_dir, allow_partial=False)
            assert session_evidence is not None
            usage, topology = session_evidence
        except PrimeSessionEvidenceError as exc:
            error = error or f"{type(exc).__name__}: {exc}"
            session_state = "failed"
    refinement = refinement_evidence(updates)
    if usage.complete:
        limit_reason = limit_reason or usage_limit_reason(usage, limits)

    exit_code = process.returncode if process is not None else None
    if exit_code not in (None, 0) and not timed_out:
        session_state = "failed"
        error = error or f"Prime Agent exited with status {exit_code}"
    if stop_reason is None and error is None:
        session_state = "failed"
        error = "Prime ACP session produced no terminal stop reason"
    if error is not None:
        error = redact_prime_bytes(
            error.encode("utf-8"),
            env,
            additional_values=redact_values,
        ).decode("utf-8", errors="replace")
    finished_at = datetime.now(UTC)
    run = PrimeAcpRun(
        command=tuple(command),
        prime_version=prime_version,
        paths=paths,
        started_at=started_at,
        finished_at=finished_at,
        elapsed_seconds=time.monotonic() - started,
        exit_code=exit_code,
        session_id=session_id,
        protocol_version=protocol_version,
        agent_name=agent_name,
        agent_version=agent_version,
        agent_capabilities=agent_capabilities,
        limits=limits,
        usage=usage,
        topology=topology,
        refinement=refinement,
        limit_reason=limit_reason,
        session_state=session_state,
        stop_reason=stop_reason,
        timed_out=timed_out,
        benchmark_valid=(
            isolation is PrimeAcpIsolation.MACOS_SANDBOX
            and session_state != "failed"
            and error is None
            and usage.complete
        ),
        isolation=isolation,
        updates=tuple(updates),
        error=error,
    )
    _write_run_provenance(
        run,
        model=model,
        instruction=instruction,
        actor_workspace=actor_workspace,
        skill_directory=skill_directory,
        sandbox_profile=sandbox_profile,
    )
    return run


class _StrictNdjsonTransport:
    def __init__(
        self,
        *,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        inbound_file: Path,
        outbound_file: Path,
        environment: Mapping[str, str],
        redact_values: tuple[str, ...],
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._inbound_file = inbound_file
        self._outbound_file = outbound_file
        self._environment = environment
        self._redact_values = redact_values
        self._closed = False
        self.received_messages: list[dict[str, Any]] = []

    async def send(self, message: dict[str, Any]) -> None:
        if self._closed:
            raise ConnectionError("Prime ACP transport is closed")
        line = json.dumps(message, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"
        self._preserve(self._inbound_file, line)
        self._writer.write(line)
        await self._writer.drain()

    async def receive(self) -> dict[str, Any] | None:
        try:
            line = await self._reader.readuntil(b"\n")
        except asyncio.IncompleteReadError as exc:
            if not exc.partial:
                return None
            line = exc.partial
        except asyncio.LimitOverrunError as exc:
            raise PrimeAcpProtocolError("Prime ACP message exceeded the stream limit") from exc
        if len(line) > _MAX_ACP_MESSAGE_BYTES:
            raise PrimeAcpProtocolError("Prime ACP message is too large")
        if not line.endswith(b"\n") or not line.strip():
            raise PrimeAcpProtocolError("Prime ACP emitted an incomplete or blank frame")
        self._preserve(self._outbound_file, line)
        try:
            message = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PrimeAcpProtocolError("Prime ACP emitted malformed JSON") from exc
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
            raise PrimeAcpProtocolError("Prime ACP emitted an unsupported JSON-RPC message")
        if "id" not in message and "method" not in message:
            raise PrimeAcpProtocolError("Prime ACP emitted an unrouteable JSON-RPC message")
        self.received_messages.append(message)
        return message

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._writer.close()
        with contextlib.suppress(Exception):
            await self._writer.wait_closed()

    def _preserve(self, path: Path, line: bytes) -> None:
        with path.open("ab") as sink:
            sink.write(redact_prime_bytes(line, self._environment, additional_values=self._redact_values))


class _AecBenchAcpClient:
    def __init__(self, updates: list[dict[str, Any]]) -> None:
        self._updates = updates
        self.protocol_error: PrimeAcpProtocolError | None = None

    def on_connect(self, connection: Any) -> None:
        del connection

    async def session_update(self, session_id: str, update: Any, **metadata: Any) -> None:
        payload = update.model_dump(mode="json", by_alias=True, exclude_none=True)
        self._updates.append({"session_id": session_id, "update": payload, "_meta": metadata or None})

    async def request_permission(
        self,
        session_id: str,
        tool_call: Any,
        options: list[Any],
        **metadata: Any,
    ) -> Any:
        del session_id, tool_call, metadata
        schema = importlib.import_module("acp.schema")
        allowed = next((option for option in options if option.kind == "allow_once"), None)
        if allowed is not None:
            return schema.RequestPermissionResponse(
                outcome=schema.AllowedOutcome(outcome="selected", option_id=allowed.option_id)
            )
        return schema.RequestPermissionResponse(outcome=schema.DeniedOutcome(outcome="cancelled"))

    async def write_text_file(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("fs/write_text_file", args, kwargs)

    async def read_text_file(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("fs/read_text_file", args, kwargs)

    async def create_terminal(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("terminal/create", args, kwargs)

    async def terminal_output(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("terminal/output", args, kwargs)

    async def release_terminal(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("terminal/release", args, kwargs)

    async def wait_for_terminal_exit(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("terminal/wait_for_exit", args, kwargs)

    async def kill_terminal(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("terminal/kill", args, kwargs)

    async def create_elicitation(self, *args: Any, **kwargs: Any) -> Any:
        return self._reject_client_operation("elicitation/create", args, kwargs)

    async def complete_elicitation(self, *args: Any, **kwargs: Any) -> None:
        self._reject_client_operation("elicitation/complete", args, kwargs)

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return self._reject_client_operation(f"_{method}", (), params)

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        self._reject_client_operation(f"_{method}", (), params)

    def _reject_client_operation(self, method: str, args: object, kwargs: object) -> NoReturn:
        del args, kwargs
        error = PrimeAcpProtocolError(f"Prime requested unsupported client operation: {method}")
        self.protocol_error = error
        raise error


def _load_acp() -> Any:
    try:
        return importlib.import_module("acp")
    except ModuleNotFoundError as exc:
        if exc.name == "acp":
            raise PrimeAcpDependencyError(
                'Prime ACP support is not installed. Install it with: pip install "aec-bench[prime-agent]"'
            ) from exc
        raise


def _validate_initialize(response: Any, protocol_version: int) -> None:
    if response.protocol_version != protocol_version:
        raise PrimeAcpProtocolError(
            f"Prime ACP selected unsupported protocol version {response.protocol_version}; expected {protocol_version}"
        )
    if response.agent_capabilities is None:
        raise PrimeAcpProtocolError("Prime ACP did not advertise agent capabilities")
    if response.agent_info is None or not response.agent_info.name.strip() or not response.agent_info.version.strip():
        raise PrimeAcpProtocolError("Prime ACP did not provide valid agent identity")


def _validate_raw_initialize(messages: Sequence[dict[str, Any]]) -> None:
    response = next((message for message in messages if message.get("id") == 0), None)
    result = response.get("result") if response is not None else None
    if not isinstance(result, dict):
        raise PrimeAcpProtocolError("Prime ACP initialize response is missing")
    if not isinstance(result.get("agentCapabilities"), dict):
        raise PrimeAcpProtocolError("Prime ACP initialize response omitted agent capabilities")
    if not isinstance(result.get("agentInfo"), dict):
        raise PrimeAcpProtocolError("Prime ACP initialize response omitted agent identity")


async def _capture_stderr(
    source: asyncio.StreamReader,
    destination: Path,
    environment: Mapping[str, str],
    redact_values: tuple[str, ...],
) -> None:
    with destination.open("ab") as sink:
        while chunk := await source.read(65536):
            sink.write(redact_prime_bytes(chunk, environment, additional_values=redact_values))
            sink.flush()


async def _prime_version(
    command_prefix: Sequence[str],
    executable: Path,
    workspace: Path,
    environment: Mapping[str, str],
    *,
    timeout_seconds: float,
) -> str:
    process: asyncio.subprocess.Process | None = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command_prefix,
            str(executable),
            "--version",
            cwd=workspace,
            env=dict(environment),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=os.name == "posix",
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
    except (OSError, TimeoutError):
        if process is not None:
            await _reap_process(process)
        return "unknown"
    if process.returncode != 0:
        return "unknown"
    match = _VERSION_PATTERN.search(stdout.decode("utf-8", errors="replace"))
    return match.group(1) if match is not None else "unknown"


async def _reap_process(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        await process.wait()
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=1)
        return
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=1)
        return
    except TimeoutError:
        pass
    with contextlib.suppress(ProcessLookupError):
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    await process.wait()


def _write_run_provenance(
    run: PrimeAcpRun,
    *,
    model: str,
    instruction: str,
    actor_workspace: Path,
    skill_directory: Path,
    sandbox_profile: Path | None,
) -> None:
    replacements = {
        str(actor_workspace): "<actor-workspace>",
        str(run.paths.session_dir): "<prime-session-dir>",
        str(skill_directory): "<aec-world-skill>",
    }
    if sandbox_profile is not None:
        replacements[str(sandbox_profile)] = "<sandbox-profile>"
    sanitized_command = [replacements.get(argument, argument) for argument in run.command]
    payload = {
        "schema": "aecbench.prime-acp-run.v1",
        "prime_version": run.prime_version,
        "tested_prime_version": PRIME_AGENT_TESTED_VERSION,
        "model_requested": model,
        "instruction_sha256": hashlib.sha256(instruction.encode("utf-8")).hexdigest(),
        "command": sanitized_command,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat(),
        "elapsed_seconds": run.elapsed_seconds,
        "exit_code": run.exit_code,
        "session_id": run.session_id,
        "protocol_version": run.protocol_version,
        "agent_name": run.agent_name,
        "agent_version": run.agent_version,
        "agent_capabilities": run.agent_capabilities,
        "limits": {
            "max_model_calls": run.limits.max_model_calls,
            "max_tokens": run.limits.max_tokens,
            "max_cost_usd": str(run.limits.max_cost_usd),
            "max_wall_seconds": run.limits.max_wall_seconds,
        },
        "usage": {
            "complete": run.usage.complete,
            "model_calls": run.usage.model_calls,
            "input_tokens": run.usage.input_tokens,
            "output_tokens": run.usage.output_tokens,
            "cache_read_tokens": run.usage.cache_read_tokens,
            "cache_write_tokens": run.usage.cache_write_tokens,
            "total_tokens": run.usage.total_tokens,
            "cost_usd": str(run.usage.cost_usd),
        },
        "topology": {
            "root_sessions": run.topology.root_sessions,
            "child_sessions": run.topology.child_sessions,
        },
        "refinement": {
            "events": run.refinement.events,
            "completed": run.refinement.completed,
            "failed": run.refinement.failed,
            "unknown": run.refinement.unknown,
        },
        "limit_reason": run.limit_reason,
        "session_state": run.session_state,
        "stop_reason": run.stop_reason,
        "timed_out": run.timed_out,
        "isolation": run.isolation,
        "benchmark_valid": run.benchmark_valid,
        "actor_principal_scope": "prime-session-composite",
        "runtime_home_scope": "actor-workspace",
        "skill_sha256": _directory_digest(skill_directory),
        "update_count": len(run.updates),
        "error": run.error,
    }
    run.paths.run_file.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return remaining


def _sandbox_quote(path: Path) -> str:
    return json.dumps(str(path), ensure_ascii=False)


def _redact_session_artifacts(
    session_directory: Path,
    environment: Mapping[str, str],
    redact_values: tuple[str, ...],
) -> None:
    for artifact in session_directory.rglob("*"):
        if not artifact.is_file():
            continue
        try:
            original = artifact.read_bytes()
            redacted = redact_prime_bytes(original, environment, additional_values=redact_values)
            if redacted != original:
                artifact.write_bytes(redacted)
        except OSError:
            continue


def _directory_digest(directory: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in directory.rglob("*") if item.is_file()):
        digest.update(path.relative_to(directory).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
