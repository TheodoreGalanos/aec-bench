# ABOUTME: Defines the isolated ASW-0B3 real-engine spike and its non-authoritative research boundary.
# ABOUTME: Keeps disposable diagnostic inputs and vendor build outputs separate from later world and runtime contracts.

# ASW-0B3 SWMM engine spike

This directory is an isolated, non-authoritative research implementation for
`ASW-0B3 — Engine roles and research spike`. It answers one question: can the
exact pinned SWMM engine execute and export the hydraulic semantics needed to
make an explicit software-role decision for `AU-NSW-LH-SYN-SPS-v1`?

It is not a production package, generator family, certifier, runtime adapter,
agent tool, scenario, or promoted asset definition. Nothing under this
directory may be imported by `src/aec_bench`. Its paths, Python names, fixture
shape, diagnostic constants, and result layout are research conveniences, not
contracts.

## Authority boundary

The spike:

- starts from the accepted B1 topology of Pump A and Pump B;
- runs one Pump-A-duty probe and one separately rendered Pump-B-duty label
  probe;
- never runs the two pumps together;
- contains no duty-transfer event, timing, trigger, or control policy;
- contains no obstruction, degradation, failure, intervention, observation,
  maintenance, obligation, authority, handover, or scoring semantics;
- treats every numerical fixture value and numerical comparison as disposable
  engine-diagnostic material that ASW-0B4 must neither inherit nor cite as a
  selected world value;
- uses real SWMM execution and the official output library only; and
- performs separately implemented label-symmetry, finite-value, period-count,
  standby-zero-flow, and cylindrical-storage identity checks.

The research report with external SHA-256
`861229eb4237c7c476fcd88d68f29d0c416446803897da3487bdf2fbda70f8e8`
provided candidate discovery and risk prompts. No supplied prototype byte,
configuration, schema, generated input, or result was copied or treated as
authority. This implementation was independently specified against the
accepted B1/B2 authorities and the official pinned SWMM source.

## Pinned candidate

| Item | Pin |
| --- | --- |
| Source | `https://github.com/USEPA/Stormwater-Management-Model.git` |
| Version | `5.2.4` |
| Commit | `7952ca837988b1c32f791812eccc9fd64547e093` |
| Source rights | US EPA public-domain source; verify the official repository notices with the recorded commit |

The pinned source needs three CMake portability repairs on the local
single-config Apple toolchain: an OpenMP generator expression uses a literal
variable name, the upstream output test is registered at a configuration
subdirectory different from its actual target path, and current CMake needs an
explicit guarded declaration that this pinned source uses the legacy
`FindBoost` policy. The tracked patch changes build/test wiring only. It does
not alter solver or output calculations. Its hash and application diff are
recorded in each build receipt.

## Tracked and excluded surfaces

Tracked:

- this boundary statement;
- the independently authored research source;
- focused tests;
- the disposable spike-only fixture declaration; and
- the exact build-wiring patch.

Excluded from Git:

- cloned vendor source and `.git` data;
- build and install trees;
- binaries and shared libraries;
- generated SWMM `.inp`, `.out`, and `.rpt` files;
- terminal logs, caches, and local receipts; and
- discarded experiments.

The stage-level engine-role decision and compact verification record live one
directory above. They contain semantic identities and hashes, not raw solver
exports or filesystem contracts.

## Focused workflow

All commands are run from the repository root with the spike source on
`PYTHONPATH`. A new, absent temporary directory must be supplied for every
build or reproduction; the implementation never deletes or reuses a build or
run directory.

```sh
PYTHONPATH=research/asset-stewardship/asw-0b3-swmm-engine-spike/src \
  uv run pytest \
  research/asset-stewardship/asw-0b3-swmm-engine-spike/tests/test_specification.py \
  research/asset-stewardship/asw-0b3-swmm-engine-spike/tests/test_rendering.py \
  research/asset-stewardship/asw-0b3-swmm-engine-spike/tests/test_build_boundary.py \
  research/asset-stewardship/asw-0b3-swmm-engine-spike/tests/test_output_contract.py \
  research/asset-stewardship/asw-0b3-swmm-engine-spike/tests/test_verification.py -q
```

The real-engine build and replay commands are documented by the CLI help after
the focused unit boundary is green:

```sh
PYTHONPATH=research/asset-stewardship/asw-0b3-swmm-engine-spike/src \
  uv run python -m asw_b3_swmm --help
```
