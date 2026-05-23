# ABOUTME: Tests the task-ecology benchmark selection and config scaffolding.
# ABOUTME: Keeps Experiment 1 setup deterministic before materialising generated tasks.

from pathlib import Path

import yaml

from aec_bench.evolution.config_loader import load_evolution_config
from aec_bench.experiments.task_ecology_benchmark import (
    DEFAULT_ANCHOR_TASK_IDS,
    DEFAULT_DIFFICULTIES,
    DEFAULT_MAX_CYCLES,
    TemplateEntry,
    build_arm_config,
    load_pressure_task_patterns,
    scaffold_workspace,
    select_benchmark_templates,
    summarise_benchmark_runs,
    write_pressure_benchmark_configs,
)


def _entries() -> list[TemplateEntry]:
    return [
        TemplateEntry(
            task_id="civil/bund-volume-calculation",
            domain="civil",
            source_task_path="src/aec_bench/templates/builtin/civil/bund_volume_calculation",
        ),
        TemplateEntry(
            task_id="civil/orifice-outlet-design",
            domain="civil",
            source_task_path="src/aec_bench/templates/builtin/civil/orifice_outlet_design",
        ),
        TemplateEntry(
            task_id="electrical/voltage-drop",
            domain="electrical",
            source_task_path="src/aec_bench/templates/builtin/electrical/voltage_drop",
        ),
        TemplateEntry(
            task_id="electrical/grid-resistance",
            domain="electrical",
            source_task_path="src/aec_bench/templates/builtin/electrical/grid_resistance",
        ),
        TemplateEntry(
            task_id="ground/consolidation-settlement",
            domain="ground",
            source_task_path="src/aec_bench/templates/builtin/ground/consolidation_settlement",
        ),
        TemplateEntry(
            task_id="ground/wall-overturning",
            domain="ground",
            source_task_path="src/aec_bench/templates/builtin/ground/wall_overturning",
        ),
        TemplateEntry(
            task_id="mechanical/npsh-available",
            domain="mechanical",
            source_task_path="src/aec_bench/templates/builtin/mechanical/npsh_available",
        ),
        TemplateEntry(
            task_id="mechanical/wave-speed-calculation",
            domain="mechanical",
            source_task_path="src/aec_bench/templates/builtin/mechanical/wave_speed_calculation",
        ),
        TemplateEntry(
            task_id="structural/gravity-base-stability",
            domain="structural",
            source_task_path="src/aec_bench/templates/builtin/structural/gravity_base_stability",
        ),
        TemplateEntry(
            task_id="structural/thermal-movement-calc",
            domain="structural",
            source_task_path="src/aec_bench/templates/builtin/structural/thermal_movement_calc",
        ),
    ]


def test_select_benchmark_templates_keeps_anchors_out_of_population() -> None:
    selection = select_benchmark_templates(
        _entries(),
        anchor_task_ids=DEFAULT_ANCHOR_TASK_IDS,
        population_per_domain=1,
        seed=123,
    )

    fixed_ids = {entry.task_id for entry in selection.fixed}
    population_ids = {entry.task_id for entry in selection.population}

    assert fixed_ids == set(DEFAULT_ANCHOR_TASK_IDS)
    assert fixed_ids.isdisjoint(population_ids)
    assert len(selection.population) == 5


def test_default_max_cycles_covers_population_once_at_default_batch_size() -> None:
    assert DEFAULT_DIFFICULTIES == ("easy", "medium", "hard")
    assert DEFAULT_MAX_CYCLES == 6


def test_build_arm_config_uses_suite_include_pattern(tmp_path: Path) -> None:
    config = build_arm_config(
        experiment_slug="task-ecology-exp1",
        suite_name="population",
        strategy="qd",
        workspace_path=tmp_path / "ws",
        batch_size=5,
        max_cycles=3,
    )

    assert config["workspace_path"] == str(tmp_path / "ws")
    assert config["tasks"]["include_patterns"] == ["generated/task-ecology-exp1/population/*"]
    assert config["strategy"] == "qd"
    assert config["batch_size"] == 5
    assert config["max_cycles"] == 3
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml.safe_dump(config), encoding="utf-8")
    assert load_evolution_config(config_path).strategy == "qd"


