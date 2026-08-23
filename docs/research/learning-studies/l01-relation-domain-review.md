# L01 Drainage Staged-Evidence Relation: Domain Review

| Field | Value |
| --- | --- |
| Class | Research |
| Status | Research |
| Study | `l01-lifecycle-staged-evidence-transfer` |
| Relation | `staged-correction-to-semantic-no-op` |
| Scope | Independent domain review of the lifecycle-family relation required by L01 §3 and §22 before `relations_reviewed=true` |

## Reviewer identity and standing

This review was performed by an AI reviewer (a Claude Sonnet 5 agent
instance, invoked fresh for this review with no involvement in implementing
PR #147, LS-06A/B/C, or the L01 study) acting as an independent
drainage/stormwater domain reviewer for the Learning Studies programme. The
reviewer read the study protocol, the maintained `family.toml`/`study.toml`,
the drainage lifecycle source (`drainage_model.py`, `drainage_variants.py`),
materialized both variants directly from the lifecycle compiler, diffed the
resulting packages file-by-file, and ran controlled simulations against the
live verifier to obtain gate-level evidence rather than relying on
descriptions alone.

**The programme owner must decide whether this AI review satisfies the
protocol's "independently reviewed by a drainage/domain reviewer"
requirement (L01 §3, §22), or whether a human drainage/stormwater engineer
must additionally sign off before any L01 result is treated as a
claim-bearing causal result.** This review does not itself resolve that
governance question; it supplies the evidence a human reviewer would need in
order to decide quickly.

**Programme-owner decision (23 August 2026):** the programme owner accepted
this AI-performed review as satisfying the L01 independent domain review
requirement. `relations_reviewed=true` may be supplied for claim-bearing L01
runs subject to the remaining interpretive conditions in the overall
recommendation (claim-boundary weighting and cold-arm ceiling monitoring).

## Method

- Read `L01-drainage-staged-evidence-transfer.md` in full (protocol,
  scientific status, authored relation §6, validity requirements §18,
  domain review checklist §22).
- Read `family.toml` and `study.toml` under
  `src/aec_bench/experimentation/learning_studies/protocols/l01-drainage-staged-evidence-transfer/`.
- Read `drainage_model.py` (lifecycle contract, gate implementations,
  canonical/seed gold content), `drainage_variants.py` (variant derivation,
  event-topology validation, per-variant release/gold overrides), and
  `drainage_learning.py` (public feedback projector).
- Materialized `staged_full_correction` and `semantic_no_op_release` with
  `materialize_lifecycle("drainage-model-evidence-lifecycle-review", ..., variant_id=...)`
  into a scratch directory and ran `diff -rq` across the two package trees
  to enumerate every file-level difference (removed afterwards; no artifact
  left in the tree).
- Ran `verify_lifecycle` against the probe package with two constructed
  "copycat" submission sequences (see "Sequence-copy detectability" below)
  to obtain actual gate scores and failure lists, rather than reasoning
  about gate logic in the abstract.
- Read `tests/lifecycles/stormwater_design/test_drainage_variants.py` and
  `test_drainage_lifecycle.py` for existing guarantees.

## Verdicts on the five invariant claims (L01 §6.3)

### 1. "Both variants use the same three-checkpoint drainage review contract and submission structure."

**CONFIRMED.**

- `instructions/initial_review.md`, `instructions/response_review.md`,
  `instructions/closeout_review.md`, and `README.md` are byte-identical
  between the materialized `staged_full_correction` and
  `semantic_no_op_release` packages (verified with `diff`, zero output).
- Both use the same `EvidenceLifecycleSpec` (`CHECKPOINT_IDS =
  ("initial_review", "response_review", "closeout_review")`,
  `drainage_model.py:26`) and the same `required_submission_fields` per
  checkpoint (`drainage_model.py:43-91`).
- Both are verified by the same `GATE_IDS` tuple and the same eight gate
  functions (`drainage_model.py:95-157`); only the `expected`
  (gold-submissions) and `config` (allowed evidence refs, decision/closure
  policies) data differ per variant, not the gate code.
- The same PRV-01..PRV-09 review matrix, the same JSON submission contract,
  and the same finding/decision/closure-request ID conventions are declared
  identically in `_review_contract()` for every variant.

### 2. "In both variants, findings, accepted decisions, evidence references, readiness, and claim boundaries must remain tied to current registered evidence."

**CONFIRMED**, with one caveat noted under "Gate sufficiency" below.

- `_staged_disclosure_gate` computes `allowed` evidence refs from each
  variant's own gold `evidence_refs` per checkpoint
  (`drainage_variants.py:167-170`) and penalizes any reference outside that
  set at that checkpoint, in both variants.
- `_closure_evidence_gate` and `_accepted_decision_gate` are identical
  functions applied to variant-specific `expected` and `config` data in both
  cases; both require closure/acceptance basis to match the currently
  registered documents, not assertions (see `_decision_basis_is_complete`,
  `_request_requirements_complete`).
- Caveat: `claim_boundary_statement` is a fixed boilerplate string
  (`_CLAIM_BOUNDARY`) reused unchanged across all three checkpoints and both
  variants in the gold data. The `claim_boundary` gate genuinely checks that
  submitted text avoids specific over-claims (authority approval, benchmark
  readiness, etc.) but, because the required statement never varies with the
  evidence state, it does not by itself demonstrate that the *claim boundary
  changes as evidence changes* — only that a static disclaimer is present.
  This is a real but narrow gap; it does not falsify the claim (the field is
  still evidence-boundedness by design/instruction), but see "Gate
  sufficiency" for its consequences for L01's primary projections.

### 3. "Stable finding and decision identities should be preserved unless evidence supports an explicit transition."

**CONFIRMED.**

- In both variants, `F-PRV03-001` is opened at `initial_review` and keeps
  the same ID through to closure; `_finding_continuity_gate` explicitly
  checks per-finding-ID field equality (`item`, `status`, `opened_at`,
  `closed_at`) at every checkpoint (`drainage_model.py:312-327`).
- Accepted-decision supersession is ID-stable and evidence-gated:
  `_accepted_decision_gate` fails any checkpoint where prior `basis_refs`
  changed without a `superseded` transition (`drainage_model.py:423-427`),
  and requires a non-empty `supersession_reason` whenever a decision is
  superseded (`drainage_model.py:410-413`).
- Existing test coverage
  (`test_direct_closeout_decision_ids_and_lineage_follow_actual_topology`,
  `test_non_evidence_response_events_preserve_engineering_state`) already
  asserts ID continuity and supersession-reason content for the probe
  specifically.

### 4. "Closure requires the complete relevant evidence chain, not an assertion or unrelated administrative release."

**CONFIRMED.**

- The probe's response-stage release (`administrative-note.md`) is not
  present in `allowed_evidence_refs["response_review"]` for the probe
  (computed from the probe's own gold `evidence_refs`, which are unchanged
  from `initial_review`). Any attempt to cite it, or to cite
  acquisition-style corrected-chain documents that were never released at
  that checkpoint, is caught by `_staged_disclosure_gate`.
- `_closure_evidence_gate` fails a checkpoint if a finding is closed with
  insufficient closure evidence, or with any closure evidence at all when
  the gold state says the finding should remain open
  (`drainage_model.py:345-348`).
- This principle is also demonstrated by the sibling variants
  `response_assertion_only` and `memo_closeout_missing`
  (`test_assertion_variants_do_not_treat_assertions_as_closure_evidence`),
  which show the same verifier code rejecting bare assertions as closure
  evidence across the whole drainage lifecycle family, not just this one
  relation.

### 5. "The probe does not change the governing review method; it changes when the method permits a status transition."

**CONFIRMED.**

- File-level diff of the two materialized packages shows differences are
  confined to: `hidden/gold-submissions.json`, `hidden/variant.json`,
  `hidden/verifier-config.json`, the response-checkpoint release files, the
  closeout-checkpoint release files, and one closeout comment-response file.
  Every agent-visible instruction, the README, and the JSON contract are
  identical.
- `_semantic_no_op_content` (`drainage_variants.py:236-252`) builds the
  probe's `response_review` gold state as an exact deep copy of
  `initial_review` (`_unchanged_response`), i.e. the method (evidence
  governs transitions) is unchanged; only the input data at that checkpoint
  changes (an administrative note supports no transition, so none is gold-
  expected).

## Changed-dimension analysis (L01 §6.4)

The declared changed dimensions
(`response_release_surface`/`response_release_form`,
`response_transition_applicability`, `corrective_chain_timing`) are real and
account for the primary behavioral difference. Materializing both variants
surfaced several **additional, dimension-implied but not separately named**
differences worth recording for interpretation:

1. **Quantity-of-material asymmetry at response.** The acquisition's
   response release is five substantive documents (register, cover letter,
   revised manifest, run register, hydraulic report); the probe's response
   release is one five-line administrative note. This is the intended
   content of `response_release_form`, but the sheer brevity/emptiness of
   the probe's response release is itself a strong surface signal that
   "nothing changed," independent of any domain judgement about drainage
   evidence governance. See "Domain realism" and "Gate sufficiency" below
   for the implication (possible reading-comprehension shortcut, ceiling
   risk for cold agents on this specific behavior).
2. **Closeout information load asymmetry.** In the acquisition, closeout
   only needs to process the propagated memo plus the closeout register
   (the manifest/run/report were already reviewed at response). In the
   probe, `_direct_closeout_release` merges the seed's `response_review`
   files (corrected manifest, run register, report) *and* the seed's
   `closeout_review` files (register, memo) into one closeout release
   (`drainage_variants.py:301-307`), so the probe's closeout step must
   process everything the acquisition processed across *two* checkpoints in
   *one* checkpoint. This is an implied consequence of
   `corrective_chain_timing`, not an undeclared confound (both study arms
   face the identical probe), but it does mean the probe's closeout
   checkpoint carries materially more review load than the acquisition's
   closeout checkpoint — worth noting when interpreting absolute headroom.
3. **Finding-count asymmetry.** The acquisition opens and closes two
   distinct findings (`F-PRV03-001`, `F-PRV06-001`) across the lifecycle;
   the probe's gold state never opens `F-PRV06-001` at all, because the
   corrected report and the propagated memo arrive simultaneously at
   closeout in the probe, so PRV-06 never has a "not yet propagated"
   window. Existing test
   `test_deferred_correction_sources_only_name_findings_present_in_gold`
   (line 264) explicitly asserts `"F-PRV06-001" not in source_finding_ids`
   for this variant, confirming this is deliberate, not a bug. This makes
   the probe's finding-tracking task slightly simpler in one respect (fewer
   IDs to track) while its evidence-completeness check is more demanding in
   another (verify a full chain arriving at once rather than staged).
