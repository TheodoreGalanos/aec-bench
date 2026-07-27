# ABOUTME: Runs one authorized governed batch in deterministic assignment order.
# ABOUTME: Closes exact result prefixes on success, failure, and durable replay.

from __future__ import annotations

from dataclasses import dataclass

from .contracts import (
    GovernedBatchAssignment,
    GovernedBatchAssignmentTerminal,
    GovernedBatchDesign,
    GovernedBatchExecutionIntegrityError,
    GovernedBatchStatus,
)
from .ports import GovernedBatchExecutionPort


@dataclass(frozen=True)
class GovernedBatchRun[ClosureT, PayloadT]:
    """Phase closure and replayed payloads produced by one governed batch."""

    closure: ClosureT
    payloads: tuple[PayloadT, ...]


def run_governed_batch[
    EffectAuthorizationT,
    ResultT,
    PayloadT,
    ClosureT,
](
    *,
    design: GovernedBatchDesign,
    port: GovernedBatchExecutionPort[
        EffectAuthorizationT,
        ResultT,
        PayloadT,
        ClosureT,
    ],
) -> GovernedBatchRun[ClosureT, PayloadT]:
    """Execute or replay a dynamically sized batch through one closed lifecycle."""

    port.replay_authorization_barrier(design)
    port.open_execution_state(design)
    terminal = port.load_terminal()
    persisted = port.load_results()
    _validate_result_prefix(
        design=design,
        results=persisted,
        port=port,
    )
    payloads: list[PayloadT] = []
    for ordinal, (assignment, expected) in enumerate(
        zip(design.assignments, persisted, strict=False),
        start=1,
    ):
        replayed, payload = port.replay_result(
            assignment=assignment,
            ordinal=ordinal,
            expected=expected,
        )
        if replayed != expected:
            _fail_integrity(
                port=port,
                design=design,
                reason="replayed assignment differs from its durable result",
            )
        payloads.append(payload)
    if terminal is not None:
        _validate_terminal(
            design=design,
            closure=terminal,
            results=persisted,
            port=port,
        )
        return GovernedBatchRun(
            closure=terminal,
            payloads=tuple(payloads),
        )

    for ordinal in range(len(persisted) + 1, design.assignment_count + 1):
        assignment = design.assignments[ordinal - 1]
        try:
            effect_authorization = port.authorize_effect(
                assignment=assignment,
                ordinal=ordinal,
            )
            result, payload = port.execute_assignment(
                assignment=assignment,
                ordinal=ordinal,
                effect_authorization=effect_authorization,
            )
            _validate_assignment_terminal(
                design=design,
                assignment=assignment,
                ordinal=ordinal,
                expected_effect_authorization_sha256=(
                    port.effect_authorization_sha256(
                        effect_authorization,
                    )
                ),
                terminal=port.project_result(result),
            )
            persisted_result = port.record_result(result)
            if persisted_result != result:
                raise GovernedBatchExecutionIntegrityError(
                    "persisted assignment differs from the executed result",
                )
            payloads.append(payload)
        except GovernedBatchExecutionIntegrityError as error:
            closure = port.close_terminal(
                incomplete_reason=f"{type(error).__name__}: {error}",
            )
            _validate_terminal(
                design=design,
                closure=closure,
                results=port.load_results(),
                port=port,
            )
            raise
        except Exception as error:
            closure = port.close_terminal(
                incomplete_reason=f"{type(error).__name__}: {error}",
            )
            _validate_terminal(
                design=design,
                closure=closure,
                results=port.load_results(),
                port=port,
            )
            return GovernedBatchRun(
                closure=closure,
                payloads=tuple(payloads),
            )

    closure = port.close_terminal(incomplete_reason=None)
    _validate_terminal(
        design=design,
        closure=closure,
        results=port.load_results(),
        port=port,
    )
    return GovernedBatchRun(
        closure=closure,
        payloads=tuple(payloads),
    )


def _validate_result_prefix[
    EffectAuthorizationT,
    ResultT,
    PayloadT,
    ClosureT,
](
    *,
    design: GovernedBatchDesign,
    results: tuple[ResultT, ...],
    port: GovernedBatchExecutionPort[
        EffectAuthorizationT,
        ResultT,
        PayloadT,
        ClosureT,
    ],
) -> None:
    if len(results) > design.assignment_count:
        raise GovernedBatchExecutionIntegrityError(
            "durable assignment prefix exceeds supplied batch cardinality",
        )
    for ordinal, (assignment, result) in enumerate(
        zip(design.assignments, results, strict=False),
        start=1,
    ):
        _validate_assignment_terminal(
            design=design,
            assignment=assignment,
            ordinal=ordinal,
            expected_effect_authorization_sha256=None,
            terminal=port.project_result(result),
        )


def _validate_assignment_terminal(
    *,
    design: GovernedBatchDesign,
    assignment: GovernedBatchAssignment,
    ordinal: int,
    expected_effect_authorization_sha256: str | None,
    terminal: GovernedBatchAssignmentTerminal,
) -> None:
    if (
        terminal.design_sha256 != design.content_sha256
        or terminal.ordinal != ordinal
        or terminal.assignment_sha256 != assignment.assignment_sha256
        or terminal.dispatch_sha256 != assignment.dispatch_sha256
        or terminal.authorization_chain_sha256 != assignment.authorization_chain_sha256
        or (
            expected_effect_authorization_sha256 is not None
            and terminal.effect_authorization_sha256 != expected_effect_authorization_sha256
        )
    ):
        raise GovernedBatchExecutionIntegrityError(
            "assignment terminal differs from its authorized batch position",
        )


def _validate_terminal[
    EffectAuthorizationT,
    ResultT,
    PayloadT,
    ClosureT,
](
    *,
    design: GovernedBatchDesign,
    closure: ClosureT,
    results: tuple[ResultT, ...],
    port: GovernedBatchExecutionPort[
        EffectAuthorizationT,
        ResultT,
        PayloadT,
        ClosureT,
    ],
) -> None:
    terminal = port.project_terminal(closure)
    result_terminals = tuple(port.project_result(result) for result in results)
    completed_assignment_sha256s = tuple(result.assignment_sha256 for result in result_terminals)
    expected_incomplete = design.ordered_assignment_sha256s[len(result_terminals) :]
    completed = len(result_terminals) == design.assignment_count
    if (
        terminal.design_sha256 != design.content_sha256
        or terminal.assignment_terminals != result_terminals
        or completed_assignment_sha256s != design.ordered_assignment_sha256s[: len(result_terminals)]
        or terminal.incomplete_assignment_sha256s != expected_incomplete
        or terminal.observed_peak_concurrency > design.max_concurrency
        or (terminal.status is GovernedBatchStatus.COMPLETED and not completed)
        or (terminal.status is GovernedBatchStatus.INCOMPLETE and completed and terminal.incomplete_reason is None)
    ):
        raise GovernedBatchExecutionIntegrityError(
            "batch terminal differs from its supplied design and durable prefix",
        )


def _fail_integrity[
    EffectAuthorizationT,
    ResultT,
    PayloadT,
    ClosureT,
](
    *,
    port: GovernedBatchExecutionPort[
        EffectAuthorizationT,
        ResultT,
        PayloadT,
        ClosureT,
    ],
    design: GovernedBatchDesign,
    reason: str,
) -> None:
    error = GovernedBatchExecutionIntegrityError(reason)
    closure = port.close_terminal(
        incomplete_reason=f"{type(error).__name__}: {error}",
    )
    _validate_terminal(
        design=design,
        closure=closure,
        results=port.load_results(),
        port=port,
    )
    raise error
