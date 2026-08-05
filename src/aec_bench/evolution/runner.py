# ABOUTME: Entry point that assembles a fully-wired EvolutionOrchestrator.
# ABOUTME: Wires workspace loading, git versioning, LLM clients, solve function, and engine.

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from aec_bench.contracts.evolution import EvolutionConfig, TaskGenerateConfig, WorkspaceSnapshot
from aec_bench.evolution.backends.local import SolveFn, make_local_solve_fn, make_stub_solve_fn
from aec_bench.evolution.engine import AECEvolutionEngine
from aec_bench.evolution.llm import build_evolution_llm_clients
from aec_bench.evolution.orchestrator import EvolutionOrchestrator
from aec_bench.evolution.workspace import Workspace

_log = logging.getLogger(__name__)


def build_evolution_runner(
    *,
    config: EvolutionConfig,
    task_dirs: list[Path],
    model: str,
    adapter: str = "rlm",
    timeout: int = 1800,
) -> EvolutionOrchestrator:
    """Assemble a fully-wired EvolutionOrchestrator ready to call .run().

    Loads the workspace from config.workspace_path, initialises git versioning,
    builds LLM clients, selects the solve function based on whether task_dirs
    is populated, and constructs the engine and orchestrator.
    """
    # 1. Load workspace
    workspace = Workspace(Path(config.workspace_path))

    # 2. Initialise git versioning (tags initial state as evo-0)
    workspace.init_versioning()

    # 3. Build LLM clients for classifier and evolver roles
    classifier_llm, evolver_llm = build_evolution_llm_clients(config.models)

    # 4. Build solve function — local execution when task_dirs provided, stub otherwise
    experiment_id = f"evo-{workspace.manifest.name}"
    solve_fn: SolveFn
    if task_dirs:
        solve_fn = make_local_solve_fn(
            task_dirs=task_dirs,
            model=model,
            experiment_id=experiment_id,
            adapter=adapter,
            timeout=timeout,
            workspace_root=Path(config.workspace_path),
        )
    else:
        solve_fn = make_stub_solve_fn([])

    # 5. Build the evolution engine with thresholds from config
    engine = AECEvolutionEngine(
        classifier_llm=classifier_llm,
        evolver_llm=evolver_llm,
        evolver_model_name=config.models.evolver if hasattr(config, "models") else None,
        improvement_threshold=config.improvement_threshold,
        stagnation_window=config.stagnation_window,
        structural_weight=config.structural_weight,
    )

    # 6. Build selection strategy — hill-climb is the default for the simple runner
    from aec_bench.evolution.strategy import HillClimbStrategy

    strategy = HillClimbStrategy()

    # 7. Assemble and return the orchestrator
    return EvolutionOrchestrator(
        workspace=workspace,
        engine=engine,
        solve_fn=solve_fn,
        config=config,
        strategy=strategy,
    )


def build_evolution_runner_from_config(
    *,
    config: EvolutionConfig,
    tasks_root: Path | None = None,
) -> EvolutionOrchestrator:
    """Assemble a fully-wired EvolutionOrchestrator from a single EvolutionConfig.

    Reads solver model, adapter, and backend entirely from the config so that
    a YAML-loaded config is the only required input. tasks_root, when provided,
    is used to resolve concrete task directories from config.task_selector.
    """
    from aec_bench.evolution.config_loader import resolve_task_dirs

    # 1. Load workspace
    workspace = Workspace(Path(config.workspace_path))

    # 2. Initialise git versioning (tags initial state as evo-0)
    workspace.init_versioning()

    # 3. Build LLM clients for classifier and evolver roles
    classifier_llm, evolver_llm = build_evolution_llm_clients(config.models)

    # 4. Resolve task directories — from generation and/or on-disk selector
    task_dirs: list[Path] = []
    if config.generate is not None:
        task_dirs.extend(generate_task_instances(config.generate))
    if tasks_root is not None:
        task_dirs.extend(resolve_task_dirs(config.task_selector, tasks_root))

    # 5. Extract model and adapter from config.solver when present, else use defaults
    model: str = config.models.evolver
    adapter: str = "rlm"
    timeout: int = config.timeout
    if config.solver is not None:
        model = config.solver.model
        adapter = config.solver.adapter

    # 6. Build solve function based on config.backend
    experiment_id = f"evo-{workspace.manifest.name}"
    if config.backend in ("modal", "morph") and config.solver is not None:
        solve_fn = _build_harbor_solve_fn(
            config=config,
            task_dirs=task_dirs,
            experiment_id=experiment_id,
        )
    elif task_dirs and config.backend == "local":
        solve_fn = make_local_solve_fn(
            task_dirs=task_dirs,
            model=model,
            experiment_id=experiment_id,
            adapter=adapter,
            timeout=timeout,
            workspace_root=Path(config.workspace_path),
        )
    else:
        if config.backend in ("modal", "morph"):
            _log.warning(
                "backend=%r requires solver config (via harness_config or explicit solver). "
                "Falling back to stub solve function.",
                config.backend,
            )
        solve_fn = make_stub_solve_fn([])

    # 7. Build the evolution engine with thresholds from config
    engine = AECEvolutionEngine(
        classifier_llm=classifier_llm,
        evolver_llm=evolver_llm,
        evolver_model_name=config.models.evolver,
        improvement_threshold=config.improvement_threshold,
        stagnation_window=config.stagnation_window,
        structural_weight=config.structural_weight,
    )

    # 8. Build selection strategy from config
    from aec_bench.evolution.strategy import HillClimbStrategy, QDStrategy

    if config.strategy == "qd":
        strategy: HillClimbStrategy | QDStrategy = QDStrategy(evolver_model=config.models.evolver)
    else:
        strategy = HillClimbStrategy()

    # 9. Assemble and return the orchestrator
    return EvolutionOrchestrator(
        workspace=workspace,
        engine=engine,
        solve_fn=solve_fn,
        config=config,
        strategy=strategy,
    )


