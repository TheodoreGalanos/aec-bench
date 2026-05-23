# ABOUTME: Tests for exporting aec-bench tasks as Prime Lab environment packages.
# ABOUTME: Verifies generated package structure, task payloads, and CLI wiring.

from __future__ import annotations

import json
import os
import py_compile
import stat
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aec_bench.cli.main import app
from aec_bench.contracts.dataset import (
    DatasetDescription,
    DatasetManifest,
    DatasetSource,
    DatasetTaskEntry,
)
from aec_bench.dataset.storage import write_manifest
from aec_bench.prime_lab.classifier import PrimeHarnessKind, classify_prime_harness
from aec_bench.prime_lab.exporter import (
    DEFAULT_PRIME_ENVIRONMENTS_DIR,
    PrimeExportHarnessMode,
    PrimeLabExportConfig,
    export_prime_lab_environment,
)
from aec_bench.prime_lab.workspace_tools import WorkspaceCommandSet
from aec_bench.tasks.loader import load_task_definition

runner = CliRunner()


def _write_dataset_manifest(
    datasets_root: Path,
    *,
    name: str,
    version: str,
    task_ids: list[str],
) -> None:
    from datetime import UTC, datetime

    manifest = DatasetManifest(
        name=name,
        version=version,
        content_hash="dataset-hash",
        description=DatasetDescription(
            summary="Prime smoke dataset",
            domains=["electrical"],
            difficulty_distribution={"easy": len(task_ids)},
            task_count=len(task_ids),
        ),
        created_at=datetime.now(UTC),
        tasks=[
            DatasetTaskEntry(
                task_id=task_id,
                task_path=f"tasks/{task_id}",
                content_hash=f"hash-{index}",
                domain="electrical",
                difficulty="easy",
                tags=["prime"],
            )
            for index, task_id in enumerate(task_ids)
        ],
        source=DatasetSource(method="manual"),
    )
    write_manifest(datasets_root, manifest)


def _make_task(
    root: Path,
    task_id: str = "electrical/voltage-drop",
    *,
    difficulty: str = "easy",
) -> Path:
    task_dir = root / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        f'difficulty = "{difficulty}"\n'
        'category = "reasoning"\n'
        'tags = ["electrical", "deterministic"]\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n",
        encoding="utf-8",
    )
    (task_dir / "instruction.md").write_text(
        "Calculate the answer and write the result to `/workspace/output.md`.\n",
        encoding="utf-8",
    )
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "verify.py").write_text(
        "from pathlib import Path\n"
        "import argparse\n"
        "import json\n"
        "parser = argparse.ArgumentParser()\n"
        "parser.add_argument('--input', type=Path)\n"
        "parser.add_argument('--output', type=Path)\n"
        "args = parser.parse_args()\n"
        "reward = 1.0 if '42' in args.input.read_text() else 0.0\n"
        "args.output.parent.mkdir(parents=True, exist_ok=True)\n"
        "args.output.write_text(json.dumps({'reward': reward}))\n",
        encoding="utf-8",
    )
    return task_dir


def _prepare_dataset_project(tmp_path: Path, task_ids: list[str]) -> None:
    (tmp_path / "aec-bench.toml").write_text(
        '[paths]\ntasks = "tasks"\ndatasets = "datasets"\n',
        encoding="utf-8",
    )
    tasks_root = tmp_path / "tasks"
    datasets_root = tmp_path / "datasets"
    for task_id in task_ids:
        _make_task(tasks_root, task_id)
    _write_dataset_manifest(datasets_root, name="suite", version="1.0.0", task_ids=task_ids)


