# ABOUTME: Local RLM execution without Docker, Modal, or Harbor.
# ABOUTME: Sets up workspace, runs adapter in-process, verifies output, and auto-imports to ledger.

from __future__ import annotations

import datetime
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from aec_bench.cli.optional_dependencies import require_optional_extra
from aec_bench.cli.output import StructuredError, console, emit
from aec_bench.contracts.experiment_manifest import AgentConfig, ComputeConfig
from aec_bench.contracts.run_plan import BestOfAttemptRecipe, SingleAttemptRecipe
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.harness.artifact.recipes import build_attempt_recipe
from aec_bench.harness.artifact_tasks import LocalTaskRuntime, run_trial, run_trial_with_verifier_feedback
from aec_bench.harness.model_execution.llm_reviewer import (
    ReviewerEndpointConfig,
    ReviewerRunConfig,
    load_reviewer_config,
)
from aec_bench.prime_agent.batch import PrimeExecutableNotFoundError, resolve_prime_executable
from aec_bench.tasks.instance import resolve_instance_paths
from aec_bench.tasks.loader import load_task_definition
from aec_bench.trials import PlannedTrial, build_trial_id

# Output files we expect the adapter to produce
_OUTPUT_FILES = [
    "output.md",
    "sections.json",
    "agent_result.json",
    ".scratchpad.json",
    "symbolic_state.json",
    "trajectory.jsonl",
    "conversation.jsonl",
    "model_reasoning.jsonl",
    "normalisation_report.json",
    "composition_trace.json",
    "grounding_report.json",
    "prime-events.jsonl",
    "prime-stderr.log",
    "prime-run.json",
]
_VERIFIER_SIDE_EFFECT_SUFFIXES = (
    "_record.json",
    "_decision.json",
    "_readback_check.json",
    "_notice.json",
    "_report.json",
    "_marker.json",
)
_VERIFIER_SIDE_EFFECT_EXCLUDED_PREFIXES = (
    "expected_",
    "input_",
    "prior_",
    "source_",
)


def _require_adapter_runtime(adapter: str) -> None:
    """Check only the runtime selected for this local execution."""
    if adapter == "deepseek_harness":
        require_optional_extra(
            "DeepSeek Harness execution support",
            "deepseek-harness",
            ("deepseek_harness",),
        )
        return
    if adapter == "prime-agent":
        try:
            resolve_prime_executable("prime-agent")
        except PrimeExecutableNotFoundError as exc:
            typer.echo(
                "Prime Agent executable was not found.\n"
                "Install Prime Agent separately: "
                "https://github.com/PrimeIntellect-ai/prime-agent#getting-started",
                err=True,
            )
            raise typer.Exit(1) from exc
        return
    require_optional_extra("Local agent execution support", "local-agents", ("pydantic_ai",))


def _copy_record_files(
    *,
    record: TrialRecord,
    artifact_root: Path,
    output_dir: Path,
    expected_output_path: str,
) -> list[str]:
    """Copy the retained command-facing artifacts from one materialized record."""

    output_dir.mkdir(parents=True, exist_ok=True)
    expected = Path(expected_output_path)
    if expected.is_absolute() and expected.parts[:2] == ("/", "workspace"):
        expected = Path(*expected.parts[2:])
    elif expected.parts and expected.parts[0] == "workspace":
        expected = Path(*expected.parts[1:])
    copied: list[str] = []
    for artifact in record.outputs.artifacts:
        logical = artifact.logical_path
        if artifact.role == "raw_output":
            destination = expected
        elif artifact.role in {"conversation", "trajectory"}:
            destination = Path(f"{artifact.role}.jsonl")
        elif logical is not None and _is_command_result_path(Path(logical), expected=expected):
            destination = Path(logical)
        else:
            continue
        source = artifact_root / artifact.artifact.artifact_id
        target = output_dir / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        relative = destination.as_posix()
        if relative not in copied:
            copied.append(relative)
    return copied


def _is_command_result_path(path: Path, *, expected: Path) -> bool:
    if path.as_posix() in _OUTPUT_FILES:
        return True
    if path.parts[:2] == ("logs", "verifier") or path.parts[:2] == ("logs", "reviewer"):
        return True
    if path.parts[:2] == ("logs", "prime") or path.parts[:2] == ("logs", "deepseek-harness"):
        return True
    if expected.parent != Path(".") and path.parent == expected.parent:
        return True
    return (
        path.parent == Path(".")
        and path.suffix == ".json"
        and path.name not in _OUTPUT_FILES
        and not path.name.startswith(_VERIFIER_SIDE_EFFECT_EXCLUDED_PREFIXES)
        and path.name.endswith(_VERIFIER_SIDE_EFFECT_SUFFIXES)
    )


