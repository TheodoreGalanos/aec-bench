# ABOUTME: Provides a narrow command-line surface for the isolated B3 build and replay workflow.
# ABOUTME: Requires fresh paths and exposes no aec-bench production command, registry, or adapter.

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from asw_b3_swmm.build import assert_absent_workspace, build_engine
from asw_b3_swmm.execution import reproduce, spike_root
from asw_b3_swmm.rendering import render_probe
from asw_b3_swmm.specification import load_specification


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m asw_b3_swmm",
        description="Isolated, non-authoritative ASW-0B3 SWMM research spike.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build", help="build the exact pinned real engine")
    build_parser.add_argument("--workspace", type=Path, required=True)
    build_parser.add_argument(
        "--patch",
        type=Path,
        default=spike_root() / "patches" / "swmm-5.2.4-cmake-portability.patch",
    )

    reproduce_parser = subparsers.add_parser("reproduce", help="run both probes twice")
    reproduce_parser.add_argument("--engine-receipt", type=Path, required=True)
    reproduce_parser.add_argument("--workspace", type=Path, required=True)

    render_parser = subparsers.add_parser("render", help="render one disposable probe")
    render_parser.add_argument(
        "--probe",
        choices=("a_duty", "b_duty_label_probe"),
        required=True,
    )
    render_parser.add_argument("--output", type=Path, required=True)
    return parser


def main(arguments: Sequence[str] | None = None) -> int:
    """Execute one bounded B3 research operation."""
    parsed = _parser().parse_args(arguments)
    if parsed.command == "build":
        receipt_path = build_engine(parsed.workspace, parsed.patch)
        print(receipt_path)
        return 0
    if parsed.command == "reproduce":
        evidence = reproduce(parsed.engine_receipt, parsed.workspace)
        print(json.dumps(evidence, indent=2, sort_keys=True, allow_nan=False))
        return 0
    if parsed.command == "render":
        output = parsed.output.resolve()
        assert_absent_workspace(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        specification = load_specification(spike_root() / "fixtures" / "spike-probes.json")
        output.write_text(render_probe(specification, parsed.probe), encoding="utf-8")
        print(output)
        return 0
    raise AssertionError(f"unhandled command: {parsed.command}")
