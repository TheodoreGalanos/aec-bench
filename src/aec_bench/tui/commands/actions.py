# ABOUTME: ActionProvider for the Command Palette — quick actions like dark mode toggle.
# ABOUTME: Returns ActionEntry objects that execute directly without screen navigation.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionEntry:
    name: str
    description: str
    action_name: str


ACTION_ENTRIES: list[ActionEntry] = [
    ActionEntry("Toggle Dark Mode", "Switch between dark and light themes", "toggle_dark"),
    ActionEntry("Quit", "Exit the application", "quit"),
]
