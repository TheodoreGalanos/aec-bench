# ABOUTME: Per-agent evolver that runs the functional candidate cycle for swarm execution.
# ABOUTME: Each agent gets an independent workspace copy, cycle state, and solver.

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolverModelConfig,
    MutationStrategy,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evolution.application import CandidateEvaluator, _execute_evolution_cycle
from aec_bench.evolution.backends.local import make_local_candidate_batch_planner, make_local_candidate_evaluator
from aec_bench.evolution.behaviour import extract_behaviour_descriptor
from aec_bench.evolution.core import EvolutionState, SelectionPlan
from aec_bench.evolution.enrichment import enrich_observations
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.strategy import HillClimbStrategy
from aec_bench.evolution.variation import run_structured_variation
from aec_bench.evolution.workspace import Workspace

_log = logging.getLogger(__name__)

# Per-token pricing for Sonnet 4 on Bedrock.
_INPUT_COST_PER_MTOK = 3.0
_OUTPUT_COST_PER_MTOK = 15.0
_CACHE_READ_COST_PER_MTOK = 0.30
_CACHE_WRITE_COST_PER_MTOK = 3.75


def _estimate_trial_cost(trial_record: TrialRecord) -> float:
    """Estimate the USD cost of a trial from its CostRecord.

    Uses estimated_cost_usd if available. When cache token counts are
    present, computes cache-aware pricing. Otherwise uses a heuristic:
    in multi-turn conversations, ~80% of input tokens are typically
    cached after the first turn.
    """
    cost = trial_record.cost
    if cost is None:
        return 0.0
    estimated = cost.estimated_cost_usd
    if estimated is not None:
        return float(estimated)

    tokens_in = cost.tokens_in or 0
    tokens_out = cost.tokens_out or 0
    cache_read = cost.cache_read_tokens
    cache_write = cost.cache_write_tokens

    output_cost = tokens_out * _OUTPUT_COST_PER_MTOK / 1_000_000

    if cache_read is not None:
        # Exact cache data available — use precise pricing
        cache_write_count = cache_write or 0
        uncached_in = max(0, tokens_in - cache_read - cache_write_count)
        input_cost = (
            uncached_in * _INPUT_COST_PER_MTOK
            + cache_read * _CACHE_READ_COST_PER_MTOK
            + cache_write_count * _CACHE_WRITE_COST_PER_MTOK
        ) / 1_000_000
    else:
        # Heuristic: assume ~80% of input tokens are cached in multi-turn
        cached_portion = 0.8 if tokens_in > 5000 else 0.0
        uncached = tokens_in * (1 - cached_portion)
        cached = tokens_in * cached_portion
        input_cost = (uncached * _INPUT_COST_PER_MTOK + cached * _CACHE_READ_COST_PER_MTOK) / 1_000_000

    return input_cost + output_cost


@dataclass(frozen=True)
class SwarmStepResult:
    """Result of one evolution cycle by a swarm agent."""

    score: float
    bd: BehaviourDescriptor | None
    cost_usd: float
    candidate_id: str
    parent_candidate_id: str = ""


