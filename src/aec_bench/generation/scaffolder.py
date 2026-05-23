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
from aec_bench.templates.registry import has_custom_verifier


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

    toml_str = f"""\
version = "1.0"

	[metadata]
	domain = "{config.meta.discipline}"
	category = "{config.meta.category}"
	difficulty = "{instance.difficulty}"
	tags = [{tags_toml}]

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
) -> str:
    """Build Dockerfile content using the extension system.

    Generated tasks use core extensions (no extras). COPY lines are added
    for system_prompt.md and the calc script (when tool_mode is WITH_TOOL).
    """
    copy_files = ["system_prompt.md"]

    if tool_mode is ToolMode.WITH_TOOL:
        calc_name = f"{config.meta.name}_calc.py"
        copy_files.append(calc_name)

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

    # 3. Write environment/Dockerfile
    (instance_dir / "environment" / "Dockerfile").write_text(_build_dockerfile(config, tool_mode))

    # 4. Write environment/system_prompt.md
    (instance_dir / "environment" / "system_prompt.md").write_text(_build_system_prompt())

    # 5. If with-tool: generate and write the calc script
    if tool_mode is ToolMode.WITH_TOOL:
        calc_filename = f"{template_name}_calc.py"
        calc_source = generate_cli_wrapper(config, engine_source)
        (instance_dir / "environment" / calc_filename).write_text(calc_source)

    # 6. Write tests/verify.py — copy custom if present, otherwise generate
    if has_custom_verifier(template_dir):
        shutil.copy(template_dir / "verify.py", instance_dir / "tests" / "verify.py")
    else:
        verifier_source = generate_verifier(instance, config)
        (instance_dir / "tests" / "verify.py").write_text(verifier_source)

    # 7. Write tests/test.sh
    test_sh_path = instance_dir / "tests" / "test.sh"
    test_sh_path.write_text(_build_test_sh())
    test_sh_path.chmod(0o755)

    # 8. Write fixture files
    (instance_dir / "tests" / "fixtures" / "golden_pass.md").write_text(_build_golden_pass(instance.ground_truth))
    (instance_dir / "tests" / "fixtures" / "golden_fail.md").write_text(_build_golden_fail(instance.ground_truth))

    return instance_dir
