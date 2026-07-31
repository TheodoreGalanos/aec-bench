# ASW-5 entry gate

## Provisional hypothesis

Information continuity can affect outcomes or process quality when correct
action depends on several overlapping required follow-ups, work processes,
operating limits, and reserved resources.

This is a hypothesis for ASW-5. It is not an ASW-4 finding.

## Authorized scope

ASW-5 can add:

- composite triggers;
- required-follow-up dependencies;
- waiver and suspension;
- nested operating limits;
- spare and access reservations;
- overlapping timed processes and work orders; and
- dependency-aware rescheduling and cancellation.

ASW-5 remains asset-local and provider-free. It does not add a generic
expression language, shared stewardship runtime, new provider study, temporal
evidence retrieval, imperfect repair, coupled assets, or institutional
adaptation.

## Required checks

The ASW-5 exit gate must prove:

- one resource cannot be reserved or consumed twice;
- suspension, waiver, cancellation, and rescheduling preserve explicit state
  and evidence;
- dependency changes cannot leave silent or unreachable required follow-up;
- simultaneous events retain one deterministic order;
- overlapping work does not duplicate physical or institutional effects;
- snapshot, resume, retry, crash recovery, and replay retain the same result;
- current views and structured handovers retain correct redaction and
  information-set binding; and
- the complete process state survives a fresh agent handover without a
  conservation error.

No model study is part of this gate. A later study must define process-quality
measures and a no-meaningful-difference rule before provider execution.
