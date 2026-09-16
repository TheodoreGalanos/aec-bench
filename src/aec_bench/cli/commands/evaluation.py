# ABOUTME: Provides evaluation regime inspection and recorded-trial regrading commands.
# ABOUTME: Keeps verifier-only assessments separate from execution records and costs.

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.optional_dependencies import require_optional_extra
from aec_bench.cli.output import console, emit
from aec_bench.evaluation.regime import (
    diff_evaluation_regimes,
    format_evaluation_regime_diff,
    resolve_evaluation_regime,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository

app = typer.Typer(help="Inspect evaluation contracts and regrade recorded trials.", no_args_is_help=True)
regime_app = typer.Typer(help="Inspect published evaluation regimes.", no_args_is_help=True)
app.add_typer(regime_app, name="regime")


@app.command("regrade")
def regrade(
    source_trial: Path = typer.Argument(..., help="Finished local Harbor trial directory."),
    task: Path = typer.Option(..., "--task", help="Revised public task with a separate artifact-only verifier."),
    output: Path = typer.Option(..., "--output", "-o", help="New directory for the assessment and retained inputs."),
    backend: str = typer.Option(
        "docker", "--backend", help="Harbor verifier environment type, for example docker or modal."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Check input structure without starting an environment."),
) -> None:
    """Run a revised verifier against recorded artifacts without rerunning the agent."""
    require_optional_extra("Harbor regrading", "execution", ("harbor",))
    from harbor.models.trial.config import EnvironmentConfig  # type: ignore[import-untyped]
    from harbor.models.trial.result import TrialResult  # type: ignore[import-untyped]
    from harbor.trial.regrade import RegradeError  # type: ignore[import-untyped]

    from aec_bench.harness.harbor_regrade import plan_regrade, run_regrade

    try:
        config = plan_regrade(
            source_trial=source_trial,
            task_dir=task,
            output_dir=output,
            environment=EnvironmentConfig(type=backend),
        )
        if dry_run:
            emit(
                "evaluation regrade",
                {
                    "dry_run": True,
                    "source_trial": str(source_trial.resolve()),
                    "task": str(task.resolve()),
                    "output": str(config.trials_dir),
                    "backend": backend,
                    "agent_rerun": False,
                    "validation": "Input structure checked. Harbor checks artifact coverage before verification.",
                },
            )
            return
        result = asyncio.run(run_regrade(config))
        original = TrialResult.model_validate_json(
            (config.trials_dir / "source" / "result.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, RegradeError) as error:
        raise typer.BadParameter(str(error)) from error

    failed = result.exception_info is not None or result.verifier_result is None
    error_message = (
        result.exception_info.exception_message
        if result.exception_info
        else "Harbor returned no verifier result."
        if failed
        else None
    )
    emit(
        "evaluation regrade",
        {
            "status": "failed" if failed else "completed",
            "source_trial_id": str(original.id),
            "result": str(config.trials_dir / "verification" / "result.json"),
            "original_rewards": original.verifier_result.rewards if original.verifier_result else None,
            "rewards": result.verifier_result.rewards if result.verifier_result and not failed else None,
            "agent_rerun": False,
            "error": error_message,
        },
        errors=[error_message] if error_message else None,
    )


@regime_app.command("show")
def show_regime(
    ref: str = typer.Argument(..., help="Canonical evaluation-regime artifact ID."),
    artifact_root: Path = typer.Option(..., "--artifact-root", help="Artifact repository root."),
) -> None:
    """Show the semantic content of one exact evaluation regime."""

    regime_ref, regime = resolve_evaluation_regime(ArtifactRepository(artifact_root), ref)
    data = {
        "reference": regime_ref.model_dump(mode="json"),
        "regime": regime.model_dump(mode="json"),
    }
    emit("evaluation regime show", data)


@regime_app.command("diff")
def diff_regimes(
    left: str = typer.Argument(..., help="First canonical evaluation-regime artifact ID."),
    right: str = typer.Argument(..., help="Second canonical evaluation-regime artifact ID."),
    artifact_root: Path = typer.Option(..., "--artifact-root", help="Artifact repository root."),
) -> None:
    """Explain semantic policy changes between two exact evaluation regimes."""

    repository = ArtifactRepository(artifact_root)
    left_ref, left_regime = resolve_evaluation_regime(repository, left)
    right_ref, right_regime = resolve_evaluation_regime(repository, right)
    diff = diff_evaluation_regimes(
        left_ref=left_ref,
        left=left_regime,
        right_ref=right_ref,
        right=right_regime,
    )
    data = diff.model_dump(mode="json")

    def _human(_: dict[str, Any]) -> None:
        console.print(format_evaluation_regime_diff(diff))

    emit("evaluation regime diff", data, human_renderer=_human)


__all__ = ("app",)
