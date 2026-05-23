# ABOUTME: Core 6-phase evolution engine for aec-bench agent improvement.
# ABOUTME: Orchestrates classify, analyse, auto-seed, evolve, gate, and version phases.

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from statistics import mean
from typing import Any

from aec_bench.contracts.evolution import (
    EvolutionCycleRecord,
    EvolutionObservation,
    GateDecision,
    MutationSummary,
    ObservationEnrichment,
    SkillEntry,
    StepResult,
)
from aec_bench.evaluation.behavioral import (
    BehavioralLLMClient,
    BondType,
    LLMTurnClassifier,
    TransitionMatrix,
    load_behavioral_trace,
    score_trace_structural,
)
from aec_bench.evolution.analysis import (
    GraduatedScope,
    compute_discipline_scores,
    compute_graduated_scope,
    detect_behavioral_patterns,
)
from aec_bench.evolution.archive_agent import SelectionResult
from aec_bench.evolution.enrichment import build_trace_digest, extract_field_scores
from aec_bench.evolution.mutation import apply_mutations, parse_evolver_response
from aec_bench.evolution.prompts import (
    build_evolution_analysis_prompt,
    build_evolver_system_prompt,
)
from aec_bench.evolution.seeding import compute_seed_skills
from aec_bench.evolution.workspace import Workspace

logger = logging.getLogger(__name__)