class SwarmAgentEvolver:
    """Runs one functional evolution cycle per step() call for one swarm agent."""

    def __init__(
        self,
        workspace: Workspace,
        config: EvolutionConfig,
        batch_planner: Any,
        solve_fn: CandidateEvaluator,
        classifier_llm: Any,
        evolver_llm: Any,
        evolver_model_name: str,
        run_id: str,
    ) -> None:
        self._workspace = workspace
        self._config = config
        self._batch_planner = batch_planner
        self._solve_fn = solve_fn
        self._classifier_llm = classifier_llm
        self._evolver_llm = evolver_llm
        self._evolver_model_name = evolver_model_name
        self._run_id = run_id
        self._shared_graveyard: Any | None = None
        self._cycle = 0
        self._history: list[EvolutionCycleRecord] = []
        self._strategy = HillClimbStrategy()
        self._graveyard = MutationGraveyard()
        self._snapshots: dict[str, WorkspaceSnapshot] = {"baseline": workspace.export_snapshot("baseline")}
        self._state: EvolutionState | None = None
        self._pending_selection: SelectionPlan | None = None

    def set_shared_state(
        self,
        graveyard: Any | None = None,
    ) -> None:
        """Inject shared swarm state into this evolver.

        Called by SwarmManager after factory creation to connect the
        evolver to the shared graveyard.
        """
        if graveyard is not None:
            self._shared_graveyard = graveyard

    async def step(self) -> SwarmStepResult:
        """Run one evolution cycle asynchronously.

        Wraps synchronous work in a thread executor with a timeout guard.
        Default timeout is 30 minutes — generous for complex evolution cycles.
        """
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self._sync_step),
            timeout=1800,  # 30 minutes
        )

    def _sync_step(self) -> SwarmStepResult:
        """Run one evolution cycle synchronously."""
        self._cycle += 1
        selection = self._pending_selection or SelectionPlan(
            parent_candidate_id="baseline",
            inspiration_candidate_ids=(),
            strategy=MutationStrategy.CONSERVATIVE,
            goal="Improve the selected agent workspace against the configured evaluation batch.",
            reasoning="Start from the baseline candidate.",
        )

        execution = _execute_evolution_cycle(
            workspace=self._workspace,
            config=self._config,
            evaluate=self._solve_fn,
            strategy=self._strategy,
            batch_planner=self._batch_planner,
            variation=lambda request, source, child_id: run_structured_variation(
                request,
                source,
                child_id,
                evolver_model_name=self._evolver_model_name,
                evolver_llm=self._evolver_llm,
                compaction_llm=self._classifier_llm,
            ),
            enrich=lambda observations: enrich_observations(observations, classifier_llm=self._classifier_llm),
            graveyard=self._graveyard,
            history=self._history,
            snapshots=self._snapshots,
            cycle=self._cycle,
            state=self._state,
            selection=selection,
            run_id=self._run_id,
            now=lambda: datetime.now(tz=UTC),
            candidate_id_factory=lambda current_run, cycle: f"{current_run}:{cycle}",
        )

        if (
            execution.outcome.decision.decision.value == "rejected"
            and execution.outcome.child is not None
            and self._shared_graveyard is not None
        ):
            entries = self._graveyard.browse(limit=1)
            if entries:
                self._shared_graveyard.insert(
                    entries[0], extract_behaviour_descriptor(execution.outcome.child.observations[0]), self._run_id
                )

        self._history.append(execution.record)
        self._state = execution.state
        self._pending_selection = SelectionPlan(
            parent_candidate_id=self._state.best_candidate_id,
            inspiration_candidate_ids=(),
            strategy=MutationStrategy.CONSERVATIVE,
            goal="Improve the selected agent workspace against the configured evaluation batch.",
            reasoning=f"Explicit state selected best candidate {self._state.best_candidate_id}.",
        )

        bd = None
        evaluated = execution.outcome.child or execution.outcome.parent
        enriched = evaluated.observations
        if enriched:
            bd = extract_behaviour_descriptor(enriched[0])

        score = execution.score
        evolver_cost = execution.record.evolver_cost_usd
        candidate_id_after = execution.outcome.active_candidate_id_after
        candidate_id_before = execution.outcome.parent.snapshot.candidate_id

        solver_cost = sum(_estimate_trial_cost(observation.trial) for observation in enriched)
        total_cost = evolver_cost + solver_cost

        return SwarmStepResult(
            score=score,
            bd=bd,
            cost_usd=total_cost,
            candidate_id=candidate_id_after,
            parent_candidate_id=candidate_id_before,
        )


