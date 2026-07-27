# ABOUTME: Opens and reloads one exact production-monitor cycle over immutable repository evidence.
# ABOUTME: Materializes committed canaries while delegating lifecycle responsibilities to focused runtime layers.

from __future__ import annotations

import os
import time
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Self

from pydantic import JsonValue

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_kernel import validate_sha256
from aec_bench.meta_harness.authority_ledger import AuthorityLedger
from aec_bench.meta_harness.immutable_artifact_store import EvidenceRepository
from aec_bench.meta_harness.monitor_repository import (
    MonitorRuntimeCollisionError,
    MonitorRuntimeIntegrityError,
    _bind_monitor_claim,
    _load_monitor_model,
    _manifest_claim_path,
    _manifest_object_path,
    _open_existing_repository,
    _prepare_new_repository,
    _RuntimeManifestClaim,
    _store_monitor_model,
)
from aec_bench.meta_harness.monitor_runtime.contracts import (
    MonitorCanaryPlacement,
    MonitorCanarySurface,
    ProductionMonitorRuntimeManifest,
)
from aec_bench.meta_harness.monitor_runtime.lifecycle import (
    MonitorLifecycleRuntime,
)
from aec_bench.meta_harness.monitor_runtime.surface_io import (
    canonical_json_bytes,
    publish_surface_exact,
    validate_canary_payload,
    validate_canary_surface,
)
from aec_bench.meta_harness.monitors import (
    CanaryCommitment,
    CycleMonitorPlan,
    StandingMonitorPolicy,
)

_HOST_MONITOR_PRINCIPAL = AuthorityPrincipal(
    principal_id="host.production-monitor-runtime",
    kind=AuthorityPrincipalKind.HOST_RUNTIME,
)


