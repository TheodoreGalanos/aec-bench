# ABOUTME: Per-agent evolver that runs the functional candidate cycle for swarm execution.
# ABOUTME: Each agent gets an independent workspace copy, cycle state, and solver.

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from collections.abc import Sequence
from pathlib import Path

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    EvolverModelConfig,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.behavioral import BehavioralLLMClient
from aec_bench.evolution.application import CandidateEvaluator, _build_analysis, _enrich_candidate
from aec_bench.evolution.backends.local import make_local_candidate_batch_planner, make_local_candidate_evaluator
from aec_bench.evolution.core import EvolutionState, VariationRequest
from aec_bench.evolution.enrichment import enrich_observations
from aec_bench.evolution.evaluation import CandidateBatchPlanner, CandidateEvaluationBatch, bind_candidate_evaluation
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.swarm.core import SwarmAgentResult, SwarmAssignment
from aec_bench.evolution.variation import run_structured_variation
from aec_bench.evolution.workspace import Workspace

_log = logging.getLogger(__name__)


class SwarmAgentEvolver:
    """Runs one functional evolution cycle per step() call for one swarm agent."""

    def __init__(
        self,
        workspace: Workspace,
        config: EvolutionConfig,
        batch_planner: CandidateBatchPlanner,
        solve_fn: CandidateEvaluator,
        classifier_llm: BehavioralLLMClient,
        evolver_llm: BehavioralLLMClient,
        evolver_model_name: str,
    ) -> None:
        self._workspace = workspace
        self._config = config
        self._batch_planner = batch_planner
        self._solve_fn = solve_fn
        self._classifier_llm = classifier_llm
        self._evolver_llm = evolver_llm
        self._evolver_model_name = evolver_model_name
        self._cycle = 0
        self._history: list[EvolutionCycleRecord] = []
        self._graveyard = MutationGraveyard()

    async def step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
        """Run one evolution cycle asynchronously.

        Wraps synchronous work in a thread executor with a timeout guard.
        Default timeout is 30 minutes — generous for complex evolution cycles.
        """
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, self._sync_step, assignment),
            timeout=1800,  # 30 minutes
        )

    def _sync_step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
        """Run variation for one exact assignment and return no evaluation evidence."""
        self._cycle += 1
        batch = self._batch_planner(self._config.batch_size, self._cycle - 1)
        parent = bind_candidate_evaluation(
            assignment.parent,
            batch,
            self._solve_fn(assignment.parent, batch),
        )
        parent = _enrich_candidate(
            parent,
            batch,
            lambda observations: enrich_observations(observations, classifier_llm=self._classifier_llm),
        )
        evolution_state = EvolutionState.from_baseline(
            parent,
            structural_weight=self._config.structural_weight,
        )
        analysis = _build_analysis(parent, evolution_state)
        request = VariationRequest(
            selection=assignment.selection,
            parent=parent,
            inspirations=assignment.inspirations,
            analysis=analysis,
            scope=analysis.scope,
            history=tuple(self._history),
            graveyard=tuple(self._graveyard.browse(limit=self._graveyard.size)),
        )
        variation = run_structured_variation(
            request,
            self._workspace,
            assignment.assignment_id,
            evolver_model_name=self._evolver_model_name,
            evolver_llm=self._evolver_llm,
            compaction_llm=self._classifier_llm,
        )
        return SwarmAgentResult(
            agent_id=assignment.agent_id,
            assignment_id=assignment.assignment_id,
            variation=variation,
            agent_cost_usd=variation.model_cost_usd,
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
        classifier_llm: BehavioralLLMClient,
        evolver_llm: BehavioralLLMClient,
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
        classifier_llm: BehavioralLLMClient
        evolver_llm: BehavioralLLMClient
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
        )

    def plan_batch(self, batch_size: int, cycle: int) -> CandidateEvaluationBatch:
        """Plan one candidate-independent host evaluation batch."""
        planner = make_local_candidate_batch_planner(
            task_dirs=self._task_dirs,
            model=self._model,
            experiment_id="swarm-host",
            adapter=self._adapter,
            timeout=self._timeout,
        )
        return planner(batch_size, cycle)

    def baseline_snapshot(self) -> WorkspaceSnapshot:
        """Return the exact source workspace material for the first assignment."""
        return Workspace(self._workspace_source).export_snapshot("baseline")

    def evaluate(self, snapshot: WorkspaceSnapshot, batch: CandidateEvaluationBatch) -> tuple[TrialRecord, ...]:
        """Evaluate an exact submitted snapshot in the host runtime."""
        evaluator = make_local_candidate_evaluator(workspace_root=self._workspace_source)
        return evaluator(snapshot, batch)

    def enrich(self, observations: Sequence[EvolutionObservation]) -> tuple[EvolutionObservation, ...]:
        """Attach trusted behavioural evidence to host observations."""
        return enrich_observations(observations, classifier_llm=self._classifier_llm)

    def cleanup(self) -> None:
        """Remove all agent workspace copies."""
        for agent_id, ws_path in self._agent_workspaces.items():
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)
                _log.info("Cleaned up workspace for %s", agent_id)
