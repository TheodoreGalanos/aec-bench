# Temporal evidence capability review

## Decision

The provider-free temporal evidence capability passed its approved focused
technical acceptance gate.

The implementation keeps evidence semantics in the wastewater pump-station
task template. It promotes only the narrow, typed `TrialRecord` grouping that
lets a completed world execution name and reload its temporal evidence.

No external archive provider, provider dependency, paid model run, study
runner, or study result is part of this decision.

## Capability boundary

| Area | Decision | Reason |
| --- | --- | --- |
| Evidence versions, corpus, lineage, rights, time, availability, access, branch, retrieval, and cost policies | Retain in the task template | These objects define the documentary world for one synthetic asset. They are not general platform contracts. |
| Deterministic search, fetch, opaque references, private receipts, budgets, access state, handover, and recovery | Retain in the task template | These objects implement this task's evidence-access semantics. |
| Actor-visible evidence events and information-set binding | Reuse the existing parent world contracts | Retrieval changes what the actor was supplied. It does not create another world or information-set authority. |
| Evidence reliance on an action | Retain in the task template | The shared action envelope remains unchanged. The task action schema accepts optional evidence references and strips them before task proposal validation. |
| Independent temporal verifier | Retain in the task template | It reconstructs this corpus, gateway, access ledger, handover, and reliance model. |
| Temporal evidence in a completed world `TrialRecord` | Promote as a narrow typed world-execution subtype | This is the one demonstrated cross-task boundary: immutable evidence references and verification facts must survive strict record reload. Capability-disabled records retain their old shape. |
| Corpus or gateway types in global contracts | Do not promote | No second task has demonstrated the same semantic contract. |
| Provider port or adapter | Do not create | Provider work is outside this provider-free stage. |
| Study contracts or outcomes | Do not create | The study freeze and model shakedown are later, separately accepted work. |

This split is the cleanup guide for later work: `TrialRecord` owns the general
recording contract. The wastewater pump-station template owns the task data,
retrieval rules, access process, and verifier.

## Dependency review

- The physical kernel does not import temporal evidence, Harbor, evaluation,
  study, or provider code.
- The temporal corpus, gateway, and repository do not import a provider,
  study runner, evaluator, or model adapter.
- The world session composes the task-local capability at the host boundary.
- Harbor export and import use immutable task evidence and the existing world
  execution boundary.
- The global `TrialRecord` models do not import the pump-station package.
- The independent verifier reloads the corpus and ledger from local files. It
  does not trust the agent, stored pass claims, or a live service.

## Storage review

| Storage class | Content | Rule |
| --- | --- | --- |
| Public | Capability and policy declarations, redistributable corpus records, actor-visible access results, actor-visible events, reliance records, sanitized handover carriers | Content-addressed and safe for the actor or trial record. Retrieved text is marked as untrusted documentary evidence. |
| Private | Source and rights lineage, exact access receipts, reference mappings, retrieval states, publication transactions, handover projection and install receipts, current information-set pointer | Host-owned and excluded from the actor tool result unless an explicit public projection exists. |
| Sealed | Evaluation targets and prohibited source bytes | Absent from this capability and from the committed corpus. |

The mutable current-information-set pointer selects one immutable manifest. It
does not replace or edit history. It restores the same actor tenure after a
process restart, including the original tenure start, view history, visible
materials, and information-set identity.

## Deterministic profile falsification matrix

| Gate | Result | Evidence |
| --- | --- | --- |
| TE-01 Future-evidence leakage | Pass | Retrieval tests keep a delayed record invisible before its access time. |
| TE-02 Event and availability separation | Pass | The delayed record describes an earlier event but remains unavailable until its declared access event. |
| TE-03 Local retrieval replay | Pass | Identical gateway inputs produce equal strict results, receipts, and next state. Durable retry returns the same terminal publication. |
| TE-04 Information-set binding | Pass | Session tests bind search and fetch events into the actor information set. Actions retain the exact pre-action information-set identity. |
| TE-05 Branch contamination | Pass | Branch-local delayed evidence is absent from a sibling branch and has a private branch-mismatch reason only. |
| TE-06 Negative-result leakage | Pass | Public no-result content is empty and uses one status family. The detailed cause remains in the private receipt. |
| TE-07 Supersession integrity | Pass | Old and current versions remain immutable, explicit, and subject to the same time and access rules. |
| TE-09 Retrieval and physics separation | Pass | Search and fetch leave the world snapshot and physical, operating, resource, and institutional state unchanged. |
| TE-11 Hidden-frontier non-interference | Pass | Filtering occurs before ranking and visible construction. Future and sibling records cannot enter rank or snippets. |
| TE-12 Opaque-reference safety | Pass | Fetch rejects references that were not returned or carried to the tenure. |
| TE-13 Handover sanitization | Pass | The carrier contains visible results, unresolved searches, and remaining budget, but no private frontier or resolution reason. |
| TE-14 Budget conservation | Pass | Strict vector equations cover calls, references, bytes, tokens, turns, duration, and spend across access, retry, resume, and handover. |
| TE-15 Capability-disabled compatibility | Pass | Disabled sessions have no temporal tools, store, or required `TrialRecord` field. |
| TE-16 Untrusted-content containment | Pass | Snippets and fetched text carry an untrusted-evidence marker and cannot alter the closed tool or authority rules. |
| TE-18 Access transaction recovery | Pass | Staged and repeated access converges on one committed result, receipt, event, information set, retrieval state, and budget charge. |
| TE-19 Documentary and world authority separation | Pass | The verifier reports accessible, observed, relied-on, recorded, and accepted sets separately. Retrieval cannot mutate truth or award success. |
| TE-20 Corpus lineage and rights | Pass | Publication and reload reject drifted parent identity, incomplete lineage, prohibited rights, prohibited bytes, and artifact drift. |

TE-10 does not block this profile. Simulated retrieval duration, resource cost,
and provider spend are all fixed at zero. Real calls, visible bytes, and visible
tokens remain measured in the retrieval budget.

TE-08 and TE-17 apply only to an opaque external-provider pilot. No such profile
is implemented or claimed here.

## Production paths

- Direct session: conditional `search_evidence` and `fetch_evidence` tools,
  action reliance, resume, handover, and independent verification.
- Installed interface: start with temporal evidence, search, fetch, verify, and
  export through installed commands.
- Harbor: the export declares the capability and tool set; both the reference
  controller and the model tool-loop path use the same production session;
  verification and import run offline from captured artifacts.
- `TrialRecord`: enabled runs use strict temporal execution and provenance
  subtypes; disabled and historical records keep their prior schema shape.

The local Harbor test proves the tool path and artifact boundary with the
provider-free reference controller. It does not claim model behaviour. A real
model-agent run is reserved for the separately approved shakedown after the
provider-free study design is frozen. That run must record input, output,
analysis, and total tokens, model identity, calls, turns, tool calls, and cost.

## Final acceptance condition

Technical acceptance used scoped Ruff, scoped MyPy, and one focused test command
over the temporal capability and changed integration paths. Ruff passed, MyPy
reported no issues in 24 files, and 22 tests passed in 22.67 seconds. No test
result in this review is a study outcome.
