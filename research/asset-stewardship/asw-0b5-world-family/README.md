# ABOUTME: Defines the B5-W0 research boundary for canonical declarations, independent readers, and receipt identities.
# ABOUTME: Prevents this code and its layouts from becoming hydraulics, runtime, package, or production contracts.

# ASW-0B5 world-family research implementation

This directory contains only `B5-W0 — research boundary and canonical
declarations` for `AU-NSW-LH-SYN-SPS-v1`. It turns the accepted B4 authority
chain into the smallest executable byte and lineage boundary needed before the
real generator can be implemented.

It is not a generated world, accepted family member, hydraulic model,
certifier, SWMM wrapper, package, manifest, runtime adapter, agent tool,
scenario, or V3 decision. Nothing under this directory may be imported by
`src/aec_bench`, and production behavior must continue to work with
`research/` physically absent.

## Exact scope

B5-W0 contains:

- one canonical machine-readable W1 declaration with all 49 stable
  identities: 46 scalar records and three fixed composites;
- one generator-side canonical JSON, identity, path, source, and dependency
  reader;
- one separately implemented certifier-side reader for the same
  specification;
- one third, lineage-only implementation of the W5 common receipt envelope,
  receipt identity, and structural DAG rules; and
- focused unit, integration, and separate-process end-to-end tests.

B5-W0 does not:

- run or build SWMM;
- render a W2 request, curve, engine input, case, or trajectory;
- implement W1 hydraulic equations or W3 independent calculations;
- implement W4 tolerances, probes, or sensitivity decisions;
- write a generated receipt, family result, package, manifest, or V3 record;
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

The generator and certifier packages deliberately share no project import,
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

The lineage package is separate from both readers. It cannot call either
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
PYTHONPATH=research/asset-stewardship/asw-0b5-world-family/src:research/asset-stewardship/asw-0b5-world-family/tests \
  uv run pytest \
  research/asset-stewardship/asw-0b5-world-family/tests -q
```

Static checks are similarly scoped:

```sh
uv run ruff check \
  research/asset-stewardship/asw-0b5-world-family/src \
  research/asset-stewardship/asw-0b5-world-family/tests

uv run mypy --strict --explicit-package-bases \
  research/asset-stewardship/asw-0b5-world-family/src
```

The tests use real files and real subprocesses. They contain no mock engine,
fabricated SWMM result, fake certification pass, or disabled boundary.

## Next allowed slice

Only after this slice is reviewed and merged may `B5-W1` add the real W2
generator. That later PR must start from these declared bytes and independent
boundaries, remain research-side, use test-first development, and run the
exact pinned SWMM engine. It may not weaken a B5-W0 rejection to make a case
execute.
