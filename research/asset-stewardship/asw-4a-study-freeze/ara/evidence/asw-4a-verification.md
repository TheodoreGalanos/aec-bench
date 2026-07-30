# ASW-4A verification evidence

## Implemented path

- Versioned, content-addressed study manifest and plan.
- Typed paired blocks, trials, treatment-delivery records, observations, and report.
- Fixed failure and ineligibility taxonomy.
- Exact-coverage and identity checks.
- Deterministic paired block-bootstrap reducer.
- Generated provider-free fixtures.
- Real immutable artifact publication.
- Independent artifact reload and report recomputation.
- Retry identity check and changed-report rejection.
- Static provider-import boundary check.
- Phase-bound report conclusions and evidence sources.
- Provider-call limit, study-outcome, and task-reward authority checks.
- Planned history, event-schedule, logical-limit, and model-condition binding.
- Phase-specific provider, model, adapter, token, currency, and spend authority.
- Canonical evidence order derived from the frozen trial plan.

## Provider-free fixture result

| Item | Value |
| --- | --- |
| Manifest identity | `91de00556cfa451bd8a9da595d4cc25e2f30ddfe7c60e65e23c85e35332bd02a` |
| Plan identity | `9c541a784ee5586d3b0875fae8a78da1ae6445aaccde4b8487cb1f61b9dfe286` |
| Report identity | `91084bb1a9c585b150cc3c30bd82f2dbfcef1bd8d05b971e152e1b703a807667` |
| Planned trajectories | 64 |
| Analyzable paired blocks | 32 |
| Paired risk difference | `-0.5` |
| 95% fixture interval | `[-0.65625, -0.34375]` |
| Report conclusion | `analysis_fixture` |
| Diagnostic rule result | `supported` |
| Provider calls | 0 |
| Input tokens | 0 |
| Output tokens | 0 |
| Spend | 0 |
| Study outcomes | 0 |
| Task reward changes | 0 |

The diagnostic rule result proves the reducer against known generated input. It
is not a conclusion about a model or a continuity treatment.

## Focused gates

- Study contracts, paired reducer, and source ownership: 21 passed.
- Immutable artifact publication, retry, reload, and tamper rejection: 9 passed.
- Provider-free end-to-end path, approved station-data reader, and stewardship
  evaluation seams: 15 passed.
- Total focused tests: 45 passed.
- Ara-lite reference validation: pass.
- Ruff lint over the 11 changed Python files: pass.
- Ruff format check over the 11 changed Python files: pass.
- Mypy over the 11 changed Python files: no issues.

The focused test groups were selected from the changed study package and the
three production seams that it reads. The repository-wide test suite was not
run.
