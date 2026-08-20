# ABOUTME: Proves CLI feature extras stay optional and report one exact installation command.
# ABOUTME: Protects provider-free CLI startup without translating defects inside installed packages.

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from importlib.util import find_spec
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from aec_bench.adapters.deepseek_harness.config import DEEPSEEK_HARNESS_VERSION
from aec_bench.cli import optional_dependencies
from aec_bench.cli.main import app
from aec_bench.providers import morph_cloud

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
OPTIONAL_IMPORT_ROOTS = {
    "PIL",
    "acp",
    "deepseek_harness",
    "fastapi",
    "harbor",
    "jsonschema",
    "morphcloud",
    "numpy",
    "pydantic_ai",
    "ribs",
    "rich_pixels",
    "textual",
    "uvicorn",
    "verifiers",
}


def _requirement_names(requirements: list[str]) -> set[str]:
    return {re.split(r"[<=>\[; ]", requirement, maxsplit=1)[0].lower() for requirement in requirements}


def test_dependency_groups_have_one_named_feature_owner() -> None:
    project = tomllib.loads((REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert _requirement_names(project["dependencies"]) == {
        "click",
        "jinja2",
        "pydantic",
        "python-dotenv",
        "pyyaml",
        "rich",
        "typer",
        "zstandard",
    }
    extras = {name: _requirement_names(requirements) for name, requirements in project["optional-dependencies"].items()}
    assert extras == {
        "execution": {"harbor"},
        "deepseek-harness": {"deepseek-harness-sdk", "jsonschema"},
        "morph": {"morphcloud"},
        "local-agents": {"boto3", "botocore", "httpx", "pydantic-ai"},
        "prime": {"packaging", "prime", "verifiers"},
        "webui": {"fastapi", "starlette", "uvicorn"},
        "tui": {"pillow", "rich-pixels", "textual"},
        "evolution": {"numpy", "ribs"},
        "prime-agent": {"agent-client-protocol"},
    }
    assert project["optional-dependencies"]["execution"] == ["harbor[modal]>=0.15,<0.16"]
    assert project["optional-dependencies"]["deepseek-harness"] == [
        f"deepseek-harness-sdk=={DEEPSEEK_HARNESS_VERSION}",
        "jsonschema>=4.26,<5",
    ]


def test_cli_startup_does_not_import_optional_feature_families() -> None:
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, sys; import aec_bench.cli.main; "
                f"roots={OPTIONAL_IMPORT_ROOTS!r}; "
                "print(json.dumps(sorted(roots & {name.split('.')[0] for name in sys.modules})))"
            ),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(probe.stdout) == []


def test_missing_extra_reports_the_exact_install_command(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(optional_dependencies, "find_spec", lambda _module: None)

    with pytest.raises(typer.Exit) as error:
        optional_dependencies.require_optional_extra("Harbor execution support", "execution", ("harbor",))

    assert error.value.exit_code == 1
    assert capsys.readouterr().err == (
        'Harbor execution support is not installed.\nInstall it with: pip install "aec-bench[execution]"\n'
    )


def test_extra_check_does_not_import_an_available_module(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    marker = tmp_path / "imported"
    (tmp_path / "optional_probe.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    optional_dependencies.require_optional_extra("Probe support", "probe", ("optional_probe",))

    assert not marker.exists()


def test_run_dry_run_reports_missing_execution_extra_before_importing_harbor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = tasks_root / "electrical" / "demo"
    (task_dir / "tests").mkdir(parents=True)
    (task_dir / "instruction.md").write_text("Write the answer.\n", encoding="utf-8")
    (task_dir / "task.toml").write_text(
        '[metadata]\nvisibility = "public"\n\n[agent]\ntimeout_sec = 60\n',
        encoding="utf-8",
    )
    (task_dir / "tests" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    monkeypatch.setattr(
        optional_dependencies,
        "find_spec",
        lambda module: None if module == "harbor" else find_spec(module),
    )

    result = CliRunner().invoke(
        app,
        [
            "run",
            str(task_dir),
            "--model",
            "test-model",
            "--tasks-root",
            str(tasks_root),
            "--dry-run",
        ],
    )

    assert result.exit_code == 1
    assert 'Install it with: pip install "aec-bench[execution]"' in result.output


def test_installed_morph_import_failure_is_not_relabelled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = tmp_path / "morphcloud"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "api.py").write_text("import broken_morph_dependency\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(morph_cloud, "find_spec", lambda _module: object())
    for name in tuple(sys.modules):
        if name == "morphcloud" or name.startswith("morphcloud."):
            monkeypatch.delitem(sys.modules, name)

    with pytest.raises(ModuleNotFoundError) as error:
        morph_cloud._morph_client()

    assert error.value.name == "broken_morph_dependency"
