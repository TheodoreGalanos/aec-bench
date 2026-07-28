# ABOUTME: End-to-end tests the bundled wastewater pump-station package in an isolated source tree.
# ABOUTME: Proves the production reader loads without research code, SWMM, or workspace paths.

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast


def test_reference_package_loads_with_research_tree_absent(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    isolated_root = tmp_path / "isolated"
    isolated_source = isolated_root / "src"
    shutil.copytree(
        repository_root / "src" / "aec_bench",
        isolated_source / "aec_bench",
    )
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(isolated_source)
    environment["PYTHONNOUSERSITE"] = "1"
    script = """
import json
from aec_bench.task_world_templates.stewardship.wastewater_pump_station import load_reference_package

package = load_reference_package()
print(json.dumps({
    "generation_id": package.generation_id,
    "package_content_id": package.package_content_id,
    "profile_id": package.profile_id,
}, sort_keys=True))
"""

    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=isolated_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
    )

    assert not (isolated_root / "research").exists()
    assert completed.returncode == 0, completed.stderr
    result = cast(dict[str, Any], json.loads(completed.stdout))
    assert result == {
        "generation_id": "738bc2b31f40ae7ea7831a54826c10c7e1f8084e64a6c0e0883bc6290aa84c8e",
        "package_content_id": "642da8bdfad63d7324e0c5886f1f8f3866c9a6bd25f165fa2a5937d68e8a5e16",
        "profile_id": "AU-NSW-LH-SYN-SPS-v1",
    }
