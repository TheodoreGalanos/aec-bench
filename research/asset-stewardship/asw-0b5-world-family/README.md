# ABOUTME: Defines the B5-W0/W1/W2 research boundary and approved pre-W3 composition repair.
# ABOUTME: Prevents research code, raw engine artifacts, candidate semantics, and repair records from becoming production contracts.

# ASW-0B5 world-family research implementation

This directory contains `B5-W0 — research boundary and canonical
declarations`, `B5-W1 — real generator`, and `B5-W2 — independent
certifier` for
`AU-NSW-LH-SYN-SPS-v1`. W0 turns the accepted B4 authority chain into an
executable byte and lineage boundary. W1 validates canonical requests,
materializes the repaired W1 hydraulic mapping, executes the pinned real SWMM
engine, extracts allowlisted semantic candidates, and proves exact replay.
W2 transfers only permitted canonical bytes into a separately executable
certifier, reconstructs the W1 catalogue and physics independently, evaluates
exact and qualitative invariants, and emits threshold-free residual
observations. The approved pre-W3 repair records three rules falsified by
those observations and the real engine before quantitative composition
begins. It changes no W1 member, W2 case, generator request, curve, or
semantic candidate bytes.

It is not an accepted family member, quantitative acceptance, package,
manifest, runtime adapter, agent tool, scenario, or V3 decision. W2's only
valid non-rejection state is `quantitative-pending-w4`; it cannot emit pass,
acceptance, certification, promotion, or V3 claims. Nothing under this
directory may be imported by `src/aec_bench`, and production behavior must
continue to work with `research/` physically absent.

## Exact scope

B5-W0 contains:

- one canonical machine-readable W1 declaration with all 49 stable
  identities: 46 scalar records and three fixed composites;
- one generator-side canonical JSON, identity, path, source, and dependency
  reader under `generator/`;
- one separately implemented certifier-side reader for the same
  specification under `certifier/`;
- one third, lineage-only implementation of the W5 common receipt envelope,
  receipt identity, and structural DAG rules under `lineage/`; and
- focused unit, integration, and separate-process end-to-end tests.

B5-W1 additionally contains:

- the exact repaired W2 case catalogue and mapping authority;
- fail-closed request, member, case, engine, workspace, and rendering gates;
- separate canonical original-pump and net-head engine curves;
- a pinned source/build/receipt boundary for EPA SWMM 5.2.4;
- the real solver lifecycle with exact one-second pump-setting capture;
- official output-library extraction by element name;
- normalized warning, convergence, continuity, and completion diagnostics;
- canonical binary32 SI series, semantic hashes, and exact G70 carry;
- two fresh-workspace replays of all 19 cases and 23 engine segments; and
- unit, integration, and end-to-end tests with no mock engine or fabricated
  output.

B5-W2 additionally contains:

- a path-free transport envelope containing exactly request, original-curve,
  repaired engine-curve, and semantic candidate bytes for each segment;
- an independently reconstructed 19-case, 23-segment catalogue;
- certifier-owned canonical parsing, content identities, binary32 decoding,
  W1 equations, fixed bisection, curve reconstruction, and one-second RK4;
- exact replay, topology, duty, carry, intervention, progression, source,
  engine-profile, diagnostic, maturity, and label checks;
- threshold-free `C-R01` through `C-R24` observations;
- exact capability, ambiguity, intervention, monotonicity, and label-mirror
  relations; and
- an end-to-end subprocess gate where generator code, SWMM, raw artifacts,
  engine paths, and the research workspace are absent.

The approved pre-W3 repair additionally contains:

- one human-readable decision record preserving the falsifying evidence;
- one canonical machine authority binding the W3, W4, and engine-mapping
  predecessor hashes;
- pinned SWMM report-time reconstruction for `C-R04`;
- original pump/system and net-head/static-HGL closures for `C-R06` and
  `C-R07`; and
- a formula-derived absolute edge-time window for `C-R12` that preserves
  exact edge identity and forbids fitting, warping, deletion, or phase reset.

B5-W0/W1/W2 and the pre-W3 repair do not:

