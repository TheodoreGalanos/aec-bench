# ABOUTME: Records the amended B5 successor execution and its first C-R02 rejection.
# ABOUTME: Preserves both hydraulic amendments while issuing no package, manifest, or V3 promotion.

# AU-NSW-LH-SYN-SPS-v1 — B5 C-R02 successor execution and decision

## 1. Decision

| Field | Result |
| --- | --- |
| Execution date | `2026-07-28` |
| Scope | Fresh complete affected `B5-W3` through `B5-W5` successor attempt |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Generation ID | `e31e64bd8f696dcb8edaa5bd2ad76f7286223094703f4181c6a203c03c49b2d0` |
| C-R07 amendment | `488c82d09696472533669f21017c19cd4156952f4d075b278de91b580bf2cbf2` |
| C-R08 amendment | `047576621781aa294b8251be433b9dba7c2efd66ffe759e633d67f26960d9a65` |
| W4 state | `w4-numerical-reject` |
| First failure | `C-R02-corrected-residual` |
| Family state | `family-member-reject` |
| Promotion state | `promotion-generation-reject` |
| V3 | **Refused** |
| V4 | `unclaimed` |
| Promoted payloads, package, or manifest | None |

The approved C-R07 and C-R08 amendments compose successfully. They do not
make the family pass: the ordinary ordered W4 path reaches an earlier
unexplained one-step mass residual at `G10_CLEAN_A_BASE`, report second `1`.
The family and promotion stages therefore stop and refuse this successor
generation.

This result does not edit or relabel the predecessor generation
`255e5b5cce2b4361bf37857ffbb386ef233bca47e9051b8f25e1689077edff06`.
Both refusals remain immutable and independently reloadable.

## 2. Amendment outcomes

The successor calculation retains each amended term separately.

### C-R07

| Quantity | Value |
| --- | ---: |
| Raw residual | `-0.00421556151771885 m` |
| Curve-head term | `0.0045166015625 m` |
| System-render term | `0.00000326134630946 m` |
| Complete derived allowance | `0.00452039985064086 m` |
| Relative hard ceiling | `0.00678068375587463 m` |
| Outcome | `c-r07-checks-pass` |

### C-R08

| Quantity | Value |
| --- | ---: |
| Raw residual | `-0.00000498497555748 m³/s` |
| Dynamic allowance | `0.00002736316302488 m³/s` |
| Numerical allowance | `0.00000534575358382 m³/s` |
| Total residual allowance | `0.00003270891660870 m³/s` |
| Dynamic hard ceiling | `0.00002736316302488 m³/s` |
| Numerical hard ceiling | `0.00002736316302488 m³/s` |
| Outcome | `c-r08-checks-pass` |

The total is not compared with the individual ceiling. In accordance with
the approved C-R08 amendment, the dynamic and non-dynamic numerical
allowances are ceilinged separately, then their outward sum bounds the raw
residual.

## 3. First ordered failure

Before candidate control-edge timestamps are used for mass correction, the
repaired C-R12 calculation proves the exact G10 edge shape and all `44`
ordered edges. The maximum observed edge-window ratio is `0.66`; C-R12
passes.

The first C-R02 sample then gives:

| Quantity | Value |
| --- | ---: |
| Case | `G10_CLEAN_A_BASE` |
| Segment | `single` |
| Report second | `1` |
| Raw one-step mass residual | `-0.00250003580133102 m³` |
| Independent signed quadrature correction | `0.00000000000000069 m³` |
| Corrected residual | `-0.00250003580133171 m³` |
| Derived unexplained-error allowance | `0.00000045211021993 m³` |
| Interval-scale hard ceiling | `0.00007547676350249 m³` |

The allowance fits its hard ceiling, but the corrected residual exceeds the
allowance by more than three orders of magnitude. This sample occurs before
the first pump start. The rejection is therefore an initial
storage/inflow-integration mismatch, not a C-R07/C-R08 hydraulic budget
conflict and not a pump-settling ambiguity.

W4 stops at that first numerical rejection. C-R03 and all later ordered
family work are recorded as not reached; they are not labelled passed or not
applicable.

## 4. Executed and retained path

The fresh successor attempt:

1. bound both exact amendment declarations into generation schema V2;
2. verified the pinned SWMM 5.2.4 build receipt;
3. regenerated all 19 W2 cases and 23 engine segments twice in fresh
   workspaces;
4. reproduced the predecessor transfer bundle and W3 result identities;
5. ran the certifier in an isolated workspace without generator or SWMM
   code;
6. recomputed the amended C-R07/C-R08 evidence and all independently
   composable anchor checks;
7. proved G10 C-R12 before using its edge timestamps;
8. stopped C-R02 at the first rejected sample;
9. retained the complete analytical family inventory without executing
   sibling family/ENG work after anchor rejection;
10. issued a connected eight-receipt graph; and
11. issued an immutable V3 refusal with empty payload, package, and manifest
    inventories.

The compact retained evidence is under
`asw-0b5-world-family/results/v3-c-r02-refusal/`. Raw engine files, the
transfer bundle, local paths, and temporary workspaces remain excluded.

## 5. Retained identities

| Evidence | Identity |
| --- | --- |
| Engine build receipt SHA-256 | `ca687ad185aa51c9c87426ab21f27f17da24c29cf9d5a6e4e932532c3e5f2644` |
| Certifier transfer bundle SHA-256 | `d476129a9a6c95d02eaaf1781353d8ecc884bec618a7c38fd064b1c94b029c19` |
| W3 result content ID | `7c7b092653684b5d340e2399e5d2829c72d413a97368f5413769b57da49bc231` |
| W4 composition result content ID | `4200748efca9d4281168bbdc02d4703dbdd71a5f6c5be349794bf92bc345e410` |
| Analytical inventory content ID | `de82cc8cb142c5ca8e2d1356763787c028fe35134c8ba548f4171b30a2db1f60` |
| Family result content ID | `d143d0075fddf0940437fe332f6b68d27fa135bf697bcbb6bc129642c21ca3b3` |
| Promotion decision content ID | `96a231e5d13d60b9d4acb5180d13863ff95162ab431276fb38fab20a9f4a27b7` |
| Receipt-index SHA-256 | `db0a41158075c6d840e39bbe2971440703040f82c0dfb287fed48e7b50f887ae` |

## 6. Next decision

Return to the W2/W4 authority owners before more family or production work.
The next review must determine, from the pinned engine algorithm and
candidate-independent calculations, whether:

1. the first report interval needs an explicit signed quadrature rule;
2. the W2 semantic/report boundary begins at the wrong physical interval;
3. the current SWMM storage/inflow mapping is insufficient and must return
   through the existing repair order; or
4. this reference profile should remain rejected.

No post-output fitted tolerance, silent first-sample deletion, result
relabel, family execution, package construction, ASW-0C work, ASW-2 work, or
production import is authorized by this decision.
