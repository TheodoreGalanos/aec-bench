# ABOUTME: Exercises evidence-index pagination at the nightly 10,000-record scale target.
# ABOUTME: Proves indexed metadata remains complete and ordered without loading evidence bodies.

from __future__ import annotations

import sqlite3
from pathlib import Path

from aec_bench.ledger.index import EvidenceIndex
from aec_bench.ledger.query import EvidenceQuery


def test_query_paginates_10000_indexed_records(tmp_path: Path) -> None:
    index = EvidenceIndex(tmp_path / "index.sqlite")
    with sqlite3.connect(tmp_path / "index.sqlite") as connection:
        connection.executemany(
            """
            INSERT INTO evidence_trial_records (
                trial_id, run_id, experiment_id, task_id, task_revision, task_kind,
                adapter, model, world_profile_id, dataset_id, attempt, reward,
                execution_status, evaluation_status, evidence_status, started_at,
                completed_at, provider_evidence_present, record_path, record_sha256
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                (
                    f"trial-{ordinal:05d}",
                    "run-001",
                    "experiment-001",
                    "civil/example",
                    "revision-001",
                    "artifact",
                    "synthetic",
                    "model-001",
                    None,
                    None,
                    1,
                    1.0,
                    "completed",
                    "completed",
                    "not_required",
                    "2026-03-13T10:00:00+00:00",
                    "2026-03-13T10:00:12+00:00",
                    0,
                    f"experiment-001/trial-{ordinal:05d}.json",
                    "0" * 64,
                )
                for ordinal in range(10_000)
            ),
        )
        connection.execute("UPDATE evidence_index_metadata SET generation = 1 WHERE singleton = 1")

    query = EvidenceQuery(index)
    rows = []
    cursor: str | None = None
    while True:
        page = query.page(page_size=1_000, after_cursor=cursor)
        rows.extend(page.rows)
        if page.next_cursor is None:
            break
        cursor = page.next_cursor

    assert len(rows) == 10_000
    assert rows[0].trial_id == "trial-00000"
    assert rows[-1].trial_id == "trial-09999"
