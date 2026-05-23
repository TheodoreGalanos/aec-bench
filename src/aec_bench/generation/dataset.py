# ABOUTME: Dataset composition engine for generating evaluation suites from templates.
# ABOUTME: Parses suite.toml, allocates instances with coverage controls, and writes dataset.json.

from __future__ import annotations

import json
import logging
import math
import tomllib
from collections import defaultdict
from datetime import UTC, datetime
from fnmatch import fnmatch
from pathlib import Path

from pydantic import Field

from aec_bench.contracts.validators import StrictModel
from aec_bench.templates.contracts import TemplateConfig, ToolMode

logger = logging.getLogger(__name__)


class CoverageConfig(StrictModel):
    """Coverage targets for difficulty distribution across the dataset."""

    difficulties: dict[str, float]
    min_tasks_per_discipline: int = 3


class TemplateSelection(StrictModel):
    """Template discovery and filtering configuration."""

    include: list[str] = Field(default_factory=lambda: ["*/*"])
    user_dirs: list[Path] = Field(default_factory=list)


class VisibilityMix(StrictModel):
    """Target visibility level ratios across the dataset."""

    mix: dict[str, float]


class ToolModeMix(StrictModel):
    """Target tool mode ratios across the dataset."""

    mix: dict[str, float]


class InstanceConfig(StrictModel):
    """Instance count configuration."""

    per_task: int = 5
    total_max: int = 200


class OutputConfig(StrictModel):
    """Output directory configuration."""

    dir: Path = Path("./tasks/")


class CoverageWarning(StrictModel):
    """A warning about a coverage target that couldn't be met."""

    category: str
    message: str
    target: float | int
    achieved: float | int


class SuiteConfig(StrictModel):
    """Top-level dataset suite configuration parsed from suite.toml."""

    name: str
    seed: int
    coverage: CoverageConfig
    templates: TemplateSelection
    visibility: VisibilityMix
    tool_mode: ToolModeMix
    instances: InstanceConfig
    output: OutputConfig

    def tool_mode_normalised(self) -> dict[str, float]:
        """Return tool_mode.mix with underscored keys normalised to hyphenated ToolMode values."""
        return {k.replace("_", "-"): v for k, v in self.tool_mode.mix.items()}


def normalise_ratios(
    ratios: dict[str, float],
) -> tuple[dict[str, float], str | None]:
    """Normalise ratio values to sum to 1.0.

    Returns (normalised_dict, warning_or_none).
    Warns if the raw sum deviates from 1.0 by more than 0.01.
    """
    total = sum(ratios.values())
    warning: str | None = None

    if total == 0:
        msg = "ratios must have at least one non-zero value"
        raise ValueError(msg)

    if abs(total - 1.0) > 0.01:
        warning = f"ratios sum to {total:.3f}, expected ~1.0; normalising"
        logger.warning(warning)

    normalised = {k: v / total for k, v in ratios.items()}
    return normalised, warning


def largest_remainder_round(ratios: dict[str, float], *, total: int) -> dict[str, int]:
    """Distribute total across categories proportional to ratios using largest-remainder method.

    Guarantees the sum of returned values equals total. Ratios are normalised internally.
    """
    if total == 0:
        return {k: 0 for k in ratios}

    norm, _ = normalise_ratios(ratios)
    raw = {k: v * total for k, v in norm.items()}
    floored = {k: math.floor(v) for k, v in raw.items()}
    remainder = {k: raw[k] - floored[k] for k in raw}

    allocated = sum(floored.values())
    remaining = total - allocated

    # Award remaining slots to categories with largest remainders
    for k in sorted(remainder, key=lambda x: remainder[x], reverse=True):
        if remaining <= 0:
            break
        floored[k] += 1
        remaining -= 1

    return floored


def filter_templates(
    templates: list[tuple[TemplateConfig, Path]],
    *,
    include: list[str],
) -> list[tuple[TemplateConfig, Path]]:
    """Filter templates by matching 'discipline/name' against include glob patterns.

    Each template's metadata discipline and name are combined as 'discipline/name'
    and matched against each include pattern using fnmatch. A template is included
    if it matches any pattern.

    Raises ValueError if no templates survive filtering.
    """
    matched: list[tuple[TemplateConfig, Path]] = []

    for config, path in templates:
        logical_path = f"{config.meta.discipline}/{config.meta.name}"
        if any(fnmatch(logical_path, pattern) for pattern in include):
            matched.append((config, path))

    if not matched:
        msg = f"No templates matched include patterns: {include}"
        raise ValueError(msg)

    return matched


