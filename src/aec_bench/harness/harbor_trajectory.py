# ABOUTME: Publishes AEC-Bench trajectory records as live ATIF through Harbor's environment interface.
# ABOUTME: Keeps preview failures separate from agent outcomes and stops polling before verification.

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Protocol

from aec_bench.contracts.trajectory import TrajectoryEntry
from aec_bench.harness.atif import to_atif, write_atif

_POLL_SECONDS = 2.0
_DOWNLOAD_TIMEOUT_SECONDS = 10.0


class TrajectoryEnvironment(Protocol):
    async def download_file(self, source_path: str, target_path: str) -> None: ...


@contextlib.asynccontextmanager
async def publish_harbor_trajectory(
    environment: TrajectoryEnvironment,
    *,
    logs_dir: Path,
    agent_name: str,
    agent_version: str,
    model_name: str | None,
    session_id: str | None,
    live: bool,
    logger: logging.Logger,
) -> AsyncIterator[None]:
    """Publish complete records during a run, then make one final export.

    This custom BaseAgent writes Harbor's normal viewer file directly. It does
    not need Harbor's installed-agent transcript converter or a second SSH
    transport. The original JSONL remains the AEC-Bench import authority.
    """

    async def publish(*, final: bool) -> None:
        try:
            with tempfile.TemporaryDirectory(prefix="aec-bench-trajectory-") as directory:
                source = Path(directory) / "trajectory.jsonl"
                await asyncio.wait_for(
                    environment.download_file("/workspace/trajectory.jsonl", str(source)),
                    timeout=_DOWNLOAD_TIMEOUT_SECONDS,
                )
                data = source.read_bytes()
                if not final:
                    # The producer may be in the middle of a UTF-8 code point
                    # or JSON record. Publish only its newline-terminated prefix.
                    data = data[: data.rfind(b"\n") + 1]
                entries = [
                    TrajectoryEntry.model_validate(json.loads(line)) for line in data.splitlines() if line.strip()
                ]
                if entries:
                    trajectory = to_atif(
                        entries,
                        agent_name=agent_name,
                        agent_version=agent_version,
                        model_name=model_name,
                        session_id=session_id,
                    )
                    assert trajectory.extra is not None
                    trajectory.extra["aec_bench"]["export_stage"] = "final" if final else "preview"
                    write_atif(trajectory, logs_dir / "trajectory.json")
        except Exception as exc:
            # Preview transfer errors must not replace the agent's exception or
            # expose provider messages, which can contain credentials.
            if final and live:
                logger.warning("ATIF export unavailable (%s); agent result is unchanged", type(exc).__name__)
            else:
                logger.debug("ATIF preview unavailable (%s)", type(exc).__name__)

    async def poll() -> None:
        while True:
            await publish(final=False)
            await asyncio.sleep(_POLL_SECONDS)

    worker = asyncio.create_task(poll()) if live else None
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        await publish(final=True)
