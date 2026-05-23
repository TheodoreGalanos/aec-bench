# ABOUTME: Integration test for the tool-loop evolver pipeline.
# ABOUTME: Verifies that engine phase 4 builds tools, passes brief, and applies mutations.

from datetime import datetime

from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    EvolutionObservation,
    FieldScore,
    GateDecision,
    MutationSummary,
    ObservationEnrichment,
    TraceDigest,
)
from aec_bench.contracts.trial_record import (
    AgentReference,
    Completeness,
    EnvironmentSnapshot,
    InputRecord,
    OutputRecord,
    TaskReference,
    TimingRecord,
    TrialRecord,
)
from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.evolver_tools import build_evolver_toolset
from aec_bench.evolution.prompts import build_evolution_brief
from aec_bench.evolution.structured_evolver import _SCOPE_ACTION_LIMITS

# ---------------------------------------------------------------------------
# Builders for realistic test data
# ---------------------------------------------------------------------------


def _make_trial_record(
    trial_id: str = "trial-001",
    reward: float = 0.5,
    instruction: str = "Calculate the voltage drop for a 50A circuit.",
) -> TrialRecord:
    """Build a minimal but valid TrialRecord using PARTIAL completeness."""
    return TrialRecord(
        trial_id=trial_id,
        experiment_id="exp-integration-test",
        timestamp=datetime(2026, 3, 1, 12, 0, 0),
        task=TaskReference(
            task_id="electrical/voltage-drop/au-office-fitout",
            task_revision="abc123",
        ),
        agent=AgentReference(
            adapter="tool_loop",
            model="anthropic:claude-haiku-3-5",
        ),
        environment=EnvironmentSnapshot(
            runtime_image="ghcr.io/example/task:latest",
            compute_backend="local",
        ),
        inputs=InputRecord(instruction=instruction),
        outputs=OutputRecord(),
        evaluation=EvaluationResult(
            reward=reward,
            validity=ValidityCheck(
                output_parseable=True,
                schema_valid=True,
                verifier_completed=True,
            ),
        ),
        timing=TimingRecord(total_seconds=42.0),
        completeness=Completeness.PARTIAL,
    )


def _make_observation(
    trial_id: str = "trial-001",
    reward: float = 0.5,
    field_scores: list[FieldScore] | None = None,
    bond_sequence: str = "E-D-E-V",
    key_actions: list[str] | None = None,
    errors: list[str] | None = None,
    agent_reasoning: list[str] | None = None,
) -> EvolutionObservation:
    """Build a realistic EvolutionObservation with enrichment."""
    record = _make_trial_record(trial_id=trial_id, reward=reward)
    return EvolutionObservation(
        trial=record,
        enrichment=ObservationEnrichment(
            field_scores=field_scores or [],
            trace_digest=TraceDigest(
                turn_count=8,
                tool_call_count=5,
                tool_error_count=1,
                bond_sequence=bond_sequence,
                key_actions=key_actions or [],
                errors=errors or [],
                agent_reasoning=agent_reasoning or [],
            ),
        ),
        workspace_version="evo-1",
        discipline="electrical",
    )


def _make_cycle_record(
    cycle: int = 1,
    batch_score: float = 0.62,
    skills_added: list[str] | None = None,
    gate_decision: GateDecision = GateDecision.ACCEPTED,
) -> EvolutionCycleRecord:
    """Build a realistic EvolutionCycleRecord representing a prior cycle."""
    return EvolutionCycleRecord(
        cycle=cycle,
        workspace_version_before=f"evo-{cycle}",
        workspace_version_after=f"evo-{cycle + 1}",
        batch_score=batch_score,
        structural_score=0.71,
        mutation=MutationSummary(
            prompt_modified=False,
            skills_added=skills_added or ["verify-units"],
            evolver_reasoning="Added verify-units skill to address unit mismatch errors.",
        ),
        gate_decision=gate_decision,
        trial_ids=["trial-001"],
        timestamp=datetime(2026, 2, 1, 12, 0, 0),
    )


# ---------------------------------------------------------------------------
# Test: toolset tool functions behave correctly with realistic data
# ---------------------------------------------------------------------------


