# ABOUTME: CLI command that launches the aec-bench web UI server.
# ABOUTME: Starts a uvicorn server serving the FastAPI web application, with optional Vite dev mode.

import signal
import subprocess
import sys
import webbrowser
from importlib.util import find_spec
from pathlib import Path
from secrets import token_urlsafe

import typer

from aec_bench.cli.commands.config import resolve_path

_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _ensure_webui_runtime() -> None:
    missing = [name for name in ("fastapi", "uvicorn") if find_spec(name) is None]
    if not missing:
        return
    packages = ", ".join(missing)
    typer.echo(
        "The web UI runtime is optional and is not installed "
        f"(missing: {packages}). Install it with 'aec-bench[webui]' "
        "or run 'uv sync --extra webui'.",
        err=True,
    )
    raise typer.Exit(1)


def _resolve_internal_token(host: str, internal_token: str | None) -> str | None:
    if internal_token is not None:
        return internal_token
    if host in _LOOPBACK_HOSTS:
        return token_urlsafe(32)
    return None


def _start_dev_servers(host: str, port: int) -> None:
    """Start Vite dev server and FastAPI in parallel for development."""
    _ensure_webui_runtime()
    frontend_dir = Path(__file__).resolve().parents[2] / "web" / "frontend"

    if not (frontend_dir / "package.json").exists():
        typer.echo("Frontend not found at " + str(frontend_dir))
        typer.echo("Run 'npm install' in src/aec_bench/web/frontend/ first.")
        raise typer.Exit(1)

    vite_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    uvicorn_proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "aec_bench.web.app:create_app",
            "--factory",
            "--host",
            host,
            "--port",
            str(port),
            "--reload",
        ],
        stdout=sys.stdout,
        stderr=sys.stderr,
    )

    def shutdown(signum: int, frame: object) -> None:
        vite_proc.terminate()
        uvicorn_proc.terminate()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    typer.echo("\n  Vite dev:  http://localhost:5173")
    typer.echo(f"  FastAPI:   http://{host}:{port}")
    typer.echo("  Open Vite URL for development with HMR\n")

    try:
        vite_proc.wait()
        uvicorn_proc.wait()
    except KeyboardInterrupt:
        vite_proc.terminate()
        uvicorn_proc.terminate()


def launch_web(
    port: int = typer.Option(8710, "--port", "-p", help="Port to serve on"),
    host: str = typer.Option("127.0.0.1", "--host", help="Host to bind to"),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
    tasks_root: str | None = typer.Option(None, "--tasks-root", help="Tasks directory"),
    feedback_root: str | None = typer.Option(None, "--feedback-root", help="Feedback directory"),
    datasets_root: str | None = typer.Option(None, "--datasets-root", help="Datasets directory"),
    internal_token: str | None = typer.Option(
        None,
        "--internal-token",
        envvar="AEC_BENCH_INTERNAL_TOKEN",
        help="Token for internal routes (or set AEC_BENCH_INTERNAL_TOKEN)",
    ),
    workspaces_root: str | None = typer.Option(None, "--workspaces-root", help="Evolution workspaces directory"),
    no_open: bool = typer.Option(False, "--no-open", help="Don't open browser automatically"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    dev: bool = typer.Option(False, "--dev", help="Run Vite dev server + FastAPI for HMR development"),
) -> None:
    """Launch the web UI for browsing experiments, triaging trials, and viewing results."""
    _ensure_webui_runtime()
    if dev:
        _start_dev_servers(host=host, port=port)
        return

    import uvicorn

    from aec_bench.web.app import create_app

    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)
    resolved_tasks = resolve_path("tasks_root", cli_override=tasks_root)
    resolved_feedback = resolve_path("feedback_root", cli_override=feedback_root)
    resolved_datasets = resolve_path("datasets_root", cli_override=datasets_root)

    # Resolve workspaces root: CLI override, or workspaces/ in cwd if it exists
    resolved_workspaces: Path | None = None
    if workspaces_root:
        resolved_workspaces = Path(workspaces_root).resolve()
    else:
        candidate = Path.cwd() / "workspaces"
        if candidate.is_dir():
            resolved_workspaces = candidate

    resolved_internal_token = _resolve_internal_token(host=host, internal_token=internal_token)

    app = create_app(
        ledger_root=resolved_ledger,
        tasks_root=resolved_tasks,
        feedback_root=resolved_feedback,
        datasets_root=resolved_datasets,
        internal_token=resolved_internal_token,
        workspaces_root=resolved_workspaces,
    )

    url = f"http://{host}:{port}"
    typer.echo(f"Starting aec-bench web UI at {url}")
    typer.echo(f"  Ledger:   {resolved_ledger}")
    typer.echo(f"  Tasks:    {resolved_tasks}")
    typer.echo(f"  Feedback: {resolved_feedback}")
    if resolved_workspaces:
        typer.echo(f"  Workspaces: {resolved_workspaces}")
    if resolved_internal_token and internal_token is None:
        typer.echo("  Internal review routes: enabled for this local browser session")

    if not no_open:
        webbrowser.open(url)

    uvicorn.run(app, host=host, port=port, log_level="info")
