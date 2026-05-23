# ABOUTME: Persistent Python REPL engine for RLM adapter execution.
# ABOUTME: Manages code parsing, exec-based execution, output truncation, and variable state.

from __future__ import annotations

import io
import re
import sys
import traceback
from dataclasses import dataclass, field
from typing import Any


def parse_code_block(model_output: str) -> str | None:
    """Extract the last ```repl code block from model output.

    Only matches ```repl blocks. Returns the last one if multiple exist.
    For backward compatibility — prefer parse_code_blocks() for new code.
    """
    blocks = parse_code_blocks(model_output)
    return blocks[-1] if blocks else None


def parse_code_blocks(model_output: str) -> list[str]:
    """Extract ALL ```repl code blocks from model output.

    Only matches ```repl blocks — ignores ```python, ```json, bare ```,
    and any other fenced blocks. Returns them in order of appearance.
    This is the core RLM contract: only ```repl is executable.
    """
    pattern = r"```repl\s*\n(.*?)\n```"
    return [m.strip() for m in re.findall(pattern, model_output, re.DOTALL)]


def truncate_after_first_block(model_output: str) -> str:
    """Return text up to and including the first ```repl block's closing fence.

    Simulates tool_use stop behaviour: the model is treated as if it stopped
    generating after the first code block. Any subsequent blocks are discarded
    from the conversation history so the model can re-plan after seeing results.
    """
    match = re.search(r"```repl\s*\n.*?\n```", model_output, re.DOTALL)
    if match is None:
        return model_output
    return model_output[: match.end()]


@dataclass(frozen=True)
class ExecutionResult:
    """Result of executing a code block in the REPL."""

    stdout: str
    error: str | None = None
    variables_changed: list[str] = field(default_factory=list)


class ReplEnvironment:
    """Persistent Python execution environment for RLM agents.

    Uses exec() with a shared globals dict. Variables persist across
    executions. Output is captured and truncated to force symbolic
    manipulation.
    """

    def __init__(self, max_output_chars: int = 2000) -> None:
        self._globals: dict[str, Any] = {"__builtins__": __builtins__}
        self._max_output_chars = max_output_chars
        self._user_vars: set[str] = set()
        self._protected_vars: set[str] = set()
        self.final_value: Any = None
        self.final_called: bool = False

    def execute(self, code: str) -> ExecutionResult:
        """Execute a code block and return captured output."""
        stdout_capture = io.StringIO()
        old_stdout = sys.stdout
        vars_before = set(self._globals.keys())

        try:
            sys.stdout = stdout_capture
            exec(code, self._globals)  # noqa: S102
            sys.stdout = old_stdout

            raw_output = stdout_capture.getvalue()
            vars_after = set(self._globals.keys())
            new_vars = list(vars_after - vars_before)
            self._user_vars.update(new_vars)

            stdout = self._truncate(raw_output)
            return ExecutionResult(stdout=stdout, variables_changed=new_vars)

        except Exception:
            sys.stdout = old_stdout
            error_text = traceback.format_exc()
            return ExecutionResult(
                stdout=stdout_capture.getvalue(),
                error=error_text,
            )

    def inject_variable(self, var_name: str, expression: str) -> None:
        """Inject a variable into the REPL by executing an assignment."""
        exec(f"{var_name} = {expression}", self._globals)  # noqa: S102
        self._user_vars.add(var_name)

    def inject_object(self, var_name: str, obj: Any, *, protected: bool = False) -> None:
        """Inject a Python object directly into the REPL namespace.

        If *protected* is True, the variable is excluded from
        ``list_variables()`` and ``snapshot_variables()``.  This is used
        for injected scaffolding functions (NOTE, RECALL, FINAL_VAR, etc.)
        that should not appear in the agent's variable summary.
        """
        self._globals[var_name] = obj
        self._user_vars.add(var_name)
        if protected:
            self._protected_vars.add(var_name)

    def list_variables(self) -> dict[str, str]:
        """Return user-defined variable names and their type names.

        Protected variables (injected scaffolding) are excluded.
        """
        return {
            name: type(self._globals[name]).__name__
            for name in self._user_vars
            if name in self._globals and name not in self._protected_vars
        }

    def get_variable(self, name: str) -> Any:
        """Retrieve a variable value from the REPL namespace."""
        return self._globals.get(name)

    def snapshot_variables(self, max_repr_len: int = 200) -> dict[str, Any]:
        """Snapshot all user variables with JSON-safe values.

        Returns a dict of variable name → serialisable value.
        Numbers, strings, bools, None are kept as-is.
        Dicts and lists are kept if JSON-serialisable.
        Everything else gets a truncated repr().
        Protected variables (injected scaffolding) are excluded.
        """
        snapshot: dict[str, Any] = {}
        for name in sorted(self._user_vars):
            if name not in self._globals or name in self._protected_vars:
                continue
            val = self._globals[name]
            snapshot[name] = _safe_serialize(val, max_repr_len)
        return snapshot

    def restore_protected(self, scaffolds: dict[str, Any]) -> None:
        """Restore protected objects after code execution.

        Prevents the agent from overwriting injected scaffolding
        functions (NOTE, RECALL, FINAL_VAR, etc.) by reassigning
        them from the provided dict.
        """
        for name, obj in scaffolds.items():
            self._globals[name] = obj

    def _truncate(self, text: str) -> str:
        if len(text) <= self._max_output_chars:
            return text
        return text[: self._max_output_chars] + "\n...[truncated]...\n"


def _safe_serialize(val: Any, max_repr_len: int = 200) -> Any:
    """Convert a Python value to a JSON-safe representation.

    Strings longer than *max_repr_len* are truncated with a character count.
    This prevents full document contents from bloating the variable snapshot
    that is appended to each tool result in the conversation.
    """
    if val is None or isinstance(val, bool | int | float):
        return val
    if isinstance(val, str):
        if len(val) <= max_repr_len:
            return val
        return f"{val[:max_repr_len]}... ({len(val):,} chars)"
    if isinstance(val, dict | list | tuple):
        try:
            import json as _json

            serialized = _json.dumps(val)
            if len(serialized) <= max_repr_len * 5:
                return list(val) if isinstance(val, tuple) else val
            return f"{type(val).__name__}({len(val)} items, {len(serialized):,} chars)"
        except (TypeError, ValueError, OverflowError):
            pass
    r = repr(val)
    if len(r) > max_repr_len:
        return r[:max_repr_len] + "..."
    return r
