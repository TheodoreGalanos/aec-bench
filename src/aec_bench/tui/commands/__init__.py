# ABOUTME: Command Palette providers for the aec-bench TUI.
# ABOUTME: AecBenchProvider aggregates search across screens, trials, tasks, datasets, experiments.

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, cast

from textual.command import DiscoveryHit, Hit, Hits, Provider

from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.tui.commands.actions import ACTION_ENTRIES, ActionEntry
from aec_bench.tui.commands.experiments import ExperimentHit, search_experiments
from aec_bench.tui.commands.screens import SCREEN_ENTRIES, ScreenEntry
from aec_bench.tui.commands.trials import TrialHit, search_trials

if TYPE_CHECKING:
    from aec_bench.tui.app import AecBenchTUI


class AecBenchProvider(Provider):
    """Aggregated Command Palette provider for the aec-bench TUI.

    Exposes screen navigation and quick actions via Ctrl+P. Screen entries
    switch the app mode; action entries run the named Textual action directly.
    Trial and experiment search is wired in when ledger_root is available.
    """

    _records_cache: dict[Path, list[TrialRecord]] = {}

    @property
    def _aec_app(self) -> AecBenchTUI:
        """Return the concrete application surface owned by this provider."""
        return cast("AecBenchTUI", self.app)

    async def discover(self) -> Hits:
        """Yield all discoverable commands (shown before the user types)."""
        for entry in SCREEN_ENTRIES:
            help_parts = [entry.description]
            if entry.keybind:
                help_parts.append(f"[{entry.keybind}]")
            yield DiscoveryHit(
                display=entry.name,
                command=self._make_screen_callback(entry),
                text=f"{entry.name} {entry.description}",
                help=" ".join(help_parts),
            )

        for action in ACTION_ENTRIES:
            yield DiscoveryHit(
                display=action.name,
                command=self._make_action_callback(action),
                text=f"{action.name} {action.description}",
                help=action.description,
            )

    async def search(self, query: str) -> Hits:
        """Yield hits matching the query across screens, actions, trials, and experiments."""
        matcher = self.matcher(query)

        for entry in SCREEN_ENTRIES:
            searchable = f"{entry.name} {entry.description}"
            score = matcher.match(searchable)
            if score > 0:
                help_parts = [entry.description]
                if entry.keybind:
                    help_parts.append(f"[{entry.keybind}]")
                yield Hit(
                    score,
                    matcher.highlight(entry.name),
                    self._make_screen_callback(entry),
                    help=" ".join(help_parts),
                )

        for action in ACTION_ENTRIES:
            searchable = f"{action.name} {action.description}"
            score = matcher.match(searchable)
            if score > 0:
                yield Hit(
                    score,
                    matcher.highlight(action.name),
                    self._make_action_callback(action),
                    help=action.description,
                )

        # Trial and experiment search (requires ledger_root on the app)
        if hasattr(self.app, "ledger_root"):
            records = self._get_cached_records()

            # Trial hits
            trial_hits = search_trials(records, query)
            for hit in trial_hits[:10]:
                display = f"{hit.task_id} ({hit.model})"
                score = matcher.match(display)
                if score > 0:
                    yield Hit(
                        score,
                        matcher.highlight(display),
                        self._make_trial_callback(hit),
                        help=f"Trial: {hit.trial_id} — reward {hit.reward:.2f}",
                    )

            # Experiment hits
            experiment_entries = self._build_experiment_entries(records)
            experiment_hits = search_experiments(experiment_entries, query)
            for exp_hit in experiment_hits[:10]:
                display = f"Experiment: {exp_hit.experiment_id}"
                score = matcher.match(display)
                if score > 0:
                    yield Hit(
                        score,
                        matcher.highlight(display),
                        self._make_experiment_callback(exp_hit),
                        help=f"{exp_hit.trial_count} trials",
                    )

    def _get_cached_records(self) -> list[TrialRecord]:
        """Return cached trial records, loading from ledger on first access."""
        ledger_root = self._aec_app.ledger_root
        if ledger_root not in AecBenchProvider._records_cache:
            from aec_bench.ledger.reader import read_trial_records

            try:
                AecBenchProvider._records_cache[ledger_root] = read_trial_records(ledger_root)
            except Exception:
                AecBenchProvider._records_cache[ledger_root] = []
        return AecBenchProvider._records_cache[ledger_root]

    def _build_experiment_entries(
        self,
        records: Sequence[TrialRecord],
    ) -> list[ExperimentHit]:
        """Aggregate trial records into experiment entries for search."""
        from collections import Counter

        counts: Counter[str] = Counter()
        for record in records:
            counts[record.experiment_id] += 1
        return [ExperimentHit(experiment_id=exp_id, trial_count=count) for exp_id, count in counts.items()]

    def _make_screen_callback(
        self,
        entry: ScreenEntry,
    ) -> Callable[[], Awaitable[None]]:
        """Return an async callable that opens the entry's mode or concrete screen."""

        async def callback() -> None:
            self._open_screen_entry(entry)

        return callback

    def _open_screen_entry(self, entry: ScreenEntry) -> None:
        """Open a mode-level or concrete screen entry from the command palette."""
        app = self._aec_app
        if entry.screen is None:
            app.switch_mode(entry.mode)
            return

        app.switch_mode(entry.mode)

        if entry.screen == "datasets":
            from aec_bench.tui.screens.datasets import DatasetsScreen

            app.push_screen(
                DatasetsScreen(
                    datasets_root=app.datasets_root,
                    ledger_root=app.ledger_root,
                )
            )
            return

        if entry.screen == "leaderboard":
            from aec_bench.tui.screens.leaderboard import LeaderboardScreen

            app.push_screen(
                LeaderboardScreen(
                    ledger_root=app.ledger_root,
                    experiment_id=app.initial_experiment_id,
                )
            )
            return

        if entry.screen == "compare":
            from aec_bench.tui.screens.compare import CompareScreen

            app.push_screen(
                CompareScreen(
                    ledger_root=app.ledger_root,
                    experiment_id=app.initial_experiment_id,
                )
            )
            return

        if entry.screen == "review":
            feedback_root = app.feedback_root
            reviewer_id = app.reviewer_id
            if feedback_root is None or reviewer_id is None:
                app.switch_mode("review")
                return
            from aec_bench.tui.screens.review import ReviewScreen

            app.push_screen(
                ReviewScreen(
                    ledger_root=app.ledger_root,
                    tasks_root=app.tasks_root,
                    feedback_root=feedback_root,
                    reviewer_id=reviewer_id,
                )
            )

    def _make_action_callback(
        self,
        action: ActionEntry,
    ) -> Callable[[], Awaitable[None]]:
        """Return an async callable that runs the named Textual action."""

        async def callback() -> None:
            await self._aec_app.run_action(action.action_name)

        return callback

    def _make_trial_callback(
        self,
        hit: TrialHit,
    ) -> Callable[[], Awaitable[None]]:
        """Return an async callable that opens the selected trial in the viewer."""

        async def callback() -> None:
            records = self._get_cached_records()
            record = next((item for item in records if item.trial_id == hit.trial_id), None)
            if record is None:
                self._aec_app.switch_mode("review")
                return
            siblings = [item for item in records if item.experiment_id == hit.experiment_id]
            from aec_bench.tui.screens.viewer import TrialViewerScreen

            self._aec_app.switch_mode("review")
            self._aec_app.push_screen(TrialViewerScreen(record=record, siblings=siblings))

        return callback

    def _make_experiment_callback(
        self,
        hit: ExperimentHit,
    ) -> Callable[[], Awaitable[None]]:
        """Return an async callable that opens triage filtered to the experiment."""

        async def callback() -> None:
            from aec_bench.tui.screens.triage import TriageScreen

            self._aec_app.switch_mode("review")
            self._aec_app.push_screen(
                TriageScreen(
                    ledger_root=self._aec_app.ledger_root,
                    experiment_id=hit.experiment_id,
                )
            )

        return callback
