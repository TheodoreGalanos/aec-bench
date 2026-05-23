# ABOUTME: Tests for the TUI app shell with Screen Modes.
# ABOUTME: Verifies mode switching, keybinds, theme registration, and Command Palette.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench.tui.app import AecBenchTUI


def _make_app(tmp_path: Path) -> AecBenchTUI:
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    return AecBenchTUI(ledger_root=ledger, tasks_root=tasks)


@pytest.mark.anyio
async def test_app_starts_in_dashboard_mode(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.current_mode == "dashboard"


@pytest.mark.anyio
async def test_app_has_four_modes(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert set(app.MODES.keys()) == {"dashboard", "explore", "review", "analyse"}


@pytest.mark.anyio
async def test_switch_to_explore_mode(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        assert app.current_mode == "explore"


@pytest.mark.anyio
async def test_switch_to_review_mode(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.current_mode == "review"


@pytest.mark.anyio
async def test_switch_to_analyse_mode(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        assert app.current_mode == "analyse"


@pytest.mark.anyio
async def test_dashboard_keybind_returns_to_dashboard(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        # The LibraryScreen has an Input widget that captures keystrokes.
        # Blur it first so the app-level "d" binding is reachable.
        app.screen.set_focus(None)
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert app.current_mode == "dashboard"


@pytest.mark.anyio
async def test_command_palette_is_enabled(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    assert app.ENABLE_COMMAND_PALETTE is True


@pytest.mark.anyio
async def test_app_has_dark_and_light_themes(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "aec-bench-dark"


# ------------------------------------------------------------------
# Screen-type assertions — verify modes wire to real screens
# ------------------------------------------------------------------


@pytest.mark.anyio
async def test_dashboard_mode_shows_dashboard_screen(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        from aec_bench.tui.screens.dashboard import DashboardScreen

        assert isinstance(app.screen, DashboardScreen)


@pytest.mark.anyio
async def test_explore_mode_shows_library_screen(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("e")
        await pilot.pause()
        from aec_bench.tui.screens.library import LibraryScreen

        assert isinstance(app.screen, LibraryScreen)


@pytest.mark.anyio
async def test_review_mode_shows_triage_screen(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        from aec_bench.tui.screens.triage import TriageScreen

        assert isinstance(app.screen, TriageScreen)


@pytest.mark.anyio
async def test_analyse_mode_shows_evaluate_screen(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("a")
        await pilot.pause()
        from aec_bench.tui.screens.evaluate import EvaluateScreen

        assert isinstance(app.screen, EvaluateScreen)


# ------------------------------------------------------------------
# Integration smoke tests
# ------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_mode_cycle(tmp_path: Path) -> None:
    """Switch through all modes and verify we can return to dashboard."""
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.current_mode == "dashboard"

        await pilot.press("e")
        await pilot.pause()
        assert app.current_mode == "explore"

        # Blur any focused widget (e.g. Input in LibraryScreen) so
        # the app-level "r" binding is reachable.
        app.screen.set_focus(None)
        await pilot.pause()
        await pilot.press("r")
        await pilot.pause()
        assert app.current_mode == "review"

        await pilot.press("a")
        await pilot.pause()
        assert app.current_mode == "analyse"

        # Blur any focused widget so the app-level "d" binding is reachable.
        app.screen.set_focus(None)
        await pilot.pause()
        await pilot.press("d")
        await pilot.pause()
        assert app.current_mode == "dashboard"


@pytest.mark.anyio
async def test_toggle_dark_mode(tmp_path: Path) -> None:
    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme == "aec-bench-dark"
        # The built-in toggle_dark action cycles to textual-light.
        await pilot.press("D")
        await pilot.pause()
        assert app.theme == "textual-light"


# ------------------------------------------------------------------
# Command Palette provider registration
# ------------------------------------------------------------------


def test_command_palette_has_aec_bench_provider(tmp_path: Path) -> None:
    """AecBenchProvider must be registered in the app COMMANDS set."""
    app = _make_app(tmp_path)
    from aec_bench.tui.commands import AecBenchProvider

    assert AecBenchProvider in app.COMMANDS


@pytest.mark.anyio
async def test_aec_bench_provider_discover_yields_screens(tmp_path: Path) -> None:
    """The provider's discover() should yield hits for every screen entry."""
    from aec_bench.tui.commands import AecBenchProvider
    from aec_bench.tui.commands.screens import SCREEN_ENTRIES

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        hits = [hit async for hit in provider.discover()]
        # We expect at least one hit per screen entry plus action entries
        assert len(hits) >= len(SCREEN_ENTRIES)


@pytest.mark.anyio
async def test_aec_bench_provider_discover_yields_actions(tmp_path: Path) -> None:
    """The provider's discover() should include action entries."""
    from aec_bench.tui.commands import AecBenchProvider
    from aec_bench.tui.commands.actions import ACTION_ENTRIES

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        hits = [hit async for hit in provider.discover()]
        hit_help = [h.help for h in hits]
        for action in ACTION_ENTRIES:
            assert action.description in hit_help


@pytest.mark.anyio
async def test_aec_bench_provider_search_matches_dashboard(tmp_path: Path) -> None:
    """Searching 'dashboard' should return at least one hit."""
    from aec_bench.tui.commands import AecBenchProvider

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        hits = [hit async for hit in provider.search("dashboard")]
        assert len(hits) >= 1


@pytest.mark.anyio
async def test_aec_bench_provider_search_no_match(tmp_path: Path) -> None:
    """Searching gibberish should return zero hits."""
    from aec_bench.tui.commands import AecBenchProvider

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        hits = [hit async for hit in provider.search("zzzzzxyzqqq")]
        assert len(hits) == 0


@pytest.mark.anyio
async def test_aec_bench_provider_opens_concrete_dataset_screen(tmp_path: Path) -> None:
    """Command palette entries with concrete screens should open that screen."""
    from aec_bench.tui.commands import AecBenchProvider
    from aec_bench.tui.commands.screens import SCREEN_ENTRIES
    from aec_bench.tui.screens.datasets import DatasetsScreen

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        entry = next(item for item in SCREEN_ENTRIES if item.name == "Datasets")
        provider._open_screen_entry(entry)
        await pilot.pause()
        assert isinstance(app.screen, DatasetsScreen)


@pytest.mark.anyio
async def test_aec_bench_provider_opens_concrete_compare_screen(tmp_path: Path) -> None:
    """Compare should no longer collapse to the generic analyse mode."""
    from aec_bench.tui.commands import AecBenchProvider
    from aec_bench.tui.commands.screens import SCREEN_ENTRIES
    from aec_bench.tui.screens.compare import CompareScreen

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        entry = next(item for item in SCREEN_ENTRIES if item.name == "Compare")
        provider._open_screen_entry(entry)
        await pilot.pause()
        assert isinstance(app.screen, CompareScreen)


@pytest.mark.anyio
async def test_aec_bench_provider_trial_hit_opens_selected_viewer(tmp_path: Path) -> None:
    """Trial search callbacks should open the selected trial, not just generic review."""
    from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
    from aec_bench.contracts.trial_record import AgentReference, TaskReference
    from aec_bench.ledger.writer import write_trial_record
    from aec_bench.tui.commands import AecBenchProvider
    from aec_bench.tui.commands.trials import TrialHit
    from aec_bench.tui.screens.viewer import TrialViewerScreen
    from tests.support.trial_record_factories import make_trial_record

    ledger = tmp_path / "ledger"
    tasks = tmp_path / "tasks"
    tasks.mkdir()
    valid = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)
    for trial_id, task_id in [
        ("trial-a", "electrical/voltage-drop"),
        ("trial-b", "civil/drainage"),
    ]:
        write_trial_record(
            ledger_root=ledger,
            record=make_trial_record(
                trial_id=trial_id,
                experiment_id="exp-search",
                task=TaskReference(task_id=task_id, task_revision="sha"),
                agent=AgentReference(adapter="rlm", model="sonnet", adapter_revision="1.0"),
                evaluation=EvaluationResult(reward=0.75, validity=valid),
            ),
        )

    app = AecBenchTUI(ledger_root=ledger, tasks_root=tasks)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        callback = provider._make_trial_callback(
            TrialHit(
                trial_id="trial-b",
                experiment_id="exp-search",
                task_id="civil/drainage",
                model="sonnet",
                reward=0.75,
            )
        )
        await callback()
        await pilot.pause()
        assert isinstance(app.screen, TrialViewerScreen)
        assert app.screen._record.trial_id == "trial-b"


@pytest.mark.anyio
async def test_aec_bench_provider_experiment_hit_opens_filtered_triage(tmp_path: Path) -> None:
    """Experiment search callbacks should carry the selected experiment id."""
    from aec_bench.tui.commands import AecBenchProvider
    from aec_bench.tui.commands.experiments import ExperimentHit
    from aec_bench.tui.screens.triage import TriageScreen

    app = _make_app(tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        provider = AecBenchProvider(app.screen)
        callback = provider._make_experiment_callback(ExperimentHit(experiment_id="exp-selected", trial_count=3))
        await callback()
        await pilot.pause()
        assert isinstance(app.screen, TriageScreen)
        assert app.screen.experiment_id == "exp-selected"


# ------------------------------------------------------------------
# Final integration smoke test
# ------------------------------------------------------------------


@pytest.mark.anyio
async def test_full_upgraded_app_smoke(tmp_path: Path) -> None:
    """Smoke test: app starts, switch all modes, verify real screens, no crashes."""
    from aec_bench.contracts.evaluation_result import EvaluationResult, ValidityCheck
    from aec_bench.contracts.trial_record import AgentReference, TaskReference
    from aec_bench.ledger.writer import write_trial_record
    from aec_bench.tui.screens.dashboard import DashboardScreen
    from tests.support.trial_record_factories import make_trial_record

    ledger = tmp_path / "ledger"
    _VALID = ValidityCheck(output_parseable=True, schema_valid=True, verifier_completed=True)
    record = make_trial_record(
        trial_id="smoke-t1",
        experiment_id="smoke-exp",
        task=TaskReference(task_id="electrical/voltage-drop", task_revision="sha"),
        agent=AgentReference(adapter="rlm", model="sonnet", adapter_revision="1.0"),
        evaluation=EvaluationResult(reward=0.85, validity=_VALID),
    )
    write_trial_record(ledger_root=ledger, record=record)

    tasks = tmp_path / "tasks"
    tasks.mkdir()
    app = AecBenchTUI(ledger_root=ledger, tasks_root=tasks)

    async with app.run_test() as pilot:
        await pilot.pause()
        # Starts in dashboard mode
        assert app.current_mode == "dashboard"
        assert isinstance(app.screen, DashboardScreen)

        # Switch to each mode
        for key, mode in [("e", "explore"), ("r", "review"), ("a", "analyse")]:
            # Unfocus any widgets that might capture keys
            app.screen.set_focus(None)
            await pilot.press(key)
            await pilot.pause()
            assert app.current_mode == mode

        # Return to dashboard
        app.screen.set_focus(None)
        await pilot.press("d")
        await pilot.pause()
        assert app.current_mode == "dashboard"

        # Command palette is available
        assert app.ENABLE_COMMAND_PALETTE is True
        from aec_bench.tui.commands import AecBenchProvider

        assert AecBenchProvider in app.COMMANDS
