# ABOUTME: Activates production monitor canaries and forbidden-flow collectors from real boundary probes.
# ABOUTME: Keeps instrumentation external to task sandboxes, authority issuance, and the probe-agnostic runtime.

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Literal, Self

from pydantic import JsonValue, field_validator, model_validator

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    canonical_json_sha256,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.experimentation.governance.authority_ledger import (
    AuthorityLedger,
    AuthorityLedgerIntegrityError,
)
from aec_bench.experimentation.governance.monitor_runtime import (
    CanaryLogicalProjectionConfiguration,
    CanarySurfaceActivation,
    CanarySurfaceProbeReceipt,
    FlowCollectorActivation,
    FlowCollectorKind,
    FlowCollectorProbeOutcome,
    FlowCollectorProbeReceipt,
    ProductionMonitorRuntime,
)
from aec_bench.experimentation.governance.motif_assurance import (
    AssuredMotifSelectionRecord,
    MotifAssuranceSnapshot,
    motif_subject_sha256,
)
from aec_bench.experimentation.governance.motifs import (
    MotifLibrary,
    MotifSelectionOutcome,
    MotifSelectionRequest,
    resolve_motif_selection,
    select_motif,
)
from aec_bench.experimentation.governance.standing_monitors import (
    CanaryCommitment,
    CanaryKind,
    ForbiddenFlowRule,
)
from aec_bench.experimentation.governance.surface_guard import (
    PrincipalAwareSurfaceGuard,
    SurfaceAccessAuditReceipt,
    SurfaceAccessDecision,
    SurfaceAccessDenied,
)


class MonitorInstrumentationError(ValueError):
    """Raised when a real monitor probe cannot close exactly."""


class MotifCanaryProbeContext(LegacyContentAddressedModel):
    """Real frozen selector and assurance inputs for one planted motif canary."""

    schema_version: Literal["aecbench.motif-canary-probe-context.v1"] = "aecbench.motif-canary-probe-context.v1"
    library: MotifLibrary
    selection_request: MotifSelectionRequest
    assurance_snapshot: MotifAssuranceSnapshot

    @model_validator(mode="after")
    def validate_context(self) -> Self:
        if (
            self.selection_request.archive_sha256 != self.library.archive_sha256
            or not self.selection_request.archive_frozen
        ):
            raise ValueError("motif canary probe requires its exact frozen motif library")
        return self


