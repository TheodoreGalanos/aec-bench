# ABOUTME: Runs the hydraulic-review evidence lifecycle through one fresh scoped Prime session per checkpoint.
# ABOUTME: Keeps lifecycle coordination, Prime evidence, and task verification as separate authorities.

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
from collections.abc import Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path, PurePosixPath
from typing import Any, Literal

from pydantic import Field, NonNegativeInt, field_validator

from aec_bench.contracts.trial_record import ArtifactReference
from aec_bench.contracts.validators import NonEmptyStr, StrictModel
from aec_bench.harness.hydraulic_review_prime.endpoint import HydraulicReviewPrimeLifecycleEndpoint
from aec_bench.ledger.durability import mkdir_durable, replace_file_bytes_durable
from aec_bench.ledger.immutable_byte_store import ImmutableByteStore
from aec_bench.lifecycles.runtime.episode import (
    LifecycleEpisodeContext,
    LifecycleEpisodeEnvironmentFailure,
    LifecycleEpisodeRequest,
    LifecycleEpisodeResult,
    LifecycleEpisodeUsage,
    LifecycleExecutionMode,
    LifecycleVisibilityPolicy,
)
from aec_bench.lifecycles.runtime.lifecycle import (
    load_evidence_lifecycle_spec,
    run_evidence_lifecycle,
    validate_evidence_checkpoint_submission,
)
from aec_bench.lifecycles.runtime.operation_protocol import LifecycleOperationResolver
from aec_bench.lifecycles.stormwater_design.hydraulic_review import (
    LIFECYCLE_ID,
    build_hydraulic_operation_resolver,
    validated_hydraulic_review_variant,
    verify_hydraulic_review_lifecycle,
)
from aec_bench.prime_agent.acp import PrimeAcpIsolation, PrimeAcpRun, run_prime_acp_session
from aec_bench.prime_agent.batch import resolve_prime_executable
from aec_bench.prime_agent.session_evidence import PrimeAcpLimits, PrimeAcpUsage
from aec_bench.prime_agent.skills import PrimeSkillInstallError, install_prime_skill

type PrimeSessionRunner = Callable[..., Coroutine[Any, Any, PrimeAcpRun]]


class HydraulicReviewPrimeLifecycleRecoveryError(RuntimeError):
    """Raised when prior Prime evidence cannot support safe lifecycle continuation."""


@dataclass(frozen=True, slots=True)
class HydraulicReviewPrimeLifecycleLimits:
    """Host limits shared by every Prime checkpoint attempt in one lifecycle."""

    max_sessions: int
    max_model_calls: int
    max_tokens: int
    max_cost_usd: Decimal
    max_wall_seconds: float

    def __post_init__(self) -> None:
        if self.max_sessions < 1:
            raise ValueError("hydraulic-review Prime max_sessions must be positive")
        PrimeAcpLimits(
            max_model_calls=self.max_model_calls,
            max_tokens=self.max_tokens,
            max_cost_usd=self.max_cost_usd,
            max_wall_seconds=self.max_wall_seconds,
        )


@dataclass(frozen=True, slots=True)
class HydraulicReviewPrimeLifecycleRun:
    """Separate Prime, lifecycle, and task-verification evidence for one completed run."""

    prime: dict[str, Any]
    lifecycle: dict[str, Any]
    verification: dict[str, Any]
    benchmark_valid: bool


class _UsageEvidence(StrictModel):
    complete: bool
    model_calls: NonNegativeInt
    input_tokens: NonNegativeInt
    output_tokens: NonNegativeInt
    cache_read_tokens: NonNegativeInt
    cache_write_tokens: NonNegativeInt
    total_tokens: NonNegativeInt
    cost_usd: Decimal = Field(ge=0)


class _TopologyEvidence(StrictModel):
    root_sessions: NonNegativeInt
    child_sessions: NonNegativeInt


