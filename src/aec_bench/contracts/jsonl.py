# ABOUTME: JSONL helpers for contract-friendly line-oriented serialization in aec-bench.
# ABOUTME: Supports deterministic read/write behavior for dicts and Pydantic models at boundaries.

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_jsonl(path: Path, records: Sequence[Mapping[str, Any] | BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file_obj:
        for record in records:
            payload = record.model_dump(mode="json") if isinstance(record, BaseModel) else record
            file_obj.write(json.dumps(payload, sort_keys=True))
            file_obj.write("\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file_obj:
        return [json.loads(line) for line in file_obj if line.strip()]
