#!/bin/sh
# ABOUTME: Runs the synthetic report verifier in the normal Harbor verifier phase.
# ABOUTME: Leaves verifier failures visible instead of manufacturing a passing result.
set -eu
python3 /tests/verify.py