def test_prime_harness_classifier_marks_plain_task_single_turn(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    task = load_task_definition(task_dir, tasks_root)

    classification = classify_prime_harness(task, task_dir)

    assert classification.kind is PrimeHarnessKind.SINGLE_TURN
    assert classification.reasons == ["no task tools or workspace policy detected"]


def test_prime_harness_classifier_prefers_lambda_rlm_policy(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root, "electrical/report-policy")
    (task_dir / "lambda-rlm.toml").write_text("[policy]\n", encoding="utf-8")
    task = load_task_definition(task_dir, tasks_root)

    classification = classify_prime_harness(task, task_dir)

    assert classification.kind is PrimeHarnessKind.LAMBDA_RLM_POLICY
    assert classification.reasons == ["lambda-rlm.toml present"]


def test_prime_harness_classifier_marks_rlm_policy(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root, "electrical/rlm-test")
    (task_dir / "rlm.toml").write_text("[guardrails]\nmax_iterations = 20\n", encoding="utf-8")
    task = load_task_definition(task_dir, tasks_root)

    classification = classify_prime_harness(task, task_dir)

    assert classification.kind is PrimeHarnessKind.RLM_POLICY
    assert classification.reasons == ["rlm.toml present"]


def test_prime_harness_classifier_marks_bash_task_stateful(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n\n"
        "[[environment.tools]]\n"
        'name = "bash"\n'
        'source = "tools/bash.py"\n'
        'description = "Run local workspace commands."\n',
        encoding="utf-8",
    )
    task = load_task_definition(task_dir, tasks_root)

    classification = classify_prime_harness(task, task_dir)

    assert classification.kind is PrimeHarnessKind.STATEFUL_WORKSPACE
    assert classification.reasons == ["workspace-affecting tool declared: bash"]


def test_workspace_commands_keep_paths_inside_workspace(tmp_path: Path) -> None:
    commands = WorkspaceCommandSet(tmp_path)

    commands.write_file("notes/result.md", "done")
    commands.write_file("/workspace/output.md", "alias")

    assert commands.read_file("notes/result.md") == "done"
    assert commands.read_file("output.md") == "alias"
    assert "notes/result.md" in commands.list_files(".")
    with pytest.raises(ValueError, match="outside workspace"):
        commands.read_file("../secret.txt")


def test_workspace_commands_run_argument_vector(tmp_path: Path) -> None:
    commands = WorkspaceCommandSet(tmp_path)

    result = commands.run_command(["python", "-c", "print('hello')"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "hello"


def test_export_creates_prime_lab_package(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-voltage-drop",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/voltage-drop"],
        )
    )

    package_dir = result.package_dir
    assert (package_dir / "pyproject.toml").exists()
    assert (package_dir / "README.md").exists()
    assert (package_dir / "aec_voltage_drop" / "environment.py").exists()
    assert (package_dir / "aec_voltage_drop" / "tasks" / "electrical" / "voltage-drop" / "instruction.md").exists()
    assert 'dependencies = ["datasets>=4.0", "verifiers>=0.1.10"]' in (package_dir / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert 'tags = ["aec-bench", "aec", "benchmark"]' in (package_dir / "pyproject.toml").read_text(encoding="utf-8")
    assert "def load_environment" in (package_dir / "aec_voltage_drop" / "environment.py").read_text(encoding="utf-8")
    assert '"harness_kind": "single_turn"' in (package_dir / "aec_voltage_drop" / "environment.py").read_text(
        encoding="utf-8"
    )
    py_compile.compile(
        str(package_dir / "aec_voltage_drop" / "environment.py"),
        doraise=True,
    )


def test_export_carries_rlm_guardrails_into_stateful_environment(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root, "electrical/rlm-test")
    (task_dir / "rlm.toml").write_text(
        '[template]\ntier = "flat"\n\n[guardrails]\ntoken_budget = 100_000\nmax_iterations = 20\n',
        encoding="utf-8",
    )

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-rlm-test",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/rlm-test"],
        )
    )

    environment_py = result.package_dir / "aec_rlm_test" / "environment.py"
    source = environment_py.read_text(encoding="utf-8")
    assert '"harness_kind": "rlm_policy"' in source
    assert '"rollout_limits": {' in source
    assert '"max_turns": 20' in source
    assert '"token_budget": 100000' in source
    assert "max_turns=_environment_max_turns(tasks)" in source
    assert "Source policy guardrails" in source
    assert "def _user_message(" in source
    py_compile.compile(str(environment_py), doraise=True)


def test_export_creates_stateful_workspace_environment_for_bash_task(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n\n"
        "[[environment.tools]]\n"
        'name = "bash"\n'
        'source = "tools/bash.py"\n'
        'description = "Run local workspace commands."\n',
        encoding="utf-8",
    )

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-workspace-task",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/voltage-drop"],
        )
    )

    environment_py = result.package_dir / "aec_workspace_task" / "environment.py"
    source = environment_py.read_text(encoding="utf-8")
    assert "class AecBenchStatefulWorkspaceEnv(vf.StatefulToolEnv)" in source
    assert "def run_command(" in source
    assert '"harness_kind": "stateful_workspace"' in source
    py_compile.compile(str(environment_py), doraise=True)


