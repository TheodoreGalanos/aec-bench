# ABOUTME: Contract model for the minimal adapter output envelope in aec-bench.
# ABOUTME: Captures completion status and output-location metadata without a global payload shape.

from enum import StrEnum

from aec_bench.contracts.validators import NonEmptyStr, StrictModel


class AgentOutputStatus(StrEnum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    EMPTY = "empty"


class AgentOutput(StrictModel):
    status: AgentOutputStatus
    output_path: NonEmptyStr
    output_format: NonEmptyStr
    error_message: str | None = None
