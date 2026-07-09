# ABOUTME: Universal Harbor agent — dispatches to library adapters via execution_entrypoint.
# ABOUTME: Replaces per-adapter agent files by serializing an execution bundle and running it.

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from harbor.agents.base import BaseAgent

from aec_bench.agents.tools import inject_trajectory_writer

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_LIBRARY_SOURCE = _PROJECT_ROOT / "src" / "aec_bench"

_RUNTIME_PIP_PACKAGES = (
    "pydantic>=2.11",
    "pydantic-ai[anthropic,openai]",
    "httpx>=0.28",
    "PyYAML>=6.0",
)

_BUNDLE_REMOTE_PATH = "/workspace/.aec-bench/execution-bundle.json"
_RESULT_REMOTE_PATH = "/workspace/.aec-bench/adapter-result.json"


class EntrypointAgent(BaseAgent):
    """Universal Harbor agent that dispatches to library adapters.

    Instead of embedding inline Python scripts, this agent uploads the
    aec_bench library source and an execution bundle into the container,
    then invokes ``execution_entrypoint.py`` to run the selected adapter.

    Harbor passes ``AgentConfig.parameters`` as keyword arguments to
    ``__init__``, so adapter selection and other config arrive via kwargs.
    """

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        # Harbor passes AgentConfig.parameters as kwargs
        self._params: dict[str, Any] = kwargs

    @staticmethod
    def name() -> str:
        return "entrypoint"

    def version(self) -> str | None:
        return "1.0.0"

    async def setup(self, environment: Any) -> None:  # type: ignore[override]
        # 1. Verify Python3 available
        result = await environment.exec("python3 --version")
        if result.return_code != 0:
            raise RuntimeError(f"Python3 not available in sandbox.\nstdout: {result.stdout}\nstderr: {result.stderr}")

        # 2. Upload library source to /opt/aec_bench/aec_bench/
        await environment.upload_dir(str(_LIBRARY_SOURCE), "/opt/aec_bench/aec_bench")

        # 3. Install pip deps if pydantic_ai not importable
        check = await environment.exec("python3 -c 'import pydantic_ai'")
        if check.return_code != 0:
            packages = " ".join(f'"{p}"' for p in _RUNTIME_PIP_PACKAGES)
            await environment.exec(f"pip install --no-cache-dir {packages}")

        # 4. Inject trajectory_writer.py
        await inject_trajectory_writer(environment)

    async def run(  # type: ignore[override]
        self,
        instruction: str,
        environment: Any,
        context: Any,
    ) -> None:
        adapter_kind = self._params.get("adapter", "rlm")
        timeout_sec = int(self._params.get("timeout_sec", 600))
        execution_payload: dict[str, Any] = {}
        client_payload = self._params.get("client")
        if isinstance(client_payload, dict):
            execution_payload["client"] = client_payload

        # Build execution bundle
        bundle: dict[str, Any] = {
            "execution": {
                "adapter_kind": adapter_kind,
                "adapter_name": self.name(),
                "resolved_model": self.model_name or "",
                "payload": execution_payload,
            },
            "request": {
                "instruction": instruction,
                "system_prompt": None,
                "tools": [],
                "configuration": dict(self._params),
                "output_path": "/workspace/output.md",
                "output_format": "markdown",
            },
        }

        # Write bundle to temp file and upload to container
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".json",
                delete=False,
            ) as tmp:
                json.dump(bundle, tmp, sort_keys=True)
                tmp_path = tmp.name

            await environment.upload_file(tmp_path, _BUNDLE_REMOTE_PATH)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        # Execute the entrypoint in the container
        cmd = (
            f"PYTHONPATH=/opt/aec_bench:$PYTHONPATH "
            f"python3 -m aec_bench.harness.execution_entrypoint "
            f"--bundle {_BUNDLE_REMOTE_PATH} "
            f"--result {_RESULT_REMOTE_PATH}"
        )
        exec_result = await environment.exec(cmd, timeout_sec=timeout_sec)

        # Read result and populate context
        try:
            local_result = Path(tempfile.mktemp(suffix=".json"))
            await environment.download_file(_RESULT_REMOTE_PATH, str(local_result))
            result_data = json.loads(local_result.read_text(encoding="utf-8"))
            local_result.unlink(missing_ok=True)

            context.n_input_tokens = result_data.get("usage_input_tokens", 0) or 0
            context.n_output_tokens = result_data.get("usage_output_tokens", 0) or 0
            context.metadata = {
                "adapter_name": result_data.get("adapter_name", ""),
                "resolved_model": result_data.get("resolved_model", ""),
                "exec_return_code": exec_result.return_code,
            }
        except Exception as exc:
            context.metadata = {
                "error": str(exc),
                "exec_return_code": getattr(exec_result, "return_code", None),
                "exec_stderr": getattr(exec_result, "stderr", ""),
            }
