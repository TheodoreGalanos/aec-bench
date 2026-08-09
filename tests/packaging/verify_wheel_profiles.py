# ABOUTME: Installs the built wheel into isolated environments for each supported feature profile.
# ABOUTME: Proves the base CLI is provider-free and named extras contain their owned runtimes.

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
import venv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Profile:
    extras: str | None
    imports: tuple[str, ...]


PROFILES = {
    "base": Profile(None, ()),
    "execution": Profile("execution", ("harbor",)),
    "morph": Profile("execution,morph", ("harbor", "morphcloud.api")),
    "local-agents": Profile(
        "local-agents",
        ("boto3", "botocore", "httpx", "pydantic_ai.models.anthropic", "pydantic_ai.models.bedrock"),
    ),
    "prime": Profile("prime", ("verifiers",)),
    "prime-agent": Profile("prime-agent", ("acp",)),
    "webui": Profile("webui", ("fastapi", "starlette", "uvicorn")),
    "tui": Profile("tui", ("PIL", "rich_pixels", "textual")),
    "evolution": Profile("evolution,local-agents", ("numpy", "pydantic_ai", "ribs")),
    "combined": Profile(
        "execution,morph,local-agents,prime,prime-agent,webui,tui,evolution",
        (
            "PIL",
            "acp",
            "fastapi",
            "harbor",
            "morphcloud",
            "numpy",
            "pydantic_ai.models.anthropic",
            "pydantic_ai.models.bedrock",
            "ribs",
            "textual",
            "verifiers",
        ),
    ),
}
OPTIONAL_BASE_MODULES = (
    "PIL",
    "acp",
    "fastapi",
    "harbor",
    "morphcloud",
    "numpy",
    "pydantic_ai",
    "ribs",
    "rich_pixels",
    "textual",
    "uvicorn",
    "verifiers",
)


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    expected: str | tuple[str, ...] | None = None,
) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    expected_values = (expected,) if isinstance(expected, str) else expected or ()
    if result.returncode != 0 or any(value not in output for value in expected_values):
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{output}")


def _expect_failure(command: list[str], *, cwd: Path, env: dict[str, str], expected: str) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0 or expected not in output:
        raise RuntimeError(f"command did not fail as expected ({result.returncode}): {' '.join(command)}\n{output}")