class MotifCanaryProbeEvidence(LegacyContentAddressedModel):
    """Selector and assurance result for one historically attractive revoked motif."""

    schema_version: Literal["aecbench.motif-canary-probe-evidence.v1"] = "aecbench.motif-canary-probe-evidence.v1"
    runtime_manifest_sha256: str
    canary_commitment_sha256: str
    motif_sha256: str
    motif_subject_sha256: str
    library_archive_sha256: str
    selection_request_sha256: str
    selection_decision_sha256: str
    assurance_snapshot_sha256: str
    observed_effective_state: str
    legacy_selector_selected: Literal[True] = True
    assurance_boundary_rejected: Literal[True] = True

    @field_validator(
        "runtime_manifest_sha256",
        "canary_commitment_sha256",
        "motif_sha256",
        "motif_subject_sha256",
        "library_archive_sha256",
        "selection_request_sha256",
        "selection_decision_sha256",
        "assurance_snapshot_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class OrdinaryLedgerCanaryProbeEvidence(LegacyContentAddressedModel):
    """Real authority resolver rejection for one ordinary-ledger canary."""

    schema_version: Literal["aecbench.ordinary-ledger-canary-probe-evidence.v1"] = (
        "aecbench.ordinary-ledger-canary-probe-evidence.v1"
    )
    runtime_manifest_sha256: str
    canary_commitment_sha256: str
    ordinary_artifact_sha256: str
    resolver: Literal["authority_event_by_content"] = "authority_event_by_content"
    authority_boundary_rejected: Literal[True] = True

    @field_validator(
        "runtime_manifest_sha256",
        "canary_commitment_sha256",
        "ordinary_artifact_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class SurfaceGuardProbeEvidence(LegacyContentAddressedModel):
    """Exact attempted operation submitted to the principal-aware surface guard."""

    schema_version: Literal["aecbench.surface-guard-probe-evidence.v1"] = "aecbench.surface-guard-probe-evidence.v1"
    runtime_manifest_sha256: str
    guard_configuration_sha256: str
    rule: ForbiddenFlowRule

    @field_validator(
        "runtime_manifest_sha256",
        "guard_configuration_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class FlowCollectorConfigurationEvidence(LegacyContentAddressedModel):
    """Exact guard, policy rule, and denied receipt wired into one collector."""

    schema_version: Literal["aecbench.flow-collector-configuration-evidence.v1"] = (
        "aecbench.flow-collector-configuration-evidence.v1"
    )
    runtime_manifest_sha256: str
    guard_configuration_sha256: str
    guard_receipt_sha256: str
    rule: ForbiddenFlowRule

    @field_validator(
        "runtime_manifest_sha256",
        "guard_configuration_sha256",
        "guard_receipt_sha256",
    )
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class MonitorInstrumentationActivation(LegacyContentAddressedModel):
    """Complete external activation result for one exact monitor runtime."""

    schema_version: Literal["aecbench.monitor-instrumentation-activation.v1"] = (
        "aecbench.monitor-instrumentation-activation.v1"
    )
    runtime_manifest_sha256: str
    guard_configuration_sha256: str
    canary_activation_sha256s: tuple[str, ...]
    flow_activation_sha256s: tuple[str, ...]
    guard_receipt_sha256s: tuple[str, ...]

    @field_validator(
        "runtime_manifest_sha256",
        "guard_configuration_sha256",
    )
    @classmethod
    def validate_required_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator(
        "canary_activation_sha256s",
        "flow_activation_sha256s",
        "guard_receipt_sha256s",
    )
    @classmethod
    def canonicalize_hashes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        for digest in value:
            validate_sha256(digest)
        if len(value) != len(set(value)):
            raise ValueError("monitor instrumentation activation references must be unique")
        return tuple(sorted(value))


_INSTRUMENTATION_OBSERVER = AuthorityPrincipal(
    principal_id="host.monitor-instrumentation-supervisor",
    kind=AuthorityPrincipalKind.HOST_RUNTIME,
)


def activate_production_monitor_instrumentation(
    *,
    runtime: ProductionMonitorRuntime,
    guard: PrincipalAwareSurfaceGuard,
    authority_ledger: AuthorityLedger,
    motif_canary_contexts: Mapping[str, MotifCanaryProbeContext],
    evidence_root: Path,
) -> MonitorInstrumentationActivation:
    """Run real probes, then activate every exact canary surface and flow collector."""

    selected_runtime = runtime.reload()
    selected_guard = guard.reload()
    manifest = selected_runtime.manifest
    configuration = selected_guard.configuration
    if (
        configuration.execution_scope_sha256 != manifest.execution_scope_sha256
        or configuration.standing_policy_sha256 != manifest.policy.content_sha256
        or configuration.policy != manifest.policy
    ):
        raise MonitorInstrumentationError("surface guard does not bind the exact monitor runtime policy and scope")
    if authority_ledger.root != authority_ledger.root.resolve(strict=False):
        raise MonitorInstrumentationError("monitor authority ledger root must be canonical")
    root = _prepare_evidence_root(
        Path(evidence_root),
        protected_roots=(
            selected_runtime.root,
            selected_guard.root,
            authority_ledger.root,
            *(Path(placement.surface.host_root) for placement in manifest.canary_placements),
        ),
    )
    motif_ids = {canary.canary_id for canary in manifest.policy.canaries if canary.kind is CanaryKind.MOTIF}
    if set(motif_canary_contexts) != motif_ids:
        raise MonitorInstrumentationError("motif canary probe contexts must cover every exact motif canary")

    canary_activations: list[CanarySurfaceActivation] = []
    for commitment in manifest.policy.canaries:
        configuration_evidence: MotifCanaryProbeEvidence | OrdinaryLedgerCanaryProbeEvidence
        if commitment.kind is CanaryKind.MOTIF:
            context = MotifCanaryProbeContext.model_validate(
                motif_canary_contexts[commitment.canary_id].model_dump(mode="python")
            )
            configuration_evidence = _probe_motif_canary(
                runtime=selected_runtime,
                commitment=commitment,
                context=context,
            )
        else:
            configuration_evidence = _probe_ordinary_ledger_canary(
                runtime=selected_runtime,
                commitment=commitment,
                authority_ledger=authority_ledger,
            )
        canary_activations.append(
            _activate_canary(
                runtime=selected_runtime,
                commitment=commitment,
                configuration_evidence=configuration_evidence,
                guard_configuration_sha256=configuration.content_sha256,
                evidence_root=root,
            )
        )

    flow_activations: list[FlowCollectorActivation] = []
    guard_receipts: list[SurfaceAccessAuditReceipt] = []
    for rule in manifest.policy.forbidden_flow_rules:
        activation, receipt = _activate_flow_rule(
            runtime=selected_runtime,
            guard=selected_guard,
            rule=rule,
            evidence_root=root,
        )
        flow_activations.append(activation)
        guard_receipts.append(receipt)

    return MonitorInstrumentationActivation(
        runtime_manifest_sha256=manifest.content_sha256,
        guard_configuration_sha256=configuration.content_sha256,
        canary_activation_sha256s=tuple(activation.content_sha256 for activation in canary_activations),
        flow_activation_sha256s=tuple(activation.content_sha256 for activation in flow_activations),
        guard_receipt_sha256s=tuple(receipt.content_sha256 for receipt in guard_receipts),
    )


def _probe_motif_canary(
    *,
    runtime: ProductionMonitorRuntime,
    commitment: CanaryCommitment,
    context: MotifCanaryProbeContext,
) -> MotifCanaryProbeEvidence:
    payload = _read_canary_payload(runtime, commitment)
    motif_sha256 = _required_string(payload, "motif_sha256")
    subject_sha256 = _required_string(payload, "motif_subject_sha256")
    effective_state = _required_string(payload, "effective_state")
    if context.assurance_snapshot.content_sha256 != runtime.manifest.cycle_plan.assurance_snapshot_sha256:
        raise MonitorInstrumentationError("motif canary probe assurance snapshot differs from the monitor cycle")
    decision = select_motif(context.library, context.selection_request)
    selected = resolve_motif_selection(
        context.library,
        context.selection_request,
        decision,
    )
    if (
        decision.outcome is not MotifSelectionOutcome.SELECTED
        or selected is None
        or selected.motif_sha256 != motif_sha256
        or motif_subject_sha256(selected) != subject_sha256
    ):
        raise MonitorInstrumentationError("real motif selector did not select the exact motif canary")
    entry = context.assurance_snapshot.require(subject_sha256)
    if entry.eligible or entry.state.value != effective_state or commitment.expected_effective_state != effective_state:
        raise MonitorInstrumentationError("motif canary is not in its exact non-eligible assurance state")
    try:
        AssuredMotifSelectionRecord.create(
            selection_request=context.selection_request,
            selection_decision=decision,
            selected_motif=selected,
            snapshot=context.assurance_snapshot,
        )
    except ValueError as error:
        if str(error) != ("assured selection requires an active eligible motif subject"):
            raise MonitorInstrumentationError("motif canary assurance boundary failed unexpectedly") from error
    else:
        raise MonitorInstrumentationError("revoked motif canary crossed the assurance selection boundary")
    return MotifCanaryProbeEvidence(
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        canary_commitment_sha256=commitment.content_sha256,
        motif_sha256=motif_sha256,
        motif_subject_sha256=subject_sha256,
        library_archive_sha256=context.library.archive_sha256,
        selection_request_sha256=context.selection_request.request_sha256,
        selection_decision_sha256=decision.decision_sha256,
        assurance_snapshot_sha256=context.assurance_snapshot.content_sha256,
        observed_effective_state=effective_state,
    )


def _probe_ordinary_ledger_canary(
    *,
    runtime: ProductionMonitorRuntime,
    commitment: CanaryCommitment,
    authority_ledger: AuthorityLedger,
) -> OrdinaryLedgerCanaryProbeEvidence:
    _read_canary_payload(runtime, commitment)
    try:
        authority_ledger.resolve_authority_event_by_content(commitment.artifact_sha256)
    except AuthorityLedgerIntegrityError as error:
        if str(error) != "authority event is missing":
            raise MonitorInstrumentationError(
                "ordinary-ledger canary authority resolution failed unexpectedly"
            ) from error
    else:
        raise MonitorInstrumentationError("ordinary-ledger canary resolved as trusted authority")
    return OrdinaryLedgerCanaryProbeEvidence(
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        canary_commitment_sha256=commitment.content_sha256,
        ordinary_artifact_sha256=commitment.artifact_sha256,
    )


def _activate_canary(
    *,
    runtime: ProductionMonitorRuntime,
    commitment: CanaryCommitment,
    configuration_evidence: (MotifCanaryProbeEvidence | OrdinaryLedgerCanaryProbeEvidence),
    guard_configuration_sha256: str,
    evidence_root: Path,
) -> CanarySurfaceActivation:
    placement = next(
        placement for placement in runtime.manifest.canary_placements if placement.canary_id == commitment.canary_id
    )
    directory = evidence_root / "canary-surfaces" / commitment.content_sha256
    semantic_probe_path = directory / "semantic-probe.json"
    semantic_probe_bytes = _canonical_model_bytes(configuration_evidence)
    _publish_exact(semantic_probe_path, semantic_probe_bytes)
    configuration = CanaryLogicalProjectionConfiguration(
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        canary_commitment_sha256=commitment.content_sha256,
        surface_sha256=placement.surface.content_sha256,
        host_path=placement.host_path,
        logical_projection_key=placement.logical_projection_key,
        guard_configuration_sha256=guard_configuration_sha256,
        semantic_probe_evidence_path=str(semantic_probe_path.resolve()),
        semantic_probe_evidence_sha256=hashlib.sha256(semantic_probe_bytes).hexdigest(),
    )
    configuration_path = directory / "configuration.json"
    configuration_bytes = _canonical_model_bytes(configuration)
    _publish_exact(configuration_path, configuration_bytes)
    probe = CanarySurfaceProbeReceipt(
        probe_id=f"probe.{commitment.canary_id}",
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        canary_commitment_sha256=commitment.content_sha256,
        host_path=placement.host_path,
        logical_projection_key=placement.logical_projection_key,
        projection_configuration_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        observed_artifact_sha256=commitment.artifact_sha256,
        observed_by=_INSTRUMENTATION_OBSERVER,
        host_placement_confirmed=True,
    )
    probe_path = directory / "probe-receipt.json"
    _publish_exact(probe_path, _canonical_model_bytes(probe))
    return runtime.activate_canary_surface(
        canary_id=commitment.canary_id,
        configuration_artifact_path=configuration_path,
        probe_receipt_path=probe_path,
    )


def _activate_flow_rule(
    *,
    runtime: ProductionMonitorRuntime,
    guard: PrincipalAwareSurfaceGuard,
    rule: ForbiddenFlowRule,
    evidence_root: Path,
) -> tuple[FlowCollectorActivation, SurfaceAccessAuditReceipt]:
    rule_id = ".".join(
        (
            rule.source_principal_kind.value,
            rule.target_surface.value,
            rule.action.value,
        )
    )
    directory = evidence_root / "flow-collectors" / rule_id
    attempt_evidence = SurfaceGuardProbeEvidence(
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        guard_configuration_sha256=guard.configuration.content_sha256,
        rule=rule,
    )
    attempt_evidence_path = directory / "attempt-evidence.json"
    _publish_exact(
        attempt_evidence_path,
        _canonical_model_bytes(attempt_evidence),
    )
    try:
        guard.reload().authorize_attempt(
            attempt_id=(f"probe.{runtime.manifest.content_sha256[:16]}.{rule_id}"),
            source_principal_kind=rule.source_principal_kind,
            target_surface=rule.target_surface,
            action=rule.action,
            evidence_path=attempt_evidence_path,
        )
    except SurfaceAccessDenied as denied:
        receipt = guard.reload().load_receipt(denied.receipt_sha256)
    else:
        raise MonitorInstrumentationError("standing forbidden-flow probe was not denied by the surface guard")
    if receipt.decision is not SurfaceAccessDecision.DENIED or receipt.matching_rule != rule or not receipt.captured:
        raise MonitorInstrumentationError("surface guard receipt does not prove the exact rule was captured and denied")
    configuration = FlowCollectorConfigurationEvidence(
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        guard_configuration_sha256=guard.configuration.content_sha256,
        guard_receipt_sha256=receipt.content_sha256,
        rule=rule,
    )
    configuration_path = directory / "configuration.json"
    configuration_bytes = _canonical_model_bytes(configuration)
    _publish_exact(configuration_path, configuration_bytes)
    guard_receipt_path = guard.reload().receipt_path(receipt.content_sha256)
    guard_receipt_bytes = guard_receipt_path.read_bytes()
    probe = FlowCollectorProbeReceipt(
        probe_id=f"probe.flow.{rule_id}",
        runtime_manifest_sha256=runtime.manifest.content_sha256,
        execution_scope_sha256=runtime.manifest.execution_scope_sha256,
        rule=rule,
        collector_kind=FlowCollectorKind.AUDIT_OR_DENIAL_PROBE,
        configuration_artifact_sha256=hashlib.sha256(configuration_bytes).hexdigest(),
        probe_evidence_sha256=hashlib.sha256(guard_receipt_bytes).hexdigest(),
        outcome=FlowCollectorProbeOutcome.CAPTURED_OR_BLOCKED,
        observed_by=_INSTRUMENTATION_OBSERVER,
        collector_armed=True,
    )
    probe_path = directory / "probe-receipt.json"
    _publish_exact(probe_path, _canonical_model_bytes(probe))
    activation = runtime.activate_flow_collector(
        rule=rule,
        configuration_artifact_path=configuration_path,
        probe_evidence_path=guard_receipt_path,
        probe_receipt_path=probe_path,
    )
    return activation, receipt


def _read_canary_payload(
    runtime: ProductionMonitorRuntime,
    commitment: CanaryCommitment,
) -> dict[str, JsonValue]:
    path = runtime.canary_path(commitment.canary_id)
    try:
        payload: JsonValue = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as error:
        raise MonitorInstrumentationError("physical monitor canary is not readable JSON") from error
    if not isinstance(payload, dict) or canonical_json_sha256(payload) != commitment.artifact_sha256:
        raise MonitorInstrumentationError("physical monitor canary differs from its exact commitment")
    return payload


def _required_string(payload: Mapping[str, JsonValue], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise MonitorInstrumentationError(f"motif canary payload requires {field}")
    return value


def _prepare_evidence_root(
    path: Path,
    *,
    protected_roots: tuple[Path, ...],
) -> Path:
    if os.path.lexists(path) and path.is_symlink():
        raise MonitorInstrumentationError("monitor instrumentation evidence root must not be a symlink")
    root = path.resolve(strict=False)
    normalized_protected = tuple(protected.resolve(strict=False) for protected in protected_roots)
    if any(_paths_overlap(root, protected) for protected in normalized_protected):
        raise MonitorInstrumentationError("monitor instrumentation evidence root overlaps a protected root")
    root.mkdir(parents=True, exist_ok=True)
    root.chmod(0o700)
    return root


def _publish_exact(path: Path, content: bytes) -> None:
    _require_safe_parent(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    _require_safe_parent(path)
    if os.path.lexists(path):
        if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
            raise MonitorInstrumentationError("monitor instrumentation path contains different immutable content")
        return
    temporary = path.parent / f".{path.name}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError:
            if path.is_symlink() or not path.is_file() or path.read_bytes() != content:
                raise MonitorInstrumentationError(
                    "monitor instrumentation path contains different immutable content"
                ) from None
    finally:
        temporary.unlink(missing_ok=True)


def _require_safe_parent(path: Path) -> None:
    cursor = path.parent
    while not cursor.exists():
        cursor = cursor.parent
    if cursor.is_symlink():
        raise MonitorInstrumentationError("monitor instrumentation path contains a symlink")
    current = cursor
    for part in path.parent.relative_to(cursor).parts:
        current /= part
        if os.path.lexists(current) and current.is_symlink():
            raise MonitorInstrumentationError("monitor instrumentation path contains a symlink")


def _canonical_model_bytes(model: FrozenStrictModel) -> bytes:
    return (
        json.dumps(
            model.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)
