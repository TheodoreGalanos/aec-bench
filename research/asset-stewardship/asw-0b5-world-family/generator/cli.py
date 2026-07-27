# ABOUTME: Exposes the generator-side B5-W0 declaration reader as a separate research process.
# ABOUTME: Emits only compact content identities and never runs SWMM or hydraulic calculations.

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from generator import boundary


def main(arguments: list[str] | None = None) -> int:
    args = sys.argv[1:] if arguments is None else arguments
    if len(args) != 2 or args[0] not in {"w1", "generation"}:
        print("usage: python -m generator.cli {w1|generation} FILE", file=sys.stderr)
        return 2
    try:
        raw = Path(args[1]).read_bytes()
        if args[0] == "w1":
            declaration = boundary.read_w1_declaration(raw)
            result: dict[str, object] = {
                "canonical_sha256": hashlib.sha256(raw).hexdigest(),
                "reader": "generator",
                "record_count": len(declaration["parameters"]) + len(declaration["composites"]),
            }
        else:
            result = {
                "reader": "generator",
                "world_generation_id": boundary.world_generation_id(raw),
            }
    except (OSError, boundary.GeneratorBoundaryError) as error:
        print(str(error), file=sys.stderr)
        return 2
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
