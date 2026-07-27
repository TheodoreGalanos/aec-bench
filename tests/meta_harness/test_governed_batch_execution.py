# ABOUTME: Exercises the cardinality-neutral governed batch lifecycle and evidence joins.
# ABOUTME: Proves authorization ordering, deterministic execution, failure closure, and replay.

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from aec_bench.meta_harness.governed_batch_execution import (
    GovernedBatchAssignment,
    GovernedBatchAssignmentTerminal,
    GovernedBatchDesign,
    GovernedBatchExecutionIntegrityError,
    GovernedBatchExecutionStore,
    GovernedBatchStatus,
    GovernedBatchTerminal,
    run_governed_batch,
)


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode()).hexdigest()


def _design(count: int) -> GovernedBatchDesign:
    return GovernedBatchDesign(
        batch_id=f"batch.{count}",
        source_batch_sha256=_sha(f"source.{count}"),
        assignments=tuple(
            GovernedBatchAssignment(
                assignment_sha256=_sha(f"assignment.{index}"),
                dispatch_sha256=_sha(f"dispatch.{index}"),
                authorization_chain_sha256=_sha(f"authorization.{index}"),
            )
            for index in range(1, count + 1)
        ),
        max_concurrency=min(count, 3),
    )


@dataclass(frozen=True)
class _LocalResult:
    terminal: GovernedBatchAssignmentTerminal
    payload: str


@dataclass
class _LocalBatchPort:
    design: GovernedBatchDesign
    fail_ordinal: int | None = None
    barrier_permitted: bool = True
    events: list[str] = field(default_factory=list)
    results: list[_LocalResult] = field(default_factory=list)
    closure: GovernedBatchTerminal | None = None

    def replay_authorization_barrier(
        self,
        design: GovernedBatchDesign,
    ) -> None:
        self.events.append("authorization")
        if design != self.design or not self.barrier_permitted:
            raise GovernedBatchExecutionIntegrityError(
                "local authorization barrier rejected the batch",
            )

    def open_execution_state(
        self,
        design: GovernedBatchDesign,
    ) -> None:
        assert design == self.design
        self.events.append("open")

    def load_terminal(self) -> GovernedBatchTerminal | None:
        return self.closure

    def load_results(self) -> tuple[_LocalResult, ...]:
        return tuple(self.results)

    def project_result(
        self,
        result: _LocalResult,
    ) -> GovernedBatchAssignmentTerminal:
        return result.terminal

    def replay_result(
        self,
        *,
        assignment: GovernedBatchAssignment,
        ordinal: int,
        expected: _LocalResult,
    ) -> tuple[_LocalResult, str]:
        self.events.append(f"replay.{ordinal}")
        assert assignment.assignment_sha256 == expected.terminal.assignment_sha256
        return expected, expected.payload

    def authorize_effect(
        self,
        *,
        assignment: GovernedBatchAssignment,
        ordinal: int,
    ) -> str:
        self.events.append(f"permit.{ordinal}")
        return _sha(f"permit.{assignment.assignment_sha256}")

    def effect_authorization_sha256(self, authorization: str) -> str:
        return authorization

    def execute_assignment(
        self,
        *,
        assignment: GovernedBatchAssignment,
        ordinal: int,
        effect_authorization: str,
    ) -> tuple[_LocalResult, str]:
        self.events.append(f"execute.{ordinal}")
        if ordinal == self.fail_ordinal:
            raise RuntimeError(f"planned failure at {ordinal}")
        attempt_terminal = _sha(f"attempt.{assignment.assignment_sha256}")
        monitor_evidence = _sha(f"monitor.{assignment.assignment_sha256}")
        result = _LocalResult(
            terminal=GovernedBatchAssignmentTerminal(
                design_sha256=self.design.content_sha256,
                ordinal=ordinal,
                assignment_sha256=assignment.assignment_sha256,
                dispatch_sha256=assignment.dispatch_sha256,
                authorization_chain_sha256=(assignment.authorization_chain_sha256),
                effect_authorization_sha256=effect_authorization,
                attempt_terminal_sha256=attempt_terminal,
                terminal_variant="scored",
                monitor_evidence_sha256s=(monitor_evidence,),
                effect_evidence_sha256s=(
                    attempt_terminal,
                    monitor_evidence,
                ),
            ),
            payload=f"payload.{ordinal}",
        )
        return result, result.payload

    def record_result(self, result: _LocalResult) -> _LocalResult:
        self.events.append(f"record.{result.terminal.ordinal}")
        self.results.append(result)
        return result

    def close_terminal(
        self,
        *,
        incomplete_reason: str | None,
    ) -> GovernedBatchTerminal:
        self.events.append("monitor-close")
        claims = tuple(result.terminal for result in self.results)
        incomplete = self.design.ordered_assignment_sha256s[len(claims) :]
        self.closure = GovernedBatchTerminal(
            design_sha256=self.design.content_sha256,
            status=(
                GovernedBatchStatus.COMPLETED
                if not incomplete and incomplete_reason is None
                else GovernedBatchStatus.INCOMPLETE
            ),
            assignment_terminals=claims,
            incomplete_assignment_sha256s=incomplete,
            monitor_closure_sha256=_sha("monitor-closure"),
            observed_peak_concurrency=1 if claims else 0,
            incomplete_reason=incomplete_reason,
        )
        return self.closure

    def project_terminal(
        self,
        closure: GovernedBatchTerminal,
    ) -> GovernedBatchTerminal:
        return closure


