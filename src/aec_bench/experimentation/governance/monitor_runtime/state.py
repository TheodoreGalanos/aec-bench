# ABOUTME: Holds one monitor cycle's immutable identity and shared confinement checks.
# ABOUTME: Provides the minimal state boundary used by instrumentation, evidence, and lifecycle services.

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

from aec_bench.experimentation.governance.authority_ledger import AuthorityLedger
from aec_bench.experimentation.governance.monitor_repository import (
    MonitorRuntimeConfinementError,
    MonitorRuntimeIntegrityError,
    ProductionMonitorCheckpointKind,
    _checkpoint_claim_path,
    _translate_repository_errors,
)
from aec_bench.experimentation.governance.monitor_runtime.contracts import (
    MonitorCanaryPlacement,
    ProductionMonitorRuntimeManifest,
)
from aec_bench.experimentation.governance.monitor_runtime.surface_io import (
    guard_surface_path,
    validate_canary_surface,
)
from aec_bench.experimentation.governance.standing_monitors import CanaryCommitment
from aec_bench.ledger.immutable_artifact_store import EvidenceRepository


class MonitorRuntimeState:
    """Shared trusted state for one exact production-monitor runtime."""

    def __init__(
        self,
        *,
        repository: EvidenceRepository,
        ledger: AuthorityLedger,
        candidate_roots: tuple[Path, ...],
        manifest: ProductionMonitorRuntimeManifest,
        manifest_path: Path,
        clock: Callable[[], float],
    ) -> None:
        self._repository = repository
        self._root = repository.root
        self._ledger = ledger
        self._candidate_roots = candidate_roots
        self._manifest = manifest
        self._manifest_path = manifest_path
        self._clock = clock

    @property
    def root(self) -> Path:
        """Return the canonical host-owned runtime root."""

        return self._root

    @property
    def manifest(self) -> ProductionMonitorRuntimeManifest:
        """Return the exact frozen runtime manifest."""

        return self._manifest

    @property
    def manifest_path(self) -> Path:
        """Return the immutable manifest object path."""

        return self._manifest_path

    def canary_path(self, canary_id: str) -> Path:
        """Return the primary physical path for one exact policy canary."""

        placement = self._canary_placement(canary_id)
        path = Path(placement.host_path)
        guard_surface_path(Path(placement.surface.host_root), path)
        return path

    def _canary_commitment(self, canary_id: str) -> CanaryCommitment:
        matches = tuple(canary for canary in self._manifest.policy.canaries if canary.canary_id == canary_id)
        if len(matches) != 1:
            raise MonitorRuntimeIntegrityError("canary id does not identify one policy commitment")
        return matches[0]

    def _canary_placement(self, canary_id: str) -> MonitorCanaryPlacement:
        matches = tuple(placement for placement in self._manifest.canary_placements if placement.canary_id == canary_id)
        if len(matches) != 1:
            raise MonitorRuntimeIntegrityError("canary id does not identify one physical placement")
        return matches[0]

    def _host_evidence_path(self, path: Path, *, label: str) -> Path:
        supplied = Path(path)
        if not supplied.is_absolute():
            raise MonitorRuntimeConfinementError(f"{label} path must be absolute")
        resolved = supplied.resolve(strict=False)
        protected_roots = (
            self._root,
            self._ledger.root,
            *self._candidate_roots,
        )
        if any(resolved == protected or resolved.is_relative_to(protected) for protected in protected_roots):
            raise MonitorRuntimeConfinementError(f"{label} must remain outside monitor, authority, and candidate roots")
        return resolved

    def _verify_placement_paths(self) -> None:
        for placement in self._manifest.canary_placements:
            validate_canary_surface(
                surface=placement.surface,
                kind=placement.kind,
                monitor_root=self._root,
                authority_root=self._ledger.root,
                candidate_roots=self._candidate_roots,
            )
            surface_root = Path(placement.surface.host_root)
            path = Path(placement.host_path)
            guard_surface_path(surface_root, path)
            parent = path.parent
            guard_surface_path(surface_root, parent)
            if parent.exists() and (parent.is_symlink() or not parent.is_dir()):
                raise MonitorRuntimeConfinementError("canary placement root must be a regular non-symlink directory")
            if os.path.lexists(path) and path.is_symlink():
                raise MonitorRuntimeConfinementError("physical canary payload must not be a symlink")

    def _assert_terminal_absent(self) -> None:
        if self._claim_exists(
            _checkpoint_claim_path(
                self._root,
                self._manifest,
                ProductionMonitorCheckpointKind.TERMINAL,
            )
        ):
            raise MonitorRuntimeIntegrityError("runtime observations cannot change after the terminal checkpoint")

    def _assert_instrumentation_open(self) -> None:
        self._assert_terminal_absent()
        if self._claim_exists(
            _checkpoint_claim_path(
                self._root,
                self._manifest,
                ProductionMonitorCheckpointKind.PRE_EFFECT,
            )
        ):
            raise MonitorRuntimeIntegrityError("monitor instrumentation cannot change after the pre-effect checkpoint")

    def _claim_exists(self, path: Path) -> bool:
        with _translate_repository_errors(label="monitor runtime claim"):
            return self._repository.exists(
                self._repository.relative_path(path),
            )
