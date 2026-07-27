# ABOUTME: Runs the independent B5-W0 certifier declaration reader as its own research process.
# ABOUTME: Reports compact identities only and has no generator, SWMM, or hydraulic dependency.

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from certifier import boundary


def main(arguments: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if arguments is None else arguments)
    if len(args) != 2 or args[0] not in ("w1", "generation"):
        print("usage: python -m certifier.cli {w1|generation} FILE", file=sys.stderr)
        return 2
    declaration_path = Path(args[1])
    try:
        payload = declaration_path.read_bytes()
        if args[0] == "w1":
            decoded = boundary.read_w1_declaration(payload)
            response: dict[str, object] = {
                "canonical_sha256": hashlib.sha256(payload).hexdigest(),
                "reader": "certifier",
                "record_count": len(decoded["parameters"]) + len(decoded["composites"]),
            }
        else:
            response = {
                "reader": "certifier",
                "world_generation_id": boundary.world_generation_id(payload),
            }
    except (OSError, boundary.CertifierBoundaryError) as error:
        print(str(error), file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(response, separators=(",", ":"), sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
