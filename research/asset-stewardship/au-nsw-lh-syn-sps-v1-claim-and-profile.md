# ABOUTME: Freezes the ASW-0B1 identity, semantic envelope, intended construct, and claim limits for the first reference profile.
# ABOUTME: Keeps evidence, numerical mechanisms, engine choices, runtime contracts, and study treatments in their later gated stages.

# `AU-NSW-LH-SYN-SPS-v1` claim and profile freeze

| Field | Value |
| --- | --- |
| Stage | `ASW-0B1 — claim and profile freeze` |
| Status | ASW-0B1 accepted; ASW-0B2 is the next permitted stage |
| Recorded | 2026-07-27 |
| Reference profile | `AU-NSW-LH-SYN-SPS-v1` |
| Parent authority | [Asset Stewardship Worlds PRD](asset-stewardship-worlds-prd.md), revision `ASW-PRD-F-2026-07-27` |
| Required parent SHA-256 | `56d6fe6a9c69796d819a1995ae63a85392ba85a4240df8baa87df99a76678335` |
| Accepted predecessor | [ASW-0A baseline and authority record](asw-0a-baseline-and-authority.md), merged by PR 25 at `1ea2606d4b71af26679b0aa68b8e8c5b2eccac0e` |
| Target branch/worktree | `feat/asset-stewardship-asw-0b1` / `.worktrees/asset-stewardship-asw-0b1` |
| Claim maturity | Profile definition only; V0, V1, V2, V3, and V4 have not been earned |
| Contract status | Design authority only; not a runtime schema, persisted payload, public API, compliance statement, or compatibility promise |

## 1. Stage decision

ASW-0B1 commits one unambiguous identity and semantic envelope for the first
Asset Stewardship Worlds reference profile. Later evidence, software, generation,
certification, research, boundary, and implementation stages must work within
this envelope or amend it explicitly before depending on a changed profile.

ASW-0B1 does not certify a world generation. It prevents later work from quietly
changing the asset, region, benchmark purpose, validity target, or claim limits
to fit whichever evidence, engine, or implementation proves convenient.

## 2. Canonical profile claim

> `AU-NSW-LH-SYN-SPS-v1` is a versioned, original, fictional reference-profile
> definition for a future synthetic family representing a duplex submersible
> wastewater pumping station in a Lower Hunter, New South Wales operating
> context. Its asset boundary contains Pump A and Pump B in a fixed
> duty/standby arrangement. The intended benchmark examines bounded asset
> stewardship across simulated time and handover. The profile does not identify,
> reconstruct, or approximate a real station, and it earns no physical,
> standards-grounded, regional-practice, or benchmark-validity claim until the
> corresponding V1, V2, or V3 gate passes.

This claim is the maximum permitted ASW-0B1 statement. Later documents may make a
narrower statement. They may not make a broader statement without an explicit
profile amendment and renewed review of every dependent artifact.

## 3. Identity and version semantics

| Identity element | Frozen meaning |
| --- | --- |
| `AU` | Australian fictional operating context; not an Australian compliance determination |
| `NSW` | New South Wales regional frame for later source and practice review; not a claim of statewide representativeness |
| `LH` | Lower Hunter fictional context; not a named utility, council, catchment, network, or physical site |
| `SYN` | Original synthetic profile and future synthetic generations; not reconstructed or field-calibrated by implication |
| `SPS` | Profile label for the submersible wastewater pumping-station archetype; not a real station identifier |
| `v1` | First frozen profile definition; distinct later world generations receive separate generation identities |

The profile identifier is not a world-instance identifier, generation identifier,
promotion-manifest identifier, run identifier, or branch identifier. Later stages
must preserve those identities separately.

Changing the region, asset type, component count, duty/standby topology, intended
construct, V3 target, or prohibited claims requires an explicit profile revision.
Evidence-driven numerical narrowing inside this envelope does not by itself
create a new profile, but every world generation remains separately identified
and content addressed.

## 4. Fictional regional context

The profile uses a Lower Hunter, New South Wales operating context because it
provides one coherent regional frame for later terminology, source selection,
environmental assumptions, operating constraints, and practice review.

