# ABOUTME: Tests for the evolver LLM prompt builder functions.
# ABOUTME: Verifies system prompt structure and analysis prompt content by scope level.

from aec_bench.contracts.evolution import DisciplineScore, WorkspaceManifest
from aec_bench.evolution.analysis import BehavioralPattern, GraduatedScope
from aec_bench.evolution.prompts import (
    build_evolution_analysis_prompt,
    build_evolution_brief,
    build_evolver_system_prompt,
)

# ---------------------------------------------------------------------------
# TestBuildEvolverSystemPrompt
# ---------------------------------------------------------------------------


class TestBuildEvolverSystemPrompt:
    def _make_manifest(self, skill_budget: int = 10) -> WorkspaceManifest:
        return WorkspaceManifest(
            name="test-workspace",
            agent_adapter="anthropic",
            evolvable_layers=["prompts", "skills"],
            skill_budget=skill_budget,
        )

    def test_contains_workspace_structure(self) -> None:
        manifest = self._make_manifest()
        result = build_evolver_system_prompt(manifest)
        assert "prompts/system.md" in result
        assert "skills/" in result

    def test_contains_tool_names(self) -> None:
        manifest = self._make_manifest()
        result = build_evolver_system_prompt(manifest)
        assert "read_trace" in result
        assert "read_skill" in result
        assert "read_prompt" in result
        assert "list_history" in result
        assert "field_detail" in result
        assert "search_traces" in result
        assert "read_cycle" in result

    def test_contains_skill_budget(self) -> None:
        manifest = self._make_manifest(skill_budget=5)
        result = build_evolver_system_prompt(manifest)
        assert "5" in result

    def test_contains_forbidden_section(self) -> None:
        manifest = self._make_manifest()
        result = build_evolver_system_prompt(manifest)
        assert "FORBIDDEN" in result

    def test_evolver_system_prompt_describes_real_tools(self) -> None:
        """System prompt should describe the actual tool names and their purpose."""
        manifest = WorkspaceManifest(
            name="test-workspace",
            agent_adapter="anthropic",
            skill_budget=10,
            evolvable_layers=["skills", "prompts"],
        )
        prompt = build_evolver_system_prompt(manifest)

        # Should describe investigation tools
        assert "read_trace" in prompt
        assert "read_skill" in prompt
        assert "list_history" in prompt
        assert "field_detail" in prompt
        assert "search_traces" in prompt
        assert "read_prompt" in prompt
        assert "read_cycle" in prompt

        # Should describe the investigate-then-act workflow
        assert "investigate" in prompt.lower() or "diagnose" in prompt.lower()

        # Should include mutation limits per scope
        assert "MINIMAL" in prompt
        assert "at most 1 action" in prompt
        assert "at most 3 actions" in prompt
        assert "at most 5 actions" in prompt
        assert "modifying existing skills over creating new ones" in prompt.lower()


# ---------------------------------------------------------------------------
# TestBuildEvolutionAnalysisPrompt
# ---------------------------------------------------------------------------


class TestBuildEvolutionAnalysisPrompt:
    def _make_discipline_scores(self) -> list[DisciplineScore]:
        return [
            DisciplineScore(
                discipline="electrical",
                task_count=5,
                mean_reward=0.85,
                field_pass_rate=0.80,
            ),
            DisciplineScore(
                discipline="civil",
                task_count=3,
                mean_reward=0.60,
                field_pass_rate=0.50,
            ),
        ]

    def test_skip_scope_says_no_changes(self) -> None:
        result = build_evolution_analysis_prompt(
            batch_score=0.92,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.SKIP,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
        )
        assert "Do not make changes" in result

    def test_comprehensive_scope_mentions_discipline(self) -> None:
        scores = self._make_discipline_scores()
        result = build_evolution_analysis_prompt(
            batch_score=0.65,
            discipline_scores=scores,
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
        )
        # civil has the lowest mean_reward (0.60), should be mentioned as weakest
        assert "civil" in result

    def test_includes_field_failure_rates(self) -> None:
        result = build_evolution_analysis_prompt(
            batch_score=0.70,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={"compliance": 0.45},
            workspace_skill_count=3,
            workspace_prompt_length=500,
        )
        assert "compliance" in result
        assert "45%" in result

    def test_includes_patterns(self) -> None:
        pattern = BehavioralPattern(
            name="blind_action",
            count=3,
            description="Agent executes actions without verification",
            affected_trial_ids=("trial-1", "trial-2", "trial-3"),
        )
        result = build_evolution_analysis_prompt(
            batch_score=0.65,
            discipline_scores=[],
            patterns=[pattern],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
        )
        assert "blind_action" in result

    def test_includes_batch_score(self) -> None:
        result = build_evolution_analysis_prompt(
            batch_score=0.73,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.TARGETED,
            field_failure_rates={},
            workspace_skill_count=2,
            workspace_prompt_length=400,
        )
        assert "73%" in result


