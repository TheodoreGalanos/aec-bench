# ABOUTME: Persists host-observed origin and authority artifacts outside candidate-controlled roots.
# ABOUTME: Enforces canonical durable bytes, typed basis closure, and human transition provenance.

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import field_validator

from aec_bench.contracts.authority import (
    AuthorityAction,
    AuthorityDecision,
    AuthorityEvent,
    AuthorityPrincipal,
    AuthorityPrincipalKind,
    BasisKind,
    BasisReference,
    HumanAuthorityApproval,
    MotifPromotionAssurance,
    MotifPromotionQualification,
    OriginStamp,
    PromotionMonitorAttestation,
    PromotionSubjectLineage,
    TaintLabel,
    derive_origin_stamp,
)
from aec_bench.contracts.content_address import ContentAddressedModel
from aec_bench.contracts.evaluation_outcome import (
    CriticEvaluationOutcome,
    EvaluationOutcome,
)
from aec_bench.contracts.evaluation_plane import Critic
from aec_bench.contracts.harness_kernel import FrozenStrictModel, validate_sha256
from aec_bench.contracts.validators import NonEmptyStr
from aec_bench.ledger.durability import fsync_directory, mkdir_durable


class AuthorityLedgerError(RuntimeError):
    """Base error for authority-ledger persistence and verification failures."""


class AuthorityLedgerConfinementError(AuthorityLedgerError):
    """Raised when authority bytes could escape or overlap their host-owned root."""


class AuthorityLedgerCollisionError(AuthorityLedgerError):
    """Raised when one logical identity is reused for different immutable content."""


class AuthorityLedgerIntegrityError(AuthorityLedgerError):
    """Raised when stored authority or basis evidence cannot be verified exactly."""


@dataclass(frozen=True)
class StoredOrigin:
    """One canonical origin model and its immutable store path."""

    origin: OriginStamp
    path: Path


@dataclass(frozen=True)
class StoredBasis:
    """One exact basis payload joined to its host-observed origin."""

    reference: BasisReference
    content_path: Path
    origin: OriginStamp
    origin_path: Path


@dataclass(frozen=True)
class StoredAuthorityEvent:
    """One canonical authority event and its immutable store path."""

    event: AuthorityEvent
    path: Path


class _IdentityClaim(ContentAddressedModel):
    """Exclusive mapping from one human-readable identity to one content digest."""

    schema_version: Literal["aecbench.authority-identity-claim.v1"] = "aecbench.authority-identity-claim.v1"
    namespace: NonEmptyStr
    logical_id: NonEmptyStr
    target_content_sha256: str

    @field_validator("target_content_sha256")
    @classmethod
    def validate_target_hash(cls, value: str) -> str:
        return validate_sha256(value)


class _BasisClaim(ContentAddressedModel):
    """Exclusive typed registration of one basis payload and its origin stamp."""

    schema_version: Literal["aecbench.authority-basis-claim.v1"] = "aecbench.authority-basis-claim.v1"
    reference: BasisReference
    origin_sha256: str

    @field_validator("origin_sha256")
    @classmethod
    def validate_origin_hash(cls, value: str) -> str:
        return validate_sha256(value)


