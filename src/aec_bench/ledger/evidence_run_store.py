# ABOUTME: Persists resolved run specifications and plans in one local evidence run directory.
# ABOUTME: Uses the ledger's confined locks and durable replacement primitives before execution starts.

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal, Self, TypeVar

from pydantic import model_validator

from aec_bench.contracts.identity import EntityIdentity
from aec_bench.contracts.resolved_run import ResolvedRunSpec
from aec_bench.contracts.run_plan import RunPlan
from aec_bench.contracts.validators import FrozenStrictModel
from aec_bench.ledger.durability import mkdir_durable, replace_file_bytes_durable
from aec_bench.ledger.local_lock import exclusive_local_file_lock


class EvidenceRunStoreError(RuntimeError):
    """Base error for one evidence run store operation."""


class EvidenceRunStoreConflict(EvidenceRunStoreError):
    """Raised when a durable identity already has different content."""


class EvidenceRunStoreIncomplete(EvidenceRunStoreError):
    """Raised when a run directory does not contain its required records."""


class EvidenceRunStoreStateError(EvidenceRunStoreError):
    """Raised when an operation is not valid for the run's operational state."""


class EvidenceRunState(FrozenStrictModel):
    """Mutable operational state for one run; the spec and plan remain separate files."""

    schema_version: Literal[1] = 1
    state: Literal["draft", "ready", "started", "closed"]
    run_identity: EntityIdentity
    plan_identity: EntityIdentity | None = None
    started_at: datetime | None = None
    closed_at: datetime | None = None

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        for name, value in (("started_at", self.started_at), ("closed_at", self.closed_at)):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"evidence run {name} must include a timezone")
        if self.state in {"started", "closed"} and self.started_at is None:
            raise ValueError("started evidence run state must include started_at")
        if self.state in {"ready", "started", "closed"} and self.plan_identity is None:
            raise ValueError("ready evidence run state must include plan identity")
        if self.state == "closed" and self.closed_at is None:
            raise ValueError("closed evidence run state must include closed_at")
        if self.state in {"draft", "ready"} and (self.started_at is not None or self.closed_at is not None):
            raise ValueError("unstarted evidence run state must not include operational timestamps")
        if self.closed_at is not None and self.started_at is not None and self.closed_at < self.started_at:
            raise ValueError("evidence run closed_at must not precede started_at")
        return self


@dataclass(frozen=True, slots=True)
class StoredEvidenceRun:
    """Strictly read records for one evidence run."""

    spec: ResolvedRunSpec
    plan: RunPlan | None
    state: EvidenceRunState


