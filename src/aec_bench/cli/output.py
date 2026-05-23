# ABOUTME: Shared output infrastructure for the aec-bench CLI.
# ABOUTME: CLIResult envelope, emit() for JSON vs human output, and helpers.

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from aec_bench import __version__

console = Console()
error_console = Console(stderr=True)


@dataclass(frozen=True)
class CLIResult:
    """Consistent JSON envelope for all data-returning CLI commands."""

    command: str
    status: Literal["success", "partial", "error"]
    data: dict[str, Any] | list[dict[str, Any]] | None
    errors: list[str]
    version: str
    duration_seconds: float

    @staticmethod
    def build(
        *,
        command: str,
        data: dict[str, Any] | list[dict[str, Any]] | None,
        errors: list[str] | None = None,
        start_time: float | None = None,
    ) -> CLIResult:
        """Factory that derives status from data and errors."""
        errors = errors or []
        duration = (time.monotonic() - start_time) if start_time is not None else 0.0

        if data is None:
            status: Literal["success", "partial", "error"] = "error"
        elif errors:
            status = "partial"
        else:
            status = "success"

        return CLIResult(
            command=command,
            status=status,
            data=data,
            errors=errors,
            version=__version__,
            duration_seconds=duration,
        )

    @property
    def exit_code(self) -> int:
        """Map status to process exit code."""
        if self.status == "success":
            return 0
        if self.status == "error":
            return 1
        return 2  # partial

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a plain dict suitable for JSON encoding."""
        return {
            "command": self.command,
            "status": self.status,
            "data": self.data,
            "errors": self.errors,
            "version": self.version,
            "duration_seconds": self.duration_seconds,
        }


def is_tty() -> bool:
    """Return True when stdout is connected to an interactive terminal."""
    return sys.stdout.isatty()


def _should_emit_json() -> bool:
    """Decide whether output should be JSON.

    Priority: --json flag > --text flag > TTY auto-detection.
    Uses click.get_current_context(silent=True) so it works both inside
    and outside a Typer/Click command invocation.
    """
    import click

    ctx = click.get_current_context(silent=True)
    if ctx is not None:
        obj = ctx.find_root().ensure_object(dict)
        if obj.get("force_json"):
            return True
        if obj.get("force_text"):
            return False
    return not is_tty()


def emit(
    command: str,
    data: Any,
    *,
    errors: list[str] | None = None,
    start_time: float | None = None,
    human_renderer: Callable[[Any], None] | None = None,
) -> None:
    """Centralised output function for all data-returning CLI commands.

    In JSON mode (piped or --json): builds a CLIResult envelope and prints
    it as raw JSON to stdout — no ANSI codes, safe for parsing.

    In human mode (TTY or --text): calls *human_renderer* if provided,
    otherwise falls back to Rich syntax-highlighted JSON.

    Raises ``typer.Exit`` for non-zero exit codes (error=1, partial=2).
    """
    result = CLIResult.build(
        command=command,
        data=data,
        errors=errors,
        start_time=start_time,
    )

    if _should_emit_json():
        print(json.dumps(result.to_dict(), default=str))
    elif human_renderer is not None:
        human_renderer(data)
    else:
        rendered = json.dumps(result.to_dict(), indent=2, default=str)
        syntax = Syntax(rendered, "json", theme="monokai")
        console.print(syntax)

    if result.exit_code != 0:
        raise typer.Exit(code=result.exit_code)


def print_table(title: str, columns: list[str], rows: list[list[str]]) -> None:
    """Print a Rich table for human consumption."""
    table = Table(title=title)
    for col in columns:
        table.add_column(col)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[green]{message}[/green]")


def print_error(message: str) -> None:
    """Print an error message to stderr."""
    error_console.print(f"[red]Error:[/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message to stderr."""
    error_console.print(f"[yellow]Warning:[/yellow] {message}")


@dataclass(frozen=True)
class StructuredError:
    """CLI error with actionable remediation guidance.

    Fields::

        message   — what happened
        why       — why it happened (optional)
        fix       — how to fix it (optional)
        try_steps — copy-pasteable commands to try (optional)
    """

    message: str
    why: str | None = None
    fix: str | None = None
    try_steps: list[str] | None = None

    def __post_init__(self) -> None:
        if self.try_steps is None:
            object.__setattr__(self, "try_steps", [])

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a dict, omitting None/empty fields."""
        d: dict[str, Any] = {"message": self.message}
        if self.why:
            d["why"] = self.why
        if self.fix:
            d["fix"] = self.fix
        if self.try_steps:
            d["try_steps"] = self.try_steps
        return d

    def render(self) -> str:
        """Render as a human-readable multi-line string."""
        lines = [f"Error: {self.message}"]
        if self.why:
            lines.append(f"  Why: {self.why}")
        if self.fix:
            lines.append(f"  Fix: {self.fix}")
        if self.try_steps:
            lines.append("  Try:")
            for step in self.try_steps:
                lines.append(f"    $ {step}")
        return "\n".join(lines)

    def print(self) -> None:
        """Print the error using rich formatting to stderr."""
        from rich.panel import Panel
        from rich.text import Text

        content = Text()
        content.append(self.message, style="bold red")
        if self.why:
            content.append("\n\nWhy: ", style="bold")
            content.append(self.why)
        if self.fix:
            content.append("\n\nFix: ", style="bold")
            content.append(self.fix)
        if self.try_steps:
            content.append("\n\nTry:", style="bold")
            for step in self.try_steps:
                content.append(f"\n  $ {step}", style="dim")

        error_console.print(Panel(content, title="Error", border_style="red"))
