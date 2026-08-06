# ABOUTME: Owns bounded, independently provisioned environment leases for proposal DAGs.
# ABOUTME: Fails closed on capacity or identity sharing and persists deterministic lifecycle receipts.

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import stat
import tempfile
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol, cast

from aec_bench.contracts.harness_kernel import (
    canonical_content_sha256,
    validate_sha256,
)
from aec_bench.harness.proposal_session_runtime import ProposalSessionEnvironment

_INVOCATION_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*\Z")


class ProposalEnvironmentPoolError(RuntimeError):
    """Fail-closed pool lifecycle or lease error."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class IsolatedProposalEnvironmentIdentity:
    """Provider identities proving one independently managed environment."""

    environment_session_id: str
    runtime_snapshot_identity: str
    trial_instance_identity: str
    candidate_container_identity: str
    runtime_archive_sha256: str
    runtime_archive_content_sha256: str

    def __post_init__(self) -> None:
        values = (
            self.environment_session_id,
            self.runtime_snapshot_identity,
            self.trial_instance_identity,
            self.candidate_container_identity,
        )
        if any(not isinstance(value, str) or not value.strip() for value in values):
            raise ValueError("isolated proposal environment identities must be non-empty")
        validate_sha256(self.runtime_archive_sha256)
        validate_sha256(self.runtime_archive_content_sha256)


class ManagedProposalSessionEnvironment(Protocol):
    """Proposal environment whose whole provider lifecycle is pool-owned."""

    session_id: str
    cleanup_receipt_path: Path

    async def start(self, force_build: bool) -> None: ...

    async def stop(self, delete: bool) -> None: ...

    def isolated_environment_identity(
        self,
    ) -> IsolatedProposalEnvironmentIdentity: ...


ManagedProposalEnvironmentFactory = Callable[
    [int],
    ManagedProposalSessionEnvironment,
]


class _PoolState(StrEnum):
    NEW = "new"
    STARTING = "starting"
    OPEN = "open"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass
class _PoolSlot:
    index: int
    environment: ManagedProposalSessionEnvironment
    identity: IsolatedProposalEnvironmentIdentity | None = None
    started: bool = False


class IsolatedProposalEnvironmentPool:
    """Bounded ready-set pool that never waits, shares, or silently serializes."""

    def __init__(
        self,
        *,
        capacity: int,
        receipt_root: Path | str,
        expected_runtime_archive_sha256: str,
        expected_runtime_archive_content_sha256: str,
        environment_factory: ManagedProposalEnvironmentFactory,
    ) -> None:
        if not isinstance(capacity, int) or isinstance(capacity, bool) or capacity < 1 or capacity > 256:
            raise ValueError("proposal environment pool capacity must be between 1 and 256")
        validate_sha256(expected_runtime_archive_sha256)
        validate_sha256(expected_runtime_archive_content_sha256)
        self.capacity = capacity
        self.receipt_root = Path(receipt_root)
        self.expected_runtime_archive_sha256 = expected_runtime_archive_sha256
        self.expected_runtime_archive_content_sha256 = expected_runtime_archive_content_sha256
        self._environment_factory = environment_factory
        self._state = _PoolState.NEW
        self._slots: list[_PoolSlot] = []
        self._available_slots: list[int] = []
        self._active_by_invocation: dict[str, int] = {}
        self._seen_invocations: set[str] = set()
        self._lock = asyncio.Lock()
        self._cleanup_completed = False

    @property
    def manifest_path(self) -> Path:
        """Canonical provisioned-pool identity receipt."""

        return self.receipt_root / "pool-manifest.json"

    @property
    def cleanup_receipt_path(self) -> Path:
        """Canonical proof that every managed environment was stopped."""

        return self.receipt_root / "pool-cleanup.json"

    @property
    def lease_receipts_dir(self) -> Path:
        """Directory of one immutable receipt per invocation lease."""

        return self.receipt_root / "leases"

    @property
    def cleanup_artifacts_dir(self) -> Path:
        """Exact provider cleanup receipts copied into session evidence."""

        return self.receipt_root / "cleanup-artifacts"

    async def __aenter__(self) -> IsolatedProposalEnvironmentPool:
        if self._state is not _PoolState.NEW:
            raise ProposalEnvironmentPoolError(
                "environment_pool_state_invalid",
                "proposal environment pool can only be entered once",
            )
        self._state = _PoolState.STARTING
        worker = asyncio.create_task(
            self._provision(),
            name="proposal-environment-pool:provision",
        )
        try:
            await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation:
            failures: list[BaseException] = []
            try:
                await worker
            except BaseException as error:
                failures.append(error)
            failures.extend(await self._cleanup_after_failed_entry())
            if failures:
                raise BaseExceptionGroup(
                    "proposal environment pool provisioning was cancelled and cleanup failed",
                    [cancellation, *failures],
                ) from cancellation
            raise
        except BaseException as provisioning_error:
            cleanup_failures = await self._cleanup_after_failed_entry()
            if cleanup_failures:
                raise BaseExceptionGroup(
                    "proposal environment pool provisioning and cleanup failed",
                    [provisioning_error, *cleanup_failures],
                ) from provisioning_error
            raise
        self._state = _PoolState.OPEN
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object,
    ) -> bool:
        del exc_type, traceback
        if self._state is not _PoolState.OPEN:
            raise ProposalEnvironmentPoolError(
                "environment_pool_state_invalid",
                "proposal environment pool cannot close outside its open lifecycle",
            )
        self._state = _PoolState.CLOSING
        worker = asyncio.create_task(
            self._cleanup_environments(),
            name="proposal-environment-pool:cleanup",
        )
        try:
            cleanup_failures = await asyncio.shield(worker)
        except asyncio.CancelledError as cancellation:
            cleanup_failures = []
            try:
                cleanup_failures.extend(await worker)
            except BaseException as error:
                cleanup_failures.append(error)
            self._state = _PoolState.CLOSED
            if cleanup_failures:
                raise BaseExceptionGroup(
                    "proposal environment pool cleanup was cancelled and failed",
                    [cancellation, *cleanup_failures],
                ) from cancellation
            raise
        self._state = _PoolState.CLOSED
        if cleanup_failures:
            causes: list[BaseException] = list(cleanup_failures)
            if exc is not None:
                causes.insert(0, exc)
            raise BaseExceptionGroup(
                "proposal environment pool cleanup failed",
                causes,
            )
        return False

    def lease(
        self,
        *,
        invocation_id: str,
    ) -> AbstractAsyncContextManager[ProposalSessionEnvironment]:
        """Lease one independent environment or fail immediately at capacity."""

        return self._lease(invocation_id=invocation_id)

    @asynccontextmanager
    async def _lease(
        self,
        *,
        invocation_id: str,
    ) -> AsyncIterator[ProposalSessionEnvironment]:
        slot = await self._acquire(invocation_id=invocation_id)
        before = self._require_bound_identity(slot)
        outcome = "completed"
        try:
            yield cast(ProposalSessionEnvironment, slot.environment)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except BaseException:
            outcome = "failed"
            raise
        finally:
            identity_error: BaseException | None = None
            after: IsolatedProposalEnvironmentIdentity | None = None
            try:
                after = slot.environment.isolated_environment_identity()
                self._validate_runtime_binding(after)
            except BaseException as error:
                identity_error = error
            await self._release(
                slot=slot,
                invocation_id=invocation_id,
                before=before,
                after=after,
                outcome=outcome,
            )
            if identity_error is not None:
                raise ProposalEnvironmentPoolError(
                    "environment_lease_identity_invalid",
                    f"proposal environment lease identity could not be verified: {identity_error}",
                ) from identity_error

    async def _provision(self) -> None:
        _create_receipt_root(self.receipt_root)
        self.lease_receipts_dir.mkdir()
        self.cleanup_artifacts_dir.mkdir()
        try:
            self._slots = [
                _PoolSlot(
                    index=index,
                    environment=self._environment_factory(index),
                )
                for index in range(self.capacity)
            ]
        except Exception as error:
            raise ProposalEnvironmentPoolError(
                "environment_pool_factory_failed",
                f"proposal environment factory failed: {error}",
            ) from error

        async def start_slot(slot: _PoolSlot) -> None:
            await slot.environment.start(force_build=False)
            slot.started = True

        results = await asyncio.gather(
            *(start_slot(slot) for slot in self._slots),
            return_exceptions=True,
        )
        failures = [result for result in results if isinstance(result, BaseException)]
        if failures:
            raise BaseExceptionGroup(
                "proposal environment pool provisioning failed",
                failures,
            )
        identities = tuple(slot.environment.isolated_environment_identity() for slot in self._slots)
        self._validate_identities(identities)
        for slot, identity in zip(self._slots, identities, strict=True):
            slot.identity = identity
        self._available_slots = [slot.index for slot in self._slots]
        _write_content_addressed_json(
            self.manifest_path,
            {
                "schema_version": "aecbench.proposal-environment-pool-manifest.v1",
                "capacity": self.capacity,
                "runtime_archive_sha256": self.expected_runtime_archive_sha256,
                "runtime_archive_content_sha256": (self.expected_runtime_archive_content_sha256),
                "environments": [
                    {
                        "slot": slot.index,
                        **asdict(self._require_bound_identity(slot)),
                    }
                    for slot in self._slots
                ],
            },
        )

    async def _acquire(self, *, invocation_id: str) -> _PoolSlot:
        if not isinstance(invocation_id, str) or not _INVOCATION_ID.fullmatch(
            invocation_id,
        ):
            raise ProposalEnvironmentPoolError(
                "environment_lease_identity_invalid",
                "proposal environment lease requires a safe invocation identity",
            )
        async with self._lock:
            if self._state is not _PoolState.OPEN:
                raise ProposalEnvironmentPoolError(
                    "environment_pool_state_invalid",
                    "proposal environment pool is not open for leases",
                )
            if invocation_id in self._seen_invocations:
                raise ProposalEnvironmentPoolError(
                    "environment_lease_replayed",
                    f"proposal invocation {invocation_id!r} already leased an environment",
                )
            if not self._available_slots:
                raise ProposalEnvironmentPoolError(
                    "environment_pool_exhausted",
                    "proposal environment pool exhausted its declared capacity",
                )
            slot_index = self._available_slots.pop(0)
            slot = self._slots[slot_index]
            identity = self._require_bound_identity(slot)
            active_instance_ids = {
                self._require_bound_identity(self._slots[index]).trial_instance_identity
                for index in self._active_by_invocation.values()
            }
            if identity.trial_instance_identity in active_instance_ids:
                raise ProposalEnvironmentPoolError(
                    "environment_pool_identity_collision",
                    "proposal environment pool attempted to share one provider instance",
                )
            self._active_by_invocation[invocation_id] = slot_index
            self._seen_invocations.add(invocation_id)
            return slot

    async def _release(
        self,
        *,
        slot: _PoolSlot,
        invocation_id: str,
        before: IsolatedProposalEnvironmentIdentity,
        after: IsolatedProposalEnvironmentIdentity | None,
        outcome: str,
    ) -> None:
        async with self._lock:
            observed_slot = self._active_by_invocation.pop(invocation_id, None)
            if observed_slot != slot.index:
                raise ProposalEnvironmentPoolError(
                    "environment_lease_state_invalid",
                    "proposal environment lease ownership changed before release",
                )
            if after is not None:
                other_container_ids = {
                    self._require_bound_identity(other).candidate_container_identity
                    for other in self._slots
                    if other.index != slot.index
                }
                if after.candidate_container_identity in other_container_ids:
                    raise ProposalEnvironmentPoolError(
                        "environment_pool_identity_collision",
                        "proposal environment lease returned a shared candidate container",
                    )
            _write_content_addressed_json(
                self.lease_receipts_dir / f"{invocation_id}.json",
                {
                    "schema_version": "aecbench.proposal-environment-lease.v1",
                    "invocation_id": invocation_id,
                    "slot": slot.index,
                    "outcome": outcome,
                    "before": asdict(before),
                    "after": None if after is None else asdict(after),
                },
            )
            if after is not None:
                slot.identity = after
            self._available_slots.append(slot.index)
            self._available_slots.sort()

    def _validate_identities(
        self,
        identities: tuple[IsolatedProposalEnvironmentIdentity, ...],
    ) -> None:
        if len(identities) != self.capacity:
            raise ProposalEnvironmentPoolError(
                "environment_pool_undercapacity",
                "proposal environment pool did not provision its declared capacity",
            )
        for identity in identities:
            self._validate_runtime_binding(identity)
        identity_fields = (
            "environment_session_id",
            "runtime_snapshot_identity",
            "trial_instance_identity",
            "candidate_container_identity",
        )
        for field_name in identity_fields:
            values = tuple(cast(str, getattr(identity, field_name)) for identity in identities)
            if len(values) != len(set(values)):
                raise ProposalEnvironmentPoolError(
                    "environment_pool_identity_collision",
                    f"proposal environment pool shares {field_name.replace('_', ' ')}",
                )

    def _validate_runtime_binding(
        self,
        identity: IsolatedProposalEnvironmentIdentity,
    ) -> None:
        if (
            identity.runtime_archive_sha256 != self.expected_runtime_archive_sha256
            or identity.runtime_archive_content_sha256 != self.expected_runtime_archive_content_sha256
        ):
            raise ProposalEnvironmentPoolError(
                "environment_pool_runtime_mismatch",
                "proposal environment differs from the exact runtime archive binding",
            )

    async def _cleanup_after_failed_entry(self) -> list[BaseException]:
        self._state = _PoolState.CLOSING
        cleanup_failures = await self._cleanup_environments()
        self._state = _PoolState.CLOSED
        return cleanup_failures

    async def _cleanup_environments(self) -> list[BaseException]:
        if self._cleanup_completed:
            return []
        self._cleanup_completed = True

        async def stop_slot(slot: _PoolSlot) -> BaseException | None:
            try:
                await slot.environment.stop(delete=True)
            except BaseException as error:
                return error
            return None

        results = await asyncio.gather(
            *(stop_slot(slot) for slot in self._slots),
        )
        failures: list[BaseException] = [result for result in results if result is not None]
        cleanup_entries = []
        for slot, result in zip(self._slots, results, strict=True):
            cleanup_path = Path(slot.environment.cleanup_receipt_path)
            copied_path: str | None = None
            copied_sha256: str | None = None
            try:
                copied_path, copied_sha256 = self._copy_cleanup_receipt(
                    slot=slot,
                    source_path=cleanup_path,
                )
            except BaseException as error:
                failures.append(error)
            cleanup_entries.append(
                {
                    "slot": slot.index,
                    "environment_session_id": slot.environment.session_id,
                    "stop_completed": result is None,
                    "cleanup_receipt_path": copied_path,
                    "cleanup_receipt_sha256": copied_sha256,
                },
            )
        if self.receipt_root.is_dir():
            _write_content_addressed_json(
                self.cleanup_receipt_path,
                {
                    "schema_version": "aecbench.proposal-environment-pool-cleanup.v1",
                    "capacity": self.capacity,
                    "runtime_archive_sha256": self.expected_runtime_archive_sha256,
                    "runtime_archive_content_sha256": (self.expected_runtime_archive_content_sha256),
                    "pool_manifest_content_sha256": _receipt_content_sha256(
                        self.manifest_path,
                    ),
                    "status": "completed" if not failures else "failed",
                    "environments": cleanup_entries,
                },
            )
        return failures

    def _copy_cleanup_receipt(
        self,
        *,
        slot: _PoolSlot,
        source_path: Path,
    ) -> tuple[str, str]:
        content = _read_regular_cleanup_receipt(source_path)
        artifact_sha256 = hashlib.sha256(content).hexdigest()
        destination = self.cleanup_artifacts_dir / f"slot-{slot.index:03d}.{artifact_sha256}.json"
        _write_bytes_atomic(destination, content)
        return (
            destination.relative_to(self.receipt_root).as_posix(),
            artifact_sha256,
        )

    @staticmethod
    def _require_bound_identity(
        slot: _PoolSlot,
    ) -> IsolatedProposalEnvironmentIdentity:
        if slot.identity is None:
            raise ProposalEnvironmentPoolError(
                "environment_pool_identity_missing",
                "proposal environment pool slot lacks its provisioned identity",
            )
        return slot.identity


def _create_receipt_root(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise ProposalEnvironmentPoolError(
            "environment_pool_receipt_collision",
            f"proposal environment pool receipt root already exists: {path}",
        )
    try:
        path.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        raise ProposalEnvironmentPoolError(
            "environment_pool_receipt_failed",
            f"proposal environment pool receipt root could not be created: {error}",
        ) from error


def _write_content_addressed_json(
    path: Path,
    payload: dict[str, object],
) -> None:
    if path.exists() or path.is_symlink():
        raise ProposalEnvironmentPoolError(
            "environment_pool_receipt_collision",
            f"proposal environment pool receipt already exists: {path}",
        )
    receipt = dict(payload)
    receipt["content_sha256"] = canonical_content_sha256(receipt)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError as error:
        raise ProposalEnvironmentPoolError(
            "environment_pool_receipt_failed",
            f"proposal environment pool receipt could not be persisted: {error}",
        ) from error
    finally:
        temporary.unlink(missing_ok=True)


def _receipt_content_sha256(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    value = payload.get("content_sha256")
    if not isinstance(value, str):
        return None
    try:
        return validate_sha256(value)
    except ValueError:
        return None


def _read_regular_cleanup_receipt(path: Path) -> bytes:
    if path.is_symlink():
        raise ProposalEnvironmentPoolError(
            "environment_pool_cleanup_receipt_invalid",
            "proposal environment cleanup receipt must not be a symbolic link",
        )
    try:
        path_stat = path.stat(follow_symlinks=False)
    except OSError as error:
        raise ProposalEnvironmentPoolError(
            "environment_pool_cleanup_receipt_invalid",
            f"proposal environment cleanup receipt cannot be inspected: {error}",
        ) from error
    if not stat.S_ISREG(path_stat.st_mode):
        raise ProposalEnvironmentPoolError(
            "environment_pool_cleanup_receipt_invalid",
            "proposal environment cleanup receipt must be a regular file",
        )
    if path_stat.st_size < 1 or path_stat.st_size > 1024 * 1024:
        raise ProposalEnvironmentPoolError(
            "environment_pool_cleanup_receipt_invalid",
            "proposal environment cleanup receipt exceeds its size boundary",
        )
    try:
        return path.read_bytes()
    except OSError as error:
        raise ProposalEnvironmentPoolError(
            "environment_pool_cleanup_receipt_invalid",
            f"proposal environment cleanup receipt cannot be read: {error}",
        ) from error


def _write_bytes_atomic(path: Path, content: bytes) -> None:
    if path.exists() or path.is_symlink():
        raise ProposalEnvironmentPoolError(
            "environment_pool_receipt_collision",
            f"proposal environment pool artifact already exists: {path}",
        )
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_raw)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    except OSError as error:
        raise ProposalEnvironmentPoolError(
            "environment_pool_receipt_failed",
            f"proposal environment pool artifact could not be persisted: {error}",
        ) from error
    finally:
        temporary.unlink(missing_ok=True)