def run_local(
    task_path: str = typer.Argument(help="Path to task directory"),
    model: str = typer.Option(..., "--model", "-m", help="Model name (e.g. us.anthropic.claude-sonnet-4-6)"),
    adapter: str = typer.Option(
        "rlm",
        "--adapter",
        "--harness",
        "-a",
        help=(
            "Agent harness: rlm, direct, tool_loop, pydantic_ai, lambda-rlm, "
            "prime-agent, deepseek_harness (default: rlm)"
        ),
    ),
    output_dir: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (default: task_path/_local_runs/<timestamp>)",
    ),
    timeout: int = typer.Option(1800, "--timeout", "-t", help="Timeout in seconds (default: 30 minutes)"),
    max_tokens: Annotated[
        int | None,
        typer.Option("--max-tokens", min=1, help="Maximum output tokens for adapters that support this limit"),
    ] = None,
    best_of_candidates: Annotated[
        int,
        typer.Option("--best-of", min=1, help="Run K independent candidates and select the first valid output"),
    ] = 1,
    selector: Annotated[
        str,
        typer.Option("--selector", help="Best-of selector (supported: self)"),
    ] = "self",
    keep_workspace: bool = typer.Option(False, "--keep-workspace", help="Don't delete temp workspace after run"),
    no_verify: Annotated[bool, typer.Option("--no-verify", help="Skip verifier execution after the agent run")] = False,
    no_import: Annotated[bool, typer.Option("--no-import", help="Skip auto-import of results into the ledger")] = False,
    no_normalise: Annotated[
        bool,
        typer.Option(
            "--no-normalise",
            help="Skip canonical-reference normalisation of agent output before verifier.",
        ),
    ] = False,
    constitutional_model: str | None = typer.Option(
        None,
        "--constitutional-model",
        help=(
            "Model for constitutional inference (overrides rlm.toml [constitution].model). "
            "Only used when rlm.toml has a [constitution] section."
        ),
    ),
    reviewer: bool = typer.Option(False, "--reviewer", help="Run the post-verifier LLM reviewer stage"),
    reviewer_model: str | None = typer.Option(None, "--reviewer-model", help="Single reviewer model name"),
    reviewer_models_config: Path | None = typer.Option(
        None,
        "--reviewer-models-config",
        help="JSON/YAML reviewer model endpoint config",
    ),
    fail_on_reviewer_error: bool = typer.Option(
        False,
        "--fail-on-reviewer-error",
        help="Fail the run when the reviewer stage cannot complete",
    ),
) -> None:
    """Run a task locally without Docker or Harbor.

    Sets up a temp workspace, copies task files, and runs the adapter
    through the selected adapter. Most built-in adapters use pydantic-ai;
    prime-agent launches the separately installed upstream executable;
    deepseek_harness launches the qualified official Harness runtime.

    Examples:
      aec-bench run-local tasks/electrical/voltage-drop -m gpt-4.1-mini --adapter direct
      aec-bench run-local tasks/electrical/voltage-drop -m anthropic/model-id --adapter prime-agent
      aec-bench run-local tasks/electrical/voltage-drop -m azure:deployment --adapter deepseek_harness
    """
    if selector != "self":
        raise typer.BadParameter("--selector must be 'self'")
    _require_adapter_runtime(adapter)
    task_dir = Path(task_path).resolve()
    if not task_dir.is_dir():
        StructuredError(
            message=f"Task directory not found: {task_dir}",
            why="The path does not exist or is not a directory",
            fix="Check the path and try again",
            try_steps=[
                "ls tasks/",
                "aec-bench task list",
            ],
        ).print()
        raise typer.Exit(1)
    from aec_bench.cli.commands.config import resolve_path
    from aec_bench.harness.local_import import find_tasks_root
    from aec_bench.ledger.writer import write_trial_record

    tasks_root = find_tasks_root(task_dir)
    task = load_task_definition(task_dir, tasks_root)
    resolved_task = resolve_instance_paths(task, task_dir)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = Path(output_dir) if output_dir else task_dir / "_local_runs" / timestamp
    ledger_root = resolve_path("ledger_root")
    artifact_root = ledger_root / "_artifacts" if not no_import else out_path / "_artifacts"
    parameters = {"max_tokens": max_tokens} if max_tokens is not None else {}
    planned_trial = PlannedTrial(
        trial_id=build_trial_id(
            experiment_id="local",
            task_id=task.task_id,
            agent_name="local",
            repetition=1,
        ),
        experiment_id="local",
        task_id=task.task_id,
        agent=AgentConfig(name="local", adapter=adapter, model=model, parameters=parameters),
        compute=ComputeConfig(backend="local", timeout_override=timeout),
        repetition=1,
    )
    runtime = LocalTaskRuntime(
        artifact_root=artifact_root,
        constitutional_model=constitutional_model,
        normalise=not no_normalise,
    )
    reviewer_config = _reviewer_config_from_cli(
        enabled=reviewer,
        model=reviewer_model,
        models_config=reviewer_models_config,
        fail_on_error=fail_on_reviewer_error,
    )
    recipe_spec = (
        SingleAttemptRecipe()
        if best_of_candidates == 1
        else BestOfAttemptRecipe(candidates=best_of_candidates, selector="self")
    )
    recipe = build_attempt_recipe(recipe_spec)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    console.print(f"[bold]Running {task.task_id} locally...[/bold]")
    console.print(f"  Model: {model}")
    console.print(f"  Adapter: {adapter}")
    try:
        if (
            best_of_candidates == 1
            and not no_verify
            and (resolved_task.instance_dir / "verifier_retry_prompt.md").is_file()
        ):
            record = run_trial_with_verifier_feedback(
                runtime=runtime,
                task=resolved_task,
                trial=planned_trial,
                reviewer=reviewer_config,
                keep_workspace=keep_workspace,
            )
        else:
            record = run_trial(
                runtime=runtime,
                task=resolved_task,
                trial=planned_trial,
                recipe=recipe,
                reviewer=reviewer_config,
                verify=not no_verify,
                keep_workspaces=keep_workspace,
            )
    except KeyboardInterrupt:
        console.print("[yellow]Interrupted[/yellow]")
        raise typer.Exit(130) from None
    except subprocess.TimeoutExpired as exc:
        console.print(f"[red]Timeout after {timeout}s[/red]")
        raise typer.Exit(1) from exc

    copied = _copy_record_files(
        record=record,
        artifact_root=artifact_root,
        output_dir=out_path,
        expected_output_path=task.verifier.expected_output_path,
    )
    if copied:
        console.print(f"\n[bold]Results copied to:[/bold] {out_path}")
        for relative in copied:
            console.print(f"  {relative} ({(out_path / relative).stat().st_size:,} bytes)")

    if not no_import:
        try:
            record_path = write_trial_record(ledger_root=ledger_root, record=record)
        except Exception as exc:
            console.print(f"[yellow]Auto-import failed: {exc}[/yellow]")
        else:
            console.print(f"\n[bold]Imported to ledger:[/bold] {record_path}")
            console.print(f"  View at: http://127.0.0.1:8710/viewer/local/{record.trial_id}")

    if keep_workspace:
        for workspace in runtime.attempt_workspaces:
            console.print(f"\n[dim]Workspace kept at: {workspace}[/dim]")

    reward = None if record.evaluation is None else record.evaluation.reward
    emit(
        "run-local",
        {
            "status": record.execution_status.value,
            "adapter": adapter,
            "mode": "adapter",
            "output_dir": str(out_path),
            "files": copied,
            "agent_seconds": record.timing.agent_seconds,
            "verifier_seconds": record.timing.verification_seconds,
            "reward": reward,
            "recipe": recipe_spec.model_dump(mode="json"),
            "reviewer_status": (
                "complete"
                if reviewer_config is not None
                and reviewer_config.enabled
                and record.evaluation is not None
                and record.evaluation.breakdown is not None
                and "llm_reviewer" in record.evaluation.breakdown
                else None
            ),
        },
    )


def _reviewer_config_from_cli(
    *,
    enabled: bool,
    model: str | None,
    models_config: Path | None,
    fail_on_error: bool,
) -> ReviewerRunConfig | None:
    if models_config is not None:
        config = load_reviewer_config(models_config)
        return config.model_copy(update={"enabled": True, "fail_on_error": fail_on_error or config.fail_on_error})
    if model is not None:
        return ReviewerRunConfig(
            enabled=True,
            fail_on_error=fail_on_error,
            models=[
                ReviewerEndpointConfig(
                    name=model,
                    model=model,
                )
            ],
        )
    if enabled:
        return ReviewerRunConfig(enabled=True, fail_on_error=fail_on_error)
    return None
