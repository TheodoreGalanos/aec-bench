# Manual Task Authoring Guidance

When a task fails any of the 5 feasibility criteria (see
`feasibility-criteria.md`), it cannot be turned into a parameterised template.
Instead, each benchmark instance must be authored by hand. This document
describes the required file structure and conventions.

---

## Required Files

Every manual task instance lives under `tasks/<discipline>/<task-type>/<instance-name>/`
and must contain these files:

```
tasks/<discipline>/<task-type>/<instance-name>/
  task.toml             # Metadata, difficulty, tool declarations
  instruction.md        # The prompt sent to the agent
  environment/
    Dockerfile          # Container setup for the task runtime
  tests/
    test.sh             # REQUIRED — Harbor's verifier entry point
    verify.py           # Python verifier that scores agent output
    ground_truth.json   # Expected answers (if using external ground truth)
```

### Harbor Container Convention

Harbor uploads directories to the container at specific mount points:

| Local path | Container path | Purpose |
|------------|---------------|---------|
| `tests/*` | `/tests/*` | Verifier scripts, ground truth, fixtures |
| `environment/` | _(build context)_ | Dockerfile build context only |
| _(agent output)_ | `/workspace/*` | Agent writes output here at runtime |
| _(verifier output)_ | `/logs/verifier/*` | Verifier writes reward here |

**Important:** Only `tests/` is uploaded to the container at runtime. Files at the
task root (like `ground_truth.json`) are NOT available inside the container.
Place all verifier dependencies in `tests/`.

---

## 1. task.toml

Declares task metadata, difficulty level, and any tools available to the agent.

```toml
version = "1.0"

[metadata]
difficulty = "medium"
category = "power-systems"
tags = ["electrical", "grid-control"]

[agent]
timeout_sec = 600.0

[verifier]
timeout_sec = 120.0

[environment]
extensions = ["multimodal"]    # optional — generates Dockerfile from extensions
cpus = 1
memory_mb = 2048
allow_internet = true

# Optional: declare tools available to the agent
[[environment.tools]]
name = "create_chart"
source = "tools/create_chart.py"
description = "Generate a chart from computed data."
returns_image = true
```

`returns_image = true` documents that the tool may produce image files. The unified entrypoint currently passes tool output as text, so binary image self-review requires an intentionally selected legacy script route.

---

## 2. instruction.md

The prompt the agent receives. Write it as a clear engineering brief:

- State what the agent must calculate or evaluate.
- Provide all necessary input data inline (or reference files in the environment).
- Specify the expected output format so `verify.py` can parse it.
- Tell the agent to write output to `/workspace/output.md`.
- Include a JSON block format the verifier can extract.

---

## 3. environment/Dockerfile

Sets up the container the agent runs inside. Can be auto-generated from
`extensions` in task.toml (run `aec-bench generate dockerfiles`), or written
manually for custom setups.

---

## 4. tests/test.sh — Harbor Entry Point

Harbor always runs `/tests/test.sh` as the verifier entry point. This file is
**required** for every task. Use this standard wrapper:

```bash
#!/bin/bash
# ABOUTME: Thin wrapper that runs the Python verifier.
# ABOUTME: Ensures reward.json is always written, even on crash.

REWARD_FILE="/logs/verifier/reward.json"
mkdir -p /logs/verifier
trap 'if [ ! -f "$REWARD_FILE" ]; then echo "{\"reward\": 0.0}" > "$REWARD_FILE"; fi' EXIT
python3 /tests/verify.py
```

The trap ensures a reward file is always written, even if the verifier crashes.
This prevents `RewardFileNotFoundError` in Harbor.

---

## 5. tests/verify.py — Scoring Logic

The verifier script that scores the agent's output.

### Path Conventions Inside the Container

| Path | Purpose |
|------|---------|
| `/workspace/output.md` | Agent's output (read by verifier) |
| `/tests/ground_truth.json` | Expected answers (uploaded from `tests/`) |
| `/tests/verify.py` | The verifier script itself |
| `/logs/verifier/reward.json` | Reward output (written by verifier) |
| `/logs/verifier/details.json` | Per-field breakdown (written by verifier) |

### Ground Truth Approaches

**Option A: External file** — Place `ground_truth.json` in `tests/` (it gets
uploaded to `/tests/ground_truth.json` in the container):

```python
DEFAULT_GROUND_TRUTH_FILE = Path("/tests/ground_truth.json")
```

**Option B: Computed inline** — Compute expected values directly in `verify.py`
(like generated tasks do). Preferred when ground truth is a deterministic
formula.

### Reward Shape Convention

Harbor's `Mean` metric requires a specific JSON format. The verifier must write
two files:

**`/logs/verifier/reward.json`** (required):
```json
{"reward": 0.85}
```

The `reward` value must be a float between `0.0` (complete failure) and `1.0`
(perfect score). This file must contain exactly one key: `"reward"`.

**`/logs/verifier/details.json`** (recommended):
```json
{"field_a": 1.0, "field_b": 0.0, "field_c": 1.0}
```

Per-field scoring details go in `details.json`, keeping `reward.json` clean for
Harbor's metric aggregation.

### Example Verifier Pattern

```python
import argparse
import json
import math
import re
from pathlib import Path

DEFAULT_OUTPUT_FILE = Path("/workspace/output.md")
DEFAULT_GROUND_TRUTH_FILE = Path("/tests/ground_truth.json")
DEFAULT_REWARD_FILE = Path("/logs/verifier/reward.json")

FIELDS = ["field_a", "field_b"]
REL_TOL = 0.03


def write_reward(reward: float, details: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"reward": round(reward, 2)}))
    (path.parent / "details.json").write_text(json.dumps(details))


def extract_json_block(text: str) -> dict | None:
    pattern = r"```json\s*\n(.*?)\n\s*```"
    matches = re.findall(pattern, text, re.DOTALL)
    if not matches:
        return None
    try:
        return json.loads(matches[-1])
    except json.JSONDecodeError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT_FILE)
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GROUND_TRUTH_FILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_REWARD_FILE)
    args = parser.parse_args()

    try:
        if not args.input.exists() or args.input.stat().st_size == 0:
            write_reward(0.0, {k: 0.0 for k in FIELDS}, args.output)
            return

        expected = json.loads(args.ground_truth.read_text())
        actual = extract_json_block(args.input.read_text())

        if not actual:
            write_reward(0.0, {k: 0.0 for k in FIELDS}, args.output)
            return

        details = {}
        for key in FIELDS:
            exp = expected.get(key)
            act = actual.get(key)
            if exp is not None and act is not None:
                details[key] = 1.0 if math.isclose(float(act), exp, rel_tol=REL_TOL) else 0.0
            else:
                details[key] = 0.0

        reward = sum(details.values()) / len(FIELDS)
        write_reward(round(reward, 2), details, args.output)
    except Exception:
        write_reward(0.0, {k: 0.0 for k in FIELDS}, args.output)


if __name__ == "__main__":
    main()
```

---

## Working Examples

See existing task instances for reference implementations:

- **Generated tasks:** `tasks/ground/` and `tasks/electrical/` contain instances
  produced by generation templates. These follow all conventions correctly.
- **Chart-generation tasks:** `tasks/electrical/pf-droop/` and `tasks/electrical/qv-droop/`
  are manually-authored tasks with tool declarations and chart generation.
- **Seed tasks:** `tasks/civil/`, `tasks/mechanical/`, and `tasks/structural/`
  contain seed inventories that describe tasks but may not yet have full instance
  directories.
