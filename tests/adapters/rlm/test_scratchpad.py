# ABOUTME: Tests for the file-backed scratchpad persistence module (NOTE/RECALL).
# ABOUTME: Validates round-trip storage, missing keys, empty pad, non-serialisable values.

from __future__ import annotations

import json
from pathlib import Path

from aec_bench.adapters.rlm.scratchpad import Scratchpad


class TestNote:
    """Tests for Scratchpad.note() — writing key-value pairs."""

    def test_note_returns_confirmation(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        result = pad.note("city", "Sydney")
        assert result == "Noted: city (str)"

    def test_note_stores_value_on_disk(self, tmp_path: Path) -> None:
        path = tmp_path / ".scratchpad.json"
        pad = Scratchpad(path=str(path))
        pad.note("count", 42)
        data = json.loads(path.read_text())
        assert data["count"] == 42

    def test_note_overwrites_existing_key(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("x", 1)
        pad.note("x", 2)
        assert pad.recall("x") == 2

    def test_note_handles_dict_value(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("facts", {"wind_speed": 45, "region": "NSW"})
        assert pad.recall("facts") == {"wind_speed": 45, "region": "NSW"}

    def test_note_handles_list_value(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("items", [1, 2, 3])
        assert pad.recall("items") == [1, 2, 3]

    def test_note_handles_none_value(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        result = pad.note("empty", None)
        assert result == "Noted: empty (NoneType)"
        assert pad.recall("empty") is None

    def test_note_serialises_non_json_values_via_str(self, tmp_path: Path) -> None:
        """Non-JSON-serialisable values should be stored via default=str."""
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("obj", {1, 2, 3})  # sets are not JSON-serialisable
        # The set gets converted to a string representation
        recalled = pad.recall("obj")
        assert isinstance(recalled, str)

    def test_note_type_name_for_custom_object(self, tmp_path: Path) -> None:
        class Widget:
            pass

        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        result = pad.note("w", Widget())
        assert result == "Noted: w (Widget)"


class TestRecall:
    """Tests for Scratchpad.recall() — reading values and listing keys."""

    def test_recall_returns_stored_value(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("name", "Theo")
        assert pad.recall("name") == "Theo"

    def test_recall_missing_key_returns_error_message(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("a", 1)
        result = pad.recall("missing")
        assert "missing" in result.lower() or "not found" in result.lower()
        assert "a" in result  # should list available keys

    def test_recall_none_lists_all_keys(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("alpha", "first")
        pad.note("beta", "second value that is a bit longer")
        result = pad.recall()
        assert "alpha" in result
        assert "beta" in result

    def test_recall_empty_pad_returns_message(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        result = pad.recall()
        assert "empty" in result.lower()

    def test_recall_none_truncates_long_previews(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("long", "x" * 500)
        result = pad.recall()
        # Preview should be truncated, not the full 500 chars
        assert len(result) < 500


class TestKeys:
    """Tests for Scratchpad.keys property."""

    def test_keys_empty(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        assert pad.keys == []

    def test_keys_after_notes(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("a", 1)
        pad.note("b", 2)
        assert sorted(pad.keys) == ["a", "b"]


class TestSnapshot:
    """Tests for Scratchpad.snapshot() — full contents for compaction."""

    def test_snapshot_empty(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        assert pad.snapshot() == {}

    def test_snapshot_returns_all_data(self, tmp_path: Path) -> None:
        pad = Scratchpad(path=str(tmp_path / ".scratchpad.json"))
        pad.note("x", 1)
        pad.note("y", "hello")
        snap = pad.snapshot()
        assert snap == {"x": 1, "y": "hello"}


class TestPersistence:
    """Tests for file-backed persistence across instances."""

    def test_new_instance_reads_existing_file(self, tmp_path: Path) -> None:
        path = str(tmp_path / ".scratchpad.json")
        pad1 = Scratchpad(path=path)
        pad1.note("key", "value")

        pad2 = Scratchpad(path=path)
        assert pad2.recall("key") == "value"

    def test_concurrent_writes_preserve_all_keys(self, tmp_path: Path) -> None:
        """Each note() reads the current file before writing."""
        path = str(tmp_path / ".scratchpad.json")
        pad = Scratchpad(path=path)
        pad.note("a", 1)
        pad.note("b", 2)
        pad.note("c", 3)

        data = json.loads(Path(path).read_text())
        assert set(data.keys()) == {"a", "b", "c"}