class SwarmEvolverFactory:
    """Creates per-agent SwarmAgentEvolver instances from swarm config.

    Each agent gets:
    - An independent workspace copy (shutil.copytree from source)
    - Its own explicit functional evolution state
    - Its own local candidate evaluator
    LLM clients are shared across agents (stateless, thread-safe).
    """

    def __init__(
        self,
        *,
        workspace_source: Path,
        task_dirs: list[Path],
        classifier_llm: Any,
        evolver_llm: Any,
        evolver_model_name: str,
        model: str,
        adapter: str = "rlm",
        timeout: int = 1800,
        batch_size: int = 1,
        improvement_threshold: float = 0.01,
        stagnation_window: int = 5,
        structural_weight: float = 0.3,
    ) -> None:
        self._workspace_source = workspace_source
        self._task_dirs = task_dirs
        self._classifier_llm = classifier_llm
        self._evolver_llm = evolver_llm
        self._evolver_model_name = evolver_model_name
        self._model = model
        self._adapter = adapter
        self._timeout = timeout
        self._batch_size = batch_size
        self._improvement_threshold = improvement_threshold
        self._stagnation_window = stagnation_window
        self._structural_weight = structural_weight
        self._agent_workspaces: dict[str, Path] = {}

    def create(self, agent_id: str, model_override: str | None = None) -> SwarmAgentEvolver:
        """Create a fully-wired evolver for a single swarm agent.

        When model_override is provided, the agent uses different LLM clients
        built from that model name instead of the factory's default.
        """
        # 1. Copy workspace to a temp directory for this agent
        agent_ws_path = Path(tempfile.mkdtemp(prefix=f"swarm-{agent_id}-"))
        shutil.copytree(self._workspace_source, agent_ws_path, dirs_exist_ok=True)
        self._agent_workspaces[agent_id] = agent_ws_path
        _log.info("Agent %s workspace: %s", agent_id, agent_ws_path)

        # 2. Load workspace and initialise git versioning
        workspace = Workspace(agent_ws_path)
        workspace.init_versioning()

        # 3. Build LLM clients — per-agent override or factory default
        if model_override and model_override != self._model:
            from aec_bench.providers.behavioral_llm import build_behavioral_llm_client

            classifier_llm = build_behavioral_llm_client(model=model_override)
            evolver_llm = build_behavioral_llm_client(model=model_override)
            evolver_model_name = model_override
            solver_model = model_override
            _log.info("Agent %s using model override: %s", agent_id, model_override)
        else:
            classifier_llm = self._classifier_llm
            evolver_llm = self._evolver_llm
            evolver_model_name = self._evolver_model_name
            solver_model = self._model

        # 4. Compose the candidate-independent plan and evaluator.
        experiment_id = f"swarm-{agent_id}"
        batch_planner = make_local_candidate_batch_planner(
            task_dirs=self._task_dirs,
            model=solver_model,
            experiment_id=experiment_id,
            adapter=self._adapter,
            timeout=self._timeout,
        )
        solve_fn = make_local_candidate_evaluator(
            workspace_root=agent_ws_path,
        )
        config = EvolutionConfig(
            workspace_path=str(agent_ws_path),
            models=EvolverModelConfig(classifier=evolver_model_name, evolver=evolver_model_name),
            task_selector=TaskSelector(),
            batch_size=self._batch_size,
            max_cycles=1,
            improvement_threshold=self._improvement_threshold,
            stagnation_window=self._stagnation_window,
            structural_weight=self._structural_weight,
            solver=AgentConfig(name=f"swarm-{agent_id}", adapter=self._adapter, model=solver_model),
        )

        return SwarmAgentEvolver(
            workspace=workspace,
            config=config,
            batch_planner=batch_planner,
            solve_fn=solve_fn,
            classifier_llm=classifier_llm,
            evolver_llm=evolver_llm,
            evolver_model_name=evolver_model_name,
            run_id=agent_id,
        )

    def cleanup(self) -> None:
        """Remove all agent workspace copies."""
        for agent_id, ws_path in self._agent_workspaces.items():
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)
                _log.info("Cleaned up workspace for %s", agent_id)
