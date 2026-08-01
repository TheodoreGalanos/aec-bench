# ASW-5 compatibility boundary

ASW-5 is the first real second schema for the pump-station world-run record.
It therefore activates the deferred migration requirement in the programme
PRD.

The implementation must meet these rules:

- Version 2 identifies state snapshots, transition receipts, approval-policy
  records, and transition-rule records.
- Existing version 1 runs reload and replay with their version 1 semantics.
- A version 1 run is not changed in place.
- Continuing a version 1 run under version 2 creates a new content-addressed
  version 2 snapshot.
- The migration record names the source run, source state, source snapshot,
  source versions, target versions, and resulting state and snapshot.
- Migration does not change the version 1 object bytes.
- Any unknown record or rule version fails closed before state changes.

The test evidence must include an existing version 1 fixture, a version 2
migration, byte-identity checks for the source objects, durable replay, and an
unknown-version rejection.
