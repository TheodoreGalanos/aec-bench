# ABOUTME: Tests for the scaffolder — scaffold_task_instance() function.
# ABOUTME: Covers directory structure, file contents, tool mode handling, and verifier logic.

import json
import tomllib
from pathlib import Path

import pytest

from aec_bench.generation.sampler import sample_instance
from aec_bench.templates.registry import load_engine_module, load_template

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "ground"
    / "terzaghi_bearing_capacity"
)


def _generate_test_instance(tmp_path: Path) -> Path:
    """Load the Terzaghi template, sample an instance, and scaffold it."""
    config, tdir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(tdir)
    inst = sample_instance(config, engine.compute, "easy", seed=42, instance_index=0)
    engine_source = (tdir / "engine.py").read_text()
    from aec_bench.generation.scaffolder import scaffold_task_instance

    return scaffold_task_instance(config, engine_source, tdir, inst, tmp_path)


# ---------------------------------------------------------------------------
# Test 1: directory structure
# ---------------------------------------------------------------------------


def test_scaffold_creates_directory_structure(tmp_path: Path) -> None:
    """scaffold_task_instance must create all required files and subdirectories."""
    instance_dir = _generate_test_instance(tmp_path)

    assert instance_dir.is_dir(), "Instance directory must exist"

    expected_files = [
        "task.toml",
        "instruction.md",
        "environment/Dockerfile",
        "environment/system_prompt.md",
        "tests/test.sh",
        "tests/fixtures/golden_pass.md",
        "tests/fixtures/golden_fail.md",
        "tests/verify.py",
    ]
    for rel in expected_files:
        assert (instance_dir / rel).exists(), f"Expected file missing: {rel}"


# ---------------------------------------------------------------------------
# Test 2: task.toml generation metadata
# ---------------------------------------------------------------------------


def test_scaffold_task_toml_has_generation_metadata(tmp_path: Path) -> None:
    """task.toml must contain a [generation] section with correct provenance fields."""
    instance_dir = _generate_test_instance(tmp_path)
    toml_path = instance_dir / "task.toml"

    with open(toml_path, "rb") as fh:
        data = tomllib.load(fh)

    assert "generation" in data, "[generation] section missing from task.toml"
    gen = data["generation"]
    assert gen["origin"] == "generated"
    assert "template" in gen
    assert "seed" in gen
    assert "timestamp" in gen
    assert "difficulty" in gen
    assert "visibility_level" in gen
    assert "archetype" in gen
    assert "site_context" in gen


def test_scaffold_task_toml_has_required_sections(tmp_path: Path) -> None:
    """task.toml must contain version, [metadata], [agent], [verifier], [environment] sections."""
    instance_dir = _generate_test_instance(tmp_path)

    with open(instance_dir / "task.toml", "rb") as fh:
        data = tomllib.load(fh)

    assert "version" in data
    assert "metadata" in data
    assert "agent" in data
    assert "verifier" in data
    assert "environment" in data


# ---------------------------------------------------------------------------
# Test 3: instruction rendering
# ---------------------------------------------------------------------------


def test_scaffold_instruction_is_rendered(tmp_path: Path) -> None:
    """instruction.md must have no unrendered Jinja2 placeholders."""
    instance_dir = _generate_test_instance(tmp_path)
    content = (instance_dir / "instruction.md").read_text()

    assert "{{" not in content, "Unrendered {{ }} Jinja2 placeholder found in instruction.md"
    assert "{%" not in content, "Unrendered {% %} Jinja2 block tag found in instruction.md"


# ---------------------------------------------------------------------------
# Test 4: verifier is valid Python
# ---------------------------------------------------------------------------


def test_scaffold_verifier_is_valid_python(tmp_path: Path) -> None:
    """tests/verify.py must be syntactically valid Python."""
    instance_dir = _generate_test_instance(tmp_path)
    code = (instance_dir / "tests" / "verify.py").read_text()

    compiled = compile(code, "<generated_verify>", "exec")
    assert compiled is not None


# ---------------------------------------------------------------------------
# Test 5: golden pass file has correct values
# ---------------------------------------------------------------------------


def test_scaffold_golden_pass_has_correct_values(tmp_path: Path) -> None:
    """tests/fixtures/golden_pass.md must contain a JSON block with ground truth values."""
    config, tdir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(tdir)
    inst = sample_instance(config, engine.compute, "easy", seed=42, instance_index=0)
    engine_source = (tdir / "engine.py").read_text()

    from aec_bench.generation.scaffolder import scaffold_task_instance

    instance_dir = scaffold_task_instance(config, engine_source, tdir, inst, tmp_path)

    golden_pass = (instance_dir / "tests" / "fixtures" / "golden_pass.md").read_text()

    # Must contain a fenced JSON block
    assert "```json" in golden_pass, "golden_pass.md must contain a fenced JSON block"

    # Extract the JSON block and verify it contains ground truth values
    import re

    matches = re.findall(r"```json\s*\n(.*?)\n\s*```", golden_pass, re.DOTALL)
    assert matches, "Could not extract JSON block from golden_pass.md"

    parsed = json.loads(matches[-1])
    for key, expected_val in inst.ground_truth.items():
        assert key in parsed, f"Ground truth key '{key}' missing from golden_pass.md JSON"
        assert parsed[key] == pytest.approx(expected_val, rel=1e-6)


