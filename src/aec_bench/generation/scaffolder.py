# ABOUTME: Orchestrates all generators to produce a complete task instance directory on disk.
# ABOUTME: Writes task.toml, instruction.md, Dockerfile, system_prompt.md, verifier, and fixtures.

import importlib.resources
import json
import shutil
from pathlib import Path

from aec_bench.generation.cli_wrapper_gen import generate_cli_wrapper
from aec_bench.generation.contracts import SampledInstance
from aec_bench.generation.instruction_renderer import render_instruction
from aec_bench.generation.verifier_gen import generate_verifier
from aec_bench.images.extensions import generate_dockerfile
from aec_bench.templates.contracts import TemplateConfig, ToolMode
from aec_bench.templates.registry import has_custom_verifier, load_engine_module

RUNNABLE_DIFFICULTIES = {"easy", "medium", "hard"}

RUNNABLE_DIFFICULTIES = {"easy", "medium", "hard"}


def _resolve_tool_mode(
    config: TemplateConfig,
    tool_mode_override: str | None,
) -> ToolMode:
    """Determine the effective ToolMode for this scaffold run.

    If an override string is provided it takes precedence. When config.meta.tool_mode
    is BOTH and no override is given, default to WITH_TOOL.
    """
    if tool_mode_override is not None:
        return ToolMode(tool_mode_override)
    if config.meta.tool_mode is ToolMode.BOTH:
        return ToolMode.WITH_TOOL
    return config.meta.tool_mode


def _runnable_metadata_difficulty(generation_difficulty: str) -> str:
    """Return the public task difficulty enum for generated task metadata."""
    if generation_difficulty in RUNNABLE_DIFFICULTIES:
        return generation_difficulty
    return "medium"


def _generation_difficulty_metadata_line(generation_difficulty: str) -> str:
    """Preserve custom generation presets when metadata difficulty is normalized."""
    if generation_difficulty in RUNNABLE_DIFFICULTIES:
        return ""
    return f'\tgeneration_difficulty = "{generation_difficulty}"\n'


def _build_task_toml(
    config: TemplateConfig,
    instance: SampledInstance,
    tool_mode: ToolMode,
) -> str:
    """Produce task.toml content as a string using f-strings (tomllib is read-only).

    Includes a [generation] section with full provenance metadata from the instance.
    When tool_mode is WITH_TOOL, includes a [tools] section listing the calc script.
    """
    # Build tags list — include config tags plus tool-mode tag
    tags = list(config.meta.tags) + [tool_mode.value]
    tags_toml = ", ".join(f'"{t}"' for t in tags)

    meta = instance.metadata
    timestamp_iso = meta.timestamp.isoformat()
    metadata_difficulty = _runnable_metadata_difficulty(instance.difficulty)
    generation_difficulty_line = _generation_difficulty_metadata_line(instance.difficulty)

    toml_str = f"""\
version = "1.0"

	[metadata]
	domain = "{config.meta.discipline}"
	category = "{config.meta.category}"
	difficulty = "{metadata_difficulty}"
{generation_difficulty_line}	tags = [{tags_toml}]

[agent]
timeout_sec = 600.0

[verifier]
timeout_sec = 120.0

[environment]
extensions = []
build_timeout_sec = 600.0
cpus = 1
memory_mb = 2048
storage_mb = 5120
allow_internet = true

[generation]
origin = "generated"
template = "{meta.template}"
template_version = "1.0"
seed = {meta.seed}
timestamp = "{timestamp_iso}"
difficulty = "{meta.difficulty}"
visibility_level = "{meta.visibility_level}"
archetype = "{meta.archetype}"
site_context = "{meta.site_context}"
"""

    # Add [tools] section when tool_mode is WITH_TOOL
    if tool_mode is ToolMode.WITH_TOOL:
        calc_name = f"{config.meta.name}_calc.py"
        toml_str += f"""
[tools]
scripts = ["{calc_name}"]
"""

    return toml_str


