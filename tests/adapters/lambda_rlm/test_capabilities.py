# ABOUTME: Tests for LambdaRlmAdapter.declare_capabilities() — the constitutional capability surface.
# ABOUTME: Verifies only source_fidelity and information_minimality are supported by the pipeline.

from aec_bench.adapters.base import AdapterCapabilities
from aec_bench.adapters.lambda_rlm.adapter import LambdaRlmAdapter


def test_declare_capabilities_returns_adapter_capabilities():
    caps = LambdaRlmAdapter.declare_capabilities()
    assert isinstance(caps, AdapterCapabilities)


def test_capabilities_source_tracing_enabled():
    caps = LambdaRlmAdapter.declare_capabilities()
    assert caps.has_source_tracing is True
    assert caps.supports_principle("source_fidelity") is True


def test_capabilities_context_filtering_enabled():
    caps = LambdaRlmAdapter.declare_capabilities()
    assert caps.has_context_filtering is True
    assert caps.supports_principle("information_minimality") is True


def test_capabilities_state_scaffolding_disabled():
    caps = LambdaRlmAdapter.declare_capabilities()
    assert caps.has_state_persistence is False
    assert caps.has_compaction is False
    assert caps.has_scaffolding is False
    assert caps.supports_principle("state_persistence") is False
    assert caps.supports_principle("progress_obligation") is False
    assert caps.supports_principle("earned_autonomy") is False


def test_capabilities_review_phase_declared():
    caps = LambdaRlmAdapter.declare_capabilities()
    assert caps.has_review_phase is True