_HUMAN_TRANSITION_ACTIONS = frozenset(
    {
        AuthorityAction.RELEASE_CRITIC,
        AuthorityAction.RETIRE_CRITIC,
        AuthorityAction.REVEAL_ACCEPTANCE_MANIFEST,
        AuthorityAction.CHANGE_KERNEL_VERSION,
    }
)
_HOST_PRINCIPAL_KINDS = frozenset(
    {
        AuthorityPrincipalKind.HOST_RUNTIME,
        AuthorityPrincipalKind.HOST_POLICY,
    }
)
_DEFAULT_TYPED_BASIS_MODELS: dict[BasisKind, type[FrozenStrictModel]] = {
    BasisKind.ORIGIN: OriginStamp,
    BasisKind.AUTHORITY_EVENT: AuthorityEvent,
    BasisKind.CRITIC: Critic,
    BasisKind.EVALUATION_OUTCOME: EvaluationOutcome,
    BasisKind.CRITIC_EVALUATION_OUTCOME: CriticEvaluationOutcome,
    BasisKind.PROMOTION_MONITOR: PromotionMonitorAttestation,
    BasisKind.PROMOTION_LINEAGE: PromotionSubjectLineage,
    BasisKind.MOTIF_ASSURANCE: MotifPromotionAssurance,
    BasisKind.MOTIF_QUALIFICATION: MotifPromotionQualification,
    BasisKind.HUMAN_APPROVAL: HumanAuthorityApproval,
}
_REQUIRED_TYPED_BASIS_KINDS = frozenset(
    {
        BasisKind.ORIGIN,
        BasisKind.AUTHORITY_EVENT,
        BasisKind.EVALUATION_OUTCOME,
        BasisKind.CRITIC_EVALUATION_OUTCOME,
        BasisKind.MONITOR_REPORT,
        BasisKind.PROMOTION_MONITOR,
        BasisKind.PROMOTION_LINEAGE,
        BasisKind.MOTIF_ASSURANCE,
        BasisKind.MOTIF_QUALIFICATION,
    }
)
_PROMOTION_ACTIONS = frozenset(
    {
        AuthorityAction.POLICY_PROMOTION,
        AuthorityAction.MOTIF_PROMOTION,
        AuthorityAction.MOTIF_STATE_CHANGE,
    }
)


