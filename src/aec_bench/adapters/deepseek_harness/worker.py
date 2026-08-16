# ABOUTME: Runs one official DeepSeek Harness SDK session inside the isolated adapter worker.
# ABOUTME: Writes raw notifications first and emits one small validated result after SDK shutdown.

from __future__ import annotations

import importlib.metadata
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import Field

from aec_bench.adapters.deepseek_harness.config import DEEPSEEK_HARNESS_VERSION
from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class WorkerRequest(StrictModel):
    harness_route: Literal["azure", "deepseek-official"]
    model: NonEmptyStr
    cordis: NonEmptyStr
    workspace: NonEmptyStr
    session_root: NonEmptyStr
    instruction: str
    system_prompt: str
    max_tokens: int | None = Field(default=None, ge=1)


def run_worker(*, request_path: Path, result_path: Path, notifications_path: Path) -> None:
    """Execute one SDK session and make its notification stream durable."""
    request = WorkerRequest.model_validate_json(request_path.read_text(encoding="utf-8"))
    try:
        sdk_version = importlib.metadata.version("deepseek-harness-sdk")
        runtime_distribution_version = importlib.metadata.version("deepseek-harness-runtime-bin")
        from deepseek_harness import DeepSeekHarness, DeepSeekHarnessConfig
    except (ImportError, importlib.metadata.PackageNotFoundError) as exc:
        raise RuntimeError("deepseek-harness-sdk is not installed; install aec-bench[deepseek-harness]") from exc
    if sdk_version != DEEPSEEK_HARNESS_VERSION or runtime_distribution_version != DEEPSEEK_HARNESS_VERSION:
        raise RuntimeError(
            "DeepSeek Harness package versions do not match the qualified runtime: "
            f"expected {DEEPSEEK_HARNESS_VERSION}, SDK {sdk_version}, runtime {runtime_distribution_version}"
        )

    notifications_path.parent.mkdir(parents=True, exist_ok=True)
    with notifications_path.open("w", encoding="utf-8") as notifications_file:
        capture_sequence = 0

        def capture(notification: object) -> None:
            nonlocal capture_sequence
            method = getattr(notification, "method", None)
            payload = getattr(notification, "payload", None)
            record = {
                "capture_sequence": capture_sequence,
                "captured_at": datetime.now(UTC).isoformat(),
                "notification_method": method,
                "payload": payload,
            }
            notifications_file.write(json.dumps(record, sort_keys=True) + "\n")
            notifications_file.flush()
            capture_sequence += 1

        config = DeepSeekHarnessConfig(
            provider=request.harness_route,
            model=request.model,
            max_tokens=request.max_tokens,
            cwd=request.workspace,
            runtime_cwd=request.workspace,
            session_root=request.session_root,
            cordis=request.cordis,
            env={"DSH_SYSTEM_PROMPT": request.system_prompt},
        )
        with DeepSeekHarness(config) as harness:
            sdk_result = harness.run(request.instruction, on_notification=capture)

    result_payload = {
        "session_id": sdk_result.session_id,
        "final_response": sdk_result.final_response,
        "finish_reason": sdk_result.finish_reason,
        "sdk_version": sdk_version,
        "runtime_distribution_version": runtime_distribution_version,
        "runtime_reported_version": None,
    }
    result_path.write_text(json.dumps(result_payload, sort_keys=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if len(arguments) != 3:
        raise SystemExit("usage: python -m aec_bench.adapters.deepseek_harness.worker REQUEST RESULT NOTIFICATIONS")
    request_path, result_path, notifications_path = map(Path, arguments)
    run_worker(
        request_path=request_path,
        result_path=result_path,
        notifications_path=notifications_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