def allocate_budget(
    templates: list[tuple[TemplateConfig, Path]],
    *,
    per_task: int,
    total_max: int,
    min_per_discipline: int,
) -> tuple[dict[str, int], list[CoverageWarning]]:
    """Allocate instance budget across templates using discipline-balanced trim.

    Returns (allocation_dict, warnings_list). Always returns both.

    1. If total demand (len(templates) * per_task) <= total_max, give each per_task.
    2. Otherwise, guarantee min_per_discipline per discipline, then distribute remainder.
    3. If guarantees alone exceed total_max, distribute total_max evenly across disciplines.
    """
    warnings: list[CoverageWarning] = []
    names = [cfg.meta.name for cfg, _ in templates]
    total_demand = len(templates) * per_task

    # No trimming needed
    if total_demand <= total_max:
        allocation = {name: per_task for name in names}
        return allocation, warnings

    # Group templates by discipline
    by_discipline: dict[str, list[str]] = defaultdict(list)
    for cfg, _ in templates:
        by_discipline[cfg.meta.discipline].append(cfg.meta.name)

    # Calculate discipline guarantees
    discipline_guarantees: dict[str, int] = {}
    for disc, disc_templates in by_discipline.items():
        max_possible = len(disc_templates) * per_task
        discipline_guarantees[disc] = min(min_per_discipline, max_possible)

    total_guaranteed = sum(discipline_guarantees.values())

    # Impossible guarantee: total_max < sum of guarantees
    if total_guaranteed > total_max:
        # Distribute total_max evenly across disciplines
        disc_alloc = largest_remainder_round({d: 1.0 for d in by_discipline}, total=total_max)
        allocation: dict[str, int] = {}
        for disc, disc_templates in by_discipline.items():
            disc_budget = disc_alloc[disc]
            per_template = largest_remainder_round({t: 1.0 for t in disc_templates}, total=disc_budget)
            allocation.update(per_template)
            if disc_budget < min_per_discipline:
                warnings.append(
                    CoverageWarning(
                        category="discipline",
                        message=(f"discipline '{disc}' got {disc_budget} instances, target was {min_per_discipline}"),
                        target=min_per_discipline,
                        achieved=disc_budget,
                    )
                )
        return allocation, warnings

    # Distribute guarantees across templates within each discipline (round-robin)
    allocation = {name: 0 for name in names}
    for disc, disc_templates in by_discipline.items():
        guarantee = discipline_guarantees[disc]
        per_template = largest_remainder_round({t: 1.0 for t in disc_templates}, total=guarantee)
        for t, count in per_template.items():
            allocation[t] = count

    # Distribute remaining budget proportionally (capped at per_task per template)
    remaining = total_max - total_guaranteed
    if remaining > 0:
        # Each template's "want" is per_task minus what it already has
        wants = {name: max(0, per_task - allocation[name]) for name in names}
        total_want = sum(wants.values())
        if total_want > 0:
            extra = largest_remainder_round(
                {k: v for k, v in wants.items() if v > 0},
                total=min(remaining, total_want),
            )
            for name, bonus in extra.items():
                allocation[name] += bonus

    return allocation, warnings


class PlannedInstance(StrictModel):
    """A single planned task instance within a composition plan."""

    template_name: str
    template_dir: Path
    difficulty: str
    tool_mode: str
    visibility: str
    seed_offset: int


class DatasetSummary(StrictModel):
    """Aggregate counts for a dataset or composition plan."""

    total_instances: int
    by_discipline: dict[str, int]
    by_difficulty: dict[str, int]
    by_visibility: dict[str, int]
    by_tool_mode: dict[str, int]


class CompositionPlan(StrictModel):
    """The output of compose_dataset: a deterministic plan for generating instances."""

    suite_name: str
    seed: int
    planned_instances: list[PlannedInstance]
    warnings: list[CoverageWarning]
    summary: DatasetSummary


