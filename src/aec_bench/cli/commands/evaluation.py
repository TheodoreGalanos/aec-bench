# ABOUTME: Provides semantic inspection commands for published evaluation regimes.
# ABOUTME: Resolves exact regime artifacts and reports policy changes by field path.

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.output import console, emit
from aec_bench.evaluation.regime import (
    diff_evaluation_regimes,
    format_evaluation_regime_diff,
    resolve_evaluation_regime,
)
from aec_bench.ledger.artifact_repository import ArtifactRepository

app = typer.Typer(help="Inspect evaluation contracts.", no_args_is_help=True)
regime_app = typer.Typer(help="Inspect published evaluation regimes.", no_args_is_help=True)
app.add_typer(regime_app, name="regime")


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
