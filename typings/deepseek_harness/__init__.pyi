# ABOUTME: Supplies the typed surface used from the optional DeepSeek Harness SDK.
# ABOUTME: Compensates for the qualified SDK wheel not declaring a py.typed marker.

from collections.abc import Callable
from types import TracebackType
from typing import Self

class Notification:
    method: str
    payload: dict[str, object]

class DeepSeekHarnessConfig:
    def __init__(
        self,
        *,
        provider: str = ...,
        model: str = ...,
        max_tokens: int | None = ...,
        cwd: str | None = ...,
        runtime_cwd: str | None = ...,
        session_root: str | None = ...,
        cordis: str | None = ...,
        env: dict[str, str] = ...,
        runtime_bin: str | None = ...,
    ) -> None: ...

class RunResult:
    session_id: str
    final_response: str
    finish_reason: str | None

class DeepSeekHarness:
    def __init__(self, config: DeepSeekHarnessConfig) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...
    def run(
        self,
        input: str,
        *,
        on_notification: Callable[[Notification], None] | None = ...,
    ) -> RunResult: ...