That context is deliberately fictional:

- no utility, council, operator, project, station, address, coordinate,
  catchment, network topology, asset register, or work history is represented;
- no real station is used as a hidden template or claimed analogue;
- no absence of field data is filled by presenting synthetic values as observed
  regional facts;
- no Australian or New South Wales law, standard, guideline, or utility practice
  is declared satisfied at this stage; and
- later regional sources may constrain or invalidate the synthetic envelope but
  cannot turn the profile into a real-asset representation by implication.

ASW-0B2 owns evidence and rights classification. Until it accepts a source and
maps it to a claim, regional details remain profile intent rather than supported
regional-practice claims.

## 5. Asset and component boundary

### 5.1 Asset in scope

The benchmark asset is one duplex submersible wastewater pump set represented by
exactly two component units:

- **Pump A**; and
- **Pump B**.

Each pump may later receive its own latent physical state, operating exposure,
observable evidence, restrictions, intervention history, and verification state.
Those fields and mechanisms are not defined by ASW-0B1.

The pumping-station label supplies operating context for the pump pair. It does
not add a third component or silently expand the asset boundary to the complete
station.

### 5.2 Context and constraint surfaces

The following may enter later generations only as explicit environmental,
resource, evidence, or boundary conditions:

- wet-well and incoming wastewater conditions;
- discharge-system conditions;
- electrical power availability;
- access and outage availability;
- personnel, lifting, or other intervention-access constraints;
- spare-parts availability and lead time; and
- instrumentation, inspection, and institutional records used as evidence.

These surfaces do not become independently managed assets in `v1`. Their presence
does not authorise full wet-well, network, electrical-system, workforce,
inventory, or work-management simulation.

### 5.3 Excluded asset scope

The profile excludes:

- a real or reconstructed pumping station;
- more than two pump components;
- fleets, multiple stations, catchments, or network optimisation;
- generalised redundancy or coupled-asset duty allocation;
- a complete wastewater process, hydraulic network, electrical, controls,
  enterprise asset-management, or work-management model; and
- an ontology intended to generalise across pump, station, or asset classes.

## 6. Fixed Pump A/Pump B duty rule

The profile freezes the following arrangement:

1. Pump A is the initial duty pump.
2. Pump B is the initial standby pump.
3. The initial vertical slice may exercise one canonical duty transfer from
   Pump A to Pump B.
4. The profile does not use periodic alternation, simultaneous load sharing,
   fleet optimisation, or an adaptive duty-selection policy.
5. Physical trigger and consequence belong to ASW-0B4; scenario timing belongs
   to ASW-0C; authority and transition semantics belong to ASW-1; implementation
   belongs to ASW-2. ASW-0B1 does not encode them as a runtime rule or schema.

This is a bounded benchmark topology, not an operational recommendation about
how a real duty/standby station should be controlled.

## 7. Intended benchmark construct

Subject to V3 certification, the profile is intended to support a bounded
benchmark of whether an agent acting as an asset steward can:

- preserve due obligations across simulated time and a mid-trajectory handover;
- distinguish latent physical truth, observable evidence, and institutional
  assertions;
- make evidence-grounded decisions using only the information available at the
  decision point;
- manage deferral, restriction, access, spare, or lead-time consequences;
- carry forward follow-up and post-maintenance verification obligations; and
- leave an inspectable record whose future consequences can be replayed and
  independently evaluated.

The first planned research focus is obligation continuity across time and
handover under fixed world histories. The exact histories, carrier treatments,
endpoint, estimand, budgets, and claim ladder remain ASW-0C decisions.

The profile is not intended to benchmark:

- pump selection, detailed station design, hydraulic-network optimisation, or
  control-system design;
- real-world reliability, remaining useful life, failure probability, or
  maintenance-interval prediction;
- compliance checking or operational approval;
- enterprise asset-management completeness;
- fleet or multi-asset optimisation;
- general language-model competence; or
- continual learning, adaptation, transfer, or causal treatment effects before
  their separately controlled programme gates.

