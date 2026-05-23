# ABOUTME: Tests for the evolver investigation tool functions.
# ABOUTME: Covers read_trace, read_skill, list_history, read_cycle, field_detail, search_traces.

from datetime import datetime

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    EvolutionObservation,
    FieldScore,
    GateDecision,
    MutationSummary,
    ObservationEnrichment,
    TraceDigest,
)
from aec_bench.evolution.evolver_tools import build_evolver_toolset
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_observation(
    trial_id: str = "trial-001",
    discipline: str = "electrical",
    reward: float = 0.8,
    field_scores: list[FieldScore] | None = None,
    bond_sequence: str = "E-D-E-V",
    key_actions: list[str] | None = None,
    errors: list[str] | None = None,
    agent_reasoning: list[str] | None = None,
) -> EvolutionObservation:
    record = make_trial_record(
        trial_id=trial_id,
        evaluation={
            "reward": reward,
            "validity": {
                "output_parseable": True,
                "schema_valid": True,
                "verifier_completed": True,
            },
        },
    )
    return EvolutionObservation(
        trial=record,
        enrichment=ObservationEnrichment(
            field_scores=field_scores or [],
            trace_digest=TraceDigest(
                turn_count=4,
                tool_call_count=3,
                tool_error_count=0,
                bond_sequence=bond_sequence,
                key_actions=key_actions or [],
                errors=errors or [],
                agent_reasoning=agent_reasoning or [],
            ),
        ),
        workspace_version="evo-1",
        discipline=discipline,
    )


def _make_cycle_record(
    cycle: int = 1,
    batch_score: float = 0.75,
    structural_score: float | None = 0.82,
    gate_decision: GateDecision = GateDecision.ACCEPTED,
    trial_ids: list[str] | None = None,
    mutation: MutationSummary | None = None,
) -> EvolutionCycleRecord:
    return EvolutionCycleRecord(
        cycle=cycle,
        workspace_version_before=f"evo-{cycle}",
        workspace_version_after=f"evo-{cycle + 1}",
        batch_score=batch_score,
        structural_score=structural_score,
        mutation=mutation,
        gate_decision=gate_decision,
        trial_ids=trial_ids or ["trial-001"],
        timestamp=datetime(2026, 1, cycle, 12, 0, 0),
    )


def _build_toolset(**kwargs):
    """Build a default toolset with minimal valid data, overriding with kwargs."""
    defaults = dict(
        observations=[],
        workspace_root=None,
        history=[],
        current_prompt="You are a helpful engineering agent.",
        current_skills=[],
    )
    defaults.update(kwargs)
    return build_evolver_toolset(**defaults)


# ---------------------------------------------------------------------------
# TestReadTrace
# ---------------------------------------------------------------------------