class AECEvolutionEngine:
    """Six-phase step function that drives one cycle of agent evolution.

    Each call to ``step()`` runs: CLASSIFY -> ANALYSE -> AUTO-SEED -> EVOLVE ->
    GATE -> VERSION. Stateful tracking of stagnation and best score is held on
    the instance so the engine can detect plateaus across consecutive cycles.
    """

    def __init__(
        self,
        *,
        classifier_llm: BehavioralLLMClient,
        evolver_llm: BehavioralLLMClient,
        evolver_model_name: str | None = None,
        ideal_pattern: TransitionMatrix | None = None,
        ideal_sequence: tuple[BondType, ...] = (),
        improvement_threshold: float = 0.02,
        stagnation_window: int = 5,
        structural_weight: float = 0.3,
    ) -> None:
        self._classifier_llm = classifier_llm
        self._evolver_llm = evolver_llm
        self._evolver_model_name = evolver_model_name
        self._ideal_pattern = ideal_pattern
        self._ideal_sequence = ideal_sequence
        self._improvement_threshold = improvement_threshold
        self._stagnation_window = stagnation_window
        self._structural_weight = structural_weight

        # Mutable tracking across cycles
        self._best_score: float = 0.0
        self._best_version: str = "evo-0"
        self._cycles_without_improvement: int = 0
        self._run_id: str = ""
        self._strategy_name: str = ""

    def set_run_id(self, run_id: str) -> None:
        """Set the run ID used for version tagging. Called by the orchestrator."""
        self._run_id = run_id

    def set_strategy_name(self, name: str) -> None:
        """Set the strategy name included in tag messages. Called by the orchestrator."""
        self._strategy_name = name

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def step(
        self,
        workspace: Workspace,
        observations: list[EvolutionObservation],
        history: list[EvolutionCycleRecord],
        selection: SelectionResult | None = None,
        graveyard: Any | None = None,
    ) -> StepResult:
        """Run the 6-phase evolution cycle and return the result."""
        cycle_num = len(history) + 1
        version_before = _current_version_tag(workspace, history)

        # Phase 1: CLASSIFY
        enriched_observations = self._phase_classify(observations)

        # Phase 2: ANALYSE
        (
            batch_score,
            scope,
            discipline_scores,
            patterns,
            improving,
            aggregate_structural,
        ) = self._phase_analyse(enriched_observations, history)

        # Phase 3: AUTO-SEED
        seeded_skills = self._phase_auto_seed(workspace, scope, patterns)

        # Phase 4: EVOLVE
        evolver_mutation = self._phase_evolve(
            workspace,
            scope,
            batch_score,
            discipline_scores,
            patterns,
            enriched_observations,
            structural_score=aggregate_structural,
            history=history,
            selection=selection,
            graveyard=graveyard,
        )

        # Merge auto-seeded skills with evolver mutations into a single summary
        mutation = _merge_mutation_summaries(seeded_skills, evolver_mutation)

        # Phase 5: GATE — check whether any actual change was made
        mutated = _has_mutations(mutation)
        gate_decision = self._phase_gate(batch_score, aggregate_structural, mutated, scope)

        # Phase 6: VERSION
        version_after = self._phase_version(workspace, gate_decision, cycle_num, batch_score)

        trial_ids = [obs.trial.trial_id for obs in observations]

        cycle_record = EvolutionCycleRecord(
            cycle=cycle_num,
            workspace_version_before=version_before,
            workspace_version_after=version_after,
            batch_score=batch_score,
            discipline_scores=discipline_scores,
            structural_score=aggregate_structural,
            mutation=mutation,
            gate_decision=gate_decision,
            trial_ids=trial_ids,
            timestamp=datetime.now(tz=UTC),
        )

        return StepResult(
            mutated=mutated,
            gate_decision=gate_decision,
            mutation=mutation,
            cycle_record=cycle_record,
            enriched_observations=enriched_observations,
        )

    # ------------------------------------------------------------------
    # Phase 1: CLASSIFY
    # ------------------------------------------------------------------

    def _phase_classify(
        self,
        observations: list[EvolutionObservation],
    ) -> list[EvolutionObservation]:
        """Classify behavioral traces for observations missing enrichment.

        Observations that already have a classified_trace in their enrichment
        are returned unchanged. For the rest, load the behavioral trace from
        the trial record, classify it, and build enrichment objects.
        """
        classifier = LLMTurnClassifier(client=self._classifier_llm)
        result: list[EvolutionObservation] = []

        for obs in observations:
            if obs.enrichment.classified_trace is not None:
                result.append(obs)
                continue

            try:
                trace = load_behavioral_trace(obs.trial)
                classified = classifier.classify_trace(trace)
            except Exception:
                logger.warning(
                    "Phase 1: failed to classify trace for trial %s, skipping",
                    obs.trial.trial_id,
                    exc_info=True,
                )
                result.append(obs)
                continue

            structural_score = None
            if self._ideal_pattern is not None:
                structural_score = score_trace_structural(
                    classified,
                    ideal_matrix=self._ideal_pattern,
                    ideal_sequence=self._ideal_sequence,
                )

            # Build a trace digest from the classifications
            tool_call_count = sum(len(turn.tool_calls) for turn in trace.turns if turn.role == "assistant")
            tool_error_count = sum(sum(1 for tr in turn.tool_results if tr.is_error) for turn in trace.turns)

            # Extract key actions, errors, and agent reasoning from trace turns
            key_actions: list[str] = []
            trace_errors: list[str] = []
            agent_reasoning: list[str] = []

            for turn in trace.turns:
                if turn.role == "assistant":
                    # Capture tool call names/summaries (truncate long args)
                    for tc in turn.tool_calls:
                        summary = tc.tool_name
                        if tc.arguments:
                            args_preview = str(dict(tc.arguments))[:150]
                            summary = f"{tc.tool_name}({args_preview})"
                        key_actions.append(summary)
                    # Capture reasoning from assistant text turns without tool calls
                    if turn.content and not turn.tool_calls:
                        agent_reasoning.append(turn.content[:200])
                # Capture errors from tool results
                for tr in turn.tool_results:
                    if tr.is_error and tr.output:
                        trace_errors.append(tr.output[:300])

            digest = build_trace_digest(
                classifications=classified.classifications,
                tool_call_count=tool_call_count,
                tool_error_count=tool_error_count,
                key_actions=key_actions[:20],
                errors=trace_errors[:10],
                agent_reasoning=agent_reasoning[:10],
            )

            # Extract field scores from the trial evaluation breakdown
            field_scores = extract_field_scores(obs.trial)

            new_enrichment = ObservationEnrichment(
                classified_trace=classified,
                structural_score=structural_score,
                field_scores=field_scores,
                trace_digest=digest,
            )

            # Reconstruct observation with the new enrichment
            new_obs = EvolutionObservation(
                trial=obs.trial,
                enrichment=new_enrichment,
                workspace_version=obs.workspace_version,
                discipline=obs.discipline,
            )
            result.append(new_obs)

        return result

    # ------------------------------------------------------------------
    # Phase 2: ANALYSE
    # ------------------------------------------------------------------

    def _phase_analyse(
        self,
        observations: list[EvolutionObservation],
        history: list[EvolutionCycleRecord],
    ) -> tuple[float, GraduatedScope, list, list, bool, float | None]:
        """Compute scores, detect patterns, and determine scope.

        Returns (batch_score, scope, discipline_scores, patterns, improving,
        aggregate_structural).
        """
        discipline_scores = compute_discipline_scores(observations)
        patterns = detect_behavioral_patterns(observations)

        batch_score = mean(obs.trial.evaluation.reward for obs in observations)

        previous_score = history[-1].batch_score if history else None
        improving = previous_score is not None and batch_score > previous_score

        scope = compute_graduated_scope(batch_score, improving)

        # Aggregate structural score from enriched observations
        structural_scores = [
            obs.enrichment.structural_score.cosine_similarity
            for obs in observations
            if obs.enrichment.structural_score is not None
        ]
        aggregate_structural = mean(structural_scores) if structural_scores else None

        logger.info(
            "Phase 2: batch_score=%.3f, scope=%s, improving=%s, patterns=%d, structural=%.3f",
            batch_score,
            scope.value,
            improving,
            len(patterns),
            aggregate_structural if aggregate_structural is not None else -1.0,
        )

        return (
            batch_score,
            scope,
            discipline_scores,
            patterns,
            improving,
            aggregate_structural,
        )

    # ------------------------------------------------------------------
    # Phase 3: AUTO-SEED
    # ------------------------------------------------------------------

    def _phase_auto_seed(
        self,
        workspace: Workspace,
        scope: GraduatedScope,
        patterns: list,
    ) -> list[SkillEntry]:
        """Seed skills based on detected behavioral anti-patterns.

        Returns the list of skills that were actually written to the workspace.
        Skipped entirely when scope is SKIP.
        """
        if scope == GraduatedScope.SKIP:
            logger.info("Phase 3: scope is SKIP, no auto-seeding")
            return []

        existing_skills = workspace.list_skills()
        existing_names = {s.name for s in existing_skills}
        budget_remaining = workspace.manifest.skill_budget - len(existing_skills)

        seeds = compute_seed_skills(patterns, existing_names, budget_remaining)

        for skill in seeds:
            workspace.write_skill(skill)
            logger.info("Phase 3: seeded skill '%s'", skill.name)

        return seeds

    # ------------------------------------------------------------------
    # Phase 4: EVOLVE
    # ------------------------------------------------------------------

    def _phase_evolve(
        self,
        workspace: Workspace,
        scope: GraduatedScope,
        batch_score: float,
        discipline_scores: list,
        patterns: list,
        observations: list[EvolutionObservation],
        *,
        structural_score: float | None = None,
        history: list[EvolutionCycleRecord] | None = None,
        selection: SelectionResult | None = None,
        graveyard: Any | None = None,
    ) -> MutationSummary | None:
        """Build evolver prompt, call the evolver LLM, and apply mutations.

        Parses the evolver's JSON response into structured mutation actions and
        applies them to the workspace. Returns a MutationSummary describing what
        changed, or None when scope is SKIP.
        """
        if scope == GraduatedScope.SKIP:
            logger.info("Phase 4: scope is SKIP, no evolution")
            return None

        manifest = workspace.manifest
        system_prompt = build_evolver_system_prompt(manifest)

        field_failure_rates = _compute_field_failure_rates(observations)

        # Collect field details (expected vs actual) for the first failing example per field
        field_details_map: dict[str, tuple[str, str]] = {}
        for obs in observations:
            for fs in obs.enrichment.field_scores:
                if fs.reward < 1.0 and fs.expected and fs.actual and fs.field_name not in field_details_map:
                    field_details_map[fs.field_name] = (fs.expected, fs.actual)

        existing_skills = workspace.list_skills()
        current_prompt = workspace.read_prompt()

        # Extract a representative task instruction from the observations
        task_instruction = ""
        for obs in observations:
            if obs.trial.inputs.instruction:
                task_instruction = obs.trial.inputs.instruction
                break

        analysis_prompt = build_evolution_analysis_prompt(
            batch_score=batch_score,
            discipline_scores=discipline_scores,
            patterns=patterns,
            scope=scope,
            field_failure_rates=field_failure_rates,
            workspace_skill_count=len(existing_skills),
            workspace_prompt_length=len(current_prompt),
            current_prompt=current_prompt,
            current_skills=[(s.name, s.body) for s in existing_skills],
            task_instruction=task_instruction,
            field_details_map=field_details_map,
            structural_score=structural_score,
        )

        # Use tool-loop structured evolver when evolver model name is available,
        # otherwise fall back to free-text parsing.
        if self._evolver_model_name:
            from aec_bench.evolution.evolver_tools import build_evolver_toolset
            from aec_bench.evolution.prompts import build_evolution_brief
            from aec_bench.evolution.structured_evolver import call_structured_evolver_with_tools

            toolset = build_evolver_toolset(
                observations=observations,
                workspace_root=workspace.root,
                history=history or [],
                current_prompt=current_prompt,
                current_skills=[(s.name, s.body) for s in existing_skills],
                graveyard=graveyard,
            )

            brief = build_evolution_brief(
                batch_score=batch_score,
                discipline_scores=discipline_scores,
                patterns=patterns,
                scope=scope,
                field_failure_rates=field_failure_rates,
                workspace_skill_count=len(existing_skills),
                workspace_prompt_length=len(current_prompt),
                skill_names=[s.name for s in existing_skills],
                trial_ids=[obs.trial.trial_id for obs in observations],
                structural_score=structural_score,
                graveyard_size=graveyard.size if graveyard else 0,
            )

            if selection:
                brief += (
                    f"\n\n## Selection Context\n"
                    f"Parent: {selection.parent_version}\n"
                    f"Strategy: {selection.strategy}\n"
                    f"Inspiration: {', '.join(selection.inspiration_versions) or 'none'}\n"
                    f"Selection reasoning: {selection.reasoning}\n"
                )

            parsed = call_structured_evolver_with_tools(
                model_name=self._evolver_model_name,
                system_prompt=system_prompt,
                analysis_brief=brief,
                toolset=toolset,
                scope=scope.value,
                workspace_root=workspace.root,
            )
        else:
            full_prompt = system_prompt + "\n\n" + analysis_prompt
            response = self._evolver_llm.complete(full_prompt, max_tokens=16384)
            logger.info("Phase 4: evolver responded with %d chars", len(response))

            parsed = parse_evolver_response(response)
            if parsed.parse_errors:
                for err in parsed.parse_errors:
                    logger.warning("Phase 4: parse error — %s", err)

        # Apply parsed actions to the workspace
        mutation_summary = apply_mutations(parsed.actions, workspace)

        # Attach evolver reasoning
        mutation_summary = mutation_summary.model_copy(
            update={"evolver_reasoning": parsed.reasoning},
        )

        # Phase 4b: SANITISE — enforce hard limits after evolver mutations
        from aec_bench.evolution.sanitiser import sanitise_workspace

        sanitise_result = sanitise_workspace(workspace, compaction_llm=self._classifier_llm)
        if (
            sanitise_result.skills_removed
            or sanitise_result.skills_truncated
            or sanitise_result.skills_compacted
            or sanitise_result.prompt_truncated
        ):
            logger.info(
                "Phase 4b: sanitised — removed %d skills, truncated %d skills, "
                "compacted %d skills, prompt_truncated=%s",
                len(sanitise_result.skills_removed),
                len(sanitise_result.skills_truncated),
                len(sanitise_result.skills_compacted),
                sanitise_result.prompt_truncated,
            )

        logger.info(
            "Phase 4: applied %d actions (added=%d, modified=%d, removed=%d, prompt=%s)",
            len(parsed.actions),
            len(mutation_summary.skills_added),
            len(mutation_summary.skills_modified),
            len(mutation_summary.skills_removed),
            mutation_summary.prompt_modified,
        )

        return mutation_summary

    # ------------------------------------------------------------------
    # Phase 5: GATE
    # ------------------------------------------------------------------

    def _phase_gate(
        self,
        batch_score: float,
        structural_score: float | None,
        mutated: bool,
        scope: GraduatedScope,
    ) -> GateDecision:
        """Evaluate whether the cycle's mutations should be kept.

        Combines reward with structural quality (when available) for improvement
        tracking. Tracks stagnation across cycles. Returns ACCEPTED, REJECTED,
        or SKIPPED.
        """
        if scope == GraduatedScope.SKIP and not mutated:
            logger.info("Phase 5: SKIPPED — scope is SKIP and no mutation occurred")
            return GateDecision.SKIPPED

        # Combine reward with structural quality when available
        if structural_score is not None:
            combined = batch_score * (1 - self._structural_weight) + structural_score * self._structural_weight
        else:
            combined = batch_score

        # Track improvement using combined score
        if combined > self._best_score + self._improvement_threshold:
            self._best_score = combined
            self._cycles_without_improvement = 0
        else:
            self._cycles_without_improvement += 1

        # Stagnation detection
        if self._cycles_without_improvement >= self._stagnation_window:
            logger.info(
                "Phase 5: REJECTED — stagnation for %d cycles",
                self._cycles_without_improvement,
            )
            return GateDecision.REJECTED

        logger.info(
            "Phase 5: ACCEPTED — batch_score=%.3f, structural=%.3f, combined=%.3f",
            batch_score,
            structural_score if structural_score is not None else -1.0,
            combined,
        )
        return GateDecision.ACCEPTED

    # ------------------------------------------------------------------
    # Phase 6: VERSION
    # ------------------------------------------------------------------

    def _phase_version(
        self,
        workspace: Workspace,
        gate_decision: GateDecision,
        cycle_num: int,
        batch_score: float,
    ) -> str:
        """Commit or rollback the workspace based on the gate decision.

        Returns the workspace version tag after this phase completes.
        """
        tag = f"evo-{self._run_id}-{cycle_num}" if self._run_id else f"evo-{cycle_num}"

        strategy_suffix = f" [{self._strategy_name}]" if self._strategy_name else ""

        if gate_decision == GateDecision.ACCEPTED:
            version = workspace.commit_and_tag(
                tag=tag,
                summary=f"cycle {cycle_num}: score {batch_score:.3f}{strategy_suffix}",
                score=batch_score,
            )
            self._best_version = tag
            logger.info("Phase 6: committed %s", tag)
            return version.tag

        if gate_decision == GateDecision.REJECTED:
            workspace.rollback_to_tag(self._best_version)
            logger.info("Phase 6: rolled back to %s", self._best_version)
            return self._best_version

        # SKIPPED — commit an empty snapshot to mark the cycle happened
        version = workspace.commit_and_tag(
            tag=tag,
            summary=f"cycle {cycle_num}: skipped (score {batch_score:.3f}){strategy_suffix}",
            score=batch_score,
        )
        logger.info("Phase 6: committed skip marker %s", tag)
        return version.tag


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _current_version_tag(
    workspace: Workspace,
    history: Sequence[EvolutionCycleRecord],
) -> str:
    """Determine the workspace version tag before this cycle starts."""
    if history:
        return history[-1].workspace_version_after
    versions = workspace.list_versions()
    if versions:
        return versions[-1].tag
    return "evo-0"


