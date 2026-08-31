# ABOUTME: Runs the shared local verifier and evaluation conformance matrix.
# ABOUTME: Keeps the production receipt and mapping path covered by one reusable test entry point.

from aec_bench.evaluation.conformance import REQUIRED_GUARANTEES, run_verifier_conformance


def test_local_verifier_and_evaluation_conformance() -> None:
    result = run_verifier_conformance()

    assert set(result["proven"]) == REQUIRED_GUARANTEES
