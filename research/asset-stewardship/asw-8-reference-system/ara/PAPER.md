---
ara_schema_version: "0.1"
title: ASW-8 coupled-asset reference-system design
---

# ASW-8 coupled-asset reference-system design

## Decision

Theo supplied and accepted one detailed ASW-8 reference-system direction on
2026-08-02. The design uses a three-pump synthetic station, two declared
service levels, one shared field-work lane, named quantity-bearing resources,
one consumable clearance kit, deterministic generated work, and independent
checks of service, resources, work, and liabilities.

The complete design is in
`research/asset-stewardship/asw-8-reference-system-design.md`. The PRD now
links this design as `ASW-8-RS1`.

## Code-grounded corrections

The audit confirmed that ASW-8 must be a separate
`AU-NSW-LH-SYN-SPS-v2` profile. The accepted v1 station data and current
physical records enforce exactly two pumps and one running pump. The current
resource state also uses singleton fields rather than named quantities.

The next durable stewardship record set can use v4. The actor current-state
projection cannot use v4 because that identity already belongs to the
date-aware temporal view. ASW-8 therefore uses state record set v4 and actor
projection v5. Old package, state, and view bytes remain unchanged.

The example journey also now separates baseline Pump C operation from cover
operation. C is baseline normal duty before the peak and replaces unavailable
Pump B only during the eight-hour peak. The host derives this attribution from
the declared baseline schedule. Pump A becomes the normal baseline after the
peak, so C's later inspection does not create a second cover item.

The code audit produced two other material corrections. Duty assignment is an
immediate persistent action, while `continue_operation` remains the only actor
time-advance action. The third field window ends at Day 2 15:00, not 14:00, so
the eight-hour C inspection completes at 14:00 before the accepted
resource-withdrawal event class.

The final audit fixed the remaining identity and information boundaries. The
task-world ID stays at v1, but ASW-8 has an exact reference-system profile and
separate opening-state and event-schedule identities before initial-state
creation. A closed task-local descriptor registry binds their hashes and
rejects caller overrides. World-run manifest v2 stores those bindings without
changing manifest v1. Verification uses the
task-local `PumpStationCoupledVerificationReport`; the existing
`WorldTrialProvenance.verification_report` binds its artifact, and evaluation
recomputes it instead of relying on a field that does not exist.

Functional checks now use a separate test-running set. Test operation adds
physical runtime, starts, and degradation, but no service or collateral SCU.
The maintained pump also follows a durable four-mode boundary:
`isolated_for_work`, `test_only`, `run_in_service`, and
`service_available`. Clearance cannot silently make a pump service-ready, and
a failed functional check leaves the same WG-03 item planned for another
authorised attempt.

The actor receives the complete disclosed service and resource schedules
through explicit horizon markers. ASW-7 child creation must also initialise a
confined temporal-evidence repository for the child without copying private
parent retrieval records. These rules close gaps found in the current physical
environment, manifest, evaluation, and rollout code.

The current temporal corpus cannot serve RS1 unchanged: it is tied to v1, an
old two-pump regime, and a 7,200,000-second reference time outside the ASW-8
window. The design now keeps that builder stable and adds a descriptor-bound
RS1 temporal template and builder with Pump C coverage and in-window document
events. The descriptor binds branch-neutral inputs. Each direct or Harbor root
manifest binds its realised branch-specific corpus. A child copies and binds
its parent's exact immutable public corpus, then creates fresh child-private
retrieval state and ancestry.

The last transport audit also separated semantic equality from artifact
identity. Harbor import adds evidence hashes that direct evaluation does not
have, and generated work can contain transition-derived IDs. Direct and Harbor
runs therefore compare a task-local semantic projection of actions, terminal
state, conservation, gates, metrics, and liabilities. Exact IDs remain required
inside each run. ASW-8 also uses a separate rollout-control v2 request and
result so the accepted v1 installed schema does not change under its old
identity.

## Evidence status

The code-grounding claim is supported by commit
`f73c692e606c2319d143bcd27cb4aafdd8d38571`, tree
`a960c51fb12621be88aaa368880f0aba8bdd773c`.

The provider-free implementation gate now supports the mechanism,
compatibility, conservation, and actor-fairness claims. The ASW-8-only gate
passed 58 tests. Six narrow historical checks passed, and three affected v4
persistence and transport checks passed after the version-selected decoder
change. Ruff and MyPy also passed for the changed implementation surface.

The separately authorised real-model journey also completed. In three of four
allowed turns, the model read the named projection-v5 pump records and started
the valid Pump A verification path with an exact backlog identity and a clear
reason. The stored proposal retained the observed view and information-set
binding. Independent replay, separate actor-proposal and host-control checks,
and all four conservation sections passed. This is behaviour and usability
evidence only; the one-action stop leaves open liabilities and does not claim a
terminally complete run.

## Artifact map

- `logic/claims.yaml` records the supported audit and implementation claims.
- `logic/experiments.yaml` records the completed audit and focused acceptance
  work.
- `evidence/code-grounding.md` maps the design to current source files and
  symbols.
- `evidence/acceptance-plan.md` records the provider-free and later bounded
  agent gates.
- `evidence/implementation-evidence.md` records the provider-free test,
  compatibility, certification, and quality results.
- `evidence/agent-journey-evidence.md` records the approved bounded Bedrock
  journey and its token, leakage, replay, and evaluation evidence.
- `trace/exploration_tree.yaml` records the source decision, audit corrections,
  implementation result, and completed bounded model journey.