4. **Decision-numbering divergence.** `D-PRV01-002` refers to a
   register-based-on-Rev-F decision in the acquisition but to a
   register-based-on-Rev-G decision directly in the probe
   (`_configure_direct_closeout_policy`, `drainage_variants.py:310-314`).
   The same decision ID means a different accepted object across variants.
   This is harmless for validity (each package is self-contained; a probe
   run never sees the acquisition's package), but it means a memorized
   mapping of "decision ID → basis document" from the acquisition would be
   actively wrong if applied to the probe — which is arguably a feature for
   detecting rote memorization, not a defect.

None of these additional differences threaten the cold-vs-structured-memory
comparison itself (both arms face byte-identical probe packages), but items
1 and 2 are worth flagging as **headroom/difficulty-asymmetry risks** for
interpreting absolute (not relative) probe performance, and should be
watched during the Stage 2 pilot per the interpretation matrix in L01 §20
("All arms at ceiling... no learning conclusion").

## Sequence-copy detectability (verified from gate logic, not intuition)

To test whether a learner that mechanically copies the acquisition's
response-stage transition onto the probe would be penalized, two "copycat"
submission sequences were constructed and run through the live
`verify_lifecycle` against the materialized probe package (gold `initial`,
then the **acquisition's** gold `response_review`/`closeout_review`
submissions substituted for the probe's):

**Full copy (response and closeout both copied from the acquisition):**

```text
overall: fail
reward: 0.8967   (perfect/gold reward is 1.0)
checkpoint_contract:              FAIL  score 0.8889
reviewer_self_consistency:        pass  score 1.0
staged_disclosure:                FAIL  score 0.8837  (cites MANIFEST-03-042 Rev B,
                                                        REG-03 Rev F, REPORT-03-043 Rev A,
                                                        RUN-03-REGISTER-01 Rev F — none
                                                        released at response in the probe)
finding_continuity:                FAIL  score 0.6667  (F-PRV03-001 closed prematurely)
closure_evidence:                  FAIL  score 0.8148
accepted_decision_preservation:    FAIL  score 0.9193
final_readiness:                   pass  score 1.0    (coincidentally same final state)
claim_boundary:                    pass  score 1.0    (boilerplate statement unchanged)
semantic retention: 0.583, interference: 0.417, acquisition: 0.194
```

**Response-only copy (agent recovers correctly at closeout):**

```text
overall: fail
reward: 0.9203
checkpoint_contract, staged_disclosure, finding_continuity, closure_evidence,
  accepted_decision_preservation: all FAIL
final_readiness, claim_boundary:  pass
semantic retention: 0.605, interference: 0.395
```

**Conclusion:** sequence-copying is clearly and repeatably detected. Five of
the eight gates fail, canonical reward drops materially (~8-10 points off a
1.0 ceiling), and three of L01's four *primary* projections
(`staged_disclosure`, `finding_continuity`, `closure_evidence`) directly
catch it with large score drops. `claim_boundary` — the fourth primary
projection — does **not** catch this failure mode in either simulation,
because the boilerplate disclaimer text is unaffected by the copying error
(see "Gate sufficiency"). `final_readiness` also does not catch it,
consistent with its status as a *secondary* (not primary) projection in
L01's `study.toml`.

## Leakage

- The probe's public release content and the acquisition's identical
  instructions do not name the probe, the acquisition, or the relation.
  `README.md` and all three `instructions/*.md` files are byte-identical
  between variants.
- `drainage_staged_review_feedback()` (`drainage_learning.py:49-83`)
  hard-rejects any record whose `task_id != DRAINAGE_ACQUISITION_TASK_ID`
  (`feedback-source-task-mismatch`), so it structurally cannot be invoked
  on, or leak, probe-side evidence. It is bounded to a fixed field
  allowlist (`_TOP_LEVEL_FIELDS`) that excludes hidden gold, verifier
  config, raw gate failures, package/run paths, and probe identity, matching
  L01 §11.2's exclusion list.
- The static `_REVIEW_PRINCIPLES` released with structured-memory feedback
  ("Non-governing administrative material does not justify correction or
  closure", etc.) are generic evidence-governance statements, not a
  paraphrase of the probe's exact release text ("document-control filing
  location has changed") or task/variant identifiers. They match the
  general rule stated in L01 §1/§6.5, which the protocol explicitly permits
  as "bounded evidence-governance principles" (§11.1). No probe-specific
  wording, checkpoint content, or variant name is present.
- The `probe_only` family-overlay flag is validated only at protocol-load
  time (`protocol_collection.py:94-95`, cross-checking role vs. `probe_only`
  for internal consistency) and is never surfaced to an agent; it is not
  agent-visible content.
- No leakage found that would differentially favor the structured-memory
  arm over the cold-reset arm, nor any leakage that reveals the probe's
  no-op status ahead of the agent reading the actual response release.

## Domain realism

Both variants are professionally plausible for a stormwater/drainage model
review workflow: a document register with revisions, a catchment/rainfall
basis pack, a model-input manifest, a hydraulic run register and report
(peak flow, HGL, continuity error), a design memo, and a comment/action
register are all standard artifacts in a real drainage-model QA/QC review.
The corrected-manifest-then-rerun-then-report-then-memo-propagation sequence
in the acquisition, and the deferred-combined-release-at-closeout sequence in
the probe, are both realistic staging patterns.

One realism caveat, not a defect: the probe's administrative note is
unusually explicit for an in-fiction document —
*"No model input, run, report, memo, or governing revision changes"* reads
as a direct statement of the grading criterion rather than naturalistic
document-control prose (a real filing-location notice would not typically
enumerate exactly the categories the review matrix cares about). This
appears deliberate, consistent with the template's declared status as a
"task-owned synthetic source packet" built for deterministic, unambiguous
grading rather than maximal realism. It is visible identically to every arm
(cold, reset, structured-memory), so it does not asymmetrically bias the
comparison, but it does raise the "gate sufficiency" and reading-shortcut
concern below.

## Gate sufficiency

The four primary projection gates (`staged_disclosure`,
`finding_continuity`, `closure_evidence`, `claim_boundary`) plus canonical
reward were evaluated directly (not by inspection alone) against a copying
failure mode:

- `staged_disclosure`, `finding_continuity`, `closure_evidence`, and
  canonical reward **do** discriminate correct rule-transfer from
  sequence-copying, with large, reproducible score drops (see
  "Sequence-copy detectability").
- `claim_boundary` **does not** discriminate this failure mode in practice,
  because the gold `claim_boundary_statement` is an identical fixed
  boilerplate string in every checkpoint of every variant, and the gate only
  checks the submitted text against a fixed set of required/forbidden
  phrases, not against evidence state. A learner that reuses the same
  boilerplate disclaimer regardless of what it does with findings/decisions
  will pass this gate every time. This is a real, measurable blind spot for
  this specific relation: one of L01's four declared primary projections
  will very likely show near-zero variance across arms and should not be
  read as supporting (or refuting) a transfer effect on its own.
- Measurement blind spot (headroom): because the probe's non-governing
  release explicitly states its own non-governing nature in plain language,
  a cold agent that merely reads carefully (with no acquisition experience
  at all) may already score well on `staged_disclosure`/`finding_continuity`
  for the response-stage behavior specifically. If cold-arm performance
  turns out to be near-ceiling on these gates in the Stage 2 pilot, that
  would indicate limited headroom for the structured-memory treatment to
  show an effect on this specific sub-behavior — this is a risk to monitor
  empirically, not a structural flaw in the relation, and the protocol's own
  interpretation matrix (§20) already anticipates and handles this pattern.
- No blind spot was found that would let a genuine sequence-copier pass
  *unnoticed* on the primary canonical-reward projection: canonical reward
  is the mean of all eight gates (not just the four primary ones), so even
  if `claim_boundary` alone were insensitive, the combined signal from the
  other seven gates still produces a materially lower reward for a copier
  in both simulations run.

## Overall recommendation

**Conditionally justified.** The relation itself is sound: all five
invariant claims are confirmed by direct inspection of materialized package
content and by running the live verifier against constructed adversarial
submissions, not merely by reading the protocol's prose description. No
leakage was found. Sequence-copying is detected, not rewarded. Domain
content is professionally plausible for the discipline being tested.

Supplying `relations_reviewed=true` for claim-bearing L01 runs is
**justified**, subject to these conditions:

1. **Programme-owner decision on reviewer standing.** The programme owner
   must explicitly decide whether this AI-performed review satisfies the
   protocol's "independently reviewed by a drainage/domain reviewer"
   requirement (L01 §3, §22), or whether a credentialed human
   drainage/stormwater engineer must also sign off before treating any L01
   result as a causal claim about a frontier model. This review supplies
   evidence but does not itself resolve that governance question.
2. **Do not weight `drainage.claim-boundary` as discriminating evidence**
   for this relation in the pilot or claim-bearing analysis. Report it, but
   interpret a null or ceiling result on this projection as expected, not as
   evidence against transfer.
3. **Watch for ceiling effects on `staged_disclosure`/`finding_continuity`
   in the cold-reset arm** during the Stage 2 pilot (L01 §16), given the
   probe's unusually explicit non-governing disclaimer. If cold-arm
   performance is already near 1.0 on these gates, treat the study as
   headroom-limited per L01 §20 rather than concluding an absence of
   transfer.
4. **No change to the relation, family.toml, study.toml, or lifecycle code
   is required** as a precondition; all findings above are either
   confirmations or documented interpretive cautions, not defects that
   require re-authoring the relation.

## Materialization and verification commands used

```bash
uv run python -c "
from pathlib import Path
from aec_bench.lifecycles.catalogue import materialize_lifecycle
materialize_lifecycle('drainage-model-evidence-lifecycle-review', Path('acq'), variant_id='staged_full_correction')
materialize_lifecycle('drainage-model-evidence-lifecycle-review', Path('probe'), variant_id='semantic_no_op_release')
"
diff -rq acq probe
```

Both scratch directories were removed after inspection; no materialized
package artifacts are retained in this document beyond the excerpts quoted
above.
