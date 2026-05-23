# ABOUTME: Tests for parallel() — concurrent sub-call execution.
# ABOUTME: Validates ordering, error handling, thread safety, and max_workers.

from __future__ import annotations

import time

from aec_bench.adapters.rlm.parallel import ParallelError, parallel


class TestParallel:
    """Core parallel() behaviour."""

    def test_returns_results_in_order(self) -> None:
        results = parallel(
            [
                lambda: "first",
                lambda: "second",
                lambda: "third",
            ]
        )
        assert results == ["first", "second", "third"]

    def test_actually_runs_concurrently(self) -> None:
        """Three 0.1s sleeps should complete in ~0.1s not ~0.3s."""

        def slow() -> str:
            time.sleep(0.1)
            return "done"

        start = time.monotonic()
        results = parallel([slow, slow, slow], max_workers=3)
        elapsed = time.monotonic() - start

        assert all(r == "done" for r in results)
        assert elapsed < 0.25  # should be ~0.1s, allow margin

    def test_handles_single_failure(self) -> None:
        def good() -> str:
            return "ok"

        def bad() -> str:
            raise ValueError("boom")

        results = parallel([good, bad, good])
        assert results[0] == "ok"
        assert results[2] == "ok"
        assert isinstance(results[1], ParallelError)
        assert "boom" in results[1].error

    def test_handles_all_failures(self) -> None:
        def bad() -> str:
            raise RuntimeError("fail")

        results = parallel([bad, bad])
        assert all(isinstance(r, ParallelError) for r in results)

    def test_empty_list_returns_empty(self) -> None:
        assert parallel([]) == []

    def test_single_callable(self) -> None:
        results = parallel([lambda: 42])
        assert results == [42]

    def test_max_workers_limits_concurrency(self) -> None:
        """With max_workers=1, execution should be sequential."""
        import threading

        peak = {"count": 0, "max": 0}
        lock = threading.Lock()

        def tracked() -> str:
            with lock:
                peak["count"] += 1
                peak["max"] = max(peak["max"], peak["count"])
            time.sleep(0.05)
            with lock:
                peak["count"] -= 1
            return "done"

        parallel([tracked] * 4, max_workers=1)
        assert peak["max"] == 1

    def test_preserves_return_types(self) -> None:
        results = parallel(
            [
                lambda: {"key": "value"},
                lambda: [1, 2, 3],
                lambda: 42,
                lambda: None,
            ]
        )
        assert results[0] == {"key": "value"}
        assert results[1] == [1, 2, 3]
        assert results[2] == 42
        assert results[3] is None

    def test_parallel_error_has_index(self) -> None:
        results = parallel(
            [
                lambda: "ok",
                lambda: (_ for _ in ()).throw(ValueError("idx1")),
                lambda: "ok",
                lambda: (_ for _ in ()).throw(TypeError("idx3")),
            ]
        )
        assert isinstance(results[1], ParallelError)
        assert results[1].index == 1
        assert isinstance(results[3], ParallelError)
        assert results[3].index == 3
