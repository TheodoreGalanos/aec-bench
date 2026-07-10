# ABOUTME: Tests for scaffolder template hooks — source packs, custom fixtures, system prompts.
# ABOUTME: Uses a synthetic template directory to verify hook behavior and no-hook regression safety.

import json
from pathlib import Path

from aec_bench.generation.sampler import sample_instance
from aec_bench.generation.scaffolder import scaffold_task_instance
from aec_bench.templates.registry import load_engine_module, load_template

_PARAMS_TOML = """\
[meta]
name = "hook-probe"
description = "Synthetic template for scaffolder hook tests"
discipline = "civil"
category = "testing"
tool_mode = "no-tool"

[params.flow_m3_s]
type = "float"
description = "Design flow"
min = 1.0
max = 2.0

[params.case_variant]
type = "enum"
description = "Scenario variant"
values = ["clean", "defect"]

[outputs.head_m]
description = "Computed head"

[archetypes.basic]
description = "Basic archetype"
site_contexts = ["test-site"]

[difficulty.easy]
description = "Easy preset"
visibility = "partial"
archetypes = ["basic"]
hidden_params = ["case_variant"]
"""

_ENGINE_WITH_HOOKS = """\
# ABOUTME: Synthetic hook-probe engine for scaffolder tests.
# ABOUTME: Provides compute plus source, golden, and instance hooks.


def compute(*, flow_m3_s: float, case_variant: str) -> dict[str, float]:
    head = flow_m3_s * 2.0
    return {"head_m": head, "variant_code": 1.0 if case_variant == "defect" else 0.0}


def build_sources(all_params: dict) -> dict[str, str]:
    return {
        "sources/register.md": f"flow = {all_params['flow_m3_s']}",
        "sources/case.md": f"variant marker: {all_params['case_variant']}",
    }


def build_golden_pass(all_params: dict, ground_truth: dict) -> str:
    return "custom golden pass " + str(ground_truth["head_m"])


def build_golden_fail(all_params: dict, ground_truth: dict) -> str:
    return "custom golden fail"
"""

_ENGINE_PLAIN = """\
# ABOUTME: Synthetic plain engine for scaffolder regression tests.
# ABOUTME: Provides compute only, no hooks.


def compute(*, flow_m3_s: float, case_variant: str) -> dict[str, float]:
    return {"head_m": flow_m3_s * 2.0}
"""

_INSTRUCTION = """\
Review the packet in /workspace/sources/ and write to /workspace/output.md.
"""

_CUSTOM_VERIFY = """\
print("custom verifier placeholder")
"""

_SYSTEM_PROMPT = """\
## Review Workflow

Inventory sources before concluding.
"""


def _write_template(tmp_path: Path, *, hooks: bool, custom_verifier: bool, system_prompt: bool) -> Path:
    tdir = tmp_path / "hook_probe"
    tdir.mkdir()
    (tdir / "params.toml").write_text(_PARAMS_TOML)
    (tdir / "engine.py").write_text(_ENGINE_WITH_HOOKS if hooks else _ENGINE_PLAIN)
    (tdir / "instruction.md").write_text(_INSTRUCTION)
    if custom_verifier:
        (tdir / "verify.py").write_text(_CUSTOM_VERIFY)
    if system_prompt:
        (tdir / "system_prompt.md").write_text(_SYSTEM_PROMPT)
    return tdir


def _scaffold(tmp_path: Path, tdir: Path) -> Path:
    config, template_dir = load_template(tdir)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, "easy", seed=7, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text()
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path / "out")


def test_build_sources_hook_writes_files_and_dockerfile_copies(tmp_path: Path) -> None:
    tdir = _write_template(tmp_path, hooks=True, custom_verifier=True, system_prompt=True)
    instance_dir = _scaffold(tmp_path, tdir)

    register = instance_dir / "environment" / "sources" / "register.md"
    case = instance_dir / "environment" / "sources" / "case.md"
    assert register.exists()
    assert case.exists()
    assert "flow = " in register.read_text()

    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text()
    assert "COPY sources/register.md /workspace/sources/register.md" in dockerfile
    assert "COPY sources/case.md /workspace/sources/case.md" in dockerfile


def test_custom_verifier_gets_instance_json(tmp_path: Path) -> None:
    tdir = _write_template(tmp_path, hooks=True, custom_verifier=True, system_prompt=True)
    instance_dir = _scaffold(tmp_path, tdir)

    instance_json = instance_dir / "tests" / "instance.json"
    assert instance_json.exists()
    payload = json.loads(instance_json.read_text())
    assert payload["all_params"]["case_variant"] in {"clean", "defect"}
    assert "head_m" in payload["ground_truth"]
    assert payload["seed"] == 7


def test_golden_hooks_override_fixture_content(tmp_path: Path) -> None:
    tdir = _write_template(tmp_path, hooks=True, custom_verifier=True, system_prompt=True)
    instance_dir = _scaffold(tmp_path, tdir)

    golden_pass = (instance_dir / "tests" / "fixtures" / "golden_pass.md").read_text()
    golden_fail = (instance_dir / "tests" / "fixtures" / "golden_fail.md").read_text()
    assert golden_pass.startswith("custom golden pass ")
    assert golden_fail == "custom golden fail"


def test_template_system_prompt_overrides_default(tmp_path: Path) -> None:
    tdir = _write_template(tmp_path, hooks=True, custom_verifier=True, system_prompt=True)
    instance_dir = _scaffold(tmp_path, tdir)

    system_prompt = (instance_dir / "environment" / "system_prompt.md").read_text()
    assert "Inventory sources before concluding." in system_prompt


def test_plain_template_without_hooks_is_unchanged(tmp_path: Path) -> None:
    tdir = _write_template(tmp_path, hooks=False, custom_verifier=False, system_prompt=False)
    instance_dir = _scaffold(tmp_path, tdir)

    assert not (instance_dir / "environment" / "sources").exists()
    assert not (instance_dir / "tests" / "instance.json").exists()

    golden_pass = (instance_dir / "tests" / "fixtures" / "golden_pass.md").read_text()
    assert "```json" in golden_pass

    system_prompt = (instance_dir / "environment" / "system_prompt.md").read_text()
    assert "## Workflow" in system_prompt

    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text()
    assert "COPY sources/" not in dockerfile