class _AttemptEvidence(StrictModel):
    schema_version: Literal["1"] = "1"
    checkpoint_id: NonEmptyStr
    attempt_id: NonEmptyStr
    session_id: NonEmptyStr
    prime_run: NonEmptyStr
    prime_run_sha256: NonEmptyStr
    transport_log: NonEmptyStr
    transport_log_sha256: NonEmptyStr
    exit_code: int | None
    session_state: NonEmptyStr
    stop_reason: str | None
    limit_reason: str | None
    error: str | None
    elapsed_seconds: float = Field(ge=0)
    isolation: PrimeAcpIsolation
    benchmark_valid: bool
    usage: _UsageEvidence
    topology: _TopologyEvidence

    @field_validator("prime_run_sha256", "transport_log_sha256")
    @classmethod
    def validate_hash(cls, value: str) -> str:
        return ArtifactReference.validate_sha256(value)


@dataclass(frozen=True)
class HydraulicReviewPrimeLifecycleEnvironment:
    """Implement one fresh Prime checkpoint through the lifecycle episode port."""

    package_dir: Path
    actor_workspace_root: Path
    model: str
    isolation: PrimeAcpIsolation
    limits: HydraulicReviewPrimeLifecycleLimits
    operation_resolver: LifecycleOperationResolver
    executable: str = "prime-agent"
    environment: Mapping[str, str] | None = None
    additional_private_paths: Sequence[Path] = ()
    prime_session_runner: PrimeSessionRunner = run_prime_acp_session
    execution_mode: LifecycleExecutionMode = LifecycleExecutionMode.FRESH_CONTEXT
    memory_visibility_policy: LifecycleVisibilityPolicy = LifecycleVisibilityPolicy.ARTIFACT_MEMORY

    def __post_init__(self) -> None:
        package = self.package_dir.resolve()
        actor_root = self.actor_workspace_root.resolve()
        if self.execution_mode is not LifecycleExecutionMode.FRESH_CONTEXT:
            raise ValueError("hydraulic-review Prime requires fresh_context execution")
        if self.memory_visibility_policy is not LifecycleVisibilityPolicy.ARTIFACT_MEMORY:
            raise ValueError("hydraulic-review Prime requires artifact_memory visibility")
        if _paths_overlap(package, actor_root):
            raise ValueError("hydraulic-review Prime actor workspaces must be separate from the lifecycle package")

    @property
    def requested_adapter(self) -> str:
        return "prime-agent"

    @property
    def requested_model(self) -> str:
        return self.model

    @property
    def max_turns_per_session(self) -> int:
        return self.limits.max_model_calls

    def recover(self, context: LifecycleEpisodeContext) -> None:
        """Reject interrupted Prime accounting before the host allocates a retry."""
        run_dir = Path(context.run_dir).resolve()
        self._ensure_paths(run_dir)
        self._ensure_configuration(
            run_dir=run_dir,
            lifecycle_id=context.lifecycle_id,
            lifecycle_spec_sha256=context.lifecycle_spec_sha256,
            package_sha256=context.package_sha256,
        )
        self._load_attempts(run_dir, require_complete_usage=True)

    def prepare(self, request: LifecycleEpisodeRequest) -> None:
        """Publish stable Prime configuration without creating host result paths."""
        run_dir = Path(request.run_dir).resolve()
        self._ensure_paths(run_dir)
        self._ensure_configuration(
            run_dir=run_dir,
            lifecycle_id=request.lifecycle_id,
            lifecycle_spec_sha256=request.lifecycle_spec_sha256,
            package_sha256=request.package_sha256,
        )
        (run_dir / "episodes" / request.checkpoint_id / request.session_id).mkdir(parents=True, exist_ok=True)
        self._write_manifest(run_dir, status="ready")

    def record_failure(
        self,
        request: LifecycleEpisodeRequest,
        *,
        failure_kind: str,
        provider_error: str | None,
    ) -> None:
        """Make the aggregate Prime manifest show the failed host attempt."""
        del provider_error
        self._write_manifest(Path(request.run_dir), status="failed", failure_kind=failure_kind)

    def execute(self, request: LifecycleEpisodeRequest) -> LifecycleEpisodeResult:
        """Run one Prime process and offer one submission to the existing lifecycle host."""
        run_dir = Path(request.run_dir).resolve()
        remaining = self._remaining_limits(run_dir)
        actor_workspace = self.actor_workspace_root.resolve() / request.session_id
        if actor_workspace.exists():
            raise LifecycleEpisodeEnvironmentFailure(
                "prime_actor_workspace_conflict",
                "Prime actor workspace already exists for this session",
            )
        actor_workspace.mkdir(parents=True)
        skill_directory = install_hydraulic_review_skill(actor_workspace)
        episode_dir = run_dir / "episodes" / request.checkpoint_id / request.session_id
        evidence_directory = episode_dir / "prime"
        transport_file = episode_dir / "hydraulic-review-transport.jsonl"
        if evidence_directory.exists():
            raise LifecycleEpisodeEnvironmentFailure(
                "prime_evidence_conflict",
                "Prime evidence already exists for this session",
            )
        private_paths = (
            self.package_dir.resolve(),
            run_dir,
            *(path.resolve() for path in self.additional_private_paths),
            *(path.resolve() for path in self.actor_workspace_root.resolve().iterdir() if path != actor_workspace),
        )
        endpoint = HydraulicReviewPrimeLifecycleEndpoint(
            package_dir=self.package_dir,
            run_dir=run_dir,
            request=request,
            operation_resolver=self.operation_resolver,
            socket_directory=actor_workspace / ".lifecycle",
            evidence_file=transport_file,
        )
        with endpoint:
            prime: PrimeAcpRun = asyncio.run(
                self.prime_session_runner(
                    actor_workspace=actor_workspace,
                    evidence_directory=evidence_directory,
                    skill_directories=(skill_directory,),
                    instruction=_prime_instruction(request),
                    model=self.model,
                    actor_environment=endpoint.connection_environment(),
                    scoped_socket=endpoint.socket_path,
                    isolation=self.isolation,
                    limits=remaining,
                    private_paths=private_paths,
                    executable=self.executable,
                    environment=self.environment,
                )
            )
            offered_submission = endpoint.offered_submission

        attempt = self._publish_attempt(request, prime, transport_file)
        self._write_manifest(run_dir, status="running")
        failure = _prime_failure(
            prime,
            offered_submission,
            expected_isolation=self.isolation,
        )
        if failure is not None:
            return self._episode_result(request, attempt, status="failed", failure_kind=failure)

        assert offered_submission is not None
        spec = load_evidence_lifecycle_spec(self.package_dir)
        checkpoint = next(item for item in spec.checkpoints if item.checkpoint_id == request.checkpoint_id)
        validate_evidence_checkpoint_submission(checkpoint, offered_submission)
        destination = Path(request.submission_path)
        mkdir_durable(destination.parent)
        replace_file_bytes_durable(
            destination.parent,
            destination.name,
            _canonical_json(offered_submission),
        )
        return self._episode_result(request, attempt, status="completed")

    def final_manifest(self, run_dir: Path, *, status: str, failure_kind: str | None = None) -> dict[str, Any]:
        """Publish and return the provider-only aggregate manifest."""
        self._write_manifest(run_dir, status=status, failure_kind=failure_kind)
        return _read_json(Path(run_dir) / "prime" / "manifest.json")

    def _episode_result(
        self,
        request: LifecycleEpisodeRequest,
        attempt: _AttemptEvidence,
        *,
        status: Literal["completed", "failed"],
        failure_kind: str | None = None,
    ) -> LifecycleEpisodeResult:
        usage = attempt.usage
        return LifecycleEpisodeResult(
            episode_id=request.episode_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            checkpoint_ids=request.checkpoint_ids,
            execution_mode=request.execution_mode,
            memory_visibility_policy=request.memory_visibility_policy,
            status=status,
            requested_adapter=self.requested_adapter,
            requested_model=self.model,
            max_turns_per_session=self.max_turns_per_session,
            adapter="prime-agent",
            resolved_model=self.model,
            configuration={
                "isolation": attempt.isolation.value,
                "benchmark_valid": attempt.benchmark_valid,
                "prime_run": attempt.prime_run,
                "transport_log": attempt.transport_log,
                "model_calls": usage.model_calls,
                "total_tokens": usage.total_tokens,
                "cost_usd": str(usage.cost_usd),
            },
            usage=LifecycleEpisodeUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
            ),
            failure_kind=failure_kind,
            provider_error=None if failure_kind is None else failure_kind,
        )

    def _publish_attempt(
        self,
        request: LifecycleEpisodeRequest,
        prime: PrimeAcpRun,
        transport_file: Path,
    ) -> _AttemptEvidence:
        run_dir = Path(request.run_dir).resolve()
        prime_run = prime.paths.run_file.resolve()
        transport = transport_file.resolve()
        episode_dir = (run_dir / "episodes" / request.checkpoint_id / request.session_id).resolve()
        expected_prime_run = episode_dir / "prime" / "prime-run.json"
        expected_transport = episode_dir / "hydraulic-review-transport.jsonl"
        if prime_run != expected_prime_run or transport != expected_transport:
            raise HydraulicReviewPrimeLifecycleRecoveryError("Prime attempt evidence does not match its episode")
        if not prime_run.is_file() or not transport.is_file():
            raise HydraulicReviewPrimeLifecycleRecoveryError("Prime attempt evidence is incomplete")
        try:
            prime_relative = prime_run.relative_to(run_dir).as_posix()
            transport_relative = transport.relative_to(run_dir).as_posix()
        except ValueError as exc:
            raise HydraulicReviewPrimeLifecycleRecoveryError(
                "Prime attempt evidence escaped the lifecycle run"
            ) from exc
        attempt = _AttemptEvidence(
            checkpoint_id=request.checkpoint_id,
            attempt_id=request.attempt_id,
            session_id=request.session_id,
            prime_run=prime_relative,
            prime_run_sha256=_sha256(prime_run),
            transport_log=transport_relative,
            transport_log_sha256=_sha256(transport),
            exit_code=prime.exit_code,
            session_state=prime.session_state,
            stop_reason=prime.stop_reason,
            limit_reason=prime.limit_reason,
            error=prime.error,
            elapsed_seconds=prime.elapsed_seconds,
            isolation=prime.isolation,
            benchmark_valid=prime.benchmark_valid,
            usage=_usage_evidence(prime.usage),
            topology=_TopologyEvidence(
                root_sessions=prime.topology.root_sessions,
                child_sessions=prime.topology.child_sessions,
            ),
        )
        store = ImmutableByteStore(episode_dir)
        store.publish_bytes("prime-attempt.json", _canonical_json(attempt.model_dump(mode="json")))
        return attempt

    def _remaining_limits(self, run_dir: Path) -> PrimeAcpLimits:
        attempts = self._load_attempts(run_dir, require_complete_usage=True)
        usage = _aggregate_usage(attempts)
        elapsed = sum(item.elapsed_seconds for item in attempts)
        if len(attempts) >= self.limits.max_sessions:
            raise LifecycleEpisodeEnvironmentFailure("max_sessions", "Prime lifecycle session limit is exhausted")
        remaining_calls = self.limits.max_model_calls - usage.model_calls
        remaining_tokens = self.limits.max_tokens - usage.total_tokens
        remaining_cost = self.limits.max_cost_usd - usage.cost_usd
        remaining_wall = self.limits.max_wall_seconds - elapsed
        if remaining_calls < 1:
            raise LifecycleEpisodeEnvironmentFailure("max_model_calls", "Prime lifecycle model-call limit is exhausted")
        if remaining_tokens < 1:
            raise LifecycleEpisodeEnvironmentFailure("max_tokens", "Prime lifecycle token limit is exhausted")
        if remaining_cost <= 0:
            raise LifecycleEpisodeEnvironmentFailure("max_cost_usd", "Prime lifecycle cost limit is exhausted")
        if remaining_wall <= 0:
            raise LifecycleEpisodeEnvironmentFailure("max_wall_seconds", "Prime lifecycle wall limit is exhausted")
        return PrimeAcpLimits(
            max_model_calls=remaining_calls,
            max_tokens=remaining_tokens,
            max_cost_usd=remaining_cost,
            max_wall_seconds=remaining_wall,
        )

    def _load_attempts(self, run_dir: Path, *, require_complete_usage: bool) -> tuple[_AttemptEvidence, ...]:
        run = run_dir.resolve()
        attempt_paths = sorted(run.glob("episodes/*/*/prime-attempt.json"))
        prime_directories = sorted(
            path for path in run.glob("episodes/*/*/prime") if path.is_dir() and any(path.iterdir())
        )
        summarized_directories = {path.parent / "prime" for path in attempt_paths}
        if set(prime_directories) != summarized_directories:
            raise HydraulicReviewPrimeLifecycleRecoveryError("Prime attempt has missing or unbound accounting evidence")
        attempts: list[_AttemptEvidence] = []
        for path in attempt_paths:
            try:
                attempt = _AttemptEvidence.model_validate_json(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, ValueError) as exc:
                raise HydraulicReviewPrimeLifecycleRecoveryError(
                    "Prime attempt accounting evidence is malformed"
                ) from exc
            expected_session_dir = run / "episodes" / attempt.checkpoint_id / attempt.session_id
            if path.parent.resolve() != expected_session_dir.resolve():
                raise HydraulicReviewPrimeLifecycleRecoveryError(
                    "Prime attempt accounting identity differs from storage"
                )
            prime_run = _confined_reference(run, attempt.prime_run)
            transport = _confined_reference(run, attempt.transport_log)
            if (
                prime_run != (expected_session_dir / "prime" / "prime-run.json").resolve()
                or transport != (expected_session_dir / "hydraulic-review-transport.jsonl").resolve()
            ):
                raise HydraulicReviewPrimeLifecycleRecoveryError(
                    "Prime attempt evidence reference differs from its episode"
                )
            if (
                not prime_run.is_file()
                or not transport.is_file()
                or _sha256(prime_run) != attempt.prime_run_sha256
                or _sha256(transport) != attempt.transport_log_sha256
            ):
                raise HydraulicReviewPrimeLifecycleRecoveryError(
                    "Prime attempt evidence reference is missing or changed"
                )
            if require_complete_usage and not attempt.usage.complete:
                raise HydraulicReviewPrimeLifecycleRecoveryError("Prime attempt usage is incomplete")
            if require_complete_usage and attempt.isolation is not self.isolation:
                raise HydraulicReviewPrimeLifecycleRecoveryError("Prime attempt isolation differs from the lifecycle")
            attempts.append(attempt)
        session_ids = [item.session_id for item in attempts]
        if len(session_ids) != len(set(session_ids)):
            raise HydraulicReviewPrimeLifecycleRecoveryError("Prime attempt session identity is duplicated")
        return tuple(attempts)

    def _ensure_paths(self, run_dir: Path) -> None:
        if _paths_overlap(run_dir.resolve(), self.actor_workspace_root.resolve()):
            raise ValueError("hydraulic-review Prime actor workspaces must be separate from lifecycle storage")

    def _ensure_configuration(
        self,
        *,
        run_dir: Path,
        lifecycle_id: str,
        lifecycle_spec_sha256: str,
        package_sha256: str,
    ) -> None:
        resolved_executable = resolve_prime_executable(self.executable)
        payload = {
            "schema_version": "2",
            "lifecycle_id": lifecycle_id,
            "lifecycle_spec_sha256": lifecycle_spec_sha256,
            "package_sha256": package_sha256,
            "model": self.model,
            "isolation": self.isolation.value,
            "limits": _limits_payload(self.limits),
            "executable": {
                "path": str(resolved_executable),
                "sha256": _sha256(resolved_executable),
            },
            "filesystem_boundary": {
                "actor_workspace_root": str(self.actor_workspace_root.resolve()),
                "package_dir": str(self.package_dir.resolve()),
                "run_dir": str(run_dir.resolve()),
                "additional_private_paths": sorted(str(path.resolve()) for path in self.additional_private_paths),
                "sibling_actor_workspaces_private": True,
            },
        }
        store = ImmutableByteStore(run_dir / "prime", host_private=True)
        store.publish_bytes("configuration.json", _canonical_json(payload))

    def _write_manifest(
        self,
        run_dir: Path,
        *,
        status: str,
        failure_kind: str | None = None,
    ) -> None:
        run = Path(run_dir).resolve()
        configuration = run / "prime" / "configuration.json"
        if not configuration.is_file():
            raise HydraulicReviewPrimeLifecycleRecoveryError("Prime lifecycle configuration is missing")
        attempts = self._load_attempts(run, require_complete_usage=False)
        usage = _aggregate_usage(attempts)
        payload = {
            "schema_version": "1",
            "configuration": "prime/configuration.json",
            "configuration_sha256": _sha256(configuration),
            "status": status,
            "failure_kind": failure_kind,
            "isolation": self.isolation.value,
            "limits": _limits_payload(self.limits),
            "usage": _usage_payload(usage),
            "elapsed_seconds": sum(item.elapsed_seconds for item in attempts),
            "topology": {
                "root_sessions": sum(item.topology.root_sessions for item in attempts),
                "child_sessions": sum(item.topology.child_sessions for item in attempts),
            },
            "attempts": [
                {
                    "checkpoint_id": item.checkpoint_id,
                    "attempt_id": item.attempt_id,
                    "session_id": item.session_id,
                    "prime_run": item.prime_run,
                    "prime_run_sha256": item.prime_run_sha256,
                    "transport_log": item.transport_log,
                    "transport_log_sha256": item.transport_log_sha256,
                    "session_state": item.session_state,
                    "stop_reason": item.stop_reason,
                    "limit_reason": item.limit_reason,
                    "isolation": item.isolation.value,
                    "benchmark_valid": item.benchmark_valid,
                }
                for item in attempts
            ],
            "benchmark_valid": bool(attempts)
            and all(item.benchmark_valid for item in attempts)
            and all(item.isolation is self.isolation for item in attempts)
            and self.isolation is not PrimeAcpIsolation.DEVELOPMENT_SAME_USER,
        }
        manifest_dir = run / "prime"
        replace_file_bytes_durable(
            manifest_dir,
            "manifest.json",
            _canonical_json(payload),
            host_private=True,
        )


