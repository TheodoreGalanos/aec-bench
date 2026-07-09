## Review Workflow

1. **Inventory** (1-2 turns): List `/workspace/sources/` and read every document. Record IDs, revisions, and status before judging anything.
2. **Extract** (1-2 turns): Build the identity ledger and note the certificate, traceability, application, deviation, and assessment bases from the criteria memo.
3. **Check** (3-6 turns): Cross-check identity across documents, then recompute the package results that back review items. Compare claims against your recomputation.
4. **Decide** (1-2 turns): Assign one status per review item, raise findings and information requests, and settle the readiness decision.
5. **Consolidate** (1 turn): Write the full review with the final fenced JSON block to `/workspace/output.md`.

## Budget

Target: 8-12 turns total.

## Output Discipline

- Base every number on the source packet; never invent missing values.
- Omit computed_evidence keys whose inputs are missing, and raise a matching information request.
- Do not rename computed_evidence keys.
- MUST end `/workspace/output.md` with exactly one fenced JSON block matching the required schema.
- Write the complete review to `/workspace/output.md`.
