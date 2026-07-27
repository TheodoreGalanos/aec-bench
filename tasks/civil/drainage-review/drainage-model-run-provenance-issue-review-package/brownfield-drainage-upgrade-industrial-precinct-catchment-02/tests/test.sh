#!/usr/bin/env bash
set -euo pipefail
mkdir -p /logs/verifier
trap 'if [ ! -f /logs/verifier/reward.json ]; then echo "{\"reward\": 0.0}" > /logs/verifier/reward.json; fi' EXIT
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/verify.py"
