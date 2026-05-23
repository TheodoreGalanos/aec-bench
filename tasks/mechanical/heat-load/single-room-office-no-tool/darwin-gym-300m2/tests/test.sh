#!/bin/bash
# ABOUTME: Thin wrapper that runs the Python verifier.
# ABOUTME: Ensures reward.json is always written, even on crash.

REWARD_FILE="/logs/verifier/reward.json"
mkdir -p /logs/verifier
trap 'if [ ! -f "$REWARD_FILE" ]; then echo "{\"reward\": 0.0}" > "$REWARD_FILE"; fi' EXIT
python3 /tests/verify.py