def _resolve_template(name_or_path: str) -> Path:
    """Resolve a template name or path to a directory.

    Accepts either a builtin template name (e.g. ``"voltage-drop"``) or a
    filesystem path. Raises FileNotFoundError when the template cannot be found.
    """
    # Try as a filesystem path first
    candidate = Path(name_or_path)
    if candidate.is_dir() and (candidate / "params.toml").exists():
        return candidate

    # Search builtin templates by name
    from aec_bench.templates.registry import discover_templates

    templates, _diagnostics = discover_templates()
    for template in templates:
        if template.config.meta.name == name_or_path:
            return template.path

    msg = f"Template '{name_or_path}' not found as path or builtin template"
    raise FileNotFoundError(msg)


def generate_task_instances(gen_config: TaskGenerateConfig) -> list[Path]:
    """Generate parameterised task instances from a template into a temp directory.

    Uses the existing generation pipeline (sample_instance + scaffold_task_instance)
    to produce ``gen_config.count`` instances, cycling through the configured
    difficulties. Returns a list of generated task directory paths.

    The template field can be a builtin template name (e.g. ``"voltage-drop"``)
    or an absolute/relative path to a template directory.
    """
    from aec_bench.generation.sampler import sample_instance
    from aec_bench.generation.scaffolder import scaffold_task_instance
    from aec_bench.templates.registry import load_template

    template_dir = _resolve_template(gen_config.template)
    template = load_template(template_dir)

    output_dir = Path(tempfile.mkdtemp(prefix="aec-bench-evo-tasks-"))
    difficulties = gen_config.difficulties
    generated_dirs: list[Path] = []

    for i in range(gen_config.count):
        difficulty = difficulties[i % len(difficulties)]
        instance = sample_instance(
            template=template,
            difficulty_name=difficulty,
            seed=gen_config.seed,
            instance_index=i,
        )
        instance_dir = scaffold_task_instance(
            template=template,
            instance=instance,
            output_dir=output_dir,
        )
        generated_dirs.append(instance_dir)
        _log.info("Generated task instance: %s", instance_dir.name)

    _log.info("Generated %d task instances in %s", len(generated_dirs), output_dir)
    return generated_dirs


def _build_harbor_solve_fn(
    *,
    config: EvolutionConfig,
    task_dirs: list[Path],
    experiment_id: str,
) -> SolveFn:
    """Build an evolution solve function that consumes the current Harbor workflow."""

    from aec_bench.contracts.experiment_manifest import ComputeConfig, ExperimentManifest, TaskSelector
    from aec_bench.contracts.task_definition import TaskDefinition
    from aec_bench.contracts.trial_record import TrialRecord
    from aec_bench.evolution.backends.local import inject_snapshot_into_workspace
    from aec_bench.harness.harbor_workflow import SynchronousHarborWorkflow
    from aec_bench.tasks.loader import load_task_definition

    solver = config.solver
    assert solver is not None
    project_root = Path(__file__).resolve().parents[3]
    artifact_root = Path(config.workspace_path) / "artifacts"
    resolved: list[tuple[TaskDefinition, Path, Path]] = []
    for task_dir in task_dirs:
        try:
            tasks_root = task_dir.parents[2]
            resolved.append((load_task_definition(task_dir, tasks_root), task_dir, tasks_root))
        except (OSError, ValueError):
            _log.warning("Failed to resolve task: %s", task_dir, exc_info=True)

    call_count = 0

    def solve(snapshot: WorkspaceSnapshot, batch_size: int) -> list[TrialRecord]:
        nonlocal call_count
        records: list[TrialRecord] = []
        for index, (task, task_dir, tasks_root) in enumerate(resolved[:batch_size]):
            try:
                inject_snapshot_into_workspace(snapshot, task_dir)
                manifest = ExperimentManifest(
                    experiment_id=experiment_id,
                    name=f"Evolution solve {call_count}:{index}",
                    tasks=TaskSelector(include_patterns=[task.task_id]),
                    agents=[solver],
                    compute=ComputeConfig(
                        backend=config.backend,
                        timeout_override=config.timeout,
                    ),
                    repetitions=1,
                )
                workflow = SynchronousHarborWorkflow(
                    project_root=project_root,
                    repo_root=project_root,
                    tasks_root=tasks_root,
                    ledger_root=artifact_root / "ledger",
                    jobs_root=artifact_root / "jobs",
                )
                result = workflow.run(
                    manifest=manifest,
                    config_path=artifact_root / f"harbor-{call_count}-{index}.yaml",
                    resolved_tasks=(task,),
                    task_path_overrides={task.task_id: task_dir.resolve()},
                )
                records.extend(
                    TrialRecord.model_validate_json(path.read_text(encoding="utf-8"))
                    for path in result.import_result.ledger_paths
                )
            except Exception:
                _log.exception("Harbor evolution task failed: %s", task.task_id)
        call_count += 1
        return records

    return solve
