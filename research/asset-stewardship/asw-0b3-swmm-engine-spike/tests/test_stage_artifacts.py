# ABOUTME: Tests the durable B3 decision and compact verification summary as bounded research evidence.
# ABOUTME: Ensures the handoff authorises only B4 and contains no local-path or production-contract leakage.

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ASSET_RESEARCH_ROOT = Path(__file__).resolve().parents[2]
DECISION_PATH = ASSET_RESEARCH_ROOT / "au-nsw-lh-syn-sps-v1-engine-role-decision.md"
RECORD_PATH = ASSET_RESEARCH_ROOT / "au-nsw-lh-syn-sps-v1-engine-verification-record.json"


def test_compact_record_preserves_research_only_authority() -> None:
    record = json.loads(RECORD_PATH.read_text(encoding="utf-8"))

    assert record["status"] == "pass"
    assert record["authority"] == {
        "stage": "ASW-0B3",
        "scope": "research_only",
        "promotable": False,
        "path_is_contract": False,
        "world_parameters_selected": False,
        "raw_engine_artifacts_promoted": False,
    }
    assert record["execution"]["real_engine_runs"] == 4
    assert record["execution"]["engine_errors"] == 0
    assert record["execution"]["engine_warnings"] == 0
    assert record["limitations"]["physical_world_certified"] is False
    assert record["limitations"]["runtime_dependency_authorized"] is False


def test_decision_binds_the_compact_record_and_only_opens_b4() -> None:
    decision = DECISION_PATH.read_text(encoding="utf-8")
    record_sha = hashlib.sha256(RECORD_PATH.read_bytes()).hexdigest()

    assert f"Compact verification record SHA-256 | `{record_sha}`" in decision
    assert "**ASW-0B3 is accepted. ASW-0B4 is authorised as the only next stage.**" in decision
    assert "Offline generator/oracle | **Selected for B4 protocol design**" in decision
    assert "Independent certifier | **Not selected**" in decision
    assert "Asset-world runtime | **Rejected for the first implementation**" in decision


def test_durable_artifacts_contain_no_ephemeral_local_paths() -> None:
    combined = DECISION_PATH.read_text(encoding="utf-8") + RECORD_PATH.read_text(encoding="utf-8")

    assert "/private/tmp" not in combined
    assert "/Users/" not in combined
    assert ".worktrees/" not in combined
