# Model Governance Criteria And Comments

Source ID: CRIT-SSC03-001
Revision: Rev C
Site: SITE-03

## Governing assessment basis

- Current revisions are those marked current in the document register.
- A model run may govern only when its manifest identifies the current catchment, rainfall,
  network-model, and configuration revisions.
- `all_input_revisions_match_score` is binary: set it to 1 only when the manifest identifies all four
  governing input revisions; set it to 0 when any identified revision differs; omit it when a required
  manifest revision is missing.
- The report run ID must match the report mapped to that run in RUN-03-REGISTER-01.
- Intrinsic report acceptance checks only report-to-run identity and continuity error against the stated
  limit. Input-governance consequences are recorded in the transition decision rather than duplicated
  under report integrity.
- A downstream design claim is supported only when it cites a governing run and report and
  reproduces their reported peak flow and maximum HGL at the shown reporting precision.
- Memo propagation integrity checks only the cited run/report identity and preservation of reported
  values. Whether those cited artifacts govern is recorded in the transition decision.
- A report timestamp or revision label alone does not establish that its input set is current.

| Controlled field | Value |
|---|---|
| Governing design storm | STORM-03-A |
| Maximum continuity error | 2.05 percent |

## Comments

All critical model-governance comments are closed.