def _assign_difficulties(
    n: int,
    target_ratios: dict[str, float],
    available: list[str],
) -> list[str]:
    """Assign difficulty levels to n slots based on target ratios.

    Only assigns difficulties that are in `available`. Redistributes shares
    of unavailable difficulties proportionally among available ones.
    """
    # Filter to available difficulties only
    filtered = {k: v for k, v in target_ratios.items() if k in available}
    if not filtered:
        # Fallback: distribute evenly across available
        filtered = {k: 1.0 for k in available}

    counts = largest_remainder_round(filtered, total=n)
    # Expand counts into a flat list
    result: list[str] = []
    for diff, count in counts.items():
        result.extend([diff] * count)
    return result


def _assign_tool_modes(
    n: int,
    target_ratios: dict[str, float],
    template_tool_mode: ToolMode,
) -> list[str]:
    """Assign tool modes to n slots based on target ratios and template capability.

    If the template only supports one mode, all slots get that mode.
    If the template supports 'both', distribute per the target ratios.
    """
    if template_tool_mode is ToolMode.WITH_TOOL:
        return ["with-tool"] * n
    if template_tool_mode is ToolMode.NO_TOOL:
        return ["no-tool"] * n

    # BOTH: distribute per ratios
    counts = largest_remainder_round(target_ratios, total=n)
    result: list[str] = []
    for mode, count in counts.items():
        result.extend([mode] * count)
    return result


def _build_summary(
    planned: list[PlannedInstance],
    templates: list[tuple[TemplateConfig, Path]],
) -> DatasetSummary:
    """Compute aggregate summary counts from planned instances."""
    name_to_discipline = {cfg.meta.name: cfg.meta.discipline for cfg, _ in templates}

    by_discipline: dict[str, int] = defaultdict(int)
    by_difficulty: dict[str, int] = defaultdict(int)
    by_visibility: dict[str, int] = defaultdict(int)
    by_tool_mode: dict[str, int] = defaultdict(int)

    for p in planned:
        disc = name_to_discipline.get(p.template_name, "unknown")
        by_discipline[disc] += 1
        by_difficulty[p.difficulty] += 1
        by_visibility[p.visibility] += 1
        by_tool_mode[p.tool_mode] += 1

    return DatasetSummary(
        total_instances=len(planned),
        by_discipline=dict(by_discipline),
        by_difficulty=dict(by_difficulty),
        by_visibility=dict(by_visibility),
        by_tool_mode=dict(by_tool_mode),
    )


def _validate_coverage(
    summary: DatasetSummary,
    config: SuiteConfig,
    templates: list[tuple[TemplateConfig, Path]],
) -> list[CoverageWarning]:
    """Compare achieved ratios against targets and produce warnings for deviations > 0.1."""
    warnings: list[CoverageWarning] = []
    total = summary.total_instances
    if total == 0:
        return warnings

    # Difficulty coverage
    norm_diff, _ = normalise_ratios(config.coverage.difficulties)
    for diff, target in norm_diff.items():
        achieved = summary.by_difficulty.get(diff, 0) / total
        if abs(achieved - target) > 0.1:
            warnings.append(
                CoverageWarning(
                    category="difficulty",
                    message=f"difficulty '{diff}': target {target:.1%}, achieved {achieved:.1%}",
                    target=target,
                    achieved=achieved,
                )
            )

    # Visibility coverage
    norm_vis, _ = normalise_ratios(config.visibility.mix)
    for vis, target in norm_vis.items():
        achieved = summary.by_visibility.get(vis, 0) / total
        if abs(achieved - target) > 0.1:
            warnings.append(
                CoverageWarning(
                    category="visibility",
                    message=f"visibility '{vis}': target {target:.1%}, achieved {achieved:.1%}",
                    target=target,
                    achieved=achieved,
                )
            )

    # Tool mode coverage
    norm_tool, _ = normalise_ratios(config.tool_mode_normalised())
    for mode, target in norm_tool.items():
        achieved = summary.by_tool_mode.get(mode, 0) / total
        if abs(achieved - target) > 0.1:
            warnings.append(
                CoverageWarning(
                    category="tool_mode",
                    message=f"tool_mode '{mode}': target {target:.1%}, achieved {achieved:.1%}",
                    target=target,
                    achieved=achieved,
                )
            )

    # Discipline minimum
    name_to_discipline = {cfg.meta.name: cfg.meta.discipline for cfg, _ in templates}
    disciplines = set(name_to_discipline.values())
    for disc in disciplines:
        count = summary.by_discipline.get(disc, 0)
        if count < config.coverage.min_tasks_per_discipline:
            warnings.append(
                CoverageWarning(
                    category="discipline",
                    message=(
                        f"discipline '{disc}': {count} instances, min target {config.coverage.min_tasks_per_discipline}"
                    ),
                    target=config.coverage.min_tasks_per_discipline,
                    achieved=count,
                )
            )

    return warnings


