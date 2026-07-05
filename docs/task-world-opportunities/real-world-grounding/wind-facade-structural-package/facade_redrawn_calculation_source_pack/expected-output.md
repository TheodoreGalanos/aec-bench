# ABOUTME: Expected response shape for the facade redrawn calculation source-pack seed.
# ABOUTME: Defines the memo, annotation, and table content a future verifier should require.

# Expected Output Shape

This is a docs-only seed skeleton for fixture research. It is not an issued facade engineering report and should not be presented as one.

Expected solver output should include:

- An annotated elevation that references `BR-B01`, `BR-E01`, and `BR-C01` from `elevation-redrawn.svg`.
- A geometry extraction table that traces drawing bounds, zone extents, opening extents, and support coordinates to `geometry-oracle.csv`.
- A pressure-zone mapping table that joins `support-schedule.csv` to `pressure-schedule.csv`.
- An anchor check table that traces selected anchor rows, embedment, edge distance, spacing, tension demand, shear demand, and combined utilization to `anchor-check-oracle.csv`.
- A calculation table that reproduces `calculation-oracle.csv` within the tolerance in `verification-rules.yaml`.
- A governing-component memo identifying `BR-C01` as the controlling row, with anchor combined utilization `0.870`.
- A source-pack trace that cites task-owned capacity rows from `capacity-excerpts.yaml`, not live vendor data.
- A verification-case note explaining that the baseline case passes and the negative cases in `verification-cases.yaml` are expected to fail for localized reasons.
- A variant-boundary note explaining that `variant-matrix.yaml` defines future fixture-generation targets and should not be solved unless a variant is selected.
- A variant-overlay note explaining that `variant-source-overlays.yaml` gives row-level research overlays for future fixture generation, not expanded runtime fixtures or issued project reports.
- An expanded-variant-source note explaining that `variants/variant-source-files.yaml` lists docs-only expanded SVG/CSV sources for future verifier work, not executable benchmark instances.
- A verifier-implementation note explaining that `verifier-implementation-brief.md` is a docs-only future implementation contract, not runtime code.

Minimum memo content:

1. State the fixture is task-owned and uses embedded excerpts.
2. Explain the tributary area calculation as `0.60 m * 1.50 m = 0.900 m2`.
3. State that `BR-B01`, `BR-E01`, and `BR-C01` coordinates fall inside the `ZB`, `ZE`, and `ZC` geometry extents respectively.
4. State that each selected anchor row satisfies the embedded minimum embedment, edge-distance, and spacing limits.
5. Explain wind load as `abs(pressure_kPa) * tributary_area_m2`.
6. Explain dead load as `dead_load_kPa * tributary_area_m2`.
7. Explain anchor combined utilization as the square-root sum of squared tension and shear ratios.
8. Report each representative support row as pass/fail.
9. Identify the governing row and governing component.
10. Keep the current baseline separate from future variants in `variant-matrix.yaml`.
11. Treat `variant-source-overlays.yaml` as fixture-generation input only unless a variant is explicitly selected.
12. Treat `variants/variant-source-files.yaml` as docs-only expanded research sources, not runtime fixtures.
13. Treat `verifier-implementation-brief.md` as acceptance guidance for future executable verifier work, not evidence that the verifier exists.
14. Avoid claiming the seed pack is an issued report, a public returned calculation, or a completed benchmark fixture.
