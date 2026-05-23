# ABOUTME: Tests for SubcallLog — records sub-call invocations for sibling sharing.
# ABOUTME: Validates logging, querying by type, persistence, and REPL integration.

from __future__ import annotations

from aec_bench.adapters.rlm.subcall_log import SubcallLog


class TestSubcallLog:
    """Core SubcallLog behaviour."""

    def test_initially_empty(self) -> None:
        log = SubcallLog()
        assert len(log) == 0
        assert log.all() == []

    def test_record_and_retrieve(self) -> None:
        log = SubcallLog()
        log.record(
            subcall_type="extract",
            args_summary="fields=['speed', 'direction']",
            result_summary={"speed": 45, "direction": "NW"},
            input_tokens=100,
            output_tokens=50,
        )
        assert len(log) == 1
        entry = log.all()[0]
        assert entry["type"] == "extract"
        assert entry["result"] == {"speed": 45, "direction": "NW"}

    def test_multiple_entries_ordered(self) -> None:
        log = SubcallLog()
        log.record(subcall_type="extract", args_summary="1st", result_summary="a")
        log.record(subcall_type="summarise", args_summary="2nd", result_summary="b")
        log.record(subcall_type="extract", args_summary="3rd", result_summary="c")
        assert len(log) == 3
        assert [e["args"] for e in log.all()] == ["1st", "2nd", "3rd"]

    def test_last_returns_most_recent(self) -> None:
        log = SubcallLog()
        for i in range(5):
            log.record(subcall_type="extract", args_summary=f"call-{i}", result_summary=i)
        last_two = log.last(2)
        assert len(last_two) == 2
        assert last_two[0]["result"] == 3
        assert last_two[1]["result"] == 4

    def test_by_type_filters(self) -> None:
        log = SubcallLog()
        log.record(subcall_type="extract", args_summary="e1", result_summary="ex1")
        log.record(subcall_type="summarise", args_summary="s1", result_summary="sum1")
        log.record(subcall_type="extract", args_summary="e2", result_summary="ex2")

        extracts = log.by_type("extract")
        assert len(extracts) == 2
        assert extracts[0]["result"] == "ex1"

        summaries = log.by_type("summarise")
        assert len(summaries) == 1

    def test_by_type_unknown_returns_empty(self) -> None:
        log = SubcallLog()
        log.record(subcall_type="extract", args_summary="e", result_summary="r")
        assert log.by_type("verify") == []

    def test_tokens_tracked(self) -> None:
        log = SubcallLog()
        log.record(
            subcall_type="extract",
            args_summary="e",
            result_summary="r",
            input_tokens=100,
            output_tokens=50,
        )
        entry = log.all()[0]
        assert entry["input_tokens"] == 100
        assert entry["output_tokens"] == 50

    def test_str_gives_readable_summary(self) -> None:
        log = SubcallLog()
        log.record(subcall_type="extract", args_summary="fields=['a']", result_summary="ok")
        log.record(subcall_type="summarise", args_summary="content=...", result_summary="ok")
        text = str(log)
        assert "extract" in text
        assert "summarise" in text
        assert "2 entries" in text

    def test_to_scratchpad_returns_serialisable(self) -> None:
        log = SubcallLog()
        log.record(subcall_type="extract", args_summary="e", result_summary={"x": 1})
        data = log.to_scratchpad()
        assert isinstance(data, list)
        assert data[0]["type"] == "extract"
        assert data[0]["result"] == {"x": 1}

    def test_thread_safe_concurrent_writes(self) -> None:
        """SubcallLog should handle concurrent writes without data loss."""
        import threading

        log = SubcallLog()
        errors: list[str] = []

        def writer(thread_id: int) -> None:
            try:
                for i in range(50):
                    log.record(
                        subcall_type="extract",
                        args_summary=f"t{thread_id}-{i}",
                        result_summary=i,
                    )
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(log) == 200  # 4 threads x 50 records
