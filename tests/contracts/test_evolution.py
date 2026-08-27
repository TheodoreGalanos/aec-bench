# ABOUTME: Tests for evolution boundary models in the aec-bench contracts package.
# ABOUTME: Validates workspace manifest, skill entries, versions, and snapshots.

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from aec_bench.contracts.evolution import (
    CandidateAssessment,
    DisciplineScore,
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    EvolutionResult,
    EvolvableLayer,
    EvolverModelConfig,
    FieldScore,
    GateDecision,
    MutationSummary,
    ObservationEnrichment,
    ProposalUsage,
    SelectionRecord,
    SkillEntry,
    StagnationInfo,
    TraceDigest,
    TraceQueryRequest,
    TraceSlice,
    TraceSliceTurn,
    WorkspaceCandidateVersion,
    WorkspaceManifest,
    WorkspaceMigrationCandidate,
    WorkspaceMigrationPlan,
    WorkspaceReadRequest,
    WorkspaceSnapshot,
    WorkspaceWriteRequest,
)
from aec_bench.contracts.experiment_manifest import TaskSelector
from aec_bench.evaluation.behavioral import BondType
from tests.support.trial_record_factories import make_trial_record


class TestEvolvableLayer:
    def test_enum_values(self) -> None:
        assert EvolvableLayer.PROMPTS == "prompts"
        assert EvolvableLayer.SKILLS == "skills"
        assert EvolvableLayer.MEMORY == "memory"

    def test_all_members_present(self) -> None:
        members = {layer.value for layer in EvolvableLayer}
        assert members == {"prompts", "skills", "memory"}


class TestWorkspaceManifest:
    def _valid_manifest(self) -> WorkspaceManifest:
        return WorkspaceManifest(
            name="structural-workspace",
            agent_adapter="anthropic",
            evolvable_layers=[EvolvableLayer.PROMPTS, EvolvableLayer.SKILLS],
        )

    def test_valid_manifest(self) -> None:
        manifest = self._valid_manifest()
        assert manifest.name == "structural-workspace"
        assert manifest.schema_version == 1
        assert manifest.agent_adapter == "anthropic"
        assert EvolvableLayer.PROMPTS in manifest.evolvable_layers
        assert manifest.skill_budget == 10

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceManifest(
                name="   ",
                agent_adapter="anthropic",
                evolvable_layers=[],
            )

    def test_blank_adapter_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceManifest(
                name="my-workspace",
                agent_adapter="",
                evolvable_layers=[],
            )

    def test_empty_layers_allowed(self) -> None:
        manifest = WorkspaceManifest(
            name="minimal",
            agent_adapter="openai",
            evolvable_layers=[],
        )
        assert manifest.evolvable_layers == []

    def test_custom_skill_budget(self) -> None:
        manifest = WorkspaceManifest(
            name="big-workspace",
            agent_adapter="anthropic",
            evolvable_layers=[EvolvableLayer.SKILLS],
            skill_budget=25,
        )
        assert manifest.skill_budget == 25

    def test_zero_budget_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceManifest(
                name="my-workspace",
                agent_adapter="anthropic",
                evolvable_layers=[],
                skill_budget=0,
            )

    def test_agent_harness_accepted_as_synonym(self) -> None:
        """Users can write 'agent_harness' instead of 'agent_adapter' in manifest YAML."""
        manifest = WorkspaceManifest.model_validate(
            {
                "name": "harness-workspace",
                "agent_harness": "rlm",
                "evolvable_layers": ["prompts"],
            }
        )
        assert manifest.agent_adapter == "rlm"

    def test_both_agent_adapter_and_agent_harness_rejected(self) -> None:
        """Providing both is ambiguous — reject it."""
        with pytest.raises(ValidationError, match="[Aa]dapter.*[Hh]arness|[Hh]arness.*[Aa]dapter"):
            WorkspaceManifest.model_validate(
                {
                    "name": "ambiguous",
                    "agent_adapter": "rlm",
                    "agent_harness": "tool_loop",
                    "evolvable_layers": [],
                }
            )

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceManifest(
                name="my-workspace",
                agent_adapter="anthropic",
                evolvable_layers=[],
                unknown_field="oops",
            )

    def test_unknown_schema_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceManifest(
                schema_version=2,
                name="my-workspace",
                agent_adapter="anthropic",
                evolvable_layers=[],
            )