def test_batch_design_derives_cardinality_from_supplied_assignments() -> None:
    singleton = _design(1)
    seven = _design(7)

    assert singleton.assignment_count == 1
    assert seven.assignment_count == 7
    assert len(seven.ordered_assignment_sha256s) == 7

    with pytest.raises(ValidationError, match="assignment identities"):
        GovernedBatchDesign(
            batch_id="batch.duplicate",
            source_batch_sha256=_sha("source.duplicate"),
            assignments=(
                seven.assignments[0],
                seven.assignments[0],
            ),
            max_concurrency=1,
        )


def test_assignment_terminal_requires_attempt_and_monitor_effect_evidence() -> None:
    design = _design(1)
    assignment = design.assignments[0]
    arguments = {
        "design_sha256": design.content_sha256,
        "ordinal": 1,
        "assignment_sha256": assignment.assignment_sha256,
        "dispatch_sha256": assignment.dispatch_sha256,
        "authorization_chain_sha256": (assignment.authorization_chain_sha256),
        "effect_authorization_sha256": _sha("permit"),
        "attempt_terminal_sha256": _sha("attempt"),
        "terminal_variant": "scored",
        "monitor_evidence_sha256s": (_sha("monitor"),),
        "effect_evidence_sha256s": (_sha("unrelated"),),
    }

    with pytest.raises(
        ValidationError,
        match="attempt or monitor closure",
    ):
        GovernedBatchAssignmentTerminal(**arguments)


def test_executes_a_dynamic_batch_in_exact_order_and_replays() -> None:
    design = _design(4)
    port = _LocalBatchPort(design=design)

    completed = run_governed_batch(design=design, port=port)

    assert completed.closure.status is GovernedBatchStatus.COMPLETED
    assert completed.payloads == tuple(f"payload.{ordinal}" for ordinal in range(1, 5))
    assert port.events == [
        "authorization",
        "open",
        "permit.1",
        "execute.1",
        "record.1",
        "permit.2",
        "execute.2",
        "record.2",
        "permit.3",
        "execute.3",
        "record.3",
        "permit.4",
        "execute.4",
        "record.4",
        "monitor-close",
    ]

    port.events.clear()
    replayed = run_governed_batch(design=design, port=port)

    assert replayed == completed
    assert port.events == [
        "authorization",
        "open",
        "replay.1",
        "replay.2",
        "replay.3",
        "replay.4",
    ]


def test_closes_a_dynamic_incomplete_prefix_without_retry() -> None:
    design = _design(5)
    port = _LocalBatchPort(
        design=design,
        fail_ordinal=3,
    )

    run = run_governed_batch(design=design, port=port)

    assert run.closure.status is GovernedBatchStatus.INCOMPLETE
    assert (
        tuple(result.assignment_sha256 for result in run.closure.assignment_terminals)
        == design.ordered_assignment_sha256s[:2]
    )
    assert run.closure.incomplete_assignment_sha256s == design.ordered_assignment_sha256s[2:]
    assert run.closure.incomplete_reason == "RuntimeError: planned failure at 3"
    assert "execute.4" not in port.events


def test_authorization_barrier_precedes_all_execution_state() -> None:
    design = _design(3)
    port = _LocalBatchPort(
        design=design,
        barrier_permitted=False,
    )

    with pytest.raises(
        GovernedBatchExecutionIntegrityError,
        match="authorization barrier",
    ):
        run_governed_batch(design=design, port=port)

    assert port.events == ["authorization"]
    assert port.results == []
    assert port.closure is None


def test_generic_store_persists_canonical_dynamic_batch_state(
    tmp_path,
) -> None:
    design = _design(2)
    store = GovernedBatchExecutionStore.open(
        root=tmp_path / "batch-state",
        design=design,
    )
    assignment = design.assignments[0]
    attempt_terminal = _sha("attempt.1")
    monitor_evidence = _sha("monitor.1")
    result = GovernedBatchAssignmentTerminal(
        design_sha256=design.content_sha256,
        ordinal=1,
        assignment_sha256=assignment.assignment_sha256,
        dispatch_sha256=assignment.dispatch_sha256,
        authorization_chain_sha256=assignment.authorization_chain_sha256,
        effect_authorization_sha256=_sha("permit.1"),
        attempt_terminal_sha256=attempt_terminal,
        terminal_variant="scored",
        monitor_evidence_sha256s=(monitor_evidence,),
        effect_evidence_sha256s=(attempt_terminal, monitor_evidence),
    )

    assert store.record_result(result) == result
    assert store.load_results() == (result,)

    result_path = tmp_path / "batch-state" / "assignments" / "01.json"
    encoded = result_path.read_bytes()
    assert (
        encoded
        == (
            json.dumps(
                json.loads(encoded),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            )
            + "\n"
        ).encode()
    )
    assert stat.S_IMODE(result_path.stat().st_mode) == 0o600
