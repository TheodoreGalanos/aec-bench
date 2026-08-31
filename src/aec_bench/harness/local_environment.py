# ABOUTME: Host workspace and verifier execution for the run-local command.
# ABOUTME: Keeps local execution direct without a speculative environment interface.

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import cast

from aec_bench.adapters.base import AdapterRequest, AdapterResult
from aec_bench.harness.local_runtime import cleanup_workspace, patch_workspace_paths, setup_workspace


class HostEnvironment:
    """Run a task directly on the host Python process.

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
        execute = getattr(adapter, "execute", None)
        if not callable(execute):
            raise TypeError("local adapter must define a callable execute(request)")
        return cast(AdapterResult, execute(request))

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
            cleanup_workspace(self._workspace)
            self._workspace = None
