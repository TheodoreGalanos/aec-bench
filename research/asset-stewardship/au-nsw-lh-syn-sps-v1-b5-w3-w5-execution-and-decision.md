# ABOUTME: Records the executed B5-W3 through B5-W5 result for the first synthetic pump family.
# ABOUTME: Preserves the W4 hard-ceiling rejection and immutable V3 refusal without promoting a package.

# AU-NSW-LH-SYN-SPS-v1 — B5-W3 through B5-W5 execution and decision

## 1. Decision

| Field | Result |
| --- | --- |
| Execution date | `2026-07-28` |
| Scope | `B5-W3`, `B5-W4`, and `B5-W5` |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Reference generation ID | `255e5b5cce2b4361bf37857ffbb386ef233bca47e9051b8f25e1689077edff06` |
| Family-coverage repair | Approved by Theo on `2026-07-28` |
| W4 state | `w4-budget-reject` |
| Family state | `family-member-reject` |
| Promotion state | `promotion-generation-reject` |
| V3 | **Refused** |
| V4 | `unclaimed` |
| Promoted payloads | None |
| Promoted package | None |
| Promotion manifest | None |

The W3-W5 implementation and one fresh real-engine execution are complete for
this generation. The generation does not pass W4 and is not a successful
world-family promotion.

## 2. First failure

The first ordered failure is:

```text
C-R08-derived-budget-lower-bound-exceeds-relative-ceiling
```

W4 defines:

```text
B_dynamic_Q = 0.001 Q_star
C_flow_relative = 0.001 abs(Q_star)
```

`T08` then adds positive binary32, bisection, curve, system-render, and
binary64 terms to `B_dynamic_Q`, while requiring the complete derived budget
to remain no larger than `C_flow_relative`. Therefore the dynamic term alone
consumes the relative hard ceiling. The independently calculated lower bound,
which deliberately omits the additional positive system-render term, already
exceeds the ceiling.

For the retained G12 evidence:

| Quantity | Value |
| --- | ---: |
| Sample second | `20` |
| Reference flow | `0.02736221946247999 m³/s` |
| Dynamic-flow term | `0.00002736221946248 m³/s` |
| Derived lower bound | `0.00003270429753756 m³/s` |
| Relative hard ceiling | `0.00002736221946248 m³/s` |
| Observation hard ceiling | `0.00005 m³/s` |

This is a preregistered protocol conflict, not a poor SWMM residual. The
candidate residual was not used to choose a threshold, and changing that
residual cannot make the budget fit its own ceiling.

## 3. Executed path

The fresh execution:

1. verified the pinned SWMM 5.2.4 build receipt;
2. ran all 19 W2 cases and 23 engine segments twice in fresh workspaces;
3. required exact rendered-input, raw-output, setting-trace, semantic,
   diagnostic, and run-set replay;
4. transferred only the exact W3 byte roles;
5. executed W3 from an isolated copy containing no generator package or SWMM
   artifacts;
6. preserved every raw W3 residual value needed by W4;
7. independently reconstructed W4 roots, slopes, RK4 reference, settling, and
   the C-R08 lower-bound budget;
8. froze all 68 OAT constructions, five interactions, eleven boundary roles,
   six grid inventories, seven repaired ENG variants, thirty mutation roles,
   and two replay ordinals;
9. stopped sibling engine/grid execution after the anchor rejection;
10. rejected package-root creation before any payload byte existed;
11. emitted a connected eight-receipt research DAG; and
12. issued one immutable V3 refusal.

The approved family-coverage repair remains retained and did not change this
outcome. It repaired W1 membership coverage before generation; it did not and
could not relax W4.

## 4. Ordered non-execution

The following stages are recorded as
`not-executed-after-generation-reject`:

- AG and V0-V2 gate review;
- rights review;
- visibility review;
- three-payload package construction;
- package conformance;
- physical research/tool absence proof; and
- second-workspace package equality.

These are not marked “not applicable.” The W5 promotion algorithm requires
`family-w4-checks-pass` before any of them may execute. Running them against a
rejected family would create misleading evidence and risk temporary package
bytes becoming de facto contracts.

## 5. Retained identities

| Evidence | Identity |
| --- | --- |
| Engine build receipt SHA-256 | `ca687ad185aa51c9c87426ab21f27f17da24c29cf9d5a6e4e932532c3e5f2644` |
| Certifier transfer bundle SHA-256 | `d476129a9a6c95d02eaaf1781353d8ecc884bec618a7c38fd064b1c94b029c19` |
| W3 result content ID | `7c7b092653684b5d340e2399e5d2829c72d413a97368f5413769b57da49bc231` |
| W4 composition result content ID | `d9e2408c7af861a6c3ea0befea0a1b6528efcd899305962d07217f1080b5c099` |
| Analytical inventory content ID | `de82cc8cb142c5ca8e2d1356763787c028fe35134c8ba548f4171b30a2db1f60` |
| Family result content ID | `efc8154ea6b10567224101cc7af038d0948fef55d1a46be3b64c78f9470caf6f` |
| Promotion decision content ID | `db16405d150451381f70b7798bad53735b8017e62c134aa440b622aed8e2cc60` |
| Receipt-index SHA-256 | `ba1cad49690373e7f578c125eadf50af4d996d7815619bd80aa31fa04bcc94c3` |

The full W3 result and transfer bundle remain certification-private in the
ignored local run root. They are not promoted or committed. Their exact
identities are retained by the generation summary and receipt chain.

## 6. Focused verification

The completed focused checks were:

- `56 passed` across the touched W3/W5 boundary and new W4/W5 unit tests;
- `1 passed` for the promotion-only process integration boundary;
- `1 passed` for the consolidated real-SWMM W3-W5 end-to-end path;
- Ruff: all focused checks passed; and
- strict mypy: no issues in 12 source files.

No repository-wide suite was run. The change is research-local and the
verification stayed within the W3-W5 scope.

## 7. Next decision

Return to the W4 authority owner. A new versioned amendment must resolve
whether:

1. the preregistered hydraulic dynamic allowance belongs inside the same
   `0.1%` root-flow ceiling;
2. the hard ceiling is intended to govern unexplained remainder rather than
   the complete allowance; or
3. the profile should be abandoned because no non-zero allowance can satisfy
   the current rule.

The amendment must be justified independently of this candidate residual,
receive a new authority identity, preserve this failed attempt, and trigger a
fresh complete affected run. No production work, package construction,
ASW-0C, or ASW-2 work is authorized by this decision.
