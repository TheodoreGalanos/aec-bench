# ABOUTME: Tests the phase-neutral governed-attempt lifecycle and its durable restart boundaries.
# ABOUTME: Uses deterministic local ports to exercise dispatch uncertainty, import recovery, and replay.

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pytest

import aec_bench.meta_harness.governed_attempt_engine as governed_attempt_api
from aec_bench.meta_harness.governed_attempt_engine import (
    GovernedAttemptBackendReceipt,
    GovernedAttemptBudgetClosure,
    GovernedAttemptBudgetReservation,
    GovernedAttemptCollisionError,
    GovernedAttemptConfinementError,
    GovernedAttemptDispatchIntent,
    GovernedAttemptDispatchUncertainError,
    GovernedAttemptEngine,
    GovernedAttemptExtensionError,
    GovernedAttemptImportReceipt,
    GovernedAttemptIntegrityError,
    GovernedAttemptMonitorClosure,
    GovernedAttemptMonitorPermit,
    GovernedAttemptPreflight,
    GovernedAttemptReconciliationRequiredError,
    GovernedAttemptReplay,
    GovernedAttemptUsage,
    GovernedAttemptUsageLimits,
)


def test_public_import_path_is_a_stable_package_surface() -> None:
    assert hasattr(governed_attempt_api, "__path__")
    assert {
        "GovernedAttemptEngine",
        "GovernedAttemptPreflight",
        "GovernedAttemptBudgetPort",
        "GovernedAttemptMonitorPort",
        "GovernedAttemptBackendPort",
        "GovernedAttemptImportExtension",
    }.issubset(governed_attempt_api.__all__)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _preflight(
    *,
    attempt_id: str = "attempt-alpha",
    workload_label: str = "workload-alpha",
) -> GovernedAttemptPreflight:
    return GovernedAttemptPreflight(
        attempt_id=attempt_id,
        workload_sha256=_sha(workload_label),
        dispatch_payload_sha256=_sha(f"dispatch:{workload_label}"),
        maximum_usage=GovernedAttemptUsageLimits(
            model_calls=1,
            total_tokens=150,
            estimated_cost_usd=1.0,
            wall_time_seconds=30.0,
        ),
        required_effect_evidence_sha256s=(_sha("effect-evidence"),),
    )


def _observed_usage() -> GovernedAttemptUsage:
    return GovernedAttemptUsage(
        model_calls=1,
        input_tokens=40,
        output_tokens=20,
        cache_read_tokens=5,
        cache_write_tokens=3,
        estimated_cost_usd=0.25,
        wall_time_seconds=3.0,
    )


@dataclass
class LocalBudgetPort:
    events: list[str]
    reserve_calls: int = 0
    close_calls: int = 0

    def reserve(
        self,
        preflight: GovernedAttemptPreflight,
    ) -> GovernedAttemptBudgetReservation:
        self.events.append("budget.reserve")
        self.reserve_calls += 1
        return GovernedAttemptBudgetReservation(
            attempt_id=preflight.attempt_id,
            preflight_sha256=preflight.content_sha256,
            reservation_id=f"local-budget:{preflight.attempt_id}",
            maximum_usage=preflight.maximum_usage,
        )

    def close(
        self,
        *,
        reservation: GovernedAttemptBudgetReservation,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
    ) -> GovernedAttemptBudgetClosure:
        self.events.append("budget.close")
        self.close_calls += 1
        return GovernedAttemptBudgetClosure(
            attempt_id=reservation.attempt_id,
            reservation_sha256=reservation.content_sha256,
            dispatch_receipt_sha256=dispatch_receipt.content_sha256,
            import_receipt_sha256=import_receipt.content_sha256,
            observed_usage=dispatch_receipt.observed_usage,
            effect_evidence_sha256s=dispatch_receipt.effect_evidence_sha256s,
        )


