# ABOUTME: Guards principal-aware task, critic, authority, holdout, and promotion surface access.
# ABOUTME: Keeps exact allow or deny receipts under the standing forbidden-flow policy.

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from pydantic import field_validator, model_validator

from aec_bench.contracts.authority import (
    AuthorityPrincipal,
    AuthorityPrincipalKind,
)
from aec_bench.contracts.harness_kernel import (
    FrozenStrictModel,
    validate_sha256,
)
from aec_bench.contracts.legacy_content_address import LegacyContentAddressedModel
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.experimentation.governance.standing_monitors import (
    FlowAction,
    FlowSurface,
    ForbiddenFlowRule,
    StandingMonitorPolicy,
)
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class SurfaceGuardError(RuntimeError):
    """Base failure for the host-owned principal-aware surface guard."""


class SurfaceGuardConfinementError(SurfaceGuardError):
    """Raised when guard state or evidence crosses a protected root."""


class SurfaceGuardCollisionError(SurfaceGuardError):
    """Raised when an immutable guard identity is rebound to different content."""


class SurfaceGuardIntegrityError(SurfaceGuardError):
    """Raised when persisted guard state cannot be reloaded exactly."""


class SurfaceAccessDecision(StrEnum):
    """Closed decisions emitted before a requested surface effect."""

    ALLOWED = "allowed"
    DENIED = "denied"


class SurfaceAccessDenied(SurfaceGuardError):
    """Raised after a forbidden attempt is durably captured and denied."""

    def __init__(self, *, attempt_id: str, receipt_sha256: str) -> None:
        self.attempt_id = attempt_id
        self.receipt_sha256 = validate_sha256(receipt_sha256)
        super().__init__(f"surface access denied for {attempt_id}; receipt {receipt_sha256}")