class TestSkillEntry:
    def test_valid_skill(self) -> None:
        skill = SkillEntry(
            name="calculate_beam_deflection",
            description="Computes mid-span deflection for simply-supported beams.",
            body="def calculate_beam_deflection(w, L, E, I): return 5*w*L**4/(384*E*I)",
        )
        assert skill.name == "calculate_beam_deflection"
        assert skill.discipline is None

    def test_discipline_optional(self) -> None:
        skill = SkillEntry(
            name="bearing_capacity",
            description="Computes ultimate bearing capacity of shallow foundations.",
            discipline="ground",
            body="def bearing_capacity(c, q, B): return c * 5.14 + q",
        )
        assert skill.discipline == "ground"

    def test_blank_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SkillEntry(
                name="  ",
                description="A skill.",
                body="def f(): pass",
            )

    def test_blank_body_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SkillEntry(
                name="my_skill",
                description="A skill.",
                body="",
            )


class TestWorkspaceCandidateVersion:
    def test_valid_candidate_with_parent(self) -> None:
        candidate = WorkspaceCandidateVersion(
            candidate_id="run:2",
            parent_candidate_id="run:1",
            source_revision="a" * 40,
            summary="Improved structural prompt.",
            score=0.74,
            label="evo-run-2",
        )
        assert candidate.candidate_id == "run:2"
        assert candidate.parent_candidate_id == "run:1"
        assert candidate.score == pytest.approx(0.74)

    def test_initial_candidate_no_parent(self) -> None:
        candidate = WorkspaceCandidateVersion(
            candidate_id="baseline",
            source_revision="b" * 40,
            summary="Initial workspace version.",
        )
        assert candidate.parent_candidate_id is None
        assert candidate.score is None

    def test_blank_candidate_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCandidateVersion(
                candidate_id="",
                source_revision="c" * 40,
            )

    @pytest.mark.parametrize("revision", ["", "aabbccdd", "A" * 40, "g" * 40])
    def test_non_full_git_sha_rejected(self, revision: str) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCandidateVersion(
                candidate_id="candidate",
                source_revision=revision,
            )

    def test_blank_optional_summary_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceCandidateVersion(
                candidate_id="candidate",
                source_revision="d" * 40,
                summary="",
            )


class TestWorkspaceMigrationPlan:
    def test_explicit_source_and_lineage(self) -> None:
        plan = WorkspaceMigrationPlan(
            candidates=(
                WorkspaceMigrationCandidate(
                    candidate_id="run:2",
                    label="evo-2",
                    parent_candidate_id="run:1",
                    expected_source_revision="e" * 40,
                ),
            )
        )
        assert plan.schema_version == 1
        assert plan.candidates[0].parent_candidate_id == "run:1"

    def test_duplicate_candidate_ids_rejected(self) -> None:
        item = WorkspaceMigrationCandidate(candidate_id="duplicate", label="evo-1")
        with pytest.raises(ValidationError, match="candidate_id values must be unique"):
            WorkspaceMigrationPlan(
                candidates=(item, item.model_copy(update={"label": "evo-2"})),
            )

    def test_unknown_schema_version_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceMigrationPlan(schema_version=2, candidates=())


class TestWorkspaceSnapshot:
    def _valid_skill(self) -> SkillEntry:
        return SkillEntry(
            name="check_slenderness",
            description="Checks column slenderness ratio.",
            body="def check_slenderness(L, r): return L / r",
        )

    def test_valid_snapshot_with_skills(self) -> None:
        snapshot = WorkspaceSnapshot(
            system_prompt="You are a structural engineering agent.",
            skills=[self._valid_skill()],
            candidate_id="run:3",
        )
        assert len(snapshot.skills) == 1
        assert snapshot.candidate_id == "run:3"

    def test_empty_skills_allowed(self) -> None:
        snapshot = WorkspaceSnapshot(
            system_prompt="You are an agent.",
            candidate_id="baseline",
        )
        assert snapshot.skills == ()

    def test_blank_system_prompt_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceSnapshot(
                system_prompt="   ",
                candidate_id="baseline",
            )

    def test_blank_candidate_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceSnapshot(
                system_prompt="You are an agent.",
                candidate_id="",
            )


class TestFieldScore:
    def test_valid_score(self) -> None:
        score = FieldScore(
            field_name="beam_deflection",
            reward=0.85,
            expected="12.3 mm",
            actual="12.1 mm",
        )
        assert score.field_name == "beam_deflection"
        assert score.reward == pytest.approx(0.85)
        assert score.expected == "12.3 mm"
        assert score.actual == "12.1 mm"

    def test_minimal_score(self) -> None:
        score = FieldScore(field_name="cable_size", reward=1.0)
        assert score.expected is None
        assert score.actual is None

    def test_blank_field_name_rejected(self) -> None:
        with pytest.raises(ValidationError):
            FieldScore(field_name="   ", reward=0.5)