class AuthorityLedger:
    """Host-confined immutable store for origin, basis, and authority artifacts."""

    def __init__(
        self,
        root: Path,
        *,
        candidate_roots: tuple[Path, ...] = (),
        typed_basis_models: Mapping[BasisKind, type[FrozenStrictModel]] | None = None,
    ) -> None:
        supplied_root = Path(root)
        if _path_lexists(supplied_root) and supplied_root.is_symlink():
            raise AuthorityLedgerConfinementError("authority root must not be a symlink")
        resolved_root = supplied_root.resolve(strict=False)
        resolved_candidates = tuple(Path(candidate).resolve(strict=False) for candidate in candidate_roots)
        for candidate in resolved_candidates:
            if _paths_overlap(resolved_root, candidate):
                raise AuthorityLedgerConfinementError("authority and candidate roots must not overlap")
        self._root = resolved_root
        self._candidate_roots = resolved_candidates
        self._typed_basis_models = dict(_DEFAULT_TYPED_BASIS_MODELS)
        for kind, model_type in (typed_basis_models or {}).items():
            existing = self._typed_basis_models.get(kind)
            if existing is not None and existing is not model_type:
                raise AuthorityLedgerIntegrityError(
                    f"typed {kind.value} basis model cannot replace the built-in schema"
                )
            if not issubclass(model_type, FrozenStrictModel):
                raise AuthorityLedgerIntegrityError(f"typed {kind.value} basis model must be content addressed")
            self._typed_basis_models[kind] = model_type
        mkdir_durable(self._root)
        self._guard_path(self._root)

    @property
    def root(self) -> Path:
        """Return the canonical host-owned authority root."""

        return self._root

    def observe_basis(
        self,
        *,
        kind: BasisKind,
        artifact_id: str,
        content: bytes,
        producer: AuthorityPrincipal,
        producer_process_id: str,
        observed_by: AuthorityPrincipal,
        channel: str,
        operation_id: str,
        invocation_id: str,
        parent_origin_sha256s: tuple[str, ...] = (),
        operation_taint: tuple[TaintLabel, ...],
    ) -> StoredBasis:
        """Copy exact basis bytes into the host store and bind their observed origin."""

        if observed_by.kind not in _HOST_PRINCIPAL_KINDS:
            raise AuthorityLedgerIntegrityError("basis observation requires a host observer")
        if (
            kind is BasisKind.HUMAN_APPROVAL
            and producer.kind is AuthorityPrincipalKind.HUMAN
            and TaintLabel.HUMAN_AUTHORITY not in operation_taint
        ):
            raise AuthorityLedgerIntegrityError("host-observed human approval requires human_authority taint")
        self._validate_typed_basis_content(kind, content)
        parents = tuple(self._resolve_origin(digest).origin for digest in parent_origin_sha256s)
        artifact_sha256 = hashlib.sha256(content).hexdigest()
        reference = BasisReference(
            kind=kind,
            artifact_id=artifact_id,
            artifact_sha256=artifact_sha256,
        )
        origin = derive_origin_stamp(
            artifact_id=artifact_id,
            artifact_sha256=artifact_sha256,
            producer=producer,
            producer_process_id=producer_process_id,
            observed_by=observed_by,
            channel=channel,
            operation_id=operation_id,
            invocation_id=invocation_id,
            parents=parents,
            operation_taint=operation_taint,
        )
        content_path = self._basis_object_path(artifact_sha256)
        self._publish_exact(content_path, content)
        stored_origin = self._persist_origin(origin)
        claim = _BasisClaim(
            reference=reference,
            origin_sha256=origin.content_sha256,
        )
        self._publish_claim(
            self._basis_claim_path(reference),
            claim,
            label="basis logical identity",
        )
        return StoredBasis(
            reference=reference,
            content_path=content_path,
            origin=stored_origin.origin,
            origin_path=stored_origin.path,
        )

    def resolve_basis(self, reference: BasisReference) -> StoredBasis:
        """Resolve one exact typed basis and replay its complete origin closure."""

        claim_path = self._basis_claim_path(reference)
        if not _path_lexists(claim_path):
            raise AuthorityLedgerIntegrityError(
                f"{reference.kind.value} basis is not registered in the authority ledger"
            )
        claim = self._load_model(claim_path, _BasisClaim, label="basis claim")
        if claim.reference != reference:
            raise AuthorityLedgerIntegrityError("basis claim does not match the exact typed reference")
        content_path = self._basis_object_path(reference.artifact_sha256)
        content = self._read_exact_file(content_path, label="basis artifact")
        if hashlib.sha256(content).hexdigest() != reference.artifact_sha256:
            raise AuthorityLedgerIntegrityError("basis artifact hash does not match its reference")
        self._validate_typed_basis_content(reference.kind, content)
        stored_origin = self._resolve_origin(claim.origin_sha256)
        if (
            stored_origin.origin.artifact_id != reference.artifact_id
            or stored_origin.origin.artifact_sha256 != reference.artifact_sha256
        ):
            raise AuthorityLedgerIntegrityError("basis origin does not match the exact artifact identity")
        self._validate_origin_closure(stored_origin.origin)
        return StoredBasis(
            reference=reference,
            content_path=content_path,
            origin=stored_origin.origin,
            origin_path=stored_origin.path,
        )

    def basis_for_id(
        self,
        *,
        kind: BasisKind,
        artifact_id: str,
    ) -> StoredBasis | None:
        """Resolve one basis through its ledger-global typed logical identity."""

        reference_key = BasisReference(
            kind=kind,
            artifact_id=artifact_id,
            artifact_sha256="0" * 64,
        )
        claim_path = self._basis_claim_path(reference_key)
        if not _path_lexists(claim_path):
            return None
        claim = self._load_model(
            claim_path,
            _BasisClaim,
            label="basis claim",
        )
        if claim.reference.kind is not kind or claim.reference.artifact_id != artifact_id:
            raise AuthorityLedgerIntegrityError("basis claim does not match its typed logical identity")
        return self.resolve_basis(claim.reference)

    def observe_model_basis(
        self,
        *,
        kind: BasisKind,
        artifact_id: str,
        model: FrozenStrictModel,
        producer: AuthorityPrincipal,
        producer_process_id: str,
        observed_by: AuthorityPrincipal,
        channel: str,
        operation_id: str,
        invocation_id: str,
        parent_origin_sha256s: tuple[str, ...] = (),
        operation_taint: tuple[TaintLabel, ...],
    ) -> StoredBasis:
        """Observe canonical content-addressed model bytes under one configured typed basis kind."""
        return self.observe_basis(
            kind=kind,
            artifact_id=artifact_id,
            content=_canonical_model_bytes(model),
            producer=producer,
            producer_process_id=producer_process_id,
            observed_by=observed_by,
            channel=channel,
            operation_id=operation_id,
            invocation_id=invocation_id,
            parent_origin_sha256s=parent_origin_sha256s,
            operation_taint=operation_taint,
        )

    def resolve_model_basis[ModelT: FrozenStrictModel](
        self,
        reference: BasisReference,
        model_type: type[ModelT],
    ) -> tuple[StoredBasis, ModelT]:
        """Resolve one basis and return its canonical model only under the configured exact type."""
        configured = self._typed_basis_models.get(reference.kind)
        if configured is not model_type:
            raise AuthorityLedgerIntegrityError(
                f"{reference.kind.value} basis is not configured for {model_type.__name__}"
            )
        stored = self.resolve_basis(reference)
        model = self._load_model(
            stored.content_path,
            model_type,
            label=f"typed {reference.kind.value} basis",
        )
        return stored, model

    def validate_basis_closure(
        self,
        event: AuthorityEvent,
    ) -> tuple[StoredBasis, ...]:
        """Resolve every typed basis and recursively verify its monotone origin chain."""

        validated = AuthorityEvent.model_validate(event.model_dump(mode="json"))
        return tuple(self.resolve_basis(reference) for reference in validated.basis)

    def issue_authority_event(
        self,
        event: AuthorityEvent,
    ) -> StoredAuthorityEvent:
        """Persist one event only after exact basis and principal authority resolve."""

        validated = AuthorityEvent.model_validate(event.model_dump(mode="json"))
        self.validate_authority_event(validated)
        path = self._persist_model(
            validated,
            namespace="authority-event",
            logical_id=validated.event_id,
        )
        return StoredAuthorityEvent(event=validated, path=path)

    def validate_authority_event(
        self,
        event: AuthorityEvent,
    ) -> tuple[StoredBasis, ...]:
        """Replay exact basis closure and every action-specific authority policy."""

        validated = AuthorityEvent.model_validate(event.model_dump(mode="json"))
        basis = self.validate_basis_closure(validated)
        if validated.decision is AuthorityDecision.GRANTED and validated.action in _PROMOTION_ACTIONS:
            self._validate_promotion_basis(validated, basis)
        if validated.decision is AuthorityDecision.GRANTED and validated.action in _HUMAN_TRANSITION_ACTIONS:
            self._validate_human_transition_basis(validated, basis)
        return basis

    def _validate_human_transition_basis(
        self,
        event: AuthorityEvent,
        basis: tuple[StoredBasis, ...],
    ) -> None:
        """Require exact host-observed human approval for human-only transitions."""

        if any(
            item.reference.kind is BasisKind.HUMAN_APPROVAL
            and (
                approval := self._load_model(
                    item.content_path,
                    HumanAuthorityApproval,
                    label="human approval basis",
                )
            ).approved
            and approval.principal == event.principal
            and approval.action is event.action
            and approval.subject_id == event.subject_id
            and approval.subject_sha256 == event.subject_sha256
            and item.origin.producer == event.principal
            and item.origin.producer.kind is AuthorityPrincipalKind.HUMAN
            and item.origin.observed_by.kind in _HOST_PRINCIPAL_KINDS
            and TaintLabel.HUMAN_AUTHORITY in item.origin.taint_labels
            for item in basis
        ):
            return
        raise AuthorityLedgerIntegrityError("human transition requires matching host-observed human approval basis")

    def _validate_promotion_basis(
        self,
        event: AuthorityEvent,
        basis: tuple[StoredBasis, ...],
    ) -> None:
        """Enforce the causal evidence closure for every granted promotion."""

        from aec_bench.experimentation.governance.authority_validation.promotion import (
            validate_promotion_basis,
        )

        validate_promotion_basis(ledger=self, event=event, basis=basis)

    def resolve_authority_event(
        self,
        *,
        event_id: str,
        content_sha256: str,
    ) -> StoredAuthorityEvent:
        """Load one exact authority event through both its logical and content identities."""

        validate_sha256(content_sha256)
        claim = self._load_identity_claim(
            namespace="authority-event",
            logical_id=event_id,
        )
        if claim.target_content_sha256 != content_sha256:
            raise AuthorityLedgerIntegrityError("authority event claim does not match the requested content identity")
        path = self._model_object_path("authority-event", content_sha256)
        event = self._load_model(path, AuthorityEvent, label="authority event")
        if event.event_id != event_id or event.content_sha256 != content_sha256:
            raise AuthorityLedgerIntegrityError("authority event content does not match its exact logical identity")
        self.validate_authority_event(event)
        return StoredAuthorityEvent(event=event, path=path)

    def resolve_authority_event_by_content(
        self,
        content_sha256: str,
    ) -> StoredAuthorityEvent:
        """Resolve one event by content while still replaying its exclusive logical claim."""
        validate_sha256(content_sha256)
        path = self._model_object_path("authority-event", content_sha256)
        event = self._load_model(path, AuthorityEvent, label="authority event")
        return self.resolve_authority_event(
            event_id=event.event_id,
            content_sha256=content_sha256,
        )

    def authority_event_for_id(
        self,
        event_id: str,
    ) -> StoredAuthorityEvent | None:
        """Resolve one registered event by logical identity, or return None when absent."""
        claim_path = self._identity_claim_path("authority-event", event_id)
        if not _path_lexists(claim_path):
            return None
        claim = self._load_identity_claim(
            namespace="authority-event",
            logical_id=event_id,
        )
        return self.resolve_authority_event(
            event_id=event_id,
            content_sha256=claim.target_content_sha256,
        )

    def _persist_origin(self, origin: OriginStamp) -> StoredOrigin:
        validated = OriginStamp.model_validate(origin.model_dump(mode="json"))
        path = self._persist_model(
            validated,
            namespace="origin-stamp",
            logical_id=validated.artifact_id,
        )
        return StoredOrigin(origin=validated, path=path)

    def _resolve_origin(self, content_sha256: str) -> StoredOrigin:
        validate_sha256(content_sha256)
        path = self._model_object_path("origin-stamp", content_sha256)
        if not _path_lexists(path):
            raise AuthorityLedgerIntegrityError(f"origin artifact is missing for content identity {content_sha256}")
        origin = self._load_model(path, OriginStamp, label="origin artifact")
        if origin.content_sha256 != content_sha256:
            raise AuthorityLedgerIntegrityError("origin artifact content hash does not match its store path")
        return StoredOrigin(origin=origin, path=path)

    def _validate_origin_closure(self, origin: OriginStamp) -> None:
        completed: set[str] = set()
        active: set[str] = set()

        def visit(current: OriginStamp) -> None:
            if current.content_sha256 in completed:
                return
            if current.content_sha256 in active:
                raise AuthorityLedgerIntegrityError("origin closure contains a cycle")
            active.add(current.content_sha256)
            current_taint = set(current.taint_labels)
            for parent_sha256 in current.parent_origin_sha256s:
                parent = self._resolve_origin(parent_sha256).origin
                if not set(parent.taint_labels).issubset(current_taint):
                    raise AuthorityLedgerIntegrityError("origin closure removes inherited taint labels")
                visit(parent)
            active.remove(current.content_sha256)
            completed.add(current.content_sha256)

        visit(origin)

    def _persist_model(
        self,
        model: ContentAddressedModel,
        *,
        namespace: str,
        logical_id: str,
    ) -> Path:
        path = self._model_object_path(namespace, model.content_sha256)
        self._publish_exact(path, _canonical_model_bytes(model))
        claim = _IdentityClaim(
            namespace=namespace,
            logical_id=logical_id,
            target_content_sha256=model.content_sha256,
        )
        self._publish_claim(
            self._identity_claim_path(namespace, logical_id),
            claim,
            label=f"{namespace} logical identity",
        )
        return path

    def _load_identity_claim(
        self,
        *,
        namespace: str,
        logical_id: str,
    ) -> _IdentityClaim:
        path = self._identity_claim_path(namespace, logical_id)
        if not _path_lexists(path):
            raise AuthorityLedgerIntegrityError(f"{namespace} logical identity is not registered")
        claim = self._load_model(path, _IdentityClaim, label=f"{namespace} identity claim")
        if claim.namespace != namespace or claim.logical_id != logical_id:
            raise AuthorityLedgerIntegrityError(f"{namespace} identity claim does not match its lookup key")
        return claim

    def _validate_typed_basis_content(
        self,
        kind: BasisKind,
        content: bytes,
    ) -> None:
        model_type = self._typed_basis_models.get(kind)
        if model_type is None:
            if kind in _REQUIRED_TYPED_BASIS_KINDS:
                raise AuthorityLedgerIntegrityError(f"typed {kind.value} basis model is not configured")
            return
        try:
            model = model_type.model_validate_json(content)
        except ValueError as error:
            raise AuthorityLedgerIntegrityError(
                f"typed {kind.value} basis does not contain the required artifact"
            ) from error
        if _canonical_model_bytes(model) != content:
            raise AuthorityLedgerIntegrityError(f"typed {kind.value} basis artifact is not canonically serialized")

    def _publish_claim(
        self,
        path: Path,
        claim: ContentAddressedModel,
        *,
        label: str,
    ) -> None:
        expected = _canonical_model_bytes(claim)
        if _path_lexists(path):
            existing = self._load_model(path, type(claim), label=label)
            if existing != claim:
                raise AuthorityLedgerCollisionError(f"{label} is already bound to different content")
            return
        try:
            self._publish_exact(path, expected)
        except AuthorityLedgerCollisionError:
            existing = self._load_model(path, type(claim), label=label)
            if existing != claim:
                raise AuthorityLedgerCollisionError(f"{label} is already bound to different content") from None

    def _publish_exact(self, path: Path, content: bytes) -> None:
        self._guard_path(path)
        mkdir_durable(path.parent)
        self._guard_path(path)
        if _path_lexists(path):
            existing = self._read_exact_file(path, label="content-addressed artifact")
            if existing != content:
                raise AuthorityLedgerCollisionError("content-addressed path contains different bytes")
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
                existing = self._read_exact_file(
                    path,
                    label="content-addressed artifact",
                )
                if existing != content:
                    raise AuthorityLedgerCollisionError("content-addressed path contains different bytes") from None
            fsync_directory(path.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_exact_file(self, path: Path, *, label: str) -> bytes:
        self._guard_path(path)
        if not _path_lexists(path):
            raise AuthorityLedgerIntegrityError(f"{label} is missing")
        if path.is_symlink() or not path.is_file():
            raise AuthorityLedgerConfinementError(f"{label} must be a regular non-symlink file")
        try:
            return path.read_bytes()
        except OSError as error:
            raise AuthorityLedgerIntegrityError(f"{label} is unreadable") from error

    def _load_model[ModelT: FrozenStrictModel](
        self,
        path: Path,
        model_type: type[ModelT],
        *,
        label: str,
    ) -> ModelT:
        encoded = self._read_exact_file(path, label=label)
        try:
            model = model_type.model_validate_json(encoded)
        except ValueError as error:
            raise AuthorityLedgerIntegrityError(f"{label} is corrupt or has the wrong typed schema") from error
        if _canonical_model_bytes(model) != encoded:
            raise AuthorityLedgerIntegrityError(f"{label} is not canonically serialized")
        return model

    def _guard_path(self, path: Path) -> None:
        absolute = Path(os.path.abspath(path))
        if not absolute.is_relative_to(self._root):
            raise AuthorityLedgerConfinementError("authority artifact path escapes the configured root")
        if any(_paths_overlap(absolute, candidate) for candidate in self._candidate_roots):
            raise AuthorityLedgerConfinementError("authority artifact path overlaps a candidate root")
        cursor = self._root
        if _path_lexists(cursor) and cursor.is_symlink():
            raise AuthorityLedgerConfinementError("authority root must not be a symlink")
        for part in absolute.relative_to(self._root).parts:
            cursor /= part
            if _path_lexists(cursor) and cursor.is_symlink():
                raise AuthorityLedgerConfinementError("authority artifact path contains a symlink")

    def _model_object_path(self, namespace: str, content_sha256: str) -> Path:
        return self._root / "model-objects" / namespace / content_sha256 / "artifact.json"

    def _identity_claim_path(self, namespace: str, logical_id: str) -> Path:
        return self._root / "model-claims" / namespace / hashlib.sha256(logical_id.encode()).hexdigest() / "claim.json"

    def _basis_object_path(self, artifact_sha256: str) -> Path:
        return self._root / "basis-objects" / artifact_sha256 / "artifact.bin"

    def _basis_claim_path(self, reference: BasisReference) -> Path:
        logical_key = json.dumps(
            {
                "artifact_id": reference.artifact_id,
                "kind": reference.kind.value,
            },
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        return (
            self._root / "basis-claims" / reference.kind.value / hashlib.sha256(logical_key).hexdigest() / "claim.json"
        )


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


def _path_lexists(path: Path) -> bool:
    return os.path.lexists(path)


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left.is_relative_to(right) or right.is_relative_to(left)
