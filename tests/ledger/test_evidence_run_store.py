# ABOUTME: Tests durable storage and state transitions for requested benchmark runs.
# ABOUTME: Covers idempotency, plan revisions, strict reads, confinement, and pre-execution locking.

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import aec_bench.ledger.evidence_run_store as evidence_run_store
from aec_bench.contracts.identity import EntityKind
from aec_bench.contracts.run_plan import RunPlan, plan_run
from aec_bench.ledger.evidence_run_store import (
    EvidenceRunStore,
    EvidenceRunStoreConflict,
    EvidenceRunStoreError,
    EvidenceRunStoreStateError,
)
from tests.contracts.test_run_plan import _accept_combination, _identity, _resolved_run, _task_profiles

_STARTED_AT = datetime(2026, 8, 30, 12, 2, tzinfo=UTC)
_CLOSED_AT = datetime(2026, 8, 30, 12, 3, tzinfo=UTC)


def _ready_plan(spec) -> RunPlan:
    return plan_run(
        spec,
        plan_identity=_identity(EntityKind.PLAN, "pump-study-plan"),
        created_at=datetime(2026, 8, 30, 12, 1, tzinfo=UTC),
        task_profiles=_task_profiles(spec),
        validate_combination=_accept_combination,
    )


def test_create_run_persists_spec_before_plan_and_uses_full_uuid_directory(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")

    stored = store.create_run(spec)

    directory = store.run_directory(spec.run_identity)
    assert directory.name == f"pump-study-run--{spec.run_identity.id}"
    assert (directory / "resolved-run-spec.json").is_file()
    assert not (directory / "run-plan.json").exists()
    assert stored.spec == spec
    assert stored.plan is None
    assert stored.state.state == "draft"


def test_create_run_is_idempotent_but_conflicting_spec_is_rejected(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)

    assert store.create_run(spec).spec == spec
    with pytest.raises(EvidenceRunStoreConflict, match="different resolved specification"):
        store.create_run(spec.model_copy(update={"created_by": "different"}))


def test_partial_publish_can_be_retried_after_state_write_failure(tmp_path: Path, monkeypatch) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    original_write = evidence_run_store.replace_file_bytes_durable

    def fail_state_write(directory: Path, name: str, payload: bytes, *, host_private: bool = False) -> None:
        if name == "state.json":
            raise RuntimeError("simulated process failure")
        original_write(directory, name, payload, host_private=host_private)

    monkeypatch.setattr(evidence_run_store, "replace_file_bytes_durable", fail_state_write)
    with pytest.raises(RuntimeError, match="simulated process failure"):
        store.create_run(spec)
    assert (store.run_directory(spec.run_identity) / "resolved-run-spec.json").is_file()
    assert not (store.run_directory(spec.run_identity) / "state.json").exists()

    monkeypatch.setattr(evidence_run_store, "replace_file_bytes_durable", original_write)
    assert store.create_run(spec).state.state == "draft"


def test_create_run_does_not_recreate_missing_state_after_plan_exists(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    ready = _ready_plan(spec)
    store.write_draft_plan(spec.run_identity, ready.model_copy(update={"state": "draft"}))
    state_path = store.run_directory(spec.run_identity) / "state.json"
    state_path.unlink()

    with pytest.raises(EvidenceRunStoreError, match="missing operational state"):
        store.create_run(spec)
    assert not state_path.exists()


def test_draft_plan_replacement_requires_higher_plan_identity_version(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    ready = _ready_plan(spec)
    draft = ready.model_copy(update={"state": "draft"})
    store.write_draft_plan(spec.run_identity, draft)

    assert store.write_draft_plan(spec.run_identity, draft) == draft
    with pytest.raises(EvidenceRunStoreConflict, match="same plan identity version"):
        store.write_draft_plan(spec.run_identity, draft.model_copy(update={"trials": draft.trials[:-1]}))
    revised = draft.model_copy(update={"plan_identity": draft.plan_identity.model_copy(update={"version": 2})})
    assert store.write_draft_plan(spec.run_identity, revised) == revised
    with pytest.raises(EvidenceRunStoreConflict, match="higher plan identity version"):
        store.write_draft_plan(spec.run_identity, draft)


def test_incomplete_draft_is_allowed_and_new_revision_clears_ready_state(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    ready = _ready_plan(spec)
    incomplete = ready.model_copy(update={"state": "draft", "trials": ready.trials[:1]})
    store.write_draft_plan(spec.run_identity, incomplete)
    ready = ready.model_copy(update={"plan_identity": ready.plan_identity.model_copy(update={"version": 2})})
    store.write_draft_plan(spec.run_identity, ready.model_copy(update={"state": "draft"}))
    store.promote_ready_plan(spec.run_identity, ready)

    revised = ready.model_copy(
        update={
            "state": "draft",
            "plan_identity": ready.plan_identity.model_copy(update={"version": 3}),
        }
    )
    store.write_draft_plan(spec.run_identity, revised)

    stored = store.read_run(spec.run_identity)
    assert stored.state.state == "draft"
    assert stored.state.plan_identity == revised.plan_identity
    assert stored.plan == revised


def test_ready_promotion_rejects_content_not_present_in_draft(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    ready = _ready_plan(spec)
    store.write_draft_plan(spec.run_identity, ready.model_copy(update={"state": "draft"}))

    changed = ready.model_copy(update={"created_at": ready.created_at + timedelta(seconds=1)})
    with pytest.raises(EvidenceRunStoreConflict, match="content must match"):
        store.promote_ready_plan(spec.run_identity, changed)


def test_ready_promotion_then_start_and_close_freezes_spec_and_plan(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    ready = _ready_plan(spec)
    store.write_draft_plan(spec.run_identity, ready.model_copy(update={"state": "draft"}))
    promoted = store.promote_ready_plan(spec.run_identity, ready)

    with pytest.raises(ValueError, match="must not precede"):
        store.start_run(spec.run_identity, started_at=ready.created_at - timedelta(seconds=1))

    started = store.start_run(spec.run_identity, started_at=_STARTED_AT)
    assert started.state.state == "started"
    assert started.plan == promoted
    assert store.start_run(spec.run_identity, started_at=_STARTED_AT).state == started.state
    with pytest.raises(EvidenceRunStoreStateError, match="cannot be edited"):
        store.write_draft_plan(spec.run_identity, ready.model_copy(update={"state": "draft"}))

    closed = store.close_run(spec.run_identity, closed_at=_CLOSED_AT)
    assert closed.state.state == "closed"
    assert closed.state.started_at == _STARTED_AT
    assert closed.plan == promoted
    assert (closed.spec, closed.plan) == (started.spec, started.plan)
    with pytest.raises(EvidenceRunStoreStateError, match="cannot be started"):
        store.start_run(spec.run_identity, started_at=_STARTED_AT)


def test_read_run_strictly_validates_records_and_rejects_symlink_directory(tmp_path: Path) -> None:
    spec = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(spec)
    (store.run_directory(spec.run_identity) / "state.json").write_text("{}", encoding="utf-8")
    with pytest.raises(EvidenceRunStoreError, match="strict validation"):
        store.read_run(spec.run_identity)

    outside = tmp_path / "outside"
    outside.mkdir()
    symlink_store = EvidenceRunStore(tmp_path / "symlink-runs")
    symlink_store.run_directory(spec.run_identity).symlink_to(outside, target_is_directory=True)
    with pytest.raises(EvidenceRunStoreError, match="regular directory"):
        symlink_store.create_run(spec)
    with pytest.raises(EvidenceRunStoreError, match="regular directory"):
        symlink_store.read_run(spec.run_identity)


def test_read_run_rejects_cross_run_state_and_plan_drift(tmp_path: Path) -> None:
    first = _resolved_run(repetitions=1)
    second = _resolved_run(repetitions=1)
    store = EvidenceRunStore(tmp_path / "runs")
    store.create_run(first)
    store.create_run(second)

    first_state = store.run_directory(first.run_identity) / "state.json"
    second_state = store.run_directory(second.run_identity) / "state.json"
    second_state.write_bytes(first_state.read_bytes())
    with pytest.raises(EvidenceRunStoreConflict, match="operational state"):
        store.read_run(second.run_identity)

    ready = _ready_plan(first)
    store.write_draft_plan(first.run_identity, ready.model_copy(update={"state": "draft"}))
    store.promote_ready_plan(first.run_identity, ready)
    plan_path = store.run_directory(first.run_identity) / "run-plan.json"
    changed = ready.model_copy(update={"trials": (ready.trials[0].model_copy(update={"seed": 99}), *ready.trials[1:])})
    plan_path.write_text(changed.model_dump_json(), encoding="utf-8")
    with pytest.raises(EvidenceRunStoreConflict, match="seeds"):
        store.read_run(first.run_identity)


def test_store_rejects_symlink_root(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    with pytest.raises(EvidenceRunStoreError, match="root must not be a symbolic link"):
        EvidenceRunStore(alias)


def test_read_only_store_requires_an_existing_root_and_rejects_writes(tmp_path: Path) -> None:
    root = tmp_path / "runs"
    with pytest.raises(EvidenceRunStoreError, match="regular directory"):
        EvidenceRunStore.open_read_only(root)
    assert not root.exists()

    spec = _resolved_run(repetitions=1)
    writable = EvidenceRunStore(root)
    writable.create_run(spec)
    lock_paths_before = {path.relative_to(root) for path in (root / "_locks").rglob("*")}
    readonly = EvidenceRunStore.open_read_only(root)

    assert readonly.find_run(str(spec.run_identity.id)).spec == spec
    assert {path.relative_to(root) for path in (root / "_locks").rglob("*")} == lock_paths_before
    with pytest.raises(EvidenceRunStoreError, match="rejects write operations"):
        readonly.create_run(spec)


def test_store_rejects_raw_path_as_run_identity(tmp_path: Path) -> None:
    store = EvidenceRunStore(tmp_path / "runs")
    with pytest.raises(EvidenceRunStoreError, match="not a raw path"):
        store.run_directory("../outside")  # type: ignore[arg-type]


def test_run_directory_bounds_long_readable_key_and_keeps_full_uuid(tmp_path: Path) -> None:
    store = EvidenceRunStore(tmp_path / "runs")
    identity = _identity(EntityKind.RUN, "r" * 400)

    directory = store.run_directory(identity)

    assert len(directory.name.encode("utf-8")) <= 255
    assert directory.name.endswith(f"--{identity.id}")
