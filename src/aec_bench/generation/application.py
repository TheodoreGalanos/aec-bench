# ABOUTME: Loads generated runnable task packages through the ordinary task validation boundary.
# ABOUTME: Converts replay sidecars into in-process GeneratedTaskSet values without making them mandatory.

from __future__ import annotations

from pathlib import Path

from aec_bench.contracts.task_definition import TaskDefinition, Visibility
from aec_bench.generation.contracts import GeneratedTaskSet
from aec_bench.generation.replay import (
    GenerationInstance,
    GenerationManifest,
    prepare_template_source,
    require_available_sidecar_paths,
    write_generation_config,
    write_generation_manifest,
)
from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.tasks.loader import load_task_definition
from aec_bench.templates.contracts import ToolMode
from aec_bench.templates.registry import LoadedTemplate, discover_templates, load_template


def resolve_template(name_or_path: str) -> LoadedTemplate:
    """Resolve one template path or built-in name through the template registry."""

    candidate = Path(name_or_path)
    if candidate.is_dir():
        return load_template(candidate.resolve())
    templates, _diagnostics = discover_templates()
    for template in templates:
        if template.config.meta.name == name_or_path:
            return template
    raise FileNotFoundError(f"template not found: {name_or_path}")


def generate_template_instances(
    *,
    template: LoadedTemplate,
    output_root: Path,
    count: int,
    difficulties: tuple[str, ...],
    seed: int,
    start_index: int = 0,
    tool_mode: str | None = None,
    task_visibility: Visibility = Visibility.PUBLIC,
    suite_id: str | None = None,
) -> GeneratedTaskSet:
    """Generate one template's runnable instances and optional replay data."""

    root = output_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    require_available_sidecar_paths(root)
    prepared_source = prepare_template_source((template,), root)
    template_id = prepared_source.template_ids[template.path.resolve()]
    effective_tool_mode = (
        ToolMode(tool_mode)
        if tool_mode is not None
        else ToolMode.WITH_TOOL
        if template.config.meta.tool_mode is ToolMode.BOTH
        else template.config.meta.tool_mode
    )
    task_paths: list[Path] = []
    entries: list[GenerationInstance] = []
    for offset in range(count):
        difficulty = difficulties[offset % len(difficulties)]
        instance_index = start_index + offset
        sampled = sample_instance(
            template=template,
            difficulty_name=difficulty,
            seed=seed,
            instance_index=instance_index,
        )
        task_path = scaffold_task_instance(
            template=template,
            instance=sampled,
            output_dir=root,
            tool_mode_override=tool_mode,
            task_visibility=task_visibility,
        )
        task_paths.append(task_path)
        entries.append(
            GenerationInstance(
                task_id=task_path.relative_to(root).as_posix(),
                template_id=template_id,
                seed=seed,
                instance_index=instance_index,
                difficulty=difficulty,
                tool_mode=effective_tool_mode,
                task_visibility=task_visibility,
            )
        )
    resolved_suite_id = suite_id or f"{template.config.meta.name}-standalone"
    config_ref = write_generation_config(
        root,
        {
            "mode": "task",
            "suite_id": resolved_suite_id,
            "template_id": template_id,
            "seed": seed,
            "start_index": start_index,
            "instances": count,
            "difficulties": difficulties,
            "tool_mode": effective_tool_mode.value,
            "task_visibility": task_visibility.value,
        },
    )
    manifest = GenerationManifest(
        suite_id=resolved_suite_id,
        source=prepared_source.source,
        config_ref=config_ref,
        instances=tuple(entries),
    )
    write_generation_manifest(root, manifest)
    return GeneratedTaskSet(output_root=root, task_paths=tuple(task_paths), manifest=manifest)


def read_generated_task_set(manifest_path: Path) -> GeneratedTaskSet:
    """Read optional replay data and identify its generated task packages."""

    path = manifest_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"generation manifest not found: {path}")
    manifest = GenerationManifest.model_validate_json(path.read_bytes())
    output_root = path.parent
    task_paths = tuple((output_root / instance.task_id).resolve() for instance in manifest.instances)
    return GeneratedTaskSet(output_root=output_root, task_paths=task_paths, manifest=manifest)


def load_generated_tasks(
    generated: GeneratedTaskSet,
    *,
    tasks_root: Path | None = None,
) -> list[TaskDefinition]:
    """Load and validate every task package named by a generated task set."""

    root = (tasks_root or generated.output_root).resolve()
    tasks: list[TaskDefinition] = []
    for task_path in generated.task_paths:
        path = task_path.resolve()
        if not path.is_dir():
            raise FileNotFoundError(f"generated task directory is missing: {path}")
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError(f"generated task is outside tasks root: {path}") from error
        tasks.append(load_task_definition(path, root))
    return tasks


__all__ = (
    "generate_template_instances",
    "load_generated_tasks",
    "read_generated_task_set",
    "resolve_template",
)
