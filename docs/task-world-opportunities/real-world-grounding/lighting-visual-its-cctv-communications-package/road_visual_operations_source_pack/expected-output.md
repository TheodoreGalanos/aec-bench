# ABOUTME: Expected response shape for the SSC-13 road visual operations synthetic seed.
# ABOUTME: Defines the memo and table content a future verifier should require.

# Expected Output Shape

This is a docs-only runnable-synthetic seed for fixture research. It is not an issued road-lighting, ITS, CCTV, communications, or traffic-control design report.

Expected solver output should include:

- A source-boundary statement saying the pack is task-owned and synthetic.
- A scene summary naming `RD-SSC13-001`, `NIGHT-INCIDENT-01`, `CAB-01`, `VMS-01`, `SW-01`, and `FIB-01`.
- A lighting summary table that reproduces:
  - average illuminance `18.875 lux`;
  - minimum illuminance `16.800 lux`;
  - min/average uniformity `0.890`;
  - pass status against the task-owned thresholds.
- A CCTV table that reproduces:
  - `CCTV-01` target width `24.0 m`, `80.0 ppm`, `0.99792 TB`;
  - `CCTV-02` target width `32.0 m`, `60.0 ppm`, `0.99792 TB`;
  - total storage `1.99584 TB`.
- A network and power table that reproduces:
  - total network load `16.700 Mbps`;
  - PoE load `44.000 W` and `76.000 W` headroom;
  - fibre loss `2.347 dB` and `12.653 dB` margin against a `15.0 dB` budget;
  - UPS energy `1.271 kWh`.
- A VMS policy statement naming `MSG-POL-01` and the two allowed messages.
- A handoff trace naming the relevant files and preserving values from `handoff-ledger.yaml`.
- A visual operations memo that says the baseline task-owned source pack passes all current docs-only checks.
- A limitation statement that the pack is not an accepted project, full standards-compliance proof, executable verifier, generated benchmark instance, or benchmark-ready fixture.

Minimum memo content:

1. State that external AGi32, DIALux, MUTCD, Axis/JVSG, ARC-IT, and NTCIP routes shape the workflow only.
2. State that numeric grading uses the task-owned source pack.
3. Explain average/minimum lighting values from the eight grid rows.
4. Explain CCTV PPM as horizontal pixels divided by target width.
5. Explain CCTV storage as bitrate converted over 14 days with 1.10 overhead.
6. Explain network load as the sum of device schedule loads.
7. Explain PoE load as the sum of PoE-powered devices only.
8. Explain fibre loss as cable loss plus connector, splice, and reserve losses.
9. Explain UPS energy as selected load times autonomy divided by efficiency.
10. Preserve all object IDs used in the source files.
11. Avoid claiming authority approval, software export validity, or benchmark readiness.
