# ABOUTME: Creates durable ASW-8 rollout-v2 children from verified coupled-world snapshots.
# ABOUTME: Preserves public evidence, starts fresh private retrieval state, and isolates every branch.

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, NoReturn, cast

from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_evaluation import (
    verify_coupled_run,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_run import (
    PumpStationCoupledRun,
    PumpStationCoupledRunRepository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_runtime import (
    PumpStationCoupledTreatmentRequest,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.coupled_temporal import (
    copy_coupled_child_temporal_repository,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.stewardship_identity import (
    canonical_stewardship_value,
    stewardship_content_id,
)
from aec_bench.task_world_templates.stewardship.wastewater_pump_station.world_run_models import (
    PumpStationInitialStateSource,
)

PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION = "pump-station.rollout-request.v2"
PUMP_STATION_COUPLED_ROLLOUT_RECEIPT_VERSION = "pump-station.rollout-child-receipt.v2"
PUMP_STATION_COUPLED_ROLLOUT_LINEAGE_VERSION = "pump-station.rollout-lineage.v2"
PUMP_STATION_COUPLED_TEMPORAL_STATE_VERSION = "pump-station.rollout-temporal-state.v2"
PUMP_STATION_COUPLED_ROLLOUT_CONTROL_VERSION = "pump-station.rollout-control.v2"
_TASK_WORLD_ID = "wastewater-pump-station-stewardship.v1"
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class PumpStationCoupledRolloutError(ValueError):
    """Raised when rollout-v2 authority, identity, or isolation differs."""

    def __init__(self, code: str, detail: str) -> None:
        self.code = code
        super().__init__(f"{code}: {detail}")


def _fail(code: str, detail: str) -> NoReturn:
    raise PumpStationCoupledRolloutError(code, detail)


@dataclass(frozen=True, slots=True)
class PumpStationCoupledSnapshotRef:
    """Exact current coupled-world snapshot used as a rollout origin."""

    run_id: str
    episode_id: str
    world_branch_id: str
    sequence: int
    state_id: str
    commit_id: str


def coupled_run_snapshot(run: PumpStationCoupledRun) -> PumpStationCoupledSnapshotRef:
    """Return one stable snapshot reference for a coupled run."""
    return PumpStationCoupledSnapshotRef(
        run_id=run.manifest.run_id,
        episode_id=run.manifest.episode_id,
        world_branch_id=run.manifest.world_branch_id,
        sequence=run.state.sequence,
        state_id=run.state.state_id,
        commit_id=run.state.state_id,
    )


@dataclass(frozen=True, slots=True)
class PumpStationCoupledRolloutChildRequest:
    """One content-addressed rollout-v2 child request."""

    request_version: str
    child_id: str
    run_id: str
    world_branch_id: str
    agent_condition_id: str
    agent_seed: int

    @property
    def content_id(self) -> str:
        """Return the complete canonical child-request identity."""
        return stewardship_content_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledRolloutGroupRequest:
    """One content-addressed request for isolated ASW-8 children."""

    request_version: str
    request_id: str
    group_id: str
    task_world_id: str
    authority_id: str
    parent_snapshot: PumpStationCoupledSnapshotRef
    parent_manifest_content_id: str
    origin_verification_content_id: str
    reference_system_content_id: str
    event_schedule_sha256: str
    information_boundary_id: str
    temporal_bundle_content_id: str
    child_request_content_ids: tuple[str, ...]
    children: tuple[PumpStationCoupledRolloutChildRequest, ...]

    @property
    def content_id(self) -> str:
        """Return the complete canonical group-request identity."""
        return stewardship_content_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledChildTemporalState:
    """Inherited public temporal identity and fresh child-private retrieval state."""

    state_version: str
    child_world_branch_id: str
    public_bundle_content_id: str
    public_corpus_content_id: str
    public_capability_content_id: str
    ancestor_branch_ids: tuple[str, ...]
    private_namespace_id: str
    private_access_result_ids: tuple[str, ...]
    private_fetched_content_ids: tuple[str, ...]

    @property
    def content_id(self) -> str:
        """Return the child temporal-state identity."""
        return stewardship_content_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledRolloutChildReceipt:
    """Creation receipt that binds request, manifest, initial state, and temporal state."""

    receipt_version: str
    group_id: str
    child_id: str
    group_request_content_id: str
    child_request_content_id: str
    parent_snapshot: PumpStationCoupledSnapshotRef
    child_manifest_content_id: str
    initial_state_id: str
    temporal_state_content_id: str
    temporal_bundle_content_id: str
    parent_origin_remaining_schedule_sha256: str

    @property
    def content_id(self) -> str:
        """Return the exact child-receipt identity."""
        return stewardship_content_id(self, record_profile="v4")


@dataclass(frozen=True, slots=True)
class PumpStationCoupledRolloutLineage:
    """Complete ordered rollout-v2 lineage for one child group."""

    lineage_version: str
    request_id: str
    group_id: str
    group_request_content_id: str
    parent_snapshot: PumpStationCoupledSnapshotRef
    parent_manifest_content_id: str
    origin_verification_content_id: str
    ancestor_branch_ids: tuple[str, ...]
    children: tuple[PumpStationCoupledRolloutChildReceipt, ...]

    @property
    def content_id(self) -> str:
        """Return the full lineage identity."""
        return stewardship_content_id(self, record_profile="v4")


class PumpStationCoupledRolloutControl:
    """Host-only durable rollout-v2 control for the ASW-8 coupled world."""

    def __init__(
        self,
        *,
        parent_repository_root: Path,
        rollout_repository_root: Path,
        authorised_principal_ids: tuple[str, ...],
    ) -> None:
        if not authorised_principal_ids or len(set(authorised_principal_ids)) != len(authorised_principal_ids):
            raise ValueError("coupled rollout control requires distinct host principals")
        self._parent_root = Path(parent_repository_root)
        self._root = Path(rollout_repository_root)
        self._authorised = frozenset(authorised_principal_ids)

    def open_parent(self) -> PumpStationCoupledRun:
        """Open and independently verify the unchanged parent run."""
        parent = PumpStationCoupledRunRepository(self._parent_root).open()
        if not verify_coupled_run(parent).valid:
            _fail("rollout-origin-verification", parent.manifest.run_id)
        return parent

    def create_group(
        self,
        request: PumpStationCoupledRolloutGroupRequest,
    ) -> PumpStationCoupledRolloutLineage:
        """Create or exactly recover every requested isolated child."""
        parent = self._validate_request(request)
        group_root = self._group_root(request.group_id)
        request_path = group_root / "group-request.json"
        self._publish_once(
            request_path,
            request,
            conflict_code="rollout-request-content",
        )
        lineage_path = group_root / "lineage.json"
        if lineage_path.exists():
            lineage = self._load_lineage(lineage_path)
            if lineage.group_request_content_id != request.content_id:
                _fail("rollout-request-content", request.request_id)
            return lineage
        remaining_schedule_sha256 = self._remaining_schedule_sha256(parent)
        receipts = tuple(
            self._create_child(
                request=request,
                child_request=child,
                parent=parent,
                remaining_schedule_sha256=remaining_schedule_sha256,
            )
            for child in request.children
        )
        parent_ancestors = parent.manifest.initial_state_source.ancestor_branch_ids
        lineage = PumpStationCoupledRolloutLineage(
            lineage_version=PUMP_STATION_COUPLED_ROLLOUT_LINEAGE_VERSION,
            request_id=request.request_id,
            group_id=request.group_id,
            group_request_content_id=request.content_id,
            parent_snapshot=request.parent_snapshot,
            parent_manifest_content_id=parent.manifest.content_id,
            origin_verification_content_id=request.origin_verification_content_id,
            ancestor_branch_ids=(*parent_ancestors, parent.manifest.world_branch_id),
            children=receipts,
        )
        self._publish_once(
            lineage_path,
            lineage,
            conflict_code="rollout-lineage-content",
        )
        return lineage

    def open_child(self, group_id: str, child_id: str) -> PumpStationCoupledRun:
        """Open and replay one confined child without reading a sibling."""
        return PumpStationCoupledRunRepository(self._child_root(group_id, child_id) / "world-run").open()

    def inspect_group(self, group_id: str) -> PumpStationCoupledRolloutLineage:
        """Load one complete published v2 lineage without changing any child."""
        return self._load_lineage(self._group_root(group_id) / "lineage.json")

    def child_run_root(self, group_id: str, child_id: str) -> Path:
        """Return the confined durable world-run root for one selected child."""
        return self._child_root(group_id, child_id) / "world-run"

    def apply_child_actor(
        self,
        group_id: str,
        child_id: str,
        *,
        request_id: str,
        action_name: str,
        arguments: dict[str, Any],
    ) -> PumpStationCoupledRun:
        """Apply one actor action only to the selected child."""
        repository = PumpStationCoupledRunRepository(self._child_root(group_id, child_id) / "world-run")
        child = repository.open().apply_actor(
            request_id=request_id,
            action_name=action_name,
            arguments=arguments,
        )
        repository.append(child)
        return repository.open()

    def apply_child_treatment(
        self,
        group_id: str,
        child_id: str,
        request: PumpStationCoupledTreatmentRequest,
    ) -> PumpStationCoupledRun:
        """Apply one host-private treatment only to the selected child."""
        if request.authority_id not in self._authorised:
            _fail("coupled-treatment-authority", request.authority_id)
        repository = PumpStationCoupledRunRepository(self._child_root(group_id, child_id) / "world-run")
        child = repository.open().apply_treatment(request)
        repository.append(child)
        return repository.open()

    def load_child_temporal_state(
        self,
        group_id: str,
        child_id: str,
    ) -> PumpStationCoupledChildTemporalState:
        """Load the child's inherited public and fresh private temporal state."""
        value = self._read_json(self._child_root(group_id, child_id) / "temporal-state.json")
        return PumpStationCoupledChildTemporalState(
            **{
                key: item
                for key, item in value.items()
                if key
                not in {
                    "ancestor_branch_ids",
                    "private_access_result_ids",
                    "private_fetched_content_ids",
                }
            },
            ancestor_branch_ids=tuple(value["ancestor_branch_ids"]),
            private_access_result_ids=tuple(value["private_access_result_ids"]),
            private_fetched_content_ids=tuple(value["private_fetched_content_ids"]),
        )

    def _validate_request(
        self,
        request: PumpStationCoupledRolloutGroupRequest,
    ) -> PumpStationCoupledRun:
        if request.request_version != PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION:
            _fail("rollout-request-version", request.request_version)
        if request.authority_id not in self._authorised:
            _fail("rollout-authority", request.authority_id)
        if request.task_world_id != _TASK_WORLD_ID:
            _fail("rollout-task-world", request.task_world_id)
        if not request.children:
            _fail("rollout-children", request.group_id)
        child_ids = tuple(child.child_id for child in request.children)
        branch_ids = tuple(child.world_branch_id for child in request.children)
        run_ids = tuple(child.run_id for child in request.children)
        if any(child.request_version != PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION for child in request.children):
            _fail("rollout-child-request-version", request.request_id)
        expected_child_content_ids = tuple(child.content_id for child in request.children)
        if request.child_request_content_ids != expected_child_content_ids:
            _fail("rollout-child-request-content", request.request_id)
        if any(len(set(values)) != len(values) for values in (child_ids, branch_ids, run_ids)):
            _fail("rollout-child-identity", request.group_id)
        parent = self.open_parent()
        verification = verify_coupled_run(parent)
        if request.parent_snapshot != coupled_run_snapshot(parent):
            _fail("rollout-origin-snapshot", request.request_id)
        if request.parent_manifest_content_id != parent.manifest.content_id:
            _fail("rollout-origin-manifest", request.request_id)
        if request.origin_verification_content_id != verification.content_id:
            _fail("rollout-origin-verification", request.request_id)
        if request.reference_system_content_id != parent.manifest.reference_system_content_id:
            _fail("rollout-reference-system", request.request_id)
        if request.event_schedule_sha256 != parent.manifest.event_schedule_sha256:
            _fail("rollout-event-schedule", request.request_id)
        if request.information_boundary_id != "pump-station-actor-view.v4":
            _fail("rollout-information-boundary", request.request_id)
        if request.temporal_bundle_content_id != parent.manifest.temporal_bundle_content_id:
            _fail("rollout-temporal-content", request.request_id)
        return parent

    def _create_child(
        self,
        *,
        request: PumpStationCoupledRolloutGroupRequest,
        child_request: PumpStationCoupledRolloutChildRequest,
        parent: PumpStationCoupledRun,
        remaining_schedule_sha256: str,
    ) -> PumpStationCoupledRolloutChildReceipt:
        child_root = self._child_root(request.group_id, child_request.child_id)
        receipt_path = child_root / "child-receipt.json"
        if receipt_path.exists():
            return self._load_receipt(receipt_path)
        ancestor_branch_ids = (
            *parent.manifest.initial_state_source.ancestor_branch_ids,
            parent.manifest.world_branch_id,
        )
        source = PumpStationInitialStateSource(
            kind="rollout_parent_snapshot",
            opening_specification_id=parent.manifest.opening_state_specification_id,
            opening_specification_sha256=parent.manifest.opening_state_specification_sha256,
            parent_run_id=parent.manifest.run_id,
            parent_branch_id=parent.manifest.world_branch_id,
            parent_state_id=parent.state.state_id,
            parent_commit_id=parent.state.state_id,
            rollout_group_request_id=request.request_id,
            child_request_content_id=child_request.content_id,
            rollout_group_request_content_id=request.content_id,
            parent_manifest_content_id=parent.manifest.content_id,
            origin_verification_content_id=request.origin_verification_content_id,
            parent_origin_remaining_schedule_sha256=remaining_schedule_sha256,
            ancestor_branch_ids=ancestor_branch_ids,
        )
        manifest = replace(
            parent.manifest,
            run_id=child_request.run_id,
            episode_id=f"episode-{child_request.run_id}",
            world_branch_id=child_request.world_branch_id,
            initial_state_id=parent.state.state_id,
            initial_state_source=source,
        )
        child = PumpStationCoupledRun(
            manifest=manifest,
            state=parent.state,
            commands=(),
            receipts=(),
            origin_manifest=parent.manifest,
            origin_commands=parent.commands,
            origin_proposals=parent.proposals,
        )
        child_world_root = child_root / "world-run"
        if child_world_root.exists():
            child_repository = PumpStationCoupledRunRepository(child_world_root)
            if child_repository.open() != child:
                _fail("rollout-child-world-content", child_request.child_id)
        else:
            child_repository = PumpStationCoupledRunRepository(child_world_root)
            child_repository.create(child)
        copy_coupled_child_temporal_repository(
            parent_run_root=self._parent_root,
            child_run_root=child_world_root,
            parent=parent,
            child=child,
        )
        temporal = PumpStationCoupledChildTemporalState(
            state_version=PUMP_STATION_COUPLED_TEMPORAL_STATE_VERSION,
            child_world_branch_id=child_request.world_branch_id,
            public_bundle_content_id=parent.manifest.temporal_bundle_content_id,
            public_corpus_content_id=parent.manifest.temporal_corpus_content_id,
            public_capability_content_id=parent.manifest.temporal_capability_content_id,
            ancestor_branch_ids=ancestor_branch_ids,
            private_namespace_id=f"references-{child_request.world_branch_id}",
            private_access_result_ids=(),
            private_fetched_content_ids=(),
        )
        self._publish_once(
            child_root / "temporal-state.json",
            temporal,
            conflict_code="rollout-temporal-content",
        )
        receipt = PumpStationCoupledRolloutChildReceipt(
            receipt_version=PUMP_STATION_COUPLED_ROLLOUT_RECEIPT_VERSION,
            group_id=request.group_id,
            child_id=child_request.child_id,
            group_request_content_id=request.content_id,
            child_request_content_id=child_request.content_id,
            parent_snapshot=request.parent_snapshot,
            child_manifest_content_id=manifest.content_id,
            initial_state_id=parent.state.state_id,
            temporal_state_content_id=temporal.content_id,
            temporal_bundle_content_id=parent.manifest.temporal_bundle_content_id,
            parent_origin_remaining_schedule_sha256=remaining_schedule_sha256,
        )
        self._publish_once(
            receipt_path,
            receipt,
            conflict_code="rollout-child-receipt-content",
        )
        return receipt

    @staticmethod
    def _remaining_schedule_sha256(parent: PumpStationCoupledRun) -> str:
        remaining = tuple(
            requirement
            for requirement in parent.state.service_schedule
            if requirement.end_calendar_seconds > parent.state.calendar_seconds
        )
        return stewardship_content_id(
            (
                parent.state.calendar_seconds,
                remaining,
                tuple((pool.pool_id, getattr(pool, "availability", ())) for pool in parent.state.resources.pools),
            ),
            record_profile="v4",
        )

    def _group_root(self, group_id: str) -> Path:
        return self._confined("groups", group_id)

    def _child_root(self, group_id: str, child_id: str) -> Path:
        return self._confined("groups", group_id, "children", child_id)

    def _confined(self, *parts: str) -> Path:
        for value in parts:
            if not _SAFE_ID.fullmatch(value) or value in {".", ".."}:
                _fail("rollout-confinement", value)
        root = self._root.resolve()
        path = root.joinpath(*parts)
        path.mkdir(parents=True, exist_ok=True)
        resolved = path.resolve()
        if resolved != root and root not in resolved.parents:
            _fail("rollout-confinement", str(path))
        return resolved

    @staticmethod
    def _payload(value: object) -> bytes:
        return (
            json.dumps(
                canonical_stewardship_value(value, record_profile="v4"),
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            )
            + "\n"
        ).encode()

    def _publish_once(
        self,
        path: Path,
        value: object,
        *,
        conflict_code: str,
    ) -> None:
        payload = self._payload(value)
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            if path.read_bytes() != payload:
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
            os.replace(temporary, path)
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            value = json.loads(path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            _fail("rollout-artifact", f"{path}: {error}")
        if not isinstance(value, dict):
            _fail("rollout-artifact", str(path))
        return cast(dict[str, Any], value)

    def _load_receipt(self, path: Path) -> PumpStationCoupledRolloutChildReceipt:
        value = self._read_json(path)
        snapshot = PumpStationCoupledSnapshotRef(**value.pop("parent_snapshot"))
        return PumpStationCoupledRolloutChildReceipt(
            **value,
            parent_snapshot=snapshot,
        )

    def _load_lineage(self, path: Path) -> PumpStationCoupledRolloutLineage:
        value = self._read_json(path)
        snapshot = PumpStationCoupledSnapshotRef(**value.pop("parent_snapshot"))
        ancestor_branch_ids = tuple(value.pop("ancestor_branch_ids", ()))
        children = tuple(
            PumpStationCoupledRolloutChildReceipt(
                **{key: item for key, item in child.items() if key != "parent_snapshot"},
                parent_snapshot=PumpStationCoupledSnapshotRef(**child["parent_snapshot"]),
            )
            for child in value.pop("children")
        )
        return PumpStationCoupledRolloutLineage(
            **value,
            parent_snapshot=snapshot,
            ancestor_branch_ids=ancestor_branch_ids,
            children=children,
        )


__all__ = (
    "PUMP_STATION_COUPLED_ROLLOUT_CONTROL_VERSION",
    "PUMP_STATION_COUPLED_ROLLOUT_LINEAGE_VERSION",
    "PUMP_STATION_COUPLED_ROLLOUT_RECEIPT_VERSION",
    "PUMP_STATION_COUPLED_ROLLOUT_REQUEST_VERSION",
    "PUMP_STATION_COUPLED_TEMPORAL_STATE_VERSION",
    "PumpStationCoupledChildTemporalState",
    "PumpStationCoupledRolloutChildReceipt",
    "PumpStationCoupledRolloutChildRequest",
    "PumpStationCoupledRolloutControl",
    "PumpStationCoupledRolloutError",
    "PumpStationCoupledRolloutGroupRequest",
    "PumpStationCoupledRolloutLineage",
    "PumpStationCoupledSnapshotRef",
    "coupled_run_snapshot",
)