def test_build_arm_config_accepts_exact_include_patterns(tmp_path: Path) -> None:
    config = build_arm_config(
        experiment_slug="task-ecology-exp1",
        suite_name="fixed",
        strategy="hill_climb",
        workspace_path=tmp_path / "ws",
        batch_size=5,
        max_cycles=3,
        include_patterns=["generated/task-ecology-exp1/fixed/civil/template/sample-00"],
    )

    assert config["tasks"]["include_patterns"] == ["generated/task-ecology-exp1/fixed/civil/template/sample-00"]


def test_load_pressure_task_patterns_filters_by_suite_and_threshold(tmp_path: Path) -> None:
    summary_path = tmp_path / "summary.yaml"
    summary_path.write_text(
        yaml.safe_dump(
            {
                "below_threshold_tasks": [
                    {
                        "task_id": "generated/task-ecology-exp1/fixed/civil/a",
                        "suite": "fixed",
                        "reward": 0.75,
                    },
                    {
                        "task_id": "generated/task-ecology-exp1/population/civil/b",
                        "suite": "population",
                        "reward": 0.5,
                    },
                    {
                        "task_id": "generated/task-ecology-exp1/population/civil/c",
                        "suite": "population",
                        "reward": 0.9,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    patterns = load_pressure_task_patterns(summary_path, score_threshold=0.85)

    assert patterns == {
        "fixed": ["generated/task-ecology-exp1/fixed/civil/a"],
        "population": ["generated/task-ecology-exp1/population/civil/b"],
    }


def test_write_pressure_benchmark_configs_points_to_pressure_tasks(tmp_path: Path) -> None:
    paths = write_pressure_benchmark_configs(
        repo_root=tmp_path,
        source_experiment_slug="task-ecology-exp1",
        pressure_experiment_slug="task-ecology-exp1-pressure",
        config_dir=tmp_path / "configs" / "task-ecology-exp1-pressure",
        workspace_root=tmp_path / "workspaces",
        pressure_task_patterns={
            "fixed": ["generated/task-ecology-exp1/fixed/civil/a"],
            "population": ["generated/task-ecology-exp1/population/civil/b"],
        },
        batch_size=5,
        max_cycles=6,
    )

    assert [path.name for path in paths] == [
        "fixed-hill-climb.yaml",
        "fixed-qd.yaml",
        "population-hill-climb.yaml",
        "population-qd.yaml",
    ]
    fixed_config = yaml.safe_load((paths[0]).read_text(encoding="utf-8"))
    assert fixed_config["workspace_path"] == ("workspaces/task-ecology-exp1-pressure-fixed-hill-climb")
    assert fixed_config["tasks"]["include_patterns"] == ["generated/task-ecology-exp1/fixed/civil/a"]


def test_scaffold_workspace_writes_manifest_and_prompt(tmp_path: Path) -> None:
    workspace = scaffold_workspace(tmp_path / "ws", name="task-ecology-exp1-fixed-hill")

    manifest = yaml.safe_load((workspace / "manifest.yaml").read_text())
    assert manifest["name"] == "task-ecology-exp1-fixed-hill"
    assert manifest["agent_adapter"] == "tool_loop"
    assert (workspace / "prompts" / "system.md").exists()


def test_summarise_benchmark_runs_marks_unrun_configs_pending(tmp_path: Path) -> None:
    workspace = scaffold_workspace(
        tmp_path / "workspaces" / "exp-fixed-hill",
        name="exp-fixed-hill",
    )
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    config = build_arm_config(
        experiment_slug="task-ecology-exp1",
        suite_name="fixed",
        strategy="hill_climb",
        workspace_path=workspace,
        batch_size=5,
        max_cycles=3,
    )
    (config_dir / "fixed-hill-climb.yaml").write_text(
        yaml.safe_dump(config),
        encoding="utf-8",
    )
    (config_dir / "manifest.yaml").write_text(
        yaml.safe_dump({"experiment": "exp"}),
        encoding="utf-8",
    )

    rows = summarise_benchmark_runs(config_dir)

    assert rows == [
        {
            "arm": "fixed-hill-climb",
            "workspace": str(workspace),
            "strategy": "hill_climb",
            "status": "pending",
            "cycles": 0,
            "best_score": None,
            "final_score": None,
            "run_id": None,
        }
    ]
