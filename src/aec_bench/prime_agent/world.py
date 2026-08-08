# ABOUTME: Exposes one host-owned pump-world episode through a capability-scoped local actor socket.
# ABOUTME: Keeps run identity, host controls, hidden state, and replay authority outside Prime's process.

from __future__ import annotations

import hmac
import json
import os
import secrets
import shutil
import socketserver
import tempfile
import threading
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import JsonValue, ValidationError

from aec_bench.contracts.continual_world import ContinualWorldActorRequest
from aec_bench.contracts.validators import StrictModel
from aec_bench.contracts.world_interface import (
    WorldActorActionRequest,
    WorldActorActionResult,
    WorldInterfaceError,
)
from aec_bench.contracts.world_session import WorldSessionRequest, WorldSessionResult
from aec_bench.prime_agent.acp import (
    PrimeAcpIsolation,
    PrimeAcpRun,
    run_prime_acp_session,
)
from aec_bench.prime_agent.session_evidence import PrimeAcpLimits
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.episode_runtime import (
    PumpStationEpisodeHost,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.evaluation import (
    evaluate_pump_station_reference_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run import (
    PumpStationWorldRun,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_repository import (
    PumpStationWorldRunRepository,
)

if TYPE_CHECKING:
    from aec_bench.contracts.evaluation_result import StewardshipEvaluation
    from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_verifier import (
        PumpStationCoupledVerificationReport,
    )

WORLD_ACTOR_SOCKET_ENV = "AEC_BENCH_WORLD_ACTOR_SOCKET"
WORLD_ACTOR_CAPABILITY_ENV = "AEC_BENCH_WORLD_ACTOR_CAPABILITY_TOKEN"
_MAX_MESSAGE_BYTES = 1024 * 1024
PUMP_STATION_GUIDANCE_INSTRUCTION = (
    "Before your first world action, load and follow the full `pump-station-guidance` skill. "
    "Keep its compact state and exact action ledger throughout the episode. "
    "Use its references when they help the current decision."
)


class PrimeWorldActorProxyError(RuntimeError):
    """Raised when the scoped actor transport cannot be opened or used safely."""


@dataclass(frozen=True, slots=True)
class PrimeWorldSessionLimits:
    """Host limits for one composed Prime and interactive-world run."""

    max_world_actions: int
    max_model_calls: int
    max_tokens: int
    max_cost_usd: Decimal
    max_wall_seconds: float

    def __post_init__(self) -> None:
        if self.max_world_actions < 1:
            raise ValueError("Prime world max_world_actions must be positive")
        self.acp_limits()

    def acp_limits(self) -> PrimeAcpLimits:
        return PrimeAcpLimits(
            max_model_calls=self.max_model_calls,
            max_tokens=self.max_tokens,
            max_cost_usd=self.max_cost_usd,
            max_wall_seconds=self.max_wall_seconds,
        )


@dataclass(frozen=True, slots=True)
class PrimePumpWorldRun:
    """Separate Prime-session and canonical-world outcomes for one interactive trial."""

    prime: PrimeAcpRun
    world_session: WorldSessionResult
    world_state: str
    completion: str
    verification: PumpStationCoupledVerificationReport
    evaluation: StewardshipEvaluation
    actor_transport_file: Path
    run_file: Path
    world_action_attempts: int
    world_action_limit_reached: bool
    benchmark_valid: bool


class _ActorTransportRequest(StrictModel):
    capability: str
    request: ContinualWorldActorRequest


class _ActorTransportError(StrictModel):
    code: str
    detail: str


class _ActorTransportResponse(StrictModel):
    result: dict[str, JsonValue] | None = None
    error: _ActorTransportError | None = None


class _ThreadedUnixServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = False


class _ActorRequestHandler(socketserver.StreamRequestHandler):
    server: _ActorProxyServer

    def handle(self) -> None:
        received_at = datetime.now(UTC)
        line = self.rfile.readline(_MAX_MESSAGE_BYTES + 1)
        if len(line) > _MAX_MESSAGE_BYTES:
            self.server.owner._reject_transport(
                self.wfile,
                received_at=received_at,
                error=("request-too-large", "actor request is too large"),
            )
            return
        if not line or not line.endswith(b"\n"):
            self.server.owner._reject_transport(
                self.wfile,
                received_at=received_at,
                error=("transport-malformed", "actor request must be one line"),
            )
            return
        self.server.owner._handle_request(line, self.wfile, received_at=received_at)


class _ActorProxyServer(_ThreadedUnixServer):
    owner: PrimeWorldActorProxy


class PrimeWorldActorProxy:
    """Own one pump episode and expose only its installed actor operations.

    The socket capability is scoped to the whole Prime session. Prime's root
    process and any descendants therefore form one composite AECBench actor
    principal for this integration.
    """

    def __init__(
        self,
        *,
        world_run_directory: Path,
        socket_directory: Path,
        max_world_actions: int,
        evidence_file: Path | None = None,
    ) -> None:
        if max_world_actions < 1:
            raise ValueError("Prime world max_world_actions must be positive")
        self._world_run_directory = world_run_directory.resolve()
        requested_socket_directory = socket_directory.resolve()
        requested_socket_path = requested_socket_directory / "actor.sock"
        self._owns_socket_directory = len(os.fsencode(requested_socket_path)) > 100
        short_socket_root = Path("/private/tmp") if Path("/private/tmp").is_dir() else Path("/tmp")
        self._socket_directory = (
            Path(tempfile.mkdtemp(prefix="aecbench-actor-", dir=short_socket_root)).resolve()
            if self._owns_socket_directory
            else requested_socket_directory
        )
        self._evidence_file = evidence_file.resolve() if evidence_file is not None else None
        self._host = PumpStationEpisodeHost(self._world_run_directory)
        self._max_world_actions = max_world_actions
        self._world_action_attempts = 0
        self._world_action_limit_reached = False
        self._world_action_requests: dict[str, str] = {}
        self._capability = secrets.token_urlsafe(32)
        self._socket_path = self._socket_directory / "actor.sock"
        self._server: _ActorProxyServer | None = None
        self._thread: threading.Thread | None = None
        self._evidence_lock = threading.Lock()
        self._sequence = 0
        self._last_action_result: WorldActorActionResult | None = None

    def open_world_session(self, request: WorldSessionRequest) -> WorldSessionResult:
        """Open the host-selected episode before Prime receives actor access."""
        if self._server is not None:
            raise PrimeWorldActorProxyError("world session cannot be opened after the actor endpoint starts")
        return self._host.open(request)

    def start(self) -> None:
        if self._server is not None:
            raise PrimeWorldActorProxyError("actor proxy is already running")
        self._socket_directory.mkdir(parents=True, exist_ok=True)
        self._socket_directory.chmod(0o700)
        if self._socket_path.exists() or self._socket_path.is_symlink():
            raise PrimeWorldActorProxyError("actor socket path already exists")
        if self._evidence_file is not None:
            self._evidence_file.parent.mkdir(parents=True, exist_ok=True)
            self._evidence_file.write_bytes(b"")
        server = _ActorProxyServer(str(self._socket_path), _ActorRequestHandler)
        self._socket_path.chmod(0o600)
        server.owner = self
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="aec-world-actor-proxy", daemon=True)
        self._thread.start()

    def connection_environment(self) -> dict[str, str]:
        """Return the two opaque values required by the packaged actor client."""
        if self._server is None:
            raise PrimeWorldActorProxyError("actor proxy is not running")
        return {
            WORLD_ACTOR_SOCKET_ENV: str(self._socket_path),
            WORLD_ACTOR_CAPABILITY_ENV: self._capability,
        }

    @property
    def last_action_result(self) -> WorldActorActionResult | None:
        return self._last_action_result

    @property
    def world_action_attempts(self) -> int:
        return self._world_action_attempts

    @property
    def world_action_limit_reached(self) -> bool:
        return self._world_action_limit_reached

    def close(self) -> None:
        server, thread = self._server, self._thread
        self._server = None
        self._thread = None
        if server is not None:
            server.shutdown()
            server.server_close()
        if thread is not None:
            thread.join(timeout=2)
        self._socket_path.unlink(missing_ok=True)
        if self._owns_socket_directory:
            self._socket_directory.rmdir()

    def __enter__(self) -> PrimeWorldActorProxy:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _handle_request(self, line: bytes, writer: Any, *, received_at: datetime) -> None:
        request: ContinualWorldActorRequest | None = None
        operation: str | None = None
        try:
            raw = json.loads(line)
            operation = _safe_operation(raw)
            envelope = _ActorTransportRequest.model_validate(raw)
            if not hmac.compare_digest(envelope.capability, self._capability):
                self._record(
                    request=None,
                    operation=operation,
                    received_at=received_at,
                    error={"code": "actor-unauthorized", "detail": "actor capability is invalid"},
                )
                self._write_response(writer, error=("actor-unauthorized", "actor capability is invalid"))
                return
            request = envelope.request
            operation = request.operation
            if request.operation == "invoke" and not self._authorize_world_action(request):
                response_error = ("world-action-budget-exhausted", "world action budget is exhausted")
                error: dict[str, JsonValue] = {
                    "code": response_error[0],
                    "detail": response_error[1],
                }
                self._record(
                    request=request,
                    operation=operation,
                    received_at=received_at,
                    error=error,
                )
                self._write_response(writer, error=response_error)
                return
            result = self._dispatch(request)
        except (UnicodeDecodeError, json.JSONDecodeError, ValidationError, TypeError, ValueError):
            self._record(
                request=None,
                operation=operation,
                received_at=received_at,
                error={
                    "code": "actor-request-invalid",
                    "detail": "actor request does not match the contract",
                },
            )
            self._write_response(writer, error=("actor-request-invalid", "actor request does not match the contract"))
            return
        except WorldInterfaceError as exc:
            self._record(
                request=request,
                operation=operation,
                received_at=received_at,
                error={"code": exc.code, "detail": exc.detail},
            )
            self._write_response(writer, error=(exc.code, exc.detail))
            return
        except Exception:
            self._record(
                request=request,
                operation=operation,
                received_at=received_at,
                error={"code": "actor-proxy-failed", "detail": "host actor call failed"},
            )
            self._write_response(writer, error=("actor-proxy-failed", "host actor call failed"))
            return
        payload = result.model_dump(mode="json")
        self._record(request=request, operation=operation, received_at=received_at, result=payload)
        self._write_response(writer, result=payload)

    def _reject_transport(self, writer: Any, *, received_at: datetime, error: tuple[str, str]) -> None:
        self._record(
            request=None,
            operation=None,
            received_at=received_at,
            error={"code": error[0], "detail": error[1]},
        )
        self._write_response(writer, error=error)

    def _authorize_world_action(self, request: ContinualWorldActorRequest) -> bool:
        assert request.request_id is not None
        fingerprint = request.model_dump_json()
        with self._evidence_lock:
            if self._world_action_requests.get(request.request_id) == fingerprint:
                return True
            self._world_action_attempts += 1
            if self._world_action_attempts > self._max_world_actions:
                self._world_action_limit_reached = True
                return False
            self._world_action_requests.setdefault(request.request_id, fingerprint)
            if self._world_action_attempts == self._max_world_actions:
                self._world_action_limit_reached = True
            return True

    def _dispatch(self, request: ContinualWorldActorRequest) -> StrictModel:
        if request.operation == "capabilities":
            return self._host.capabilities()
        if request.operation == "observe":
            return self._host.observe()
        assert request.request_id is not None
        assert request.decision_id is not None
        assert request.action_name is not None
        assert request.arguments is not None
        action = WorldActorActionRequest(
            request_id=request.request_id,
            decision_id=request.decision_id,
            action_name=request.action_name,
            arguments=request.arguments,
        )
        result = self._host.invoke(action)
        self._last_action_result = result
        return result

    def _record(
        self,
        *,
        request: ContinualWorldActorRequest | None,
        operation: str | None,
        received_at: datetime,
        result: dict[str, JsonValue] | None = None,
        error: dict[str, JsonValue] | None = None,
    ) -> None:
        if self._evidence_file is None:
            return
        with self._evidence_lock:
            self._sequence += 1
            event: dict[str, JsonValue] = {
                "sequence": self._sequence,
                "received_at": received_at.isoformat(),
                "operation": operation,
                "request": request.model_dump(mode="json") if request is not None else None,
                "result": result,
                "error": error,
            }
            with self._evidence_file.open("ab") as sink:
                sink.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n")

    @staticmethod
    def _write_response(
        writer: Any,
        *,
        result: dict[str, JsonValue] | None = None,
        error: tuple[str, str] | None = None,
    ) -> None:
        response = _ActorTransportResponse(
            result=result,
            error=None if error is None else _ActorTransportError(code=error[0], detail=error[1]),
        )
        writer.write(response.model_dump_json(exclude_none=True).encode("utf-8") + b"\n")
        writer.flush()


def install_aec_world_skill(actor_workspace: Path) -> Path:
    """Install the packaged skill and importable client into one isolated actor workspace."""
    actor_workspace = actor_workspace.resolve()
    package_directory = actor_workspace / "aec_world"
    if package_directory.exists():
        package_source = _packaged_skill_source("aec-world") / "src" / "aec_world"
        if not _installed_tree_matches(package_source, package_directory):
            raise PrimeWorldActorProxyError("aec-world package destination already exists with different content")
        return _install_packaged_skill(actor_workspace, "aec-world")
    skill_directory = _install_packaged_skill(actor_workspace, "aec-world")
    source = _packaged_skill_source("aec-world")
    shutil.copytree(source / "src" / "aec_world", package_directory)
    return skill_directory


def install_pump_station_guidance_skill(actor_workspace: Path) -> Path:
    """Install the packaged Markdown guidance into one isolated actor workspace."""
    return _install_packaged_skill(actor_workspace.resolve(), "pump-station-guidance")


async def run_prime_pump_world_session(
    *,
    actor_workspace: Path,
    world_run_directory: Path,
    evidence_directory: Path,
    session_request: WorldSessionRequest,
    instruction: str,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: PrimeWorldSessionLimits,
    prime_runtime_directory: Path | None = None,
    additional_private_paths: Sequence[Path] = (),
    pump_station_guidance: bool = False,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
) -> PrimePumpWorldRun:
    """Compose Prime with the current pump world without changing task-owned runtime paths."""
    actor_workspace = actor_workspace.resolve()
    world_run_directory = world_run_directory.resolve()
    evidence_directory = evidence_directory.resolve()
    if _paths_overlap(actor_workspace, world_run_directory) or _paths_overlap(actor_workspace, evidence_directory):
        raise PrimeWorldActorProxyError("actor workspace must be separate from host world and evidence paths")
    actor_workspace.mkdir(parents=True, exist_ok=True)
    evidence_directory.mkdir(parents=True, exist_ok=False)
    skill_directories = [install_aec_world_skill(actor_workspace)]
    prime_instruction = instruction
    if pump_station_guidance:
        skill_directories.append(install_pump_station_guidance_skill(actor_workspace))
        prime_instruction = instruction.rstrip() + "\n\n" + PUMP_STATION_GUIDANCE_INSTRUCTION + "\n"
    actor_transport_file = evidence_directory / "world-actor-transport.jsonl"
    proxy = PrimeWorldActorProxy(
        world_run_directory=world_run_directory,
        socket_directory=actor_workspace / ".actor",
        max_world_actions=limits.max_world_actions,
        evidence_file=actor_transport_file,
    )
    world_session = proxy.open_world_session(session_request)
    with proxy:
        prime = await run_prime_acp_session(
            actor_workspace=actor_workspace,
            evidence_directory=evidence_directory,
            skill_directories=tuple(skill_directories),
            instruction=prime_instruction,
            model=model,
            actor_environment=proxy.connection_environment(),
            isolation=isolation,
            limits=limits.acp_limits(),
            runtime_directory=prime_runtime_directory,
            private_paths=(world_run_directory, evidence_directory, *additional_private_paths),
            executable=executable,
            environment=environment,
        )
        last_action = proxy.last_action_result
        world_action_attempts = proxy.world_action_attempts
        world_action_limit_reached = proxy.world_action_limit_reached

    repository = PumpStationWorldRunRepository(world_run_directory)
    run = PumpStationWorldRun.resume_reference_system(
        repository=repository,
        snapshot=repository.current_snapshot(),
    )
    verification = run.verify()
    # One Prime ACP session can make only actor-authorised progress. Host-owned
    # Operations reviews remain outside its capability, so this composition is
    # a bounded continuation rather than the task's complete reference journey.
    evaluation = evaluate_pump_station_reference_run(run, evaluation_scope="bounded_continuation")
    if not verification.valid:
        world_state = "failed"
    elif last_action is not None and last_action.terminated:
        world_state = "completed"
    elif last_action is not None and last_action.truncated:
        world_state = "truncated"
    else:
        world_state = "active"
    if prime.session_state == "failed" or world_state == "failed":
        completion = "failed"
    elif prime.session_state == "cancelled":
        completion = "interrupted"
    elif world_state == "completed":
        completion = "completed"
    elif world_state == "truncated":
        completion = "truncated"
    else:
        completion = "incomplete"
    benchmark_valid = prime.benchmark_valid and verification.valid
    run_file = evidence_directory / "prime-world-run.json"
    run_file.write_text(
        json.dumps(
            {
                "schema": "aecbench.prime-world-run.v1",
                "limits": {
                    "max_world_actions": limits.max_world_actions,
                    "max_model_calls": limits.max_model_calls,
                    "max_tokens": limits.max_tokens,
                    "max_cost_usd": str(limits.max_cost_usd),
                    "max_wall_seconds": limits.max_wall_seconds,
                },
                "world_action_attempts": world_action_attempts,
                "world_action_limit_reached": world_action_limit_reached,
                "prime_session_state": prime.session_state,
                "prime_limit_reason": prime.limit_reason,
                "world_state": world_state,
                "completion": completion,
                "evaluation_scope": evaluation.evaluation_scope,
                "evaluation_valid": evaluation.valid,
                "benchmark_valid": benchmark_valid,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return PrimePumpWorldRun(
        prime=prime,
        world_session=world_session,
        world_state=world_state,
        completion=completion,
        verification=verification,
        evaluation=evaluation,
        actor_transport_file=actor_transport_file,
        run_file=run_file,
        world_action_attempts=world_action_attempts,
        world_action_limit_reached=world_action_limit_reached,
        benchmark_valid=benchmark_valid,
    )


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents


def _packaged_skill_source(name: str) -> Path:
    source = Path(__file__).with_name("skills") / name
    if not source.is_dir():
        raise PrimeWorldActorProxyError(f"packaged Prime skill is missing: {name}")
    return source


def _install_packaged_skill(actor_workspace: Path, name: str) -> Path:
    source = _packaged_skill_source(name)
    skill_directory = actor_workspace / ".prime-skills" / name
    if skill_directory.exists():
        if not _installed_tree_matches(source, skill_directory):
            raise PrimeWorldActorProxyError(f"Prime skill destination already exists with different content: {name}")
        return skill_directory
    skill_directory.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, skill_directory)
    return skill_directory


def _installed_tree_matches(source: Path, destination: Path) -> bool:
    if not destination.is_dir() or destination.is_symlink():
        return False
    if any(path.is_symlink() for path in destination.rglob("*")):
        return False
    expected = {
        path.relative_to(source): path.read_bytes()
        for path in source.rglob("*")
        if path.is_file() and not path.is_symlink()
    }
    installed = {path.relative_to(destination): path for path in destination.rglob("*") if path.is_file()}
    if any(relative not in expected and "__pycache__" not in relative.parts for relative in installed):
        return False
    return all(
        relative in installed and installed[relative].read_bytes() == content for relative, content in expected.items()
    )


def _safe_operation(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    request = value.get("request")
    if not isinstance(request, dict):
        return None
    operation = request.get("operation")
    if isinstance(operation, str) and operation in {"capabilities", "observe", "invoke"}:
        return operation
    return None
