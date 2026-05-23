# ABOUTME: Local diagnostics for the optional Prime Lab integration.
# ABOUTME: Checks Prime CLI, auth, verifiers availability, and generated env loading.

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PrimeCheck:
    name: str
    ok: bool
    detail: str


def run_prime_doctor(*, check_inference: bool = False) -> list[PrimeCheck]:
    """Run non-invasive checks for local Prime integration readiness."""
    checks = [
        _check_prime_cli(),
        _check_prime_auth(),
        _check_verifiers_import(),
    ]
    if check_inference:
        checks.append(_check_prime_inference())
    return checks


def load_generated_environment(package_dir: Path, env_id: str) -> PrimeCheck:
    """Verify the generated environment can be imported through verifiers."""
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = f"{package_dir}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else str(package_dir)
    code = (
        "from verifiers import load_environment\n"
        f"env = load_environment({env_id!r})\n"
        "print(type(env).__name__)\n"
        "print(len(env.dataset))\n"
    )
    result = _run([sys.executable, "-c", code], env=env, cwd=package_dir)
    if result.returncode == 0:
        detail = " ".join(line.strip() for line in result.stdout.splitlines() if line.strip())
        return PrimeCheck("load environment", True, detail)
    return PrimeCheck("load environment", False, _summarise_failure(result))


def install_generated_environment(output_dir: Path, env_id: str) -> PrimeCheck:
    """Install a locally generated environment package with Prime CLI."""
    result = _run(
        [
            "prime",
            "--plain",
            "env",
            "install",
            env_id,
            "--path",
            str(output_dir),
            "--no-upgrade",
        ]
    )
    if result.returncode == 0:
        return PrimeCheck("prime env install", True, f"installed {env_id}")
    return PrimeCheck("prime env install", False, _summarise_failure(result))


def run_prime_eval_smoke(
    *,
    env_id: str,
    model: str,
    endpoints_path: Path | None = None,
    cwd: Path | None = None,
    max_tokens: int = 2048,
) -> PrimeCheck:
    """Run a one-example Prime eval against an installed environment."""
    command = [
        "prime",
        "--plain",
        "eval",
        "run",
        env_id,
        "--model",
        model,
        "--num-examples",
        "1",
        "--rollouts-per-example",
        "1",
        "--max-tokens",
        str(max_tokens),
        "--timeout",
        "120",
        "--disable-tui",
        "--abbreviated-summary",
    ]
    if endpoints_path is not None:
        command.extend(["--endpoints-path", str(endpoints_path)])

    result = _run(command, cwd=cwd)
    if result.returncode == 0:
        return PrimeCheck("prime eval run", True, "one-example eval completed")
    return PrimeCheck("prime eval run", False, _summarise_failure(result))


def _check_prime_cli() -> PrimeCheck:
    if shutil.which("prime") is None:
        return PrimeCheck("prime cli", False, "prime executable not found on PATH")
    result = _run(["prime", "--plain", "--version"])
    if result.returncode == 0:
        return PrimeCheck("prime cli", True, result.stdout.strip() or "prime available")
    return PrimeCheck("prime cli", False, _summarise_failure(result))


def _check_prime_auth() -> PrimeCheck:
    if shutil.which("prime") is None:
        return PrimeCheck("prime auth", False, "prime executable not found on PATH")
    result = _run(["prime", "--plain", "whoami"])
    if result.returncode == 0:
        first_line = next((line.strip() for line in result.stdout.splitlines() if line.strip()), "")
        return PrimeCheck("prime auth", True, first_line or "authenticated")
    return PrimeCheck("prime auth", False, _summarise_failure(result))


def _check_verifiers_import() -> PrimeCheck:
    if importlib.util.find_spec("verifiers") is None:
        return PrimeCheck(
            "verifiers package",
            False,
            'install the optional extra with `pip install "aec-bench[prime]"`',
        )
    return PrimeCheck("verifiers package", True, "importable")


def _check_prime_inference() -> PrimeCheck:
    result = _run(["prime", "--plain", "inference", "models"])
    if result.returncode == 0:
        return PrimeCheck("prime inference", True, "models endpoint reachable")
    return PrimeCheck("prime inference", False, _summarise_failure(result))


def _run(
    command: list[str], *, env: dict[str, str] | None = None, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
            env=env,
            cwd=cwd,
        )
    except FileNotFoundError as exc:
        return subprocess.CompletedProcess(command, 127, "", str(exc))
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(command, 124, exc.stdout or "", exc.stderr or "timed out")


def _summarise_failure(result: subprocess.CompletedProcess[str]) -> str:
    text = (result.stderr or result.stdout or "").strip()
    if not text:
        return f"exit code {result.returncode}"
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else text
