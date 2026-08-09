# ABOUTME: Locks the phase-neutral monitor evidence repository's durable contracts and path identity.
# ABOUTME: Proves canonical claims, host-private storage, deterministic enumeration, and collision rejection.

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path

import pytest

from aec_bench.experimentation.governance.monitor_repository import (
    MonitorRuntimeCollisionError,
    ProductionMonitorCheckpointKind,
    _bind_monitor_claim,
    _canary_activation_claim_path,
    _canary_activation_object_path,
    _CanaryReferenceClaim,
    _CanarySurfaceActivationClaim,
    _checkpoint_claim_path,
    _checkpoint_object_path,
    _CheckpointClaim,
    _closure_claim_path,
    _closure_object_path,
    _cycle_root,
    _effect_permit_claim_path,
    _effect_permit_object_path,
    _EffectPermitClaim,
    _flow_activation_claim_path,
    _flow_activation_object_path,
    _flow_claim_path,
    _flow_object_path,
    _FlowCollectorActivationClaim,
    _load_monitor_model,
    _manifest_claim_path,
    _manifest_object_path,
    _monitor_claim_files,
    _prepare_new_repository,
    _reference_claim_path,
    _reference_object_path,
    _RuntimeClosureClaim,
    _RuntimeFlowClaim,
    _RuntimeManifestClaim,
)
from aec_bench.experimentation.governance.standing_monitors import default_forbidden_flow_rules


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


@dataclass(frozen=True)
class _CycleIdentity:
    cycle_id: str


@dataclass(frozen=True)
class _ManifestIdentity:
    cycle_plan: _CycleIdentity


