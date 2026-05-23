# Feasibility Criteria for Parameterisable Tasks

A task is **parameterisable** when it can be turned into a reusable generation
template -- a `compute()` function that accepts typed inputs, runs a closed-form
calculation, and returns numeric outputs. The `/create-template` skill builds
these templates automatically.

Five criteria must ALL pass. If any single criterion fails, the task requires
manual authoring instead.

---

## 1. Closed-form computation

The calculation uses explicit formulae and/or table lookups. No iteration, no
finite-element methods, no optimisation solvers.

**PASS examples:**

- **Terzaghi bearing capacity** -- single formula: `q_ult = c * Nc + q * Nq + 0.5 * gamma * B * Ngamma`
- **Voltage drop** -- Ohm's law combined with cable impedance table lookup per AS3008
- **Steel beam capacity** -- direct application of AS4100 Section 5 moment capacity formula

**FAIL examples:**

- **FEM pile analysis** -- requires an iterative finite-element solver to converge on deflections
- **Pipe network analysis** -- Hardy-Cross iterative balancing until flow residuals converge
- **Non-linear buckling** -- requires incremental load stepping with equilibrium iterations

---

## 2. Deterministic

Given the same inputs, the calculation always produces the same outputs. No
random sampling, no stochastic processes, no user-judgment steps.

**PASS examples:**

- **Cable sizing** -- table lookup plus formula, fully determined by inputs
- **Slope stability factor of safety** -- Bishop or Fellenius method with fixed geometry and soil params
- **Heat load calculation** -- CIBSE/ASHRAE steady-state formula with fixed coefficients

**FAIL examples:**

- **Monte Carlo risk assessment** -- outputs vary with random seed
- **Stochastic structural analysis** -- probabilistic load combinations produce distributions
- **Design optimisation with random restarts** -- different runs yield different optima

---

## 3. Parameterisable inputs

Every input to the calculation is either numeric (`float`, `int`) or categorical
(a fixed set of string enum values). No freeform text, no images, no document
parsing.

**PASS examples:**

- **Soil properties** -- cohesion (kPa), friction angle (degrees), unit weight (kN/m3) -- all numeric
- **Installation method** -- categorical enum: `["buried", "in-tray", "in-conduit"]`
- **Concrete grade** -- categorical enum: `["N20", "N25", "N32", "N40"]`

**FAIL examples:**

- **Freeform specification text** -- cannot enumerate all possible spec paragraphs
- **Drawing images** -- agent must interpret a CAD drawing or scanned PDF
- **Geotechnical borehole logs** -- semi-structured tabular data with annotations

---

## 4. Numeric outputs

Every output is a number (float or int) that can be compared against a reference
value with a tolerance. No prose, no pass/fail judgments, no design narratives.

**PASS examples:**

- **Factor of safety** -- `float`, compared with tolerance (e.g. +/- 0.05)
- **Conductor cross-section area** -- `float` in mm2, exact match from standard sizes
- **Voltage drop percentage** -- `float`, compared with tolerance (e.g. +/- 0.1%)

**FAIL examples:**

- **"Compliant / non-compliant" prose** -- requires semantic comparison, not numeric
- **Design review findings** -- free-text narrative about deficiencies
- **Error description strings** -- cannot be scored with numeric tolerances

---

## 5. Single compute() call

The entire calculation fits inside one pure function. No iteration loops waiting
for convergence, no multi-stage design sequences where later stages depend on
intermediate human decisions.

**PASS examples:**

- **Cable sizing** -- inputs go in, cross-section and voltage drop come out, one call
- **Bearing capacity** -- inputs (soil params, footing geometry) produce q_ult in one call
- **Fire sprinkler flow** -- Hazen-Williams formula, single pass from inputs to flow rate and pressure

**FAIL examples:**

- **Iterative convergence** -- loop until residual falls below tolerance (e.g. Hardy-Cross)
- **Multi-stage design optimisation** -- size member, check deflection, resize, re-check
- **Sequential dependent calculations** -- foundation design that feeds into superstructure design

---

## Decision Rule

| All 5 pass? | Path |
|-------------|------|
| **Yes** | Task is **parameterisable**. Hand the seed to `/create-template` to generate `engine.py`, `params.toml`, and `instruction.md`. |
| **No** | Task needs **manual authoring**. See `manual-task-guidance.md` for the required file structure. |

Record the assessment in the seed file's `feasibility` block so downstream
tooling can route automatically:

```json
"feasibility": {
  "parameterisable": false,
  "criteria": {
    "closed_form": true,
    "deterministic": true,
    "parameterisable_inputs": false,
    "numeric_outputs": true,
    "single_compute": true
  },
  "notes": "Task requires parsing a geotechnical borehole log PDF -- inputs are not parameterisable."
}
```
