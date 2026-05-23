# ABOUTME: Tests for the AdapterCapabilities declaration and validation.
# ABOUTME: Capabilities are used by the constitutional inference engine.

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.adapters.base import AdapterCapabilities


class TestAdapterCapabilities:
    def test_defaults_all_false(self) -> None:
        cap = AdapterCapabilities()
        assert cap.has_context_filtering is False
        assert cap.has_state_persistence is False
        assert cap.has_compaction is False
        assert cap.has_scaffolding is False
        assert cap.has_review_phase is False
        assert cap.has_source_tracing is False

    def test_all_enabled(self) -> None:
        cap = AdapterCapabilities(
            has_context_filtering=True,
            has_state_persistence=True,
            has_compaction=True,
            has_scaffolding=True,
            has_review_phase=True,
            has_source_tracing=True,
        )
        assert cap.has_compaction is True

    def test_frozen(self) -> None:
        cap = AdapterCapabilities()
        with pytest.raises(FrozenInstanceError):
            cap.has_compaction = True  # type: ignore[misc]

    def test_supports_principle_information_minimality(self) -> None:
        cap = AdapterCapabilities(has_context_filtering=True)
        assert cap.supports_principle("information_minimality") is True

        cap_missing = AdapterCapabilities(has_context_filtering=False)
        assert cap_missing.supports_principle("information_minimality") is False

    def test_supports_principle_state_persistence(self) -> None:
        cap = AdapterCapabilities(
            has_state_persistence=True,
            has_compaction=True,
        )
        assert cap.supports_principle("state_persistence") is True

        cap_missing = AdapterCapabilities(has_state_persistence=False)
        assert cap_missing.supports_principle("state_persistence") is False

    def test_supports_principle_progress_obligation(self) -> None:
        cap = AdapterCapabilities(has_scaffolding=True)
        assert cap.supports_principle("progress_obligation") is True

        cap_missing = AdapterCapabilities(has_scaffolding=False)
        assert cap_missing.supports_principle("progress_obligation") is False

    def test_supports_principle_source_fidelity(self) -> None:
        cap = AdapterCapabilities(has_source_tracing=True)
        assert cap.supports_principle("source_fidelity") is True

        cap_missing = AdapterCapabilities(has_source_tracing=False)
        assert cap_missing.supports_principle("source_fidelity") is False

    def test_supports_principle_earned_autonomy(self) -> None:
        cap = AdapterCapabilities(has_scaffolding=True)
        assert cap.supports_principle("earned_autonomy") is True

    def test_supports_principle_unknown(self) -> None:
        cap = AdapterCapabilities()
        with pytest.raises(ValueError, match="unknown principle"):
            cap.supports_principle("mystery_principle")
