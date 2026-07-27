# ABOUTME: Records the ASW-0B3 engineering-engine role decision for the synthetic duty/standby profile.
# ABOUTME: Authorises only a bounded B4 generator/certification protocol and creates no runtime or production contract.

# AU-NSW-LH-SYN-SPS-v1 — ASW-0B3 engine-role decision

| Field | Decision identity |
| --- | --- |
| Stage | `ASW-0B3 — Engine roles and research spike` |
| Status | **Accepted** |
| Repository baseline | `2725bf522b3b4d3c557649d452faec06b8cf349a` |
| Parent PRD SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| B1 profile SHA-256 | `1956883951dd70ce52ec89f4c24ed69e5aaa4617796b803668e44002eafed954` |
| B2 pack SHA-256 | `8d8e057792763531ebd3c8709f039c0aa7150a22ce734857221cef3339378e96` |
| Compact verification record SHA-256 | `db93443b31a197864709e7011af8a6aa15932cbec3260cf1a2afed735ffa3f11` |
| Next permitted stage | `ASW-0B4 — Generator and certification protocol` only |

## 1. Decision

Select **EPA SWMM 5.2.4 at commit
`7952ca837988b1c32f791812eccc9fd64547e093`** as the hydraulic software
for which ASW-0B4 may specify an offline synthetic generator/oracle.

This is a bounded research-role decision:

- SWMM may produce candidate hydraulic consequences for later, separately
  specified synthetic-family generation;
- SWMM and its output wrapper may not certify their own claim-critical
  results;
- SWMM is not an asset-world runtime dependency;
- raw SWMM is not an agent-visible tool;
- no live-solver integration is authorised; and
- no diagnostic value, curve, comparison tolerance, generated input, output,
  path, Python name, or file layout from B3 is a B4 or production contract.

The decision establishes that the pinned engine can perform and export the
narrow hydraulic operations needed to design B4. It does not establish a
physically coherent world, a certified generator family, benchmark validity,
regional representativeness, operational suitability, or any real-asset claim.

## 2. Candidate assessment

The accepted B2 pack retained SWMM, EPANET, and OpenModelica as candidate
metadata. B3 evaluated them against the frozen profile and executed only the
candidate with the strongest direct fit.

| Candidate | B3 assessment | Role outcome |
| --- | --- | --- |
| EPA SWMM 5.2.4 | Direct support for storage, externally imposed inflow, pumps, dynamic-wave routing, force-main calculation, report output, and an official binary output API; exact pinned source built and executed | **Selected for B4 offline generator/oracle protocol design** |
| EPANET 2.2 | Strong pressurised-network solver, but a weaker primary fit for the profile's wet-well filling, flooding boundary, and wastewater/sewer context | Not selected as the first generator; may be reconsidered only as a separately justified pressure-network comparison |
| OpenModelica | Expressive enough to construct a station, but would make the first world depend on more self-authored component equations and a broader toolchain before those equations are independently certified | Not selected for the first generator or certifier |

EPANET and OpenModelica were not executed in B3. This is a profile-fit
selection, not a general quality judgement and not evidence that those tools
cannot model related systems.

## 3. Exact executed candidate

| Item | Executed identity |
| --- | --- |
| Official source | `https://github.com/USEPA/Stormwater-Management-Model.git` |
| Version response | Exact full match `5.2.4` |
| Commit | `7952ca837988b1c32f791812eccc9fd64547e093` |
| Official README SHA-256 | `11b8645890d1befb9dded9aea32c17611f1595a252edca6eea8400a2576a04a8` |
| Rights basis | The official pinned README states that the C source is released in the Public Domain |
| Portability patch SHA-256 | `522fa1f285b27bfdd614eae79a841e5b9a7892573521d032f78fdbd281dba894` |
| Build receipt SHA-256 | `36dffda0813faf3f3e6581046e6d1c3ce100927ac06a096511ae23a3fdc67e93` |
| `runswmm` SHA-256 | `a944ecff7ebb0d01b3c4aba934046feb578c9373418914a78e0c9150bc235188` |
| Output library SHA-256 | `11be24989820a3fc21d48f07182b8641ed621da498acb4edcf84c486fc5b9e22` |
| Solver library SHA-256 | `adc467fc3db029617b4b9280bcec72fde0a7a0e7e236a7f8cf9e7218a43ff796` |
| Build environment | macOS 15.7.5 arm64; Apple clang 17.0.0; CMake 3.31.5; Boost 1.87.0; no OpenMP |
| Upstream validation | The single relevant official output-API test passed; one executed, zero failed |