# ---------------------------------------------------------------------------
# Test 6: no-tool mode omits calc script
# ---------------------------------------------------------------------------


def test_scaffold_no_tool_mode_omits_calc_script(tmp_path: Path) -> None:
    """With tool_mode_override='no-tool', no *_calc.py should be present in environment/."""
    config, tdir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(tdir)
    inst = sample_instance(config, engine.compute, "easy", seed=42, instance_index=0)
    engine_source = (tdir / "engine.py").read_text()

    from aec_bench.generation.scaffolder import scaffold_task_instance

    instance_dir = scaffold_task_instance(config, engine_source, tdir, inst, tmp_path, tool_mode_override="no-tool")

    calc_scripts = list((instance_dir / "environment").glob("*_calc.py"))
    assert calc_scripts == [], "No *_calc.py should be present in no-tool mode"

    # Dockerfile should also not reference the calc script
    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text()
    assert "_calc.py" not in dockerfile, "Dockerfile must not reference calc script in no-tool mode"


# ---------------------------------------------------------------------------
# Test 7: custom verifier is copied
# ---------------------------------------------------------------------------


def test_scaffold_copies_custom_verifier(tmp_path: Path) -> None:
    """If template_dir contains verify.py, scaffold must copy it instead of generating one."""
    import shutil

    # Create a minimal fake template directory with a custom verify.py
    fake_template_dir = tmp_path / "fake_template"
    shutil.copytree(TEMPLATE_DIR, fake_template_dir)

    custom_verifier_content = (
        "# ABOUTME: Custom verifier.\n"
        "# ABOUTME: This is a hand-written verifier used to test copy logic.\n"
        "print('custom verifier')\n"
    )
    (fake_template_dir / "verify.py").write_text(custom_verifier_content)

    config, tdir = load_template(fake_template_dir)
    engine = load_engine_module(tdir)
    inst = sample_instance(config, engine.compute, "easy", seed=42, instance_index=0)
    engine_source = (tdir / "engine.py").read_text()

    from aec_bench.generation.scaffolder import scaffold_task_instance

    instance_dir = scaffold_task_instance(config, engine_source, fake_template_dir, inst, tmp_path / "output")

    verify_py = (instance_dir / "tests" / "verify.py").read_text()
    assert "custom verifier" in verify_py, "Custom verify.py content must be copied verbatim"
    assert "custom" in verify_py


# ---------------------------------------------------------------------------
# Test 8: Dockerfile contains ubuntu:24.04
# ---------------------------------------------------------------------------


def test_scaffold_dockerfile_exists_and_has_ubuntu(tmp_path: Path) -> None:
    """environment/Dockerfile must exist and reference ubuntu:24.04."""
    instance_dir = _generate_test_instance(tmp_path)
    dockerfile = (instance_dir / "environment" / "Dockerfile").read_text()

    assert "ubuntu:24.04" in dockerfile, "Dockerfile must use ubuntu:24.04 base image"
    assert "python3" in dockerfile, "Dockerfile must install python3"


# ---------------------------------------------------------------------------
# Test 9: [tools] section in task.toml for with-tool mode
# ---------------------------------------------------------------------------


def test_scaffold_task_toml_has_tools_section_when_with_tool(tmp_path: Path) -> None:
    """task.toml must contain a [tools] section with the calc script when tool_mode is with-tool."""
    instance_dir = _generate_test_instance(tmp_path)

    with open(instance_dir / "task.toml", "rb") as fh:
        data = tomllib.load(fh)

    assert "tools" in data, "[tools] section missing from task.toml"
    assert "scripts" in data["tools"], "'scripts' key missing from [tools] section"
    scripts = data["tools"]["scripts"]
    assert len(scripts) == 1
    assert scripts[0].endswith("_calc.py")


def test_scaffold_task_toml_no_tools_section_in_no_tool_mode(tmp_path: Path) -> None:
    """task.toml must NOT contain a [tools] section when tool_mode is no-tool."""
    config, tdir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(tdir)
    inst = sample_instance(config, engine.compute, "easy", seed=42, instance_index=0)
    engine_source = (tdir / "engine.py").read_text()

    from aec_bench.generation.scaffolder import scaffold_task_instance

    instance_dir = scaffold_task_instance(config, engine_source, tdir, inst, tmp_path, tool_mode_override="no-tool")

    with open(instance_dir / "task.toml", "rb") as fh:
        data = tomllib.load(fh)

    assert "tools" not in data, "[tools] section should not be present in no-tool mode"