def compose_dataset(
    config: SuiteConfig,
    templates: list[tuple[TemplateConfig, Path]],
) -> CompositionPlan:
    """Build a deterministic composition plan from a suite config and template list.

    Pure function: no I/O, no side effects. Returns a plan that can be inspected
    (dry-run) or executed (scaffold all instances).
    """
    # Step 1: Filter
    filtered = filter_templates(templates, include=config.templates.include)

    # Step 2: Allocate budget
    allocation, budget_warnings = allocate_budget(
        filtered,
        per_task=config.instances.per_task,
        total_max=config.instances.total_max,
        min_per_discipline=config.coverage.min_tasks_per_discipline,
    )

    # Step 3: Assign instances
    norm_tool = config.tool_mode_normalised()
    available_difficulties, _ = normalise_ratios(config.coverage.difficulties)

    planned: list[PlannedInstance] = []
    cumulative_index = 0
    template_lookup = {cfg.meta.name: (cfg, path) for cfg, path in filtered}

    for template_name, instance_count in allocation.items():
        cfg, path = template_lookup[template_name]
        template_difficulties = list(cfg.difficulty.keys())

        # Assign difficulties for this template's instances
        difficulties = _assign_difficulties(instance_count, available_difficulties, template_difficulties)

        # Assign tool modes for this template's instances
        tool_modes = _assign_tool_modes(instance_count, norm_tool, cfg.meta.tool_mode)

        for i in range(instance_count):
            diff_name = difficulties[i] if i < len(difficulties) else template_difficulties[0]
            tm = tool_modes[i] if i < len(tool_modes) else cfg.meta.tool_mode.value

            # Visibility comes from the difficulty preset
            preset = cfg.difficulty[diff_name]
            vis = preset.visibility.value

            planned.append(
                PlannedInstance(
                    template_name=template_name,
                    template_dir=path,
                    difficulty=diff_name,
                    tool_mode=tm,
                    visibility=vis,
                    seed_offset=config.seed + cumulative_index,
                )
            )
            cumulative_index += 1

    # Step 4: Coverage validation
    summary = _build_summary(planned, filtered)
    coverage_warnings = _validate_coverage(summary, config, filtered)

    all_warnings = list(budget_warnings) + coverage_warnings

    return CompositionPlan(
        suite_name=config.name,
        seed=config.seed,
        planned_instances=planned,
        warnings=all_warnings,
        summary=summary,
    )


class InstanceEntry(StrictModel):
    """One instance's metadata in the dataset manifest."""

    path: str
    template: str
    difficulty: str
    archetype: str
    site_context: str
    visibility: str
    tool_mode: str


class DatasetManifest(StrictModel):
    """The dataset.json file written alongside generated instances."""

    name: str
    seed: int
    created: datetime
    framework_version: str
    config: str
    summary: DatasetSummary
    instances: list[InstanceEntry]


def load_suite_config(config_path: Path) -> SuiteConfig:
    """Load a suite.toml file and return a validated SuiteConfig."""
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)
    return SuiteConfig.model_validate(raw)