def test_repository_persists_canonical_claims_with_host_private_permissions(
    tmp_path: Path,
) -> None:
    repository, normalized_candidates = _prepare_new_repository(
        root=tmp_path / "monitor",
        authority_root=tmp_path / "authority",
        candidate_roots=(tmp_path / "candidate",),
    )
    claim = _RuntimeManifestClaim(
        cycle_id="cycle.009",
        runtime_manifest_sha256=_sha("manifest"),
    )
    claim_path = _manifest_claim_path(repository.root, claim.cycle_id)

    _bind_monitor_claim(
        repository,
        claim_path,
        claim,
        _RuntimeManifestClaim,
        label="monitor runtime cycle",
    )

    assert normalized_candidates == ((tmp_path / "candidate").resolve(strict=False),)
    assert (
        _load_monitor_model(
            repository,
            claim_path,
            _RuntimeManifestClaim,
            label="monitor runtime cycle claim",
        )
        == claim
    )
    assert claim_path.read_bytes() == (
        json.dumps(
            claim.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    assert stat.S_IMODE(repository.root.stat().st_mode) == 0o700
    assert stat.S_IMODE(claim_path.stat().st_mode) == 0o600


def test_repository_claim_schema_versions_remain_exact() -> None:
    assert {
        model.model_fields["schema_version"].default
        for model in (
            _RuntimeManifestClaim,
            _RuntimeFlowClaim,
            _CanaryReferenceClaim,
            _CanarySurfaceActivationClaim,
            _FlowCollectorActivationClaim,
            _CheckpointClaim,
            _EffectPermitClaim,
            _RuntimeClosureClaim,
        )
    } == {
        "aecbench.monitor-runtime-manifest-claim.v1",
        "aecbench.monitor-runtime-flow-claim.v1",
        "aecbench.monitor-canary-reference-claim.v1",
        "aecbench.canary-surface-activation-claim.v1",
        "aecbench.flow-collector-activation-claim.v1",
        "aecbench.monitor-runtime-checkpoint-claim.v1",
        "aecbench.monitor-effect-permit-claim.v1",
        "aecbench.monitor-runtime-closure-claim.v1",
    }


def test_repository_claim_binding_is_idempotent_and_rejects_rebinding(
    tmp_path: Path,
) -> None:
    repository, _ = _prepare_new_repository(
        root=tmp_path / "monitor",
        authority_root=tmp_path / "authority",
        candidate_roots=(tmp_path / "candidate",),
    )
    first = _RuntimeManifestClaim(
        cycle_id="cycle.009",
        runtime_manifest_sha256=_sha("manifest-one"),
    )
    second = _RuntimeManifestClaim(
        cycle_id=first.cycle_id,
        runtime_manifest_sha256=_sha("manifest-two"),
    )
    claim_path = _manifest_claim_path(repository.root, first.cycle_id)

    for claim in (first, first):
        _bind_monitor_claim(
            repository,
            claim_path,
            claim,
            _RuntimeManifestClaim,
            label="monitor runtime cycle",
        )

    with pytest.raises(
        MonitorRuntimeCollisionError,
        match="monitor runtime cycle is already bound to different content",
    ):
        _bind_monitor_claim(
            repository,
            claim_path,
            second,
            _RuntimeManifestClaim,
            label="monitor runtime cycle",
        )


def test_repository_paths_and_claim_enumeration_preserve_runtime_identity(
    tmp_path: Path,
) -> None:
    root = tmp_path / "monitor"
    manifest = _ManifestIdentity(cycle_plan=_CycleIdentity(cycle_id="cycle.009"))
    cycle_key = _sha("cycle.009")
    flow_key = _sha("flow.002")
    reference_key = _sha("reference.002")
    digest = _sha("content")
    canary_digest = _sha("canary")
    rule = default_forbidden_flow_rules()[0]
    rule_key = _sha(
        json.dumps(
            (
                rule.source_principal_kind.value,
                rule.target_surface.value,
                rule.action.value,
            )
        )
    )
    cycle_root = root / "cycles" / cycle_key

    assert _manifest_object_path(root, digest) == root / "objects" / "manifests" / digest / "manifest.json"
    assert _manifest_claim_path(root, "cycle.009") == root / "claims" / "cycles" / cycle_key / "claim.json"
    assert _cycle_root(root, manifest) == cycle_root
    assert _flow_object_path(root, manifest, digest) == (cycle_root / "flows" / "objects" / digest / "observation.json")
    assert _flow_claim_path(root, manifest, "flow.002") == (cycle_root / "flows" / "claims" / flow_key / "claim.json")
    assert _reference_object_path(root, manifest, digest) == (
        cycle_root / "references" / "objects" / digest / "event.json"
    )
    assert _reference_claim_path(root, manifest, "reference.002") == (
        cycle_root / "references" / "claims" / reference_key / "claim.json"
    )
    assert _canary_activation_object_path(root, manifest, digest) == (
        cycle_root / "instrumentation" / "canary-surfaces" / "objects" / digest / "activation.json"
    )
    assert _canary_activation_claim_path(root, manifest, canary_digest) == (
        cycle_root / "instrumentation" / "canary-surfaces" / "claims" / canary_digest / "claim.json"
    )
    assert _flow_activation_object_path(root, manifest, digest) == (
        cycle_root / "instrumentation" / "flow-collectors" / "objects" / digest / "activation.json"
    )
    assert _flow_activation_claim_path(root, manifest, rule) == (
        cycle_root / "instrumentation" / "flow-collectors" / "claims" / rule_key / "claim.json"
    )
    assert _checkpoint_object_path(root, manifest, digest) == (
        cycle_root / "checkpoints" / "objects" / digest / "checkpoint.json"
    )
    assert (
        _checkpoint_claim_path(
            root,
            manifest,
            ProductionMonitorCheckpointKind.PRE_EFFECT,
        )
        == cycle_root / "checkpoints" / "claims" / "pre_effect" / "claim.json"
    )
    assert _effect_permit_object_path(root, manifest, digest) == (
        cycle_root / "effect-permit" / "objects" / digest / "permit.json"
    )
    assert _effect_permit_claim_path(root, manifest) == cycle_root / "effect-permit" / "claim" / "claim.json"
    assert _closure_object_path(root, manifest, digest) == (
        cycle_root / "closure" / "objects" / digest / "closure.json"
    )
    assert _closure_claim_path(root, manifest) == cycle_root / "closure" / "claim" / "claim.json"

    repository, _ = _prepare_new_repository(
        root=root,
        authority_root=tmp_path / "authority",
        candidate_roots=(tmp_path / "candidate",),
    )
    claims_root = cycle_root / "checkpoints" / "claims"
    for checkpoint in (
        ProductionMonitorCheckpointKind.TERMINAL,
        ProductionMonitorCheckpointKind.PRE_EFFECT,
    ):
        claim = _CheckpointClaim(
            runtime_manifest_sha256=_sha("manifest"),
            checkpoint=checkpoint,
            checkpoint_sha256=_sha(checkpoint.value),
        )
        _bind_monitor_claim(
            repository,
            _checkpoint_claim_path(root, manifest, checkpoint),
            claim,
            _CheckpointClaim,
            label=f"{checkpoint.value} checkpoint",
        )

    assert _monitor_claim_files(repository, claims_root) == (
        claims_root / "pre_effect" / "claim.json",
        claims_root / "terminal" / "claim.json",
    )