class TestTraceDigest:
    def test_valid_digest_with_all_fields(self) -> None:
        digest = TraceDigest(
            turn_count=12,
            tool_call_count=8,
            tool_error_count=1,
            bond_sequence="EDEDV",
            key_actions=["read_file", "write_output"],
            errors=["tool timeout"],
            agent_reasoning=["checked units", "verified formula"],
        )
        assert digest.turn_count == 12
        assert digest.bond_sequence == "EDEDV"
        assert len(digest.key_actions) == 2

    def test_empty_lists_allowed(self) -> None:
        digest = TraceDigest(
            turn_count=3,
            tool_call_count=2,
            tool_error_count=0,
            bond_sequence="EDE",
        )
        assert digest.key_actions == []
        assert digest.errors == []
        assert digest.agent_reasoning == []

    def test_empty_bond_sequence_allowed(self) -> None:
        digest = TraceDigest(
            turn_count=0,
            tool_call_count=0,
            tool_error_count=0,
            bond_sequence="",
        )
        assert digest.bond_sequence == ""


class TestObservationEnrichment:
    def _make_field_score(self, name: str = "voltage_drop") -> FieldScore:
        return FieldScore(field_name=name, reward=0.9)

    def _make_trace_digest(self) -> TraceDigest:
        return TraceDigest(
            turn_count=5,
            tool_call_count=3,
            tool_error_count=0,
            bond_sequence="EDE",
        )

    def test_fully_enriched(self) -> None:
        enrichment = ObservationEnrichment(
            classified_trace=None,
            structural_score=None,
            field_scores=[self._make_field_score()],
            trace_digest=self._make_trace_digest(),
        )
        assert len(enrichment.field_scores) == 1
        assert enrichment.trace_digest is not None
        assert enrichment.classified_trace is None

    def test_empty_enrichment(self) -> None:
        enrichment = ObservationEnrichment()
        assert enrichment.classified_trace is None
        assert enrichment.structural_score is None
        assert enrichment.field_scores == []
        assert enrichment.trace_digest is None


class TestEvolutionObservation:
    def test_valid_observation(self) -> None:
        observation = EvolutionObservation(
            trial=make_trial_record(),
            enrichment=ObservationEnrichment(),
            candidate_id="run:2",
            discipline="electrical",
        )
        assert observation.candidate_id == "run:2"
        assert observation.discipline == "electrical"

    def test_blank_discipline_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionObservation(
                trial=make_trial_record(),
                enrichment=ObservationEnrichment(),
                candidate_id="baseline",
                discipline="",
            )


class TestTraceQueryRequest:
    def test_basic_query_all_defaults(self) -> None:
        query = TraceQueryRequest(trial_id="trial-abc")
        assert query.trial_id == "trial-abc"
        assert query.turn_range is None
        assert query.bond_type_filter is None
        assert query.errors_only is False
        assert query.reasoning_only is False

    def test_filtered_query(self) -> None:
        query = TraceQueryRequest(
            trial_id="trial-xyz",
            turn_range=(2, 8),
            bond_type_filter=BondType.DELIBERATION,
        )
        assert query.turn_range == (2, 8)
        assert query.bond_type_filter == BondType.DELIBERATION

    def test_errors_only_query(self) -> None:
        query = TraceQueryRequest(trial_id="trial-err", errors_only=True)
        assert query.errors_only is True
        assert query.reasoning_only is False

    def test_blank_trial_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TraceQueryRequest(trial_id="  ")


class TestTraceSlice:
    def _make_turn(self, index: int = 0) -> TraceSliceTurn:
        return TraceSliceTurn(
            turn_index=index,
            role="assistant",
            bond_type=BondType.EXECUTION,
            bond_confidence=0.92,
            content="Calling read_file tool.",
            tool_calls=["read_file('/workspace/input.json')"],
            tool_outputs=["{'voltage': 415}"],
        )

    def test_valid_slice_with_turns(self) -> None:
        turns = [self._make_turn(0), self._make_turn(1)]
        slc = TraceSlice(
            trial_id="trial-001",
            turns=turns,
            context="Turns 0-1 during initial file reading phase.",
        )
        assert len(slc.turns) == 2
        assert slc.turns[0].bond_type == BondType.EXECUTION
        assert slc.turns[0].is_error is False

    def test_empty_slice(self) -> None:
        slc = TraceSlice(
            trial_id="trial-002",
            turns=[],
            context="No turns matched the query filters.",
        )
        assert slc.turns == []

    def test_blank_context_rejected(self) -> None:
        with pytest.raises(ValidationError):
            TraceSlice(trial_id="trial-003", turns=[], context="")


