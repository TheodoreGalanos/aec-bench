# ABOUTME: Static typing surface for Harbor's annotated but unmarked BaseAgent module.
# ABOUTME: Mirrors the subclass contract consumed by bundled aec-bench agent entrypoints.

import logging
from pathlib import Path
from typing import Any

class BaseAgent:
    logs_dir: Path
    model_name: str | None
    logger: logging.Logger

    def __init__(
        self,
        logs_dir: Path,
        model_name: str | None = None,
        logger: logging.Logger | None = None,
        mcp_servers: list[Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None: ...
    @staticmethod
    def name() -> str: ...
    def version(self) -> str | None: ...
    @classmethod
    def import_path(cls) -> str: ...
    async def setup(self, environment: Any) -> None: ...
    async def run(self, instruction: str, environment: Any, context: Any) -> None: ...
