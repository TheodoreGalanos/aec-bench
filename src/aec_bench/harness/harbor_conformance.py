# ABOUTME: Provides reusable assertions for the concrete scheduler-facing Harbor backend.
# ABOUTME: Keeps backend conformance checks independent from Harbor provider credentials and transport clients.

from __future__ import annotations

import json
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from typing import Any

from aec_bench.execution.models import (
    BackendCancellationResult,
    FailureClass,
    FailureClassification,
    WorkerOutcome,
)
from aec_bench.harness.harbor_backend import HarborBackend

REQUIRED_GUARANTEES = frozenset(
    {
        "declared_capabilities",
        "planned_trial_identity",
        "readable_status",
        "cancellation_declaration",
        "retryable_terminal_classification",
        "unknown_state_retained_as_unknown",
        "complete_attempt_receipt",
        "no_persisted_secrets",
        "idempotent_repeated_collection",
        "wrong_identity_rejection",
    }
)

EXPECTED_CAPABILITIES = frozenset({"submit", "inspect", "collect", "cancel", "reconcile"})


@dataclass(frozen=True, slots=True)
class HarborBackendConformanceCase:
    """Owner-supplied exercises for one concrete :class:`HarborBackend`."""

    backend: HarborBackend
    successful_execution: Callable[[], WorkerOutcome]
    repeated_collection: Callable[[], WorkerOutcome]
    unknown_execution: Callable[[], WorkerOutcome]
    cancellation: Callable[[], BackendCancellationResult]
    retryable_failure: Callable[[], FailureClassification]
    terminal_failure: Callable[[], FailureClassification]
    persisted_transport: Callable[[], Mapping[str, object]]
    wrong_identity: Callable[[], None]
    planned_trial_identity: Callable[[], tuple[str, str, str]]
    capabilities: Collection[str] = EXPECTED_CAPABILITIES


def assert_harbor_backend_conformance(case: HarborBackendConformanceCase) -> None:
    """Assert the scheduler, transport, and evidence guarantees for one backend case."""

    assert frozenset(case.capabilities) == EXPECTED_CAPABILITIES
    assert frozenset(case.backend.capabilities) == EXPECTED_CAPABILITIES

    successful = case.successful_execution()
    assert successful.terminal_state == "succeeded"
    assert successful.finalization is not None
    assert len(successful.receipts) == 1
    receipt = successful.receipts[0]
    assert receipt.process_status.value == "succeeded"
    assert receipt.receipt_id and receipt.attempt_id and receipt.submission_id
    assert receipt.started_at <= receipt.finished_at
    assert receipt.failure is None

    submitted_id, collected_id, published_id = case.planned_trial_identity()
    assert submitted_id == collected_id == published_id
    assert submitted_id

    repeated = case.repeated_collection()
    assert repeated == successful

    unknown = case.unknown_execution()
    assert unknown.terminal_state == "unknown"
    assert unknown.finalization is None
    assert len(unknown.receipts) == 1
    assert unknown.receipts[0].process_status.value == "unknown"
    assert unknown.receipts[0].failure is not None
    assert unknown.receipts[0].failure.failure_class is FailureClass.UNKNOWN

    cancellation = case.cancellation()
    assert cancellation.status in {"confirmed", "rejected", "unsupported", "unknown"}
    assert cancellation.message.strip()

    retryable = case.retryable_failure()
    terminal = case.terminal_failure()
    assert retryable.failure_class is FailureClass.INFRASTRUCTURE
    assert terminal.failure_class in {FailureClass.BENCHMARK, FailureClass.INVALIDATING}

    persisted = json.dumps(dict(case.persisted_transport()), sort_keys=True)
    assert "password" not in persisted.lower()
    assert "secret" not in persisted.lower()
    assert "token" not in persisted.lower()

    try:
        case.wrong_identity()
    except (ValueError, RuntimeError):
        pass
    else:
        raise AssertionError("Harbor backend accepted a wrong trial identity")


def run_harbor_backend_conformance(case: HarborBackendConformanceCase) -> dict[str, Any]:
    """Run one owner case and return the stable guarantee names."""

    assert_harbor_backend_conformance(case)
    return {"proven": sorted(REQUIRED_GUARANTEES)}


__all__ = (
    "EXPECTED_CAPABILITIES",
    "HarborBackendConformanceCase",
    "REQUIRED_GUARANTEES",
    "assert_harbor_backend_conformance",
    "run_harbor_backend_conformance",
)
