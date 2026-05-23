# ABOUTME: Tests for advisor boundary contracts.
# ABOUTME: Verifies frozen dataclasses, protocol shape, and default values.

from dataclasses import FrozenInstanceError

import pytest

from aec_bench.contracts.advisor import (
    AdvisorConfig,
    AdvisorContextStrategy,
    AdvisorRequest,
    AdvisorResponse,
    AdvisorUsageStats,
)


class TestAdvisorConfig:
    def test_defaults(self) -> None:
        cfg = AdvisorConfig(model="claude-opus-4-6")
        assert cfg.model == "claude-opus-4-6"
        assert cfg.max_uses == 5
        assert cfg.max_response_tokens == 500
        assert cfg.context_window == 10
        assert cfg.enabled is True

    def test_frozen(self) -> None:
        cfg = AdvisorConfig(model="claude-opus-4-6")
        with pytest.raises(FrozenInstanceError):
            cfg.model = "other"  # type: ignore[misc]

    def test_custom_values(self) -> None:
        cfg = AdvisorConfig(
            model="gpt-4.1",
            max_uses=10,
            max_response_tokens=800,
            context_window=20,
            enabled=False,
        )
        assert cfg.max_uses == 10
        assert cfg.enabled is False


class TestAdvisorRequest:
    def test_required_fields(self) -> None:
        req = AdvisorRequest(goal="write section", problem="missing data")
        assert req.goal == "write section"
        assert req.problem == "missing data"
        assert req.attempt is None

    def test_with_attempt(self) -> None:
        req = AdvisorRequest(
            goal="calculate load",
            problem="formula unclear",
            attempt="tried AS3600 table 8.6",
        )
        assert req.attempt == "tried AS3600 table 8.6"

    def test_frozen(self) -> None:
        req = AdvisorRequest(goal="x", problem="y")
        with pytest.raises(FrozenInstanceError):
            req.goal = "z"  # type: ignore[misc]


class TestAdvisorResponse:
    def test_all_fields(self) -> None:
        resp = AdvisorResponse(
            advice="Re-read clause 4.3",
            suggested_action="extract from standards document",
            confidence=0.85,
            reasoning="The required values are in the referenced standard",
        )
        assert resp.advice == "Re-read clause 4.3"
        assert resp.confidence == 0.85

    def test_frozen(self) -> None:
        resp = AdvisorResponse(
            advice="a",
            suggested_action="b",
            confidence=0.5,
            reasoning="c",
        )
        with pytest.raises(FrozenInstanceError):
            resp.advice = "d"  # type: ignore[misc]


class TestAdvisorUsageStats:
    def test_defaults(self) -> None:
        stats = AdvisorUsageStats(calls_made=0, calls_remaining=5)
        assert stats.advisor_input_tokens == 0
        assert stats.advisor_output_tokens == 0
        assert stats.advisor_cost_usd == 0.0

    def test_accumulation(self) -> None:
        stats = AdvisorUsageStats(
            advisor_input_tokens=2400,
            advisor_output_tokens=760,
            advisor_cost_usd=0.15,
            calls_made=3,
            calls_remaining=2,
        )
        assert stats.calls_made + stats.calls_remaining == 5


class TestAdvisorContextStrategyProtocol:
    def test_protocol_conformance(self) -> None:
        class DummyStrategy:
            def build_advisor_context(
                self,
                request: AdvisorRequest,
                conversation_state: dict,
            ) -> list[dict]:
                return [{"role": "user", "content": request.goal}]

        strategy: AdvisorContextStrategy = DummyStrategy()
        msgs = strategy.build_advisor_context(
            AdvisorRequest(goal="test", problem="test"),
            {},
        )
        assert len(msgs) == 1
