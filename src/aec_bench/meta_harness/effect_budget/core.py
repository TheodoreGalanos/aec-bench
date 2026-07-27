# ABOUTME: Implements phase-neutral durable reserve-before-effect storage, locking, and replay.
# ABOUTME: Delegates experiment policy while owning one canonical fail-closed evidence lifecycle.

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import TypeAdapter

from aec_bench.contracts.harness_kernel import (
    ContentAddressedModel,
)
from aec_bench.meta_harness.effect_budget.errors import (
    EffectBudgetCollisionError,
    EffectBudgetConfinementError,
    EffectBudgetExceededError,
    EffectBudgetIncompleteError,
    EffectBudgetIntegrityError,
)
from aec_bench.meta_harness.immutable_artifact_store import (
    EvidenceRepository,
    ImmutableArtifactCollisionError,
    ImmutableArtifactConfinementError,
    ImmutableArtifactIntegrityError,
)


@dataclass(frozen=True, slots=True)
class EffectBudgetErrorTypes:
    """Concrete error categories emitted by one ledger specialization."""

    confinement: type[EffectBudgetConfinementError]
    collision: type[EffectBudgetCollisionError]
    integrity: type[EffectBudgetIntegrityError]
    incomplete: type[EffectBudgetIncompleteError]
    exceeded: type[EffectBudgetExceededError]


@dataclass(frozen=True, slots=True)
class EffectBudgetLayout:
    """Stable evidence paths and vocabulary for one ledger specialization."""

    namespace: str = "effect"
    lifecycle_noun: str = "run"
    lock_filename: str = ".effect-budget.lock"
    binding_filename: str = "binding.json"
    operations_directory: str = "operations"
    reservation_filename: str = "reservation.json"
    terminal_filename: str = "terminal.json"
    extra_root_entries: frozenset[str] = frozenset()

    @property
    def root_label(self) -> str:
        """Return the specialization's evidence-root label."""

        return f"{self.namespace} budget root"

    @property
    def binding_label(self) -> str:
        """Return the specialization's immutable-binding label."""

        return f"{self.namespace} {self.lifecycle_noun} budget binding"

    @property
    def operations_label(self) -> str:
        """Return the specialization's operation-collection label."""

        return f"{self.namespace} operations root"

    @property
    def operation_directory_label(self) -> str:
        """Return the specialization's operation-directory label."""

        return f"{self.namespace} operation directory"

    @property
    def reservation_label(self) -> str:
        """Return the specialization's reservation label."""

        return f"{self.namespace} budget reservation"

    @property
    def terminal_label(self) -> str:
        """Return the specialization's terminal-receipt label."""

        return f"{self.namespace} budget terminal receipt"

    @property
    def lock_label(self) -> str:
        """Return the specialization's lock label."""

        return f"{self.namespace} budget lock"


@dataclass(frozen=True)
class EffectOperationState[
    ReservationT: ContentAddressedModel,
    TerminalT: ContentAddressedModel,
]:
    """Verified immutable reservation and optional terminal for one effect."""

    reservation: ReservationT
    terminal: TerminalT | None


_DEFAULT_ERRORS = EffectBudgetErrorTypes(
    confinement=EffectBudgetConfinementError,
    collision=EffectBudgetCollisionError,
    integrity=EffectBudgetIntegrityError,
    incomplete=EffectBudgetIncompleteError,
    exceeded=EffectBudgetExceededError,
)


