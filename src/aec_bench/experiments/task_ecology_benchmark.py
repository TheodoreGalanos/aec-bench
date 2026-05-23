# ABOUTME: Builds deterministic task-ecology benchmark suites for evolution experiments.
# ABOUTME: Materialises fixed and population task sets plus comparison configs.

from __future__ import annotations

import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml

from aec_bench.evolution.config_loader import load_evolution_config
from aec_bench.evolution.report_data import list_runs
from aec_bench.generation.contracts import SampledInstance
from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import load_engine_module, load_template

Strategy = Literal["hill_climb", "qd"]

DEFAULT_ANCHOR_TASK_IDS = [
    "civil/bund-volume-calculation",
    "electrical/voltage-drop",
    "ground/consolidation-settlement",
    "mechanical/npsh-available",
    "structural/gravity-base-stability",
]

DEFAULT_DIFFICULTIES = ("easy", "medium", "hard")
DEFAULT_EXPERIMENT_SLUG = "task-ecology-exp1"
DEFAULT_MAX_CYCLES = 6
DEFAULT_SEED = 20260514


@dataclass(frozen=True)
class TemplateEntry:
    task_id: str
    domain: str
    source_task_path: str


@dataclass(frozen=True)
class BenchmarkSelection:
    fixed: list[TemplateEntry]
    population: list[TemplateEntry]


@dataclass(frozen=True)
class MaterialisedInstance:
    suite: str
    task_id: str
    template_task_id: str
    difficulty: str
    path: str


def load_template_entries(index_path: Path) -> list[TemplateEntry]:
    """Load template entries from a task genome catalogue index."""
    index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    root = index_path.parent
    entries: list[TemplateEntry] = []
    for entry in index.get("entries", []):
        genome_path = root / entry["path"]
        genome = yaml.safe_load(genome_path.read_text(encoding="utf-8"))
        entries.append(
            TemplateEntry(
                task_id=entry["task_id"],
                domain=entry["domain"],
                source_task_path=genome["source_task_path"],
            )
        )
    return entries


def select_benchmark_templates(
    entries: list[TemplateEntry],
    *,
    anchor_task_ids: list[str] | None = None,
    population_per_domain: int = 2,
    seed: int = DEFAULT_SEED,
) -> BenchmarkSelection:
    """Select fixed anchors and a balanced template population."""
    anchor_task_ids = anchor_task_ids or DEFAULT_ANCHOR_TASK_IDS
    by_id = {entry.task_id: entry for entry in entries}
    missing = [task_id for task_id in anchor_task_ids if task_id not in by_id]
    if missing:
        msg = f"Anchor template ids not found: {', '.join(missing)}"
        raise ValueError(msg)

    fixed = [by_id[task_id] for task_id in anchor_task_ids]
    fixed_ids = {entry.task_id for entry in fixed}
    by_domain: dict[str, list[TemplateEntry]] = {}
    for entry in entries:
        if entry.task_id in fixed_ids:
            continue
        by_domain.setdefault(entry.domain, []).append(entry)

    rng = random.Random(seed)
    population: list[TemplateEntry] = []
    for domain in sorted(by_domain):
        candidates = sorted(by_domain[domain], key=lambda item: item.task_id)
        rng.shuffle(candidates)
        population.extend(sorted(candidates[:population_per_domain], key=lambda item: item.task_id))

    return BenchmarkSelection(fixed=fixed, population=population)


def materialise_suite(
    *,
    repo_root: Path,
    suite_name: str,
    entries: list[TemplateEntry],
    output_root: Path,
    seed: int,
    difficulties: tuple[str, ...] = DEFAULT_DIFFICULTIES,
) -> list[MaterialisedInstance]:
    """Generate concrete task instances for the selected templates."""
    suite_root = output_root / suite_name
    if suite_root.exists():
        shutil.rmtree(suite_root)
    suite_root.mkdir(parents=True, exist_ok=True)

    materialised: list[MaterialisedInstance] = []
    for template_index, entry in enumerate(entries):
        template_dir = repo_root / entry.source_task_path
        config, loaded_template_dir = load_template(template_dir)
        engine_module = load_engine_module(loaded_template_dir)
        engine_source = (loaded_template_dir / "engine.py").read_text(encoding="utf-8")

        for difficulty_index, difficulty in enumerate(difficulties):
            instance = _sample_instance_with_retries(
                template_task_id=entry.task_id,
                config=config,
                engine_compute=engine_module.compute,
                difficulty=difficulty,
                seed=seed + template_index * 100,
                instance_index=difficulty_index,
            )
            instance_dir = scaffold_task_instance(
                config=config,
                engine_source=engine_source,
                template_dir=loaded_template_dir,
                instance=instance,
                output_dir=suite_root,
            )
            materialised.append(
                MaterialisedInstance(
                    suite=suite_name,
                    task_id=instance_dir.relative_to(output_root).as_posix(),
                    template_task_id=entry.task_id,
                    difficulty=difficulty,
                    path=instance_dir.relative_to(repo_root).as_posix(),
                )
            )

    return materialised


