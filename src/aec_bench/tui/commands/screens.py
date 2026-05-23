# ABOUTME: ScreenProvider for the Command Palette — navigate to any screen by name.
# ABOUTME: Returns fuzzy-matched screen entries with mode and description.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScreenEntry:
    """A navigable screen registered in the Command Palette."""

    name: str
    mode: str
    description: str
    keybind: str | None = None
    screen: str | None = None


SCREEN_ENTRIES: list[ScreenEntry] = [
    ScreenEntry("Dashboard", "dashboard", "Home screen with stats and sparklines", "D"),
    ScreenEntry("Library", "explore", "Browse tasks, templates, and instances", "E"),
    ScreenEntry("Datasets", "explore", "Versioned benchmark snapshots", screen="datasets"),
    ScreenEntry("Leaderboard", "explore", "Model rankings across datasets", screen="leaderboard"),
    ScreenEntry("Triage", "review", "Filterable trial list with annotations", "R"),
    ScreenEntry(
        "Review Queue",
        "review",
        "Structured annotation and calibration forms",
        screen="review",
    ),
    ScreenEntry("Evaluate", "analyse", "Adapter x task heatmap matrix", "A"),
    ScreenEntry("Compare", "analyse", "Model x task comparison matrix", screen="compare"),
]


class ScreenProvider:
    """Command Palette provider for screen navigation.

    Provides fuzzy-matched screen entries so the Command Palette can offer
    direct navigation to any TUI screen. Full Textual Provider integration
    is wired in Plan C Task 6.
    """

    entries: list[ScreenEntry] = SCREEN_ENTRIES

    def search(self, query: str) -> list[ScreenEntry]:
        """Return screen entries whose names contain the query (case-insensitive)."""
        query_lower = query.lower()
        return [e for e in self.entries if query_lower in e.name.lower()]
