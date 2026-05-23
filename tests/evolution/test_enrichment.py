# ABOUTME: Tests for the evolution enrichment pipeline that converts TrialRecords to observations.
# ABOUTME: Covers field score extraction, trace digest building, and full observation assembly.

from aec_bench.contracts.evolution import FieldScore, TraceDigest
from aec_bench.evaluation.behavioral import BondType, TurnClassification
from tests.support.trial_record_factories import make_trial_record


class TestExtractFieldScores:
    def test_extracts_from_breakdown(self) -> None:
        from aec_bench.evolution.enrichment import extract_field_scores

        record = make_trial_record(
            evaluation={
                "reward": 0.67,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
                "breakdown": {
                    "voltage_drop_v": 1.0,
                    "voltage_drop_pct": 1.0,
                    "compliance": 0.0,
                },
            },
        )

        result = extract_field_scores(record)

        assert len(result) == 3
        by_name = {fs.field_name: fs for fs in result}
        assert by_name["voltage_drop_v"].reward == 1.0
        assert by_name["voltage_drop_pct"].reward == 1.0
        assert by_name["compliance"].reward == 0.0
        for field_score in result:
            assert isinstance(field_score, FieldScore)

    def test_empty_breakdown(self) -> None:
        from aec_bench.evolution.enrichment import extract_field_scores

        record = make_trial_record()
        # Default record has no breakdown
        result = extract_field_scores(record)

        assert result == []


class TestExtractFieldScoresWithDetails:
    """Tests for expected/actual population from ground_truth and actual sub-dicts."""

    def test_extracts_expected_from_ground_truth(self) -> None:
        """When breakdown has ground_truth and actual, expected/actual values are populated."""
        from aec_bench.evolution.enrichment import extract_field_scores

        record = make_trial_record(
            evaluation={
                "reward": 0.5,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
                "breakdown": {
                    "vc_mv_per_a_m": 0.0,
                    "voltage_drop_pct": 1.0,
                    "ground_truth": {"vc_mv_per_a_m": 6.18, "voltage_drop_pct": 2.5},
                    "actual": {"vc_mv_per_a_m": 8.69, "voltage_drop_pct": 2.5},
                },
            },
        )

        result = extract_field_scores(record)

        assert len(result) == 2
        by_name = {fs.field_name: fs for fs in result}

        assert by_name["vc_mv_per_a_m"].reward == 0.0
        assert by_name["vc_mv_per_a_m"].expected == "6.18"
        assert by_name["vc_mv_per_a_m"].actual == "8.69"

        assert by_name["voltage_drop_pct"].reward == 1.0
        assert by_name["voltage_drop_pct"].expected == "2.5"
        assert by_name["voltage_drop_pct"].actual == "2.5"

    def test_handles_breakdown_without_ground_truth(self) -> None:
        """When breakdown has no ground_truth key, expected/actual stay None."""
        from aec_bench.evolution.enrichment import extract_field_scores

        record = make_trial_record(
            evaluation={
                "reward": 0.67,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
                "breakdown": {
                    "voltage_drop_v": 1.0,
                    "compliance": 0.0,
                },
            },
        )

        result = extract_field_scores(record)

        assert len(result) == 2
        for fs in result:
            assert fs.expected is None
            assert fs.actual is None

    def test_partial_ground_truth_coverage(self) -> None:
        """When ground_truth only covers some fields, others remain None."""
        from aec_bench.evolution.enrichment import extract_field_scores

        record = make_trial_record(
            evaluation={
                "reward": 0.5,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
                "breakdown": {
                    "field_a": 1.0,
                    "field_b": 0.0,
                    "ground_truth": {"field_a": 10},
                    "actual": {"field_a": 10},
                },
            },
        )

        result = extract_field_scores(record)
        by_name = {fs.field_name: fs for fs in result}

        assert by_name["field_a"].expected == "10"
        assert by_name["field_a"].actual == "10"
        assert by_name["field_b"].expected is None
        assert by_name["field_b"].actual is None

    def test_ground_truth_and_actual_not_included_as_field_scores(self) -> None:
        """The ground_truth and actual dict keys should not appear as FieldScores."""
        from aec_bench.evolution.enrichment import extract_field_scores

        record = make_trial_record(
            evaluation={
                "reward": 0.5,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
                "breakdown": {
                    "field_a": 1.0,
                    "ground_truth": {"field_a": 10},
                    "actual": {"field_a": 10},
                },
            },
        )

        result = extract_field_scores(record)
        field_names = {fs.field_name for fs in result}

        assert "ground_truth" not in field_names
        assert "actual" not in field_names
        assert "field_a" in field_names