def test_export_can_force_single_turn_for_workspace_task(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n\n"
        "[[environment.tools]]\n"
        'name = "bash"\n'
        'source = "tools/bash.py"\n'
        'description = "Run local workspace commands."\n',
        encoding="utf-8",
    )

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-forced-single",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/voltage-drop"],
            harness_mode=PrimeExportHarnessMode.SINGLE_TURN,
        )
    )

    source = (result.package_dir / "aec_forced_single" / "environment.py").read_text(encoding="utf-8")
    assert "vf.SingleTurnEnv" in source
    assert "class AecBenchStatefulWorkspaceEnv" not in source
    assert '"harness_kind": "single_turn"' in source
    assert "forced by export harness mode" in source


def test_prime_export_cli_accepts_harness_mode(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)
    output_dir = tmp_path / "prime-envs"

    result = runner.invoke(
        app,
        [
            "prime",
            "export",
            "--name",
            "aec-forced-stateful",
            "--tasks-root",
            str(tasks_root),
            "--output-dir",
            str(output_dir),
            "--task",
            "electrical/voltage-drop",
            "--harness-mode",
            "stateful-workspace",
        ],
    )

    assert result.exit_code == 0
    source = (output_dir / "aec_forced_stateful" / "aec_forced_stateful" / "environment.py").read_text(encoding="utf-8")
    assert "class AecBenchStatefulWorkspaceEnv(vf.StatefulToolEnv)" in source
    assert '"harness_kind": "stateful_workspace"' in source


def test_generated_stateful_package_loads_outside_repo_root(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n\n"
        "[[environment.tools]]\n"
        'name = "bash"\n'
        'source = "tools/bash.py"\n'
        'description = "Run local workspace commands."\n',
        encoding="utf-8",
    )
    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-workspace-task",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/voltage-drop"],
        )
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(result.package_dir)

    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "from verifiers import load_environment; "
            "env = load_environment('aec_workspace_task'); "
            "print(type(env).__name__)",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert "AecBenchStatefulWorkspaceEnv" in process.stdout


def test_generated_stateful_workspace_tools_score_with_verifier(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n\n"
        "[[environment.tools]]\n"
        'name = "bash"\n'
        'source = "tools/bash.py"\n'
        'description = "Run local workspace commands."\n',
        encoding="utf-8",
    )
    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-workspace-task",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/voltage-drop"],
        )
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(result.package_dir)

    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import asyncio, tempfile\n"
            "from pathlib import Path\n"
            "from aec_workspace_task.environment import (\n"
            "    WorkspaceCommandSet,\n"
            "    aec_bench_reward,\n"
            "    run_command,\n"
            "    submit_answer,\n"
            ")\n"
            "with tempfile.TemporaryDirectory() as temp_dir:\n"
            "    workspace = Path(temp_dir) / 'workspace'\n"
            "    task_dir = Path(__import__('aec_workspace_task').__file__).parent\n"
            "    source = task_dir / 'tasks' / 'electrical' / 'voltage-drop'\n"
            "    import shutil\n"
            "    shutil.copytree(source, workspace)\n"
            "    commands = WorkspaceCommandSet(workspace)\n"
            "    state = {'workspace_path': str(workspace)}\n"
            "    result = run_command(['python', '-c', \"print('tool-ok')\"], commands)\n"
            "    assert result['exit_code'] == 0\n"
            "    assert 'tool-ok' in result['stdout']\n"
            "    submit_answer('42', commands, state, path='/workspace/output.md')\n"
            "    reward = asyncio.run(\n"
            "        aec_bench_reward([], {'verifier_timeout_seconds': 120}, state)\n"
            "    )\n"
            "    print(reward)\n",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "1.0"


