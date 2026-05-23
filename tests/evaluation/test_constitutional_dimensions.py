# ABOUTME: Tests for mechanical constitutional evaluation dimensions.
# ABOUTME: Covers context efficiency, state utilisation, time-to-first-output, and stall count.

from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.evaluation.constitutional_dimensions import compute_constitutional_dimensions


def _entry(**kwargs) -> TrajectoryEntry:
    defaults = {
        "step": 0,
        "role": "tool",
        "tool_name": "repl",
    }
    defaults.update(kwargs)
    return TrajectoryEntry(**defaults)


class TestComputeConstitutionalDimensions:
    def test_empty_trajectory(self) -> None:
        dims = compute_constitutional_dimensions(trajectory=[])
        assert dims.context_efficiency_ratio == 0.0
        assert dims.state_utilisation_ratio == 0.0
        assert dims.turns_to_first_output is None
        assert dims.stall_count == 0

    def test_context_efficiency_ratio(self) -> None:
        # 3 repl tool results: 1 metadata-like (short "Output: N chars"), 2 verbatim
        entries = [
            _entry(step=0, stdout="Output: 5,000 chars.\nPreview: ...", tool_name="repl"),
            _entry(step=1, stdout="hello world", tool_name="repl"),
            _entry(step=2, stdout="another output", tool_name="repl"),
        ]
        dims = compute_constitutional_dimensions(trajectory=entries)
        # 1/3 entries match metadata pattern
        assert abs(dims.context_efficiency_ratio - (1 / 3)) < 1e-6

    def test_state_utilisation_ratio(self) -> None:
        entries = [
            _entry(step=0, metadata={"new_vars": ["data"], "scratchpad_writes": 1}),
            _entry(step=1, metadata={"new_vars": [], "scratchpad_writes": 0}),
            _entry(step=2, metadata={"new_vars": ["x", "y"], "scratchpad_writes": 2}),
        ]
        dims = compute_constitutional_dimensions(trajectory=entries)
        # 2/3 steps created state
        assert abs(dims.state_utilisation_ratio - (2 / 3)) < 1e-6

    def test_turns_to_first_output(self) -> None:
        entries = [
            _entry(step=0, tool_name="repl", command="DOCS()"),
            _entry(step=1, tool_name="repl", command="READ('doc1')"),
            _entry(
                step=2,
                tool_name="repl",
                command="FILL('intro', data)",
                metadata={"section_filled": "intro"},
            ),
            _entry(step=3, tool_name="repl"),
        ]
        dims = compute_constitutional_dimensions(trajectory=entries)
        assert dims.turns_to_first_output == 2

    def test_turns_to_first_output_never(self) -> None:
        entries = [
            _entry(step=0),
            _entry(step=1),
            _entry(step=2),
        ]
        dims = compute_constitutional_dimensions(trajectory=entries)
        assert dims.turns_to_first_output is None

    def test_stall_count(self) -> None:
        # Trajectory with a 4-turn run of no progress
        entries = [
            _entry(step=0, metadata={"sections_filled": 0}),
            _entry(step=1, metadata={"sections_filled": 0}),
            _entry(step=2, metadata={"sections_filled": 0}),
            _entry(step=3, metadata={"sections_filled": 0}),
            _entry(step=4, metadata={"sections_filled": 1}),
            _entry(step=5, metadata={"sections_filled": 1}),
            _entry(step=6, metadata={"sections_filled": 1}),
            _entry(step=7, metadata={"sections_filled": 1}),
        ]
        dims = compute_constitutional_dimensions(trajectory=entries, stall_threshold=3)
        # Two stall events: steps 0-3 (len 4) and steps 4-7 (len 4 after first fill)
        # Each stall counted once at threshold crossing
        assert dims.stall_count == 2