class TestBuildTraceDigest:
    def test_builds_from_classifications(self) -> None:
        from aec_bench.evolution.enrichment import build_trace_digest

        classifications = [
            TurnClassification(turn_index=0, bond_type=BondType.EXECUTION, confidence=0.9),
            TurnClassification(turn_index=1, bond_type=BondType.EXECUTION, confidence=0.8),
            TurnClassification(turn_index=2, bond_type=BondType.VERIFICATION, confidence=0.85),
            TurnClassification(turn_index=3, bond_type=BondType.DELIBERATION, confidence=0.7),
            TurnClassification(turn_index=4, bond_type=BondType.EXECUTION, confidence=0.95),
        ]

        result = build_trace_digest(
            classifications=classifications,
            tool_call_count=10,
            tool_error_count=2,
        )

        assert isinstance(result, TraceDigest)
        assert result.bond_sequence == "E-E-V-D-E"
        assert result.turn_count == 5
        assert result.tool_call_count == 10
        assert result.tool_error_count == 2

    def test_empty_classifications(self) -> None:
        from aec_bench.evolution.enrichment import build_trace_digest

        result = build_trace_digest(
            classifications=[],
            tool_call_count=0,
            tool_error_count=0,
        )

        assert result.bond_sequence == ""
        assert result.turn_count == 0

    def test_key_actions_flow_through(self) -> None:
        """key_actions passed to build_trace_digest appear in the resulting TraceDigest."""
        from aec_bench.evolution.enrichment import build_trace_digest

        actions = ["bash(ls -la)", "read_file(/workspace/output.md)"]
        result = build_trace_digest(
            classifications=[],
            tool_call_count=2,
            tool_error_count=0,
            key_actions=actions,
        )

        assert result.key_actions == actions

    def test_errors_flow_through(self) -> None:
        """errors passed to build_trace_digest appear in the resulting TraceDigest."""
        from aec_bench.evolution.enrichment import build_trace_digest

        errors = ["FileNotFoundError: /workspace/missing.txt"]
        result = build_trace_digest(
            classifications=[],
            tool_call_count=1,
            tool_error_count=1,
            errors=errors,
        )

        assert result.errors == errors

    def test_agent_reasoning_flow_through(self) -> None:
        """agent_reasoning passed to build_trace_digest appears in the resulting TraceDigest."""
        from aec_bench.evolution.enrichment import build_trace_digest

        reasoning = ["I need to check the voltage drop formula first."]
        result = build_trace_digest(
            classifications=[],
            tool_call_count=0,
            tool_error_count=0,
            agent_reasoning=reasoning,
        )

        assert result.agent_reasoning == reasoning

    def test_optional_fields_default_to_empty_lists(self) -> None:
        """When key_actions, errors, and agent_reasoning are omitted they default to []."""
        from aec_bench.evolution.enrichment import build_trace_digest

        result = build_trace_digest(
            classifications=[],
            tool_call_count=0,
            tool_error_count=0,
        )

        assert result.key_actions == []
        assert result.errors == []
        assert result.agent_reasoning == []

    def test_all_optional_fields_together(self) -> None:
        """All three optional fields can be passed simultaneously."""
        from aec_bench.evolution.enrichment import build_trace_digest

        classifications = [
            TurnClassification(turn_index=0, bond_type=BondType.EXECUTION, confidence=0.9),
        ]
        actions = ["bash(echo hello)"]
        errors = ["Error: command failed"]
        reasoning = ["Let me think about this."]

        result = build_trace_digest(
            classifications=classifications,
            tool_call_count=1,
            tool_error_count=1,
            key_actions=actions,
            errors=errors,
            agent_reasoning=reasoning,
        )

        assert result.key_actions == actions
        assert result.errors == errors
        assert result.agent_reasoning == reasoning
        assert result.bond_sequence == "E"