## 8. Semantic operating envelope

ASW-0B1 freezes the shape of the envelope, not its numerical values.

| Dimension | Included in the `v1` semantic envelope | Excluded or deferred |
| --- | --- | --- |
| Asset population | One fictional pump set with Pump A and Pump B | Real assets, fleets, or more than two components |
| Role topology | Initial A-duty/B-standby assignment and one canonical A-to-B transfer | Periodic rotation, load sharing, optimisation, or generalised redundancy |
| Time and exposure | Simulated calendar time plus pump operating exposure such as operating hours and starts | Wall-clock background execution, stochastic prognostics, and numerical ranges before ASW-0B4 |
| Physical evolution | Deterministic deterioration with meaningful no-maintenance consequences | Mechanism forms, parameter values, equations, and tolerances before ASW-0B4 |
| Evidence | At least one condition trend or inspection path through which observations may differ from latent truth | Real sensor data, manufacturer claims, and observation schemas before their evidence and boundary stages |
| Stewardship work | Deferral, restriction, intervention, follow-up, and verification must be meaningful in the eventual reference trajectory | Exact action, authority, obligation, process, and receipt contracts before ASW-0C and ASW-1 |
| Resources | At least one access, spare, outage, or lead-time constraint may affect the trajectory | Enterprise workforce, inventory, procurement, or outage-management simulation |
| Execution | One deterministic, replayable, locally executable reference scenario | Providers, Harbor integration, runtime schemas, or source code during ASW-0B1 |

The numerical synthetic parameter family and operating limits are jointly owned
by ASW-0B4. ASW-0B1 constrains their semantic scope but does not guess values,
units, distributions, curves, failure rates, or tolerances.

## 9. Validity target and current maturity

The profile targets **V3 — construct-valid benchmark** before any ASW-2 runtime
implementation begins.

| Level | ASW-0B1 status | Claim discipline |
| --- | --- | --- |
| V0 — reproducible synthetic | Not yet earned | No generated artifact or replay exists |
| V1 — physically coherent | Not yet earned | No physical-coherence, numerical-validity, or bounded-envelope claim |
| V2 — standards-grounded archetype | Not yet earned | No standards-grounded or regional-practice claim |
| V3 — construct-valid benchmark | Required future gate | No benchmark-suitability claim until AG-01 through AG-13 and the V3 evidence pass |
| V4 — optional empirical calibration | Not required and not implied | No field-calibrated, representative, or operational-authority claim |

Any parent-PRD description of the profile as “standards-grounded” or as a
benchmark archetype is a target-state programme description. It is not evidence
that V2 or V3 has already been achieved.

## 10. Prohibited claims

The following claims are prohibited unless a later explicitly authorised stage
earns the narrower claim it names:

| Prohibited claim | Maximum permitted wording before its gate |
| --- | --- |
| The profile represents, reconstructs, approximates, or anonymises a real station | It is an original fictional profile |
| The profile represents a utility, council, Lower Hunter population, or typical NSW practice | It uses a fictional Lower Hunter regional context for later source review |
| The profile or a generated world is compliant with law, standards, guidelines, utility requirements, or design approval | Later sources may inform bounded synthetic assumptions; no compliance claim |
| The profile gives an operational, maintenance, safety, or control recommendation | It defines a research benchmark envelope only |
| Degradation parameters are observed failure rates, reliability statistics, manufacturer performance, or population estimates | Numerical families will be synthetic unless later specific V4 evidence supports a narrower claim |
| A generated world is physically coherent | Prohibited until V1 passes |
| The family is standards-grounded or regionally grounded | Prohibited until V2 passes |
| The profile is suitable as an agent benchmark | Prohibited until V3 passes |
| The profile is a digital twin or field-calibrated model | Prohibited without the corresponding narrowly scoped V4 evidence; “digital twin” remains prohibited for `v1` |
| Results generalise to other pumps, stations, networks, regions, utilities, or operating regimes | Results apply only to accepted generations inside the certified envelope |
| A model is competent, handover causes an effect, learning occurred, or continual learning occurred | Those require separate executed studies and the programme research-claim ladder |

