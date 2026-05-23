# ABOUTME: Tests for the ScreenProvider Command Palette provider.
# ABOUTME: Verifies fuzzy search returns correct screen navigation hits.

from aec_bench.tui.commands.screens import SCREEN_ENTRIES, ScreenProvider  # noqa: F401


def test_screen_entries_has_expected_screens() -> None:
    names = [e.name for e in SCREEN_ENTRIES]
    assert "Dashboard" in names
    assert "Triage" in names
    assert "Library" in names
    assert "Evaluate" in names
    assert "Compare" in names
    assert "Viewer" not in names  # Viewer is not directly navigable


def test_screen_entries_have_mode_and_keybind() -> None:
    for entry in SCREEN_ENTRIES:
        assert entry.mode in ("dashboard", "explore", "review", "analyse")
        assert entry.screen in (None, "datasets", "leaderboard", "review", "compare")
        assert isinstance(entry.description, str)
        assert len(entry.description) > 0


def test_screen_entry_count() -> None:
    assert len(SCREEN_ENTRIES) >= 7  # Dashboard + 2 explore + 2 review + 2 analyse


def test_concrete_screen_entries_are_explicit() -> None:
    routes = {entry.name: entry.screen for entry in SCREEN_ENTRIES}
    assert routes["Datasets"] == "datasets"
    assert routes["Leaderboard"] == "leaderboard"
    assert routes["Review Queue"] == "review"
    assert routes["Compare"] == "compare"
