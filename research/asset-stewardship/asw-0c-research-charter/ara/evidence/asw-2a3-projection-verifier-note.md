# ASW-2A3 projection and verifier evidence note

ASW-2A3 implements the in-memory actor projection and task-verifier boundary
under:

```text
src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/
```

The production path:

- projects the current quantized station observation, visible clocks,
  environment, resources, restrictions, obligations, work orders, processes,
  and evidence;
- records separate episode and actor-tenure elapsed time;
- creates a bounded structured handover without mutating authoritative state;
- binds each proposal to the exact actor view, tenure observation manifest, and
  current visible context;
- rejects stale bindings before execution;
- keeps full authoritative state identity in transition receipts and verifier
  replay, not in the actor projection; and
- replays immutable proposal steps through a separate pure task verifier.

The redaction test changes only the hidden future event schedule and proves that
the actor view and its identity do not change.

Focused validation on 2026-07-29:

```text
uv run pytest tests/task_world_templates/stewardship/wastewater_pump_station
49 passed

uv run ruff check <pump-station production and test paths>
All checks passed

uv run ruff format --check <pump-station production and test paths>
24 files already formatted

uv run mypy <five changed production modules>
Success: no issues found
```

Pandoc also parsed the PRD and charter successfully as GitHub-flavoured
Markdown.
