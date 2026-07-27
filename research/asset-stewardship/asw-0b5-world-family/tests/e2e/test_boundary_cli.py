# ABOUTME: Runs the two B5-W0 declaration readers as separate real Python programs.
# ABOUTME: Proves valid-byte agreement and independently owned malformed-byte rejection end to end.

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from support import canonical_bytes, generation_declaration

B5_ROOT = Path(__file__).parents[2]
SOURCE_ROOT = B5_ROOT
W1_DECLARATION = B5_ROOT / "declarations" / "w1-member-authority.json"


def run_reader(package: str, kind: str, declaration: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(SOURCE_ROOT)
    return subprocess.run(
        [sys.executable, "-m", package, kind, str(declaration)],
        check=False,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_two_processes_agree_on_w1_and_generation_identities(
    tmp_path: Path,
) -> None:
    generator_w1 = run_reader(
        "generator.cli",
        "w1",
        W1_DECLARATION,
    )
    certifier_w1 = run_reader(
        "certifier.cli",
        "w1",
        W1_DECLARATION,
    )
    generation_path = tmp_path / "generation.json"
    generation_path.write_bytes(canonical_bytes(generation_declaration()))
    generator_generation = run_reader(
        "generator.cli",
        "generation",
        generation_path,
    )
    certifier_generation = run_reader(
        "certifier.cli",
        "generation",
        generation_path,
    )

    assert generator_w1.returncode == certifier_w1.returncode == 0
    assert generator_generation.returncode == certifier_generation.returncode == 0
    generator_w1_result = json.loads(generator_w1.stdout)
    certifier_w1_result = json.loads(certifier_w1.stdout)
    generator_generation_result = json.loads(generator_generation.stdout)
    certifier_generation_result = json.loads(certifier_generation.stdout)
    assert generator_w1_result["canonical_sha256"] == certifier_w1_result["canonical_sha256"]
    assert generator_w1_result["record_count"] == certifier_w1_result["record_count"] == 49
    assert generator_generation_result["world_generation_id"] == certifier_generation_result["world_generation_id"]


def test_two_processes_reject_malformed_bytes_for_their_own_reasons(
    tmp_path: Path,
) -> None:
    malformed = tmp_path / "malformed.json"
    malformed.write_bytes(W1_DECLARATION.read_bytes().replace(b":", b": ", 1))

    generator_result = run_reader(
        "generator.cli",
        "w1",
        malformed,
    )
    certifier_result = run_reader(
        "certifier.cli",
        "w1",
        malformed,
    )

    assert generator_result.returncode == certifier_result.returncode == 2
    assert "generator:" in generator_result.stderr
    assert "certifier:" in certifier_result.stderr
