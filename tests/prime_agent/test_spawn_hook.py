# ABOUTME: Verifies Prime spawn hooks retain the originating cell across concurrent work.
# ABOUTME: Checks unchanged provider calls and safe trace capture failures without live models.

import asyncio
import base64
import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from aec_bench.prime_agent.spawn_hook import install_prime_spawn_hook

ASSETS = Path("src/aec_bench/prime_agent/hook_assets")


def _tag(call_id: str, code: str = "original()") -> str:
    data = json.dumps({"parent_session_id": "root", "parent_tool_call_id": call_id}).encode()
    return code + "\n# aec-bench-prime-call " + base64.b64encode(data).decode() + "\n"


@pytest.mark.asyncio
async def test_spawn_hook_keeps_origin_across_cells_and_out_of_order_returns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    handlers: dict[str, Any] = {}
    shell = SimpleNamespace(input_transformers_cleanup=[], events=SimpleNamespace(register=handlers.__setitem__))
    release = asyncio.Event()
    calls = []

    async def request(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        calls.append((kind, payload))
        if payload and payload["prompt"] == "first":
            await release.wait()
        identity = payload["prompt"] if payload else "other"
        directory = tmp_path / identity
        directory.mkdir()
        return {"rlm_child_id": identity, "session_dir": str(directory), "name": identity, "model": "test"}

    runtime = SimpleNamespace(host_request=request)
    monkeypatch.setitem(sys.modules, "rlm", runtime)
    monkeypatch.setenv("AEC_BENCH_PRIME_SESSION_ROOT", str(tmp_path))
    hook = runpy.run_path(str(ASSETS / "spawn.py"))
    hook["load_ipython_extension"](shell)
    handlers["pre_run_cell"](SimpleNamespace(raw_cell=_tag("call-a")))
    first = asyncio.create_task(runtime.host_request("rlm.run", {"prompt": "first"}))
    # This task has inherited call-a, even though its spawn starts after cell B.
    handlers["pre_run_cell"](SimpleNamespace(raw_cell=_tag("call-b")))
    second = await runtime.host_request("rlm.run", {"prompt": "second"})
    release.set()
    await first
    assert second["name"] == "second"
    assert json.loads((tmp_path / "first/aec-spawn.json").read_text())["parent_tool_call_id"] == "call-a"
    assert json.loads((tmp_path / "second/aec-spawn.json").read_text())["parent_tool_call_id"] == "call-b"
    assert calls == [("rlm.run", {"prompt": "second"}), ("rlm.run", {"prompt": "first"})]
    assert shell.input_transformers_cleanup[0](_tag("call-a", "%%bash\nprintf ok").splitlines(True)) == [
        "%%bash\n",
        "printf ok\n",
    ]
    # An untagged cell cannot inherit the most recent call's attribution.
    handlers["pre_run_cell"](SimpleNamespace(raw_cell="untagged()"))
    await runtime.host_request("rlm.run", {"prompt": "untagged"})
    assert not (tmp_path / "untagged/aec-spawn.json").exists()


@pytest.mark.asyncio
async def test_spawn_hook_preserves_provider_failure_and_capture_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    handlers: dict[str, Any] = {}
    shell = SimpleNamespace(input_transformers_cleanup=[], events=SimpleNamespace(register=handlers.__setitem__))
    result = {"rlm_child_id": "outside", "session_dir": str(tmp_path.parent)}
    failure = RuntimeError("private provider diagnostic")

    async def request(kind: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if payload:
            raise failure
        return result

    runtime = SimpleNamespace(host_request=request)
    monkeypatch.setitem(sys.modules, "rlm", runtime)
    monkeypatch.setenv("AEC_BENCH_PRIME_SESSION_ROOT", str(tmp_path))
    install = runpy.run_path(str(ASSETS / "spawn.py"))["load_ipython_extension"]
    install(shell)
    observed = runtime.host_request
    install(shell)
    assert runtime.host_request is observed
    handlers["pre_run_cell"](SimpleNamespace(raw_cell=_tag("call")))
    with pytest.raises(RuntimeError) as exc:
        await runtime.host_request("rlm.run", {"fail": True})
    assert exc.value is failure
    assert await runtime.host_request("rlm.run") is result
    assert "spawn capture failed" in caplog.text
    assert "private provider diagnostic" not in caplog.text
    assert list(tmp_path.iterdir()) == []


def test_spawn_hook_in_installed_prime_kernel(tmp_path: Path) -> None:
    """Opt in with a Python containing Prime's runtime and ipykernel; no models run."""
    python = os.environ.get("AEC_BENCH_PRIME_TEST_KERNEL_PYTHON")
    prime = shutil.which("prime-agent")
    node = shutil.which("node")
    if not python or not prime or not node:
        pytest.skip("set AEC_BENCH_PRIME_TEST_KERNEL_PYTHON and install Prime and Node for the kernel probe")
    root = tmp_path.resolve()
    (root / "sessions").mkdir()
    environment = dict(os.environ)
    install_prime_spawn_hook(root / "sessions", environment)
    # The executable lives at <installation>/dist/bundle/cli.js.
    prime_root = Path(prime).resolve().parents[2]
    result = subprocess.run(
        [
            node,
            str(Path(__file__).with_name("spawn_hook_probe.mjs")),
            str(prime_root),
            python,
            str(root),
            str(root / "spawn-hook/spawn.mjs"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_spawn_hook_installation_rejects_linked_destinations(tmp_path: Path) -> None:
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (tmp_path / "spawn-hook").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic links"):
        install_prime_spawn_hook(sessions, {})
    assert list(outside.iterdir()) == []
