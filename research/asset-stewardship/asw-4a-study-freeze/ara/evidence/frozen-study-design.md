# Frozen study design evidence

## Authority

- Research charter: `ASW-0C-3`.
- Station profile: `AU-NSW-LH-SYN-SPS-v1`.
- Study stage: `ASW-4A`.
- Execution class: generated analysis fixture.

## Fixed plan

- 32 paired blocks and 64 planned trajectories.
- 16 H1 stable-inspected blocks.
- 16 H2 worsening-verification blocks.
- Complete current station view and structured handover in each pair.
- Hidden windows of 86,400 and 115,200 simulated seconds.
- Counterbalanced treatment order.
- Each block binds its planned history and event-schedule identities.

## Fixed per-trajectory limits

- 16 model turns.
- 12 agent proposals.
- 32 host commands.
- One fresh handover.
- No temporal retrieval.
- No external historical search.
- No visible evaluation-window position.
- No visible future event schedule.

## Fixed analysis

- Binary required-follow-up continuity failure.
- Paired difference: structured handover minus current station view.
- Minimum meaningful absolute effect: `0.25`.
- 20,000 paired block-bootstrap resamples.
- Deterministic seed: `20260729`.
- Two-sided 95% interval.
- At least 28 eligible pairs.
- Maximum host-fault arm imbalance: 2.
- Missing pairs are not replaced.

## Model-phase authority slots

The versioned manifest requires one phase-specific approval before model
execution. The approval records:

- provider, model, and adapter identity;
- maximum provider calls;
- maximum input and output tokens per call;
- maximum total tokens;
- spend currency; and
- maximum spend in currency microunits.

ASW-4A leaves this approval empty and therefore authorizes zero provider calls.

These values come from sections 10 to 12 of
`research/asset-stewardship/asw-0c-research-charter.md`. ASW-4A binds them in
strict, content-addressed study-local contracts.
