# ABOUTME: Tests for the trace query tool that lets the evolver inspect trace slices.
# ABOUTME: Covers turn range filtering, bond type filtering, and error-only queries.

from aec_bench.contracts.evolution import TraceQueryRequest, TraceSlice
from aec_bench.evaluation.behavioral import BondType, TurnClassification
from aec_bench.evolution.trace_query import execute_trace_query


def _make_turn(
    turn_index: int,
    *,
    role: str = "assistant",
    content: str = "text",
    tool_calls: list[str] | None = None,
    tool_outputs: list[str] | None = None,
    is_error: bool = False,
) -> dict:
    return {
        "turn_index": turn_index,
        "role": role,
        "content": content,
        "tool_calls": tool_calls or [],
        "tool_outputs": tool_outputs or [],
        "is_error": is_error,
    }


def _make_classification(
    turn_index: int,
    bond_type: BondType,
    confidence: float = 0.9,
) -> TurnClassification:
    return TurnClassification(
        turn_index=turn_index,
        bond_type=bond_type,
        confidence=confidence,
    )


class TestExecuteTraceQuery:
    def test_full_trace_no_filter(self) -> None:
        turns = [
            _make_turn(0),
            _make_turn(1),
            _make_turn(2),
        ]
        classifications = [
            _make_classification(0, BondType.EXECUTION),
            _make_classification(1, BondType.DELIBERATION),
            _make_classification(2, BondType.VERIFICATION),
        ]
        query = TraceQueryRequest(trial_id="trial-001")

        result = execute_trace_query(query, turns=turns, classifications=classifications)

        assert isinstance(result, TraceSlice)
        assert result.trial_id == "trial-001"
        assert len(result.turns) == 3
        assert result.turns[0].turn_index == 0
        assert result.turns[1].turn_index == 1
        assert result.turns[2].turn_index == 2

    def test_turn_range_filter(self) -> None:
        turns = [_make_turn(i) for i in range(5)]
        classifications = [_make_classification(i, BondType.EXECUTION) for i in range(5)]
        query = TraceQueryRequest(trial_id="trial-002", turn_range=(1, 3))

        result = execute_trace_query(query, turns=turns, classifications=classifications)

        assert len(result.turns) == 3
        indices = [t.turn_index for t in result.turns]
        assert indices == [1, 2, 3]

    def test_bond_type_filter(self) -> None:
        turns = [
            _make_turn(0),
            _make_turn(1),
            _make_turn(2),
        ]
        classifications = [
            _make_classification(0, BondType.EXECUTION),
            _make_classification(1, BondType.VERIFICATION),
            _make_classification(2, BondType.EXECUTION),
        ]
        query = TraceQueryRequest(trial_id="trial-003", bond_type_filter=BondType.EXECUTION)

        result = execute_trace_query(query, turns=turns, classifications=classifications)

        assert len(result.turns) == 2
        for turn in result.turns:
            assert turn.bond_type == BondType.EXECUTION

    def test_errors_only_filter(self) -> None:
        turns = [
            _make_turn(0, is_error=True),
            _make_turn(1, is_error=False),
        ]
        classifications = [
            _make_classification(0, BondType.EXECUTION),
            _make_classification(1, BondType.EXECUTION),
        ]
        query = TraceQueryRequest(trial_id="trial-004", errors_only=True)

        result = execute_trace_query(query, turns=turns, classifications=classifications)

        assert len(result.turns) == 1
        assert result.turns[0].turn_index == 0
        assert result.turns[0].is_error is True

    def test_empty_result(self) -> None:
        turns: list[dict] = []
        classifications: list[TurnClassification] = []
        query = TraceQueryRequest(
            trial_id="trial-005",
            bond_type_filter=BondType.EXPLORATION,
        )

        result = execute_trace_query(query, turns=turns, classifications=classifications)

        assert isinstance(result, TraceSlice)
        assert result.trial_id == "trial-005"
        assert result.turns == []
        assert len(result.context) > 0
