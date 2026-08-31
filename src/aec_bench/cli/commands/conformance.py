# ABOUTME: Runs the installed conformance checks for maintained world owners.
# ABOUTME: Uses the canonical world key and reports executed conformance guarantees.

from __future__ import annotations

import time
from typing import Any

import typer

from aec_bench.cli.output import emit, print_error, print_success
from aec_bench.worlds.catalogue import _catalogue
from aec_bench.worlds.conformance import run_world_conformance, world_conformance_case

app = typer.Typer(
    help="Run reusable conformance checks for maintained task families.",
    no_args_is_help=True,
)


@app.callback()
def _callback() -> None:
    """Run conformance checks for one task family."""


def _render_world_result(data: dict[str, Any]) -> None:
    print_success(f"World conformance passed for {data['world_key']} — {len(data['proven'])} checks passed")


@app.command("world")
def world_cmd(
    world_key: str = typer.Argument(..., help="Canonical world key, for example monitoring/dam-seepage."),
    seed: int = typer.Option(0, "--seed", help="Deterministic conformance scenario seed."),
) -> None:
    """Run conformance checks for one maintained world."""

    start = time.monotonic()
    try:
        definition = next(
            (definition for definition in _catalogue().definitions if str(definition.identity.key) == world_key),
            None,
        )
        if definition is None:
            known = ", ".join(str(item.identity.key) for item in _catalogue().definitions)
            raise KeyError(f"unknown world key: {world_key}. Known: {known}")
        case = world_conformance_case(world_key)
        result = run_world_conformance(case, seed=seed)
        if definition.identity.version <= 0 or any(identity.version <= 0 for identity in definition.profile_identities):
            raise ValueError("world and profile versions must be positive")
        result["proven"].insert(0, "identity_and_profile_versions")
        result["identity"] = {
            "id": str(definition.identity.id),
            "key": str(definition.identity.key),
            "version": definition.identity.version,
            "profiles": len(definition.profile_identities),
        }
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        print_error(str(error) or "world conformance failed")
        raise typer.Exit(1) from error
    emit("conformance world", result, start_time=start, human_renderer=_render_world_result)
