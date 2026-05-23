# ABOUTME: Tests for the RLM three-level error capture and recovery tracking module.
# ABOUTME: Covers ErrorLevel enum, ErrorRecord dataclass, and ErrorTracker behaviour.
"""Tests for RLM 3-level error capture and recovery tracking."""

from aec_bench.adapters.rlm.errors import ErrorLevel, ErrorTracker


def test_record_repl_error() -> None:
    tracker = ErrorTracker()
    tracker.record(
        level=ErrorLevel.REPL,
        iteration=3,
        error="NameError: name 'foo' is not defined",
        code_attempted="print(foo)",
    )
    assert len(tracker.errors) == 1
    assert tracker.errors[0].level == ErrorLevel.REPL
    assert tracker.errors[0].iteration == 3


def test_record_recovery_attempt() -> None:
    tracker = ErrorTracker()
    tracker.record(
        level=ErrorLevel.REPL,
        iteration=3,
        error="NameError: name 'foo' is not defined",
        code_attempted="print(foo)",
    )
    tracker.record_recovery(iteration=4, succeeded=True)
    assert tracker.errors[0].recovery_iteration == 4
    assert tracker.errors[0].recovery_succeeded


def test_unrecovered_errors_are_tracked() -> None:
    tracker = ErrorTracker()
    tracker.record(
        level=ErrorLevel.SUBCALL,
        iteration=5,
        error="Timeout after 30s",
    )
    assert len(tracker.unrecovered_errors) == 1


def test_error_summary_for_trajectory() -> None:
    tracker = ErrorTracker()
    tracker.record(
        level=ErrorLevel.REPL,
        iteration=1,
        error="SyntaxError: invalid syntax",
        code_attempted="def foo(:",
    )
    tracker.record_recovery(iteration=2, succeeded=True)
    tracker.record(
        level=ErrorLevel.TEMPLATE,
        iteration=5,
        error="Section 'methodology' depends on 'design' which is not filled",
    )
    summary = tracker.summary()
    assert summary["total_errors"] == 2
    assert summary["recovered"] == 1
    assert summary["unrecovered"] == 1
