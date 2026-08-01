# ASW-5 final test status

## Focused ASW-5 gate

The four ASW-5 world test modules and the ASW-5 evaluator contract test passed
on 2026-08-01 after the final coverage audit:

```text
17 passed in 18.14s
```

The modules cover process rules, version migration, direct and Harbor
end-to-end work, and semantic attacks.

The final additions directly prove repair-kit retention during suspension,
release on cancellation, consumption only after successful clearance,
deadline movement during suspension, blocked resume without access, stale
completion after cancellation, deterministic migration, unknown record-version
rejection, and exact direct/Harbor final-state identity.

The installed Harbor trial also proves reference-controller dispatch,
independent verification, TrialRecord import, strict reload, and evaluation.
The Harbor verifier awards execution reward `1.0`. Evaluation records one
obligation breach because the access interruption does not pause the Pump A
verification deadline, so the imported TrialRecord reward is `0.0`. Direct and
Harbor metrics and gates are identical. One cross-tenure handover is present
and its omission count is zero.

## Static checks

```text
Ruff: All checks passed for the changed source and test boundary.
MyPy source: Success: no issues found in 24 source files.
MyPy ASW-5 tests: Success: no issues found in 5 source files.
```

## Wider pump-station regression

The complete pump-station test directory passed:

```text
163 passed in 85.07s
```

## Repository-wide comparison

Pytest's default collection mode first found two unqualified files named
`test_contracts`. Importlib collection then exposed existing bare local-helper
imports. The complete suite ran after both identities were made explicit for
the command, without skipping tests:

```text
7601 passed, 21 skipped, 10 failed in 2780.20s
```

The 10 failures were outside ASW-5:

- Eight reproduced at unchanged `origin/main`: two prior ASW-4 source-ownership
  checks, one proposal-evidence hash, one kernel inventory check, and four
  compiled-world golden hashes.
- The bootstrap test assumes that the checkout directory is named
  `aec-bench`. It passed in the baseline worktree with that name and failed in
  the feature worktree with a different name.
- The Azure reviewer routing test passed alone on both ASW-5 and the baseline.
  Its failure in the complete run is order-dependent.

The repository-wide Ruff command also reported 267 existing findings outside
the changed pump-station paths. The focused Ruff boundary is clean.

## Disposition

The focused ASW-5 gate and the complete pump-station cumulative gate pass with
clean output. The wider repository failures are retained as explicit baseline
defects. No unrelated source, generated task, golden file, or repository-wide
test configuration was changed in ASW-5.