class TestReadTrace:
    def test_returns_formatted_trace_with_bond_sequence(self) -> None:
        obs = _make_observation(
            trial_id="trial-abc",
            bond_sequence="E-D-E-V",
            key_actions=["read_file input.json", "write_file output.json"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["read_trace"]("trial-abc")

        assert "trial-abc" in result
        assert "E-D-E-V" in result

    def test_returns_key_actions(self) -> None:
        obs = _make_observation(
            trial_id="trial-abc",
            key_actions=["ran voltage drop calculation", "checked compliance"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["read_trace"]("trial-abc")

        assert "ran voltage drop calculation" in result
        assert "checked compliance" in result

    def test_returns_errors(self) -> None:
        obs = _make_observation(
            trial_id="trial-abc",
            errors=["tool_call failed: FileNotFoundError"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["read_trace"]("trial-abc")

        assert "tool_call failed: FileNotFoundError" in result

    def test_returns_error_for_unknown_trial_id(self) -> None:
        obs = _make_observation(trial_id="trial-001")
        tools = _build_toolset(observations=[obs])
        result = tools["read_trace"]("nonexistent-trial")

        assert "not found" in result.lower()
        assert "trial-001" in result

    def test_shows_available_ids_when_trial_missing(self) -> None:
        obs1 = _make_observation(trial_id="trial-001")
        obs2 = _make_observation(trial_id="trial-002")
        tools = _build_toolset(observations=[obs1, obs2])
        result = tools["read_trace"]("missing-id")

        assert "trial-001" in result
        assert "trial-002" in result

    def test_includes_field_results_with_masked_direction(self) -> None:
        obs = _make_observation(
            trial_id="trial-abc",
            reward=0.5,
            field_scores=[
                FieldScore(field_name="v_drop", reward=0.0, expected="3.2", actual="8.1"),
                FieldScore(field_name="compliance", reward=1.0),
            ],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["read_trace"]("trial-abc")

        assert "v_drop" in result
        assert "FAIL" in result
        assert "compliance" in result
        assert "PASS" in result
        # Raw values must not appear
        assert "3.2" not in result
        assert "8.1" not in result

    def test_includes_agent_reasoning(self) -> None:
        obs = _make_observation(
            trial_id="trial-abc",
            agent_reasoning=["I need to check the cable sizing formula first."],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["read_trace"]("trial-abc")

        assert "I need to check the cable sizing formula first." in result


# ---------------------------------------------------------------------------
# TestReadSkill
# ---------------------------------------------------------------------------


class TestReadSkill:
    def test_returns_full_skill_body(self) -> None:
        body = "## Voltage Drop Formula\n\nUse V = I * R where R = ρL/A.\nReference AS/NZS 3008."
        tools = _build_toolset(current_skills=[("voltage-drop", body)])
        result = tools["read_skill"]("voltage-drop")

        assert body in result
        # Must not truncate
        assert "ρL/A" in result
        assert "AS/NZS 3008" in result

    def test_returns_error_for_unknown_skill(self) -> None:
        tools = _build_toolset(current_skills=[("voltage-drop", "body text")])
        result = tools["read_skill"]("nonexistent-skill")

        assert "not found" in result.lower()

    def test_shows_available_skills_when_not_found(self) -> None:
        tools = _build_toolset(
            current_skills=[
                ("voltage-drop", "body 1"),
                ("cable-sizing", "body 2"),
            ]
        )
        result = tools["read_skill"]("missing-skill")

        assert "voltage-drop" in result
        assert "cable-sizing" in result

    def test_returns_error_when_no_skills(self) -> None:
        tools = _build_toolset(current_skills=[])
        result = tools["read_skill"]("anything")

        assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# TestReadPrompt
# ---------------------------------------------------------------------------


class TestReadPrompt:
    def test_returns_full_prompt_text(self) -> None:
        prompt = "You are a helpful engineering agent with deep expertise in electrical systems."
        tools = _build_toolset(current_prompt=prompt)
        result = tools["read_prompt"]()

        assert result == prompt

    def test_returns_prompt_unchanged(self) -> None:
        prompt = "Line 1\nLine 2\n\n## Section\nContent here."
        tools = _build_toolset(current_prompt=prompt)
        result = tools["read_prompt"]()

        assert result == prompt


# ---------------------------------------------------------------------------
# TestListHistory
# ---------------------------------------------------------------------------


class TestListHistory:
    def test_returns_score_trajectory(self) -> None:
        cycle1 = _make_cycle_record(cycle=1, batch_score=0.65)
        cycle2 = _make_cycle_record(cycle=2, batch_score=0.72)
        tools = _build_toolset(history=[cycle1, cycle2])
        result = tools["list_history"]()

        assert "0.65" in result
        assert "0.72" in result

    def test_includes_gate_decision(self) -> None:
        cycle = _make_cycle_record(gate_decision=GateDecision.REJECTED)
        tools = _build_toolset(history=[cycle])
        result = tools["list_history"]()

        assert "rejected" in result.lower()

    def test_includes_mutation_info(self) -> None:
        mutation = MutationSummary(
            prompt_modified=True,
            skills_added=["cable-sizing"],
            evolver_reasoning="Prompt needed clarity on cable sizing steps.",
        )
        cycle = _make_cycle_record(mutation=mutation)
        tools = _build_toolset(history=[cycle])
        result = tools["list_history"]()

        assert "prompt" in result.lower()
        assert "cable-sizing" in result or "+1 skill" in result.lower()

    def test_includes_evolver_reasoning(self) -> None:
        mutation = MutationSummary(evolver_reasoning="Added voltage-drop skill to address 80% failure rate.")
        cycle = _make_cycle_record(mutation=mutation)
        tools = _build_toolset(history=[cycle])
        result = tools["list_history"]()

        assert "Added voltage-drop skill to address 80% failure rate." in result

    def test_returns_no_history_message_when_empty(self) -> None:
        tools = _build_toolset(history=[])
        result = tools["list_history"]()

        assert "no" in result.lower() or "empty" in result.lower() or "available" in result.lower()


# ---------------------------------------------------------------------------
# TestReadCycle
# ---------------------------------------------------------------------------


class TestReadCycle:
    def test_returns_detailed_cycle_info(self) -> None:
        cycle = _make_cycle_record(
            cycle=3,
            batch_score=0.78,
            structural_score=0.65,
            trial_ids=["trial-001", "trial-002"],
        )
        tools = _build_toolset(history=[cycle])
        result = tools["read_cycle"](3)

        assert "0.78" in result
        assert "0.65" in result
        assert "trial-001" in result
        assert "trial-002" in result

    def test_returns_mutation_details(self) -> None:
        mutation = MutationSummary(
            prompt_modified=False,
            skills_added=["new-skill"],
            skills_removed=["old-skill"],
            evolver_reasoning="Replaced outdated skill.",
        )
        cycle = _make_cycle_record(cycle=2, mutation=mutation)
        tools = _build_toolset(history=[cycle])
        result = tools["read_cycle"](2)

        assert "new-skill" in result
        assert "old-skill" in result
        assert "Replaced outdated skill." in result

    def test_returns_error_for_missing_cycle(self) -> None:
        cycle = _make_cycle_record(cycle=1)
        tools = _build_toolset(history=[cycle])
        result = tools["read_cycle"](99)

        assert "not found" in result.lower()
        assert "1" in result

    def test_shows_available_cycles_when_missing(self) -> None:
        cycles = [_make_cycle_record(cycle=i) for i in [2, 4, 7]]
        tools = _build_toolset(history=cycles)
        result = tools["read_cycle"](99)

        assert "2" in result
        assert "4" in result
        assert "7" in result


# ---------------------------------------------------------------------------
# TestFieldDetail
# ---------------------------------------------------------------------------


class TestFieldDetail:
    def test_returns_pass_fail_status(self) -> None:
        obs1 = _make_observation(
            trial_id="trial-001",
            field_scores=[FieldScore(field_name="v_drop", reward=1.0)],
        )
        obs2 = _make_observation(
            trial_id="trial-002",
            field_scores=[FieldScore(field_name="v_drop", reward=0.0, expected="3.2", actual="8.1")],
        )
        tools = _build_toolset(observations=[obs1, obs2])
        result = tools["field_detail"]("v_drop")

        assert "PASS" in result
        assert "FAIL" in result

    def test_returns_masked_error_direction_not_raw_values(self) -> None:
        obs = _make_observation(
            trial_id="trial-001",
            field_scores=[FieldScore(field_name="cable_size", reward=0.0, expected="16.0", actual="50.0")],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["field_detail"]("cable_size")

        # Raw values must NOT appear
        assert "16.0" not in result
        assert "50.0" not in result
        # Direction should appear
        assert "too high" in result or "direction" in result.lower() or "high" in result

    def test_does_not_expose_expected_values(self) -> None:
        obs = _make_observation(
            trial_id="trial-001",
            field_scores=[FieldScore(field_name="compliance", reward=0.0, expected="1.05", actual="0.87")],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["field_detail"]("compliance")

        assert "1.05" not in result
        assert "0.87" not in result

    def test_returns_error_for_unknown_field(self) -> None:
        obs = _make_observation(
            field_scores=[FieldScore(field_name="v_drop", reward=1.0)],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["field_detail"]("nonexistent_field")

        assert "not found" in result.lower() or "no observation" in result.lower()

    def test_includes_all_trials_for_field(self) -> None:
        obs1 = _make_observation(
            trial_id="trial-001",
            field_scores=[FieldScore(field_name="v_drop", reward=1.0)],
        )
        obs2 = _make_observation(
            trial_id="trial-002",
            field_scores=[FieldScore(field_name="v_drop", reward=0.0, expected="3.2", actual="8.1")],
        )
        obs3 = _make_observation(
            trial_id="trial-003",
            field_scores=[FieldScore(field_name="other_field", reward=0.0)],
        )
        tools = _build_toolset(observations=[obs1, obs2, obs3])
        result = tools["field_detail"]("v_drop")

        assert "trial-001" in result
        assert "trial-002" in result
        # obs3 has a different field, should not appear
        assert "trial-003" not in result


# ---------------------------------------------------------------------------
# TestSearchTraces
# ---------------------------------------------------------------------------


class TestSearchTraces:
    def test_finds_pattern_in_key_actions(self) -> None:
        obs = _make_observation(
            trial_id="trial-001",
            key_actions=["calculated voltage drop using Ohm's law", "checked AS/NZS 3008"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["search_traces"]("voltage drop")

        assert "trial-001" in result
        assert "voltage drop" in result.lower()

    def test_finds_pattern_in_errors(self) -> None:
        obs = _make_observation(
            trial_id="trial-002",
            errors=["FileNotFoundError: cannot open drawing.pdf"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["search_traces"]("FileNotFoundError")

        assert "trial-002" in result

    def test_finds_pattern_in_agent_reasoning(self) -> None:
        obs = _make_observation(
            trial_id="trial-003",
            agent_reasoning=["The cable resistance is the dominant term here."],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["search_traces"]("cable resistance")

        assert "trial-003" in result

    def test_case_insensitive_search(self) -> None:
        obs = _make_observation(
            trial_id="trial-004",
            key_actions=["Checked VOLTAGE DROP compliance"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["search_traces"]("voltage drop")

        assert "trial-004" in result

    def test_returns_no_matches_message_when_not_found(self) -> None:
        obs = _make_observation(
            trial_id="trial-001",
            key_actions=["did something unrelated"],
        )
        tools = _build_toolset(observations=[obs])
        result = tools["search_traces"]("xyz-pattern-not-present")

        assert "no match" in result.lower() or "not found" in result.lower()

    def test_caps_at_30_matches(self) -> None:
        observations = [
            _make_observation(
                trial_id=f"trial-{i:03d}",
                key_actions=["common action matching pattern"],
            )
            for i in range(50)
        ]
        tools = _build_toolset(observations=observations)
        result = tools["search_traces"]("common action")

        # Count number of matches: each line contains a trial ID
        match_lines = [line for line in result.split("\n") if "trial-" in line]
        assert len(match_lines) <= 30

    def test_multiple_trials_with_pattern(self) -> None:
        obs1 = _make_observation(trial_id="trial-001", key_actions=["used python script"])
        obs2 = _make_observation(trial_id="trial-002", key_actions=["ran python calculation"])
        obs3 = _make_observation(trial_id="trial-003", key_actions=["wrote output"])
        tools = _build_toolset(observations=[obs1, obs2, obs3])
        result = tools["search_traces"]("python")

        assert "trial-001" in result
        assert "trial-002" in result
        assert "trial-003" not in result


# ---------------------------------------------------------------------------
# TestReadGraveyard
# ---------------------------------------------------------------------------


class TestReadGraveyard:
    def test_read_graveyard_returns_formatted_entries(self) -> None:
        """read_graveyard() returns enriched failure info."""
        from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard

        graveyard = MutationGraveyard()
        graveyard.insert(
            GraveyardEntry(
                cycle=1,
                strategy="conservative",
                mutation_description="Added cable-sizing skill",
                score_before=0.5,
                score_after=0.3,
                workspace_version="evo-1",
                failure_reason="Score delta: -0.20",
                field_failures={"vc_mv_per_a_m": "too_high"},
                detected_patterns=["no_verification"],
                mutation_actions=[{"action_type": "write_skill", "skill_name": "cable-ref"}],
                investigation_summary="Agent used wrong table values.",
            )
        )

        toolset = build_evolver_toolset(
            observations=[],
            workspace_root=None,
            history=[],
            current_prompt="prompt",
            current_skills=[],
            graveyard=graveyard,
        )

        result = toolset["read_graveyard"]()
        assert "cable-sizing skill" in result
        assert "vc_mv_per_a_m" in result
        assert "no_verification" in result
        assert "wrong table values" in result

    def test_read_graveyard_empty(self) -> None:
        """read_graveyard() returns helpful message when empty."""
        from aec_bench.evolution.graveyard import MutationGraveyard

        toolset = build_evolver_toolset(
            observations=[],
            workspace_root=None,
            history=[],
            current_prompt="prompt",
            current_skills=[],
            graveyard=MutationGraveyard(),
        )

        result = toolset["read_graveyard"]()
        assert "No failed mutations" in result

    def test_read_graveyard_none_graveyard(self) -> None:
        """read_graveyard() handles None graveyard gracefully."""
        toolset = build_evolver_toolset(
            observations=[],
            workspace_root=None,
            history=[],
            current_prompt="prompt",
            current_skills=[],
            graveyard=None,
        )

        result = toolset["read_graveyard"]()
        assert "No failed mutations" in result

    def test_read_graveyard_shows_cycle_and_strategy(self) -> None:
        """read_graveyard() includes cycle number and strategy name."""
        from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard

        graveyard = MutationGraveyard()
        graveyard.insert(
            GraveyardEntry(
                cycle=5,
                strategy="aggressive",
                mutation_description="Rewrote system prompt",
                score_before=0.6,
                score_after=0.4,
                workspace_version="evo-5",
                failure_reason="Score delta: -0.20",
            )
        )

        toolset = build_evolver_toolset(
            observations=[],
            workspace_root=None,
            history=[],
            current_prompt="prompt",
            current_skills=[],
            graveyard=graveyard,
        )

        result = toolset["read_graveyard"]()
        assert "Cycle 5" in result
        assert "aggressive" in result

    def test_read_graveyard_respects_limit(self) -> None:
        """read_graveyard(limit=N) shows at most N entries."""
        from aec_bench.evolution.graveyard import GraveyardEntry, MutationGraveyard

        graveyard = MutationGraveyard()
        for i in range(10):
            graveyard.insert(
                GraveyardEntry(
                    cycle=i,
                    strategy="conservative",
                    mutation_description=f"Mutation {i}",
                    score_before=0.5,
                    score_after=0.3,
                    workspace_version=f"evo-{i}",
                    failure_reason="Score delta: -0.20",
                )
            )

        toolset = build_evolver_toolset(
            observations=[],
            workspace_root=None,
            history=[],
            current_prompt="prompt",
            current_skills=[],
            graveyard=graveyard,
        )

        result = toolset["read_graveyard"](limit=3)
        # Count "### Cycle" headers — each entry produces one
        cycle_headers = [line for line in result.split("\n") if line.startswith("### Cycle")]
        assert len(cycle_headers) == 3
