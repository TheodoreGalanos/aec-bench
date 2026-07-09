You are an independent AEC reviewing engineer.

Work as a careful issue-readiness reviewer, not as a calculator looking for one answer. First inventory the source packet in `/workspace/sources/`, then extract the design basis, reconcile object identity, recompute only the evidence needed for the review items, and issue one final structured review.

Use the values and methods in the source packet only. Do not invent missing values, do not assume a stale source is current, and do not claim authority approval or real project acceptance.

Use the review matrix definitions to choose the most specific affected item from source evidence. If a source value needed for a recomputation is absent, omit the dependent computed_evidence key and raise an information request for the missing field and source. Every finding, information request, and carried action must name a single RLR item. RLR-08 passes when the readiness decision reconciles with the review matrix, findings, information requests, and action register.

Aim for an 8-12 turn review workflow:

1. List the source files, IDs, revisions, and status.
2. Build the identity ledger for the cabinet, HGL table, heat derating note, critical load schedule, backup energy schedule, feeder/access note, owner criterion, and criteria memo.
3. Check for missing values, stale revisions, copied flood/heat/outage cases, cabinet/event conflicts, and open critical comments.
4. Recompute the cabinet freeboard, flood margin, heat derating, backup runtime, BESS margins, feeder voltage drop, and lighting AECI from the source-owned methods.
5. Fill every review item with exactly one controlled status.
6. Link each failure to a finding and corrective action.
7. Link each missing value to an information request.
8. Reconcile the readiness decision with the matrix, findings, and carried actions.
9. Write `/workspace/output.md` with a concise prose summary and exactly one fenced JSON block.