def test_generated_stateful_write_file_keeps_rollout_open_for_workspace_alias(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root)
    (task_dir / "task.toml").write_text(
        'version = "1.0"\n\n'
        "[metadata]\n"
        'difficulty = "easy"\n'
        'category = "reasoning"\n\n'
        "[agent]\ntimeout_sec = 600\n\n"
        "[verifier]\ntimeout_sec = 120\n\n"
        "[environment]\nextensions = []\n\n"
        "[[environment.tools]]\n"
        'name = "bash"\n'
        'source = "tools/bash.py"\n'
        'description = "Run local workspace commands."\n',
        encoding="utf-8",
    )
    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-workspace-task",
            tasks_root=tasks_root,
            output_dir=tmp_path / "environments",
            task_ids=["electrical/voltage-drop"],
        )
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(result.package_dir)

    process = subprocess.run(
        [
            sys.executable,
            "-c",
            "import asyncio, tempfile, shutil\n"
            "from pathlib import Path\n"
            "from aec_workspace_task.environment import (\n"
            "    WorkspaceCommandSet,\n"
            "    aec_bench_reward,\n"
            "    write_file,\n"
            "    submit_answer,\n"
            ")\n"
            "with tempfile.TemporaryDirectory() as temp_dir:\n"
            "    workspace = Path(temp_dir) / 'workspace'\n"
            "    task_dir = Path(__import__('aec_workspace_task').__file__).parent\n"
            "    source = task_dir / 'tasks' / 'electrical' / 'voltage-drop'\n"
            "    shutil.copytree(source, workspace)\n"
            "    commands = WorkspaceCommandSet(workspace)\n"
            "    state = {'workspace_path': str(workspace)}\n"
            "    written = write_file('/workspace/output.md', '42', commands)\n"
            "    assert written == 'output.md'\n"
            "    assert 'final_env_response' not in state\n"
            "    submit_answer('42', commands, state, path='/workspace/output.md')\n"
            "    assert state['final_env_response']\n"
            "    reward = asyncio.run(\n"
            "        aec_bench_reward([], {'verifier_timeout_seconds': 120}, state)\n"
            "    )\n"
            "    print(reward)\n",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == "1.0"


def test_prime_export_cli_selects_task_pattern(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)
    output_dir = tmp_path / "prime-envs"

    result = runner.invoke(
        app,
        [
            "prime",
            "export",
            "--name",
            "aec-electrical-smoke",
            "--tasks-root",
            str(tasks_root),
            "--output-dir",
            str(output_dir),
            "--pattern",
            "electrical/*",
        ],
    )

    assert result.exit_code == 0
    assert "aec_electrical_smoke" in result.output
    assert (output_dir / "aec_electrical_smoke" / "pyproject.toml").exists()


def test_prime_export_cli_selects_dataset_tasks(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root, "electrical/voltage-drop-a")
    _make_task(tasks_root, "electrical/voltage-drop-b")
    datasets_root = tmp_path / "datasets"
    _write_dataset_manifest(
        datasets_root,
        name="prime-smoke-suite",
        version="0.1.0",
        task_ids=["electrical/voltage-drop-a", "electrical/voltage-drop-b"],
    )
    output_dir = tmp_path / "prime-envs"

    result = runner.invoke(
        app,
        [
            "prime",
            "export",
            "--name",
            "aec-prime-smoke-suite",
            "--tasks-root",
            str(tasks_root),
            "--datasets-root",
            str(datasets_root),
            "--dataset",
            "prime-smoke-suite@0.1.0",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    environment_py = (output_dir / "aec_prime_smoke_suite" / "aec_prime_smoke_suite" / "environment.py").read_text(
        encoding="utf-8"
    )
    assert '"task_id": "electrical/voltage-drop-a"' in environment_py
    assert '"task_id": "electrical/voltage-drop-b"' in environment_py
    assert '"name": "prime-smoke-suite"' in environment_py
    assert '"version": "0.1.0"' in environment_py
    assert '"content_hash": "dataset-hash"' in environment_py


def test_prime_export_cli_rejects_dataset_with_task_filter(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)
    datasets_root = tmp_path / "datasets"
    _write_dataset_manifest(
        datasets_root,
        name="prime-smoke-suite",
        version="0.1.0",
        task_ids=["electrical/voltage-drop"],
    )

    result = runner.invoke(
        app,
        [
            "prime",
            "export",
            "--name",
            "aec-prime-smoke-suite",
            "--tasks-root",
            str(tasks_root),
            "--datasets-root",
            str(datasets_root),
            "--dataset",
            "prime-smoke-suite@0.1.0",
            "--task",
            "electrical/voltage-drop",
        ],
    )

    assert result.exit_code != 0
    assert "--dataset cannot be combined" in result.output


def test_prime_export_cli_defaults_to_repo_prime_rl_directory(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)
    run_root = tmp_path / "run"
    run_root.mkdir()

    with runner.isolated_filesystem(temp_dir=run_root):
        result = runner.invoke(
            app,
            [
                "prime",
                "export",
                "--name",
                "aec-electrical-smoke",
                "--tasks-root",
                str(tasks_root),
                "--task",
                "electrical/voltage-drop",
            ],
        )

        assert result.exit_code == 0
        assert (Path(DEFAULT_PRIME_ENVIRONMENTS_DIR) / "aec_electrical_smoke" / "pyproject.toml").exists()


def test_prime_doctor_reports_cli_and_verifiers(monkeypatch, tmp_path: Path) -> None:
    prime = tmp_path / "prime"
    prime.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--plain" ] && [ "$2" = "--version" ]; then echo \'prime 0.6.2\'; exit 0; fi\n'
        'if [ "$1" = "--plain" ] && [ "$2" = "whoami" ]; then echo \'Username  theo\'; exit 0; fi\n'
        "exit 1\n",
        encoding="utf-8",
    )
    prime.chmod(prime.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path))

    result = runner.invoke(app, ["--json", "prime", "doctor"])

    assert result.exit_code == 0
    assert '"check": "prime cli"' in result.output
    assert '"ok": true' in result.output


def test_prime_smoke_exports_and_loads_with_fake_prime(monkeypatch, tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)
    output_dir = tmp_path / "prime-envs"
    prime = tmp_path / "prime"
    prime.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    prime.chmod(prime.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "smoke",
            "--name",
            "aec-voltage-drop",
            "--task",
            "electrical/voltage-drop",
            "--tasks-root",
            str(tasks_root),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert '"environment_id": "aec_voltage_drop"' in result.output
    assert (output_dir / "aec_voltage_drop" / "aec_voltage_drop" / "environment.py").exists()


def test_prime_smoke_accepts_dataset_with_fake_prime(monkeypatch, tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root, "electrical/voltage-drop-a")
    _make_task(tasks_root, "electrical/voltage-drop-b")
    datasets_root = tmp_path / "datasets"
    _write_dataset_manifest(
        datasets_root,
        name="prime-smoke-suite",
        version="0.1.0",
        task_ids=["electrical/voltage-drop-a", "electrical/voltage-drop-b"],
    )
    output_dir = tmp_path / "prime-envs"
    prime = tmp_path / "prime"
    prime.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    prime.chmod(prime.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path))

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "smoke",
            "--name",
            "aec-prime-smoke-suite",
            "--dataset",
            "prime-smoke-suite@0.1.0",
            "--tasks-root",
            str(tasks_root),
            "--datasets-root",
            str(datasets_root),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert '"environment_id": "aec_prime_smoke_suite"' in result.output
    environment_py = (output_dir / "aec_prime_smoke_suite" / "aec_prime_smoke_suite" / "environment.py").read_text(
        encoding="utf-8"
    )
    assert '"task_id": "electrical/voltage-drop-a"' in environment_py
    assert '"task_id": "electrical/voltage-drop-b"' in environment_py


def test_prime_smoke_runs_eval_from_generated_package(monkeypatch, tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root)
    output_dir = tmp_path / "prime-envs"
    pwd_file = tmp_path / "prime-eval-pwd.txt"
    prime = tmp_path / "prime"
    prime.write_text(
        '#!/bin/sh\nif [ "$2" = "eval" ]; then pwd > "$PRIME_EVAL_PWD_FILE"; fi\nexit 0\n',
        encoding="utf-8",
    )
    prime.chmod(prime.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setenv("PRIME_EVAL_PWD_FILE", str(pwd_file))

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "smoke",
            "--name",
            "aec-voltage-drop",
            "--task",
            "electrical/voltage-drop",
            "--tasks-root",
            str(tasks_root),
            "--output-dir",
            str(output_dir),
            "--model",
            "openai/gpt-4.1-nano",
        ],
    )

    assert result.exit_code == 0
    assert pwd_file.read_text(encoding="utf-8").strip() == str(output_dir / "aec_voltage_drop")


def test_exported_environment_filters_training_tasks_by_difficulty(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    _make_task(tasks_root, "electrical/easy-a", difficulty="easy")
    _make_task(tasks_root, "electrical/easy-b", difficulty="easy")
    _make_task(tasks_root, "structural/hard-a", difficulty="hard")
    output_dir = tmp_path / "prime-envs"

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-difficulty-filter",
            tasks_root=tasks_root,
            output_dir=output_dir,
            task_ids=["electrical/easy-a", "electrical/easy-b", "structural/hard-a"],
        )
    )

    environment_py = result.package_dir / "aec_difficulty_filter" / "environment.py"
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(result.package_dir)!r})\n"
        "from aec_difficulty_filter.environment import load_environment\n"
        "env = load_environment(difficulty=['easy'], num_examples=1, seed=7)\n"
        "print(len(env.dataset))\n"
        "print(env.dataset[0]['answer'])\n"
        "eval_env = load_environment(split='eval', difficulty='hard')\n"
        "print(eval_env.dataset[0]['answer'])\n"
    )
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=result.package_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    lines = process.stdout.splitlines()
    assert lines == ["1", "electrical/easy-a", "structural/hard-a"]
    py_compile.compile(str(environment_py), doraise=True)