class SurfaceGuardConfiguration(LegacyContentAddressedModel):
    """Exact standing policy and filesystem confinement for one guard instance."""

    schema_version: Literal["aecbench.surface-guard-configuration.v1"] = "aecbench.surface-guard-configuration.v1"
    guard_id: NonEmptyStr
    execution_scope_sha256: str
    standing_policy_sha256: str
    policy: StandingMonitorPolicy
    candidate_roots: tuple[NonEmptyStr, ...]
    observed_by: AuthorityPrincipal

    @field_validator("execution_scope_sha256", "standing_policy_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)

    @field_validator("candidate_roots")
    @classmethod
    def canonicalize_candidate_roots(
        cls,
        value: tuple[str, ...],
    ) -> tuple[str, ...]:
        if any(not Path(root).is_absolute() for root in value):
            raise ValueError("surface guard candidate roots must be absolute")
        if len(value) != len(set(value)):
            raise ValueError("surface guard candidate roots must be unique")
        return tuple(sorted(value))

    @model_validator(mode="after")
    def validate_configuration(self) -> Self:
        if self.standing_policy_sha256 != self.policy.content_sha256:
            raise ValueError("surface guard configuration does not bind its standing policy")
        if self.observed_by.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
            raise ValueError("surface guard requires a host-runtime observer")
        return self


class SurfaceAccessAttempt(LegacyContentAddressedModel):
    """One exact principal, surface, action, and copied evidence identity."""

    schema_version: Literal["aecbench.surface-access-attempt.v1"] = "aecbench.surface-access-attempt.v1"
    attempt_id: NonEmptyStr
    guard_configuration_sha256: str
    source_principal_kind: AuthorityPrincipalKind
    target_surface: FlowSurface
    action: FlowAction
    evidence_sha256: str

    @field_validator("guard_configuration_sha256", "evidence_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


class SurfaceAccessAuditReceipt(LegacyContentAddressedModel):
    """Durable decision proving one exact attempt was captured before its effect."""

    schema_version: Literal["aecbench.surface-access-audit-receipt.v1"] = "aecbench.surface-access-audit-receipt.v1"
    guard_configuration_sha256: str
    attempt: SurfaceAccessAttempt
    matching_rule: ForbiddenFlowRule | None
    decision: SurfaceAccessDecision
    captured: Literal[True] = True
    observed_by: AuthorityPrincipal

    @field_validator("guard_configuration_sha256")
    @classmethod
    def validate_configuration_hash(cls, value: str) -> str:
        return validate_sha256(value)

    @model_validator(mode="after")
    def validate_decision_binding(self) -> Self:
        if self.guard_configuration_sha256 != self.attempt.guard_configuration_sha256:
            raise ValueError("surface access receipt does not bind its attempt configuration")
        if self.observed_by.kind is not AuthorityPrincipalKind.HOST_RUNTIME:
            raise ValueError("surface access receipt requires a host-runtime observer")
        if self.matching_rule is None:
            if self.decision is not SurfaceAccessDecision.ALLOWED:
                raise ValueError("surface access without a forbidden rule must be allowed")
            return self
        if (
            self.matching_rule.source_principal_kind is not self.attempt.source_principal_kind
            or self.matching_rule.target_surface is not self.attempt.target_surface
            or self.matching_rule.action is not self.attempt.action
            or self.decision is not SurfaceAccessDecision.DENIED
        ):
            raise ValueError("surface access forbidden rule must exactly match a denied attempt")
        return self


class _SurfaceGuardConfigurationClaim(LegacyContentAddressedModel):
    """Exclusive binding from one guard identity to one configuration."""

    schema_version: Literal["aecbench.surface-guard-configuration-claim.v1"] = (
        "aecbench.surface-guard-configuration-claim.v1"
    )
    guard_id: NonEmptyStr
    configuration_sha256: str

    @field_validator("configuration_sha256")
    @classmethod
    def validate_configuration_hash(cls, value: str) -> str:
        return validate_sha256(value)


class _SurfaceAccessAttemptClaim(LegacyContentAddressedModel):
    """Exclusive binding from one attempt identity to one audit receipt."""

    schema_version: Literal["aecbench.surface-access-attempt-claim.v1"] = "aecbench.surface-access-attempt-claim.v1"
    guard_configuration_sha256: str
    attempt_id: NonEmptyStr
    receipt_sha256: str

    @field_validator("guard_configuration_sha256", "receipt_sha256")
    @classmethod
    def validate_hashes(cls, value: str) -> str:
        return validate_sha256(value)


_GUARD_OBSERVER = AuthorityPrincipal(
    principal_id="host.principal-aware-surface-guard",
    kind=AuthorityPrincipalKind.HOST_RUNTIME,
)


class PrincipalAwareSurfaceGuard:
    """Host-owned pre-effect gate over the exact standing forbidden-flow policy."""

    def __init__(
        self,
        *,
        root: Path,
        configuration: SurfaceGuardConfiguration,
        configuration_path: Path,
    ) -> None:
        self._root = root
        self._configuration = configuration
        self._configuration_path = configuration_path

    @property
    def root(self) -> Path:
        """Return the canonical host-owned guard root."""

        return self._root

    @property
    def configuration(self) -> SurfaceGuardConfiguration:
        """Return the exact immutable guard configuration."""

        return self._configuration

    @property
    def configuration_path(self) -> Path:
        """Return the exact immutable configuration object path."""

        return self._configuration_path

    @classmethod
    def open(
        cls,
        *,
        root: Path,
        guard_id: str,
        execution_scope_sha256: str,
        policy: StandingMonitorPolicy,
        candidate_roots: tuple[Path, ...] = (),
    ) -> PrincipalAwareSurfaceGuard:
        """Create or idempotently reopen one exact host-confined guard."""

        normalized_root, normalized_candidates = _prepare_root(
            root=Path(root),
            candidate_roots=candidate_roots,
            create=True,
        )
        selected_policy = StandingMonitorPolicy.model_validate(policy.model_dump(mode="python"))
        configuration = SurfaceGuardConfiguration(
            guard_id=guard_id,
            execution_scope_sha256=execution_scope_sha256,
            standing_policy_sha256=selected_policy.content_sha256,
            policy=selected_policy,
            candidate_roots=tuple(str(path) for path in normalized_candidates),
            observed_by=_GUARD_OBSERVER,
        )
        configuration_path = _configuration_object_path(
            normalized_root,
            configuration.content_sha256,
        )
        _publish_exact(
            root=normalized_root,
            path=configuration_path,
            content=_canonical_model_bytes(configuration),
        )
        claim = _SurfaceGuardConfigurationClaim(
            guard_id=guard_id,
            configuration_sha256=configuration.content_sha256,
        )
        _publish_claim(
            root=normalized_root,
            path=_configuration_claim_path(normalized_root, guard_id),
            claim=claim,
            model_type=_SurfaceGuardConfigurationClaim,
            label="surface guard configuration",
        )
        return cls._load_exact(
            root=normalized_root,
            expected=configuration,
        )

    @classmethod
    def load(
        cls,
        *,
        root: Path,
        guard_id: str,
        execution_scope_sha256: str,
        policy: StandingMonitorPolicy,
        candidate_roots: tuple[Path, ...] = (),
    ) -> PrincipalAwareSurfaceGuard:
        """Reload one guard only under its exact policy and confinement inputs."""

        normalized_root, normalized_candidates = _prepare_root(
            root=Path(root),
            candidate_roots=candidate_roots,
            create=False,
        )
        selected_policy = StandingMonitorPolicy.model_validate(policy.model_dump(mode="python"))
        expected = SurfaceGuardConfiguration(
            guard_id=guard_id,
            execution_scope_sha256=execution_scope_sha256,
            standing_policy_sha256=selected_policy.content_sha256,
            policy=selected_policy,
            candidate_roots=tuple(str(path) for path in normalized_candidates),
            observed_by=_GUARD_OBSERVER,
        )
        return cls._load_exact(root=normalized_root, expected=expected)

    @classmethod
    def _load_exact(
        cls,
        *,
        root: Path,
        expected: SurfaceGuardConfiguration,
    ) -> PrincipalAwareSurfaceGuard:
        claim = _load_model(
            root=root,
            path=_configuration_claim_path(root, expected.guard_id),
            model_type=_SurfaceGuardConfigurationClaim,
            label="surface guard configuration claim",
        )
        if claim.guard_id != expected.guard_id or claim.configuration_sha256 != expected.content_sha256:
            raise SurfaceGuardIntegrityError("surface guard configuration claim differs from expected inputs")
        path = _configuration_object_path(root, claim.configuration_sha256)
        configuration = _load_model(
            root=root,
            path=path,
            model_type=SurfaceGuardConfiguration,
            label="surface guard configuration",
        )
        if configuration != expected:
            raise SurfaceGuardIntegrityError("surface guard configuration differs from expected inputs")
        return cls(
            root=root,
            configuration=configuration,
            configuration_path=path,
        )

    def reload(self) -> PrincipalAwareSurfaceGuard:
        """Reload this exact guard without accepting caller identity changes."""

        return type(self).load(
            root=self._root,
            guard_id=self._configuration.guard_id,
            execution_scope_sha256=self._configuration.execution_scope_sha256,
            policy=self._configuration.policy,
            candidate_roots=tuple(Path(root) for root in self._configuration.candidate_roots),
        )

    def authorize_attempt(
        self,
        *,
        attempt_id: str,
        source_principal_kind: AuthorityPrincipalKind,
        target_surface: FlowSurface,
        action: FlowAction,
        evidence_path: Path,
    ) -> SurfaceAccessAuditReceipt:
        """Capture one attempt, returning only allowed access and raising on denial."""

        evidence = _read_external_evidence(
            path=Path(evidence_path),
            root=self._root,
            candidate_roots=tuple(Path(root) for root in self._configuration.candidate_roots),
        )
        evidence_sha256 = hashlib.sha256(evidence).hexdigest()
        _publish_exact(
            root=self._root,
            path=_evidence_object_path(self._root, evidence_sha256),
            content=evidence,
        )
        attempt = SurfaceAccessAttempt(
            attempt_id=attempt_id,
            guard_configuration_sha256=self._configuration.content_sha256,
            source_principal_kind=source_principal_kind,
            target_surface=target_surface,
            action=action,
            evidence_sha256=evidence_sha256,
        )
        matches = tuple(
            rule
            for rule in self._configuration.policy.forbidden_flow_rules
            if (
                rule.source_principal_kind is attempt.source_principal_kind
                and rule.target_surface is attempt.target_surface
                and rule.action is attempt.action
            )
        )
        if len(matches) > 1:
            raise SurfaceGuardIntegrityError("standing policy contains duplicate exact forbidden-flow rules")
        matching_rule = matches[0] if matches else None
        receipt = SurfaceAccessAuditReceipt(
            guard_configuration_sha256=self._configuration.content_sha256,
            attempt=attempt,
            matching_rule=matching_rule,
            decision=(SurfaceAccessDecision.DENIED if matching_rule is not None else SurfaceAccessDecision.ALLOWED),
            observed_by=_GUARD_OBSERVER,
        )
        _publish_exact(
            root=self._root,
            path=_attempt_object_path(self._root, attempt.content_sha256),
            content=_canonical_model_bytes(attempt),
        )
        _publish_exact(
            root=self._root,
            path=_receipt_object_path(self._root, receipt.content_sha256),
            content=_canonical_model_bytes(receipt),
        )
        claim = _SurfaceAccessAttemptClaim(
            guard_configuration_sha256=self._configuration.content_sha256,
            attempt_id=attempt.attempt_id,
            receipt_sha256=receipt.content_sha256,
        )
        _publish_claim(
            root=self._root,
            path=_attempt_claim_path(
                self._root,
                self._configuration.content_sha256,
                attempt.attempt_id,
            ),
            claim=claim,
            model_type=_SurfaceAccessAttemptClaim,
            label="surface access attempt",
        )
        reloaded = self.load_receipt(receipt.content_sha256)
        if reloaded.decision is SurfaceAccessDecision.DENIED:
            raise SurfaceAccessDenied(
                attempt_id=attempt.attempt_id,
                receipt_sha256=reloaded.content_sha256,
            )
        return reloaded

    def load_receipt(self, receipt_sha256: str) -> SurfaceAccessAuditReceipt:
        """Reload one exact receipt, its attempt, claim, and copied evidence."""

        validate_sha256(receipt_sha256)
        receipt = _load_model(
            root=self._root,
            path=_receipt_object_path(self._root, receipt_sha256),
            model_type=SurfaceAccessAuditReceipt,
            label="surface access audit receipt",
        )
        if (
            receipt.content_sha256 != receipt_sha256
            or receipt.guard_configuration_sha256 != self._configuration.content_sha256
        ):
            raise SurfaceGuardIntegrityError("surface access receipt differs from its guard or lookup identity")
        attempt = _load_model(
            root=self._root,
            path=_attempt_object_path(
                self._root,
                receipt.attempt.content_sha256,
            ),
            model_type=SurfaceAccessAttempt,
            label="surface access attempt",
        )
        if attempt != receipt.attempt:
            raise SurfaceGuardIntegrityError("surface access receipt attempt changed after capture")
        claim = _load_model(
            root=self._root,
            path=_attempt_claim_path(
                self._root,
                self._configuration.content_sha256,
                attempt.attempt_id,
            ),
            model_type=_SurfaceAccessAttemptClaim,
            label="surface access attempt claim",
        )
        if (
            claim.guard_configuration_sha256 != self._configuration.content_sha256
            or claim.attempt_id != attempt.attempt_id
            or claim.receipt_sha256 != receipt.content_sha256
        ):
            raise SurfaceGuardIntegrityError("surface access attempt claim differs from its receipt")
        evidence = _read_private_file(
            root=self._root,
            path=_evidence_object_path(self._root, attempt.evidence_sha256),
            label="surface access attempt evidence",
        )
        if hashlib.sha256(evidence).hexdigest() != attempt.evidence_sha256:
            raise SurfaceGuardIntegrityError("surface access attempt evidence digest changed")
        expected_rule = next(
            (
                rule
                for rule in self._configuration.policy.forbidden_flow_rules
                if (
                    rule.source_principal_kind is attempt.source_principal_kind
                    and rule.target_surface is attempt.target_surface
                    and rule.action is attempt.action
                )
            ),
            None,
        )
        if receipt.matching_rule != expected_rule:
            raise SurfaceGuardIntegrityError("surface access receipt decision differs from the standing policy")
        return receipt

    def receipt_path(self, receipt_sha256: str) -> Path:
        """Return one verified receipt's immutable object path."""

        self.load_receipt(receipt_sha256)
        return _receipt_object_path(self._root, receipt_sha256)


def _prepare_root(
    *,
    root: Path,
    candidate_roots: tuple[Path, ...],
    create: bool,
) -> tuple[Path, tuple[Path, ...]]:
    if os.path.lexists(root) and root.is_symlink():
        raise SurfaceGuardConfinementError("surface guard root must not be a symlink")
    normalized_root = root.resolve(strict=False)
    normalized_candidates = tuple(
        sorted(
            (Path(path).resolve(strict=False) for path in candidate_roots),
            key=str,
        )
    )
    if len(normalized_candidates) != len(set(normalized_candidates)):
        raise SurfaceGuardConfinementError("surface guard candidate roots must be unique")
    if any(_paths_overlap(normalized_root, candidate) for candidate in normalized_candidates):
        raise SurfaceGuardConfinementError("surface guard root must not overlap a candidate root")
    if create:
        mkdir_durable(normalized_root)
        normalized_root.chmod(0o700)
        fsync_directory(normalized_root.parent)
    if (
        not normalized_root.is_dir()
        or normalized_root.is_symlink()
        or stat.S_IMODE(normalized_root.stat().st_mode) & 0o077
    ):
        raise SurfaceGuardConfinementError("surface guard root must be a private regular directory")
    return normalized_root, normalized_candidates


def _publish_claim[ModelT: FrozenStrictModel](
    *,
    root: Path,
    path: Path,
    claim: ModelT,
    model_type: type[ModelT],
    label: str,
) -> None:
    if os.path.lexists(path):
        existing = _load_model(
            root=root,
            path=path,
            model_type=model_type,
            label=f"{label} claim",
        )
        if existing != claim:
            raise SurfaceGuardCollisionError(f"{label} is already bound to different content")
        return
    try:
        _publish_exact(
            root=root,
            path=path,
            content=_canonical_model_bytes(claim),
        )
    except SurfaceGuardCollisionError:
        existing = _load_model(
            root=root,
            path=path,
            model_type=model_type,
            label=f"{label} claim",
        )
        if existing != claim:
            raise


def _publish_exact(*, root: Path, path: Path, content: bytes) -> None:
    _guard_path(root, path)
    _mkdir_private(path.parent)
    _guard_path(root, path)
    if os.path.lexists(path):
        if _read_private_file(root=root, path=path, label="surface guard artifact") != content:
            raise SurfaceGuardCollisionError("surface guard path contains different immutable content")
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
            if (
                _read_private_file(
                    root=root,
                    path=path,
                    label="surface guard artifact",
                )
                != content
            ):
                raise SurfaceGuardCollisionError("surface guard path contains different immutable content") from None
        fsync_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def _mkdir_private(path: Path) -> None:
    missing: list[Path] = []
    cursor = path
    while not cursor.exists():
        missing.append(cursor)
        cursor = cursor.parent
    mkdir_durable(path)
    for directory in reversed(missing):
        directory.chmod(0o700)
        fsync_directory(directory.parent)


def _load_model[ModelT: FrozenStrictModel](
    *,
    root: Path,
    path: Path,
    model_type: type[ModelT],
    label: str,
) -> ModelT:
    encoded = _read_private_file(root=root, path=path, label=label)
    try:
        model = model_type.model_validate_json(encoded)
    except ValueError as error:
        raise SurfaceGuardIntegrityError(f"{label} is corrupt or has the wrong typed schema") from error
    if _canonical_model_bytes(model) != encoded:
        raise SurfaceGuardIntegrityError(f"{label} is not canonically serialized")
    return model


def _read_private_file(*, root: Path, path: Path, label: str) -> bytes:
    _guard_path(root, path)
    if not os.path.lexists(path):
        raise SurfaceGuardIntegrityError(f"{label} is missing")
    if path.is_symlink() or not path.is_file():
        raise SurfaceGuardConfinementError(f"{label} must be a regular non-symlink file")
    if stat.S_IMODE(path.stat(follow_symlinks=False).st_mode) & 0o077:
        raise SurfaceGuardConfinementError(f"{label} must retain host-only permissions")
    try:
        return path.read_bytes()
    except OSError as error:
        raise SurfaceGuardIntegrityError(f"{label} is unreadable") from error


def _read_external_evidence(
    *,
    path: Path,
    root: Path,
    candidate_roots: tuple[Path, ...],
) -> bytes:
    supplied = Path(os.path.abspath(path))
    cursor = Path(supplied.anchor)
    for part in supplied.relative_to(cursor).parts:
        cursor /= part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise SurfaceGuardConfinementError("surface guard attempt evidence must be a regular non-symlink file")
    normalized = supplied.resolve(strict=False)
    if _paths_overlap(normalized, root) or any(_paths_overlap(normalized, candidate) for candidate in candidate_roots):
        raise SurfaceGuardConfinementError("surface guard attempt evidence must remain host-owned and external")
    if not os.path.lexists(normalized):
        raise SurfaceGuardIntegrityError("surface guard attempt evidence is missing")
    if normalized.is_symlink() or not normalized.is_file():
        raise SurfaceGuardConfinementError("surface guard attempt evidence must be a regular non-symlink file")
    try:
        content = normalized.read_bytes()
    except OSError as error:
        raise SurfaceGuardIntegrityError("surface guard attempt evidence is unreadable") from error
    if not content:
        raise SurfaceGuardIntegrityError("surface guard attempt evidence must not be empty")
    return content


def _guard_path(root: Path, path: Path) -> None:
    absolute_root = Path(os.path.abspath(root))
    absolute = Path(os.path.abspath(path))
    if not absolute.is_relative_to(absolute_root):
        raise SurfaceGuardConfinementError("surface guard artifact escapes its host-owned root")
    cursor = absolute_root
    if os.path.lexists(cursor) and cursor.is_symlink():
        raise SurfaceGuardConfinementError("surface guard root must not be a symlink")
    for part in absolute.relative_to(absolute_root).parts:
        cursor /= part
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise SurfaceGuardConfinementError("surface guard artifact path contains a symlink")


def _configuration_object_path(root: Path, digest: str) -> Path:
    return root / "objects" / "configurations" / digest / "configuration.json"


def _configuration_claim_path(root: Path, guard_id: str) -> Path:
    digest = hashlib.sha256(guard_id.encode()).hexdigest()
    return root / "claims" / "configurations" / digest / "claim.json"


def _evidence_object_path(root: Path, digest: str) -> Path:
    return root / "objects" / "evidence" / digest / "evidence.bin"


def _attempt_object_path(root: Path, digest: str) -> Path:
    return root / "objects" / "attempts" / digest / "attempt.json"


def _receipt_object_path(root: Path, digest: str) -> Path:
    return root / "objects" / "receipts" / digest / "receipt.json"


def _attempt_claim_path(
    root: Path,
    configuration_sha256: str,
    attempt_id: str,
) -> Path:
    logical = json.dumps(
        {
            "configuration_sha256": configuration_sha256,
            "attempt_id": attempt_id,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return root / "claims" / "attempts" / hashlib.sha256(logical).hexdigest() / "claim.json"


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
