# ABOUTME: Library screen for browsing the AEC-Bench task collection and datasets.
# ABOUTME: Shows seeds, templates, instances, and datasets with bar charts and detail pane.

from __future__ import annotations

import textwrap
import tomllib
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Static, Tree

from aec_bench.contracts.dataset import DatasetManifest
from aec_bench.contracts.trial_record import TrialRecord
from aec_bench.dataset.storage import list_datasets
from aec_bench.generation.discovery import (
    LibrarySeed,
    LibraryTemplate,
    scan_seeds,
    scan_templates,
)
from aec_bench.ledger.reader import query_trial_records
from aec_bench.tui.widgets.shared import reward_style


@dataclass(frozen=True)
class LibraryInstance:
    """A concrete task instance with task.toml and instruction.md."""

    discipline: str
    category: str
    task_name: str
    instance_name: str
    difficulty: str
    path: Path
    has_dockerfile: bool
    has_verifier: bool
    tags: tuple[str, ...]


@dataclass(frozen=True)
class LibrarySummary:
    """Aggregate statistics for the library."""

    total_seeds: int
    total_templates: int
    total_instances: int
    total_categories: int
    seeds_by_discipline: dict[str, int]
    complexity_counts: dict[str, int]


def scan_instances(tasks_root: Path) -> list[LibraryInstance]:
    """Scan task instances that have task.toml + instruction.md."""
    if not tasks_root.is_dir():
        return []
    instances: list[LibraryInstance] = []
    for toml_path in sorted(tasks_root.rglob("task.toml")):
        instruction_path = toml_path.parent / "instruction.md"
        if not instruction_path.exists():
            continue
        try:
            raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
            metadata = raw.get("metadata", {})
            parts = toml_path.parent.relative_to(tasks_root).parts
            discipline = parts[0] if len(parts) >= 1 else "unknown"
            category = parts[1] if len(parts) >= 2 else discipline
            task_name = parts[2] if len(parts) >= 3 else parts[-1]
            instance_name = parts[-1]
            instances.append(
                LibraryInstance(
                    discipline=discipline,
                    category=category,
                    task_name=task_name,
                    instance_name=instance_name,
                    difficulty=metadata.get("difficulty", "unknown"),
                    path=toml_path.parent,
                    has_dockerfile=(toml_path.parent / "environment" / "Dockerfile").exists(),
                    has_verifier=(
                        (toml_path.parent / "tests" / "verify.py").exists()
                        or (toml_path.parent / "tests" / "test.sh").exists()
                    ),
                    tags=tuple(metadata.get("tags", [])),
                )
            )
        except (tomllib.TOMLDecodeError, KeyError):
            continue
    return instances


def build_summary(
    seeds: list[LibrarySeed],
    templates: list[LibraryTemplate],
    instances: list[LibraryInstance],
) -> LibrarySummary:
    """Build aggregate statistics from scanned data."""
    disc_counts: dict[str, int] = {}
    comp_counts: dict[str, int] = {}
    categories: set[str] = set()
    for seed in seeds:
        disc_counts[seed.discipline] = disc_counts.get(seed.discipline, 0) + 1
        comp_counts[seed.complexity] = comp_counts.get(seed.complexity, 0) + 1
        categories.add(seed.category)
    return LibrarySummary(
        total_seeds=len(seeds),
        total_templates=len(templates),
        total_instances=len(instances),
        total_categories=len(categories),
        seeds_by_discipline=disc_counts,
        complexity_counts=comp_counts,
    )


# ---------------------------------------------------------------------------
# Bar chart renderer
# ---------------------------------------------------------------------------