def test_exported_environment_uses_disjoint_train_and_eval_splits(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_ids = [f"electrical/task-{index}" for index in range(10)]
    for task_id in task_ids:
        _make_task(tasks_root, task_id, difficulty="easy")
    output_dir = tmp_path / "prime-envs"

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-split-filter",
            tasks_root=tasks_root,
            output_dir=output_dir,
            task_ids=task_ids,
        )
    )

    environment_py = result.package_dir / "aec_split_filter" / "environment.py"
    code = (
        "import sys\n"
        f"sys.path.insert(0, {str(result.package_dir)!r})\n"
        "from aec_split_filter.environment import load_environment\n"
        "train_env = load_environment(split='train', difficulty='easy', seed=7)\n"
        "eval_env = load_environment(split='eval', difficulty='easy', seed=7)\n"
        "train_ids = {row['answer'] for row in train_env.dataset}\n"
        "eval_ids = {row['answer'] for row in eval_env.dataset}\n"
        "print(len(train_ids))\n"
        "print(len(eval_ids))\n"
        "print(bool(train_ids & eval_ids))\n"
    )
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=result.package_dir,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.splitlines() == ["8", "2", "False"]
    py_compile.compile(str(environment_py), doraise=True)


def test_export_escapes_percent_literals_in_argparse_help(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root, "electrical/percent-help", difficulty="easy")
    environment_dir = task_dir / "environment"
    environment_dir.mkdir(exist_ok=True)
    helper = environment_dir / "percent_help.py"
    helper.write_text(
        "\n".join(
            [
                "# ABOUTME: Helper used to verify percent signs in argparse help.",
                "# ABOUTME: Exercises generated task tool help under Prime export.",
                "import argparse",
                "",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--uk', help='Transformer impedance (uk%) (%)')",
                "parser.parse_args()",
                "",
            ]
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "prime-envs"

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-percent-help",
            tasks_root=tasks_root,
            output_dir=output_dir,
            task_ids=["electrical/percent-help"],
        )
    )

    exported_helper = (
        result.package_dir
        / "aec_percent_help"
        / "tasks"
        / "electrical"
        / "percent-help"
        / "environment"
        / "percent_help.py"
    )
    process = subprocess.run(
        [sys.executable, str(exported_helper), "--help"],
        cwd=exported_helper.parent,
        capture_output=True,
        text=True,
        check=False,
    )

    assert process.returncode == 0, process.stderr
    assert "Transformer impedance (uk%) (%)" in process.stdout


