# ABOUTME: Independently scores a synthetic inspection report from its submitted JSON.
# ABOUTME: Checks stated counts, source attribution, and concise presentation without actor state.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def evaluate(text: str) -> dict[str, float]:
    try:
        payload = json.loads(text)
    except (ValueError, TypeError):
        payload = None
    sections = []
    if isinstance(payload, dict):
        for sid in ("findings", "summary"):
            section = payload.get(sid)
            value = section.get("text") if isinstance(section, dict) else None
            if isinstance(value, str) and value.strip():
                sections.append(value)
    if len(sections) != 2:
        return {"evidence": 0.0, "clarity": 0.0}
    count_correct = all(set(re.findall(r"\b\d+\b", value)) == {"12"} for value in sections)
    attributed = all("inspection" in value.lower() for value in sections)
    return {
        "evidence": float(count_correct and attributed),
        "clarity": float(all(len(value) < 160 for value in sections)),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("/workspace/output.json"))
    parser.add_argument("--output", type=Path, default=Path("/logs/verifier/reward.json"))
    args = parser.parse_args()
    details = evaluate(args.input.read_text() if args.input.exists() else "")
    reward = (2 * details["evidence"] + details["clarity"]) / 3
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"reward": round(reward, 4)}))
    (args.output.parent / "details.json").write_text(json.dumps(details))


if __name__ == "__main__":
    main()
