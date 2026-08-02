# ABOUTME: Stores private rollout requests, child receipts, lineage, and treatment evidence.
# ABOUTME: Uses confined host directories, immutable files, and a process-safe group lock.

from __future__ import annotations

import fcntl
import os
import re
import stat
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import NoReturn, TypeVar

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.physical_treatments import (
    PumpStationPhysicalTreatmentActivationRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.rollout_models import (
    PumpStationPhysicalTreatmentActivationReceipt,
    PumpStationPhysicalTreatmentScheduleReceipt,
    PumpStationRolloutChildReceipt,
    PumpStationRolloutGroupRequest,
    PumpStationRolloutLineage,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_serialization import (
    load_pump_station_artifact,
    pump_station_artifact_bytes,
)

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")
ArtifactT = TypeVar("ArtifactT")


class PumpStationRolloutRepositoryError(RuntimeError):
    """Raised when private rollout evidence is missing, unsafe, or conflicting."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationRolloutRepositoryError(code, detail)


def _identity(value: str, field_name: str) -> str:
    if _SAFE_ID.fullmatch(value) is None:
        _fail("rollout-identity", f"{field_name} is not a safe identity")
    return value


class PumpStationRolloutRepository:
    """Confined durable repository for all children from rollout origins."""

    def __init__(self, root: Path) -> None:
        selected = Path(root)
        if selected.exists() and (selected.is_symlink() or not selected.is_dir()):
            _fail("rollout-confinement", "rollout root must be a plain directory")
        selected.mkdir(parents=True, exist_ok=True)
        selected.chmod(0o700)
        self._root = selected.resolve(strict=True)
        self._lock_path = self._root / ".rollout.lock"

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Serialize group and treatment publication across local processes."""

        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._lock_path, flags, 0o600)
        try:
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                _fail("rollout-confinement", "rollout lock is not a regular file")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
        finally:
            os.close(descriptor)

    def group_root(self, group_id: str) -> Path:
        """Return one confined group directory."""

        return self._directory("groups", _identity(group_id, "group_id"))

    def child_world_root(self, group_id: str, child_id: str) -> Path:
        """Return one child world-run root without creating sibling access."""

        return self._directory(
            "groups",
            _identity(group_id, "group_id"),
            "children",
            _identity(child_id, "child_id"),
            "world-run",
        )

    def publish_group_request(self, request: PumpStationRolloutGroupRequest) -> None:
        """Publish the exact idempotent group input."""

        self._publish(
            self.group_root(request.group_id) / "request.json",
            request,
            conflict_code="request-id-conflict",
        )

    def load_group_request(self, group_id: str) -> PumpStationRolloutGroupRequest:
        """Load one immutable group input."""

        return self._load(
            self.group_root(group_id) / "request.json",
            PumpStationRolloutGroupRequest,
        )

    def group_request_payload_if_present(self, group_id: str) -> bytes | None:
        """Load confined request bytes without selecting a rollout schema."""

        path = self.group_root(group_id) / "request.json"
        if not path.exists():
            return None
        return self._read(path)

    def publish_child_receipt(self, receipt: PumpStationRolloutChildReceipt) -> None:
        """Publish one child creation receipt."""

        path = self.group_root(receipt.group_id) / "children" / receipt.child_id
        self._publish(
            path / "branch-receipt.json",
            receipt,
            conflict_code="child-id-conflict",
        )

    def load_child_receipt(
        self,
        group_id: str,
        child_id: str,
    ) -> PumpStationRolloutChildReceipt:
        """Load one child creation receipt."""

        path = self.group_root(group_id) / "children" / _identity(child_id, "child_id")
        return self._load(path / "branch-receipt.json", PumpStationRolloutChildReceipt)

    def publish_lineage(self, lineage: PumpStationRolloutLineage) -> None:
        """Publish the complete group lineage after all children exist."""

        self._publish(
            self.group_root(lineage.group_id) / "lineage.json",
            lineage,
            conflict_code="lineage-conflict",
        )

    def load_lineage(self, group_id: str) -> PumpStationRolloutLineage:
        """Load one complete rollout lineage."""

        return self._load(
            self.group_root(group_id) / "lineage.json",
            PumpStationRolloutLineage,
        )

    def lineage_exists(self, group_id: str) -> bool:
        """Report whether complete lineage is durable for one group."""

        return (self.group_root(group_id) / "lineage.json").is_file()

    def child_receipt_exists(self, group_id: str, child_id: str) -> bool:
        """Report whether one child receipt is durable without creating the child."""

        return (
            self.group_root(group_id) / "children" / _identity(child_id, "child_id") / "branch-receipt.json"
        ).is_file()

    def publish_treatment_schedule(
        self,
        receipt: PumpStationPhysicalTreatmentScheduleReceipt,
    ) -> None:
        """Publish one private treatment declaration."""

        path = self._treatment_root(
            receipt.request.group_id,
            receipt.request.child_id,
            receipt.request.request_id,
        )
        self._publish(
            path / "schedule-receipt.json",
            receipt,
            conflict_code="treatment-request-id-conflict",
        )

    def load_treatment_schedule(
        self,
        group_id: str,
        child_id: str,
        request_id: str,
    ) -> PumpStationPhysicalTreatmentScheduleReceipt:
        """Load one private treatment declaration."""

        return self._load(
            self._treatment_root(group_id, child_id, request_id) / "schedule-receipt.json",
            PumpStationPhysicalTreatmentScheduleReceipt,
        )

    def publish_activation_request(
        self,
        group_id: str,
        child_id: str,
        request_id: str,
        request: PumpStationPhysicalTreatmentActivationRequest,
    ) -> None:
        """Publish the exact child-state binding before changing the child."""

        self._publish(
            self._treatment_root(group_id, child_id, request_id) / "activation-request.json",
            request,
            conflict_code="treatment-activation-conflict",
        )

    def load_activation_request(
        self,
        group_id: str,
        child_id: str,
        request_id: str,
    ) -> PumpStationPhysicalTreatmentActivationRequest:
        """Load one immutable activation input for crash recovery."""

        return self._load(
            self._treatment_root(group_id, child_id, request_id) / "activation-request.json",
            PumpStationPhysicalTreatmentActivationRequest,
        )

    def activation_request_exists(
        self,
        group_id: str,
        child_id: str,
        request_id: str,
    ) -> bool:
        """Report whether treatment activation began before a restart."""

        return (self._treatment_root(group_id, child_id, request_id) / "activation-request.json").is_file()

    def publish_treatment_activation(
        self,
        receipt: PumpStationPhysicalTreatmentActivationReceipt,
    ) -> None:
        """Publish one treatment-to-child transition link."""

        request = receipt.request
        self._publish(
            self._treatment_root(request.group_id, request.child_id, request.request_id) / "activation-receipt.json",
            receipt,
            conflict_code="treatment-activation-conflict",
        )

    def load_treatment_activation(
        self,
        group_id: str,
        child_id: str,
        request_id: str,
    ) -> PumpStationPhysicalTreatmentActivationReceipt:
        """Load one realised treatment receipt."""

        return self._load(
            self._treatment_root(group_id, child_id, request_id) / "activation-receipt.json",
            PumpStationPhysicalTreatmentActivationReceipt,
        )

    def treatment_activation_exists(
        self,
        group_id: str,
        child_id: str,
        request_id: str,
    ) -> bool:
        """Report whether a complete treatment receipt is durable."""

        return (self._treatment_root(group_id, child_id, request_id) / "activation-receipt.json").is_file()

    def _treatment_root(self, group_id: str, child_id: str, request_id: str) -> Path:
        return self._directory(
            "groups",
            _identity(group_id, "group_id"),
            "children",
            _identity(child_id, "child_id"),
            "treatments",
            _identity(request_id, "treatment_request_id"),
        )

    def _directory(self, *parts: str) -> Path:
        path = self._root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        path.chmod(0o700)
        resolved = path.resolve(strict=True)
        if not resolved.is_relative_to(self._root):
            _fail("rollout-confinement", "rollout path escapes its root")
        return resolved

    def _publish(
        self,
        path: Path,
        value: object,
        *,
        conflict_code: str,
    ) -> None:
        payload = pump_station_artifact_bytes(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.parent.chmod(0o700)
        if path.exists():
            if self._read(path) != payload:
                _fail(conflict_code, path.name)
            return
        temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0),
            0o600,
        )
        try:
            with os.fdopen(descriptor, "wb", closefd=False) as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            try:
                os.link(temporary, path)
            except FileExistsError:
                if self._read(path) != payload:
                    _fail(conflict_code, path.name)
            finally:
                temporary.unlink(missing_ok=True)
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass

    def _load(self, path: Path, artifact_type: type[ArtifactT]) -> ArtifactT:
        return load_pump_station_artifact(self._read(path), artifact_type)

    def _read(self, path: Path) -> bytes:
        if path.is_symlink() or not path.is_file():
            _fail("rollout-artifact", f"missing or unsafe artifact {path.name}")
        details = path.stat(follow_symlinks=False)
        if not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) & 0o077:
            _fail("rollout-confinement", f"artifact {path.name} is not host-private")
        return path.read_bytes()