def _build_dockerfile(
    config: TemplateConfig,
    tool_mode: ToolMode,
    extra_copy_files: list[str] | None = None,
) -> str:
    """Build Dockerfile content using the extension system.

    Generated tasks use core extensions (no extras). COPY lines are added
    for system_prompt.md, the calc script (when tool_mode is WITH_TOOL),
    and any template-provided source-pack files.
    """
    copy_files = ["system_prompt.md"]

    if tool_mode is ToolMode.WITH_TOOL:
        calc_name = f"{config.meta.name}_calc.py"
        copy_files.append(calc_name)

    if extra_copy_files:
        copy_files.extend(extra_copy_files)

    return generate_dockerfile(
        extensions=[],
        task_description=f"{config.meta.discipline} — {config.meta.name}",
        copy_files=copy_files,
    )


def _build_system_prompt() -> str:
    """Build the system_prompt.md content for the container workspace."""
    return """\
## Workflow

1. **Orient** (1 turn): Read the problem, identify what is being asked.
2. **Compute** (1-2 turns): Use the provided tool or your knowledge to calculate.
3. **Consolidate** (1 turn): Write your solution with working to /workspace/output.md.

## Budget

Target: 3-4 turns total.

## Output Discipline

- MUST include a fenced JSON block with your final numeric answers
- Write complete solution to `/workspace/output.md`
"""


def _build_test_sh() -> str:
    """Build the test.sh bash verifier entry point."""
    trap_line = (
        "trap 'if [ ! -f /logs/verifier/reward.json ];"
        ' then echo "{\\"reward\\": 0.0}" > /logs/verifier/reward.json; fi\' EXIT'
    )
    return "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -euo pipefail",
            "mkdir -p /logs/verifier",
            trap_line,
            "python3 /workspace/tests/verify.py",
            "",
        ]
    )


def _build_golden_pass(ground_truth: dict[str, float]) -> str:
    """Build golden_pass.md with the correct ground truth values as a fenced JSON block."""
    json_block = json.dumps(ground_truth, indent=2)
    return f"""\
## Solution

```json
{json_block}
```
"""


def _build_golden_fail(ground_truth: dict[str, float]) -> str:
    """Build golden_fail.md with all-zero values for each ground truth key."""
    zeroed = {key: 0.0 for key in ground_truth}
    json_block = json.dumps(zeroed, indent=2)
    return f"""\
## Solution

```json
{json_block}
```
"""


def _write_source_pack(
    engine_module,
    instance: SampledInstance,
    environment_dir: Path,
) -> list[str]:
    """Write template-provided source-pack files into the environment directory.

    Templates may define ``build_sources(all_params) -> dict[relpath, content]``
    on their engine module. Each file is written under ``environment/`` and its
    relative path is returned so the Dockerfile can COPY it into /workspace.
    """
    if not hasattr(engine_module, "build_sources"):
        return []

    sources: dict[str, str] = engine_module.build_sources(dict(instance.all_params))
    written: list[str] = []
    for relpath, content in sources.items():
        target = environment_dir / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        written.append(relpath)
    return written


def _write_instance_record(instance: SampledInstance, tests_dir: Path) -> None:
    """Write tests/instance.json so a custom verifier can read instance gold state."""
    record = {
        "instance_name": instance.instance_name,
        "seed": instance.metadata.seed,
        "difficulty": instance.difficulty,
        "all_params": instance.all_params,
        "ground_truth": instance.ground_truth,
    }
    (tests_dir / "instance.json").write_text(json.dumps(record, indent=2))


