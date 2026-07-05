# ABOUTME: Captures review-loop lessons for constructing long-horizon AEC-Bench tasks.
# ABOUTME: Applies SME checklist-review patterns without claiming new runnable templates or source packs.

# Review-Loop Lessons For Long-Horizon Tasks

The Power Playground skill pack adds a useful design lens: a long-horizon task does not have to be a longer chain of calculations. It can be an auditable engineering review loop where the agent has to decide what is ready, what fails, what is missing, and what needs action before issue.

This is a research-design note only. It does not add runnable templates, accepted project evidence, executable source-pack parsers, generated benchmark instances, or benchmark readiness.

## Core Lesson

The strongest pattern in the SME skills is:

```text
source packet inventory
  -> design basis extraction
  -> source identity and scenario preservation
  -> checklist or risk taxonomy review
  -> pass/fail/not-applicable/insufficient-data labels
  -> findings and action register
  -> final completeness verification
```

That pattern turns long-horizon work into a review of an engineering evidence packet, not a formula marathon.

## What This Adds

- Missing data becomes a first-class result. A model should say `[ID]` and request the exact missing source, not invent a value.
- Failures need traceability. A finding should point to the source artifact, affected object, consequence, and corrective action.
- Not-applicable needs a scope reason. It should not be a quiet skip.
- Review artifacts become outputs. The task can ask for a completed checklist, findings summary, action register, risk register, verification log, or issue-readiness memo.
- Final verification becomes part of the task. Every failure needs an action, every insufficient-data item needs a request, and every visible major object should be accounted for.
- Identity preservation is still the spine. The same asset, chainage, feeder, relay, room, cabinet, storm case, or authority criterion has to survive across documents and the final memo.

## Verifier Implications

A review-loop verifier should check more than final scalar answers:

- source IDs and object IDs are preserved;
- every checklist item has exactly one status;
- `[F]` items cite a source and produce an action;
- `[ID]` items name the missing data;
- `[N/A]` items state a scope reason;
- critical issues are prioritized above ordinary documentation gaps;
- action items match the findings they claim to resolve;
- the response avoids unsupported compliance, approval, certification, or benchmark-readiness claims.

## Construction Implications

For future source packs, include both calculation tables and review artifacts:

- source manifest with document IDs, revisions, object IDs, and authority roles;
- source tables for the values used in checks;
- a checklist or risk taxonomy with stable item IDs;
- an expected-output schema for statuses, findings, actions, and unresolved gaps;
- negative cases for source conflict, missing data, object drift, authority collapse, and unsupported repair;
- an explicit non-claim boundary.

## SSC-01 Pilot

The first applied pilot is `SSC-01` road/corridor profile and traffic scene. The review-loop lens adds an "issue-readiness" view over the existing corridor products: instead of only checking drainage, signal timing, ITS, and cabinet power, the task can ask whether the corridor package is ready to issue, which assumptions fail, which data is missing, and what actions must be resolved.

The original calculation-chain `SSC-01-LH-01` product remains preserved in `../shared-subworld-designs/ssc-01-road-corridor-profile-long-horizon-design.md`. The separate review-first redesign is captured in `ssc01-lh01-review-first-redesign.md`.