def execute_plan(
    plan: CompositionPlan,
    config: SuiteConfig,
    *,
    config_path: str = "suite.toml",
) -> DatasetManifest:
    """Execute a composition plan by scaffolding all instances and writing dataset.json.

    Caches template loads per template_dir to avoid redundant I/O.
    Returns the DatasetManifest that was written to disk.
    """
    from aec_bench import __version__
    from aec_bench.generation.sampler import sample_instance
    from aec_bench.generation.scaffolder import scaffold_task_instance
    from aec_bench.templates.registry import load_engine_module, load_template

    output_dir = config.output.dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Cache: template_dir -> (TemplateConfig, engine_module, engine_source)
    cache: dict[Path, tuple[TemplateConfig, object, str]] = {}

    entries: list[InstanceEntry] = []

    for instance_index, planned in enumerate(plan.planned_instances):
        tdir = planned.template_dir

        # Load and cache template resources
        if tdir not in cache:
            template_config, _ = load_template(tdir)
            engine_module = load_engine_module(tdir)
            engine_source = (tdir / "engine.py").read_text(encoding="utf-8")
            cache[tdir] = (template_config, engine_module, engine_source)

        template_config, engine_module, engine_source = cache[tdir]

        # Sample instance
        sampled = sample_instance(
            config=template_config,
            engine_compute=engine_module.compute,
            difficulty_name=planned.difficulty,
            seed=planned.seed_offset,
            instance_index=instance_index,
        )

        # Scaffold to disk
        instance_dir = scaffold_task_instance(
            config=template_config,
            engine_source=engine_source,
            template_dir=tdir,
            instance=sampled,
            output_dir=output_dir,
            tool_mode_override=planned.tool_mode,
        )

        # Build manifest entry with relative path
        rel_path = instance_dir.relative_to(output_dir)
        entries.append(
            InstanceEntry(
                path=str(rel_path),
                template=planned.template_name,
                difficulty=planned.difficulty,
                archetype=sampled.archetype_name,
                site_context=sampled.site_context,
                visibility=planned.visibility,
                tool_mode=planned.tool_mode,
            )
        )

    # Build manifest
    manifest = DatasetManifest(
        name=plan.suite_name,
        seed=plan.seed,
        created=datetime.now(tz=UTC),
        framework_version=__version__,
        config=config_path,
        summary=plan.summary,
        instances=entries,
    )

    # Write dataset.json
    manifest_path = output_dir / "dataset.json"
    manifest_path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2, default=str) + "\n")

    # Write Harbor-compatible job.yaml with one dataset path per instance
    _write_harbor_job_config(output_dir, entries)

    return manifest


def _write_harbor_job_config(
    output_dir: Path,
    entries: list[InstanceEntry],
) -> None:
    """Write a Harbor job.yaml alongside dataset.json.

    Includes provider documentation and references the Harbor BaseAgent contract
    so users know how to plug in their own agents.
    """
    parent_dirs: dict[str, list[str]] = {}
    for entry in entries:
        parts = Path(entry.path).parts
        parent = str(Path(*parts[:-1])) if len(parts) > 1 else "."
        if parent not in parent_dirs:
            parent_dirs[parent] = []
        parent_dirs[parent].append(parts[-1])

    dataset_lines: list[str] = []
    for parent_path in sorted(parent_dirs):
        full_path = output_dir / parent_path
        dataset_lines.append(f"  - path: {full_path}")

    job_yaml = (
        "# Auto-generated Harbor job config for this dataset.\n"
        "#\n"
        "# To use your own agent:\n"
        "#   1. Subclass Harbor's BaseAgent, compose aec_bench utility functions\n"
        "#   2. See agents/ directory for ready-to-use default agents\n"
        "#   3. Set import_path below to your module:class\n"
        "#\n"
        "# Provider options (set in agent kwargs or env):\n"
        "#   anthropic     — direct Anthropic API (ANTHROPIC_API_KEY)\n"
        "#   bedrock       — AWS Bedrock (AWS_BEDROCK_ENDPOINT, AWS_BEARER_TOKEN)\n"
        "#   azure_openai  — Azure OpenAI (AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY)\n"
        "#   openai        — OpenAI API (OPENAI_API_KEY)\n"
        "\n"
        "jobs_dir: jobs\n"
        "n_attempts: 1\n"
        "timeout_multiplier: 1.0\n"
        "\n"
        "orchestrator:\n"
        "  type: local\n"
        "  n_concurrent_trials: 1\n"
        "  quiet: false\n"
        "\n"
        "environment:\n"
        "  type: modal\n"
        "  force_build: false\n"
        "  delete: true\n"
        "  kwargs:\n"
        "    secrets:\n"
        "      - azure-openai-key\n"
        "\n"
        "agents:\n"
        "  - name: my-agent\n"
        "    import_path: agents.tool_loop_anthropic:ToolLoopAnthropicAgent\n"
        "    model_name: claude-sonnet-4-20250514\n"
        "\n"
        "datasets:\n" + "\n".join(dataset_lines) + "\n"
    )

    job_path = output_dir / "job.yaml"
    job_path.write_text(job_yaml)
