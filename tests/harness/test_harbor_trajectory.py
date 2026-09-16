# ABOUTME: Checks live ATIF publication through the existing Harbor file-transfer boundary.
# ABOUTME: Covers partial writes, failed transfers, final export, and cancellation cleanup.

import asyncio
import json
import logging
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from harbor.models.trajectories.trajectory import Trajectory
from harbor.viewer.server import create_app

from aec_bench.harness.harbor_trajectory import publish_harbor_trajectory


def test_live_atif_is_visible_before_agent_completion(tmp_path: Path) -> None:
    logs_dir = tmp_path / "job" / "trial" / "agent"
    viewer = TestClient(create_app(tmp_path))

    async def exercise() -> None:
        transferred = asyncio.Event()

        class Environment:
            content = b'{"step":0,"role":"user","content":"Size cable"}\n{"step":1,"role":"assistant","content":"\xc2'

            async def download_file(self, source_path: str, target_path: str) -> None:
                assert source_path == "/workspace/trajectory.jsonl"
                Path(target_path).write_bytes(self.content)
                transferred.set()

        environment = Environment()
        async with publish_harbor_trajectory(
            environment,
            logs_dir=logs_dir,
            agent_name="tool_loop",
            agent_version="1",
            model_name="test-model",
            session_id="trial-1",
            live=True,
            logger=logging.getLogger(__name__),
        ):
            await asyncio.wait_for(transferred.wait(), 1)
            response = viewer.get("/api/jobs/job/trials/trial/trajectory")
            assert response.status_code == 200
            preview = Trajectory.model_validate(response.json())
            assert [step.message for step in preview.steps] == ["Size cable"]
            assert preview.extra is not None
            assert preview.extra["aec_bench"]["export_stage"] == "preview"
            environment.content = (
                b'{"step":0,"role":"user","content":"Size cable"}\n{"step":1,"role":"assistant","content":"25 mm2"}'
            )
        final = Trajectory.model_validate(viewer.get("/api/jobs/job/trials/trial/trajectory").json())
        assert final.steps[-1].message == "25 mm2"
        assert final.session_id == "trial-1"
        assert final.extra is not None
        assert final.extra["aec_bench"]["export_stage"] == "final"

    asyncio.run(exercise())


def test_preview_failure_preserves_agent_error_and_previous_atif(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    original = '{"previous":"valid preview retained"}'
    (tmp_path / "trajectory.json").write_text(original)

    class Environment:
        async def download_file(self, source_path: str, target_path: str) -> None:
            raise RuntimeError("provider-secret-value")

    async def exercise() -> None:
        async with publish_harbor_trajectory(
            Environment(),
            logs_dir=tmp_path,
            agent_name="tool_loop",
            agent_version="1",
            model_name=None,
            session_id=None,
            live=True,
            logger=logging.getLogger(__name__),
        ):
            raise ValueError("agent failed")

    with pytest.raises(ValueError, match="agent failed"):
        asyncio.run(exercise())
    assert (tmp_path / "trajectory.json").read_text() == original
    assert "provider-secret-value" not in caplog.text
    assert "ATIF export unavailable" in caplog.text


def test_non_stream_run_exports_once_after_completion(tmp_path: Path) -> None:
    calls: list[str] = []

    class Environment:
        async def download_file(self, source_path: str, target_path: str) -> None:
            calls.append(source_path)
            Path(target_path).write_text(json.dumps({"step": 1, "role": "assistant", "content": "Done"}) + "\n")

    async def exercise() -> None:
        async with publish_harbor_trajectory(
            Environment(),
            logs_dir=tmp_path,
            agent_name="rlm",
            agent_version="1",
            model_name=None,
            session_id=None,
            live=False,
            logger=logging.getLogger(__name__),
        ):
            assert calls == []

    asyncio.run(exercise())
    assert calls == ["/workspace/trajectory.jsonl"]
    assert Trajectory.model_validate_json((tmp_path / "trajectory.json").read_text()).steps[0].message == "Done"


def test_cancellation_stops_polling_and_attempts_final_export(tmp_path: Path) -> None:
    async def exercise() -> None:
        downloading = asyncio.Event()
        cancelled = asyncio.Event()
        attempts = 0

        class Environment:
            async def download_file(self, source_path: str, target_path: str) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    downloading.set()
                    try:
                        await asyncio.Event().wait()
                    finally:
                        cancelled.set()
                Path(target_path).write_text('{"step":1,"role":"assistant","content":"Partial"}\n')

        async def run() -> None:
            async with publish_harbor_trajectory(
                Environment(),
                logs_dir=tmp_path,
                agent_name="tool_loop",
                agent_version="1",
                model_name=None,
                session_id=None,
                live=True,
                logger=logging.getLogger(__name__),
            ):
                await asyncio.Event().wait()

        task = asyncio.create_task(run())
        await asyncio.wait_for(downloading.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 1)
        assert cancelled.is_set()
        assert attempts == 2
        assert Trajectory.model_validate_json((tmp_path / "trajectory.json").read_text()).steps[0].message == "Partial"

    asyncio.run(exercise())