class TestGateDecision:
    def test_accepted_value(self) -> None:
        assert GateDecision.ACCEPTED == "accepted"

    def test_rejected_value(self) -> None:
        assert GateDecision.REJECTED == "rejected"

    def test_skipped_value(self) -> None:
        assert GateDecision.SKIPPED == "skipped"

    def test_all_members_present(self) -> None:
        members = {d.value for d in GateDecision}
        assert members == {"accepted", "rejected", "skipped"}


class TestMutationSummary:
    def test_no_mutation_defaults(self) -> None:
        summary = MutationSummary()
        assert summary.prompt_modified is False
        assert summary.skills_added == []
        assert summary.skills_modified == []
        assert summary.skills_removed == []
        assert summary.memory_entries_added == 0
        assert summary.evolver_reasoning is None

    def test_skill_mutation_with_reasoning(self) -> None:
        summary = MutationSummary(
            prompt_modified=True,
            skills_added=["calculate_beam_depth"],
            skills_modified=["check_slenderness"],
            skills_removed=["old_formula"],
            memory_entries_added=2,
            evolver_reasoning="Improved deflection accuracy by adding new skill.",
        )
        assert summary.prompt_modified is True
        assert summary.skills_added == ["calculate_beam_depth"]
        assert summary.skills_modified == ["check_slenderness"]
        assert summary.skills_removed == ["old_formula"]
        assert summary.memory_entries_added == 2
        assert summary.evolver_reasoning == "Improved deflection accuracy by adding new skill."


class TestDisciplineScore:
    def test_valid_score(self) -> None:
        score = DisciplineScore(
            discipline="electrical",
            task_count=12,
            mean_reward=0.78,
            field_pass_rate=0.83,
            mean_structural_similarity=0.65,
        )
        assert score.discipline == "electrical"
        assert score.task_count == 12
        assert score.mean_reward == pytest.approx(0.78)
        assert score.field_pass_rate == pytest.approx(0.83)
        assert score.mean_structural_similarity == pytest.approx(0.65)

    def test_without_structural_similarity(self) -> None:
        score = DisciplineScore(
            discipline="civil",
            task_count=5,
            mean_reward=0.60,
            field_pass_rate=0.70,
        )
        assert score.mean_structural_similarity is None

    def test_blank_discipline_rejected(self) -> None:
        with pytest.raises(ValidationError):
            DisciplineScore(
                discipline="   ",
                task_count=3,
                mean_reward=0.5,
                field_pass_rate=0.5,
            )


class TestEvolutionCycleRecord:
    def _make_mutation(self) -> MutationSummary:
        return MutationSummary(
            prompt_modified=True,
            skills_added=["new_formula"],
            evolver_reasoning="Added formula to improve accuracy.",
        )

    def _make_assessment(self, candidate_id: str, trial_id: str = "trial-001") -> CandidateAssessment:
        return CandidateAssessment(
            candidate_id=candidate_id,
            batch_score=0.75,
            structural_score=0.68,
            discipline_scores={"structural": 0.72},
            trial_ids=(trial_id,),
            evaluation_case_ids=(f"case-{trial_id}",),
            valid=True,
        )

    def _make_selection(self, parent_candidate_id: str) -> SelectionRecord:
        return SelectionRecord(
            parent_candidate_id=parent_candidate_id,
            strategy="conservative",
            goal="Improve the selected candidate.",
            reasoning="Select the current best candidate.",
        )

    def test_accepted_cycle_full(self) -> None:
        record = EvolutionCycleRecord(
            cycle=3,
            selection=self._make_selection("run:2"),
            parent_assessment=self._make_assessment("run:2"),
            child_assessment=self._make_assessment("run:3", "trial-002"),
            mutation=self._make_mutation(),
            gate_decision=GateDecision.ACCEPTED,
            gate_reason="Child improved the configured objective.",
            active_candidate_id_after="run:3",
            best_candidate_id_after="run:3",
            timestamp=datetime.now(UTC),
            evolver_usage=ProposalUsage(model_requests=1, model_cost_usd=0.04),
        )
        assert record.cycle == 3
        assert record.gate_decision == GateDecision.ACCEPTED
        assert record.parent_assessment.candidate_id == "run:2"
        assert record.child_assessment is not None
        assert record.child_assessment.candidate_id == "run:3"
        assert record.active_candidate_id_after == "run:3"
        assert record.evolver_usage.total_cost_usd == pytest.approx(0.04)

    def test_skipped_cycle_same_versions(self) -> None:
        record = EvolutionCycleRecord(
            cycle=1,
            selection=self._make_selection("baseline"),
            parent_assessment=self._make_assessment("baseline", "trial-100"),
            child_assessment=None,
            mutation=None,
            gate_decision=GateDecision.SKIPPED,
            gate_reason="Variation abstained.",
            active_candidate_id_after="baseline",
            best_candidate_id_after="baseline",
            timestamp=datetime.now(UTC),
            evolver_usage=ProposalUsage(),
        )
        assert record.gate_decision == GateDecision.SKIPPED
        assert record.active_candidate_id_after == record.best_candidate_id_after == "baseline"
        assert record.mutation is None

    def test_blank_version_before_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionCycleRecord(
                cycle=1,
                selection=self._make_selection(""),
                parent_assessment=self._make_assessment("baseline"),
                child_assessment=None,
                mutation=None,
                gate_decision=GateDecision.REJECTED,
                gate_reason="Rejected child.",
                active_candidate_id_after="baseline",
                best_candidate_id_after="baseline",
                timestamp=datetime.now(UTC),
                evolver_usage=ProposalUsage(),
            )


