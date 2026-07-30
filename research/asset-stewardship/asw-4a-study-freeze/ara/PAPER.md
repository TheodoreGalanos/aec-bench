---
ara_schema_version: "0.1"
title: ASW-4A provider-free stewardship continuity study freeze
---

# Research continuation summary

ASW-4A freezes the first stewardship continuity study before a model is used.
It implements a study-local manifest, a complete paired plan, typed treatment
delivery, a failure taxonomy, a paired reducer, immutable evidence, and
independent report reload.

The research question stays unchanged:

> Under matched continuing pump-station histories, does a structured handover
> reduce required-follow-up continuity failure when compared with a complete
> current station view?

## Frozen study design

| Item | Frozen value |
| --- | --- |
| Research authority | `ASW-0C-3` |
| Station profile | `AU-NSW-LH-SYN-SPS-v1` |
| Treatments | Complete current station view; structured handover |
| History classes | 16 H1 stable-inspected blocks; 16 H2 worsening-verification blocks |
| Plan | 32 paired blocks; 64 planned trajectories |
| Hidden windows | `3D` and `4D`, with `D = 28,800` simulated seconds |
| Per-trajectory limits | 16 model turns; 12 proposals; 32 host commands; one fresh handover |
| Search | No temporal retrieval and no external historical search |
| Hidden information | Evaluation-window position and future events |
| Endpoint | Binary required-follow-up continuity failure |
| Difference | Structured handover minus current station view |
| Meaningful effect | Absolute paired risk reduction of `0.25` |
| Uncertainty | 20,000 paired block-bootstrap resamples; seed `20260729`; 95% interval |
| Coverage gate | At least 28 eligible pairs; host-fault arm imbalance no more than 2 |

The plan counterbalances treatment order. Each pair binds the same current
station state, current duties, world history, event schedule, model condition,
logical limits, and hidden evaluation window.

## Provider-free proof

Generated analysis fixtures pass through the real study contracts, immutable
artifact store, reducer, report writer, and independent reload path. They make
zero provider calls, use zero tokens and spend, create zero study outcomes, and
change no task reward.

The generated fixture has a paired risk difference of `-0.5` and a 95% interval
of `[-0.65625, -0.34375]`. This proves that the frozen decision rule can detect
its known input. It is not evidence about model performance. The authoritative
fixture conclusion is `analysis_fixture`, not `supported`.

The fixture identities are:

- manifest: `91de00556cfa451bd8a9da595d4cc25e2f30ddfe7c60e65e23c85e35332bd02a`;
- plan: `9c541a784ee5586d3b0875fae8a78da1ae6445aaccde4b8487cb1f61b9dfe286`; and
- report: `91084bb1a9c585b150cc3c30bd82f2dbfcef1bd8d05b971e152e1b703a807667`.

Repeated publication keeps the same identities. Independent reload rejects
changed report bytes and recomputes the report from the exact manifest, plan,
treatment-delivery records, and observations.

Report authority is phase-bound. Analysis fixtures can report only
`analysis_fixture`. A shakedown can report only `shakedown`, even when its
diagnostic values cross the confirmatory threshold. Only a confirmatory
generation can report `supported`, `refuted`, `inconclusive`, or
`coverage_blocked`.

## Boundary

The continuity study remains under
`aec_bench.experiments.stewardship_continuity`. It does not change the physical
world, operating rules, host session, Harbor path, evaluation reward, or shared
contracts. It does not extract the ASW-3C publication candidate.

Provider identity, model identity, token limits, and approved spend remain open
under `OD-14`. ASW-4B cannot start until Theo gives separate approval for those
values. The approval is phase-specific and content-bound to the model condition.
ASW-4B evidence cannot enter the confirmatory result.

Artifact layers:

- `logic/claims.yaml` records the supported and provisional claims.
- `logic/experiments.yaml` records the provider-free checks.
- `evidence/index.yaml` points to the design and verification records.
- `trace/exploration_tree.yaml` records the freeze and the approval stop.
- `staging/observations.yaml` retains the open provider decision.
