# ABOUTME: Redesigns SSC-01-LH-01 as a review-first long-horizon task.
# ABOUTME: Preserves the existing calculation-chain task as the baseline instead of appending a checklist to it.

# SSC-01-LH-01 Review-First Redesign

This note preserves the original `SSC-01-LH-01` task as a calculation-chain baseline and sketches a separate review-native version. It does not change the runnable `road-low-point-resilience-package` template, add a new source pack, add an executable verifier, or claim benchmark readiness.

## Baseline To Preserve

The existing task is `SSC-01-LH-01: Road Low-Point Drainage And Field Equipment Resilience`.

Its current shape is:

```text
road profile low point and crossfall
  -> pit, gutter, spread, and HGL check
  -> cabinet or signal asset elevation
  -> backup power and communications consequence
  -> resilience design memo
```

That is a good synthetic calculation-chain task. The model is asked to compute or propagate drainage, visibility, equipment, and backup-power consequences for one corridor condition.

The review-loop lesson should not be treated as an extra section on that same response. The stronger redesign changes the job from "compute the resilience memo" to "review whether the issue package is ready to release."

## Review-First Task

Human title:

```text
Review the road low-point resilience package for issue
```

Task prompt shape:

```text
You are reviewing a road-corridor issue package for a sag low point near roadside field equipment.

Using the supplied source packet, decide whether the package is ready to issue, ready to issue only with carried actions, or not ready to issue.

Produce a source inventory, corridor identity ledger, review matrix, critical findings, information requests, action register, and issue-readiness decision. Do not invent missing values; mark missing evidence as insufficient data and request the exact source or field needed.
```

The primary output is the review decision and its audit trail. Calculations still exist, but only as evidence behind review items.

## Source Packet

The review-native task needs a source packet with explicit document identity, object identity, and source gaps:

| Source Class | Required Evidence | Why It Matters |
| --- | --- | --- |
| Document register | Source ID, revision, date, discipline, and status for every file. | Lets the model prove which packet it reviewed. |
| Road geometry | Alignment plan, long section, crossfall or surface extract, datum, and low-point chainage. | Anchors the sag point and road surface used by all later checks. |
| Drainage | Pit schedule, gutter/spread result, pipe or HGL table, outfall notes, and storm case. | Supports flood, surcharge, and freeboard findings. |
| Field equipment | Cabinet or signal layout, device IDs, cabinet level, served equipment, and location relative to the low point. | Connects water levels to exposed assets. |
| Traffic operations | Speed or closure case, sight-distance basis, VMS or signal assumptions, and reviewer comments. | Tests whether the same scenario is used for road-user consequence. |
| Power/comms | Load schedule, battery runtime, PoE or feeder limits, network topology, and outage assumption. | Tests whether required devices remain operational in the event. |
| Criteria and comments | Authority criteria, owner comments, discipline review comments, and response status. | Separates engineering failure from authority or documentation action. |

## Review Workflow

```text
1. Inventory the source packet before drawing conclusions.
2. Build the corridor identity ledger: chainage frame, datum, low point, pit, cabinet or signal asset, storm case, traffic scenario, and power/comms boundary.
3. Check source conflicts and missing evidence first; do not bury missing cabinet levels or stale HGL tables inside later calculations.
4. Use the calculations only where they answer review items: spread, HGL, freeboard, stopping or legibility distance, battery runtime, and network headroom.
5. Assign exactly one status to each review item: pass, fail, not applicable, or insufficient data.
6. Prioritize critical blockers before ordinary documentation gaps.
7. Convert every fail or insufficient-data status into an action, information request, or carried issue.
8. Issue the final readiness decision and verify that the matrix, findings, and actions reconcile.
```

## Review Matrix

