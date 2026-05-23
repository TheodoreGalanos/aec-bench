# ABOUTME: Reusable stat card widget for the TUI dashboard.
# ABOUTME: Displays a large value with a small label underneath.

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget


class StatCard(Widget):
    """Single stat display: large value text with a small label below."""

    DEFAULT_CSS = """
    StatCard {
        width: 1fr;
        height: auto;
        min-height: 4;
        padding: 1 2;
        background: $surface;
        border: round $secondary;
        content-align: center middle;
    }
    """

    value: reactive[str] = reactive("")
    label: reactive[str] = reactive("")
    color: reactive[str | None] = reactive(None)

    def __init__(
        self,
        value: str = "",
        label: str = "",
        color: str | None = None,
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self.value = value
        self.label = label
        self.color = color

    def render(self) -> Text:
        text = Text()
        style = f"bold {self.color}" if self.color else "bold"
        text.append(self.value, style=style)
        text.append("\n")
        text.append(self.label, style="dim")
        return text