class EvidenceRunStore:
    """Store requested run state below one trusted local root."""

    _SPEC_FILE = "resolved-run-spec.json"
    _PLAN_FILE = "run-plan.json"
    _STATE_FILE = "state.json"

    def __init__(self, root: Path, *, read_only: bool = False) -> None:
        selected = Path(root).expanduser().absolute()
        self.read_only = read_only
        if selected.exists() and selected.is_symlink():
            raise EvidenceRunStoreError("evidence run store root must not be a symbolic link")
        if not read_only:
            try:
                mkdir_durable(selected, created_mode=0o700)
            except OSError as cause:
                raise EvidenceRunStoreError(f"evidence run store root cannot be created: {cause}") from cause
        if selected.is_symlink() or not selected.is_dir():
            raise EvidenceRunStoreError("evidence run store root must be a regular directory")
        self.root = selected

    @classmethod
    def open_read_only(cls, root: Path) -> EvidenceRunStore:
        """Open an existing run store without creating roots or lock files."""

        return cls(root, read_only=True)

    def run_directory(self, identity: EntityIdentity) -> Path:
        """Return the safe key-plus-full-UUID directory for one run identity."""

        locator = self._locator(identity)
        directory = self.root / locator
        if not directory.is_relative_to(self.root):
            raise EvidenceRunStoreError("evidence run directory escapes its trusted root")
        return directory

    def create_run(self, spec: ResolvedRunSpec) -> StoredEvidenceRun:
        """Durably publish a resolved specification before a plan is written."""

        self._require_writable()
        directory = self.run_directory(spec.run_identity)
        with self._lock(spec.run_identity):
            self._ensure_run_directory(directory)
            existing = self._read_optional_model(directory / self._SPEC_FILE, ResolvedRunSpec)
            if existing is not None and existing != spec:
                raise EvidenceRunStoreConflict("run identity already has a different resolved specification")
            if existing is None:
                self._write_model(directory, self._SPEC_FILE, spec)
            state = self._read_optional_model(directory / self._STATE_FILE, EvidenceRunState)
            if state is None:
                if self._read_optional_model(directory / self._PLAN_FILE, RunPlan) is not None:
                    raise EvidenceRunStoreIncomplete("evidence run with a plan is missing operational state")
                self._write_model(
                    directory,
                    self._STATE_FILE,
                    EvidenceRunState(state="draft", run_identity=spec.run_identity),
                )
            return self._read_run_unlocked(spec.run_identity)

    def write_draft_plan(self, run_identity: EntityIdentity, plan: RunPlan) -> RunPlan:
        """Publish a draft plan, replacing it only with a higher plan identity version."""

        self._require_writable()
        self._validate_plan_identity(run_identity, plan)
        if plan.state != "draft":
            raise EvidenceRunStoreStateError("draft plan writes require plan state 'draft'")
        directory = self.run_directory(run_identity)
        with self._lock(run_identity):
            spec, state = self._require_spec_and_state(directory, run_identity)
            self._validate_plan_against_spec(plan, spec, require_complete=False)
            if state.state in {"started", "closed"}:
                raise EvidenceRunStoreStateError("started evidence run plans cannot be edited")
            current = self._read_optional_model(directory / self._PLAN_FILE, RunPlan)
            if current is not None:
                self._check_plan_revision(current, plan)
            self._write_model_if_changed(directory, self._PLAN_FILE, current, plan)
            draft_state = EvidenceRunState(
                state="draft",
                run_identity=run_identity,
                plan_identity=plan.plan_identity,
            )
            self._write_model_if_changed(directory, self._STATE_FILE, state, draft_state)
            return plan

    def promote_ready_plan(self, run_identity: EntityIdentity, plan: RunPlan) -> RunPlan:
        """Publish one validated ready plan and move the operational state to ready."""

        self._require_writable()
        self._validate_plan_identity(run_identity, plan)
        if plan.state != "ready":
            raise EvidenceRunStoreStateError("ready promotion requires plan state 'ready'")
        directory = self.run_directory(run_identity)
        with self._lock(run_identity):
            spec, state = self._require_spec_and_state(directory, run_identity)
            self._validate_plan_against_spec(plan, spec, require_complete=True)
            if state.state in {"started", "closed"}:
                raise EvidenceRunStoreStateError("started evidence run plans cannot be replaced")
            current = self._read_optional_model(directory / self._PLAN_FILE, RunPlan)
            if current is None:
                raise EvidenceRunStoreIncomplete("ready promotion requires a persisted draft plan")
            if (
                current.plan_identity.id != plan.plan_identity.id
                or current.plan_identity.key != plan.plan_identity.key
                or current.plan_identity.version != plan.plan_identity.version
            ):
                raise EvidenceRunStoreConflict("ready plan identity does not match the persisted draft")
            expected_ready = current.model_copy(update={"state": "ready"})
            if plan != expected_ready:
                raise EvidenceRunStoreConflict("ready plan content must match the persisted draft")
            self._write_model_if_changed(directory, self._PLAN_FILE, current, plan)
            ready_state = EvidenceRunState(
                state="ready",
                run_identity=run_identity,
                plan_identity=plan.plan_identity,
            )
            self._write_model_if_changed(directory, self._STATE_FILE, state, ready_state)
            return plan

    def start_run(self, run_identity: EntityIdentity, *, started_at: datetime) -> StoredEvidenceRun:
        """Lock the spec and ready plan, then record the stable started condition."""

        _require_aware(started_at, "started_at")
        directory = self.run_directory(run_identity)
        self._require_writable()
        with self._lock(run_identity):
            spec, state = self._require_spec_and_state(directory, run_identity)
            plan = self._read_optional_model(directory / self._PLAN_FILE, RunPlan)
            if plan is None or plan.state != "ready":
                raise EvidenceRunStoreStateError("run must have a persisted ready plan before start")
            self._validate_plan_against_spec(plan, spec, require_complete=True)
            if state.plan_identity != plan.plan_identity:
                raise EvidenceRunStoreConflict("operational state plan identity does not match the persisted plan")
            if state.state == "started":
                if state.started_at != started_at:
                    raise EvidenceRunStoreConflict("started run identity already has a different started_at")
                return StoredEvidenceRun(spec, plan, state)
            if state.state == "closed":
                raise EvidenceRunStoreStateError("closed evidence runs cannot be started")
            if state.state != "ready" or state.plan_identity != plan.plan_identity:
                raise EvidenceRunStoreStateError("run must be promoted to the recorded ready plan before start")
            if started_at < plan.created_at:
                raise ValueError("evidence run started_at must not precede plan creation")
            started = EvidenceRunState(
                state="started",
                run_identity=run_identity,
                plan_identity=plan.plan_identity,
                started_at=started_at,
            )
            self._write_model(directory, self._STATE_FILE, started)
            return StoredEvidenceRun(spec, plan, started)

    def close_run(self, run_identity: EntityIdentity, *, closed_at: datetime) -> StoredEvidenceRun:
        """Move operational state from started to closed without rewriting spec or plan."""

        _require_aware(closed_at, "closed_at")
        directory = self.run_directory(run_identity)
        self._require_writable()
        with self._lock(run_identity):
            spec, state = self._require_spec_and_state(directory, run_identity)
            if state.state == "closed":
                if state.closed_at != closed_at:
                    raise EvidenceRunStoreConflict("closed run identity already has a different closed_at")
                return self._read_run_unlocked(run_identity)
            if state.state != "started" or state.started_at is None:
                raise EvidenceRunStoreStateError("only started evidence runs can be closed")
            plan = self._read_optional_model(directory / self._PLAN_FILE, RunPlan)
            if plan is None:
                raise EvidenceRunStoreIncomplete("started evidence run requires its stable ready plan")
            self._validate_plan_against_spec(plan, spec, require_complete=True)
            if state.plan_identity != plan.plan_identity:
                raise EvidenceRunStoreConflict("operational state plan identity does not match the persisted plan")
            closed = EvidenceRunState(
                state="closed",
                run_identity=run_identity,
                plan_identity=plan.plan_identity,
                started_at=state.started_at,
                closed_at=closed_at,
            )
            self._write_model(directory, self._STATE_FILE, closed)
            return StoredEvidenceRun(spec, plan, closed)

    def read_run(self, run_identity: EntityIdentity) -> StoredEvidenceRun:
        """Read and strictly validate the spec, optional plan, and operational state."""

        with self._lock(run_identity):
            return self._read_run_unlocked(run_identity)

    def find_run(self, selector: str) -> StoredEvidenceRun:
        """Find one stored run by its readable key or UUID."""

        if not selector.strip():
            raise EvidenceRunStoreError("run lookup selector must not be blank")
        matches: list[EntityIdentity] = []
        try:
            candidates = tuple(self.root.iterdir())
        except OSError as cause:
            raise EvidenceRunStoreError("evidence run store root cannot be listed") from cause
        for directory in candidates:
            try:
                details = directory.lstat()
            except OSError as cause:
                raise EvidenceRunStoreError("evidence run directory cannot be inspected") from cause
            if not stat.S_ISDIR(details.st_mode):
                continue
            spec = self._read_optional_model(directory / self._SPEC_FILE, ResolvedRunSpec)
            if spec is not None and selector in {str(spec.run_identity.key), str(spec.run_identity.id)}:
                matches.append(spec.run_identity)
        if not matches:
            raise EvidenceRunStoreIncomplete(f"no evidence run matches selector: {selector}")
        if len(matches) > 1:
            raise EvidenceRunStoreConflict(f"run selector matches multiple evidence runs: {selector}")
        return self.read_run(matches[0])

    @contextmanager
    def _lock(self, run_identity: EntityIdentity) -> Iterator[None]:
        if self.read_only:
            yield
            return
        with exclusive_local_file_lock(self.root, f"_locks/{self._locator(run_identity)}.lock"):
            yield

    def _require_writable(self) -> None:
        if self.read_only:
            raise EvidenceRunStoreError("read-only evidence run store rejects write operations")

    def _read_run_unlocked(self, run_identity: EntityIdentity) -> StoredEvidenceRun:
        directory = self.run_directory(run_identity)
        spec, state = self._require_spec_and_state(directory, run_identity)
        plan = self._read_optional_model(directory / self._PLAN_FILE, RunPlan)
        if plan is None:
            if state.state != "draft" or state.plan_identity is not None:
                raise EvidenceRunStoreIncomplete("non-draft evidence run requires a persisted plan")
        else:
            require_complete = state.state in {"ready", "started", "closed"}
            self._validate_plan_against_spec(plan, spec, require_complete=require_complete)
            if state.plan_identity != plan.plan_identity:
                raise EvidenceRunStoreConflict("operational state plan identity does not match the persisted plan")
            expected_plan_state = "draft" if state.state == "draft" else "ready"
            if plan.state != expected_plan_state:
                raise EvidenceRunStoreConflict("operational state does not match the persisted plan state")
        return StoredEvidenceRun(spec, plan, state)

    def _require_spec_and_state(
        self,
        directory: Path,
        run_identity: EntityIdentity,
    ) -> tuple[ResolvedRunSpec, EvidenceRunState]:
        self._require_safe_run_directory(directory)
        spec = self._read_optional_model(directory / self._SPEC_FILE, ResolvedRunSpec)
        state = self._read_optional_model(directory / self._STATE_FILE, EvidenceRunState)
        if spec is None or state is None:
            raise EvidenceRunStoreIncomplete("evidence run requires a resolved specification and state")
        if spec.run_identity != run_identity:
            raise EvidenceRunStoreConflict("run directory identity does not match its resolved specification")
        if state.run_identity != run_identity:
            raise EvidenceRunStoreConflict("run directory identity does not match its operational state")
        return spec, state

    def _ensure_run_directory(self, directory: Path) -> None:
        if directory.exists():
            self._require_safe_run_directory(directory)
            return
        mkdir_durable(directory, created_mode=0o700)

    @staticmethod
    def _require_safe_run_directory(directory: Path) -> None:
        try:
            details = directory.lstat()
        except FileNotFoundError as cause:
            raise EvidenceRunStoreIncomplete("evidence run directory does not exist") from cause
        except OSError as cause:
            raise EvidenceRunStoreError("evidence run directory cannot be inspected") from cause
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISDIR(details.st_mode):
            raise EvidenceRunStoreError("evidence run directory must be a regular directory")

    @staticmethod
    def _validate_plan_identity(run_identity: EntityIdentity, plan: RunPlan) -> None:
        if plan.run_identity != run_identity:
            raise EvidenceRunStoreConflict("plan run identity does not match the requested run")

    @staticmethod
    def _validate_plan_against_spec(
        plan: RunPlan,
        spec: ResolvedRunSpec,
        *,
        require_complete: bool,
    ) -> None:
        if plan.run_identity != spec.run_identity:
            raise EvidenceRunStoreConflict("plan run identity does not match the resolved specification")
        if any(trial.run_identity != spec.run_identity for trial in plan.trials):
            raise EvidenceRunStoreConflict("plan trial run identity does not match the resolved specification")
        spec_releases = {release.task_id: release for release in spec.task_releases}
        plan_releases = {trial.task_release.task_id: trial.task_release for trial in plan.trials}
        if any(spec_releases.get(task_id) != release for task_id, release in plan_releases.items()):
            raise EvidenceRunStoreConflict("plan task releases do not match the resolved specification")
        spec_conditions = {condition.identity.id: condition for condition in spec.agent_conditions}
        plan_conditions = {trial.agent_condition.identity.id: trial.agent_condition for trial in plan.trials}
        if any(spec_conditions.get(condition_id) != condition for condition_id, condition in plan_conditions.items()):
            raise EvidenceRunStoreConflict("plan agent conditions do not match the resolved specification")
        if any(trial.compute != spec.compute for trial in plan.trials):
            raise EvidenceRunStoreConflict("plan compute settings do not match the resolved specification")
        if any(trial.repetition > spec.repetitions for trial in plan.trials):
            raise EvidenceRunStoreConflict("plan repetitions exceed the resolved specification")
        if any(trial.seed != spec.randomization_seed for trial in plan.trials):
            raise EvidenceRunStoreConflict("plan seeds do not match the resolved specification")
        if any(trial.evaluation_profile != spec.evaluation_regime for trial in plan.trials):
            raise EvidenceRunStoreConflict("plan evaluation profiles do not match the resolved specification")
        if plan.summary.visibility_policy != spec.visibility:
            raise EvidenceRunStoreConflict("plan visibility policy does not match the resolved specification")
        if not require_complete:
            return
        if plan_releases != spec_releases:
            raise EvidenceRunStoreConflict("ready plan task releases do not match the resolved specification")
        if plan_conditions != spec_conditions:
            raise EvidenceRunStoreConflict("ready plan agent conditions do not match the resolved specification")
        expected_trials = len(spec.task_releases) * len(spec.agent_conditions) * spec.repetitions
        if plan.summary.repetitions != spec.repetitions or plan.summary.total_trials != expected_trials:
            raise EvidenceRunStoreConflict("plan trial count does not match the resolved specification")

    @staticmethod
    def _check_plan_revision(current: RunPlan, candidate: RunPlan) -> None:
        if (
            current.plan_identity.id != candidate.plan_identity.id
            or current.plan_identity.key != candidate.plan_identity.key
        ):
            raise EvidenceRunStoreConflict("plan replacement must preserve the plan identity")
        if candidate.plan_identity.version < current.plan_identity.version:
            raise EvidenceRunStoreConflict("plan replacement must use a higher plan identity version")
        if candidate.plan_identity.version == current.plan_identity.version and current != candidate:
            raise EvidenceRunStoreConflict("same plan identity version already has different content")

    @staticmethod
    def _locator(identity: EntityIdentity) -> str:
        if not isinstance(identity, EntityIdentity):
            raise EvidenceRunStoreError("evidence run operations require an EntityIdentity, not a raw path")
        readable_key = str(identity.key).replace("/", "__")
        max_key_bytes = 255 - len(str(identity.id)) - len("--")
        readable_key = readable_key[:max_key_bytes].rstrip("_-") or "run"
        return f"{readable_key}--{identity.id}"

    @staticmethod
    def _write_model(directory: Path, name: str, model: FrozenStrictModel) -> None:
        replace_file_bytes_durable(directory, name, _canonical_json(model), host_private=True)

    @staticmethod
    def _write_model_if_changed(
        directory: Path,
        name: str,
        current: FrozenStrictModel | None,
        candidate: FrozenStrictModel,
    ) -> None:
        if current != candidate:
            EvidenceRunStore._write_model(directory, name, candidate)

    @staticmethod
    def _read_optional_model(path: Path, model_type: type[_ModelT]) -> _ModelT | None:
        if not os.path.lexists(path):
            return None
        try:
            details = path.lstat()
        except OSError as cause:
            raise EvidenceRunStoreError(f"evidence run record cannot be inspected: {path}") from cause
        if stat.S_ISLNK(details.st_mode) or not stat.S_ISREG(details.st_mode):
            raise EvidenceRunStoreError(f"evidence run record is not a regular file: {path.name}")
        flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
            with os.fdopen(descriptor, "rb") as stream:
                payload = stream.read()
        except OSError as cause:
            raise EvidenceRunStoreError(f"evidence run record cannot be read: {path.name}") from cause
        try:
            return model_type.model_validate_json(payload)
        except ValueError as cause:
            raise EvidenceRunStoreError(f"evidence run record failed strict validation: {path.name}") from cause


def _canonical_json(model: FrozenStrictModel) -> bytes:
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


_ModelT = TypeVar("_ModelT", bound=FrozenStrictModel)


def _require_aware(value: datetime, name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"evidence run {name} must include a timezone")


__all__ = (
    "EvidenceRunState",
    "EvidenceRunStore",
    "EvidenceRunStoreConflict",
    "EvidenceRunStoreError",
    "EvidenceRunStoreIncomplete",
    "EvidenceRunStoreStateError",
    "StoredEvidenceRun",
)
