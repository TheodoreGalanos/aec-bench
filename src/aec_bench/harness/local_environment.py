# ABOUTME: LocalEnvironment protocol and default HostEnvironment for run-local execution.
# ABOUTME: Provides extensibility point for future sandbox backends (Pyodide, AgentOS).

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.harness.local_runtime import patch_workspace_paths, setup_workspace


class LocalEnvironment(Protocol):
    """Lightweight execution environment for local (non-container) runs.

    Distinct from Harbor's BaseEnvironment which handles full container
    lifecycle. This protocol covers workspace setup, adapter execution,
    verifier running, and cleanup.

    Future implementations: Pyodide, AgentOS, DockerLite.
    """

    def setup_workspace(self, task_dir: Path) -> str:
        """Prepare workspace from task directory, return workspace path."""
        ...

    def run_adapter(self, adapter: object, request: AdapterRequest) -> AdapterResult:
        """Execute the adapter in this environment."""
        ...

    def run_verifier(
        self,
        verifier_script: Path,
        output_path: Path,
        reward_path: Path,
    ) -> None:
        """Run the verification script."""
        ...

    def teardown(self, *, keep: bool = False) -> None:
        """Clean up the environment."""
        ...


class HostEnvironment:
    """Default LocalEnvironment that runs directly on the host Python process.

    Workspace setup uses the standard local_runtime helpers. Adapter execution
    is in-process. Verifier runs in a subprocess so its imports don't pollute
    the host environment.
    """

    def __init__(self) -> None:
        self._workspace: str | None = None

    def setup_workspace(self, task_dir: Path) -> str:
        """Copy task files into a temp workspace and patch /workspace/ paths."""
        workspace = setup_workspace(str(task_dir))
        patch_workspace_paths(workspace)
        self._workspace = workspace
        return workspace

    def run_adapter(self, adapter: object, request: AdapterRequest) -> AdapterResult:
        """Execute the adapter in-process by calling adapter.execute(request)."""
        return adapter.execute(request)  # type: ignore[attr-defined]

    def run_verifier(
        self,
        verifier_script: Path,
        output_path: Path,
        reward_path: Path,
    ) -> None:
        """Run the verifier script in a subprocess.

        Supports verify.py (run with sys.executable) and test.sh (run with bash).
        Creates the reward_path parent directory before running.
        """
        reward_path.parent.mkdir(parents=True, exist_ok=True)

        env_vars = None
        if self._workspace is not None:
            import os

            env_vars = {**os.environ, "PYTHONPATH": self._workspace}

        if verifier_script.suffix == ".py":
            cmd = [
                sys.executable,
                str(verifier_script),
                str(output_path),
                str(reward_path),
            ]
        else:
            cmd = ["bash", str(verifier_script), str(output_path), str(reward_path)]

        subprocess.run(cmd, check=True, env=env_vars)

    def teardown(self, *, keep: bool = False) -> None:
        """Remove the workspace directory unless keep=True."""
        if not keep and self._workspace is not None:
            shutil.rmtree(self._workspace, ignore_errors=True)
            self._workspace = None