class ProductionMonitorRuntime(MonitorLifecycleRuntime):
    """Durable owner of all observations and checkpoints for one production cycle."""

    def reload(self) -> Self:
        """Reopen this exact runtime without allowing caller-supplied identity drift."""

        return type(self).load(
            root=self._root,
            execution_scope_sha256=self._manifest.execution_scope_sha256,
            policy=self._manifest.policy,
            cycle_plan=self._manifest.cycle_plan,
            ledger=self._ledger,
            candidate_roots=self._candidate_roots,
            clock=self._clock,
        )

    @classmethod
    def open(
        cls,
        *,
        root: Path,
        execution_scope_sha256: str,
        policy: StandingMonitorPolicy,
        cycle_plan: CycleMonitorPlan,
        canary_payloads: Mapping[str, JsonValue],
        canary_surfaces: Mapping[str, MonitorCanarySurface],
        ledger: AuthorityLedger,
        candidate_roots: tuple[Path, ...] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> Self:
        """Open one immutable cycle and physically place every committed canary."""

        selected_policy = StandingMonitorPolicy.model_validate(policy.model_dump(mode="python"))
        selected_cycle = CycleMonitorPlan.model_validate(cycle_plan.model_dump(mode="python"))
        validate_sha256(execution_scope_sha256)
        repository, normalized_candidates = _prepare_new_repository(
            root=Path(root),
            authority_root=ledger.root,
            candidate_roots=candidate_roots,
        )
        if selected_cycle.standing_policy_sha256 != selected_policy.content_sha256:
            raise MonitorRuntimeIntegrityError("cycle monitor plan does not bind the supplied standing policy")
        payload_by_id = dict(canary_payloads)
        surface_by_id = {
            canary_id: MonitorCanarySurface.model_validate(surface.model_dump(mode="python"))
            for canary_id, surface in canary_surfaces.items()
        }
        _validate_canary_inputs(
            policy=selected_policy,
            payload_by_id=payload_by_id,
            surface_by_id=surface_by_id,
        )
        placements = _build_canary_placements(
            policy=selected_policy,
            surfaces=surface_by_id,
            monitor_root=repository.root,
            authority_root=ledger.root,
            candidate_roots=normalized_candidates,
        )
        manifest = ProductionMonitorRuntimeManifest(
            execution_scope_sha256=execution_scope_sha256,
            policy=selected_policy,
            cycle_plan=selected_cycle,
            observed_by=_HOST_MONITOR_PRINCIPAL,
            canary_placements=placements,
        )
        _assert_cycle_binding_available(
            repository=repository,
            manifest=manifest,
        )
        _publish_canary_payloads(
            manifest=manifest,
            payload_by_id=payload_by_id,
        )
        _persist_manifest(repository=repository, manifest=manifest)
        return cls._load_exact(
            repository=repository,
            policy=selected_policy,
            cycle_plan=selected_cycle,
            execution_scope_sha256=execution_scope_sha256,
            ledger=ledger,
            candidate_roots=normalized_candidates,
            clock=clock,
        )

    @classmethod
    def load(
        cls,
        *,
        root: Path,
        execution_scope_sha256: str,
        policy: StandingMonitorPolicy,
        cycle_plan: CycleMonitorPlan,
        ledger: AuthorityLedger,
        candidate_roots: tuple[Path, ...] = (),
        clock: Callable[[], float] = time.monotonic,
    ) -> Self:
        """Reload one exact cycle while verifying its immutable host-owned state."""

        repository, normalized_candidates = _open_existing_repository(
            root=Path(root),
            authority_root=ledger.root,
            candidate_roots=candidate_roots,
        )
        return cls._load_exact(
            repository=repository,
            policy=StandingMonitorPolicy.model_validate(policy.model_dump(mode="python")),
            cycle_plan=CycleMonitorPlan.model_validate(cycle_plan.model_dump(mode="python")),
            execution_scope_sha256=execution_scope_sha256,
            ledger=ledger,
            candidate_roots=normalized_candidates,
            clock=clock,
        )

    @classmethod
    def _load_exact(
        cls,
        *,
        repository: EvidenceRepository,
        policy: StandingMonitorPolicy,
        cycle_plan: CycleMonitorPlan,
        execution_scope_sha256: str,
        ledger: AuthorityLedger,
        candidate_roots: tuple[Path, ...],
        clock: Callable[[], float],
    ) -> Self:
        validate_sha256(execution_scope_sha256)
        claim = _load_monitor_model(
            repository,
            _manifest_claim_path(repository.root, cycle_plan.cycle_id),
            _RuntimeManifestClaim,
            label="monitor runtime cycle claim",
        )
        if claim.cycle_id != cycle_plan.cycle_id:
            raise MonitorRuntimeIntegrityError("monitor runtime cycle claim does not match its lookup identity")
        manifest_path = _manifest_object_path(
            repository.root,
            claim.runtime_manifest_sha256,
        )
        manifest = _load_monitor_model(
            repository,
            manifest_path,
            ProductionMonitorRuntimeManifest,
            label="monitor runtime manifest",
        )
        if manifest.content_sha256 != claim.runtime_manifest_sha256:
            raise MonitorRuntimeIntegrityError("monitor runtime manifest hash does not match its cycle claim")
        if (
            manifest.policy != policy
            or manifest.cycle_plan != cycle_plan
            or manifest.execution_scope_sha256 != execution_scope_sha256
        ):
            raise MonitorRuntimeIntegrityError("persisted monitor runtime differs from the supplied policy or cycle")
        runtime = cls(
            repository=repository,
            ledger=ledger,
            candidate_roots=candidate_roots,
            manifest=manifest,
            manifest_path=manifest_path,
            clock=clock,
        )
        runtime._verify_placement_paths()
        return runtime


def _validate_canary_inputs(
    *,
    policy: StandingMonitorPolicy,
    payload_by_id: Mapping[str, JsonValue],
    surface_by_id: Mapping[str, MonitorCanarySurface],
) -> None:
    expected_ids = {canary.canary_id for canary in policy.canaries}
    if set(payload_by_id) != expected_ids or set(surface_by_id) != expected_ids:
        raise MonitorRuntimeIntegrityError("runtime canary payloads and surfaces must cover every exact policy canary")


def _build_canary_placements(
    *,
    policy: StandingMonitorPolicy,
    surfaces: Mapping[str, MonitorCanarySurface],
    monitor_root: Path,
    authority_root: Path,
    candidate_roots: tuple[Path, ...],
) -> tuple[MonitorCanaryPlacement, ...]:
    placements: list[MonitorCanaryPlacement] = []
    for canary in policy.canaries:
        surface = surfaces[canary.canary_id]
        validate_canary_surface(
            surface=surface,
            kind=canary.kind,
            monitor_root=monitor_root,
            authority_root=authority_root,
            candidate_roots=candidate_roots,
        )
        relative = (
            PurePosixPath(".aecbench-monitor-canaries") / canary.kind.value / canary.content_sha256 / "canary.json"
        )
        placements.append(
            MonitorCanaryPlacement(
                canary_id=canary.canary_id,
                commitment_sha256=canary.content_sha256,
                kind=canary.kind,
                surface=surface,
                host_path=str((Path(surface.host_root) / relative.as_posix()).resolve(strict=False)),
                logical_projection_key=":".join(
                    (
                        surface.logical_projection_namespace,
                        canary.kind.value,
                        canary.content_sha256,
                    )
                ),
            )
        )
    return tuple(placements)


def _assert_cycle_binding_available(
    *,
    repository: EvidenceRepository,
    manifest: ProductionMonitorRuntimeManifest,
) -> None:
    claim_path = _manifest_claim_path(
        repository.root,
        manifest.cycle_plan.cycle_id,
    )
    if not os.path.lexists(claim_path):
        return
    existing_claim = _load_monitor_model(
        repository,
        claim_path,
        _RuntimeManifestClaim,
        label="monitor runtime cycle claim",
    )
    if (
        existing_claim.cycle_id != manifest.cycle_plan.cycle_id
        or existing_claim.runtime_manifest_sha256 != manifest.content_sha256
    ):
        raise MonitorRuntimeCollisionError("monitor runtime cycle is already bound to a different manifest")


def _publish_canary_payloads(
    *,
    manifest: ProductionMonitorRuntimeManifest,
    payload_by_id: Mapping[str, JsonValue],
) -> None:
    commitments_by_id: dict[str, CanaryCommitment] = {canary.canary_id: canary for canary in manifest.policy.canaries}
    for placement in manifest.canary_placements:
        payload = payload_by_id[placement.canary_id]
        validate_canary_payload(
            commitment=commitments_by_id[placement.canary_id],
            payload=payload,
        )
        publish_surface_exact(
            surface_root=Path(placement.surface.host_root),
            path=Path(placement.host_path),
            content=canonical_json_bytes(payload),
        )


def _persist_manifest(
    *,
    repository: EvidenceRepository,
    manifest: ProductionMonitorRuntimeManifest,
) -> None:
    _store_monitor_model(
        repository,
        _manifest_object_path(
            repository.root,
            manifest.content_sha256,
        ),
        manifest,
        ProductionMonitorRuntimeManifest,
        label="monitor runtime manifest",
    )
    claim = _RuntimeManifestClaim(
        cycle_id=manifest.cycle_plan.cycle_id,
        runtime_manifest_sha256=manifest.content_sha256,
    )
    _bind_monitor_claim(
        repository,
        _manifest_claim_path(
            repository.root,
            manifest.cycle_plan.cycle_id,
        ),
        claim,
        _RuntimeManifestClaim,
        label="monitor runtime cycle",
    )