def _sample_instance_with_retries(
    *,
    template_task_id: str,
    config,
    engine_compute,
    difficulty: str,
    seed: int,
    instance_index: int,
    max_attempts: int = 50,
) -> SampledInstance:
    """Sample an instance, retrying invalid random parameter combinations."""
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return sample_instance(
                config=config,
                engine_compute=engine_compute,
                difficulty_name=difficulty,
                seed=seed,
                instance_index=instance_index + attempt * 1000,
            )
        except ValueError as exc:
            last_error = exc
    msg = (
        f"Could not sample valid {difficulty} instance for {template_task_id} "
        f"after {max_attempts} attempts: {last_error}"
    )
    raise ValueError(msg) from last_error


def scaffold_workspace(workspace_path: Path, *, name: str) -> Path:
    """Create an evolution workspace if it does not already exist."""
    (workspace_path / "prompts").mkdir(parents=True, exist_ok=True)
    (workspace_path / "skills").mkdir(parents=True, exist_ok=True)
    manifest = {
        "name": name,
        "agent_adapter": "tool_loop",
        "evolvable_layers": ["prompts", "skills"],
    }
    (workspace_path / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    (workspace_path / "prompts" / "system.md").write_text(
        "You are an expert engineering agent. Solve the task carefully and verify your work.\n",
        encoding="utf-8",
    )
    return workspace_path


def build_arm_config(
    *,
    experiment_slug: str,
    suite_name: str,
    strategy: Strategy,
    workspace_path: Path,
    batch_size: int,
    max_cycles: int,
    include_patterns: list[str] | None = None,
    classifier_model: str = "claude-haiku-4-5-20251001",
    evolver_model: str = "claude-sonnet-4-20250514",
    solver_model: str = "claude-sonnet-4-20250514",
) -> dict:
    """Build one evolution YAML config for a benchmark arm."""
    return {
        "workspace_path": str(workspace_path),
        "models": {
            "classifier": classifier_model,
            "evolver": evolver_model,
        },
        "tasks": {
            "include_patterns": include_patterns or [f"generated/{experiment_slug}/{suite_name}/*"],
        },
        "batch_size": batch_size,
        "max_cycles": max_cycles,
        "improvement_threshold": 0.02,
        "stagnation_window": 3,
        "structural_weight": 0.3,
        "solver": {
            "name": f"{experiment_slug}-solver",
            "adapter": "tool_loop",
            "model": solver_model,
        },
        "backend": "local",
        "timeout": 1800,
        "strategy": strategy,
    }


def load_pressure_task_patterns(
    summary_path: Path,
    *,
    score_threshold: float = 0.85,
) -> dict[str, list[str]]:
    """Load below-threshold baseline tasks as exact selector include patterns."""
    summary = yaml.safe_load(summary_path.read_text(encoding="utf-8"))
    pressure_tasks = summary.get("below_threshold_tasks", [])
    patterns: dict[str, list[str]] = {"fixed": [], "population": []}
    for row in pressure_tasks:
        if float(row["reward"]) >= score_threshold:
            continue
        suite = row["suite"]
        if suite not in patterns:
            continue
        patterns[suite].append(row["task_id"])
    return {suite: sorted(task_ids) for suite, task_ids in patterns.items()}


def write_pressure_benchmark_configs(
    *,
    repo_root: Path,
    source_experiment_slug: str,
    pressure_experiment_slug: str,
    config_dir: Path,
    workspace_root: Path,
    pressure_task_patterns: dict[str, list[str]],
    batch_size: int,
    max_cycles: int,
) -> list[Path]:
    """Write fixed/population by hill/QD configs for pressure-bearing tasks only."""
    config_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for suite_name in ("fixed", "population"):
        include_patterns = pressure_task_patterns.get(suite_name, [])
        if not include_patterns:
            msg = f"No pressure tasks found for suite {suite_name!r}"
            raise ValueError(msg)
        for strategy in ("hill_climb", "qd"):
            arm_slug = f"{suite_name}-{strategy.replace('_', '-')}"
            workspace = workspace_root / f"{pressure_experiment_slug}-{arm_slug}"
            scaffold_workspace(workspace, name=f"{pressure_experiment_slug}-{arm_slug}")
            config = build_arm_config(
                experiment_slug=source_experiment_slug,
                suite_name=suite_name,
                strategy=strategy,  # type: ignore[arg-type]
                workspace_path=workspace.relative_to(repo_root),
                batch_size=batch_size,
                max_cycles=max_cycles,
                include_patterns=include_patterns,
            )
            config["solver"]["name"] = f"{pressure_experiment_slug}-solver"
            path = config_dir / f"{arm_slug}.yaml"
            path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            paths.append(path)
    return paths


def write_benchmark_configs(
    *,
    repo_root: Path,
    experiment_slug: str,
    config_dir: Path,
    workspace_root: Path,
    batch_size: int,
    max_cycles: int,
) -> list[Path]:
    """Write the four fixed/population by hill/QD evolution configs."""
    config_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for suite_name in ("fixed", "population"):
        for strategy in ("hill_climb", "qd"):
            arm_slug = f"{suite_name}-{strategy.replace('_', '-')}"
            workspace = workspace_root / f"{experiment_slug}-{arm_slug}"
            scaffold_workspace(workspace, name=f"{experiment_slug}-{arm_slug}")
            config = build_arm_config(
                experiment_slug=experiment_slug,
                suite_name=suite_name,
                strategy=strategy,  # type: ignore[arg-type]
                workspace_path=workspace.relative_to(repo_root),
                batch_size=batch_size,
                max_cycles=max_cycles,
            )
            path = config_dir / f"{arm_slug}.yaml"
            path.write_text(yaml.safe_dump(config, sort_keys=False), encoding="utf-8")
            paths.append(path)
    return paths


def build_benchmark(
    *,
    repo_root: Path,
    index_path: Path,
    output_root: Path,
    config_dir: Path,
    workspace_root: Path,
    seed: int = DEFAULT_SEED,
    population_per_domain: int = 2,
    batch_size: int = 5,
    max_cycles: int = DEFAULT_MAX_CYCLES,
    difficulties: tuple[str, ...] = DEFAULT_DIFFICULTIES,
) -> dict:
    """Build Experiment 1 benchmark suites, workspaces, configs, and manifest."""
    entries = load_template_entries(index_path)
    selection = select_benchmark_templates(
        entries,
        population_per_domain=population_per_domain,
        seed=seed,
    )

    fixed_instances = materialise_suite(
        repo_root=repo_root,
        suite_name="fixed",
        entries=selection.fixed,
        output_root=output_root,
        seed=seed,
        difficulties=difficulties,
    )
    population_instances = materialise_suite(
        repo_root=repo_root,
        suite_name="population",
        entries=selection.population,
        output_root=output_root,
        seed=seed + 1000,
        difficulties=difficulties,
    )
    config_paths = write_benchmark_configs(
        repo_root=repo_root,
        experiment_slug=output_root.name,
        config_dir=config_dir,
        workspace_root=workspace_root,
        batch_size=batch_size,
        max_cycles=max_cycles,
    )

    run_commands = []
    for path in config_paths:
        config_path = path.relative_to(repo_root).as_posix()
        run_commands.append(f"uv run aec-bench evolve run --config {config_path} --tasks-root tasks")

    manifest = {
        "experiment": output_root.name,
        "seed": seed,
        "difficulties": list(difficulties),
        "population_per_domain": population_per_domain,
        "batch_size": batch_size,
        "max_cycles": max_cycles,
        "suites": {
            "fixed": {
                "template_count": len(selection.fixed),
                "instance_count": len(fixed_instances),
                "templates": [entry.task_id for entry in selection.fixed],
                "instances": [instance.__dict__ for instance in fixed_instances],
            },
            "population": {
                "template_count": len(selection.population),
                "instance_count": len(population_instances),
                "templates": [entry.task_id for entry in selection.population],
                "instances": [instance.__dict__ for instance in population_instances],
            },
        },
        "configs": [path.relative_to(repo_root).as_posix() for path in config_paths],
        "run_commands": run_commands,
    }
    (output_root / "manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False),
        encoding="utf-8",
    )
    return manifest


def summarise_benchmark_runs(config_dir: Path) -> list[dict]:
    """Summarise the latest run for each benchmark arm config."""
    rows: list[dict] = []
    for config_path in sorted(config_dir.glob("*.yaml")):
        if config_path.name == "manifest.yaml":
            continue
        config = load_evolution_config(config_path)
        workspace_path = Path(config.workspace_path)
        runs = list_runs(workspace_path) if workspace_path.exists() else []
        latest = runs[0] if runs else None
        rows.append(
            {
                "arm": config_path.stem,
                "workspace": str(workspace_path),
                "strategy": config.strategy,
                "status": "complete" if latest else "pending",
                "cycles": latest["cycles"] if latest else 0,
                "best_score": latest["best_score"] if latest else None,
                "final_score": latest["final_score"] if latest else None,
                "run_id": latest["run_id"] if latest else None,
            }
        )
    return rows
