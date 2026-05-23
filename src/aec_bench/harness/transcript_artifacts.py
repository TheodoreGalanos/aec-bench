# ABOUTME: Transcript artifact serialization helpers for harness collection in aec-bench Python.
# ABOUTME: Persists canonical adapter transcript entries as JSONL conversation artifacts.

from dataclasses import asdict
from pathlib import Path
from typing import Any

from aec_bench.adapters.transcript import TranscriptEntry
from aec_bench.contracts.jsonl import write_jsonl


def write_transcript_artifact(*, path: Path, transcript: list[TranscriptEntry]) -> Path:
    records = [_transcript_record(entry) for entry in transcript]
    write_jsonl(path, records)
    return path


def _transcript_record(entry: TranscriptEntry) -> dict[str, Any]:
    record = asdict(entry)
    if entry.role is not None:
        record["role"] = entry.role.value
    if entry.event is not None:
        record["event"] = entry.event.value
    if entry.occurred_at is not None:
        record["occurred_at"] = entry.occurred_at.isoformat()
    return record
