# ABOUTME: Per-agent evolver that runs the functional candidate cycle for swarm execution.
# ABOUTME: Each agent gets an independent workspace copy, cycle state, and solver.

from __future__ import annotations

import asyncio
import logging
import math
import shutil
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from threading import Lock

from aec_bench.contracts.evolution import (
    EvolutionConfig,
    EvolutionCycleRecord,
    EvolutionObservation,
    EvolverModelConfig,
    VariationUsage,
    WorkspaceSnapshot,
)
from aec_bench.contracts.experiment_manifest import AgentConfig, TaskSelector
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.evaluation.behavioral import BehavioralLLMClient
from aec_bench.evolution.application import CandidateEvaluator, _build_analysis, _enrich_candidate
from aec_bench.evolution.backends.local import make_local_candidate_batch_planner, make_local_candidate_evaluator
from aec_bench.evolution.cancellation import (
    AVOCancellationCode,
    AVOCancellationReason,
    AVOCancellationSignal,
)
from aec_bench.evolution.checkpoint import AVOConfigurationIdentity
from aec_bench.evolution.core import AVOBudget, EvolutionState, VariationRequest, VariationResult
from aec_bench.evolution.enrichment import enrich_observations
from aec_bench.evolution.evaluation import CandidateBatchPlanner, CandidateEvaluationBatch, bind_candidate_evaluation
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.memory import AVOMemoryEntry
from aec_bench.evolution.model_provider import build_pydantic_model
from aec_bench.evolution.swarm.core import SwarmAgentResult, SwarmAssignment
from aec_bench.evolution.variation_operator import build_agentic_variation_operator
from aec_bench.evolution.workspace import Workspace

_log = logging.getLogger(__name__)

VariationOperator = Callable[[VariationRequest, Workspace, str], VariationResult]


