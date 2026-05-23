# ABOUTME: Tests for shared trajectory reading utilities in the evaluation package.
# ABOUTME: Covers step grouping, status computation, and adapter type detection.

from __future__ import annotations

from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.evaluation.trajectory_reader import (
    compute_step_status,
    detect_adapter_type,
    detect_rlm_trial,
    group_by_step,
)


def _entry(
    step: int = 0,
    role: str = "assistant",
    *,
    exit_code: int | None = None,
    tool_name: str | None = None,
    metadata: dict | None = None,
) -> TrajectoryEntry:
    """Construct a minimal TrajectoryEntry for testing."""
    return TrajectoryEntry(
        step=step,
        role=role,
        exit_code=exit_code,
        tool_name=tool_name,
        metadata=metadata,
    )


class TestGroupByStep:
    def test_groups_entries_by_step_number(self) -> None:
        entries = [
            _entry(step=0, role="assistant"),
            _entry(step=0, role="tool", tool_name="bash"),
            _entry(step=1, role="assistant"),
            _entry(step=1, role="tool", tool_name="python"),
        ]
        grouped = group_by_step(entries)

        assert set(grouped.keys()) == {0, 1}
        assert len(grouped[0]) == 2
        assert len(grouped[1]) == 2

    def test_returns_sorted_dict(self) -> None:
        entries = [
            _entry(step=3, role="assistant"),
            _entry(step=1, role="assistant"),
            _entry(step=2, role="assistant"),
        ]
        grouped = group_by_step(entries)

        assert list(grouped.keys()) == [1, 2, 3]

    def test_empty_entries(self) -> None:
        grouped = group_by_step([])

        assert grouped == {}


class TestComputeStepStatus:
    def test_returns_fail_when_any_entry_has_nonzero_exit_code(self) -> None:
        entries = [
            _entry(step=0, role="tool", exit_code=0),
            _entry(step=0, role="tool", exit_code=1),
        ]
        assert compute_step_status(entries) == "fail"

    def test_returns_success_when_all_tool_results_have_zero_exit_code(self) -> None:
        entries = [
            _entry(step=0, role="tool", exit_code=0),
            _entry(step=0, role="tool", exit_code=0),
        ]
        assert compute_step_status(entries) == "success"

    def test_returns_incomplete_when_tool_entry_has_none_exit_code(self) -> None:
        entries = [
            _entry(step=0, role="tool", exit_code=None),
        ]
        assert compute_step_status(entries) == "incomplete"

    def test_returns_success_for_assistant_only_entries(self) -> None:
        entries = [
            _entry(step=0, role="assistant"),
        ]
        assert compute_step_status(entries) == "success"


class TestDetectRlmTrial:
    def test_returns_true_when_metadata_has_template_progress(self) -> None:
        entries = [
            _entry(step=0, role="assistant"),
            _entry(
                step=1,
                role="tool",
                metadata={"template_progress": {"done": 2, "total": 5}},
            ),
        ]
        assert detect_rlm_trial(entries) is True

    def test_returns_true_when_metadata_has_tokens(self) -> None:
        entries = [
            _entry(step=0, role="tool", metadata={"tokens": {"in": 100, "out": 50}}),
        ]
        assert detect_rlm_trial(entries) is True

    def test_returns_false_for_plain_entries(self) -> None:
        entries = [
            _entry(step=0, role="assistant"),
            _entry(step=1, role="tool", exit_code=0),
        ]
        assert detect_rlm_trial(entries) is False

    def test_returns_false_for_empty_entries(self) -> None:
        assert detect_rlm_trial([]) is False


class TestDetectAdapterType:
    def test_returns_lambda_rlm_when_metadata_has_phase_and_plan_state(self) -> None:
        entries = [
            _entry(
                step=0,
                role="tool",
                metadata={"phase": "investigate", "plan_state": {"sections": []}},
            ),
        ]
        assert detect_adapter_type(entries) == "lambda-rlm"

    def test_returns_rlm_when_metadata_has_template_progress(self) -> None:
        entries = [
            _entry(
                step=0,
                role="tool",
                metadata={"template_progress": {"done": 1, "total": 3}},
            ),
        ]
        assert detect_adapter_type(entries) == "rlm"

    def test_returns_rlm_when_metadata_has_tokens(self) -> None:
        entries = [
            _entry(step=0, role="tool", metadata={"tokens": {"in": 500, "out": 200}}),
        ]
        assert detect_adapter_type(entries) == "rlm"

    def test_returns_other_for_plain_entries(self) -> None:
        entries = [
            _entry(step=0, role="assistant"),
            _entry(step=1, role="tool", exit_code=0),
        ]
        assert detect_adapter_type(entries) == "other"

    def test_returns_other_for_empty_entries(self) -> None:
        assert detect_adapter_type([]) == "other"

    def test_lambda_rlm_takes_priority_over_rlm(self) -> None:
        """When entries have both lambda-RLM and RLM markers, lambda-rlm wins."""
        entries = [
            _entry(
                step=0,
                role="tool",
                metadata={"phase": "propose", "plan_state": {"sections": []}},
            ),
            _entry(
                step=1,
                role="tool",
                metadata={"template_progress": {"done": 1, "total": 3}},
            ),
        ]
        assert detect_adapter_type(entries) == "lambda-rlm"
