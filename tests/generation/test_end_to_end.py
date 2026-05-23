# ABOUTME: End-to-end integration test for the generation pipeline.
# ABOUTME: Proves: load template -> sample instance -> scaffold -> run verifier against golden output.

import json
import subprocess
from pathlib import Path

TEMPLATE_DIR = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "aec_bench"
    / "templates"
    / "builtin"
    / "ground"
    / "terzaghi_bearing_capacity"
)


def _find_template_by_name(name: str) -> tuple:
    """Discover built-in templates and find one by name."""
    from aec_bench.templates.registry import discover_templates

    templates = discover_templates()
    for config, tdir in templates:
        if config.meta.name == name:
            return config, tdir
    msg = f"Template {name} not found in built-ins"
    raise ValueError(msg)


def _scaffold_terzaghi_instance(tmp_path: Path, difficulty: str = "easy", seed: int = 42) -> Path:
    """Helper: generate a complete Terzaghi instance in tmp_path."""
    from aec_bench.generation.sampler import sample_instance
    from aec_bench.generation.scaffolder import scaffold_task_instance
    from aec_bench.templates.registry import load_engine_module, load_template

    config, template_dir = load_template(TEMPLATE_DIR)
    engine = load_engine_module(template_dir)
    instance = sample_instance(config, engine.compute, difficulty, seed=seed, instance_index=0)
    engine_source = (template_dir / "engine.py").read_text()
    return scaffold_task_instance(config, engine_source, template_dir, instance, tmp_path)


