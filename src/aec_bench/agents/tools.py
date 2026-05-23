# ABOUTME: Agent setup utilities — tool discovery and trajectory writer injection.
# ABOUTME: Pure parsing functions plus thin async wrappers for container interaction.

from __future__ import annotations

import importlib.resources
import tomllib
from pathlib import PurePosixPath
from typing import Any


def parse_tools_from_toml(toml_content: str) -> list[dict[str, Any]]:
    """Parse tool declarations from task.toml content. Pure function.

    Handles two formats:
    - New: [[environment.tools]] entries with name, source, description, returns_image
    - Legacy: [tools] scripts = ["calc.py", ...] — derives name from filename
    """
    if not toml_content.strip():
        return []

    try:
        toml_data = tomllib.loads(toml_content)
    except (tomllib.TOMLDecodeError, ValueError):
        return []

    # New format: [[environment.tools]]
    env_tools = toml_data.get("environment", {}).get("tools", [])
    if env_tools:
        discovered: list[dict[str, Any]] = []
        for entry in env_tools:
            tool: dict[str, Any] = {
                "name": entry["name"],
                "source": entry.get("source", ""),
                "description": entry.get("description", f"Tool: {entry['name']}"),
            }
            if "returns_image" in entry:
                tool["returns_image"] = entry["returns_image"]
            discovered.append(tool)
        return discovered

    # Legacy format: [tools] scripts = [...]
    tools_section = toml_data.get("tools", {})
    scripts = tools_section.get("scripts", [])

    legacy_discovered: list[dict[str, Any]] = []
    for script in scripts:
        stem = PurePosixPath(script).stem
        legacy_discovered.append(
            {
                "name": stem.replace("_", "-") if "_" in stem else stem,
                "source": script,
                "description": f"Tool: {stem}",
            }
        )

    return legacy_discovered


async def discover_tools(environment: Any) -> list[dict[str, Any]]:
    """Read task.toml from environment and parse tools. Thin async wrapper.

    The environment parameter is duck-typed — any object with an async
    exec(command) method works. No Harbor import needed.
    """
    result = await environment.exec("cat /workspace/task.toml")
    if result.return_code != 0:
        return []
    return parse_tools_from_toml(result.stdout)


def build_trajectory_writer_source() -> str:
    """Return the trajectory_writer.py source code for container injection.

    Reads from the bundled aec_bench.trajectory.writer module — the same
    source used by the scaffolder for generated tasks.
    """
    writer_resource = importlib.resources.files("aec_bench.trajectory") / "writer.py"
    return writer_resource.read_text(encoding="utf-8")


async def inject_trajectory_writer(environment: Any) -> None:
    """Write trajectory_writer.py into the container at /workspace/.

    The agent's embedded scripts import `from trajectory_writer import TrajectoryWriter`.
    Rather than requiring every task Dockerfile to COPY this file, the agent
    injects it at setup time — keeping trajectory recording an agent concern,
    not a task concern.
    """
    source = build_trajectory_writer_source()
    # Heredoc avoids shell quoting issues with embedded quotes in the source
    write_cmd = f"cat > /workspace/trajectory_writer.py << 'TRAJECTORY_WRITER_EOF'\n{source}\nTRAJECTORY_WRITER_EOF"
    result = await environment.exec(write_cmd)
    if result.return_code != 0:
        raise RuntimeError(f"Failed to inject trajectory_writer.py: {result.stderr}")
