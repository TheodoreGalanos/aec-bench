# ABOUTME: Tests for the AECEvolutionEngine 6-phase evolution step.
# ABOUTME: Uses stub LLM clients to test analysis, seeding, gating, and versioning.

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

import yaml

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    EvolutionObservation,
    FieldScore,
    GateDecision,
    ObservationEnrichment,
    StepResult,
    TraceDigest,
)
from aec_bench.evaluation.behavioral import (
    BehavioralTrace,
    BondType,
    ClassifiedTrace,
    ToolCall,
    ToolResult,
    Turn,
    TurnClassification,
)
from aec_bench.evolution.analysis import GraduatedScope
from aec_bench.evolution.engine import AECEvolutionEngine
from aec_bench.evolution.workspace import Workspace
from tests.support.trial_record_factories import make_trial_record

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_workspace(root: Path) -> Path:
    """Create the minimal directory structure for a valid Workspace."""
    root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": "test-workspace",
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (root / "manifest.yaml").write_text(yaml.dump(manifest))
    prompts_dir = root / "prompts"
    prompts_dir.mkdir()
    (prompts_dir / "system.md").write_text("You are an engineering agent.")
    return root


class StubClassifierLLM:
    """Return valid bond-type JSON based on keyword matching in the prompt."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        indices_match = re.search(r"Classify turns:\s*([\d,\s]+)$", prompt, re.MULTILINE)
        if indices_match is None:
            return '{"classifications": []}'
        indices = [int(x.strip()) for x in indices_match.group(1).split(",")]
        return json.dumps(
            {
                "classifications": [
                    {
                        "turn_index": i,
                        "bond_type": "execution",
                        "confidence": 0.9,
                        "rationale": "stub",
                    }
                    for i in indices
                ]
            }
        )


class StubEvolverLLM:
    """Return a simple string indicating no changes are needed."""

    def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> str:
        return "No changes needed."


def _make_classified_trace(
    trace_id: str = "trial-001",
    bond_types: tuple[BondType, ...] = (
        BondType.EXECUTION,
        BondType.DELIBERATION,
        BondType.EXECUTION,
        BondType.VERIFICATION,
    ),
) -> ClassifiedTrace:
    """Build a ClassifiedTrace with given bond types."""
    classifications = tuple(
        TurnClassification(turn_index=i, bond_type=bt, confidence=0.9, rationale="test")
        for i, bt in enumerate(bond_types)
    )
    return ClassifiedTrace(
        trace_id=trace_id,
        model_name="test-model",
        classifications=classifications,
    )


def _make_observation(
    trial_id: str = "trial-001",
    discipline: str = "electrical",
    reward: float = 0.8,
    bond_sequence: str = "E-D-E-V",
    field_scores: list[FieldScore] | None = None,
    classified_trace: ClassifiedTrace | None = None,
) -> EvolutionObservation:
    """Build a pre-enriched EvolutionObservation suitable for engine tests."""
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
    enrichment = ObservationEnrichment(
        classified_trace=classified_trace,
        field_scores=field_scores or [],
        trace_digest=TraceDigest(
            turn_count=4,
            tool_call_count=3,
            tool_error_count=0,
            bond_sequence=bond_sequence,
        ),
    )
    return EvolutionObservation(
        trial=record,
        enrichment=enrichment,
        workspace_version="evo-0",
        discipline=discipline,
    )


# ---------------------------------------------------------------------------
# TestAECEvolutionEngine
# ---------------------------------------------------------------------------


class TestAECEvolutionEngine:
    """Core tests for the 6-phase evolution step function."""

    def test_step_returns_step_result(self, tmp_path: Path) -> None:
        """Create engine with stubs, 2 observations. Verify StepResult structure."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

        # Pre-populate enrichment with ClassifiedTrace so Phase 1 is skipped
        ct = _make_classified_trace(trace_id="trial-001")
        obs1 = _make_observation(
            trial_id="trial-001",
            reward=0.7,
            bond_sequence="E-D-E-V",
            classified_trace=ct,
        )
        ct2 = _make_classified_trace(trace_id="trial-002")
        obs2 = _make_observation(
            trial_id="trial-002",
            reward=0.6,
            bond_sequence="E-E-E-V",
            classified_trace=ct2,
        )

        result = engine.step(workspace=ws, observations=[obs1, obs2], history=[])

        assert isinstance(result, StepResult)
        assert isinstance(result.gate_decision, GateDecision)
        assert isinstance(result.cycle_record, EvolutionCycleRecord)
        assert result.cycle_record.cycle == 1
        assert abs(result.cycle_record.batch_score - 0.65) < 1e-9
        assert len(result.cycle_record.trial_ids) == 2

    def test_auto_seeds_on_blind_action_pattern(self, tmp_path: Path) -> None:
        """Observations with E-E-E-E-E should trigger blind_action seeding."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

        ct1 = _make_classified_trace(trace_id="trial-ba-1")
        obs1 = _make_observation(
            trial_id="trial-ba-1",
            reward=0.4,
            bond_sequence="E-E-E-E-E",
            classified_trace=ct1,
        )
        ct2 = _make_classified_trace(trace_id="trial-ba-2")
        obs2 = _make_observation(
            trial_id="trial-ba-2",
            reward=0.3,
            bond_sequence="E-E-E-E-E-E",
            classified_trace=ct2,
        )

        result = engine.step(workspace=ws, observations=[obs1, obs2], history=[])

        # The seeding phase should have written the verification-checkpoint skill
        skill_names = {s.name for s in ws.list_skills()}
        assert "verification-checkpoint" in skill_names
        # The mutation summary should list it
        assert result.mutation is not None
        assert "verification-checkpoint" in result.mutation.skills_added

    def test_skip_scope_no_mutation(self, tmp_path: Path) -> None:
        """High-reward, not-improving observations produce SKIP scope and SKIPPED gate."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

        ct = _make_classified_trace(trace_id="trial-skip-1")
        obs1 = _make_observation(
            trial_id="trial-skip-1",
            reward=0.95,
            bond_sequence="E-D-V-E-V",
            classified_trace=ct,
        )
        ct2 = _make_classified_trace(trace_id="trial-skip-2")
        obs2 = _make_observation(
            trial_id="trial-skip-2",
            reward=0.98,
            bond_sequence="E-D-V-E-V",
            classified_trace=ct2,
        )

        result = engine.step(workspace=ws, observations=[obs1, obs2], history=[])

        assert result.gate_decision == GateDecision.SKIPPED
        assert not result.mutated
        # No skills should have been added
        assert ws.list_skills() == []

    def test_gate_accepts_improvement(self, tmp_path: Path) -> None:
        """First cycle score 0.6, second cycle score 0.8 -> ACCEPTED."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

        # Cycle 1: score 0.6
        ct1 = _make_classified_trace(trace_id="trial-c1")
        obs_c1 = _make_observation(
            trial_id="trial-c1",
            reward=0.6,
            bond_sequence="E-E-E-V",
            classified_trace=ct1,
        )
        result1 = engine.step(workspace=ws, observations=[obs_c1], history=[])
        assert result1.cycle_record.cycle == 1

        # Cycle 2: score 0.8 (improvement of 0.2, well above 0.02 threshold)
        ct2 = _make_classified_trace(trace_id="trial-c2")
        obs_c2 = _make_observation(
            trial_id="trial-c2",
            reward=0.8,
            bond_sequence="E-D-V-E-V",
            classified_trace=ct2,
        )
        result2 = engine.step(
            workspace=ws,
            observations=[obs_c2],
            history=[result1.cycle_record],
        )

        assert result2.gate_decision == GateDecision.ACCEPTED
        assert result2.cycle_record.cycle == 2

    def test_evolver_mutations_applied(self, tmp_path: Path) -> None:
        """Evolver returns a write_skill action; verify skill appears in workspace."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        class MutatingEvolverLLM:
            def complete(
                self,
                prompt: str,
                *,
                temperature: float = 0.0,
                max_tokens: int = 4000,
            ) -> str:
                return json.dumps(
                    {
                        "actions": [
                            {
                                "type": "write_skill",
                                "name": "cable-sizing-reference",
                                "description": "AS/NZS 3008 cable sizing lookup",
                                "discipline": "electrical",
                                "body": "## Cable Sizing\n\nUse Table 3 of AS/NZS 3008...",
                            }
                        ],
                        "reasoning": ("Electrical tasks fail on cable sizing fields. Adding reference."),
                    }
                )

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=MutatingEvolverLLM(),
        )

        ct = _make_classified_trace(trace_id="trial-mut-1")
        obs = _make_observation(
            trial_id="trial-mut-1",
            reward=0.5,
            bond_sequence="E-D-E-V",
            classified_trace=ct,
        )

        result = engine.step(workspace=ws, observations=[obs], history=[])

        # Skill should appear in workspace
        skill_names = {s.name for s in ws.list_skills()}
        assert "cable-sizing-reference" in skill_names

        # Mutation summary should report the skill
        assert result.mutation is not None
        assert "cable-sizing-reference" in result.mutation.skills_added

        # Evolver reasoning should be populated
        assert result.mutation.evolver_reasoning is not None
        assert "cable sizing" in result.mutation.evolver_reasoning.lower()

        # Gate should accept since mutations happened
        assert result.gate_decision == GateDecision.ACCEPTED
        assert result.mutated is True

    def test_evolver_malformed_response_no_crash(self, tmp_path: Path) -> None:
        """Evolver returns unparseable text; verify no crash and no mutations."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        class MalformedEvolverLLM:
            def complete(
                self,
                prompt: str,
                *,
                temperature: float = 0.0,
                max_tokens: int = 4000,
            ) -> str:
                return "I don't know what to change."

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=MalformedEvolverLLM(),
        )

        ct = _make_classified_trace(trace_id="trial-bad-1")
        obs = _make_observation(
            trial_id="trial-bad-1",
            reward=0.5,
            bond_sequence="E-D-E-V",
            classified_trace=ct,
        )

        result = engine.step(workspace=ws, observations=[obs], history=[])

        # No skills should have been added
        assert ws.list_skills() == []

        # Mutation summary should reflect no changes
        # With no mutations, the summary may be None or have empty lists
        if result.mutation is not None:
            assert result.mutation.skills_added == []
            assert result.mutation.skills_modified == []
            assert result.mutation.skills_removed == []
            assert result.mutation.prompt_modified is False

        # Gate decision should reflect the lack of mutations
        # (score 0.5 is first cycle, so ACCEPTED because it beats default 0.0+0.02)
        assert result.gate_decision in (GateDecision.ACCEPTED, GateDecision.SKIPPED)


# ---------------------------------------------------------------------------
# TestStructuralScoreInGate
# ---------------------------------------------------------------------------


class TestStructuralScoreInGate:
    """Tests that the gate uses structural score in combined scoring."""

    def test_gate_uses_combined_score_for_tracking(self, tmp_path: Path) -> None:
        """Gate uses combined (reward + structural) score for improvement tracking."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
            structural_weight=0.3,
        )

        # batch_score=0.85, structural_score=0.9
        # combined = 0.85 * 0.7 + 0.9 * 0.3 = 0.595 + 0.27 = 0.865
        # This exceeds default best_score (0.0) + threshold (0.02) -> ACCEPTED
        gate = engine._phase_gate(
            batch_score=0.85,
            structural_score=0.9,
            mutated=True,
            scope=GraduatedScope.COMPREHENSIVE,
        )
        assert gate == GateDecision.ACCEPTED

    def test_gate_without_structural_score_uses_raw_batch(self, tmp_path: Path) -> None:
        """When structural_score is None, gate uses raw batch_score."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
            structural_weight=0.3,
        )

        gate = engine._phase_gate(
            batch_score=0.6,
            structural_score=None,
            mutated=True,
            scope=GraduatedScope.COMPREHENSIVE,
        )
        assert gate == GateDecision.ACCEPTED
        # _best_score should be 0.6 (raw, not combined)
        assert abs(engine._best_score - 0.6) < 1e-9

    def test_structural_score_in_cycle_record(self, tmp_path: Path) -> None:
        """step() populates structural_score in the cycle record when available."""
        from aec_bench.evaluation.behavioral import StructuralScore

        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

        ct = _make_classified_trace(trace_id="trial-ss-1")
        # Create observation with a structural_score in enrichment
        structural = StructuralScore(
            trace_id="trial-ss-1",
            cosine_similarity=0.82,
            edit_distance=3,
            normalized_edit_distance=0.25,
        )
        record = make_trial_record(
            trial_id="trial-ss-1",
            evaluation={
                "reward": 0.7,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
            },
        )
        obs = EvolutionObservation(
            trial=record,
            enrichment=ObservationEnrichment(
                classified_trace=ct,
                structural_score=structural,
                field_scores=[],
                trace_digest=TraceDigest(
                    turn_count=4,
                    tool_call_count=3,
                    tool_error_count=0,
                    bond_sequence="E-D-E-V",
                ),
            ),
            workspace_version="evo-0",
            discipline="electrical",
        )

        result = engine.step(workspace=ws, observations=[obs], history=[])
        assert result.cycle_record.structural_score is not None
        assert abs(result.cycle_record.structural_score - 0.82) < 1e-9

    def test_structural_score_none_when_no_enrichment(self, tmp_path: Path) -> None:
        """step() leaves structural_score as None when observations lack it."""
        root = _scaffold_workspace(tmp_path / "ws")
        ws = Workspace(root)
        ws.init_versioning()

        engine = AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

        ct = _make_classified_trace(trace_id="trial-ns-1")
        obs = _make_observation(
            trial_id="trial-ns-1",
            reward=0.6,
            bond_sequence="E-D-E-V",
            classified_trace=ct,
        )

        result = engine.step(workspace=ws, observations=[obs], history=[])
        assert result.cycle_record.structural_score is None


# ---------------------------------------------------------------------------
# TestPhaseClassifyTraceExtraction
# ---------------------------------------------------------------------------


class TestPhaseClassifyTraceExtraction:
    """Unit tests for the trace data extraction in Phase 1 (_phase_classify).

    These tests patch load_behavioral_trace to inject synthetic BehavioralTrace
    objects so we can verify that key_actions, errors, and agent_reasoning are
    correctly extracted from trace turns and stored in the resulting TraceDigest.
    """

    def _make_engine(self) -> AECEvolutionEngine:
        return AECEvolutionEngine(
            classifier_llm=StubClassifierLLM(),
            evolver_llm=StubEvolverLLM(),
        )

    def _make_unenriched_obs(self, trial_id: str = "trial-extract-1") -> EvolutionObservation:
        """Build an observation with no classified_trace so Phase 1 runs."""
        record = make_trial_record(
            trial_id=trial_id,
            evaluation={
                "reward": 0.7,
                "validity": {
                    "output_parseable": True,
                    "schema_valid": True,
                    "verifier_completed": True,
                },
            },
        )
        return EvolutionObservation(
            trial=record,
            enrichment=ObservationEnrichment(),
            workspace_version="evo-0",
            discipline="electrical",
        )

    def _make_trace(
        self,
        turns: tuple[Turn, ...],
        trace_id: str = "trial-extract-1",
    ) -> BehavioralTrace:
        return BehavioralTrace(
            trace_id=trace_id,
            model_name="test-model",
            task_description="Test task",
            turns=turns,
        )

    def test_key_actions_extracted_from_tool_calls(self) -> None:
        """Tool call names and truncated args appear in trace_digest.key_actions."""
        turns = (
            Turn(
                turn_index=0,
                role="assistant",
                content="",
                tool_calls=(
                    ToolCall(tool_name="bash", arguments={"command": "ls -la /workspace"}),
                    ToolCall(
                        tool_name="read_file",
                        arguments={"path": "/workspace/output.md"},
                    ),
                ),
            ),
        )
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert len(digest.key_actions) == 2
        assert "bash" in digest.key_actions[0]
        assert "read_file" in digest.key_actions[1]

    def test_tool_call_args_truncated_in_key_actions(self) -> None:
        """Long tool call arguments are truncated to 150 chars in the summary."""
        long_arg = "x" * 300
        turns = (
            Turn(
                turn_index=0,
                role="assistant",
                content="",
                tool_calls=(ToolCall(tool_name="bash", arguments={"command": long_arg}),),
            ),
        )
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert len(digest.key_actions) == 1
        # 150 char preview + surrounding dict/function formatting: should be well under 200 chars
        assert len(digest.key_actions[0]) < 200

    def test_errors_extracted_from_tool_results(self) -> None:
        """Tool result errors appear in trace_digest.errors."""
        turns = (
            Turn(
                turn_index=0,
                role="assistant",
                content="",
                tool_calls=(ToolCall(tool_name="bash", arguments={}),),
                tool_results=(
                    ToolResult(
                        tool_name="bash",
                        output="FileNotFoundError: /workspace/missing.txt",
                        is_error=True,
                    ),
                ),
            ),
        )
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert len(digest.errors) == 1
        assert "FileNotFoundError" in digest.errors[0]

    def test_non_error_tool_results_not_captured(self) -> None:
        """Successful tool results are not included in trace_digest.errors."""
        turns = (
            Turn(
                turn_index=0,
                role="assistant",
                content="",
                tool_calls=(ToolCall(tool_name="bash", arguments={}),),
                tool_results=(ToolResult(tool_name="bash", output="ok", is_error=False),),
            ),
        )
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert digest.errors == []

    def test_agent_reasoning_extracted_from_text_only_turns(self) -> None:
        """Assistant turns with content and no tool calls produce agent_reasoning entries."""
        turns = (
            Turn(
                turn_index=0,
                role="assistant",
                content="I need to check the voltage drop formula first.",
                tool_calls=(),
            ),
        )
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert len(digest.agent_reasoning) == 1
        assert "voltage drop" in digest.agent_reasoning[0]

    def test_tool_call_turns_do_not_produce_reasoning(self) -> None:
        """Assistant turns that contain tool calls are not captured as agent_reasoning."""
        turns = (
            Turn(
                turn_index=0,
                role="assistant",
                content="Running calculation.",
                tool_calls=(ToolCall(tool_name="bash", arguments={}),),
            ),
        )
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert digest.agent_reasoning == []

    def test_key_actions_capped_at_twenty(self) -> None:
        """More than 20 tool calls produce at most 20 key_actions entries."""
        tool_calls = tuple(ToolCall(tool_name=f"tool_{i}", arguments={}) for i in range(25))
        turns = (Turn(turn_index=0, role="assistant", content="", tool_calls=tool_calls),)
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert len(digest.key_actions) == 20

    def test_empty_trace_produces_empty_fields(self) -> None:
        """A trace with only user/system turns produces empty digest lists."""
        turns = (Turn(turn_index=0, role="user", content="Please complete the task."),)
        trace = self._make_trace(turns)
        obs = self._make_unenriched_obs()
        engine = self._make_engine()

        with patch("aec_bench.evolution.engine.load_behavioral_trace", return_value=trace):
            result_obs = engine._phase_classify([obs])

        digest = result_obs[0].enrichment.trace_digest
        assert digest is not None
        assert digest.key_actions == []
        assert digest.errors == []
        assert digest.agent_reasoning == []
