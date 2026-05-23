# ABOUTME: Safe workspace command helpers for Prime stateful environment exports.
# ABOUTME: Provides path-contained file and subprocess primitives for generated tools.

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkspaceCommandResult:
    exit_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class WorkspaceCommandSet:
    root: Path
    max_output_chars: int = 20_000
    timeout_seconds: int = 30

    def read_file(self, path: str) -> str:
        return self._resolve(path).read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> str:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target.relative_to(self._root()).as_posix()

    def list_files(self, path: str = ".") -> list[str]:
        base = self._resolve(path)
        if base.is_file():
            return [base.relative_to(self._root()).as_posix()]
        return sorted(child.relative_to(self._root()).as_posix() for child in base.rglob("*") if child.is_file())

    def run_command(self, command: list[str], cwd: str | None = None) -> WorkspaceCommandResult:
        if not command:
            raise ValueError("command cannot be empty")
        run_cwd = self._resolve(cwd or ".")
        process = subprocess.run(
            command,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            timeout=self.timeout_seconds,
            check=False,
        )
        return WorkspaceCommandResult(
            exit_code=process.returncode,
            stdout=self._truncate(process.stdout),
            stderr=self._truncate(process.stderr),
        )

    def submit_answer(self, content: str, path: str = "output.md") -> str:
        return self.write_file(path, content)

    def _root(self) -> Path:
        root = self.root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve(self, path: str) -> Path:
        root = self._root()
        candidate = (root / _workspace_relative_path(path)).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path is outside workspace: {path}") from exc
        return candidate

    def _truncate(self, text: str) -> str:
        if len(text) <= self.max_output_chars:
            return text
        return text[: self.max_output_chars] + "\n...[truncated]"


def _workspace_relative_path(path: str) -> str:
    if path == "/workspace":
        return "."
    if path.startswith("/workspace/"):
        return path.removeprefix("/workspace/")
    return path