class SwarmAgentEvolver:
    """Runs one functional evolution cycle per step() call for one swarm agent."""

    def __init__(
        self,
        workspace: Workspace,
        config: EvolutionConfig,
        batch_planner: CandidateBatchPlanner,
        solve_fn: CandidateEvaluator,
        classifier_llm: BehavioralLLMClient,
        variation_operator: VariationOperator,
        cancellation_signal: AVOCancellationSignal | None = None,
        timeout: float = 1800,
    ) -> None:
        self._workspace = workspace
        self._config = config
        self._batch_planner = batch_planner
        self._solve_fn = solve_fn
        self._classifier_llm = classifier_llm
        self._variation_operator = variation_operator
        self._cancellation_signal = cancellation_signal or AVOCancellationSignal()
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int | float)
            or not math.isfinite(timeout)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a finite positive number")
        self._timeout = timeout
        self._active_lock = Lock()
        self._active_future: asyncio.Future[SwarmAgentResult] | None = None
        self._cycle = 0
        self._history: list[EvolutionCycleRecord] = []
        self._graveyard = MutationGraveyard()
        self._memory: tuple[AVOMemoryEntry, ...] = ()

    async def step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
        """Run one evolution cycle asynchronously.

        Wraps synchronous work in a thread executor with a timeout guard.
        Default timeout is 30 minutes — generous for complex evolution cycles.
        """
        self._cancellation_signal.raise_if_cancelled()
        loop = asyncio.get_running_loop()
        worker = loop.run_in_executor(None, self._sync_step, assignment)
        with self._active_lock:
            self._active_future = worker
        try:
            return await asyncio.wait_for(asyncio.shield(worker), timeout=self._timeout)
        except TimeoutError as exc:
            self._cancellation_signal.cancel(
                AVOCancellationReason(
                    code=AVOCancellationCode.TIMEOUT,
                    detail=f"swarm agent step exceeded its {self._timeout}s timeout.",
                )
            )
            try:
                await asyncio.shield(worker)
            except BaseException as worker_error:
                raise TimeoutError(f"swarm agent step exceeded its {self._timeout}s timeout") from worker_error
            raise TimeoutError(f"swarm agent step exceeded its {self._timeout}s timeout") from exc
        except asyncio.CancelledError:
            self._cancellation_signal.cancel()
            try:
                await asyncio.shield(worker)
            except BaseException:
                pass
            raise
        finally:
            with self._active_lock:
                if worker.done():
                    self._active_future = None

    @property
    def cancellation_signal(self) -> AVOCancellationSignal:
        """Return this agent's private cooperative cancellation signal."""
        return self._cancellation_signal

    @property
    def worker_active(self) -> bool:
        """Return whether the synchronous worker can still write its workspace."""
        with self._active_lock:
            return self._active_future is not None and not self._active_future.done()

    def _sync_step(self, assignment: SwarmAssignment) -> SwarmAgentResult:
        """Run variation for one exact assignment and return no evaluation evidence."""
        self._cancellation_signal.raise_if_cancelled()
        self._cycle += 1
        batch = self._batch_planner(self._config.batch_size, self._cycle - 1)
        self._cancellation_signal.raise_if_cancelled()
        parent = bind_candidate_evaluation(
            assignment.parent,
            batch,
            self._solve_fn(assignment.parent, batch),
        )
        self._cancellation_signal.raise_if_cancelled()
        parent = _enrich_candidate(
            parent,
            batch,
            lambda observations: enrich_observations(observations, classifier_llm=self._classifier_llm),
        )
        self._cancellation_signal.raise_if_cancelled()
        evolution_state = EvolutionState.from_baseline(
            parent,
            structural_weight=self._config.structural_weight,
        )
        analysis = _build_analysis(parent, evolution_state)
        request = VariationRequest(
            run_id=assignment.run_id,
            selection=assignment.selection,
            parent=parent,
            inspirations=assignment.inspirations,
            analysis=analysis,
            scope=analysis.scope,
            history=tuple(self._history),
            graveyard=tuple(self._graveyard.browse(limit=self._graveyard.size)),
            cycle=self._cycle,
            memory=self._memory,
        )
        self._cancellation_signal.raise_if_cancelled()
        variation = self._variation_operator(request, self._workspace, assignment.assignment_id)
        self._cancellation_signal.raise_if_cancelled()
        self._memory = variation.memory
        parent_costs = tuple(
            None
            if observation.trial.cost is None or observation.trial.cost.estimated_cost_usd is None
            else float(observation.trial.cost.estimated_cost_usd)
            for observation in parent.observations
        )
        parent_cost = sum(cost for cost in parent_costs if cost is not None)
        if any(cost is None for cost in parent_costs):
            parent_cost_value: float | None = None
        else:
            parent_cost_value = parent_cost
        variation_usage = variation.usage
        development_cost = variation_usage.development_evaluation_cost_usd
        if variation_usage.development_evaluations and development_cost is None:
            combined_development_cost = None
        elif parent_cost_value is None:
            combined_development_cost = None
        else:
            combined_development_cost = (development_cost or 0.0) + parent_cost_value
        agent_usage = VariationUsage(
            model_requests=variation_usage.model_requests,
            tool_calls=variation_usage.tool_calls,
            development_evaluations=variation_usage.development_evaluations + 1,
            supervisor_interventions=variation_usage.supervisor_interventions,
            model_cost_usd=variation_usage.model_cost_usd,
            development_evaluation_cost_usd=combined_development_cost,
            elapsed_seconds=variation_usage.elapsed_seconds,
        )
        return SwarmAgentResult(
            agent_id=assignment.agent_id,
            assignment_id=assignment.assignment_id,
            variation=variation,
            agent_usage=agent_usage,
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
        self._model = model
        self._adapter = adapter
        self._timeout = timeout
        self._batch_size = batch_size
        self._improvement_threshold = improvement_threshold
        self._stagnation_window = stagnation_window
        self._structural_weight = structural_weight
        self._agent_workspaces: dict[str, Path] = {}
        self._agent_evolvers: dict[str, SwarmAgentEvolver] = {}

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
        if model_override and model_override != self._model:
            from aec_bench.providers.behavioral_llm import build_behavioral_llm_client

            classifier_llm = build_behavioral_llm_client(model=model_override)
            evolver_model_name = model_override
            solver_model = model_override
            _log.info("Agent %s using model override: %s", agent_id, model_override)
        else:
            classifier_llm = self._classifier_llm
            evolver_model_name = self._model
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
        development_experiment_id = f"{experiment_id}-development"
        development_batch_planner = make_local_candidate_batch_planner(
            task_dirs=self._task_dirs,
            model=solver_model,
            experiment_id=development_experiment_id,
            adapter=self._adapter,
            timeout=self._timeout,
        )
        development_evaluator = make_local_candidate_evaluator(
            workspace_root=agent_ws_path,
            candidate_identity=False,
        )
        cancellation_signal = AVOCancellationSignal()
        variation_operator = build_agentic_variation_operator(
            agent_model=build_pydantic_model(evolver_model_name),
            development_batch_planner=development_batch_planner,
            development_evaluator=development_evaluator,
            development_batch_size=self._batch_size,
            development_experiment_prefix=development_experiment_id,
            budget=AVOBudget(),
            compaction_llm=classifier_llm,
            # Agent workspaces are disposable copies. Keep the checkpoint in
            # the factory's source workspace so cleanup cannot remove the
            # only resume authority.
            checkpoint_root=self._workspace_source,
            configuration_identity=AVOConfigurationIdentity(
                model_identity=evolver_model_name,
                tool_identity="avo-tools:1",
                development_evaluator_identity=(
                    f"local:{development_experiment_id}:{self._adapter}:{solver_model}:timeout-{self._timeout}"
                ),
                configuration_identity=(
                    f"swarm-config:batch-{self._batch_size}:threshold-{self._improvement_threshold}"
                    f":stagnation-{self._stagnation_window}:structural-{self._structural_weight}"
                ),
            ),
            cancellation_signal=cancellation_signal,
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

        evolver = SwarmAgentEvolver(
            workspace=workspace,
            config=config,
            batch_planner=batch_planner,
            solve_fn=solve_fn,
            classifier_llm=classifier_llm,
            variation_operator=variation_operator,
            cancellation_signal=cancellation_signal,
            timeout=self._timeout,
        )
        self._agent_evolvers[agent_id] = evolver
        return evolver

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
        """Remove agent workspace copies only after all workers have stopped."""
        active = [agent_id for agent_id, evolver in self._agent_evolvers.items() if evolver.worker_active]
        if active:
            raise RuntimeError(f"cannot clean up active swarm agent workspaces: {', '.join(sorted(active))}")
        for agent_id, ws_path in self._agent_workspaces.items():
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)
                _log.info("Cleaned up workspace for %s", agent_id)