class EffectBudgetLedger[
    BindingT: ContentAddressedModel,
    ReservationT: ContentAddressedModel,
    TerminalT: ContentAddressedModel,
](ABC):
    """Canonical durable ledger mechanics shared by effect-budget policies."""

    def __init__(
        self,
        *,
        root: Path,
        proposed_binding: BindingT,
        binding_type: type[BindingT],
        reservation_type: type[ReservationT],
        terminal_type: type[TerminalT],
        candidate_roots: tuple[Path, ...] = (),
        now: Callable[[], datetime] | None = None,
        layout: EffectBudgetLayout | None = None,
        error_types: EffectBudgetErrorTypes | None = None,
    ) -> None:
        self._effect_layout = layout or EffectBudgetLayout()
        self._effect_errors = error_types or _DEFAULT_ERRORS
        self._effect_binding_type = binding_type
        self._effect_reservation_type = reservation_type
        self._effect_terminal_type = terminal_type
        self._effect_now = now or _utc_now
        self._effect_repository = self._open_effect_repository(
            Path(root),
            candidate_roots=candidate_roots,
        )
        self._effect_root = self._effect_repository.root
        self._effect_lock_path = self._effect_root / self._effect_layout.lock_filename
        self._effect_owned_reservation_sha256s: set[str] = set()

        with self._effect_locked():
            binding = self._publish_effect_model(
                path=self._effect_root / self._effect_layout.binding_filename,
                proposed=proposed_binding,
                label=self._effect_layout.binding_label,
                allow_existing_different=True,
            )
            self._validate_effect_binding(binding)
            self._effect_binding = binding

    @property
    def root(self) -> Path:
        """Return the canonical confined effect-budget evidence root."""

        return self._effect_root

    @property
    def effect_binding(self) -> BindingT:
        """Return the exact immutable root binding selected by the ledger."""

        return self._effect_binding

    def _reserve_effect(
        self,
        *,
        operation_id: str,
        build_reservation: Callable[
            [dict[str, EffectOperationState[ReservationT, TerminalT]]],
            ReservationT,
        ],
        breach_reasons: Callable[
            [dict[str, EffectOperationState[ReservationT, TerminalT]]],
            tuple[str, ...],
        ],
    ) -> ReservationT:
        """Publish one exact reservation before the represented effect may begin."""

        self._effect_operation_key(operation_id)
        with self._effect_locked():
            states = self._load_effect_states()
            self._raise_for_foreign_incomplete_effects(states)
            self._raise_for_reused_operation_id(
                operation_id=operation_id,
                states=states,
            )
            reservation = build_reservation(states)
            if self._effect_operation_id(reservation) != operation_id:
                raise self._effect_errors.integrity(
                    "effect reservation operation identity differs from its request",
                )
            proposed_states = {
                **states,
                operation_id: EffectOperationState(
                    reservation=reservation,
                    terminal=None,
                ),
            }
            self._raise_for_effect_breaches(
                breach_reasons(proposed_states),
            )
            selected = self._publish_effect_model(
                path=self._effect_operation_root(operation_id) / self._effect_layout.reservation_filename,
                proposed=reservation,
                label=self._effect_layout.reservation_label,
            )
            if selected != reservation:
                raise self._effect_errors.collision(
                    f"{self._effect_layout.lifecycle_noun} operation {operation_id!r} selected a different reservation",
                )
            self._effect_owned_reservation_sha256s.add(
                reservation.content_sha256,
            )
            return reservation

    def _commit_effect(
        self,
        *,
        reservation_sha256: str,
        build_terminal: Callable[
            [EffectOperationState[ReservationT, TerminalT]],
            TerminalT,
        ],
        terminal_matches: Callable[[TerminalT], bool],
        breach_reasons: Callable[
            [dict[str, EffectOperationState[ReservationT, TerminalT]]],
            tuple[str, ...],
        ],
    ) -> TerminalT:
        """Publish terminal evidence for one exact reservation and replay idempotently."""

        with self._effect_locked():
            states = self._load_effect_states()
            state = self._state_for_reservation_sha256(
                reservation_sha256=reservation_sha256,
                states=states,
            )
            if state.terminal is not None:
                if terminal_matches(state.terminal):
                    self._raise_for_effect_breaches(
                        breach_reasons(states),
                    )
                    return state.terminal
                raise self._effect_errors.collision(
                    f"{self._effect_layout.lifecycle_noun} operation "
                    f"{self._effect_operation_id(state.reservation)!r} "
                    "already has a different terminal receipt",
                )
            terminal = build_terminal(state)
            self._validate_effect_terminal(
                reservation=state.reservation,
                terminal=terminal,
            )
            operation_id = self._effect_operation_id(state.reservation)
            selected = self._publish_effect_model(
                path=self._effect_operation_root(operation_id) / self._effect_layout.terminal_filename,
                proposed=terminal,
                label=self._effect_layout.terminal_label,
            )
            if selected != terminal:
                raise self._effect_errors.collision(
                    f"{self._effect_layout.lifecycle_noun} operation "
                    f"{operation_id!r} selected a different terminal receipt",
                )
            completed_states = {
                **states,
                operation_id: EffectOperationState(
                    reservation=state.reservation,
                    terminal=terminal,
                ),
            }
            self._raise_for_effect_breaches(
                breach_reasons(completed_states),
            )
            return terminal

    def _read_effect_states(
        self,
    ) -> dict[str, EffectOperationState[ReservationT, TerminalT]]:
        """Return a verified snapshot of every persisted operation."""

        with self._effect_locked():
            return self._load_effect_states()

    def _read_effect_operation(
        self,
        operation_id: str,
    ) -> EffectOperationState[ReservationT, TerminalT] | None:
        """Return one verified persisted operation by logical identity."""

        self._effect_operation_key(operation_id)
        with self._effect_locked():
            return self._load_effect_states().get(operation_id)

    @contextmanager
    def _effect_transaction(self) -> Iterator[None]:
        """Hold the ledger lock across one specialization-owned transaction."""

        with self._effect_locked():
            yield

    def _load_effect_states(
        self,
    ) -> dict[str, EffectOperationState[ReservationT, TerminalT]]:
        self._validate_effect_root()
        operations_root = self._effect_root / self._effect_layout.operations_directory
        if not self._effect_path_exists(
            path=operations_root,
            label=self._effect_layout.operations_label,
        ):
            return {}
        self._require_effect_directory(
            path=operations_root,
            label=self._effect_layout.operations_label,
        )
        states: dict[str, EffectOperationState[ReservationT, TerminalT]] = {}
        for operation_root in sorted(
            operations_root.iterdir(),
            key=lambda path: path.name,
        ):
            state = self._load_effect_operation_state(operation_root)
            operation_id = self._effect_operation_id(state.reservation)
            if operation_id in states:
                raise self._effect_errors.collision(
                    f"duplicate {self._effect_layout.namespace} operation identity in budget ledger",
                )
            states[operation_id] = state
        self._validate_effect_states(states)
        return states

    def _publish_effect_extension_model[
        ModelT: ContentAddressedModel,
    ](
        self,
        *,
        relative_path: str,
        proposed: ModelT,
        label: str,
    ) -> ModelT:
        """Publish specialization evidence beneath the same confined ledger root."""

        return self._publish_effect_model(
            path=self._effect_root / relative_path,
            proposed=proposed,
            label=label,
        )

    def _load_effect_extension_model[
        ModelT: ContentAddressedModel,
    ](
        self,
        *,
        relative_path: str,
        model_type: type[ModelT],
        label: str,
    ) -> ModelT:
        """Load specialization evidence beneath the same confined ledger root."""

        return self._load_effect_model(
            path=self._effect_root / relative_path,
            model_type=model_type,
            label=label,
        )

    def _effect_extension_exists(
        self,
        *,
        relative_path: str,
        label: str,
    ) -> bool:
        """Return whether specialization evidence exists at one confined path."""

        return self._effect_path_exists(
            path=self._effect_root / relative_path,
            label=label,
        )

    def _effect_observed_now(self) -> datetime:
        observed = self._effect_now()
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise self._effect_errors.integrity(
                f"{self._effect_layout.namespace} budget clock must return a timezone-aware timestamp",
            )
        return observed

    def _effect_elapsed_wall_seconds(self, *, opened_at: datetime) -> float:
        return max(
            0.0,
            (self._effect_observed_now() - opened_at).total_seconds(),
        )

    def _validate_effect_root(self) -> None:
        allowed_root_entries = {
            self._effect_layout.lock_filename,
            self._effect_layout.binding_filename,
            self._effect_layout.operations_directory,
            *self._effect_layout.extra_root_entries,
        }
        observed_root_entries = {item.name for item in self._effect_root.iterdir()}
        if not observed_root_entries.issubset(allowed_root_entries):
            raise self._effect_errors.integrity(
                f"{self._effect_layout.root_label} contains unrecognized evidence",
            )
        persisted_binding = self._load_effect_model(
            path=self._effect_root / self._effect_layout.binding_filename,
            model_type=self._effect_binding_type,
            label=self._effect_layout.binding_label,
        )
        if persisted_binding != self._effect_binding:
            raise self._effect_errors.integrity(
                f"{self._effect_layout.binding_label} changed after ledger initialization",
            )

    def _load_effect_operation_state(
        self,
        operation_root: Path,
    ) -> EffectOperationState[ReservationT, TerminalT]:
        self._require_effect_directory(
            path=operation_root,
            label=self._effect_layout.operation_directory_label,
        )
        reservation_path = operation_root / self._effect_layout.reservation_filename
        terminal_path = operation_root / self._effect_layout.terminal_filename
        allowed = {
            self._effect_layout.reservation_filename,
            self._effect_layout.terminal_filename,
        }
        if not {item.name for item in operation_root.iterdir()}.issubset(allowed):
            raise self._effect_errors.integrity(
                f"{self._effect_layout.operation_directory_label} contains unrecognized evidence",
            )
        reservation = self._load_effect_model(
            path=reservation_path,
            model_type=self._effect_reservation_type,
            label=self._effect_layout.reservation_label,
        )
        operation_id = self._effect_operation_id(reservation)
        if operation_root.name != self._effect_operation_key(operation_id):
            raise self._effect_errors.integrity(
                f"{self._effect_layout.namespace} reservation is stored below the wrong operation identity",
            )
        self._validate_effect_reservation(reservation)
        terminal = self._load_effect_terminal(
            reservation=reservation,
            terminal_path=terminal_path,
        )
        return EffectOperationState(
            reservation=reservation,
            terminal=terminal,
        )

    def _load_effect_terminal(
        self,
        *,
        reservation: ReservationT,
        terminal_path: Path,
    ) -> TerminalT | None:
        if not self._effect_path_exists(
            path=terminal_path,
            label=self._effect_layout.terminal_label,
        ):
            return None
        terminal = self._load_effect_model(
            path=terminal_path,
            model_type=self._effect_terminal_type,
            label=self._effect_layout.terminal_label,
        )
        self._validate_effect_terminal(
            reservation=reservation,
            terminal=terminal,
        )
        return terminal

    def _raise_for_foreign_incomplete_effects(
        self,
        states: dict[str, EffectOperationState[ReservationT, TerminalT]],
    ) -> None:
        incomplete = tuple(
            self._effect_operation_id(state.reservation)
            for state in states.values()
            if state.terminal is None and state.reservation.content_sha256 not in self._effect_owned_reservation_sha256s
        )
        if incomplete:
            raise self._effect_errors.incomplete(
                f"{self._effect_layout.lifecycle_noun} has incomplete prior "
                "reservations and cannot begin another effect",
            )

    def _raise_for_reused_operation_id(
        self,
        *,
        operation_id: str,
        states: dict[str, EffectOperationState[ReservationT, TerminalT]],
    ) -> None:
        existing = states.get(operation_id)
        if existing is None:
            return
        if existing.terminal is None:
            raise self._effect_errors.incomplete(
                f"{self._effect_layout.lifecycle_noun} operation "
                f"{operation_id!r} is already started without terminal evidence",
            )
        raise self._effect_errors.collision(
            f"{self._effect_layout.lifecycle_noun} operation {operation_id!r} is already terminal and cannot be reused",
        )

    def _state_for_reservation_sha256(
        self,
        *,
        reservation_sha256: str,
        states: dict[str, EffectOperationState[ReservationT, TerminalT]],
    ) -> EffectOperationState[ReservationT, TerminalT]:
        matches = tuple(state for state in states.values() if state.reservation.content_sha256 == reservation_sha256)
        if len(matches) != 1:
            raise self._effect_errors.integrity(
                "cannot commit unknown reservation identity",
            )
        return matches[0]

    def _raise_for_effect_breaches(self, reasons: tuple[str, ...]) -> None:
        if reasons:
            raise self._effect_errors.exceeded(reasons[0])

    def _effect_operation_root(self, operation_id: str) -> Path:
        return self._effect_root / self._effect_layout.operations_directory / self._effect_operation_key(operation_id)

    def _effect_operation_key(self, operation_id: str) -> str:
        if not operation_id or not operation_id.strip():
            raise self._effect_errors.integrity(
                f"{self._effect_layout.lifecycle_noun} operation id must be non-empty",
            )
        return hashlib.sha256(operation_id.encode("utf-8")).hexdigest()

    def _open_effect_repository(
        self,
        root: Path,
        *,
        candidate_roots: tuple[Path, ...],
    ) -> EvidenceRepository:
        with self._translate_effect_repository_errors(
            label=self._effect_layout.root_label,
        ):
            return EvidenceRepository(
                root,
                disjoint_roots=candidate_roots,
            )
        raise AssertionError("unreachable")

    def _publish_effect_model[
        ModelT: ContentAddressedModel,
    ](
        self,
        *,
        path: Path,
        proposed: ModelT,
        label: str,
        allow_existing_different: bool = False,
    ) -> ModelT:
        relative_path = self._effect_relative_path(path=path, label=label)
        adapter = TypeAdapter(type(proposed))
        with self._translate_effect_repository_errors(label=label):
            if self._effect_repository.exists(relative_path):
                selected = self._effect_repository.load_canonical_model(
                    relative_path,
                    adapter,
                )
            else:
                try:
                    selected = self._effect_repository.publish_canonical_model(
                        relative_path,
                        proposed,
                        adapter,
                    ).model
                except ImmutableArtifactCollisionError:
                    if not allow_existing_different or not self._effect_repository.exists(relative_path):
                        raise
                    selected = self._effect_repository.load_canonical_model(
                        relative_path,
                        adapter,
                    )
        if selected != proposed and not allow_existing_different:
            raise self._effect_errors.collision(
                f"{label} already contains different immutable content",
            )
        return selected

    def _load_effect_model[
        ModelT: ContentAddressedModel,
    ](
        self,
        *,
        path: Path,
        model_type: type[ModelT],
        label: str,
    ) -> ModelT:
        relative_path = self._effect_relative_path(path=path, label=label)
        with self._translate_effect_repository_errors(label=label):
            return self._effect_repository.load_canonical_model(
                relative_path,
                TypeAdapter(model_type),
            )
        raise AssertionError("unreachable")

    def _effect_path_exists(
        self,
        *,
        path: Path,
        label: str,
    ) -> bool:
        relative_path = self._effect_relative_path(path=path, label=label)
        with self._translate_effect_repository_errors(label=label):
            return self._effect_repository.exists(relative_path)
        raise AssertionError("unreachable")

    def _effect_relative_path(self, *, path: Path, label: str) -> str:
        with self._translate_effect_repository_errors(label=label):
            return self._effect_repository.relative_path(path)
        raise AssertionError("unreachable")

    def _require_effect_directory(self, *, path: Path, label: str) -> Path:
        self._effect_relative_path(path=path, label=label)
        try:
            details = path.stat(follow_symlinks=False)
        except FileNotFoundError as error:
            raise self._effect_errors.integrity(f"{label} is missing") from error
        if not stat.S_ISDIR(details.st_mode):
            raise self._effect_errors.integrity(
                f"{label} must be a directory",
            )
        return path

    @contextmanager
    def _translate_effect_repository_errors(
        self,
        *,
        label: str,
    ) -> Iterator[None]:
        try:
            yield
        except ImmutableArtifactCollisionError as error:
            raise self._effect_errors.collision(
                f"{label} already contains different immutable content",
            ) from error
        except ImmutableArtifactConfinementError as error:
            detail = str(error).replace("symbolic-link", "symlink")
            raise self._effect_errors.confinement(
                f"{label}: {detail}",
            ) from error
        except ImmutableArtifactIntegrityError as error:
            raise self._effect_errors.integrity(
                f"{label} could not be loaded as canonical evidence: {error}",
            ) from error

    @contextmanager
    def _effect_locked(self) -> Iterator[None]:
        self._effect_relative_path(
            path=self._effect_lock_path,
            label=self._effect_layout.lock_label,
        )
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self._effect_lock_path, flags, 0o600)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise self._effect_errors.confinement(
                    f"{self._effect_layout.lock_label} must be a regular file",
                )
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    @abstractmethod
    def _validate_effect_binding(self, binding: BindingT) -> None:
        """Validate a selected immutable binding against specialization input."""

    @abstractmethod
    def _effect_operation_id(self, reservation: ReservationT) -> str:
        """Return the logical operation identity from a reservation."""

    @abstractmethod
    def _validate_effect_reservation(self, reservation: ReservationT) -> None:
        """Validate a replayed reservation against specialization state."""

    @abstractmethod
    def _validate_effect_terminal(
        self,
        *,
        reservation: ReservationT,
        terminal: TerminalT,
    ) -> None:
        """Validate a replayed terminal against its exact reservation."""

    @abstractmethod
    def _validate_effect_states(
        self,
        states: dict[str, EffectOperationState[ReservationT, TerminalT]],
    ) -> None:
        """Validate cross-operation invariants after canonical replay."""


def _utc_now() -> datetime:
    return datetime.now(UTC)
