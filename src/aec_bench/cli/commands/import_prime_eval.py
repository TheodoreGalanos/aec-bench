# ABOUTME: CLI command for importing Prime hosted eval samples into the ledger.
# ABOUTME: Materialises Prime rollouts as standard artefacts for existing reports.

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import typer

from aec_bench.cli.commands.config import resolve_path
from aec_bench.cli.output import console, emit, print_success
from aec_bench.prime_lab.eval_import import (
    fetch_prime_eval_payloads,
    import_prime_eval_samples,
)


def import_prime_eval(
    eval_id: str | None = typer.Argument(
        None,
        help="Prime evaluation id. Omit when using --evaluation-json and --samples-json.",
    ),
    experiment_id: str | None = typer.Option(
        None,
        "--experiment",
        "-e",
        help="Ledger experiment id. Defaults to prime-eval-<eval-id>.",
    ),
    ledger_root: str | None = typer.Option(None, "--ledger-root", help="Ledger directory"),
    evaluation_json: Path | None = typer.Option(
        None,
        "--evaluation-json",
        help="Saved `prime eval get` JSON payload.",
    ),
    samples_json: Path | None = typer.Option(
        None,
        "--samples-json",
        help="Saved `prime eval samples` JSON payload with a samples array.",
    ),
) -> None:
    """Import Prime hosted evaluation samples as standard ledger artefacts.

    Examples:
      aec-bench import-prime-eval cefmpy8npgz5d807l5d4hlua
      aec-bench import-prime-eval --evaluation-json eval.json --samples-json samples.json
      aec-bench report behavioral -e prime-eval-cefmpy8npgz5d807l5d4hlua --classifier MODEL
    """
    start = time.monotonic()
    resolved_ledger = resolve_path("ledger_root", cli_override=ledger_root)

    try:
        evaluation, samples = _load_payloads(
            eval_id=eval_id,
            evaluation_json=evaluation_json,
            samples_json=samples_json,
        )
    except ValueError as exc:
        emit("import-prime-eval", data=None, errors=[str(exc)], start_time=start)
        return

    with console.status("Importing Prime eval samples into ledger artefacts..."):
        result = import_prime_eval_samples(
            evaluation=evaluation,
            samples=samples,
            ledger_root=resolved_ledger,
            experiment_id=experiment_id,
        )

    data = {
        "experiment_id": result.experiment_id,
        "imported": len(result.records),
        "duplicates": result.skipped_duplicates,
        "ledger_root": str(resolved_ledger),
        "record_paths": [str(path) for path in result.record_paths],
        "artifact_paths": [str(path) for path in result.artifact_paths],
        "next_command": (f"aec-bench report behavioral -e {result.experiment_id} --classifier <classifier-model>"),
    }

    def _render(d: dict[str, Any]) -> None:
        print_success(f"Imported {d['imported']} Prime samples ({d['duplicates']} duplicates skipped)")
        console.print(f"  Experiment: {d['experiment_id']}")
        console.print(f"  Ledger: {d['ledger_root']}")
        console.print(f"  Next: {d['next_command']}")

    emit("import-prime-eval", data, start_time=start, human_renderer=_render)


def _load_payloads(
    *,
    eval_id: str | None,
    evaluation_json: Path | None,
    samples_json: Path | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if evaluation_json is not None or samples_json is not None:
        if evaluation_json is None or samples_json is None:
            raise ValueError("--evaluation-json and --samples-json must be provided together")
        evaluation = _read_json_object(evaluation_json)
        samples_payload = _read_json_object(samples_json)
        raw_samples = samples_payload.get("samples")
        if not isinstance(raw_samples, list):
            raise ValueError("--samples-json must contain a top-level samples array")
        return evaluation, [sample for sample in raw_samples if isinstance(sample, dict)]

    if eval_id is None:
        raise ValueError("provide a Prime eval id or both --evaluation-json and --samples-json")
    return fetch_prime_eval_payloads(eval_id)


def _read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload
