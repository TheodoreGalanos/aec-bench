# ABOUTME: Provides a real local-filesystem Harbor environment for lifecycle integration tests.
# ABOUTME: Executes verifier commands in a task-scoped tree while recording phase boundaries.

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from harbor.environments.base import BaseEnvironment, ExecResult  # type: ignore[import-untyped]
from harbor.models.environment_type import EnvironmentType  # type: ignore[import-untyped]


class LocalFilesystemHarborEnvironment(BaseEnvironment):  # type: ignore[misc]
    """Run Harbor's lifecycle locally without pretending to provide container isolation."""

    @staticmethod
    def type() -> EnvironmentType:
        return EnvironmentType.DOCKER

    @property
    def is_mounted(self) -> bool:
        return False

    @property
    def supports_gpus(self) -> bool:
        return False

    @property
    def can_disable_internet(self) -> bool:
        return True

    @property
    def _root(self) -> Path:
        return Path(self.trial_paths.trial_dir) / "local-environment"

    @property
    def _audit_path(self) -> Path:
        return Path(self.trial_paths.trial_dir) / "environment-operations.jsonl"

    def _validate_definition(self) -> None:
        if not (self.environment_dir / "Dockerfile").is_file():
            raise FileNotFoundError(f"task environment Dockerfile is missing: {self.environment_dir}")

    async def start(self, force_build: bool) -> None:
        del force_build
        if self._root.exists():
            raise FileExistsError(f"local Harbor environment already exists: {self._root}")
        for relative in ("workspace", "logs/agent", "logs/verifier"):
            (self._root / relative).mkdir(parents=True, exist_ok=True)
        context = self.environment_dir / "context"
        if context.is_dir():
            shutil.copytree(context, self._root / "workspace" / "context")
        self._record("start", source=str(self.environment_dir), target=str(self._root))

    async def stop(self, delete: bool) -> None:
        self._record("stop", delete=delete)

    async def upload_file(self, source_path: Path | str, target_path: str) -> None:
        source = Path(source_path)
        target = self._remote_path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        self._record("upload_file", source=str(source), target=target_path)

    async def upload_dir(self, source_dir: Path | str, target_dir: str) -> None:
        source = Path(source_dir)
        target = self._remote_path(target_dir)
        if not source.is_dir():
            raise FileNotFoundError(f"upload source directory is missing: {source}")
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
        self._record("upload_dir", source=str(source), target=target_dir)

    async def download_file(self, source_path: str, target_path: Path | str) -> None:
        source = self._remote_path(source_path)
        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        self._record("download_file", source=source_path, target=str(target))

    async def download_dir(self, source_dir: str, target_dir: Path | str) -> None:
        source = self._remote_path(source_dir)
        target = Path(target_dir)
        if not source.is_dir():
            raise FileNotFoundError(f"remote directory is missing: {source_dir}")
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, target, dirs_exist_ok=True)
        self._record("download_dir", source=source_dir, target=str(target))

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout_sec: int | None = None,
    ) -> ExecResult:
        rewritten = self._rewrite_command(command)
        process_environment = dict(os.environ)
        process_environment.pop("PYTHONPATH", None)
        process_environment.update(env or {})
        process_environment.update(self._verifier_environment())
        working_directory = self._remote_path(cwd or "/workspace")
        self._record("exec", command=command, verifier_uploaded=(self._root / "tests").is_dir())
        process = await asyncio.create_subprocess_shell(
            rewritten,
            cwd=working_directory,
            env=process_environment,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            if timeout_sec is None:
                stdout, stderr = await process.communicate()
            else:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
        except TimeoutError:
            process.kill()
            await process.wait()
            raise
        return ExecResult(
            stdout=stdout.decode("utf-8", errors="replace"),
            stderr=stderr.decode("utf-8", errors="replace"),
            return_code=int(process.returncode or 0),
        )

    def _rewrite_command(self, command: str) -> str:
        rewritten = command
        for remote in ("/workspace", "/tests", "/logs", "/opt"):
            rewritten = rewritten.replace(remote, str(self._remote_path(remote)))
        return rewritten

    def _verifier_environment(self) -> dict[str, str]:
        tests = self._root / "tests"
        runtime_candidates = sorted((tests / "runtime").glob("*.whl")) if tests.is_dir() else []
        values = {
            "AEC_BENCH_COMPILED_WORLD_DIR": str(tests / "compiled-world"),
            "AEC_BENCH_LIFECYCLE_RUN_DIR": str(self._root / "workspace" / "lifecycle-run"),
            "AEC_BENCH_ENVELOPE_PATH": str(tests / "compiled-world-envelope.json"),
            "AEC_BENCH_EXPORT_MANIFEST": str(tests / "compiled-world-export.json"),
            "AEC_BENCH_INITIAL_CONTEXT_DIR": str(self._root / "workspace" / "context" / "initial"),
            "AEC_BENCH_REWARD_PATH": str(self._root / "logs" / "verifier" / "reward.json"),
            "AEC_BENCH_DETAILS_PATH": str(self._root / "logs" / "verifier" / "details.json"),
            "AEC_BENCH_PYTHON": sys.executable,
        }
        if runtime_candidates:
            values["AEC_BENCH_VERIFIER_RUNTIME"] = str(runtime_candidates[0])
        return values

    def _remote_path(self, raw_path: str) -> Path:
        path = PurePosixPath(raw_path)
        if not path.is_absolute() or ".." in path.parts:
            raise ValueError(f"local Harbor remote path must be absolute and confined: {raw_path}")
        if len(path.parts) < 2 or path.parts[1] not in {"workspace", "tests", "logs", "opt"}:
            raise ValueError(f"local Harbor remote path uses an unsupported root: {raw_path}")
        target = self._root.joinpath(*path.parts[1:])
        resolved_root = self._root.resolve()
        resolved_target = target.resolve()
        if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
            raise ValueError(f"local Harbor remote path escapes its task root: {raw_path}")
        return target

    def _record(self, event: str, **payload: Any) -> None:
        self._audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self._audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"event": event, **payload}, sort_keys=True) + "\n")