class TestEvolutionResult:
    def _make_cycle_record(self) -> EvolutionCycleRecord:
        return EvolutionCycleRecord(
            cycle=1,
            selection=SelectionRecord(
                parent_candidate_id="baseline",
                strategy="conservative",
                goal="Improve the selected candidate.",
                reasoning="Select the current best candidate.",
            ),
            parent_assessment=CandidateAssessment(
                candidate_id="baseline",
                batch_score=0.82,
                structural_score=0.70,
                discipline_scores={},
                trial_ids=("trial-001",),
                evaluation_case_ids=("case-001",),
                valid=True,
            ),
            child_assessment=None,
            mutation=MutationSummary(prompt_modified=True),
            gate_decision=GateDecision.ACCEPTED,
            gate_reason="Accepted baseline cycle.",
            active_candidate_id_after="run:2",
            best_candidate_id_after="run:2",
            timestamp=datetime.now(UTC),
            evolver_usage=ProposalUsage(model_requests=1, model_cost_usd=0.01),
        )

    def test_converged_run(self) -> None:
        result = EvolutionResult(
            run_id="run-abc123",
            workspace_name="structural-workspace",
            cycles_completed=10,
            final_score=0.85,
            best_score=0.88,
            best_candidate_id="run:9",
            score_history=[0.60, 0.72, 0.80, 0.85, 0.88],
            converged=True,
            total_trials=100,
            cycle_records=[self._make_cycle_record()],
        )
        assert result.converged is True
        assert result.best_score == pytest.approx(0.88)
        assert result.stagnation is None
        assert result.total_evolver_cost is None

    def test_stagnated_run(self) -> None:
        stagnation = StagnationInfo(
            cycles_without_improvement=5,
            best_score=0.72,
            best_candidate_id="run:5",
            rolled_back=True,
        )
        result = EvolutionResult(
            run_id="run-xyz",
            workspace_name="civil-workspace",
            cycles_completed=20,
            final_score=0.70,
            best_score=0.72,
            best_candidate_id="run:5",
            score_history=[0.60, 0.65, 0.70, 0.72, 0.71, 0.70],
            converged=False,
            stagnation=stagnation,
            total_trials=200,
            cycle_records=[],
        )
        assert result.converged is False
        assert result.stagnation is not None
        assert result.stagnation.rolled_back is True

    def test_blank_run_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionResult(
                run_id="  ",
                workspace_name="my-workspace",
                cycles_completed=1,
                final_score=0.5,
                best_score=0.5,
                best_candidate_id="baseline",
                score_history=[0.5],
                converged=False,
                total_trials=10,
                cycle_records=[],
            )


