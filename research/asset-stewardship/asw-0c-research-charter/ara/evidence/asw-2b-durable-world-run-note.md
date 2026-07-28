# ABOUTME: Records the ASW-2B durable pump-station world-run evidence.
# ABOUTME: Links immutable storage, snapshot, replay, duration, and crash-recovery checks.

# ASW-2B durable world-run evidence

Production paths:

- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/world_run.py`
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/world_run_models.py`
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/world_run_repository.py`
- `src/aec_bench/task_world_templates/stewardship/wastewater_pump_station/world_run_serialization.py`

The host supplies one filesystem root for one pump-station run. The repository
writes immutable state, proposal, information-set, receipt, event-batch, and
commit artifacts. It then uses one atomic `current.json` replacement as the
transition commit point. A local file lock serializes writers.

The crash end-to-end test stages real immutable artifacts and stops before
pointer publication. Resume still selects the earlier state. Retrying the same
proposal publishes the transition once. A second resume models a lost caller
response after publication. Repeating the proposal returns the stored
transition. It does not create a second obligation, work order, restriction, or
duty transfer.

The filesystem integration test also advances through a real inspection event.
The resumed state retains the simulated calendar duration and the exact applied
event identity.

Focused commands:

```text
uv run pytest -q tests/task_world_templates/stewardship/wastewater_pump_station
uv run ruff check src/aec_bench/task_world_templates/stewardship/wastewater_pump_station tests/task_world_templates/stewardship/wastewater_pump_station
uv run ruff format --check src/aec_bench/task_world_templates/stewardship/wastewater_pump_station tests/task_world_templates/stewardship/wastewater_pump_station
uv run mypy <six changed pump-station production modules>
```

Observed results:

- pump-station tests: 55 passed;
- new ASW-2B tests: 6 passed;
- Ruff lint: passed;
- Ruff format: passed; and
- focused Mypy: passed for six changed production modules.

No CLI, Harbor, `TrialRecord`, study runner, provider call, database, or shared
stewardship runtime is part of this evidence.
