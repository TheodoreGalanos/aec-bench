# ABOUTME: Context filter for RLM tool results — controls what goes into conversation history.
# ABOUTME: Applies threshold-based filtering driven by constitutional InformationMinimalityParams.

from __future__ import annotations

import re
from typing import Any

from aec_bench.contracts.constitution import InformationMinimalityParams

# Pattern that grep output starts with (see adapter.py _grep function).
_GREP_PATTERN = re.compile(r"^\d+ match\(es\) for /")


def _is_grep_output(stdout: str) -> bool:
    """Detect whether stdout looks like grep() output."""
    return bool(_GREP_PATTERN.match(stdout))


class ContextFilter:
    """Gatekeeper deciding what REPL output goes into conversation history.

    Parameterised by InformationMinimalityParams — the five-layer filtering
    thresholds become instance state so the constitutional inference engine
    can tune them per task.

    Rules:
    - Errors/tracebacks: bounded by the normal display threshold
    - grep() output: verbatim up to search_threshold, then truncated
    - Everything else: verbatim up to default_threshold, then metadata + preview
    """

    def __init__(self, params: InformationMinimalityParams) -> None:
        if min(params.default_threshold, params.search_threshold, params.preview_length) <= 0:
            raise ValueError("context display limits must be positive")
        if max(params.default_threshold, params.search_threshold, params.preview_length) > 1_000_000:
            raise ValueError("context display limits cannot exceed the REPL capture limit")
        if params.truncation_strategy not in {"metadata", "head", "tail"}:
            raise ValueError("unsupported truncation_strategy")
        self._params = params

    def _format_metadata(
        self,
        stdout: str,
        *,
        code: str,
        new_vars: list[str] | None = None,
        total_chars: int | None = None,
    ) -> str:
        total_chars = total_chars if total_chars is not None else len(stdout)
        preview = stdout[: self._params.preview_length].rstrip()

        parts: list[str] = []
        if new_vars:
            var_list = ", ".join(f"`{v}`" for v in new_vars)
            parts.append(f"Stored in {var_list}.")
        parts.append(f"Output: {total_chars:,} chars.")
        parts.append(f'Preview: "{preview}..."')
        parts.append("Use grep(variable, 'pattern') to search.")
        return "\n".join(parts)

    def build_context_message(
        self,
        *,
        stdout: str | None,
        error: str | None,
        code: str,
        new_vars: list[str] | None = None,
        stdout_chars: int | None = None,
        error_chars: int | None = None,
    ) -> str:
        """Build a context-safe message from REPL execution results."""
        if error:
            total_error = error_chars if error_chars is not None else len(error)
            if total_error > self._params.default_threshold:
                return f"{error[: self._params.default_threshold]}\n[Error truncated; {total_error:,} chars total]"
            return error
        if not stdout:
            return "(no output)"

        total_chars = stdout_chars if stdout_chars is not None else len(stdout)
        if _is_grep_output(stdout):
            if total_chars <= self._params.search_threshold:
                return stdout
            truncated = stdout[: self._params.search_threshold]
            remaining_chars = total_chars - len(truncated)
            return f"{truncated}\n...[truncated — {remaining_chars:,} more chars]..."

        if total_chars <= self._params.default_threshold:
            return stdout

        if self._params.truncation_strategy in {"head", "tail"}:
            text = (
                stdout[: self._params.default_threshold]
                if self._params.truncation_strategy == "head"
                else stdout[-self._params.default_threshold :]
            )
            capture_note = (
                "; tail of captured prefix"
                if len(stdout) < total_chars and self._params.truncation_strategy == "tail"
                else ""
            )
            return f"{text}\n[Truncated; {total_chars:,} chars total{capture_note}]"
        return self._format_metadata(stdout, code=code, new_vars=new_vars, total_chars=total_chars)

    def format_var_diff(
        self,
        *,
        new: list[str],
        removed: list[str],
        repl_vars: dict[str, Any],
    ) -> str:
        """Format a variable diff summary for the conversation context."""
        if not new and not removed:
            return ""

        parts: list[str] = []
        for name in new:
            val = repl_vars.get(name)
            if val is None:
                parts.append(f"  New: {name} (None)")
                continue
            type_name = type(val).__name__
            size_info = _describe_size(val)
            parts.append(f"  New: {name} ({type_name}, {size_info})")
        for name in removed:
            parts.append(f"  Removed: {name}")
        return "--- variables ---\n" + "\n".join(parts)


def _describe_size(val: Any) -> str:
    """Describe the size of a value in human-readable terms."""
    if isinstance(val, str):
        return f"{len(val):,} chars"
    if isinstance(val, list | tuple):
        return f"{len(val):,} items"
    if isinstance(val, dict):
        return f"{len(val):,} items"
    if isinstance(val, int | float):
        return str(val)
    return f"{len(repr(val)):,} chars repr"
