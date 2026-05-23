# ABOUTME: Per-agent evolver that wraps the evolution engine + solver for swarm execution.
# ABOUTME: Each agent gets an independent workspace copy, engine instance, and solver.

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aec_bench.contracts.evolution import (
    BehaviourDescriptor,
    EvolutionCycleRecord,
    EvolutionObservation,
    ObservationEnrichment,
)
from aec_bench.evolution.backends.local import SolveFn, make_local_solve_fn
from aec_bench.evolution.behaviour import extract_behaviour_descriptor
from aec_bench.evolution.engine import AECEvolutionEngine
from aec_bench.evolution.graveyard import MutationGraveyard
from aec_bench.evolution.workspace import Workspace

_log = logging.getLogger(__name__)

# Per-token pricing for Sonnet 4 on Bedrock.
_INPUT_COST_PER_MTOK = 3.0
_OUTPUT_COST_PER_MTOK = 15.0
_CACHE_READ_COST_PER_MTOK = 0.30
_CACHE_WRITE_COST_PER_MTOK = 3.75


def _estimate_trial_cost(trial_record: Any) -> float:
    """Estimate the USD cost of a trial from its CostRecord.

    Uses estimated_cost_usd if available. When cache token counts are
    present, computes cache-aware pricing. Otherwise uses a heuristic:
    in multi-turn conversations, ~80% of input tokens are typically
    cached after the first turn.
    """
    cost = getattr(trial_record, "cost", None)
    if cost is None:
        return 0.0
    estimated = getattr(cost, "estimated_cost_usd", None)
    if estimated is not None:
        return float(estimated)

    tokens_in = getattr(cost, "tokens_in", 0) or 0
    tokens_out = getattr(cost, "tokens_out", 0) or 0
    cache_read = getattr(cost, "cache_read_tokens", None)
    cache_write = getattr(cost, "cache_write_tokens", None)

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
    workspace_version: str
    parent_version: str = ""


def _extract_discipline(task_id: str) -> str:
    """Extract discipline from task_id, e.g. 'electrical/voltage-drop/...' → 'electrical'."""
    return task_id.split("/")[0]


class SwarmAgentEvolver:
    """Runs one evolution cycle per step() call for a single swarm agent.

    Wraps the existing 6-phase AECEvolutionEngine with a LocalSolver.
    Each agent has its own workspace copy, engine instance, and solve function.
    The step() method is async (runs synchronous work in a thread executor).
    """

    def __init__(
        self,
        workspace: Workspace,
        engine: AECEvolutionEngine,
        solve_fn: SolveFn,
        batch_size: int = 1,
    ) -> None:
        self._workspace = workspace
        self._engine = engine
        self._solve_fn = solve_fn
        self._batch_size = batch_size
        self._shared_graveyard: MutationGraveyard | None = None
        self._context_provider: Any | None = None
        self._cycle = 0
        self._history: list[EvolutionCycleRecord] = []

    def set_shared_state(
        self,
        graveyard: MutationGraveyard | None = None,
        context_provider: Any | None = None,
    ) -> None:
        """Inject shared swarm state into this evolver.

        Called by SwarmManager after factory creation to connect the
        evolver to shared graveyard and archive context.
        """
        if graveyard is not None:
            self._shared_graveyard = graveyard
        if context_provider is not None:
            self._context_provider = context_provider

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

        # 1. Export current workspace state
        version_tag = self._workspace.list_versions()[-1].tag if self._workspace.list_versions() else "evo-0"
        snapshot = self._workspace.export_snapshot(version_tag)

        # 2. Solve — run tasks against current harness
        trial_records = self._solve_fn(snapshot, self._batch_size)

        # 3. Build observations (engine enriches in CLASSIFY phase)
        observations = [
            EvolutionObservation(
                trial=tr,
                enrichment=ObservationEnrichment(),
                workspace_version=version_tag,
                discipline=_extract_discipline(tr.task.task_id),
            )
            for tr in trial_records
        ]

        # 4. Inject archive context into workspace system prompt so the
        #    evolution engine's evolver LLM sees archive state, notes,
        #    nudges, and pivot instructions from the swarm manager.
        original_prompt = self._workspace.read_prompt()
        if self._context_provider is not None:
            try:
                archive_context = self._context_provider()
                if archive_context:
                    augmented = original_prompt + "\n\n---\n\n" + archive_context
                    self._workspace.write_prompt(augmented)
            except Exception:
                _log.warning("Failed to inject archive context", exc_info=True)

        # 5. Run the 6-phase engine step (shared graveyard gives evolver
        #    visibility into failures from all agents, not just this one)
        try:
            step_result = self._engine.step(
                self._workspace,
                observations,
                self._history,
                graveyard=self._shared_graveyard,
            )
        finally:
            # Restore original prompt to avoid context accumulation
            self._workspace.write_prompt(original_prompt)

        # 5. Cleanup solver temp workspaces
        if hasattr(self._solve_fn, "cleanup"):
            self._solve_fn.cleanup()

        # 6. Track history
        if step_result.cycle_record is not None:
            self._history.append(step_result.cycle_record)

        # 7. Extract BD from enriched observations (includes trace_digest for full BD)
        bd = None
        enriched = step_result.enriched_observations or observations
        if enriched:
            bd = extract_behaviour_descriptor(enriched[0])

        # 8. Compute score, cost, and parent version
        score = step_result.cycle_record.batch_score if step_result.cycle_record else 0.0
        evolver_cost = step_result.cycle_record.evolver_cost if step_result.cycle_record else 0.0
        version_after = step_result.cycle_record.workspace_version_after if step_result.cycle_record else version_tag
        version_before = step_result.cycle_record.workspace_version_before if step_result.cycle_record else ""

        solver_cost = sum(_estimate_trial_cost(tr) for tr in trial_records)
        total_cost = (evolver_cost or 0.0) + solver_cost

        return SwarmStepResult(
            score=score,
            bd=bd,
            cost_usd=total_cost,
            workspace_version=version_after,
            parent_version=version_before,
        )


class SwarmEvolverFactory:
    """Creates per-agent SwarmAgentEvolver instances from swarm config.

    Each agent gets:
    - An independent workspace copy (shutil.copytree from source)
    - Its own AECEvolutionEngine (separate stagnation tracking)
    - Its own LocalSolver
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

        # 4. Create engine (separate state tracking per agent)
        engine = AECEvolutionEngine(
            classifier_llm=classifier_llm,
            evolver_llm=evolver_llm,
            evolver_model_name=evolver_model_name,
            improvement_threshold=self._improvement_threshold,
            stagnation_window=self._stagnation_window,
            structural_weight=self._structural_weight,
        )

        # 5. Create solver (uses agent's model, not factory default)
        experiment_id = f"swarm-{agent_id}"
        solve_fn = make_local_solve_fn(
            task_dirs=self._task_dirs,
            model=solver_model,
            experiment_id=experiment_id,
            adapter=self._adapter,
            timeout=self._timeout,
        )

        return SwarmAgentEvolver(
            workspace=workspace,
            engine=engine,
            solve_fn=solve_fn,
            batch_size=self._batch_size,
        )

    def cleanup(self) -> None:
        """Remove all agent workspace copies."""
        for agent_id, ws_path in self._agent_workspaces.items():
            if ws_path.exists():
                shutil.rmtree(ws_path, ignore_errors=True)
                _log.info("Cleaned up workspace for %s", agent_id)