- implement W4 tolerances, probes, or sensitivity decisions;
- write a family result, promoted package, manifest, or V3 record;
- define actor-visible fields, stewardship actions, authority, obligations,
  handover, outcomes, evaluation, or scoring; or
- establish a production filename, module, schema, or application interface.

## Authority and declaration

The declaration
`declarations/w1-member-authority.json` was reviewed directly against the W1
stable identity register and owning parameter tables. Its canonical SHA-256
is:

```text
4470e8af16bb6238a11045847199ffad95f1a7f57f64e85978a009bdda30ded9
```

It preserves:

- every W1 scalar anchor, inclusive bound, value kind, evidence class, and
  canonical unit;
- the exact inflow pattern, severity interval, and inspection-band edges;
- the W1 level and inflow ordering identities;
- research-private rights, visibility, and synthetic-claim dispositions; and
- stable rule identities only, without executable formula strings or Markdown
  parsing.

The declaration is research input for later B5 work. It is not the promoted
`physical-member` payload and does not preselect a successful member.

## Independence boundary

The generator and certifier role directories deliberately share no project import,
canonical helper, unit helper, source-identity helper, or receipt helper.
Their permitted common dependencies are the accepted specification, Python's
standard library, UTF-8, decimal arithmetic, and SHA-256.

Each reader:

- reconstructs canonical JSON bytes itself;
- rejects BOMs, duplicate or unknown keys, non-canonical numbers, unsafe
  paths, wrong units, malformed identities, and path-dependent fields;
- validates the same exact authority and W2 case inventories;
- calculates the W5 world-generation identity independently; and
- captures source and dependency inventories under a reader-specific domain.

The lineage role directory is separate from both readers. It cannot call either
reader, issue promotion, or approve its own output.

## Identity formulas

World-generation identity:

```text
sha256(
  "asw-0b5.world-generation.v1\0"
  || canonical_generation_declaration_bytes
)
```

Research-receipt identity:

```text
sha256(
  "asw-0b5.research-receipt.v1\0"
  || receipt_kind
  || "\0"
  || canonical_receipt_bytes
)
```

The generation declaration binds the profile, exact W1–W5 authority hashes,
member and W2 case content identities, W4 catalogue identity, generator,
certifier, engine, replay, receipt-profile, and package-specification
identities. It contains no local path, timestamp, hostname, user, process,
environment-variable name, or mutable alias.

## Focused verification

Run only this research slice:

```sh
ASW_B5_ENGINE_RECEIPT=/absolute/path/to/engine-build-receipt.json \
PYTHONPATH=research/asset-stewardship/asw-0b5-world-family:research/asset-stewardship/asw-0b5-world-family/tests \
  uv run pytest \
  research/asset-stewardship/asw-0b5-world-family/tests -q
```

Static checks are similarly scoped:

```sh
uv run ruff check \
  research/asset-stewardship/asw-0b5-world-family/generator \
  research/asset-stewardship/asw-0b5-world-family/certifier \
  research/asset-stewardship/asw-0b5-world-family/lineage \
  research/asset-stewardship/asw-0b5-world-family/tests

MYPYPATH=research/asset-stewardship/asw-0b5-world-family \
  uv run mypy --strict --explicit-package-bases \
  research/asset-stewardship/asw-0b5-world-family/generator \
  research/asset-stewardship/asw-0b5-world-family/certifier \
  research/asset-stewardship/asw-0b5-world-family/lineage
```

The tests use real files, real source/build receipts, the real pinned solver
lifecycle, and the real official output API. They contain no mock engine,
fabricated SWMM result, fake certification pass, skipped real-engine gate, or
disabled boundary.

## Next allowed slice

The next staged commit is `B5-W3 — quantitative composition`. It must bind
`declarations/w3-w4-quantitative-composition-repair.json` before applying the
accepted W4 budgets to W2's `C-R01` through `C-R24` observations. It may
evaluate every preregistered sample, derive the repaired `C-R12` window, and
issue a new composed quantitative result. It may not alter W1/W2 bytes,
candidate series, raw observations, inherited hard ceilings, or failed-rule
history; fit a threshold from the candidate; warp or reset edge time; skip a
required residual; edit a result in place; or promote a family member.