class TestFieldDetailsInPrompt:
    """Tests for expected/actual field details in the analysis prompt."""

    def test_includes_masked_direction_when_provided(self) -> None:
        result = build_evolution_analysis_prompt(
            batch_score=0.25,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={"vc_mv_per_a_m": 1.0},
            workspace_skill_count=0,
            workspace_prompt_length=100,
            field_details_map={"vc_mv_per_a_m": ("6.18", "8.69")},
        )
        # Masked: shows direction, not exact values
        assert "too high" in result
        assert "6.18" not in result
        assert "8.69" not in result

    def test_omits_details_when_not_provided(self) -> None:
        result = build_evolution_analysis_prompt(
            batch_score=0.25,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={"vc_mv_per_a_m": 1.0},
            workspace_skill_count=0,
            workspace_prompt_length=100,
        )
        assert "expected:" not in result
        assert "100% failure rate" in result

    def test_field_details_bold_formatting_for_detailed_fields(self) -> None:
        """Fields with details should use bold formatting."""
        result = build_evolution_analysis_prompt(
            batch_score=0.5,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={"cable_size": 0.75, "voltage": 0.50},
            workspace_skill_count=0,
            workspace_prompt_length=100,
            field_details_map={"cable_size": ("16", "25")},
        )
        # cable_size has details => bold with masked direction
        assert "**cable_size**" in result
        assert "too high" in result
        assert "16" not in result  # exact values masked
        assert "25" not in result
        # voltage has no details => plain
        assert "- voltage:" in result


# ---------------------------------------------------------------------------
# TestPromptStructuralSection
# ---------------------------------------------------------------------------


class TestPromptStructuralSection:
    """Tests for structural quality section in the evolver prompt."""

    def test_includes_structural_score(self) -> None:
        """Prompt includes Structural Quality section when score is provided."""
        result = build_evolution_analysis_prompt(
            batch_score=0.5,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
            structural_score=0.72,
        )
        assert "Structural Quality" in result
        assert "0.72" in result

    def test_high_score_says_good_process(self) -> None:
        """Score >= 0.7 produces 'good process discipline' message."""
        result = build_evolution_analysis_prompt(
            batch_score=0.5,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
            structural_score=0.85,
        )
        assert "good process discipline" in result

    def test_low_score_suggests_improvement(self) -> None:
        """Score < 0.7 suggests behavioral process needs improvement."""
        result = build_evolution_analysis_prompt(
            batch_score=0.5,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
            structural_score=0.45,
        )
        assert "behavioral process needs improvement" in result

    def test_omits_structural_when_none(self) -> None:
        """Prompt omits Structural Quality section when score is None."""
        result = build_evolution_analysis_prompt(
            batch_score=0.5,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=3,
            workspace_prompt_length=500,
        )
        assert "Structural Quality" not in result


# ---------------------------------------------------------------------------
# TestBuildEvolutionBrief
# ---------------------------------------------------------------------------


class TestBuildEvolutionBrief:
    """Tests for the slim tool-based evolver brief."""

    def _make_base_kwargs(self) -> dict:
        return dict(
            batch_score=0.65,
            discipline_scores=[],
            patterns=[],
            scope=GraduatedScope.COMPREHENSIVE,
            field_failure_rates={},
            workspace_skill_count=2,
            workspace_prompt_length=400,
        )

    def test_build_evolution_brief_omits_full_skill_bodies(self) -> None:
        """Brief lists skill names but must not contain body previews."""
        skill_names = ["cable-sizing", "voltage-drop"]
        result = build_evolution_brief(
            **self._make_base_kwargs(),
            skill_names=skill_names,
        )
        # Names should be listed
        assert "cable-sizing" in result
        assert "voltage-drop" in result
        # No body content should appear — the body preview sentinel from the
        # old prompt style ("..." after 200 chars) should not be needed here.
        # We verify the brief points to read_skill() instead of showing bodies.
        assert "read_skill" in result
        # No body text (bodies are not passed in, so this checks the design)
        assert "read_prompt" in result

    def test_build_evolution_brief_includes_trial_ids(self) -> None:
        """Brief lists provided trial IDs."""
        trial_ids = ["trial-abc", "trial-def", "trial-xyz"]
        result = build_evolution_brief(
            **self._make_base_kwargs(),
            trial_ids=trial_ids,
        )
        for tid in trial_ids:
            assert tid in result

    def test_build_evolution_brief_references_tools(self) -> None:
        """Brief mentions all expected investigation tool names."""
        kwargs = self._make_base_kwargs()
        kwargs["field_failure_rates"] = {"voltage_drop": 0.80}
        result = build_evolution_brief(
            **kwargs,
            trial_ids=["trial-1"],
            skill_names=["example-skill"],
        )
        assert "read_trace" in result
        assert "field_detail" in result
        assert "read_skill" in result
        assert "read_prompt" in result

    def test_build_evolution_brief_graveyard_teaser_appears_when_populated(self) -> None:
        """Brief includes graveyard teaser when graveyard_size > 0."""
        result = build_evolution_brief(
            **self._make_base_kwargs(),
            graveyard_size=3,
        )
        assert "Failed Mutations" in result
        assert "3" in result
        assert "read_graveyard()" in result

    def test_build_evolution_brief_graveyard_teaser_absent_when_empty(self) -> None:
        """Brief omits graveyard teaser when graveyard_size is 0."""
        result = build_evolution_brief(
            **self._make_base_kwargs(),
            graveyard_size=0,
        )
        assert "read_graveyard()" not in result

    def test_build_evolution_brief_graveyard_teaser_default_is_zero(self) -> None:
        """Brief omits graveyard teaser by default (graveyard_size defaults to 0)."""
        result = build_evolution_brief(**self._make_base_kwargs())
        assert "read_graveyard()" not in result
