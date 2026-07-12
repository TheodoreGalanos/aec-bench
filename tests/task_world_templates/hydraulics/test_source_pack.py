# ABOUTME: Protects the canonical EPA SWMM Example 3 research packet used by PR18.
# ABOUTME: Ensures the packet is restored at its original path without silent rewriting.

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_PACK = (
    REPO_ROOT
    / "docs"
    / "task-world-opportunities"
    / "real-world-grounding"
    / "stormwater-drainage-package"
    / "swmm_example3_detention_source_pack"
)
EXPECTED_SHA256 = {
    "expected-output.md": "beb4bda1a9d01997b5dd3a90b15f38ef5f78f0cdc87dbab7c6a0b914a2dd69f8",
    "model-summary.yaml": "061d12e1790972eaeb8959f41c5a3e696dcc7136e429cc844d9aec3fc70f6cbf",
    "source-manifest.yaml": "21f606340520d3fdfc5143df7bc26cd3752555294fa31380b90a1c969446d315",
    "source-pack-plan.md": "8f5d40d408c564342f4ff3d5cee21bce6884453f581bc11c9370884267fb0616",
    "verification-cases.yaml": "7bf336f947dc91bbc22dc4e24aaf8c25c9e8f7cb2655ed2b69836e18399382a7",
    "verification-rules.yaml": "dbcc3b59d5974efc244403f09792a71f7485f8c4d67e04acd87784e1db247db8",
    "verifier-implementation-brief.md": "24679c47d0e7078b9381f24d1e6259b06507b29947254ff5d8665117b92a3b80",
}
COMPATIBILITY_MATRIX = REPO_ROOT / "docs" / "ssc03-swmm-compatibility-matrix.yaml"


def test_canonical_swmm_example3_packet_is_restored_byte_for_byte() -> None:
    actual = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(SOURCE_PACK.iterdir())
        if path.is_file()
    }

    assert actual == EXPECTED_SHA256


def test_compatibility_matrix_records_native_failure_and_honest_fallback() -> None:
    matrix = yaml.safe_load(COMPATIBILITY_MATRIX.read_text(encoding="utf-8"))
    probes = {probe["id"]: probe for probe in matrix["probes"]}

    assert matrix["candidate"]["version"] == "0.17.0"
    assert matrix["candidate"]["selected_wheel_sha256"] == (
        "0390d0afdfb7fb3296638c813dd549b290e0028e6812aac4acab59b442f88870"
    )
    assert probes["python313_namespace"]["exit_status"] == 0
    assert probes["python313_solver_binding"]["exit_status"] == 137
    assert probes["python313_output_binding"]["exit_status"] == 137
    assert matrix["selection_gate"]["selected_route"] == "aec-bench.deterministic-hydraulic-screening-kernel"
    assert matrix["decision"]["actual_swmm_run_attempted"] is False
    assert matrix["decision"]["dependency_added"] is False