The portability patch:

1. corrects an OpenMP generator expression that otherwise links a nonexistent
   target when OpenMP is unavailable;
2. registers the upstream output test at its actual target path on a
   single-config generator; and
3. declares the pinned source's intended legacy `FindBoost` policy on current
   CMake.

It changes no solver or output calculation. Build and upstream-test output was
clean after the patch. Exact source, patch, toolchain, commands, and executed
artifact identities are recorded. Cross-workspace byte-identical rebuilds were
not demonstrated or made an acceptance claim.

## 4. B1-compatible spike

The disposable fixture SHA-256 is
`17aaefb61745ab99332e0ebdde9bb7108bcc85b2005d4926d7da9eac9dbd66fe`.
It has exactly two component labels, `PUMP_A` and `PUMP_B`, and two separate
probes:

- `a_duty`: Pump A active and Pump B inactive; and
- `b_duty_label_probe`: Pump B active and Pump A inactive solely to test
  label-symmetric calculation and export.

The second probe is not a transfer event or scenario state. The fixture has no
controls section, simultaneous pumping, duty-transfer timing or trigger,
obstruction, degradation, failure, maintenance, intervention, observation,
obligation, handover, authority, or scoring semantics.

Every numerical fixture value is disposable diagnostic material. ASW-0B4 must
select, derive, document, and independently challenge its own family; it may
not inherit B3 values or tolerances by path, name, or convenience.

## 5. Real-engine result

The final verification executed four real simulations: both probes twice.

| Gate | Result |
| --- | --- |
| Expected reporting periods | `120` per run, computed without the output API |
| Extracted reporting periods | `120` per run |
| Engine errors | `0` |
| Engine warnings | `0` |
| Steps not converging | `0.0%` |
| Input hashes across replay | Exact match |
| Binary output hashes across replay | Exact match |
| Semantic output hashes across replay | Exact match |
| Pump A duty semantic SHA-256 | `aaa0281b0c10c06e4e6b361d85c727d4fdc22f6a2946d871d05f2efb4ae54252` |
| Pump B label-probe semantic SHA-256 | `fb1faf4d897abd0cfd276bd0d40014fc7b2604ab524e34283b78f812a12b61ad` |

The independently implemented diagnostic checks passed:

- period count exactly matched the independently calculated value;
- every allowlisted series was finite;
- the inactive pump exported zero flow;
- the active pump exported positive flow;
- exported depth and volume satisfied the constant-area cylindrical-storage
  identity within float-output representation tolerance;
- the wet well did not flood; and
- active-pump, inactive-pump, wet-well, and force-main series matched after the
  A/B label swap.

The reports disclosed a flow-routing continuity error of `-0.943%`. B3 records
that value but does not turn it into a physical-coherence pass or tolerance.
ASW-0B4 owns numerical acceptance criteria and ASW-0B5 owns family
certification. A B4 protocol must reject or revise candidates that fail its
preregistered continuity, sensitivity, or independent-check thresholds.

Human-readable report bytes are not replay contracts because they contain
wall-clock analysis timestamps. The generated input, binary output, and
allowlisted semantic outputs were stable across the two runs.

## 6. Role matrix

| Engineering role | B3 decision | Authority boundary |
| --- | --- | --- |
| Offline generator/oracle | **Selected for B4 protocol design** | SWMM may generate candidate hydraulic consequences from B4-owned inputs; it cannot promote or certify them |
| Independent certifier | **Not selected** | B4 must specify a separately executable path for claim-critical equations, units, invariants, sensitivities, and tolerances |
| Asset-world runtime | **Rejected for the first implementation** | A later runtime may consume only a B5-promoted deterministic package and must succeed without SWMM, research code, or raw solver artifacts |
| Agent-visible engineering tool | **Not authorised** | Raw SWMM would expose an unbounded surface; any later calculator needs a separate capability and visibility review |
| Live solver integration | **Deferred** | Remains out of scope through ASW-4 unless separately authorised for replay, availability, licensing, failure, cost, and version controls |

