#!/usr/bin/env python3
# ABOUTME: Compares pytest JUnit results for two commits without requiring a green baseline.
# ABOUTME: Reports retained, removed, and newly introduced failures as deterministic JSON.

from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _case_id(case: ET.Element) -> str:
    class_name = case.get("classname", "")
    test_name = case.get("name", "")
    return f"{class_name}::{test_name}" if class_name else test_name


def _read_results(path: Path) -> dict[str, Any]:
    root = ET.parse(path).getroot()
    cases = tuple(root.iter("testcase"))
    failures = sorted(
        _case_id(case) for case in cases if case.find("failure") is not None or case.find("error") is not None
    )
    return {
        "tests": len(cases),
        "passed": sum(
            case.find("failure") is None and case.find("error") is None and case.find("skipped") is None
            for case in cases
        ),
        "failed_or_error": len(failures),
        "skipped": sum(case.find("skipped") is not None for case in cases),
        "failure_ids": failures,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent", type=Path, required=True)
    parser.add_argument("--parent-commit", required=True)
    parser.add_argument("--head", type=Path, required=True)
    parser.add_argument("--head-commit", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    parent = _read_results(args.parent)
    head = _read_results(args.head)
    parent_failures = set(parent["failure_ids"])
    head_failures = set(head["failure_ids"])
    report = {
        "schema_version": "1",
        "command": args.command,
        "parent_commit": args.parent_commit,
        "head_commit": args.head_commit,
        "parent": parent,
        "head": head,
        "retained_failures": sorted(parent_failures & head_failures),
        "removed_failures": sorted(parent_failures - head_failures),
        "new_failures": sorted(head_failures - parent_failures),
        "no_new_failures": not (head_failures - parent_failures),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
