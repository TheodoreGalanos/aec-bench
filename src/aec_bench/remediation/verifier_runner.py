# ABOUTME: Re-invokes a task verifier against a synthesised patched workspace.
# ABOUTME: Mirrors the /workspace layout and passes WORKSPACE via sys.argv.

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VerifierResult:
    reward: float
    details: dict


_COPY_DIRS = ("documents", "reference_data")
_COPY_FILES = ("report_template.toml", "validation_rules.toml")


def _copy_and_patch_verify_script(task_dir: Path, workspace: Path) -> Path:
    """Copy tests/verify.py into workspace and rewrite /workspace/ to workspace path.

    Report-style verifiers can hardcode `WORKSPACE = Path("/workspace")`
    at module level and ignore sys.argv[1]. Mirrors local_runtime.patch_workspace_paths
    so remediation can re-run the same verify.py against a temp workspace.
    """
    src = task_dir / "tests" / "verify.py"
    content = src.read_text(encoding="utf-8")
    normalised = str(workspace).rstrip("/")
    content = content.replace('"/workspace"', f'"{normalised}"')
    content = content.replace('"/workspace/', f'"{normalised}/')
    tests_dir = workspace / "tests"
    tests_dir.mkdir(exist_ok=True)
    dest = tests_dir / "verify.py"
    dest.write_text(content, encoding="utf-8")
    return dest


def _prepare_workspace(task_dir: Path, output_md_text: str, workspace: Path) -> Path:
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "logs" / "verifier").mkdir(parents=True, exist_ok=True)
    for name in _COPY_FILES:
        src = task_dir / name
        if src.exists():
            shutil.copy2(src, workspace / name)
    for name in _COPY_DIRS:
        src = task_dir / name
        if src.exists() and src.is_dir():
            dest = workspace / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
    (workspace / "output.md").write_text(output_md_text)
    return _copy_and_patch_verify_script(task_dir, workspace)


def run_verifier(
    *,
    task_dir: Path,
    output_md_text: str,
    workspace_root: Path,
) -> VerifierResult:
    """Run the task's verify.py against a synthesised workspace with output_md_text.

    task_dir: directory containing tests/verify.py, report_template.toml, documents/
    output_md_text: the output.md content to verify
    workspace_root: temp dir to use as the verifier's WORKSPACE (passed via sys.argv[1])
    """
    source_verify = task_dir / "tests" / "verify.py"
    if not source_verify.exists():
        msg = f"verify.py not found at {source_verify}"
        raise FileNotFoundError(msg)

    patched_verify = _prepare_workspace(task_dir, output_md_text, workspace_root)

    try:
        subprocess.run(
            [sys.executable, str(patched_verify), str(workspace_root)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        msg = f"verify.py exited with code {exc.returncode}\nstdout:\n{exc.stdout}\nstderr:\n{exc.stderr}"
        raise RuntimeError(msg) from exc

    reward_path = workspace_root / "logs" / "verifier" / "reward.json"
    details_path = workspace_root / "logs" / "verifier" / "details.json"
    reward = json.loads(reward_path.read_text())["reward"]
    details = json.loads(details_path.read_text()) if details_path.exists() else {}
    return VerifierResult(reward=float(reward), details=details)