def _python(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _command(env_dir: Path, name: str) -> Path:
    suffix = ".exe" if os.name == "nt" else ""
    return env_dir / ("Scripts" if os.name == "nt" else "bin") / f"{name}{suffix}"


def _wheel_requirement(wheel: Path, extras: str | None) -> str:
    if extras is None:
        return str(wheel)
    return f"aec-bench[{extras}] @ {wheel.as_uri()}"


def _verify_base(*, python: Path, cli: Path, work: Path, env: dict[str, str]) -> None:
    absent_probe = ";".join(
        (
            "import importlib.util",
            f"names={OPTIONAL_BASE_MODULES!r}",
            "missing=[name for name in names if importlib.util.find_spec(name) is not None]",
            "assert not missing, missing",
            "import aec_bench, aec_bench.cli.main, aec_bench.providers",
        )
    )
    _run([str(python), "-I", "-c", absent_probe], cwd=work, env=env)
    _run(
        [str(cli), "--help"],
        cwd=work,
        env=env,
        expected=("evolve", "import", "prime", "run", "run-local", "swarm", "tui", "web"),
    )
    _run([str(cli), "--version"], cwd=work, env=env, expected="aec-bench 0.1.0")
    _run([str(cli), "config", "view"], cwd=work, env=env)
    _run([str(cli), "generate", "list-templates"], cwd=work, env=env, expected="a-weighting")
    _run(
        [
            str(cli),
            "generate",
            "task",
            "a-weighting",
            "--instances",
            "1",
            "--seed",
            "42",
            "--output",
            str(work / "generated"),
        ],
        cwd=work,
        env=env,
    )
    _run([str(cli), "library", "export", "--out", str(work / "library.json")], cwd=work, env=env)
    _run([str(cli), "dataset", "list", "--datasets-root", str(work / "datasets")], cwd=work, env=env)
    _run([str(cli), "ledger", "list", "--ledger-root", str(work / "ledger")], cwd=work, env=env)

    expected_errors = (
        (["web", "--no-open"], 'pip install "aec-bench[webui]"'),
        (["tui"], 'pip install "aec-bench[tui]"'),
        (["run-local", ".", "--model", "test"], 'pip install "aec-bench[local-agents]"'),
        (["run", ".", "--model", "test", "--dry-run"], 'pip install "aec-bench[execution]"'),
        (["import", "."], 'pip install "aec-bench[execution]"'),
        (["prime", "adapters"], 'pip install "aec-bench[prime]"'),
    )
    for args, expected in expected_errors:
        _expect_failure([str(cli), *args], cwd=work, env=env, expected=expected)

    pump_probe = ";".join(
        (
            "from aec_bench.worlds.stewardship.wastewater_pump_station.coupled_runtime import initial_state, observe",
            "state=initial_state()",
            "view=observe(state)",
            "assert view.calendar_seconds == state.calendar_seconds",
        )
    )
    _run([str(python), "-I", "-c", pump_probe], cwd=work, env=env)


def _verify_profile(
    *,
    name: str,
    profile: Profile,
    python: Path,
    cli: Path,
    work: Path,
    env: dict[str, str],
) -> None:
    imports = ";".join(f"import {module}" for module in profile.imports)
    _run([str(python), "-I", "-c", imports], cwd=work, env=env)
    if name == "prime":
        _run([str(_command(python.parents[1], "prime")), "--version"], cwd=work, env=env, expected="0.6.2")
    elif name == "webui":
        _run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "from pathlib import Path; from aec_bench.web.app import create_app; "
                    "app=create_app(ledger_root=Path('ledger'), tasks_root=Path('tasks')); assert app.routes"
                ),
            ],
            cwd=work,
            env=env,
        )
    elif name == "tui":
        _run(
            [
                str(python),
                "-I",
                "-c",
                (
                    "from pathlib import Path; from aec_bench.tui.app import AecBenchTUI; "
                    "app=AecBenchTUI(ledger_root=Path('ledger'), tasks_root=Path('tasks')); assert app"
                ),
            ],
            cwd=work,
            env=env,
        )
    elif name == "evolution":
        _run(
            [str(python), "-I", "-c", "from aec_bench.evolution.archive import CVTArchive; assert CVTArchive"],
            cwd=work,
            env=env,
        )


def verify(wheel: Path, profile_names: list[str]) -> None:
    clean_env = os.environ.copy()
    clean_env.pop("PYTHONPATH", None)
    clean_env.pop("VIRTUAL_ENV", None)
    for name in profile_names:
        profile = PROFILES[name]
        with tempfile.TemporaryDirectory(prefix=f"aec-bench-{name}-") as temp_dir:
            root = Path(temp_dir)
            env_dir = root / "venv"
            work = root / "work"
            work.mkdir()
            venv.EnvBuilder(with_pip=True).create(env_dir)
            python = _python(env_dir)
            cli = _command(env_dir, "aec-bench")
            _run(
                [
                    str(python),
                    "-m",
                    "pip",
                    "install",
                    "--disable-pip-version-check",
                    _wheel_requirement(wheel, profile.extras),
                ],
                cwd=work,
                env=clean_env,
            )
            _run([str(python), "-m", "pip", "check"], cwd=work, env=clean_env)
            if name == "base":
                _verify_base(python=python, cli=cli, work=work, env=clean_env)
            else:
                _verify_profile(name=name, profile=profile, python=python, cli=cli, work=work, env=clean_env)
        print(f"verified wheel profile: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--profile", action="append", choices=PROFILES, dest="profiles")
    args = parser.parse_args()
    wheel = args.wheel.resolve()
    if not wheel.is_file():
        parser.error(f"wheel not found: {wheel}")
    verify(wheel, args.profiles or list(PROFILES))


if __name__ == "__main__":
    main()