def test_generated_verifier_scores_golden_pass_at_1_0(tmp_path: Path) -> None:
    """Generate a Terzaghi task, run its verifier against golden_pass — expect reward 1.0."""
    instance_dir = _scaffold_terzaghi_instance(tmp_path)

    # Copy golden_pass as the agent's output
    golden = (instance_dir / "tests" / "fixtures" / "golden_pass.md").read_text()
    output_md = tmp_path / "output.md"
    output_md.write_text(golden)

    # Run verifier
    verify_py = instance_dir / "tests" / "verify.py"
    reward_file = tmp_path / "reward.json"

    result = subprocess.run(
        ["python3", str(verify_py), "--input", str(output_md), "--output", str(reward_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Verifier failed: {result.stderr}"

    reward_data = json.loads(reward_file.read_text())
    assert reward_data["reward"] == 1.0, f"Expected reward 1.0, got {reward_data}"


def test_generated_verifier_scores_golden_fail_below_1(tmp_path: Path) -> None:
    """Generate a Terzaghi task, run its verifier against golden_fail — expect reward < 1.0."""
    instance_dir = _scaffold_terzaghi_instance(tmp_path)

    # Copy golden_fail as the agent's output
    golden_fail = (instance_dir / "tests" / "fixtures" / "golden_fail.md").read_text()
    output_md = tmp_path / "output.md"
    output_md.write_text(golden_fail)

    # Run verifier
    verify_py = instance_dir / "tests" / "verify.py"
    reward_file = tmp_path / "reward.json"

    result = subprocess.run(
        ["python3", str(verify_py), "--input", str(output_md), "--output", str(reward_file)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"Verifier failed: {result.stderr}"

    reward_data = json.loads(reward_file.read_text())
    assert reward_data["reward"] == 0.0, f"Expected reward 0.0 for all-zeros, got {reward_data}"


def test_generated_cli_tool_runs_and_returns_json(tmp_path: Path) -> None:
    """If with-tool, the generated calc script should run with --help and return valid output."""
    instance_dir = _scaffold_terzaghi_instance(tmp_path)

    # Find the generated calc script
    calc_scripts = list(instance_dir.glob("environment/*_calc.py"))
    assert len(calc_scripts) == 1, f"Expected 1 calc script, found {calc_scripts}"

    calc_script = calc_scripts[0]

    # Run with --help (should exit 0)
    result = subprocess.run(
        ["python3", str(calc_script), "--help"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, f"--help failed: {result.stderr}"
    assert "usage" in result.stdout.lower() or "help" in result.stdout.lower()


def test_full_pipeline_via_discovery(tmp_path: Path) -> None:
    """Test that the template can be found via discovery and used end-to-end."""
    config, tdir = _find_template_by_name("terzaghi-bearing-capacity")
    assert config.meta.discipline == "ground"
    assert config.meta.category == "shallow-foundations"


def test_dataset_generation_verifier_scores_golden_pass(tmp_path: Path) -> None:
    """Compose a 2-instance dataset via SuiteConfig, then verify each instance scores 1.0."""
    from aec_bench.generation.dataset import (
        CoverageConfig,
        InstanceConfig,
        OutputConfig,
        SuiteConfig,
        TemplateSelection,
        ToolModeMix,
        VisibilityMix,
        compose_dataset,
        execute_plan,
    )
    from aec_bench.templates.registry import discover_templates

    output_dir = tmp_path / "dataset_out"
    output_dir.mkdir()

    suite = SuiteConfig(
        name="e2e-golden-test",
        seed=99,
        coverage=CoverageConfig(
            difficulties={"easy": 1.0},
            min_tasks_per_discipline=1,
        ),
        templates=TemplateSelection(include=["ground/*"]),
        visibility=VisibilityMix(mix={"all_given": 1.0}),
        tool_mode=ToolModeMix(mix={"with-tool": 1.0}),
        instances=InstanceConfig(per_task=2, total_max=2),
        output=OutputConfig(dir=output_dir),
    )

    templates = discover_templates()
    plan = compose_dataset(suite, templates)
    assert plan.summary.total_instances == 2

    manifest = execute_plan(plan, suite)
    assert len(manifest.instances) == 2

    for entry in manifest.instances:
        instance_dir = output_dir / entry.path
        assert instance_dir.is_dir(), f"Instance dir missing: {instance_dir}"

        # Copy golden_pass.md as the agent output
        golden = (instance_dir / "tests" / "fixtures" / "golden_pass.md").read_text()
        agent_output = tmp_path / f"output_{entry.path.replace('/', '_')}.md"
        agent_output.write_text(golden)

        # Run verifier
        verify_py = instance_dir / "tests" / "verify.py"
        reward_file = tmp_path / f"reward_{entry.path.replace('/', '_')}.json"

        result = subprocess.run(
            ["python3", str(verify_py), "--input", str(agent_output), "--output", str(reward_file)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"Verifier failed for {entry.path}: {result.stderr}"

        reward_data = json.loads(reward_file.read_text())
        assert reward_data["reward"] == 1.0, f"Expected reward 1.0 for {entry.path}, got {reward_data}"


def test_builtin_templates_discovered() -> None:
    """All built-in templates should be discoverable."""
    from aec_bench.templates.registry import discover_templates

    templates = discover_templates()
    names = sorted(cfg.meta.name for cfg, _ in templates)
    assert len(templates) >= 3
    assert "infinite-slope" in names
    assert "spt-corrections" in names
    assert "terzaghi-bearing-capacity" in names


def test_dataset_with_three_templates(tmp_path: Path) -> None:
    """Generate a dataset from all 3 ground templates and verify coverage."""
    import tomllib

    from aec_bench.generation.dataset import (
        SuiteConfig,
        compose_dataset,
        execute_plan,
    )
    from aec_bench.templates.registry import discover_templates

    raw = tomllib.loads("""
        name = "three-template-test"
        seed = 42

        [coverage]
        difficulties = {easy = 0.5, medium = 0.5}
        min_tasks_per_discipline = 1

        [templates]
        include = ["ground/*"]

        [visibility]
        mix = {all_given = 1.0}

        [tool_mode]
        mix = {with_tool = 1.0}

        [instances]
        per_task = 2
        total_max = 100

        [output]
        dir = "PLACEHOLDER"
    """)
    raw["output"]["dir"] = str(tmp_path)
    config = SuiteConfig.model_validate(raw)

    templates = discover_templates()
    plan = compose_dataset(config, templates)

    # All ground templates represented (2 instances each)
    template_names = {p.template_name for p in plan.planned_instances}
    assert "terzaghi-bearing-capacity" in template_names
    assert "spt-corrections" in template_names
    assert "infinite-slope" in template_names
    expected_count = len(template_names) * 2
    assert plan.summary.total_instances == expected_count

    # Execute and verify manifest
    manifest = execute_plan(plan, config)
    assert len(manifest.instances) == expected_count

    dataset_json = tmp_path / "dataset.json"
    assert dataset_json.exists()