def test_stateful_export_accepts_shell_commands_and_exposes_environment_tools(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = _make_task(tasks_root, "civil/tool-path", difficulty="easy")
    environment_dir = task_dir / "environment"
    environment_dir.mkdir(exist_ok=True)
    (environment_dir / "helper.py").write_text("print('helper-ok')\n", encoding="utf-8")
    output_dir = tmp_path / "prime-envs"

    result = export_prime_lab_environment(
        PrimeLabExportConfig(
            name="aec-tool-path",
            tasks_root=tasks_root,
            output_dir=output_dir,
            task_ids=["civil/tool-path"],
            harness_mode=PrimeExportHarnessMode.STATEFUL_WORKSPACE,
        )
    )

    code = (
        "import tempfile, sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(result.package_dir)!r})\n"
        "from aec_tool_path.environment import WorkspaceCommandSet, _expose_environment_files\n"
        "with tempfile.TemporaryDirectory() as temp_dir:\n"
        "    root = Path(temp_dir)\n"
        "    (root / 'environment').mkdir()\n"
        "    (root / 'environment' / 'helper.py').write_text(\"print('helper-ok')\\n\")\n"
        "    _expose_environment_files(root)\n"
        "    result = WorkspaceCommandSet(root).run_command('python3 /workspace/helper.py')\n"
        "    print(result.exit_code)\n"
        "    print(result.stdout.strip())\n"
    )
    process = subprocess.run(
        [sys.executable, "-c", code],
        cwd=result.package_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    environment_py = result.package_dir / "aec_tool_path" / "environment.py"
    source = environment_py.read_text(encoding="utf-8")

    assert process.returncode == 0, process.stderr
    assert process.stdout.splitlines() == ["0", "helper-ok"]
    assert "run_command command accepts either a JSON list of argv strings" in source
    py_compile.compile(str(environment_py), doraise=True)


def test_prime_push_exports_dataset_and_pushes_from_package(monkeypatch, tmp_path: Path) -> None:
    _prepare_dataset_project(tmp_path, ["electrical/voltage-drop"])
    output_dir = tmp_path / "prime-envs"
    calls: list[tuple[list[str], Path | None, bool]] = []

    def fake_run(command: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "push",
            "--name",
            "aec-prime-test",
            "--dataset",
            "suite@1.0.0",
            "--output-dir",
            str(output_dir),
            "--visibility",
            "PRIVATE",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            ["prime", "env", "push", "--visibility", "PRIVATE", "--plain"],
            output_dir / "aec_prime_test",
            True,
        )
    ]
    assert '"task_count": 1' in result.output


def test_prime_eval_hosted_pushes_and_runs_remote_environment(monkeypatch, tmp_path: Path) -> None:
    _prepare_dataset_project(tmp_path, ["electrical/voltage-drop"])
    output_dir = tmp_path / "prime-envs"
    calls: list[tuple[list[str], Path | None, bool]] = []

    def fake_run(command: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append((command, cwd, check))
        if command[:3] == ["prime", "env", "push"]:
            assert cwd is not None
            metadata_dir = cwd / ".prime"
            metadata_dir.mkdir()
            (metadata_dir / ".env-metadata.json").write_text(
                json.dumps({"owner": "gabriel-syme", "name": "aec_prime_50_suite"}),
                encoding="utf-8",
            )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "eval",
            "--name",
            "aec-prime-50-suite",
            "--dataset",
            "suite@1.0.0",
            "--output-dir",
            str(output_dir),
            "--model",
            "Qwen/Qwen3.5-4B",
            "--num-examples",
            "50",
            "--rollouts-per-example",
            "1",
            "--max-tokens",
            "4096",
            "--max-concurrent",
            "5",
            "--hosted",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0] == (
        ["prime", "env", "push", "--visibility", "PRIVATE", "--plain"],
        output_dir / "aec_prime_50_suite",
        True,
    )
    assert calls[1] == (
        [
            "prime",
            "--plain",
            "eval",
            "run",
            "gabriel-syme/aec_prime_50_suite",
            "--model",
            "Qwen/Qwen3.5-4B",
            "--num-examples",
            "50",
            "--rollouts-per-example",
            "1",
            "--max-tokens",
            "4096",
            "--max-concurrent",
            "5",
            "--hosted",
            "--timeout-minutes",
            "120",
            "--follow",
        ],
        output_dir / "aec_prime_50_suite",
        True,
    )
    assert '"environment": "gabriel-syme/aec_prime_50_suite"' in result.output


def test_prime_eval_passes_env_args_and_adapter_model(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[list[str], Path | None, bool]] = []

    def fake_run(command: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "eval",
            "--remote-env",
            "gabriel-syme/aec_prime_50_suite",
            "--model",
            "Qwen/Qwen3.5-4B",
            "--adapter-id",
            "uv124zgh7ttg3in94f7jzmv2",
            "--split",
            "eval",
            "--difficulty",
            "medium",
            "--harness",
            "stateful",
            "--env-num-examples",
            "10",
            "--seed",
            "20260509",
            "--env-arg",
            "source=adapter-smoke",
            "--num-examples",
            "5",
            "--rollouts-per-example",
            "3",
            "--max-tokens",
            "4096",
            "--eval-name",
            "aec-prime-50-adapter-medium-stateful",
            "--hosted",
            "--no-follow",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls == [
        (
            [
                "prime",
                "--plain",
                "eval",
                "run",
                "gabriel-syme/aec_prime_50_suite",
                "--model",
                "Qwen/Qwen3.5-4B:uv124zgh7ttg3in94f7jzmv2",
                "--env-args",
                (
                    '{"split": "eval", "difficulty": "medium", "harness": "stateful", '
                    '"num_examples": 10, "seed": 20260509, "source": "adapter-smoke"}'
                ),
                "--num-examples",
                "5",
                "--rollouts-per-example",
                "3",
                "--max-tokens",
                "4096",
                "--hosted",
                "--timeout-minutes",
                "120",
                "--eval-name",
                "aec-prime-50-adapter-medium-stateful",
            ],
            None,
            True,
        )
    ]
    assert '"model": "Qwen/Qwen3.5-4B:uv124zgh7ttg3in94f7jzmv2"' in result.output


def test_prime_eval_resolves_deployed_adapter_from_training_run(monkeypatch) -> None:
    calls: list[tuple[list[str], Path | None, bool]] = []
    deployments = {
        "models": [
            {
                "id": "checkpoint-only",
                "rft_run_id": "lo5ku8w86s9k7gayy5465cmu",
                "base_model": "Qwen/Qwen3.5-4B",
                "status": "UPLOADING",
                "deployment_status": "NOT_DEPLOYED",
                "deployable": True,
            },
            {
                "id": "uv124zgh7ttg3in94f7jzmv2",
                "rft_run_id": "lo5ku8w86s9k7gayy5465cmu",
                "base_model": "Qwen/Qwen3.5-4B",
                "status": "READY",
                "deployment_status": "DEPLOYED",
                "deployable": True,
            },
        ]
    }

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ):
        calls.append((command, cwd, check))
        if command[:5] == ["prime", "--plain", "deployments", "list", "--output"]:
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(deployments), stderr="")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "eval",
            "--remote-env",
            "gabriel-syme/aec_prime_50_suite",
            "--model",
            "Qwen/Qwen3.5-4B",
            "--adapter-from-run",
            "lo5ku8w86s9k7gayy5465cmu",
            "--adapter-step",
            "latest",
            "--hosted",
            "--no-follow",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls[0][0] == ["prime", "--plain", "deployments", "list", "--output", "json"]
    assert calls[1][0][4:7] == [
        "gabriel-syme/aec_prime_50_suite",
        "--model",
        "Qwen/Qwen3.5-4B:uv124zgh7ttg3in94f7jzmv2",
    ]
    assert '"adapter_id": "uv124zgh7ttg3in94f7jzmv2"' in result.output