@dataclass
class LocalMonitorPort:
    events: list[str]
    authorize_calls: int = 0
    close_calls: int = 0

    def authorize(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        reservation: GovernedAttemptBudgetReservation,
    ) -> GovernedAttemptMonitorPermit:
        self.events.append("monitor.authorize")
        self.authorize_calls += 1
        return GovernedAttemptMonitorPermit(
            attempt_id=preflight.attempt_id,
            preflight_sha256=preflight.content_sha256,
            reservation_sha256=reservation.content_sha256,
            permit_id=f"local-monitor:{preflight.attempt_id}",
        )

    def close(
        self,
        *,
        permit: GovernedAttemptMonitorPermit,
        dispatch_receipt: GovernedAttemptBackendReceipt,
        import_receipt: GovernedAttemptImportReceipt,
        budget_closure: GovernedAttemptBudgetClosure,
    ) -> GovernedAttemptMonitorClosure:
        self.events.append("monitor.close")
        self.close_calls += 1
        return GovernedAttemptMonitorClosure(
            attempt_id=permit.attempt_id,
            permit_sha256=permit.content_sha256,
            dispatch_receipt_sha256=dispatch_receipt.content_sha256,
            import_receipt_sha256=import_receipt.content_sha256,
            budget_closure_sha256=budget_closure.content_sha256,
            observed_usage=dispatch_receipt.observed_usage,
            effect_evidence_sha256s=dispatch_receipt.effect_evidence_sha256s,
            closure_permitted=True,
        )


