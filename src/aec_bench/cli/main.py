# ABOUTME: Main entrypoint for the aec-bench CLI.
# ABOUTME: Registers subcommand groups and provides the top-level typer app.

import typer

from aec_bench import __version__
from aec_bench.cli.commands.config import app as config_app
from aec_bench.cli.commands.dataset import app as dataset_app
from aec_bench.cli.commands.evaluate import evaluate_experiment
from aec_bench.cli.commands.evolve import app as evolve_app
from aec_bench.cli.commands.generate import app as generate_app
from aec_bench.cli.commands.import_job import import_job
from aec_bench.cli.commands.import_local import import_local_run
from aec_bench.cli.commands.import_prime_eval import import_prime_eval
from aec_bench.cli.commands.init import init_command
from aec_bench.cli.commands.ledger import app as ledger_app
from aec_bench.cli.commands.library import app as library_app
from aec_bench.cli.commands.prime import app as prime_app
from aec_bench.cli.commands.remediate import remediate
from aec_bench.cli.commands.report import app as report_app
from aec_bench.cli.commands.run import run_experiment
from aec_bench.cli.commands.run_local import run_local
from aec_bench.cli.commands.search import search_command
from aec_bench.cli.commands.swarm import app as swarm_app
from aec_bench.cli.commands.task import app as task_app
from aec_bench.cli.commands.tui_cmd import launch_tui
from aec_bench.cli.commands.web_cmd import launch_web

app = typer.Typer(
    name="aec-bench",
    help=f"AEC-Bench: Benchmark platform for AI agent evaluation (v{__version__})",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Single commands registered directly
app.command("init", rich_help_panel="Setup")(init_command)
app.command("run", rich_help_panel="Experiments")(run_experiment)
app.command("run-local", rich_help_panel="Experiments")(run_local)
app.command("import", rich_help_panel="Experiments")(import_job)
app.command("import-local", rich_help_panel="Experiments")(import_local_run)
app.command("import-prime-eval", rich_help_panel="Experiments")(import_prime_eval)
app.command("evaluate", rich_help_panel="Analysis")(evaluate_experiment)
app.command("remediate", rich_help_panel="Analysis")(remediate)
app.command("tui", rich_help_panel="Interactive")(launch_tui)
app.command("web", rich_help_panel="Interactive")(launch_web)
app.command("search", rich_help_panel="Discovery")(search_command)

# Subcommand groups
app.add_typer(report_app, name="report", rich_help_panel="Analysis")
app.add_typer(ledger_app, name="ledger", rich_help_panel="Analysis")
app.add_typer(config_app, name="config", rich_help_panel="Configuration")
app.add_typer(generate_app, name="generate", rich_help_panel="Generation")
app.add_typer(dataset_app, name="dataset", rich_help_panel="Datasets")
app.add_typer(evolve_app, name="evolve", rich_help_panel="Evolution")
app.add_typer(swarm_app, name="swarm", rich_help_panel="Evolution")
app.add_typer(task_app, name="task", rich_help_panel="Tasks")
app.add_typer(library_app, name="library", rich_help_panel="Library")
app.add_typer(prime_app, name="prime", rich_help_panel="Integrations")


@app.callback(invoke_without_command=True)
def callback(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-v", help="Show version and exit"),
    json_output: bool = typer.Option(False, "--json", help="Force JSON envelope output"),
    text_output: bool = typer.Option(False, "--text", help="Force human-readable output"),
) -> None:
    """AEC-Bench: Benchmark platform for evaluating AI agents on AEC engineering tasks.

    Output is JSON when piped, human-readable in terminal. Use --json or --text to override.
    """
    if json_output and text_output:
        from aec_bench.cli.output import print_error

        print_error("Cannot use --json and --text together")
        raise typer.Exit(1)
    ctx.ensure_object(dict)
    ctx.obj["force_json"] = json_output
    ctx.obj["force_text"] = text_output
    if version:
        typer.echo(f"aec-bench {__version__}")
        raise typer.Exit()


def run() -> None:
    """Entry point for the CLI.

    Loads .env from the project root (if present) so API keys and
    provider credentials are available to agents without requiring
    manual export in the shell.
    """
    from dotenv import load_dotenv

    load_dotenv()
    app()
