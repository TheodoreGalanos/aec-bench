#!/usr/bin/env python3
# ABOUTME: Produces read-only trajectory metrics for retained Prime interactive-world trials.
# ABOUTME: Keeps study analysis outside task-owned evaluation and world state.

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aec_bench.experimentation.qualification.pump_station_prime_trajectory import (
    analyze_pump_station_prime_trial,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyse retained Prime interactive-world trial evidence.")
    parser.add_argument("trial_directories", nargs="+", type=Path)
    parser.add_argument(
        "--large-output-threshold-chars",
        type=int,
        default=10_000,
        help="Minimum retained tool-result characters counted as a large output.",
    )
    parser.add_argument("--output", type=Path, help="Write JSON to this file instead of stdout.")
    args = parser.parse_args()

    analyses = [
        analyze_pump_station_prime_trial(
            directory,
            large_output_threshold_chars=args.large_output_threshold_chars,
        ).model_dump(mode="json")
        for directory in args.trial_directories
    ]
    payload = {
        "schema_id": "aecbench.prime-world-study-analysis.v1",
        "trials": analyses,
    }
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(text, end="")
        return
    args.output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
