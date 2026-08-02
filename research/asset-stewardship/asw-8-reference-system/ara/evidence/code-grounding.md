# ABOUTME: Maps the ASW-8 design decisions to current pump-station source code.
# ABOUTME: Separates reusable behaviour from two-pump limits and shared-contract boundaries.

# ASW-8 code grounding

This audit uses commit `f73c692e606c2319d143bcd27cb4aafdd8d38571`,
tree `a960c51fb12621be88aaa368880f0aba8bdd773c`.

## Station data and physics

- `au-nsw-lh-syn-sps-v1-claim-and-profile.md` fixes two pumps, one canonical
  transfer, and profile revision for a topology change.
- `reference_package_reader.py` pins the v1 identity, inventory, manifest,
  cross-file fields, and bytes.
- `physical_models.py::PumpStationModel` requires two pump IDs and one maximum
  running pump.
- `physical_models.py::PumpStationState` stores one duty pump, one standby
  pump, and exactly two pump states.
- `physical_models.py::OperatingInterval` stores one duty-pump exposure.
- `physical_models.py::PumpStationEnvironment` has one station-wide
  `isolated` Boolean, so it cannot express target-local isolation with sibling
  operation.
- `physical_kernel.py::pump_station_model_from_package` rejects a component
  count other than two.
- `physical_kernel.py::advance_pump_station` advances one duty pump.
- `physical_kernel.py::transfer_duty_to_standby` swaps the two pump roles.
- `stewardship_state_machine.py` currently gives all scheduled runtime to one
  duty pump and records zero starts.

These sources support a separate v2 package and coupled physical records. They
do not support injecting Pump C into the v1 model.

A narrow design calculation loaded the promoted v1 package and used the
current pump-local kernel with the exact copied constants proposed for v2. B
at obstruction `0.10539999999998400` and clearance loss
`0.00011999999998800` returned `review_required = false`. A C-equivalent pump
at obstruction `0.00514999999968000` and clearance loss
`0.00239999999976000` returned `NO_MATERIAL_CONFIRMED` and
`review_required = false`. This supports the fixed RS1 conditions; it is not an
ASW-8 implementation test.

## Work and resources

- `stewardship_models.py::PumpStationWorkResources` stores access seconds, one
  repair-kit Boolean, and an intervention-slot count.
- `stewardship_models.py::PumpStationResourceReservation` stores one resource
  kind and no quantity.
- `PumpStationStewardshipState.resources` requires the singleton
  `PumpStationWorkResources`, and its top-level `resource_reservations` field
  requires legacy reservation records. V4 must select the pool state and
  quantity-reservation forms instead of retaining both truths.
- `rich_work_processes.py` defines fixed bundles, one reservation per kind,
  target clearance, reserve, release, completion, suspension, resumption, and
  cancellation.
- `tests/task_world_templates/stewardship/wastewater_pump_station/test_asw_5_process_rules.py`
  covers remaining duration, resource release, kit retention and consumption,
  waiver limits, and singleton exclusion.

ASW-8 must generalise pool and reservation records. It retains the accepted
process effects.

## Views and versions

- `stewardship_views.py::PumpStationCurrentStateView` contains singular duty
  and standby fields.
- `stewardship_views.py::project_actor_view` adds current rich-work and
  evidence-health fields and performs redaction;
  `stewardship_views.py::bind_information_set` binds the visible content.
- `time_presentation.py` assigns `pump-station-current-state.v4` to the
  date-aware actor projection.
- `world_run_serialization.py` uses an internal v4 profile for that projection
  while state-profile detection recognises only v2 and v3.
- `world_session.py` infers several features from exact state-version suffixes.

ASW-8 can use stewardship state v4, but it needs actor projection v5 and
separate serializer routing. Exact v3 checks must not drop evidence-health
fields from v4.

## Durable history and replay

- `world_run_models.py` defines coherent v1-v3 record sets and v1-to-v2 and
  v2-to-v3 migrations.
- `world_run.py` checks model identity on resume and publishes idempotent
  transitions.
- `world_run_repository.py` owns immutable content, locks, atomic head update,
  and recovery.
- `stewardship_verifier.py` replays the ordered chain and compares the complete
  transition.

ASW-8 reuses this machinery. It adds one coherent v4 record set and no
two-pump-to-three-pump migration. The derived conservation report checks the
chain and does not repair it.

## Actor, Harbor, evaluation, and branches

- `contracts/world_interface.py::WorldActorActionRequest.binding` owns the
  base-view, information-set, tenure, and sequence binding;
  `actor_interface.py::pump_station_proposal_from_actor_request` copies it into
  `ProposalContext` with the reason and request identity. Actor interface v1
  has the old action catalogue.
- `actor_interface.py::PUMP_STATION_ACTOR_ACTION_NAMES` includes the two-pump
  `transfer_duty` and fixed-transfer `request_conditional_deferral` actions,
  and has no `request_functional_check` action. Current clearance completion
  schedules the functional-check process directly in
  `stewardship_events.py::_complete_obstruction_clearance`. Interface v2 must
  omit both topology-specific actions and add an explicit backlog-bound
  functional-check request without changing legacy catalogues.
- `world_session.py` owns the direct task session.
- `harbor_export.py` binds the package, task ID, tool list, and hashes, but it
  does not yet bind the actor interface version.
- `harbor_session.py` and `harbor_verifier.py` contain the current two-pump
  reference flow and final-value checks.
- `evaluation/stewardship.py` recomputes current task metrics and terminal
  state.
- `contracts/evaluation_result.py` and `contracts/trial_record.py` provide
  shared envelopes without a need for pump-station ledger rows.
