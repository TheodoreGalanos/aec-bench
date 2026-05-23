# ABOUTME: CLI config command for viewing and setting aec-bench configuration.
# ABOUTME: Manages persistent settings like tasks-root, ledger-root, and feedback-root.

import json
import time
from pathlib import Path

import typer

from aec_bench.cli.output import console, emit, print_error, print_success

app = typer.Typer(help="View and manage aec-bench configuration.")

CONFIG_DIR = Path.home() / ".config" / "aec-bench"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "tasks_root": "tasks",
    "ledger_root": "artefacts/ledger",
    "feedback_root": "artefacts/feedback",
    "jobs_root": "jobs",
    "datasets_root": "artefacts/datasets",
}


def _load_config() -> dict[str, str]:
    if CONFIG_FILE.exists():
        return {**DEFAULTS, **json.loads(CONFIG_FILE.read_text(encoding="utf-8"))}
    return dict(DEFAULTS)


def _save_config(config: dict[str, str]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    saved = {k: v for k, v in config.items() if k not in DEFAULTS or v != DEFAULTS[k]}
    CONFIG_FILE.write_text(json.dumps(saved, indent=2), encoding="utf-8")


@app.command("view")
def view() -> None:
    """Show current configuration.

    Returns: settings map, each key with value and source (config or default).
    Known keys: tasks_root, ledger_root, feedback_root, jobs_root, datasets_root.

    Examples:
      aec-bench config view
      aec-bench config view --json | jq '.data.settings.tasks_root'
    """
    start = time.monotonic()
    config = _load_config()

    # Annotate each key with its source for the human renderer
    saved: dict[str, str] = {}
    if CONFIG_FILE.exists():
        saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))

    data = {
        "settings": {
            key: {"value": value, "source": "config" if key in saved else "default"}
            for key, value in sorted(config.items())
        }
    }

    def _render(d: dict) -> None:
        from rich.table import Table

        table = Table(title="aec-bench configuration")
        table.add_column("Setting", style="bold")
        table.add_column("Value")
        table.add_column("Source", style="dim")

        for key, info in d["settings"].items():
            table.add_row(key, info["value"], info["source"])

        console.print(table)

    emit("config view", data, start_time=start, human_renderer=_render)


@app.command("set")
def set_value(
    key: str = typer.Argument(help="Configuration key (e.g., tasks-root, ledger-root)"),
    value: str = typer.Argument(help="Value to set"),
) -> None:
    """Set a configuration value."""
    normalized_key = key.replace("-", "_")
    known_keys = set(DEFAULTS.keys())

    if normalized_key not in known_keys:
        print_error(f"unknown config key: {key}")
        print_error(f"known keys: {', '.join(sorted(known_keys))}")
        raise typer.Exit(1)

    config = _load_config()
    config[normalized_key] = value
    _save_config(config)
    print_success(f"{normalized_key} = {value}")


@app.command("reset")
def reset(
    key: str | None = typer.Argument(None, help="Key to reset (omit to reset all)"),
) -> None:
    """Reset configuration to defaults."""
    if key is not None:
        normalized_key = key.replace("-", "_")
        config = _load_config()
        if normalized_key in config and normalized_key in DEFAULTS:
            config[normalized_key] = DEFAULTS[normalized_key]
            _save_config(config)
            print_success(f"reset {normalized_key} to default: {DEFAULTS[normalized_key]}")
        else:
            print_error(f"unknown config key: {key}")
            raise typer.Exit(1)
    else:
        if CONFIG_FILE.exists():
            CONFIG_FILE.unlink()
        print_success("all configuration reset to defaults")


def resolve_path(key: str, *, cli_override: str | None = None) -> Path:
    """Resolve a config path: CLI override > project TOML > global JSON > default."""
    if cli_override is not None:
        return Path(cli_override).resolve()
    from aec_bench.config import load_config

    config = load_config()
    value = getattr(config, key, None)
    if value is not None and isinstance(value, Path):
        return value.resolve()
    return Path(DEFAULTS.get(key, ".")).resolve()