def _merge_mutation_summaries(
    seeded_skills: list[SkillEntry],
    evolver_mutation: MutationSummary | None,
) -> MutationSummary | None:
    """Combine auto-seeded skills with evolver mutation into one summary.

    Returns None when neither auto-seeding nor evolver produced changes.
    """
    seeded_names = [s.name for s in seeded_skills]
    has_seeds = len(seeded_names) > 0
    has_evolver = evolver_mutation is not None

    if not has_seeds and not has_evolver:
        return None

    if has_evolver and has_seeds:
        # Merge seeded skill names into the evolver summary
        combined_added = seeded_names + list(evolver_mutation.skills_added)
        return evolver_mutation.model_copy(update={"skills_added": combined_added})

    if has_evolver:
        return evolver_mutation

    # Only auto-seeded skills, no evolver changes
    return MutationSummary(skills_added=seeded_names)


def _has_mutations(mutation: MutationSummary | None) -> bool:
    """Return True if the mutation summary contains any actual workspace changes."""
    if mutation is None:
        return False
    return (
        mutation.prompt_modified
        or len(mutation.skills_added) > 0
        or len(mutation.skills_modified) > 0
        or len(mutation.skills_removed) > 0
    )


def _compute_field_failure_rates(
    observations: Sequence[EvolutionObservation],
) -> dict[str, float]:
    """Compute per-field failure rates across all observations.

    A field "fails" when its reward is below 1.0. Returns a dict mapping field
    name to the fraction of observations that failed for that field.
    """
    field_totals: dict[str, int] = {}
    field_failures: dict[str, int] = {}

    for obs in observations:
        for fs in obs.enrichment.field_scores:
            field_totals[fs.field_name] = field_totals.get(fs.field_name, 0) + 1
            if fs.reward < 1.0:
                field_failures[fs.field_name] = field_failures.get(fs.field_name, 0) + 1

    return {name: field_failures.get(name, 0) / total for name, total in field_totals.items() if total > 0}
