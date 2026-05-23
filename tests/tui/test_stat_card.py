# ABOUTME: Tests for the StatCard widget used on the TUI dashboard.
# ABOUTME: Verifies rendering of value, label, and optional colour.

import pytest
from textual.app import App, ComposeResult

from aec_bench.tui.widgets.stat_card import StatCard


class StatCardTestApp(App[None]):
    def __init__(self, value: str, label: str, color: str | None = None) -> None:
        super().__init__()
        self._value = value
        self._label = label
        self._color = color

    def compose(self) -> ComposeResult:
        yield StatCard(value=self._value, label=self._label, color=self._color)


@pytest.mark.anyio
async def test_stat_card_renders_value_and_label() -> None:
    app = StatCardTestApp(value="47", label="Total Trials")
    async with app.run_test() as pilot:
        await pilot.pause()
        card = app.query_one(StatCard)
        rendered = str(card.render())
        assert "47" in rendered
        assert "Total Trials" in rendered


@pytest.mark.anyio
async def test_stat_card_accepts_color() -> None:
    app = StatCardTestApp(value="0.68", label="Mean Reward", color="#D4A27F")
    async with app.run_test() as pilot:
        await pilot.pause()
        card = app.query_one(StatCard)
        assert card.color == "#D4A27F"
        rendered = str(card.render())
        assert "0.68" in rendered


def test_stat_card_default_color_is_none() -> None:
    card = StatCard(value="5", label="Count")
    assert card.color is None