@dataclass
class LocalBackendPort:
    events: list[str]
    observed_usage: GovernedAttemptUsage = field(default_factory=_observed_usage)
    effect_evidence_sha256s: tuple[str, ...] = field(
        default_factory=lambda: (_sha("effect-evidence"),),
    )
    crash_after_effect_once: bool = False
    reconciliation_available: bool = True
    dispatch_calls: int = 0
    reconcile_calls: int = 0
    receipts: dict[str, GovernedAttemptBackendReceipt] = field(
        default_factory=dict,
    )

    def dispatch(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt:
        self.events.append("backend.dispatch")
        self.dispatch_calls += 1
        receipt = GovernedAttemptBackendReceipt(
            attempt_id=intent.attempt_id,
            dispatch_intent_sha256=intent.content_sha256,
            dispatch_key_sha256=intent.dispatch_key_sha256,
            backend_receipt_id=f"local-backend:{intent.dispatch_key_sha256}",
            observed_usage=self.observed_usage,
            effect_evidence_sha256s=self.effect_evidence_sha256s,
        )
        self.receipts[intent.dispatch_key_sha256] = receipt
        if self.crash_after_effect_once:
            self.crash_after_effect_once = False
            raise RuntimeError("local backend lost the receipt after dispatch")
        return receipt

    def reconcile(
        self,
        intent: GovernedAttemptDispatchIntent,
    ) -> GovernedAttemptBackendReceipt | None:
        self.events.append("backend.reconcile")
        self.reconcile_calls += 1
        if not self.reconciliation_available:
            return None
        return self.receipts.get(intent.dispatch_key_sha256)


@dataclass
class LocalImportExtension:
    events: list[str]
    failures_remaining: int = 0
    source_evidence_override: tuple[str, ...] | None = None
    import_calls: int = 0

    def import_result(
        self,
        *,
        preflight: GovernedAttemptPreflight,
        dispatch_receipt: GovernedAttemptBackendReceipt,
    ) -> GovernedAttemptImportReceipt:
        self.events.append("import.result")
        self.import_calls += 1
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("local import extension failed before publication")
        return GovernedAttemptImportReceipt(
            attempt_id=preflight.attempt_id,
            dispatch_receipt_sha256=dispatch_receipt.content_sha256,
            import_id=f"local-import:{dispatch_receipt.backend_receipt_id}",
            observed_usage=dispatch_receipt.observed_usage,
            source_effect_evidence_sha256s=(
                dispatch_receipt.effect_evidence_sha256s
                if self.source_evidence_override is None
                else self.source_evidence_override
            ),
            imported_evidence_sha256s=(_sha("imported-evidence"),),
        )


@dataclass
class LocalAttemptRuntime:
    root: Path
    events: list[str]
    budget: LocalBudgetPort
    monitor: LocalMonitorPort
    backend: LocalBackendPort
    importer: LocalImportExtension

    def engine(self) -> GovernedAttemptEngine:
        return GovernedAttemptEngine(
            root=self.root,
            budget=self.budget,
            monitor=self.monitor,
            backend=self.backend,
            import_extension=self.importer,
        )


def _runtime(
    root: Path,
    *,
    backend: LocalBackendPort | None = None,
    importer: LocalImportExtension | None = None,
) -> LocalAttemptRuntime:
    events: list[str] = []
    return LocalAttemptRuntime(
        root=root,
        events=events,
        budget=LocalBudgetPort(events),
        monitor=LocalMonitorPort(events),
        backend=backend or LocalBackendPort(events),
        importer=importer or LocalImportExtension(events),
    )


def _assert_complete_replay(
    replay: GovernedAttemptReplay,
    preflight: GovernedAttemptPreflight,
) -> None:
    assert replay.preflight == preflight
    assert replay.terminal.attempt_id == preflight.attempt_id
    assert replay.terminal.monitor_closure_sha256 == replay.monitor_closure.content_sha256


def test_happy_path_persists_the_exact_governed_attempt_lifecycle(
    tmp_path: Path,
) -> None:
    root = tmp_path / "attempt-evidence"
    runtime = _runtime(root)
    preflight = _preflight()

    replay = runtime.engine().execute(preflight)

    _assert_complete_replay(replay, preflight)
    assert runtime.events == [
        "budget.reserve",
        "monitor.authorize",
        "backend.dispatch",
        "import.result",
        "budget.close",
        "monitor.close",
    ]
    assert len(tuple(root.glob("governed-attempt/objects/dispatch_intent/*/record.json"))) == 1
    assert len(tuple(root.glob("governed-attempt/claims/terminal/*/claim.json"))) == 1


def test_restart_replays_terminal_evidence_without_reinvoking_ports(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "attempt-evidence")
    preflight = _preflight()
    expected = runtime.engine().execute(preflight)
    counts_before = (
        runtime.budget.reserve_calls,
        runtime.monitor.authorize_calls,
        runtime.backend.dispatch_calls,
        runtime.backend.reconcile_calls,
        runtime.importer.import_calls,
        runtime.budget.close_calls,
        runtime.monitor.close_calls,
    )

    restarted = runtime.engine()
    assert restarted.execute(preflight) == expected
    assert restarted.replay(preflight.attempt_id) == expected
    assert counts_before == (
        runtime.budget.reserve_calls,
        runtime.monitor.authorize_calls,
        runtime.backend.dispatch_calls,
        runtime.backend.reconcile_calls,
        runtime.importer.import_calls,
        runtime.budget.close_calls,
        runtime.monitor.close_calls,
    )


def test_uncertain_dispatch_requires_reconciliation_and_never_redispatches(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    backend = LocalBackendPort(
        events,
        crash_after_effect_once=True,
    )
    runtime = LocalAttemptRuntime(
        root=tmp_path / "attempt-evidence",
        events=events,
        budget=LocalBudgetPort(events),
        monitor=LocalMonitorPort(events),
        backend=backend,
        importer=LocalImportExtension(events),
    )
    preflight = _preflight()

    with pytest.raises(
        GovernedAttemptDispatchUncertainError,
        match="receipt is uncertain",
    ):
        runtime.engine().execute(preflight)
    assert backend.dispatch_calls == 1
    assert (
        len(
            tuple(
                runtime.root.glob(
                    "governed-attempt/claims/dispatch_intent/*/claim.json",
                )
            )
        )
        == 1
    )

    backend.reconciliation_available = False
    with pytest.raises(
        GovernedAttemptReconciliationRequiredError,
        match="could not reconcile",
    ):
        runtime.engine().execute(preflight)
    assert backend.dispatch_calls == 1

    backend.reconciliation_available = True
    replay = runtime.engine().execute(preflight)
    _assert_complete_replay(replay, preflight)
    assert backend.dispatch_calls == 1
    assert backend.reconcile_calls == 2


def test_import_failure_recovers_without_backend_redispatch(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    importer = LocalImportExtension(events, failures_remaining=1)
    runtime = LocalAttemptRuntime(
        root=tmp_path / "attempt-evidence",
        events=events,
        budget=LocalBudgetPort(events),
        monitor=LocalMonitorPort(events),
        backend=LocalBackendPort(events),
        importer=importer,
    )
    preflight = _preflight()

    with pytest.raises(
        GovernedAttemptExtensionError,
        match="import extension failed",
    ):
        runtime.engine().execute(preflight)
    assert runtime.backend.dispatch_calls == 1

    replay = runtime.engine().execute(preflight)
    _assert_complete_replay(replay, preflight)
    assert runtime.backend.dispatch_calls == 1
    assert runtime.backend.reconcile_calls == 0
    assert importer.import_calls == 2


@pytest.mark.parametrize(
    "mismatch",
    ["usage", "backend_evidence", "import_evidence"],
)
def test_usage_and_evidence_mismatches_fail_closed_without_redispatch(
    tmp_path: Path,
    mismatch: str,
) -> None:
    events: list[str] = []
    backend = LocalBackendPort(
        events,
        observed_usage=(GovernedAttemptUsage(model_calls=2) if mismatch == "usage" else _observed_usage()),
        effect_evidence_sha256s=(
            (_sha("wrong-effect-evidence"),) if mismatch == "backend_evidence" else (_sha("effect-evidence"),)
        ),
    )
    runtime = LocalAttemptRuntime(
        root=tmp_path / mismatch,
        events=events,
        budget=LocalBudgetPort(events),
        monitor=LocalMonitorPort(events),
        backend=backend,
        importer=LocalImportExtension(
            events,
            source_evidence_override=(
                (_sha("wrong-import-source-evidence"),) if mismatch == "import_evidence" else None
            ),
        ),
    )
    preflight = _preflight()

    with pytest.raises(
        GovernedAttemptIntegrityError,
        match="usage exceeds|effect evidence",
    ):
        runtime.engine().execute(preflight)
    with pytest.raises(
        GovernedAttemptIntegrityError,
        match="usage exceeds|effect evidence",
    ):
        runtime.engine().execute(preflight)
    assert backend.dispatch_calls == 1
    assert backend.reconcile_calls == 0


def test_total_token_limit_counts_cache_usage(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    runtime = LocalAttemptRuntime(
        root=tmp_path / "cached-token-limit",
        events=events,
        budget=LocalBudgetPort(events),
        monitor=LocalMonitorPort(events),
        backend=LocalBackendPort(events),
        importer=LocalImportExtension(events),
    )
    baseline = _preflight()
    preflight = GovernedAttemptPreflight(
        **baseline.model_dump(
            mode="python",
            exclude={"content_sha256", "maximum_usage"},
        ),
        maximum_usage=GovernedAttemptUsageLimits(
            model_calls=1,
            total_tokens=67,
            estimated_cost_usd=None,
            wall_time_seconds=30.0,
        ),
    )

    with pytest.raises(
        GovernedAttemptIntegrityError,
        match="total tokens",
    ):
        runtime.engine().execute(preflight)

    assert runtime.backend.dispatch_calls == 1


def test_attempt_identity_collision_cannot_rebind_a_completed_attempt(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path / "attempt-evidence")
    runtime.engine().execute(_preflight())

    with pytest.raises(
        GovernedAttemptCollisionError,
        match="preflight.*different immutable content",
    ):
        runtime.engine().execute(
            _preflight(workload_label="different-workload"),
        )
    assert runtime.backend.dispatch_calls == 1


def test_repository_root_rejects_symlink_confinement(
    tmp_path: Path,
) -> None:
    real_root = tmp_path / "real-root"
    real_root.mkdir(mode=0o700)
    linked_root = tmp_path / "linked-root"
    linked_root.symlink_to(real_root, target_is_directory=True)
    runtime = _runtime(linked_root)

    with pytest.raises(
        GovernedAttemptConfinementError,
        match="symlink|symbolic-link",
    ):
        runtime.engine()