def install_hydraulic_review_skill(actor_workspace: Path) -> Path:
    """Install the hydraulic-review skill and importable client in one actor workspace."""
    actor_workspace = actor_workspace.resolve()
    source = Path(__file__).with_name("skills") / "hydraulic-review"
    package_source = source / "src" / "hydraulic_review"
    package_destination = actor_workspace / "hydraulic_review"
    if package_destination.exists():
        if not _installed_tree_matches(package_source, package_destination):
            raise PrimeSkillInstallError("hydraulic-review package destination has different content")
    else:
        shutil.copytree(package_source, package_destination)
    return install_prime_skill(actor_workspace, source)


def run_hydraulic_review_prime_lifecycle(
    *,
    package_dir: Path,
    run_dir: Path,
    actor_workspace_root: Path,
    model: str,
    isolation: PrimeAcpIsolation,
    limits: HydraulicReviewPrimeLifecycleLimits,
    executable: str = "prime-agent",
    environment: Mapping[str, str] | None = None,
    additional_private_paths: Sequence[Path] = (),
    prime_session_runner: PrimeSessionRunner = run_prime_acp_session,
) -> HydraulicReviewPrimeLifecycleRun:
    """Run and verify the concrete hydraulic-review lifecycle without creating another coordinator."""
    package = package_dir.resolve()
    run = run_dir.resolve()
    validated_hydraulic_review_variant(package)
    spec = load_evidence_lifecycle_spec(package)
    if spec.lifecycle_id != LIFECYCLE_ID:
        raise ValueError("package is not the hydraulic-review hydraulic interaction lifecycle")
    resolver = build_hydraulic_operation_resolver(package, run)
    episode_environment = HydraulicReviewPrimeLifecycleEnvironment(
        package_dir=package,
        actor_workspace_root=actor_workspace_root,
        model=model,
        isolation=isolation,
        limits=limits,
        operation_resolver=resolver,
        executable=executable,
        environment=environment,
        additional_private_paths=additional_private_paths,
        prime_session_runner=prime_session_runner,
    )
    try:
        lifecycle = run_evidence_lifecycle(
            package,
            run,
            episode_environment=episode_environment,
            operation_resolver=resolver,
        )
    except Exception as exc:
        if (run / "prime" / "configuration.json").is_file():
            try:
                episode_environment.final_manifest(run, status="failed", failure_kind=type(exc).__name__)
            except Exception as reconciliation_error:
                exc.add_note(f"Prime manifest reconciliation failed: {reconciliation_error}")
        raise
    prime = episode_environment.final_manifest(run, status="complete")
    verification = verify_hydraulic_review_lifecycle(package, run)
    benchmark_valid = bool(
        lifecycle.get("status") == "complete" and prime["benchmark_valid"] and verification.get("passed")
    )
    return HydraulicReviewPrimeLifecycleRun(
        prime=prime,
        lifecycle=lifecycle,
        verification=verification,
        benchmark_valid=benchmark_valid,
    )