def render_bar_chart(data: dict[str, int], *, max_width: int = 20, color: str = "#61AAF2") -> str:
    """Render a horizontal bar chart as Rich markup."""
    if not data:
        return ""
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=True)
    max_val = max(v for _, v in sorted_items) if sorted_items else 1
    max_label = max(len(k) for k, _ in sorted_items)
    max_num_width = max(len(str(v)) for _, v in sorted_items)
    lines: list[str] = []
    for label, value in sorted_items:
        bar_len = int((value / max_val) * max_width) if max_val > 0 else 0
        bar = "\u2588" * bar_len + "\u2591" * (max_width - bar_len)
        lines.append(f"  {label:<{max_label}}  [{color}]{bar}[/] {value:>{max_num_width}}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Detail pane renderers — each returns a Rich markup string
# ---------------------------------------------------------------------------


def _section(title: str, body: str) -> str:
    """Format a titled section with Rich markup."""
    return f"[bold]{title}[/bold]\n{body}\n"


def render_seed_detail(
    seed: LibrarySeed,
    *,
    has_template: bool,
    instance_count: int,
    template: LibraryTemplate | None = None,
) -> str:
    """Render detail pane for a seed task."""
    parts: list[str] = []
    parts.append(f"[bold underline]{seed.task_name}[/bold underline]")
    parts.append(f"[dim]seed \u2022 {seed.discipline} \u2022 {seed.category}[/dim]")
    parts.append(f"[dim]{'─' * 50}[/dim]\n")

    # Show template long_description if available, otherwise seed description
    long_desc = ""
    if template:
        long_desc = template.params_raw.get("meta", {}).get("long_description", "")
    desc_text = long_desc if long_desc else seed.description
    parts.append(textwrap.fill(desc_text, width=75) + "\n")

    # Show tags from template if available
    if template:
        tags = template.params_raw.get("meta", {}).get("tags", [])
        if tags:
            tag_str = " ".join(f"[cyan]#{t}[/cyan]" for t in tags)
            parts.append(f"{tag_str}\n")

    if seed.complexity:
        parts.append(f"[bold]Complexity:[/bold] {seed.complexity}\n")

    if seed.standards:
        standards_str = ", ".join(seed.standards)
        parts.append(_section("Standards", f"  {standards_str}"))

    if seed.inputs:
        inputs_str = "\n".join(f"    \u2022 {inp}" for inp in seed.inputs)
        parts.append(_section("Inputs", inputs_str))

    if seed.outputs:
        outputs_str = "\n".join(f"    \u2022 {out}" for out in seed.outputs)
        parts.append(_section("Outputs", outputs_str))

    # Pipeline status
    seed_mark = "[green]\u2713[/green]"
    template_mark = "[green]\u2713[/green]" if has_template else "[red]\u2717[/red]"
    instance_str = f"{instance_count}" if instance_count > 0 else "[dim]0[/dim]"
    pipeline = f"  Seed {seed_mark}  \u2192  Template {template_mark}  \u2192  Instances {instance_str}"
    parts.append(_section("Pipeline", pipeline))

    if not has_template:
        parts.append("[dim italic]Tip: Use /create-template to build a template from this seed.[/dim italic]")

    return "\n".join(parts)


def render_template_detail(template: LibraryTemplate) -> str:
    """Render detail pane for a template."""
    raw = template.params_raw
    meta = raw.get("meta", {})
    parts: list[str] = []

    # Header with category and discipline
    category = meta.get("category", "")
    parts.append(f"[bold underline]{template.task_id}[/bold underline]")
    parts.append(f"[dim]template \u2022 {template.discipline} \u2022 {category}[/dim]")
    parts.append(f"[dim]{'─' * 50}[/dim]\n")

    # Long description (paragraph) if available, otherwise short description
    long_description = meta.get("long_description", "")
    description = meta.get("description", "")
    desc_text = long_description if long_description else description
    if desc_text:
        parts.append(textwrap.fill(desc_text, width=75) + "\n")

    # Tags
    tags = meta.get("tags", [])
    if tags:
        tag_str = " ".join(f"[cyan]#{t}[/cyan]" for t in tags)
        parts.append(f"{tag_str}\n")

    # Standards
    standards = meta.get("standards", [])
    if standards:
        parts.append(_section("Standards", "  " + ", ".join(standards)))

    # Parameters
    params = raw.get("params", {})
    if params:
        param_lines: list[str] = []
        for name, spec in params.items():
            p_type = spec.get("type", "?")
            p_min = spec.get("min", "")
            p_max = spec.get("max", "")
            p_unit = spec.get("unit", "")
            range_str = ""
            if p_min != "" or p_max != "":
                range_str = f" [{p_min}\u2013{p_max}]"
            unit_str = f" ({p_unit})" if p_unit else ""
            param_lines.append(f"    {name}: {p_type}{range_str}{unit_str}")
        parts.append(_section("Parameters", "\n".join(param_lines)))

    # Outputs
    outputs = raw.get("outputs", {})
    if outputs:
        output_lines: list[str] = []
        for name, spec in outputs.items():
            desc = spec.get("description", "")
            tol = spec.get("tolerance", "")
            tol_str = f" (\u00b1{tol})" if tol else ""
            output_lines.append(f"    {name}: {desc}{tol_str}")
        parts.append(_section("Outputs", "\n".join(output_lines)))

    # Archetypes
    archetypes = raw.get("archetypes", {})
    if archetypes:
        arch_lines: list[str] = []
        for name, spec in archetypes.items():
            desc = spec.get("description", name)
            arch_lines.append(f"    \u2022 {name}: {desc}")
        parts.append(_section("Archetypes", "\n".join(arch_lines)))

    # Difficulty presets
    difficulty = raw.get("difficulty", {})
    if difficulty:
        diff_lines: list[str] = []
        for level, spec in difficulty.items():
            desc = spec.get("description", level)
            diff_lines.append(f"    {level}: {desc}")
        parts.append(_section("Difficulty Presets", "\n".join(diff_lines)))

    # Pipeline status
    parts.append(
        _section(
            "Pipeline",
            "  Seed \u2192  Template [green]\u2713[/green]  \u2192  Instances",
        )
    )

    return "\n".join(parts)


def render_instance_detail(instance: LibraryInstance) -> str:
    """Render detail pane for a task instance."""
    parts: list[str] = []

    parts.append(f"[bold underline]{instance.instance_name}[/bold underline]")
    parts.append(
        f"  [dim]instance \u2022 {instance.discipline} \u2022 {instance.category} \u2022 {instance.task_name}[/dim]\n"
    )

    parts.append(f"[bold]Difficulty:[/bold] {instance.difficulty}")
    if instance.tags:
        parts.append(f"[bold]Tags:[/bold] {', '.join(instance.tags)}")
    parts.append("")

    # Instruction preview
    instruction_path = instance.path / "instruction.md"
    if instruction_path.is_file():
        try:
            text = instruction_path.read_text(encoding="utf-8")
            preview = text[:150].replace("\n", " ").strip()
            if len(text) > 150:
                preview += "\u2026"
            parts.append(_section("Instruction Preview", f"  {preview}"))
        except OSError:
            pass

    # Environment checks
    docker_mark = "[green]\u2713[/green]" if instance.has_dockerfile else "[dim]\u2717[/dim]"
    verify_mark = "[green]\u2713[/green]" if instance.has_verifier else "[dim]\u2717[/dim]"
    env_lines = f"    Dockerfile {docker_mark}\n    Verifier   {verify_mark}"
    parts.append(_section("Environment", env_lines))

    # Pipeline status
    parts.append(
        _section(
            "Pipeline",
            f"  Seed \u2192  Template \u2192  Instance [green]\u2713[/green] ({instance.instance_name})",
        )
    )

    return "\n".join(parts)


def render_discipline_detail(
    discipline: str,
    seeds: Sequence[LibrarySeed],
    *,
    template_count: int,
    instance_count: int,
) -> str:
    """Render detail pane for a discipline overview."""
    parts: list[str] = []

    parts.append(f"[bold underline]{discipline.title()}[/bold underline]")
    parts.append("  [dim]discipline[/dim]\n")

    seed_count = len(seeds)
    parts.append(f"[bold]Seeds:[/bold] {seed_count}")
    parts.append(f"[bold]Templates:[/bold] {template_count}")
    parts.append(f"[bold]Instances:[/bold] {instance_count}")
    parts.append("")

    # Top categories by seed count
    cat_counts = Counter(s.category for s in seeds)
    if cat_counts:
        cat_lines: list[str] = []
        for cat, count in cat_counts.most_common():
            cat_lines.append(f"    {cat}: {count}")
        parts.append(_section("Categories", "\n".join(cat_lines)))

    # Complexity breakdown
    comp_counts = Counter(s.complexity for s in seeds)
    if comp_counts:
        comp_lines: list[str] = []
        for comp, count in comp_counts.most_common():
            comp_lines.append(f"    {comp}: {count}")
        parts.append(_section("Complexity", "\n".join(comp_lines)))

    # Pipeline coverage
    if seed_count > 0:
        coverage_pct = (template_count / seed_count * 100) if seed_count else 0
        parts.append(
            _section(
                "Pipeline Coverage",
                f"    {template_count}/{seed_count} seeds have templates ({coverage_pct:.0f}%)",
            )
        )

    return "\n".join(parts)


def render_category_detail(
    category: str,
    seeds: Sequence[LibrarySeed],
    *,
    template_ids: set[str],
) -> str:
    """Render detail pane for a category listing."""
    parts: list[str] = []

    parts.append(f"[bold underline]{category}[/bold underline]")
    if seeds:
        parts.append(f"  [dim]{seeds[0].discipline} \u2022 category[/dim]\n")
    else:
        parts.append("  [dim]category[/dim]\n")

    parts.append(f"[bold]Seeds:[/bold] {len(seeds)}\n")

    # List each seed with status marker
    if seeds:
        seed_lines: list[str] = []
        for seed in sorted(seeds, key=lambda s: s.task_id):
            marker = "\u25c6" if seed.task_id in template_ids else "\u00b7"
            seed_lines.append(f"    {marker} {seed.task_id} [{seed.complexity}]")
        parts.append(_section("Tasks", "\n".join(seed_lines)))

    # Union of standards across all seeds
    all_standards: set[str] = set()
    for seed in seeds:
        all_standards.update(seed.standards)
    if all_standards:
        parts.append(_section("Standards", "    " + ", ".join(sorted(all_standards))))

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tree node data carrier
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LibraryNodeData:
    """Metadata attached to each tree node for dispatch in the detail pane."""

    kind: Literal[
        "discipline",
        "category",
        "seed",
        "template",
        "instance",
        "dataset",
        "dataset_experiment",
    ]
    label: str
    discipline: str = ""
    category: str = ""
    task_id: str = ""
    instance_name: str = ""
    dataset_id: str = ""
    experiment_id: str = ""


# ---------------------------------------------------------------------------
# View / filter cycles
# ---------------------------------------------------------------------------

_VIEW_CYCLE: list[Literal["discipline", "category", "datasets"]] = [
    "discipline",
    "category",
    "datasets",
]

_DISCIPLINE_CYCLE: list[str] = [
    "all",
    "civil",
    "electrical",
    "ground",
    "mechanical",
    "structural",
]


def _next_in_cycle(current: str, cycle: list[str]) -> str:
    """Return the next value in a cycle list, wrapping around."""
    idx = cycle.index(current) if current in cycle else 0
    return cycle[(idx + 1) % len(cycle)]


# ---------------------------------------------------------------------------
# Library screen
# ---------------------------------------------------------------------------


class LibraryScreen(Screen):
    """Browsable inventory of all benchmark seeds, templates, and instances."""

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("b", "go_back", "Back"),
        Binding("enter", "toggle_node", "Expand", priority=True),
        Binding("v", "cycle_view", "View"),
        Binding("m", "cycle_discipline", "Discipline"),
        Binding("s", "push_datasets", "Datasets", show=True),
        Binding("o", "push_leaderboard", "Leaderboard", show=True),
        Binding("j", "cursor_down", show=False),
        Binding("k", "cursor_up", show=False),
        Binding("tab", "focus_next", "Next pane"),
        Binding("shift+tab", "focus_previous", show=False),
    ]

    CSS = """
    .library-summary-panel {
        height: 10;
        border: round #40403E;
        padding: 0 2;
        margin: 0 1;
    }

    .library-tree-panel {
        width: 1fr;
        min-width: 30;
        border: round #40403E;
        padding: 1 1;
        margin: 0 1 0 0;
    }

    .library-details-panel {
        width: 2fr;
        border: round #40403E;
        padding: 1 2;
    }

    .library-columns {
        height: 1fr;
        margin: 0 1;
    }

    """

    def __init__(
        self,
        *,
        tasks_root: Path,
        templates_root: Path | None = None,
        datasets_root: Path | None = None,
        ledger_root: Path | None = None,
    ) -> None:
        super().__init__()
        self._tasks_root = tasks_root
        if templates_root is None:
            templates_root = tasks_root.parent / "src" / "aec_bench" / "templates" / "builtin"
        self._templates_root = templates_root
        self._datasets_root = datasets_root
        self._ledger_root = ledger_root

        # Populated on mount
        self._seeds: list[LibrarySeed] = []
        self._templates: list[LibraryTemplate] = []
        self._instances: list[LibraryInstance] = []
        self._summary: LibrarySummary = build_summary([], [], [])
        self._template_ids: set[tuple[str, str]] = set()

        # Dataset data (populated on mount if datasets_root provided)
        self._dataset_manifests: list[DatasetManifest] = []
        self._dataset_records: dict[str, list[TrialRecord]] = {}

        # View state
        self._view: Literal["discipline", "category", "datasets"] = "discipline"
        self._discipline_filter: str = "all"

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(id="library-summary", markup=True, classes="library-summary-panel")
            with Horizontal(classes="library-columns"):
                with Container(classes="library-tree-panel"):
                    yield Tree("Library", id="library-tree")
                with Container(classes="library-details-panel"):
                    yield VerticalScroll(
                        Static("", id="library-details", markup=True),
                    )
        yield Footer()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        tree = self.query_one("#library-tree", Tree)
        tree.loading = True
        self._load_tree()

    @work(thread=True, exclusive=True)
    def _load_tree(self) -> None:
        """Scan the filesystem in a background thread, then update the UI."""
        seeds = scan_seeds(self._tasks_root)
        templates = scan_templates(self._templates_root)
        instances = scan_instances(self._tasks_root)
        summary = build_summary(seeds, templates, instances)
        template_ids = {(t.discipline, t.task_id) for t in templates}

        # Load datasets if configured
        dataset_manifests: list[DatasetManifest] = []
        dataset_records: dict[str, list[TrialRecord]] = {}
        if self._datasets_root is not None:
            dataset_manifests = list_datasets(self._datasets_root)
            if self._ledger_root is not None:
                for m in dataset_manifests:
                    dataset_id = f"{m.name}@{m.version}"
                    records = query_trial_records(self._ledger_root, dataset_id=dataset_id)
                    if records:
                        dataset_records[dataset_id] = records

        self.app.call_from_thread(
            self._apply_loaded_data,
            seeds,
            templates,
            instances,
            summary,
            template_ids,
            dataset_manifests,
            dataset_records,
        )

    def _apply_loaded_data(
        self,
        seeds: list[LibrarySeed],
        templates: list[LibraryTemplate],
        instances: list[LibraryInstance],
        summary: LibrarySummary,
        template_ids: set[tuple[str, str]],
        dataset_manifests: list[DatasetManifest],
        dataset_records: dict[str, list[TrialRecord]],
    ) -> None:
        """Apply data loaded by the background worker and refresh the UI."""
        self._seeds = seeds
        self._templates = templates
        self._instances = instances
        self._summary = summary
        self._template_ids = template_ids
        self._dataset_manifests = dataset_manifests
        self._dataset_records = dataset_records

        tree = self.query_one("#library-tree", Tree)
        tree.loading = False

        self._render_summary()
        self._populate_tree()

    # ------------------------------------------------------------------
    # Summary panel
    # ------------------------------------------------------------------

    def _render_summary(self) -> None:
        """Render the top summary panel with bar charts."""
        summary_widget = self.query_one("#library-summary", Static)
        s = self._summary

        header = (
            f"[bold]Library[/bold]  "
            f"{s.total_seeds} seeds · "
            f"{s.total_templates} templates · "
            f"{s.total_instances} instances · "
            f"{s.total_categories} categories"
        )

        if not self._seeds:
            summary_widget.update(f"{header}\n\n[dim]No tasks found.[/dim]")
            return

        disc_chart = render_bar_chart(s.seeds_by_discipline, max_width=25)
        comp_chart = render_bar_chart(s.complexity_counts, max_width=25, color="#D4A27F")

        parts = [
            header,
            "",
            f"  [dim]{'Seeds by discipline':<50}Complexity[/dim]",
        ]
        # Merge charts side by side with fixed-width left column
        disc_lines = disc_chart.split("\n") if disc_chart else []
        comp_lines = comp_chart.split("\n") if comp_chart else []
        max_rows = max(len(disc_lines), len(comp_lines))
        for i in range(max_rows):
            left = disc_lines[i] if i < len(disc_lines) else ""
            right = comp_lines[i] if i < len(comp_lines) else ""
            # Use a fixed-width padded left column (50 chars visible width)
            # Rich markup makes len() unreliable, so pad generously
            parts.append(f"{left:<50}       {right}")

        summary_widget.update("\n".join(parts))

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _populate_tree(self) -> None:
        """Build the tree based on the current view and discipline filter."""
        tree = self.query_one("#library-tree", Tree)
        tree.clear()
        tree.show_root = False
        tree.auto_expand = False
        tree.guide_depth = 2

        if self._view == "datasets":
            self._populate_datasets_view(tree)
        else:
            seeds = self._filtered_seeds()
            if not seeds:
                details = self.query_one("#library-details", Static)
                details.update("[dim]No tasks found.[/dim]")
                return
            if self._view == "discipline":
                self._populate_discipline_view(tree, seeds)
            else:
                self._populate_category_view(tree, seeds)

        tree.focus()

    def _filtered_seeds(self) -> list[LibrarySeed]:
        """Return seeds filtered by the current discipline filter."""
        seeds = self._seeds
        if self._discipline_filter != "all":
            seeds = [s for s in seeds if s.discipline == self._discipline_filter]
        return list(seeds)

    def _populate_discipline_view(self, tree: Tree[LibraryNodeData], seeds: list[LibrarySeed]) -> None:
        """Populate tree grouped by discipline > category > task."""
        by_disc: dict[str, list[LibrarySeed]] = defaultdict(list)
        for seed in seeds:
            by_disc[seed.discipline].append(seed)

        for disc_name in sorted(by_disc):
            disc_seeds = by_disc[disc_name]
            disc_node = tree.root.add(
                f"{disc_name} ({len(disc_seeds)})",
                data=LibraryNodeData(kind="discipline", label=disc_name, discipline=disc_name),
            )

            by_cat: dict[str, list[LibrarySeed]] = defaultdict(list)
            for seed in disc_seeds:
                by_cat[seed.category].append(seed)

            for cat_name in sorted(by_cat):
                cat_seeds = by_cat[cat_name]
                tmpl_count = sum(1 for s in cat_seeds if (s.discipline, s.task_id) in self._template_ids)
                if tmpl_count == len(cat_seeds):
                    cat_label = f"{cat_name} ({len(cat_seeds)}) [green]\u25c6{tmpl_count}[/]"
                elif tmpl_count > 0:
                    cat_label = f"{cat_name} ({len(cat_seeds)}) [yellow]\u25c6{tmpl_count}[/]"
                else:
                    cat_label = f"{cat_name} ({len(cat_seeds)})"
                cat_node = disc_node.add(
                    cat_label,
                    data=LibraryNodeData(
                        kind="category",
                        label=cat_name,
                        discipline=disc_name,
                        category=cat_name,
                    ),
                )

                for seed in sorted(cat_seeds, key=lambda s: s.task_id):
                    has_template = (seed.discipline, seed.task_id) in self._template_ids
                    matching_instances = [
                        inst
                        for inst in self._instances
                        if inst.discipline == seed.discipline and inst.task_name == seed.task_id
                    ]
                    marker = "\u25c6" if has_template else "\u00b7"
                    label = f"{marker} {seed.task_id}"
                    if matching_instances:
                        label += f" ({len(matching_instances)})"

                    if not matching_instances or (
                        len(matching_instances) == 1
                        and matching_instances[0].instance_name == matching_instances[0].task_name
                    ):
                        # Leaf node — no nested instances
                        cat_node.add_leaf(
                            label,
                            data=LibraryNodeData(
                                kind="seed",
                                label=seed.task_id,
                                discipline=seed.discipline,
                                category=seed.category,
                                task_id=seed.task_id,
                            ),
                        )
                    else:
                        # Expandable with instances
                        task_node = cat_node.add(
                            label,
                            data=LibraryNodeData(
                                kind="seed",
                                label=seed.task_id,
                                discipline=seed.discipline,
                                category=seed.category,
                                task_id=seed.task_id,
                            ),
                        )
                        for inst in sorted(matching_instances, key=lambda i: i.instance_name):
                            task_node.add_leaf(
                                f"  {inst.instance_name} [{inst.difficulty}]",
                                data=LibraryNodeData(
                                    kind="instance",
                                    label=inst.instance_name,
                                    discipline=inst.discipline,
                                    category=inst.category,
                                    task_id=inst.task_name,
                                    instance_name=inst.instance_name,
                                ),
                            )

    def _populate_category_view(self, tree: Tree[LibraryNodeData], seeds: list[LibrarySeed]) -> None:
        """Populate tree as a flat alphabetical list of categories."""
        by_cat: dict[str, list[LibrarySeed]] = defaultdict(list)
        for seed in seeds:
            by_cat[seed.category].append(seed)

        for cat_name in sorted(by_cat):
            cat_seeds = by_cat[cat_name]
            disc_label = cat_seeds[0].discipline if cat_seeds else ""
            tmpl_count = sum(1 for s in cat_seeds if (s.discipline, s.task_id) in self._template_ids)
            if tmpl_count == len(cat_seeds):
                badge = f" [green]\u25c6{tmpl_count}[/]"
            elif tmpl_count > 0:
                badge = f" [yellow]\u25c6{tmpl_count}[/]"
            else:
                badge = ""
            cat_node = tree.root.add(
                f"{cat_name} ({len(cat_seeds)}) [{disc_label}]{badge}",
                data=LibraryNodeData(
                    kind="category",
                    label=cat_name,
                    discipline=disc_label,
                    category=cat_name,
                ),
            )

            for seed in sorted(cat_seeds, key=lambda s: s.task_id):
                has_template = (seed.discipline, seed.task_id) in self._template_ids
                marker = "\u25c6" if has_template else "\u00b7"
                cat_node.add_leaf(
                    f"{marker} {seed.task_id}",
                    data=LibraryNodeData(
                        kind="seed",
                        label=seed.task_id,
                        discipline=seed.discipline,
                        category=seed.category,
                        task_id=seed.task_id,
                    ),
                )

    def _populate_datasets_view(self, tree: Tree[LibraryNodeData]) -> None:
        """Populate tree with datasets and their experiments."""
        if not self._dataset_manifests:
            details = self.query_one("#library-details", Static)
            details.update("[dim]No datasets found.[/dim]")
            return

        for manifest in self._dataset_manifests:
            dataset_id = f"{manifest.name}@{manifest.version}"
            n_tasks = len(manifest.tasks)
            records = self._dataset_records.get(dataset_id, [])
            n_experiments = len({r.experiment_id for r in records}) if records else 0

            label = f"{manifest.name} v{manifest.version}  ({n_tasks} tasks)"
            if n_experiments:
                label += f"  [{n_experiments} exp]"

            ds_node = tree.root.add(
                label,
                data=LibraryNodeData(
                    kind="dataset",
                    label=manifest.name,
                    dataset_id=dataset_id,
                ),
            )

            if records:
                by_exp: dict[str, list[TrialRecord]] = defaultdict(list)
                for r in records:
                    by_exp[r.experiment_id].append(r)
                for exp_id in sorted(by_exp):
                    exp_records = by_exp[exp_id]
                    mean_reward = sum(r.evaluation.reward for r in exp_records) / len(exp_records)
                    style = reward_style(mean_reward)
                    n_trials = len(exp_records)
                    exp_label = f"[{style}]\u25cf[/] {exp_id}  ({n_trials} trials  \u03bc {mean_reward:.2f})"
                    ds_node.add_leaf(
                        exp_label,
                        data=LibraryNodeData(
                            kind="dataset_experiment",
                            label=exp_id,
                            dataset_id=dataset_id,
                            experiment_id=exp_id,
                        ),
                    )

    # ------------------------------------------------------------------
    # Detail pane updates
    # ------------------------------------------------------------------

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted[LibraryNodeData]) -> None:
        """Update the details pane when a tree node is highlighted."""
        node = event.node
        data = node.data
        if data is None:
            return
        details = self.query_one("#library-details", Static)
        details.update(self._render_detail(data))

    def _render_detail(self, data: LibraryNodeData) -> str:
        """Dispatch to the appropriate detail renderer based on node kind."""
        if data.kind == "discipline":
            disc_seeds = [s for s in self._seeds if s.discipline == data.discipline]
            template_count = sum(1 for t in self._templates if t.discipline == data.discipline)
            instance_count = sum(1 for i in self._instances if i.discipline == data.discipline)
            return render_discipline_detail(
                data.discipline,
                disc_seeds,
                template_count=template_count,
                instance_count=instance_count,
            )

        if data.kind == "category":
            cat_seeds = [s for s in self._seeds if s.category == data.category and s.discipline == data.discipline]
            template_id_strs = {tid for _, tid in self._template_ids}
            return render_category_detail(data.category, cat_seeds, template_ids=template_id_strs)

        if data.kind == "seed":
            seed = next(
                (s for s in self._seeds if s.task_id == data.task_id and s.discipline == data.discipline),
                None,
            )
            if seed is None:
                return f"[dim]Seed not found: {data.task_id}[/dim]"
            has_template = (seed.discipline, seed.task_id) in self._template_ids
            instance_count = sum(
                1 for i in self._instances if i.discipline == seed.discipline and i.task_name == seed.task_id
            )
            template = next(
                (t for t in self._templates if t.discipline == seed.discipline and t.task_id == seed.task_id),
                None,
            )
            return render_seed_detail(
                seed,
                has_template=has_template,
                instance_count=instance_count,
                template=template,
            )

        if data.kind == "template":
            template = next(
                (t for t in self._templates if t.task_id == data.task_id and t.discipline == data.discipline),
                None,
            )
            if template is None:
                return f"[dim]Template not found: {data.task_id}[/dim]"
            return render_template_detail(template)

        if data.kind == "instance":
            instance = next(
                (
                    i
                    for i in self._instances
                    if i.instance_name == data.instance_name and i.discipline == data.discipline
                ),
                None,
            )
            if instance is None:
                return f"[dim]Instance not found: {data.instance_name}[/dim]"
            return render_instance_detail(instance)

        if data.kind == "dataset":
            from aec_bench.tui.screens.dataset import render_dataset_card

            manifest = next(
                (m for m in self._dataset_manifests if f"{m.name}@{m.version}" == data.dataset_id),
                None,
            )
            if manifest is None:
                return f"[dim]Dataset not found: {data.dataset_id}[/dim]"
            return render_dataset_card(manifest, self._dataset_records)

        if data.kind == "dataset_experiment":
            from aec_bench.tui.screens.dataset import render_experiment_card

            manifest = next(
                (m for m in self._dataset_manifests if f"{m.name}@{m.version}" == data.dataset_id),
                None,
            )
            if manifest is None:
                return f"[dim]Dataset not found: {data.dataset_id}[/dim]"
            records = self._dataset_records.get(data.dataset_id, [])
            exp_records = [r for r in records if r.experiment_id == data.experiment_id]
            return render_experiment_card(manifest, data.experiment_id, exp_records)

        return ""

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_go_back(self) -> None:
        if len(self.app.screen_stack) > 1:
            self.app.pop_screen()
        else:
            self.app.switch_mode("dashboard")

    def action_toggle_node(self) -> None:
        """Expand/collapse tree node, or drill-through to Triage for leaf nodes."""
        tree: Tree[LibraryNodeData] = self.query_one("#library-tree", Tree)
        node = tree.cursor_node
        if node is None:
            return
        data = node.data
        if data is not None and data.kind == "dataset_experiment" and self._ledger_root:
            from aec_bench.tui.screens.triage import TriageScreen

            self.app.push_screen(
                TriageScreen(
                    ledger_root=self._ledger_root,
                    experiment_id=data.experiment_id,
                )
            )
            return
        node.toggle()

    def action_cycle_view(self) -> None:
        """Cycle between discipline, category, and datasets tree views."""
        self._view = _next_in_cycle(self._view, _VIEW_CYCLE)  # type: ignore[assignment]
        self._populate_tree()

    def action_cycle_discipline(self) -> None:
        """Cycle through discipline filters: all -> civil -> ... -> all."""
        self._discipline_filter = _next_in_cycle(self._discipline_filter, _DISCIPLINE_CYCLE)
        self._populate_tree()
        self._render_summary()

    def action_cursor_down(self) -> None:
        """Move tree cursor down (vim j)."""
        tree = self.query_one("#library-tree", Tree)
        tree.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move tree cursor up (vim k)."""
        tree = self.query_one("#library-tree", Tree)
        tree.action_cursor_up()

    def action_push_datasets(self) -> None:
        """Push the Datasets screen for browsing versioned benchmark snapshots."""
        from aec_bench.tui.screens.datasets import DatasetsScreen

        self.app.push_screen(
            DatasetsScreen(
                datasets_root=self._datasets_root,
                ledger_root=self._ledger_root,
            )
        )

    def action_push_leaderboard(self) -> None:
        """Push the Leaderboard screen for model ranking by mean reward."""
        from aec_bench.tui.screens.leaderboard import LeaderboardScreen

        if self._ledger_root is None:
            self.notify("No ledger root configured", severity="warning")
            return
        self.app.push_screen(
            LeaderboardScreen(
                ledger_root=self._ledger_root,
            )
        )
