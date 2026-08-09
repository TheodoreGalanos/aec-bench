# ABOUTME: Stores immutable rollout requests, child receipts, and ordered lineage records.
# ABOUTME: Confines host-private group paths and provides one durable lock per rollout group.

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from aec_bench.contracts.continual_world import (
    ContinualRolloutChildReceipt,
    ContinualRolloutChildRequest,
    ContinualRolloutGroupRequest,
    ContinualRolloutLineage,
)
from aec_bench.ledger.immutable_byte_store import (
    ImmutableArtifactCollisionError,
    ImmutableArtifactStoreError,
    ImmutableByteStore,
)
from aec_bench.ledger.local_lock import exclusive_local_file_lock

_SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_ModelT = TypeVar("_ModelT", bound=BaseModel)


class ContinualRolloutError(RuntimeError):
    """Stable shared failure for rollout validation, storage, and task ports."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}")


class ContinualRolloutRepository:
    """Host-private immutable repository for generic rollout orchestration."""

    def __init__(self, root: Path, *, disjoint_roots: tuple[Path, ...] = ()) -> None:
        try:
            self._store = ImmutableByteStore(
                Path(root),
                disjoint_roots=disjoint_roots,
                host_private=True,
            )
        except ImmutableArtifactStoreError as exc:
            raise ContinualRolloutError("artifact-confinement", str(exc)) from exc

    @property
    def root(self) -> Path:
        """Return the trusted physical repository root."""
        return self._store.root

    def validate_storage_identities(
        self,
        group_id: str,
        child_ids: tuple[str, ...],
    ) -> None:
        """Validate every path identity without preparing storage."""
        _safe_id(group_id, label="group")
        for child_id in child_ids:
            _safe_id(child_id, label="child")

    @contextmanager
    def locked(self, group_id: str) -> Iterator[None]:
        """Hold the confined mutation lock for exactly one rollout group."""
        selected = _safe_id(group_id, label="group")
        with exclusive_local_file_lock(
            self.root,
            f".locks/groups/{selected}.lock",
            error_factory=lambda error: ContinualRolloutError("artifact-confinement", str(error)),
        ):
            yield

    @contextmanager
    def materializing_child(self, group_id: str, child_id: str) -> Iterator[None]:
        """Serialize task-port materialization for one exact child identity."""
        selected_group = _safe_id(group_id, label="group")
        selected_child = _safe_id(child_id, label="child")
        with exclusive_local_file_lock(
            self.root,
            f".locks/groups/{selected_group}/children/{selected_child}.lock",
            error_factory=lambda error: ContinualRolloutError("artifact-confinement", str(error)),
        ):
            yield

    def publish_group_request(self, request: ContinualRolloutGroupRequest) -> None:
        self._publish(
            self._request_path(request.group_id),
            request,
            conflict_code="request-conflict",
        )

    def load_group_request(self, group_id: str) -> ContinualRolloutGroupRequest:
        return self._load(self._request_path(group_id), ContinualRolloutGroupRequest)

    def publish_child_request(
        self,
        group_id: str,
        child: ContinualRolloutChildRequest,
    ) -> None:
        self._publish(
            self._child_request_path(group_id, child.child_id),
            child,
            conflict_code="child-request-conflict",
        )

    def load_child_request(self, group_id: str, child_id: str) -> ContinualRolloutChildRequest:
        return self._load(
            self._child_request_path(group_id, child_id),
            ContinualRolloutChildRequest,
        )

    def child_request_exists(self, group_id: str, child_id: str) -> bool:
        return self._exists(self._child_request_path(group_id, child_id))

    def publish_child_receipt(self, receipt: ContinualRolloutChildReceipt) -> None:
        self._publish(
            self._child_receipt_path(receipt.group_id, receipt.child_id),
            receipt,
            conflict_code="child-receipt-conflict",
        )

    def load_child_receipt(self, group_id: str, child_id: str) -> ContinualRolloutChildReceipt:
        return self._load(
            self._child_receipt_path(group_id, child_id),
            ContinualRolloutChildReceipt,
        )

    def child_receipt_exists(self, group_id: str, child_id: str) -> bool:
        return self._exists(self._child_receipt_path(group_id, child_id))

    def publish_lineage(self, lineage: ContinualRolloutLineage) -> None:
        self._publish(
            self._lineage_path(lineage.group_id),
            lineage,
            conflict_code="lineage-conflict",
        )

    def load_lineage(self, group_id: str) -> ContinualRolloutLineage:
        return self._load(self._lineage_path(group_id), ContinualRolloutLineage)

    def lineage_exists(self, group_id: str) -> bool:
        return self._exists(self._lineage_path(group_id))

    def child_world_root(self, group_id: str, child_id: str) -> Path:
        """Return the confined task-owned world destination for one reserved child."""
        selected_group = _safe_id(group_id, label="group")
        selected_child = _safe_id(child_id, label="child")
        try:
            return self._store.prepare_directory_destination(
                f"groups/{selected_group}/children/{selected_child}",
                "world",
            )
        except ImmutableArtifactStoreError as exc:
            raise ContinualRolloutError("artifact-confinement", str(exc)) from exc

    def _publish(self, relative_path: str, value: BaseModel, *, conflict_code: str) -> None:
        payload = _canonical_json_bytes(value)
        try:
            self._store.publish_bytes(relative_path, payload)
        except ImmutableArtifactCollisionError as exc:
            raise ContinualRolloutError(conflict_code, relative_path) from exc
        except ImmutableArtifactStoreError as exc:
            raise ContinualRolloutError("artifact-confinement", str(exc)) from exc

    def _load(self, relative_path: str, model_type: type[_ModelT]) -> _ModelT:
        try:
            payload = self._store.load_bytes(relative_path)
            return model_type.model_validate_json(payload)
        except (ImmutableArtifactStoreError, ValidationError) as exc:
            raise ContinualRolloutError("artifact-integrity", f"{relative_path}: {exc}") from exc

    def _exists(self, relative_path: str) -> bool:
        try:
            return self._store.exists(relative_path)
        except ImmutableArtifactStoreError as exc:
            raise ContinualRolloutError("artifact-confinement", str(exc)) from exc

    @staticmethod
    def _request_path(group_id: str) -> str:
        return f"groups/{_safe_id(group_id, label='group')}/request.json"

    @staticmethod
    def _lineage_path(group_id: str) -> str:
        return f"groups/{_safe_id(group_id, label='group')}/lineage.json"

    @staticmethod
    def _child_request_path(group_id: str, child_id: str) -> str:
        return f"groups/{_safe_id(group_id, label='group')}/children/{_safe_id(child_id, label='child')}/request.json"

    @staticmethod
    def _child_receipt_path(group_id: str, child_id: str) -> str:
        return f"groups/{_safe_id(group_id, label='group')}/children/{_safe_id(child_id, label='child')}/receipt.json"


def _safe_id(value: str, *, label: str) -> str:
    if not _SAFE_ID.fullmatch(value):
        raise ContinualRolloutError("unsafe-identity", f"invalid {label} id")
    return value


def _canonical_json_bytes(value: BaseModel) -> bytes:
    payload = value.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