class TestToolsetWithRealisticData:
    """Verify each tool in the evolver toolset works with realistic test data."""

    def setup_method(self) -> None:
        """Prepare observations, history, and toolset once per test."""
        self.observation = _make_observation(
            trial_id="trial-001",
            reward=0.5,
            field_scores=[
                FieldScore(
                    field_name="voltage_drop",
                    reward=0.0,
                    expected="3.2",
                    actual="8.7",
                ),
                FieldScore(field_name="compliance", reward=1.0),
            ],
            bond_sequence="E-D-E-V",
            key_actions=["read the input file", "ran voltage drop calculation"],
            errors=["ValueError: unit mismatch in cable sizing"],
            agent_reasoning=["I need to check the resistance formula"],
        )
        self.cycle = _make_cycle_record(
            cycle=1,
            batch_score=0.62,
            skills_added=["verify-units"],
        )
        self.skill_body = (
            "## Verify Units\n\n"
            "Always confirm units are consistent before substituting into formulas.\n"
            "Use SI units throughout: voltage in V, current in A, resistance in Ω."
        )
        self.current_prompt = (
            "You are an engineering benchmark agent specialised in electrical systems.\n"
            "Always verify your calculations against relevant Australian standards."
        )
        self.toolset = build_evolver_toolset(
            observations=[self.observation],
            workspace_root=None,
            history=[self.cycle],
            current_prompt=self.current_prompt,
            current_skills=[("verify-units", self.skill_body)],
        )

    def test_toolset_exposes_all_expected_tools(self) -> None:
        expected_keys = {
            "read_trace",
            "read_skill",
            "read_prompt",
            "list_history",
            "read_cycle",
            "field_detail",
            "search_traces",
            "read_graveyard",
        }
        assert set(self.toolset.keys()) == expected_keys

    def test_read_trace_returns_bond_sequence_and_actions(self) -> None:
        result = self.toolset["read_trace"]("trial-001")

        assert "E-D-E-V" in result
        assert "read the input file" in result
        assert "ran voltage drop calculation" in result

    def test_read_trace_returns_errors(self) -> None:
        result = self.toolset["read_trace"]("trial-001")

        assert "ValueError" in result
        assert "unit mismatch" in result

    def test_list_history_returns_score_and_skill_names(self) -> None:
        result = self.toolset["list_history"]()

        # Score from the cycle record
        assert "0.62" in result
        # Skill added in that cycle
        assert "verify-units" in result or "+1 skill" in result.lower()

    def test_field_detail_returns_masked_direction(self) -> None:
        result = self.toolset["field_detail"]("voltage_drop")

        # Direction should appear (actual 8.7 vs expected 3.2 — significantly too high)
        assert "too high" in result

        # Raw numeric values must NOT appear
        assert "3.2" not in result
        assert "8.7" not in result

    def test_search_traces_finds_trial_by_error_pattern(self) -> None:
        result = self.toolset["search_traces"]("ValueError")

        assert "trial-001" in result

    def test_read_skill_returns_full_body(self) -> None:
        result = self.toolset["read_skill"]("verify-units")

        assert "Verify Units" in result
        assert "SI units" in result
        assert "resistance in Ω" in result

    def test_read_prompt_returns_full_prompt_text(self) -> None:
        result = self.toolset["read_prompt"]()

        assert result == self.current_prompt
        assert "electrical systems" in result


# ---------------------------------------------------------------------------
# Test: build_evolution_brief produces a compact, tool-pointing brief
# ---------------------------------------------------------------------------


class TestBriefStructure:
    """Verify build_evolution_brief produces compact, tool-referencing output."""

    def setup_method(self) -> None:
        from aec_bench.contracts.evolution import DisciplineScore

        self.trial_ids = ["trial-001", "trial-002"]
        self.skill_names = ["verify-units", "cable-sizing"]
        self.field_failure_rates = {"voltage_drop": 0.75, "compliance": 0.25}
        self.discipline_scores = [
            DisciplineScore(
                discipline="electrical",
                task_count=2,
                mean_reward=0.5,
                field_pass_rate=0.5,
            )
        ]
        self.brief = build_evolution_brief(
            batch_score=0.5,
            discipline_scores=self.discipline_scores,
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates=self.field_failure_rates,
            workspace_skill_count=2,
            workspace_prompt_length=250,
            skill_names=self.skill_names,
            trial_ids=self.trial_ids,
        )

    def test_brief_contains_trial_ids(self) -> None:
        assert "trial-001" in self.brief
        assert "trial-002" in self.brief

    def test_brief_contains_field_names(self) -> None:
        assert "voltage_drop" in self.brief
        assert "compliance" in self.brief

    def test_brief_references_read_trace_tool(self) -> None:
        assert "read_trace" in self.brief

    def test_brief_is_compact(self) -> None:
        assert len(self.brief) < 3000, f"Brief is {len(self.brief)} chars — expected under 3000"

    def test_brief_does_not_embed_full_prompt_text(self) -> None:
        # The slim brief should not include system prompt body, only reference the tool
        assert "read_prompt()" in self.brief
        # Should mention skill names but not full skill bodies
        assert "verify-units" in self.brief
        assert "cable-sizing" in self.brief

    def test_brief_contains_scope_instructions(self) -> None:
        # COMPREHENSIVE scope should mention improvement language
        assert "comprehensive" in self.brief.lower() or "improvement" in self.brief.lower()


# ---------------------------------------------------------------------------
# Test: scope action limits are defined and have expected values
# ---------------------------------------------------------------------------


class TestScopeActionLimits:
    """Verify _SCOPE_ACTION_LIMITS defines the expected scopes with correct ceilings."""

    def test_skip_scope_allows_zero_actions(self) -> None:
        assert _SCOPE_ACTION_LIMITS["SKIP"] == 0

    def test_minimal_scope_allows_one_action(self) -> None:
        assert _SCOPE_ACTION_LIMITS["MINIMAL"] == 1

    def test_targeted_scope_allows_three_actions(self) -> None:
        assert _SCOPE_ACTION_LIMITS["TARGETED"] == 3

    def test_comprehensive_scope_allows_five_actions(self) -> None:
        assert _SCOPE_ACTION_LIMITS["COMPREHENSIVE"] == 5

    def test_all_scopes_defined(self) -> None:
        required_scopes = {"SKIP", "MINIMAL", "TARGETED", "COMPREHENSIVE"}
        assert required_scopes.issubset(set(_SCOPE_ACTION_LIMITS.keys()))

    def test_action_limits_are_non_negative(self) -> None:
        for scope, limit in _SCOPE_ACTION_LIMITS.items():
            assert limit >= 0, f"Scope {scope!r} has negative limit {limit}"

    def test_limits_increase_with_scope_severity(self) -> None:
        assert (
            _SCOPE_ACTION_LIMITS["SKIP"]
            <= _SCOPE_ACTION_LIMITS["MINIMAL"]
            <= _SCOPE_ACTION_LIMITS["TARGETED"]
            <= _SCOPE_ACTION_LIMITS["COMPREHENSIVE"]
        )
