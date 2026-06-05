# ABOUTME: Entry point that assembles a fully-wired EvolutionOrchestrator.
# ABOUTME: Wires workspace loading, git versioning, LLM clients, solve function, and engine.

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from aec_bench.contracts.evolution import EvolutionConfig, TaskGenerateConfig
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
    if config.backend in ("harbor", "modal", "morph") and config.solver is not None:
        solve_fn = _build_remote_solve_fn(
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
        if config.backend in ("harbor", "modal", "morph"):
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

    for config, path in discover_templates():
        if config.meta.name == name_or_path:
            return path

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
    from aec_bench.templates.registry import load_engine_module, load_template

    template_dir = _resolve_template(gen_config.template)
    config, template_dir = load_template(template_dir)
    engine_module = load_engine_module(template_dir)
    engine_source = (template_dir / "engine.py").read_text(encoding="utf-8")

    output_dir = Path(tempfile.mkdtemp(prefix="aec-bench-evo-tasks-"))
    difficulties = gen_config.difficulties
    generated_dirs: list[Path] = []

    for i in range(gen_config.count):
        difficulty = difficulties[i % len(difficulties)]
        instance = sample_instance(
            config=config,
            engine_compute=engine_module.compute,
            difficulty_name=difficulty,
            seed=gen_config.seed,
            instance_index=i,
        )
        instance_dir = scaffold_task_instance(
            config=config,
            engine_source=engine_source,
            template_dir=template_dir,
            instance=instance,
            output_dir=output_dir,
        )
        generated_dirs.append(instance_dir)
        _log.info("Generated task instance: %s", instance_dir.name)

    _log.info("Generated %d task instances in %s", len(generated_dirs), output_dir)
    return generated_dirs


def _build_remote_solve_fn(
    *,
    config: EvolutionConfig,
    task_dirs: list[Path],
    experiment_id: str,
) -> SolveFn:
    """Build a remote solve function from config.

    Constructs a remote ComputeBackend, adapter, and resolved tasks from the solver config.
    All harness imports are deferred to avoid requiring Modal SDK at module load.
    Falls back to the stub solve function when backend dependencies are not installed.
    """
    try:
        from aec_bench.adapters.factory import build_remote_adapter
        from aec_bench.evolution.backends.harbor import make_harbor_solve_fn
        from aec_bench.harness.trial_runner import TrialRunner
        from aec_bench.tasks.instance import ResolvedTaskInstance, resolve_instance_paths
        from aec_bench.tasks.loader import load_task_definition
    except ImportError as exc:
        _log.error("Remote backend wiring failed to import common dependencies. Error: %s", exc)
        return make_stub_solve_fn([])

    assert config.solver is not None  # caller guarantees this

    # Build adapter from solver config
    adapter = build_remote_adapter(config.solver)

    # Build artifacts dir alongside the workspace
    artifacts_dir = Path(config.workspace_path) / "artifacts"

    backend: object
    if config.backend == "morph":
        try:
            from aec_bench.harness.morph_runner import MorphSandboxRunner
            from aec_bench.providers.morph_cloud import MorphCloudOperations
        except ImportError as exc:
            _log.error(
                "Morph backend requires Morph Cloud dependencies. Install with: uv add morphcloud. Error: %s",
                exc,
            )
            return make_stub_solve_fn([])
        backend = MorphSandboxRunner(
            operations=MorphCloudOperations(),
            artifacts_dir=artifacts_dir,
        )
    else:
        try:
            from aec_bench.harness.modal_runner import ModalSandboxRunner, ModalSdkOperations
        except ImportError as exc:
            _log.error("Harbor/modal backend requires Modal SDK. Install with: uv add modal. Error: %s", exc)
            return make_stub_solve_fn([])
        backend = ModalSandboxRunner(
            operations=ModalSdkOperations(),
            artifacts_dir=artifacts_dir,
        )

    # Resolve task instances — tasks_root is the parent of the first task dir's
    # discipline segment, inferred as the common ancestor two levels up from each
    # task_dir so that derive_task_id produces the right slash-separated IDs.
    resolved_tasks: list[ResolvedTaskInstance] = []
    for task_dir in task_dirs:
        try:
            # tasks_root is two levels above the task instance dir
            # (tasks/<discipline>/<task-type>/<instance> → tasks_root = tasks/)
            tasks_root = task_dir.parents[2]
            task_def = load_task_definition(task_dir, tasks_root)
            resolved = resolve_instance_paths(task_def, task_dir)
            resolved_tasks.append(resolved)
        except Exception:
            _log.warning("Failed to resolve task: %s", task_dir, exc_info=True)

    # Build trial runner
    trial_runner = TrialRunner(artifacts_dir=artifacts_dir)

    backend_tasks: list[object] = list(resolved_tasks)

    return make_harbor_solve_fn(
        trial_runner=trial_runner,
        backend=backend,
        tasks=backend_tasks,
        adapter=adapter,
        experiment_id=experiment_id,
        runtime_image=f"evolution-{config.solver.adapter}",
    )
