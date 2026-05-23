# ABOUTME: CLI integration tests for the task validate command.
# ABOUTME: Verifies human-readable and JSON output for valid and invalid tasks.

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from aec_bench.cli.main import app

runner = CliRunner()


def _make_valid_task(root: Path) -> Path:
    task_dir = root / "electrical" / "test-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n'
        'tags = ["electrical"]\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n"
    )
    (task_dir / "instruction.md").write_text("Calculate the result and write to `/workspace/output.md`.\n")
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text("# verifier\n")
    (tests_dir / "test.sh").write_text("#!/bin/bash\npython3 /tests/verify.py\n")
    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text("FROM python:3.12\n")
    return task_dir


def _make_valid_named_task(root: Path, *segments: str) -> Path:
    task_dir = root.joinpath(*segments)
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n'
        f'tags = ["{segments[0]}"]\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n"
    )
    (task_dir / "instruction.md").write_text("Calculate the result and write to `/workspace/output.md`.\n")
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text("# verifier\n")
    (tests_dir / "test.sh").write_text("#!/bin/bash\npython3 /tests/verify.py\n")
    env_dir = task_dir / "environment"
    env_dir.mkdir()
    (env_dir / "Dockerfile").write_text("FROM python:3.12\n")
    return task_dir


class TestTaskValidate:
    def test_valid_task_exits_zero(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        result = runner.invoke(app, ["task", "validate", str(task_dir)])
        assert result.exit_code == 0

    def test_missing_files_exits_one(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "electrical" / "bad-task"
        task_dir.mkdir(parents=True)
        result = runner.invoke(app, ["task", "validate", str(task_dir)])
        assert result.exit_code == 1

    def test_output_includes_task_id(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        result = runner.invoke(app, ["task", "validate", str(task_dir)])
        assert "test-task" in result.output

    def test_json_output_has_findings(self, tmp_path: Path) -> None:
        task_dir = tmp_path / "electrical" / "bad-task"
        task_dir.mkdir(parents=True)
        result = runner.invoke(app, ["--json", "task", "validate", str(task_dir)])
        assert "findings" in result.output

    def test_tasks_root_option(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        result = runner.invoke(
            app,
            ["task", "validate", str(task_dir), "--tasks-root", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "electrical/test-task" in result.output


class TestTaskGenome:
    def test_genome_command_prints_sidecar_yaml(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)

        result = runner.invoke(
            app,
            ["task", "genome", str(task_dir), "--tasks-root", str(tmp_path)],
        )

        assert result.exit_code == 0
        assert "task_id: electrical/test-task" in result.output
        assert "output_contract:" in result.output

    def test_genome_command_can_print_evidence_packet(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)

        result = runner.invoke(
            app,
            [
                "task",
                "genome",
                str(task_dir),
                "--tasks-root",
                str(tmp_path),
                "--mode",
                "evidence",
            ],
        )

        assert result.exit_code == 0
        assert "deterministic_manifest:" in result.output
        assert "instruction_sections:" in result.output

    def test_genome_batch_writes_engineering_catalogue(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        _make_valid_named_task(tasks_root, "electrical", "voltage-drop")
        _make_valid_named_task(tasks_root, "mechanical", "heat-load", "demo")
        _make_valid_named_task(tasks_root, "generated", "suite", "electrical", "demo")
        output_dir = tmp_path / "task_genomes"

        result = runner.invoke(
            app,
            [
                "task",
                "genome-batch",
                str(tasks_root),
                "--output-dir",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0
        assert (output_dir / "electrical" / "voltage-drop.yaml").exists()
        assert (output_dir / "mechanical" / "heat-load" / "demo.yaml").exists()
        assert not (output_dir / "generated" / "suite" / "electrical" / "demo.yaml").exists()
        assert (output_dir / "index.yaml").exists()
        assert "written: 2" in result.output

    def test_genome_batch_can_include_generated_instances(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        _make_valid_named_task(tasks_root, "electrical", "voltage-drop")
        _make_valid_named_task(tasks_root, "generated", "suite", "electrical", "demo")
        output_dir = tmp_path / "task_genomes"

        result = runner.invoke(
            app,
            [
                "task",
                "genome-batch",
                str(tasks_root),
                "--output-dir",
                str(output_dir),
                "--include-generated",
            ],
        )

        assert result.exit_code == 0
        assert (output_dir / "electrical" / "voltage-drop.yaml").exists()
        assert (output_dir / "generated" / "suite" / "electrical" / "demo.yaml").exists()
        assert "written: 2" in result.output

    def test_genome_batch_can_filter_by_domain(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        _make_valid_named_task(tasks_root, "electrical", "voltage-drop")
        _make_valid_named_task(tasks_root, "mechanical", "heat-load", "demo")
        output_dir = tmp_path / "task_genomes"

        result = runner.invoke(
            app,
            [
                "task",
                "genome-batch",
                str(tasks_root),
                "--output-dir",
                str(output_dir),
                "--domains",
                "electrical",
            ],
        )

        assert result.exit_code == 0
        assert (output_dir / "electrical" / "voltage-drop.yaml").exists()
        assert not (output_dir / "mechanical" / "heat-load" / "demo.yaml").exists()
        assert "written: 1" in result.output

    def test_genome_template_batch_writes_template_catalogue(self, tmp_path: Path) -> None:
        templates_root = tmp_path / "templates"
        velocity_dir = templates_root / "mechanical" / "velocity_check"
        velocity_dir.mkdir(parents=True)
        (velocity_dir / "engine.py").write_text("def compute():\n    return {}\n")
        (velocity_dir / "instruction.md").write_text(
            "You are a senior mechanical engineer.\n\n"
            "## Problem\n\nCalculate pipe velocity.\n\n"
            '## Output Format\n\n```json\n{"velocity_m_s": 1.0}\n```\n'
        )
        (velocity_dir / "params.toml").write_text(
            "[meta]\n"
            'name = "velocity-check"\n'
            'description = "Pipe velocity calculation"\n'
            'discipline = "mechanical"\n'
            'category = "pipe-hydraulics"\n'
            'standards = ["AWWA M11"]\n'
            'tags = ["mechanical"]\n'
            'tool_mode = "with-tool"\n\n'
            "[params.flow_rate_l_s]\n"
            'type = "float"\n'
            'description = "Flow rate"\n'
            'unit = "L/s"\n'
            "min = 0\n"
            "max = 10\n\n"
            "[outputs.velocity_m_s]\n"
            'description = "Velocity"\n'
            "tolerance = 0.03\n"
        )
        output_dir = tmp_path / "template_genomes"

        result = runner.invoke(
            app,
            [
                "task",
                "genome-template-batch",
                str(templates_root),
                "--output-dir",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0
        assert (output_dir / "mechanical" / "velocity-check.yaml").exists()
        assert (output_dir / "index.yaml").exists()
        assert "written: 1" in result.output

    def test_decomposition_template_batch_writes_decomposition_catalogue(
        self,
        tmp_path: Path,
    ) -> None:
        genomes_root = tmp_path / "template_genomes"
        genomes_root.mkdir()
        mechanical_dir = genomes_root / "mechanical"
        mechanical_dir.mkdir()
        (mechanical_dir / "velocity-check.yaml").write_text(
            "task_id: mechanical/velocity-check\n"
            "source_task_path: src/aec_bench/templates/builtin/mechanical/velocity_check\n"
            "status: extracted\n"
            "domain_frame:\n"
            "  discipline: mechanical\n"
            "  subdomain: pipe-hydraulics\n"
            "  standards: [AWWA M11]\n"
            "scenario:\n"
            "  summary: Calculates pipe velocity from flow and diameter.\n"
            "input_bundle:\n"
            "  quantities: [flow_rate_l_s, pipe_internal_diameter_mm]\n"
            "  artifacts: []\n"
            "  assumptions: []\n"
            "reasoning_moves: [calculation]\n"
            "pressure_points:\n"
            "  - id: explicit_range_check\n"
            "    type: threshold_decision\n"
            "    description: Solver must compare velocity against an explicit range.\n"
            "    provenance: []\n"
            "output_contract:\n"
            "  format: markdown_with_json_block\n"
            "  required_fields: [velocity_m_s, velocity_within_range]\n"
            "  output_path: /workspace/output.md\n"
            "verifier_contract:\n"
            "  mode: template_engine\n"
            "  script: src/aec_bench/templates/builtin/mechanical/velocity_check/engine.py\n"
            "  field_scores: {velocity_m_s: tolerance_0.03}\n"
            "difficulty_controls:\n"
            "  difficulty_levels: [easy]\n"
            "  hidden_parameter_count: 0\n"
            "trajectory_affordances:\n"
            "  expected_intermediate_steps: [compute_velocity_m_s]\n"
            "extraction:\n"
            "  deterministic_fields: []\n"
            "  reasoning_review_fields: []\n"
            "  missing_fields: []\n",
            encoding="utf-8",
        )
        output_dir = tmp_path / "template_decompositions"

        result = runner.invoke(
            app,
            [
                "task",
                "decomposition-template-batch",
                str(genomes_root),
                "--output-dir",
                str(output_dir),
            ],
        )

        assert result.exit_code == 0
        assert (output_dir / "mechanical" / "velocity-check.yaml").exists()
        assert (output_dir / "index.yaml").exists()
        assert "written: 1" in result.output