def _prime_instruction(request: LifecycleEpisodeRequest) -> str:
    return (
        "Complete only the active hydraulic-review lifecycle checkpoint. Load and follow the full "
        "`hydraulic-review` skill before the first operation. Use the scoped client to inspect evidence, "
        "execute declared operations, and "
        "offer one complete checkpoint submission. End the turn after the offer is accepted.\n\n" + request.instruction
    )


def _prime_failure(
    prime: PrimeAcpRun,
    offered_submission: dict[str, Any] | None,
    *,
    expected_isolation: PrimeAcpIsolation,
) -> str | None:
    if prime.error is not None or prime.session_state == "failed":
        return "prime_session_failed"
    if prime.exit_code != 0:
        return "prime_process_failed"
    if not prime.usage.complete:
        return "prime_usage_incomplete"
    if prime.isolation is not expected_isolation:
        return "prime_isolation_mismatch"
    if prime.limit_reason is not None:
        return prime.limit_reason
    if prime.session_state != "ended":
        return "prime_session_not_ended"
    if prime.stop_reason != "end_turn":
        return "prime_stop_reason_unsupported"
    if offered_submission is None:
        return "prime_submission_missing"
    return None


def _usage_evidence(usage: PrimeAcpUsage) -> _UsageEvidence:
    return _UsageEvidence(
        complete=usage.complete,
        model_calls=usage.model_calls,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        total_tokens=usage.total_tokens,
        cost_usd=usage.cost_usd,
    )