def test_prime_adapters_lists_prime_deployments(monkeypatch) -> None:
    calls: list[list[str]] = []
    deployments = {
        "models": [
            {
                "id": "uv124zgh7ttg3in94f7jzmv2",
                "display_name": "aec_prime_50--qwen3.5-4b--lo5ku8",
                "rft_run_id": "lo5ku8w86s9k7gayy5465cmu",
                "base_model": "Qwen/Qwen3.5-4B",
                "step": None,
                "status": "READY",
                "deployment_status": "DEPLOYED",
                "deployable": True,
            }
        ]
    }

    def fake_run(
        command: list[str],
        *,
        cwd: Path | None = None,
        check: bool = False,
        capture_output: bool = False,
        text: bool = False,
    ):
        del cwd, check, capture_output, text
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(deployments), stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(app, ["--json", "prime", "adapters"])

    assert result.exit_code == 0, result.output
    assert calls == [["prime", "--plain", "deployments", "list", "--output", "json"]]
    assert '"id": "uv124zgh7ttg3in94f7jzmv2"' in result.output
    assert '"deployment_status": "DEPLOYED"' in result.output


def test_prime_train_config_writes_hosted_baby_qwen_config(tmp_path: Path) -> None:
    config_path = tmp_path / "configs" / "rl" / "aec-prime-50-suite.toml"

    result = runner.invoke(
        app,
        [
            "--json",
            "prime",
            "train-config",
            "--environment",
            "gabriel-syme/aec_prime_50_suite",
            "--output",
            str(config_path),
            "--model",
            "Qwen/Qwen3.5-0.8B",
            "--difficulty",
            "easy",
            "--difficulty",
            "medium",
            "--harness",
            "stateful",
            "--num-examples",
            "50",
            "--max-steps",
            "20",
            "--batch-size",
            "32",
            "--rollouts-per-example",
            "4",
            "--max-tokens",
            "2048",
            "--eval-interval",
            "10",
            "--eval-num-examples",
            "10",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert payload["model"] == "Qwen/Qwen3.5-0.8B"
    assert payload["max_steps"] == 20
    assert payload["batch_size"] == 32
    assert payload["rollouts_per_example"] == 4
    assert payload["sampling"]["max_tokens"] == 2048
    assert payload["env"][0]["id"] == "gabriel-syme/aec_prime_50_suite"
    assert payload["env"][0]["args"] == {
        "split": "train",
        "difficulty": ["easy", "medium"],
        "harness": "stateful",
        "num_examples": 50,
    }
    assert payload["eval"]["interval"] == 10
    assert payload["eval"]["num_examples"] == 10
    assert payload["eval"]["rollouts_per_example"] == 1
    assert payload["eval"]["eval_base_model"] is True
    assert payload["adapters"]["interval"] == 0
    assert payload["adapters"]["keep_last"] == 3


def test_prime_train_runs_hosted_training_config(monkeypatch, tmp_path: Path) -> None:
    config_path = tmp_path / "aec-train.toml"
    config_path.write_text('model = "Qwen/Qwen3.5-0.8B"\n', encoding="utf-8")
    calls: list[tuple[list[str], Path | None, bool]] = []

    def fake_run(command: list[str], *, cwd: Path | None = None, check: bool = False):
        calls.append((command, cwd, check))
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = runner.invoke(app, ["--json", "prime", "train", str(config_path)])

    assert result.exit_code == 0, result.output
    assert calls == [(["prime", "train", str(config_path), "--plain"], None, True)]
    assert '"config_path":' in result.output