- `contracts/evaluation_result.py::EvaluationResult` has no verification-report
  ID. `WorldTrialProvenance.verification_report` binds the report artifact, and
  `StewardshipEvaluationEvidence.imported_artifact_sha256` can carry its hash
  after Harbor import.
- `StewardshipEvaluationEvidence` also contains manifest, initial-state,
  terminal-state, and replayed-transition content identities. The stewardship
  Harbor importer fills `imported_artifact_sha256`, while direct evaluation
  does not. A full `EvaluationResult` is therefore not a valid cross-transport
  equality object. ASW-8 needs a task-local semantic projection that excludes
  this evidence object and normalizes transition-derived work identities.
- `world_run_models.py::PumpStationWorldRunManifest` uses
  `serialization_version = pump-station-world-run.v1` and has no
  reference-system, opening-state-specification, or event-schedule identity
  fields.
- `world_session.py::PumpStationWorldSessionFactory` accepts a caller schedule,
  builds the initial state before `PumpStationWorldRun.create`, and does not
  load a named scenario descriptor or opening-state specification. The current
  manifest binds only the resulting initial-state identity. ASW-8 therefore
  needs a closed task-local descriptor registry and immutable source artifacts
  before the state is constructed.
- `rollout_control.py` creates isolated world-run children and retains package,
  model, record, event, and information-boundary identities. It does not copy
  or initialise the parent's `temporal-evidence` repository.
- `rollout_interface.py` fixes
  `PUMP_STATION_ROLLOUT_CONTROL_INTERFACE_VERSION` at
  `pump-station.rollout-control.v1`. Its request and result fields name the
  concrete v1 rollout records. Replacing those field types under the same
  interface identity would change the accepted installed JSON schema, so
  ASW-8 needs a separate rollout-control v2 route.
- `rollout_models.py::PumpStationRolloutChildRequest` is an unversioned frozen
  dataclass, and `PumpStationRolloutControlResult.origin_verification` is fixed
  to the legacy `PumpStationVerificationReport`. V2 needs a strict
  content-addressed child request and a result fixed to
  `PumpStationCoupledVerificationReport`; widening the v1 types would change
  its accepted schema.
- `world_session.py::PumpStationWorldSessionFactory.open` enables temporal
  tools on resume only when the selected run root already contains the
  temporal capability. An ASW-8 rollout child therefore needs an explicit
  confined child-corpus initialisation path.
- `world_session.py::_temporal_access_context` currently supplies
  `branch_ancestor_ids=()`. A child-initialisation record must persist the
  parent's ordered ancestors followed by the parent branch, and every resumed
  child access context must load that chain.
- `PumpStationWorldSessionFactory` enables temporal tools through an optional
  `temporal_evidence` Boolean. Actor interface v2 always names search and fetch,
  so RS1 must require, initialise, verify, and bind that capability before the
  catalogue is published.
- `temporal_evidence/corpus.py::build_reference_temporal_evidence_bundle` is
  tied to the v1 package and its document text, uses
  `REFERENCE_WORLD_TIME_SECONDS = 7_200_000`, applies documents to the
  `normal-duty-standby` regime, and does not cover Pump C in its common
  applicability. Its evidence versions and branch policy also include the
  world branch, so complete corpus and bundle hashes differ across direct,
  Harbor, and child branches. The v1 builder must remain unchanged. A separate
  RS1 template and root builder must use in-window times and bind each realised
  root corpus in its manifest. A rollout child must copy and bind the parent's
  exact public bundle and add only child ancestry and fresh private retrieval
  state.
- `TemporalEvidenceAvailabilityEvent` is documentary state and does not create
  an actor turn. The current world scheduler does not select its next stop from
  the temporal schedule. The current `DECISION_POINT` also refreshes enabled
  observation sources, so it is not a no-op. RS1 therefore needs a v4-only,
  branch-neutral 100,800-second `DOCUMENT_REVIEW_POINT` that advances the world
  clock without refreshing evidence; creation and ingestion remain non-turn
  temporal facts.

ASW-8 adds a task-owned actor interface v2, task evaluation v2, and strict
v2/v4/v5 transport support. It reuses shared envelopes and ASW-7 branching.
It does not perform shared extraction.

## Current semantic risks for the new version

- `stewardship_events.py` must not lift a run-in restriction after failed
  verification. ASW-8 retains the restriction and generates one rework item.
- Current verification completion can lift a restriction inside one event
  effect. V4 requires an explicit host-only Operations boundary review with a
  separate receipt. Without that receipt, a verified pump remains
  `run_in_service`, and a no-finding inspection target remains isolated.
- `stewardship_events.py::_complete_functional_checks` and
  `stewardship_events.py::_complete_verification` call
  `physical_kernel.py::assess_pump_station`; the coupled version must produce
  target-specific capability instead of the current singular-duty result.
- The current process clock does not add target-pump exposure during a
  functional check. ASW-8 needs a separate test-running set so the target gains
  physical runtime and starts without supplying service or collateral SCU.
- The current model has no durable pump-local `test_only` boundary between
  successful clearance and provisional return. ASW-8 must record that mode,
  require an Operations controlled-test permit, and leave a failed check on
  the same planned WG-03 item rather than granting service eligibility or
  inventing an undeclared follow-up.
- Planned outage admission must not use hidden future events.
- The serializer must not use one v4 selector for both durable state and the
  already existing temporal actor projection.
- The current world-run manifest must remain v1. ASW-8 needs manifest v2 for
  reference-system and event-schedule bindings without changing v1 bytes.

These are ASW-8 version requirements. Historical run meaning remains intact.
