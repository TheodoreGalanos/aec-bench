# Provider-free gates

Status: passed.

No ASW-4C provider call had started when these provider-free gates were
recorded.

## Focused results

- Ara-lite validation: passed with no diagnostic.
- Matched-history and endpoint tests: 5 passed.
- Real 64-branch preparation and independent reload: 1 passed in 44.42
  seconds.
- Complete provider-free run, one-trial pause, ordered resume, 64 completion
  records, final analysis, and independent reload: 1 passed in 96.54 seconds.
- Ruff format: passed.
- Ruff lint: passed.
- Mypy over the ASW-4C source and tests: passed with no issue.

The provider-free end-to-end run used the real promoted station data, physical
kernel, operating rules, durable repositories, two carrier treatments, hidden
event windows, endpoint classifier, evidence store, and analysis path. A
scripted test adapter replaced only the network model call. Its result is test
evidence and cannot enter the confirmatory estimand.

## Post-run focused validation

After the confirmatory run completed:

- adapter-limit, confirmatory unit, preflight, and analysis tests: 25 passed in
  57.28 seconds;
- ASW-4C execution and recovery end-to-end tests: 8 passed in 331.37 seconds;
- Ruff format over the affected source and tests: passed;
- Ruff lint over the affected source and tests: passed;
- Mypy over five affected source files: passed with no issue; and
- Ara-lite validation: passed with no diagnostic.

The ASW-4C end-to-end file covers ordered execution and resume, spend-derived
token measurement control, expired credentials, the initial token guard,
denied provider token counting, serialized station mutations, world-owned
early termination, and exact endpoint-prefix recovery.