The selected initial architecture is therefore asymmetric:

```text
B4/B5 research generation: pinned SWMM
Claim-critical certification: separately implemented independent path
First asset runtime: promoted deterministic package, not live SWMM
Agent tool: none
```

## 7. Contract, boundary, and invariant review

The B3 change preserves the parent PRD guardrails:

- no file under `src/aec_bench` changes;
- no contract, registry identifier, `TrialRecord` field, CLI command, Harbor
  key, runtime schema, example, or production import is created;
- the research package is excluded from the distributable wheel and source
  archive;
- exact `.gitignore` allowlisting tracks only research source, tests, fixture,
  patch, decision, and compact record;
- vendor source, `.git` data, build/install trees, binaries, shared libraries,
  generated `.inp/.out/.rpt` files, logs, caches, local receipts, and discarded
  experiments remain ignored or outside the worktree;
- every build and run requires an absent target path and never deletes or
  silently reuses a workspace;
- the exact executable and library hashes are rechecked before every run;
- stale report and output paths fail closed;
- output version, units, report step, period count, element names, warnings,
  errors, and convergence status fail closed;
- generator output cannot self-certify; and
- the research Python package, fixture structure, and paths are expressly
  non-authoritative.

Later production work must re-express only fields named by a B5 promotion
manifest in the owning asset-local package. It must not import, copy, or read
this research package at runtime.

## 8. B3 acceptance gate

| Requirement | Assessment |
| --- | --- |
| Predecessor binding | Pass: exact PRD, B1, B2, and repository identities recorded |
| Candidate pin and rights | Pass: exact official source, version, commit, README hash, and public-domain notice recorded |
| Reproducible build evidence | Pass: fresh path, declared patch, toolchain, commands, hashes, and relevant upstream test recorded |
| B1 topology | Pass: exactly Pump A/Pump B, one active per independent probe, no load sharing |
| B4 separation | Pass: no family value, mechanism, transfer, tolerance, observation model, or intervention selected |
| Real engine | Pass: four actual simulations; no mock, fallback, skipped integration gate, or fabricated output |
| Export semantics | Pass: exact version, LPS units, report step, independently expected period count, element allowlist, and series extracted through the official API |
| Replay | Pass: inputs, binary outputs, and semantic hashes stable across repeated runs |
| Independent checks | Pass for B3 diagnostics only; no generator self-certification or physical-world claim |
| Warning and convergence handling | Pass: zero engine warnings/errors and zero non-converging steps |
| Production boundary | Pass: no vendor, spike, raw output, research receipt, or dependency becomes a runtime contract |
| Explicit role decision | Pass: generator selected; certifier separate; runtime rejected; agent tool not authorised; live solver deferred |

**ASW-0B3 is accepted. ASW-0B4 is authorised as the only next stage.**

## 9. B4 handoff

ASW-0B4 must begin in a new focused worktree and PR after this stage is
accepted. Its first task is not to copy the spike. It is to freeze the
generator and independent-certification protocol:

1. define an original bounded synthetic parameter family and derivation chain;
2. select the primary and secondary mechanisms without importing the report's
   old obstruction transform;
3. specify SWMM inputs and the semantic output allowlist owned by the
   generator;
4. specify a separately executable certifier with disclosed common
   dependencies;
5. preregister units, invariants, sensitivities, tolerances, rejection rules,
   and stop conditions;
6. define lineage and content-addressed receipts without making research paths
   authoritative; and
7. define the B5 promotion-manifest schema without producing or promoting a
   world family yet.

ASW-0B4 may revisit the SWMM generator decision if the constructed family,
certification requirements, solver limitations, or portability evidence make
the selected role unsuitable. That stop would be a successful stage result,
not pressure to weaken a verifier.