class TestEvolverModelConfig:
    def test_valid_config_with_defaults(self) -> None:
        config = EvolverModelConfig(
            classifier="claude-haiku-4-5",
            evolver="claude-sonnet-4-6",
        )
        assert config.classifier == "claude-haiku-4-5"
        assert config.evolver == "claude-sonnet-4-6"
        assert config.classifier_temperature == pytest.approx(0.0)
        assert config.evolver_temperature == pytest.approx(0.7)
        assert config.evolver_max_tokens == 16384

    def test_custom_temperatures(self) -> None:
        config = EvolverModelConfig(
            classifier="gpt-4o-mini",
            evolver="gpt-4o",
            classifier_temperature=0.1,
            evolver_temperature=0.5,
            evolver_max_tokens=8192,
        )
        assert config.classifier_temperature == pytest.approx(0.1)
        assert config.evolver_temperature == pytest.approx(0.5)
        assert config.evolver_max_tokens == 8192

    def test_blank_classifier_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolverModelConfig(classifier="", evolver="claude-sonnet-4-6")

    def test_blank_evolver_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolverModelConfig(classifier="claude-haiku-4-5", evolver="  ")


class TestEvolutionConfig:
    def _make_model_config(self) -> EvolverModelConfig:
        return EvolverModelConfig(
            classifier="claude-haiku-4-5",
            evolver="claude-sonnet-4-6",
        )

    def test_defaults(self) -> None:
        config = EvolutionConfig(
            workspace_path="/workspaces/structural",
            models=self._make_model_config(),
            task_selector=TaskSelector(),
        )
        assert config.batch_size == 10
        assert config.max_cycles == 20
        assert config.improvement_threshold == pytest.approx(0.02)
        assert config.stagnation_window == 5
        assert config.structural_weight == pytest.approx(0.3)
        assert config.discipline_balanced is False

    def test_single_task_config(self) -> None:
        selector = TaskSelector(include_patterns=["electrical/voltage-drop-*"])
        config = EvolutionConfig(
            workspace_path="/workspaces/electrical",
            models=self._make_model_config(),
            task_selector=selector,
            batch_size=1,
        )
        assert config.batch_size == 1
        assert config.task_selector.include_patterns == ["electrical/voltage-drop-*"]

    def test_blank_workspace_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionConfig(
                workspace_path="",
                models=self._make_model_config(),
                task_selector=TaskSelector(),
            )

    def test_zero_batch_size_rejected(self) -> None:
        with pytest.raises(ValidationError):
            EvolutionConfig(
                workspace_path="/workspaces/test",
                models=self._make_model_config(),
                task_selector=TaskSelector(),
                batch_size=0,
            )

    def test_with_solver_config(self) -> None:
        from aec_bench.contracts.experiment_manifest import AgentConfig, ClientConfig

        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            solver=AgentConfig(
                name="evo-solver",
                adapter="rlm",
                model="claude-sonnet-4-20250514",
                client=ClientConfig(kind="anthropic"),
            ),
        )
        assert config.solver is not None
        assert config.solver.model == "claude-sonnet-4-20250514"

    def test_solver_defaults_to_none(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        assert config.solver is None

    def test_backend_defaults_to_local(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        assert config.backend == "local"

    def test_harness_config_defaults_to_none(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        assert config.harness_config is None

    def test_harness_config_accepts_path(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            harness_config="experiment.yaml",
        )
        assert config.harness_config == "experiment.yaml"

    def test_harbor_backend_is_not_a_supported_alias(self) -> None:
        with pytest.raises(ValidationError, match="local.*modal.*morph"):
            EvolutionConfig(
                workspace_path="/tmp/workspace",
                models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
                task_selector=TaskSelector(),
                backend="harbor",
            )

    def test_timeout_defaults(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
        )
        assert config.timeout == 1800

    def test_custom_timeout(self) -> None:
        config = EvolutionConfig(
            workspace_path="/tmp/workspace",
            models=EvolverModelConfig(classifier="haiku", evolver="sonnet"),
            task_selector=TaskSelector(),
            timeout=600,
        )
        assert config.timeout == 600


class TestWorkspaceReadRequest:
    def test_valid_read(self) -> None:
        req = WorkspaceReadRequest(path="prompts/system.md")
        assert req.path == "prompts/system.md"

    def test_blank_path_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceReadRequest(path="   ")


class TestWorkspaceWriteRequest:
    def test_valid_write(self) -> None:
        req = WorkspaceWriteRequest(
            path="prompts/system.md",
            content="You are a structural engineering agent.",
        )
        assert req.path == "prompts/system.md"
        assert req.content == "You are a structural engineering agent."

    def test_blank_content_rejected(self) -> None:
        with pytest.raises(ValidationError):
            WorkspaceWriteRequest(path="prompts/system.md", content="")