| Item | Review Question | Status Rules |
| --- | --- | --- |
| `RLR-01` Packet completeness | Are all required source classes present with document IDs and revisions? | `pass` only when every required source class is present; `insufficient data` when a required source class is missing. |
| `RLR-02` Object identity | Do chainage, datum, low point, pit, cabinet or signal asset, storm case, and traffic scenario remain stable across sources? | `fail` when the same object is silently renamed, moved, or tied to another datum. |
| `RLR-03` Drainage basis | Is the spread/HGL/freeboard basis traceable to the selected storm case and low point? | `pass` when source values and calculations reconcile; `insufficient data` when the HGL or spread basis is absent. |
| `RLR-04` Equipment exposure | Is the field equipment level adequate against the selected water level and criterion? | `fail` when the water level plus required freeboard exceeds the cabinet or equipment level. |
| `RLR-05` Traffic operation consequence | Does the package preserve the same storm, closure, speed, sight-distance, or VMS legibility scenario? | `fail` when a traffic scenario is reused from another case without a case-selection record. |
| `RLR-06` Power/comms resilience | Does source evidence support battery runtime and network capacity through the event? | `pass` only when runtime and network headroom are both source-backed. |
| `RLR-07` Comment and action closure | Are authority or discipline comments either closed, carried with owner/action, or blocked by named missing data? | `fail` when a critical comment has no closure path. |
| `RLR-08` Readiness decision | Does the final decision match the matrix and action register? | `fail` when the memo says "ready" while unresolved critical failures remain. |
| `RLR-09` Claim boundary | Does the response avoid unsupported approval, full-compliance, accepted-project, source-pack-hardening, executable-verifier, or benchmark-readiness claims? | `fail` on any unsupported overclaim. |

## Expected Output

The response should be structured as:

```text
1. Source inventory
2. Corridor identity ledger
3. Review matrix
4. Critical findings
5. Information requests
6. Action register
7. Issue-readiness decision
8. Final completeness check
```

The issue-readiness decision should use a small controlled vocabulary:

- `ready_to_issue`
- `ready_with_carried_actions`
- `not_ready_to_issue`

## Negative Cases

Good generated variants for this redesigned task:

| Variant | Expected Behaviour |
| --- | --- |
| Missing cabinet elevation | Mark equipment exposure as `insufficient data`; request the exact cabinet elevation source instead of guessing. |
| Stale HGL table | Mark drainage basis or object identity as `fail` if the HGL table revision does not match the selected road profile or storm case. |
| Chainage/datum mismatch | Mark object identity as `fail`; do not reconcile by silently moving the pit, low point, or cabinet. |
| Scenario copy-forward | Mark traffic consequence as `fail` if a closure, storm, or VMS legibility case is copied from another scenario without a decision record. |
| No VMS in scope | Mark the VMS legibility item as `not applicable` only if the source packet proves no VMS or sign is part of the reviewed package. |
| Comment left open | Mark comment/action closure as `fail` when a critical authority or discipline comment has no owner, action, or carried-issue decision. |
| Unsupported repair | Reject a memo that edits downstream values without resolving the source conflict that created the failure. |

## Verifier Shape

A verifier for the review-first version should grade the review packet, not only final scalar values:

- every required source class is inventoried or explicitly marked missing;
- the identity ledger preserves chainage, datum, low point, pit, cabinet, scenario, and power/comms boundary;
- every `RLR-*` row has exactly one status;
- every `fail` has a source pointer, affected object, consequence, and action;
- every `insufficient data` item names the missing source or field;
- every `not applicable` item gives a scope reason;
- calculations used as evidence are internally consistent with source values;
- final readiness status is consistent with unresolved failures and missing data;
- the memo avoids unsupported approval, compliance, accepted-project, source-pack-hardening, executable-verifier, and benchmark-readiness claims.

## Why This Is A Better Long-Horizon Shape

This redesign creates a more realistic long-horizon task because the model has to manage a package over time: sources, revisions, object identities, reviewer comments, calculations, missing evidence, actions, and the final release decision.

The long horizon is no longer just a longer formula chain. It is the controlled movement from evidence intake to engineering judgement, with enough structure for a verifier to distinguish a responsible reviewer from a fluent but unsafe memo writer.
