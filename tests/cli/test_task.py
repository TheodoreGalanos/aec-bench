# ABOUTME: CLI integration tests for the task validate command.
# ABOUTME: Verifies human-readable and JSON output for valid and invalid tasks.

from __future__ import annotations

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.identity import EntityKind, new_entity_id

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


def _add_explicit_identity(task_dir: Path, *, lifecycle: str = "active", visibility: str = "public") -> str:
    task_id = new_entity_id(EntityKind.TASK)
    task_toml = (task_dir / "task.toml").read_text(encoding="utf-8")
    task_toml = task_toml.replace(
        "[metadata]\n",
        f'[identity]\nid = "{task_id}"\nkey = "electrical/test-task"\nversion = 2\n\n'
        f'[metadata]\nlifecycle = "{lifecycle}"\nvisibility = "{visibility}"\n',
    )
    (task_dir / "task.toml").write_text(task_toml, encoding="utf-8")
    return str(task_id)


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
        task_dir = _make_valid_task(tmp_path)
        task_id = _add_explicit_identity(task_dir)
        result = runner.invoke(app, ["--json", "task", "validate", str(task_dir)])

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "success"
        assert payload["data"]["findings"] == []
        assert payload["data"]["identity"]["id"] == task_id
        assert payload["data"]["identity"]["version"] == 2
        assert payload["data"]["identity"]["lifecycle"] == "active"
        assert payload["data"]["identity"]["visibility"] == "public"

    def test_tasks_root_option(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        result = runner.invoke(
            app,
            ["task", "validate", str(task_dir), "--tasks-root", str(tmp_path)],
        )
        assert result.exit_code == 0
        assert "electrical/test-task" in result.output

    def test_output_includes_explicit_identity_and_policy(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        _add_explicit_identity(task_dir)

        result = runner.invoke(app, ["--text", "task", "validate", str(task_dir)])

        assert result.exit_code == 0
        assert "Task: electrical/test-task ·" in result.output
        assert "Version: 2" in result.output
        assert "Lifecycle: active" in result.output
        assert "Visibility: public" in result.output
        assert "Runnable: yes" in result.output
        assert "Verifier: tests/test.sh, version 1" in result.output
        assert "Errors: none" in result.output
        assert "Warnings: none" in result.output


class TestTaskExplain:
    def test_explain_resolves_key_and_uuid(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        task_id = _add_explicit_identity(task_dir)

        result = runner.invoke(app, ["--text", "task", "explain", task_id, "--tasks-root", str(tmp_path)])

        assert result.exit_code == 0
        assert "Canonical_key" not in result.output
        assert "Task: electrical/test-task" in result.output
        assert task_id in result.output
        assert "Version: 2" in result.output
        assert "Output contract" in result.output
        assert "tests/test.sh" in result.output

    def test_explain_unknown_task_fails(self, tmp_path: Path) -> None:
        result = runner.invoke(app, ["--text", "task", "explain", "electrical/missing", "--tasks-root", str(tmp_path)])

        assert result.exit_code == 1
        assert "task not found" in result.output


class TestTaskMetadataMigration:
    def test_check_write_and_second_check_are_idempotent(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        report_path = tmp_path / "migration-report.json"
        task_toml = (
            (task_dir / "task.toml")
            .read_text(encoding="utf-8")
            .replace("[metadata]\n", '[metadata]\nlifecycle = "active"\nvisibility = "public"\n')
        )
        (task_dir / "task.toml").write_text(task_toml, encoding="utf-8")

        check = runner.invoke(
            app,
            [
                "--text",
                "task",
                "migrate-metadata",
                "--check",
                "--tasks-root",
                str(tmp_path),
                "--report-path",
                str(report_path),
            ],
        )
        write = runner.invoke(
            app,
            [
                "--text",
                "task",
                "migrate-metadata",
                "--write",
                "--tasks-root",
                str(tmp_path),
                "--report-path",
                str(report_path),
            ],
        )
        second_check = runner.invoke(
            app,
            [
                "--text",
                "task",
                "migrate-metadata",
                "--check",
                "--tasks-root",
                str(tmp_path),
                "--report-path",
                str(report_path),
            ],
        )

        assert check.exit_code == 0
        assert "would update 1" in check.output
        assert write.exit_code == 0
        assert "updated 1" in write.output
        assert second_check.exit_code == 0
        assert "would update 0" in second_check.output

    def test_write_refuses_missing_policy_instead_of_inventing_it(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        task_toml = (
            (task_dir / "task.toml")
            .read_text(encoding="utf-8")
            .replace("[metadata]\n", '[metadata]\nvisibility = "public"\n')
        )
        (task_dir / "task.toml").write_text(task_toml, encoding="utf-8")

        check = runner.invoke(
            app,
            ["--text", "task", "migrate-metadata", "--check", "--tasks-root", str(tmp_path)],
        )
        result = runner.invoke(
            app,
            ["--text", "task", "migrate-metadata", "--write", "--tasks-root", str(tmp_path)],
        )

        assert check.exit_code == 0
        assert "review:" in check.output
        assert result.exit_code == 1
        assert "reviewer must author" in result.output

    def test_json_output_is_single_envelope(self, tmp_path: Path) -> None:
        task_dir = _make_valid_task(tmp_path)
        _add_explicit_identity(task_dir)
        report_path = tmp_path / "migration-report.json"

        result = runner.invoke(
            app,
            [
                "--json",
                "task",
                "migrate-metadata",
                "--check",
                "--tasks-root",
                str(tmp_path),
                "--report-path",
                str(report_path),
            ],
        )

        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["status"] == "success"
        assert payload["data"]["mode"] == "check"
        assert payload["data"]["task_count"] == 1


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
        assert "extractor: deterministic-task-genome" in result.output
        assert "genome:" in result.output
        assert "evidence:" in result.output
        assert "instruction_sections:" not in result.output
        assert "verifier_files:" not in result.output

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

    def test_genome_batch_retains_each_review_as_one_artifact_reference(self, tmp_path: Path) -> None:
        tasks_root = tmp_path / "tasks"
        _make_valid_named_task(tasks_root, "electrical", "voltage-drop")
        output_dir = tmp_path / "task_genomes"

        result = runner.invoke(
            app,
            [
                "task",
                "genome-batch",
                str(tasks_root),
                "--output-dir",
                str(output_dir),
                "--mode",
                "evidence",
            ],
        )

        assert result.exit_code == 0
        index = yaml.safe_load((output_dir / "index.yaml").read_text(encoding="utf-8"))
        entry = index["entries"][0]
        assert entry["status"] == "extracted"
        assert set(entry["review"]) == {"artifact_id", "sha256", "size_bytes", "media_type"}
        assert (output_dir / "review_artifacts" / entry["review"]["artifact_id"]).is_file()
        assert not (output_dir / "electrical" / "voltage-drop.yaml").exists()

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
        index = yaml.safe_load((output_dir / "index.yaml").read_text(encoding="utf-8"))
        assert index["entries"][0]["template_path"] == "templates/mechanical/velocity_check"
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
