#!/usr/bin/env python3
# ABOUTME: Generates the committed lifecycle owner composition module.
# ABOUTME: Uses an explicit owner list so discovery is deterministic and reviewable.

from __future__ import annotations

import argparse
from pathlib import Path

from aec_bench.catalogue import LIFECYCLE_OWNER_IMPORTS, render_lifecycle_catalogue

OWNER_IMPORTS = LIFECYCLE_OWNER_IMPORTS
render_catalogue = render_lifecycle_catalogue


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/aec_bench/lifecycles/generated_catalogue.py"),
        help="Generated module path.",
    )
    args = parser.parse_args()
    args.output.write_text(render_catalogue(), encoding="utf-8")


if __name__ == "__main__":
    main()
