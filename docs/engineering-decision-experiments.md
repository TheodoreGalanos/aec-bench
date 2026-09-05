# Engineering decision experiments

| Field | Value |
| --- | --- |
| Class | Guide |
| Status | Current |
| Owner | Experimentation and task owners |

The library supplies hydraulic lineage generation and revision checks, costed dam
investigation semantics, and public pump handover assessment. Four separate
experiments consume these capabilities: hydraulic counterfactuals, dam investigations,
pump handover continuation, and verifier challenges. A qualification command checks
the same experiments against stated control expectations. It uses deterministic
controls through the existing lifecycle and actor runtimes. It does not call a model,
train weights, establish transfer, or certify real engineering decisions.

Run one experiment from the repository root, with development dependencies installed:

```bash
uv run python -m aec_bench.experimentation.engineering_decisions dam \
  --output /tmp/aec-dam-investigation
```

The other choices are `hydraulic`, `pump`, and `verifier`. Supply `--definition`
with a JSON condition definition or a previous `experiment.json` to repeat those
conditions in a new output directory. The saved definition declares seeds and
partitions, revisions, profiles, policies, action limits, or the closing horizon,
as applicable. Duplicate conditions and lineage assignments are rejected.

Each experiment saves its definition and `PlannedTrial` values before execution.
Hydraulic execution uses `run_lifecycle_trial()`. Dam and pump execution use
`run_world_experiment()` with deterministic controllers and the existing world
hosts. All return ordinary `TrialRecord` values and publish them through the
ledger writer. Records retain the experiment definition, source digests, diagnostics,
and execution evidence. Pump records also retain the existing world repository
files in a `world_run` ZIP artifact. Restore it to a private directory, with
owner-only directory access and file read/write permissions, before opening the
canonical repository. The source digests identify source bytes; they are not a source archive.
Use the same package build and dependency environment for reproduction.

The controls are explicit Python policies. This command does not select arbitrary
model adapters. Model comparisons can use the domain capabilities through their
normal lifecycle or world runner, with a separately declared experiment.

Run qualification for all four experiments:

```bash
uv run python -m aec_bench.experimentation.qualification.engineering_decisions \
  --output /tmp/aec-engineering-decisions
```

The destination must be empty. `--seeds 2 8 12` selects the default synthetic project
lineages. The command returns non-zero when a control fails its stated expectation.
The root `qualification.json` records checks, source hashes, and projections of
the retained trial diagnostics. It does not define a second reward.
Each experiment has its own `experiment.json` and `ledger/`. Hydraulic packages
and durable pump runs remain beside them for inspection. Output contains verifier
diagnostics and public synthetic examples labelled for intended acceptance use;
keep it private when preparing a later acceptance bank.
The command creates a new output directory with owner-only access.

## Hydraulic changes and generated data

`HydraulicLineage` varies catchment area, correlated basin area, and rainfall within
narrow synthetic ranges. Each seed produces one baseline and the existing
administrative, rainfall, outlet, and tailwater revision siblings. The lifecycle
materializer accepts `lineage=HydraulicLineage(seed=...)`; ordinary materialization
continues to use the authored calibration sources.

The hydraulic experiment assigns each seed to exactly one explicit train, development,
or acceptance partition before it expands revision siblings. `HydraulicLineage` has
no split policy. Every sibling remains with its project. Custom qualification seed
lists use the development partition; the default experiment declares all three. These labels do not make the
qualification output a sealed acceptance set. Freeze and protect a separate bank
before using it for a learning claim. Nearby scalar variants do not establish
mechanism or topology transfer, and the ranges are not an SME-calibrated distribution.

The package validator regenerates the expected sources from the recorded seed.
The normal solver, operation resolver, checkpoint runtime, and eleven-gate verifier
then execute the lifecycle. The resolver's actual input projections determine
retention and invalidation. The verifier no longer contains a second revision-to-reuse
lookup table. The report separates physical readiness from valid reporting of a
physical failure.

## Investigation cost and delay

Dam scenarios can declare `SeepageInvestigation`: investigation credits, response
deadline, action prices, and inspection durations. These values are public task
constraints. Accepted investigations consume credits. Rejected investigations do
not change state. A confirmation reading advances time to at least its scheduled
time; inspections add their declared duration. Late submissions remain observable
but cannot be successful. Existing scenarios without this declaration retain their
cost-free, untimed behaviour.

The three costed scenarios are registered, content-pinned world profiles.
The qualification includes two identical opening observations with different hidden
instrument conditions, plus an urgent fault case. Its observation-only control checks
the instrument, escalates on released fault evidence, or completes the evidence
needed for routine surveillance. The experiment applies evidence-first, unsupported-response, and delayed-response
controls to every selected profile. Qualification checks the relevant contrasts.

Outcome correctness, evidence completeness, timeliness, expenditure, and rejections
remain separate fields. The private exhaustive search reports a **perfect-information
minimum cost**. It is a lower bound for each hidden scenario, not a feasible policy
or a measured expected value of information. Scenario construction and task semantics
belong to the dam owner; qualification and policy comparisons belong to experimentation.

## Pump continuation and handover

The pump control creates independent runs from the same registered opening state and
uses the same absolute closing horizon. One handover contains the public verification
work item; the other omits it. A fresh actor host chooses whether to start that work
from the handover. The normal actor interface advances time, and the existing host
policy applies eligible Operations reviews. Neither control receives new authority.
A completed continuation must replay successfully and close at exactly the requested
world boundary. The action limit counts the initial verification request and continuation actions.
Exhausting that limit produces a failed, truncated
trial with its observed closing time; it cannot claim the requested horizon was reached.

`PumpHandover` carries facts from one released actor view: clocks, duty assignment,
restrictions, liabilities, accepted evidence and its health, resources and schedules,
work, active processes, and physical boundaries. Its assessment identifies omitted,
contradicted, invented, and stale information. The source view identity binds the
assessment to an exact observation. A handover is a communication artifact, not a
second world state or an approval.

The deliberately weak omitted-work control measures a causal consequence of missing
handover content. It does not demonstrate that a model can recover from incomplete
records. The horizon is a bounded continuation, not complete operational success.
The existing frozen `handover_omission_count` field stays reserved and unmeasured;
the explicit `handover_assessment` in this experiment has its own defined scope.

## Verifier challenge cases

The hydraulic control changes actor submissions **before** host acceptance. Cases
include stale source identity, missing memo evidence, false readiness, and an
unsupported authority claim. A reordered but consistent decision list is a positive
control. The command records expected and observed acceptance, including individual
gate failures. These cases are maintained examples, not proof against every exploit.

Permanent tests also cover budget rejection, correct answers without sufficient
evidence, late supported answers, handover omissions and contradictions, and exact
pump replay. Do not turn deterministic control success into a model-performance,
real-project, or RL-readiness claim. Weight training and its hosted integration remain
separate work.