def scaffold_task_instance(
    config: TemplateConfig,
    engine_source: str,
    template_dir: Path,
    instance: SampledInstance,
    output_dir: Path,
    tool_mode_override: str | None = None,
) -> Path:
    """Scaffold a complete task instance directory from a TemplateConfig and SampledInstance.

    Orchestrates all generators (CLI wrapper, verifier, instruction renderer) and writes
    every file the Harbor harness expects: task.toml, instruction.md, Dockerfile,
    system_prompt.md, verify.py, test.sh, and fixture files.

    Returns the path to the created instance directory.
    """
    tool_mode = _resolve_tool_mode(config, tool_mode_override)
    engine_module = load_engine_module(template_dir)

    # Build the instance directory path: output_dir/discipline/category/template_name/instance_name
    template_name = config.meta.name
    instance_dir = output_dir / config.meta.discipline / config.meta.category / template_name / instance.instance_name

    # Create required subdirectories
    (instance_dir / "environment").mkdir(parents=True, exist_ok=True)
    (instance_dir / "tests" / "fixtures").mkdir(parents=True, exist_ok=True)

    # Copy trajectory_writer.py into the environment directory so the Dockerfile can COPY it
    writer_source = importlib.resources.files("aec_bench.trajectory") / "writer.py"
    (instance_dir / "environment" / "trajectory_writer.py").write_text(writer_source.read_text(encoding="utf-8"))

    # 1. Write task.toml
    (instance_dir / "task.toml").write_text(_build_task_toml(config, instance, tool_mode))

    # 2. Render and write instruction.md
    instruction_template = (template_dir / "instruction.md").read_text()
    rendered_instruction = render_instruction(instruction_template, instance, config)
    (instance_dir / "instruction.md").write_text(rendered_instruction)

    # 3. Write template-provided source-pack files, then environment/Dockerfile
    source_files = _write_source_pack(engine_module, instance, instance_dir / "environment")
    (instance_dir / "environment" / "Dockerfile").write_text(_build_dockerfile(config, tool_mode, source_files))

    # 4. Write environment/system_prompt.md — template-owned prompt wins over the default
    template_system_prompt = template_dir / "system_prompt.md"
    if template_system_prompt.exists():
        (instance_dir / "environment" / "system_prompt.md").write_text(template_system_prompt.read_text())
    else:
        (instance_dir / "environment" / "system_prompt.md").write_text(_build_system_prompt())

    # 5. If with-tool: generate and write the calc script
    if tool_mode is ToolMode.WITH_TOOL:
        calc_filename = f"{template_name}_calc.py"
        calc_source = generate_cli_wrapper(config, engine_source)
        (instance_dir / "environment" / calc_filename).write_text(calc_source)

    # 6. Write tests/verify.py — copy custom if present, otherwise generate.
    #    Custom verifiers also get tests/instance.json with the instance gold state.
    if has_custom_verifier(template_dir):
        shutil.copy(template_dir / "verify.py", instance_dir / "tests" / "verify.py")
        _write_instance_record(instance, instance_dir / "tests")
    else:
        verifier_source = generate_verifier(instance, config)
        (instance_dir / "tests" / "verify.py").write_text(verifier_source)

    # 7. Write tests/test.sh
    test_sh_path = instance_dir / "tests" / "test.sh"
    test_sh_path.write_text(_build_test_sh())
    test_sh_path.chmod(0o755)

    # 8. Write fixture files — template golden hooks win over the generated defaults
    if hasattr(engine_module, "build_golden_pass"):
        golden_pass = engine_module.build_golden_pass(dict(instance.all_params), dict(instance.ground_truth))
    else:
        golden_pass = _build_golden_pass(instance.ground_truth)
    if hasattr(engine_module, "build_golden_fail"):
        golden_fail = engine_module.build_golden_fail(dict(instance.all_params), dict(instance.ground_truth))
    else:
        golden_fail = _build_golden_fail(instance.ground_truth)
    (instance_dir / "tests" / "fixtures" / "golden_pass.md").write_text(golden_pass)
    (instance_dir / "tests" / "fixtures" / "golden_fail.md").write_text(golden_fail)

    return instance_dir
