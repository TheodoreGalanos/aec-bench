# ASW-5I decision

## Plan conflict

The accepted ASW-5 checkpoint authorized ASW-6A. A later local plan added
ASW-5I as a mandatory interface gate before ASW-6A. The later draft was based
on an old copy of the parent plan and also removed the accepted checkpoint text
by accident.

## Theo decision

On 2026-08-01, Theo approved doing ASW-5I first. The implementation must keep
the accepted checkpoint and add only the later interface decision.

## Accepted boundary

- Shared: actor request, observation, action result, host-control request,
  capability, receipt, progress, and verification envelopes.
- Task-owned: action names, argument rules, proposals, state effects,
  projections, and verifier.
- Transport: importable Python and one installed JSON command.
- Real clients: direct Python and local Harbor.
- Excluded: ASW-6A evidence controls and all later review, rollout, physical,
  provider, and model-study work.

## Exit decision

The provider-free gate passed. ASW-6A local evidence health is active. No other
later-stage authority is granted.
