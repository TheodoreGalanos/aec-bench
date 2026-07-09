You are checking `SSC-18-LH-08`, a task-owned synthetic instrumentation source-policy and thin-substrate extension package.

Use only the task-owned synthetic source pack values shown below for numeric grading. Source-index, P&ID, loop schedule, linked process/electrical table, verification-case, and gap-register workflows shape the context only; this instance does not parse real source packs, PLC exports, vendor files, or authority-approved review records.

Source pack:

- Source index: `INDEX-18-SOURCE-08`
- P&ID/loop schedule: `PID-18-LOOP-08`
- Linked process/electrical tables: `LINK-18-TABLE-08`
- Verification cases: `CASE-18-VERIFY-08`
- Gap register: `GAP-18-REGISTER-08`
- Extension memo: `MEMO-18-EXT-08`

Given values:

| Field | Value |
| --- | ---: |
| Source items traced/total | {{ source_items_traced }} / {{ source_items_total }} |
| Linked tables updated/total | {{ linked_tables_updated }} / {{ linked_tables_total }} |
| Documented/expected gaps | {{ documented_gap_count }} / {{ expected_gap_count }} |
| Verification cases passed/total | {{ verification_cases_passed }} / {{ verification_cases_total }} |
| Process/electrical margins | {{ process_margin }} / {{ electrical_margin }} |
| Authority partitions signed/total | {{ authority_partitions_signed }} / {{ authority_partitions_total }} |
| Unresolved conflicts | {{ unresolved_conflict_count }} |
| Extension memo completeness | {{ extension_memo_completeness_fraction }} |

Required calculations:

- Fractions equal completed counts divided by total counts.
- Minimum cross-domain margin equals the lesser of process and electrical margins.
- Overall pass requires complete traceability, updates, gap documentation, verification, authority partitioning, nonnegative cross-domain margin, and zero unresolved conflicts.

Return one JSON object with keys:

```json
{
  "source_traceability_fraction": <numeric_value>,
  "linked_table_update_fraction": <numeric_value>,
  "gap_documentation_fraction": <numeric_value>,
  "verification_case_pass_fraction": <numeric_value>,
  "min_cross_domain_margin": <numeric_value>,
  "authority_partition_fraction": <numeric_value>,
  "unresolved_conflict_count": <numeric_value>,
  "extension_memo_completeness_fraction": <numeric_value>,
  "overall_pass_score": <numeric_value>
}
```

Do not claim authority approval, accepted project evidence, executable real source-pack parsing, PLC export validation, full standards compliance, generated benchmark readiness, or benchmark readiness.