Prohibited claims apply to source notes, generated artifacts, code comments,
package metadata, task instructions, run records, reports, figures, PR text, and
public descriptions—not only to this document.

## 11. Deferred decisions and owners

ASW-0B1 is complete only if every important unresolved technical decision has a
named later owner rather than being smuggled into this profile as an assumption.

| Deferred decision | Owning stage |
| --- | --- |
| Source authority, evidence class, rights class, citation/hash, claim mapping, units authority, and redistributability | ASW-0B2 |
| Generator, independent certifier, runtime, optional agent-tool, and deferred-live-solver roles | ASW-0B3 |
| Numerical parameter family, operating ranges, primary and secondary mechanisms, equations, transformations, units, transfer physics, observation model, intervention effects, invariants, tolerances, sensitivities, and stop rules | ASW-0B4 |
| Generated world-family members, replay evidence, independent certification, rejected generations, and V3 promotion decision | ASW-0B5 |
| First scenario histories, exact action and authority catalogue, obligations, carrier treatments, endpoint, estimand, budgets, and research claims | ASW-0C |
| Host-execution boundary, conceptual schemas, validation/failure semantics, package ownership, persistence, visibility, and promotion plan | ASW-1 |
| Runtime package, physical kernel, state machine, projections, persistence, CLI, Harbor, records, and evaluation implementation | ASW-2 |
| Temporal Evidence Frontier declarations, retrieval, corpus, ranker, and providers | Not before an accepted ASW-4 checkpoint |

No deferred item is an optional hole in the profile. Its owning stage must
resolve, narrow, or explicitly remove it before the dependent stage opens.

## 12. Change control

Later evidence may show that the frozen profile is incoherent, unsupported,
unlawful to distribute, too broad for deterministic certification, or too narrow
to exercise the intended construct. That is a successful stop signal.

If a required change alters the frozen identity, regional fiction, two-component
boundary, duty topology, intended construct, V3 target, or prohibited claims:

1. stop the dependent stage;
2. amend this authority through a separately reviewed change;
3. issue a new profile revision when the meaning changes materially;
4. update or invalidate dependent evidence and decisions explicitly; and
5. never rewrite an accepted world generation or its provenance in place.

## 13. ASW-0B1 acceptance gate

| Gate | Assessment |
| --- | --- |
| Parent binding | Pass: revision and SHA-256 bind the accepted parent PRD |
| Predecessor binding | Pass: the stage begins from accepted PR 25 merge `1ea2606d4b71af26679b0aa68b8e8c5b2eccac0e` |
| Profile identity | Pass: one fictional `AU-NSW-LH-SYN-SPS-v1` identity with explicit version semantics |
| Regional identity | Pass: Lower Hunter context is committed without naming or implying a real asset or representative population |
| Asset boundary | Pass: one pump-set asset and exactly two component pumps; contextual systems do not become assets |
| Duty/standby rule | Pass: A-duty/B-standby initial state and the sole canonical A-to-B transfer topology are explicit |
| Intended construct | Pass: obligation continuity and evidence-grounded stewardship across time and handover are bounded |
| Validity discipline | Pass: V3 is the target; V0 through V4 current maturity and permitted language are explicit |
| Claim limits | Pass: real-asset, regional-representativeness, compliance, operational, observed-failure, digital-twin, benchmark, and learning claims are prohibited at their current maturity |
| Deferred ownership | Pass: evidence, engines, mechanisms, studies, schemas, implementation, and TEF each have a later owner |
| Stage isolation | Pass: no source, schema, runtime package, implementation code, test, engine, provider, or study treatment is introduced |
| Exit gate | Pass: one reviewable claim-and-envelope statement exists with no unresolved asset identity or claim inflation |

ASW-0B1 acceptance authorises **ASW-0B2 — evidence and rights pack** as the only
next programme stage. It does not authorise ASW-0B3, ASW-0B4, ASW-0B5, ASW-0C,
ASW-1, ASW-2, or any Temporal Evidence Frontier work by implication.