def _aggregate_usage(attempts: Sequence[_AttemptEvidence]) -> PrimeAcpUsage:
    return PrimeAcpUsage(
        complete=bool(attempts) and all(item.usage.complete for item in attempts),
        model_calls=sum(item.usage.model_calls for item in attempts),
        input_tokens=sum(item.usage.input_tokens for item in attempts),
        output_tokens=sum(item.usage.output_tokens for item in attempts),
        cache_read_tokens=sum(item.usage.cache_read_tokens for item in attempts),
        cache_write_tokens=sum(item.usage.cache_write_tokens for item in attempts),
        total_tokens=sum(item.usage.total_tokens for item in attempts),
        cost_usd=sum((item.usage.cost_usd for item in attempts), start=Decimal(0)),
    )


def _usage_payload(usage: PrimeAcpUsage) -> dict[str, Any]:
    return {
        "complete": usage.complete,
        "model_calls": usage.model_calls,
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cache_read_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": str(usage.cost_usd),
    }


def _limits_payload(limits: HydraulicReviewPrimeLifecycleLimits) -> dict[str, Any]:
    return {
        "max_sessions": limits.max_sessions,
        "max_model_calls": limits.max_model_calls,
        "max_tokens": limits.max_tokens,
        "max_cost_usd": str(limits.max_cost_usd),
        "max_wall_seconds": limits.max_wall_seconds,
    }


def _confined_reference(root: Path, relative: str) -> Path:
    path = PurePosixPath(relative)
    if path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise HydraulicReviewPrimeLifecycleRecoveryError("Prime evidence reference is unsafe")
    target = root.joinpath(*path.parts)
    for parent in (target, *target.parents):
        if parent == root.parent:
            break
        if parent.is_symlink():
            raise HydraulicReviewPrimeLifecycleRecoveryError("Prime evidence reference contains a symbolic link")
    resolved = target.resolve()
    if resolved != root and root not in resolved.parents:
        raise HydraulicReviewPrimeLifecycleRecoveryError("Prime evidence reference escaped the lifecycle run")
    return resolved


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


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise HydraulicReviewPrimeLifecycleRecoveryError(f"expected JSON object: {path.name}")
    return value


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths_overlap(first: Path, second: Path) -> bool:
    first = first.resolve()
    second = second.resolve()
    return first == second or first in second.parents or second in first.parents


__all__ = [
    "HydraulicReviewPrimeLifecycleLimits",
    "HydraulicReviewPrimeLifecycleRun",
    "install_hydraulic_review_skill",
    "run_hydraulic_review_prime_lifecycle",
]
