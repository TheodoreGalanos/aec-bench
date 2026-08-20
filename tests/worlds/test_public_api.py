# ABOUTME: Tests public Interactive World discovery, task construction, and file-backed loading.
# ABOUTME: Proves the facade projects exact registered metadata without exposing internal loaders.

from __future__ import annotations

from pathlib import Path

import pytest

from aec_bench import worlds
from aec_bench.worlds.monitoring.dam_seepage.definition import DamSeepageProfile
from aec_bench.worlds.monitoring.dam_seepage.world import DAM_SEEPAGE_TASK_WORLD_ID
from aec_bench.worlds.stewardship.wastewater_pump_station.episode_runtime import (
    PUMP_STATION_TASK_WORLD_ID,
)


def test_public_discovery_is_stable_searchable_and_descriptive() -> None:
    discovered = worlds.list()

    assert tuple(item.id for item in discovered) == (
        DAM_SEEPAGE_TASK_WORLD_ID,
        PUMP_STATION_TASK_WORLD_ID,
    )
    assert worlds.find("seepage") == (discovered[0],)
    assert worlds.find("WASTEWATER") == (discovered[1],)
    assert worlds.find("   ") == ()
    assert discovered[0].capabilities == frozenset()
    assert discovered[1].capabilities == frozenset({"branching", "host-controls", "persistence"})
    assert worlds.profiles(DAM_SEEPAGE_TASK_WORLD_ID) == discovered[0].profiles


def test_public_discovery_rejects_unknown_world_and_profile() -> None:
    with pytest.raises(KeyError, match="unknown Interactive World"):
        worlds.get("unknown")
    with pytest.raises(KeyError, match="unknown Interactive World profile"):
        worlds.task(DAM_SEEPAGE_TASK_WORLD_ID, profile="unknown", instruction="Monitor the dam.")


def test_public_task_binds_registered_profile_and_derives_revision() -> None:
    task = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam and respond as conditions evolve.",
    )
    repeated = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam and respond as conditions evolve.",
    )

    assert task == repeated
    assert task.task_id == f"{DAM_SEEPAGE_TASK_WORLD_ID}/synthetic-rising-seepage"
    assert len(task.task_revision) == 64
    assert isinstance(worlds.load_profile(task).value, DamSeepageProfile)


def test_file_backed_world_task_has_direct_task_semantics(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = tasks_root / "civil" / "dam-monitoring"
    task_dir.mkdir(parents=True)
    direct = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        task_id="civil/dam-monitoring",
        instruction="Monitor the dam and respond as conditions evolve.",
    )
    (task_dir / "instruction.md").write_text(direct.instruction + "\n", encoding="utf-8")
    (task_dir / "world.toml").write_text(
        "\n".join(
            (
                "[world]",
                f'task_world_id = "{direct.world.task_world_id}"',
                f'entry_point = "{direct.world.entry_point}"',
                f'artifact_sha256 = "{direct.world.artifact_sha256}"',
                "",
                "[profile]",
                f'task_world_id = "{direct.profile.task_world_id}"',
                f'profile_id = "{direct.profile.profile_id}"',
                f'profile_content_sha256 = "{direct.profile.profile_content_sha256}"',
                "",
                "[metadata]",
                'domain = "civil"',
                'category = "monitoring"',
                'difficulty = "medium"',
                'lifecycle = "active"',
                'visibility = "public"',
                'tags = ["dam", "monitoring", "seepage", "synthetic"]',
                "",
            )
        ),
        encoding="utf-8",
    )

    assert worlds.load_world_task(task_dir, tasks_root) == direct


def test_file_backed_world_task_rejects_stale_build(tmp_path: Path) -> None:
    tasks_root = tmp_path / "tasks"
    task_dir = tasks_root / "civil" / "dam-monitoring"
    task_dir.mkdir(parents=True)
    direct = worlds.task(
        DAM_SEEPAGE_TASK_WORLD_ID,
        profile="synthetic-rising-seepage",
        instruction="Monitor the dam.",
    )
    (task_dir / "instruction.md").write_text(direct.instruction, encoding="utf-8")
    (task_dir / "world.toml").write_text(
        f"""[world]
task_world_id = "{direct.world.task_world_id}"
entry_point = "{direct.world.entry_point}"
artifact_sha256 = "{"f" * 64}"

[profile]
task_world_id = "{direct.profile.task_world_id}"
profile_id = "{direct.profile.profile_id}"
profile_content_sha256 = "{direct.profile.profile_content_sha256}"

[metadata]
domain = "civil"
category = "monitoring"
difficulty = "medium"
lifecycle = "active"
visibility = "public"
tags = ["dam", "monitoring", "seepage", "synthetic"]
""",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="world build does not match"):
        worlds.load_world_task(task_dir, tasks_root)
