# Seed File Schema Reference

The seed file is a JSON document that captures a benchmark task idea in enough
detail for downstream tooling (`/create-template` for parameterisable tasks, or
manual authoring for everything else). Two origin styles exist: **expert** seeds
(rich, structured inputs/outputs) and **ngnbench** seeds (flat string lists
imported from legacy inventories). Both are valid.

---

## Top-Level Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `status` | `string` | **yes** | Lifecycle state. Always `"proposed"` for new seeds. |
| `seed_origin` | `string` | **yes** | How the seed was created. `"expert"` for interview-authored, `"ngnbench"` for legacy import. |
| `created_by` | `string` | no | Author handle (e.g. `"theo"`). Recommended for expert seeds. |
| `source` | `object` | **yes** | The task definition payload. See below. |
| `feasibility` | `object` | no | Parameterisability assessment. See below. |

---

## `source` Object

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `discipline` | `enum` | One of: `civil`, `electrical`, `ground`, `mechanical`, `structural`. |
| `task_id` | `string` | Kebab-case unique identifier (e.g. `"cable-sizing-long-runs"`). |
| `task_name` | `string` | Human-readable title (e.g. `"Cable Sizing for Long Runs"`). |
| `description` | `string` | One or two sentences explaining what the task calculates or evaluates. |
| `inputs` | `array` | Task inputs. See Input Formats below. |
| `outputs` | `array` | Task outputs. See Output Formats below. |
| `standards` | `array[string]` | Relevant codes and standards (e.g. `["AS/NZS 3008.1.1"]`). |
| `complexity` | `enum` | One of: `low`, `medium`, `high`. |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `reference_details` | `array[string]` | Specific clause/table references within standards. |
| `worked_examples` | `array[object]` | Concrete input/output pairs. See Worked Examples below. |
| `edge_cases` | `array[string]` | Known boundary conditions or tricky scenarios. |
| `community` | `string` | Legacy sub-community tag (e.g. `"civil_energy"`). Mainly for ngnbench seeds. |
| `category_id` | `string` | Kebab-case category (e.g. `"access-roads"`). Mainly for ngnbench seeds. |
| `category_name` | `string` | Human-readable category (e.g. `"Access Road Design"`). Mainly for ngnbench seeds. |
| `keyword_hits` | `array[string]` | Keywords that flagged this task during inventory mining. Mainly for ngnbench seeds. |
| `source_file` | `string` | Path to the inventory file this seed was extracted from. Mainly for ngnbench seeds. |
| `suggested_relative_path` | `string` | Suggested location under `tasks/` (e.g. `"civil/access-roads/gravel-road-thickness"`). |

---

## Input and Output Formats

Inputs and outputs support two formats. All items in a single array **must** use
the same format -- do not mix flat strings with structured objects.

### Flat String (old-style, ngnbench seeds)

Each item is a plain string describing the parameter and its unit in
parentheses:

```json
"inputs": [
  "Subgrade CBR (%)",
  "Design traffic (ESAs)",
  "Gravel material properties"
]
```

### Structured Object (enhanced, expert seeds)

Each item is an object with explicit metadata:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `string` | **yes** | Parameter name. |
| `type` | `string` | **yes** | One of: `float`, `int`, `categorical`. |
| `unit` | `string` | conditional | Required for `float` and `int` types. Physical unit (e.g. `"m"`, `"A"`, `"mm2"`). |
| `values` | `array[string]` | conditional | Required for `categorical` type. The allowed enum values. |

```json
"inputs": [
  {"name": "Cable length", "type": "float", "unit": "m"},
  {"name": "Load current", "type": "float", "unit": "A"},
  {"name": "Installation method", "type": "categorical", "values": ["buried", "in-tray", "in-conduit"]}
]
```

---

## Worked Examples

Each worked example is an object with three fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | `string` | **yes** | Brief prose describing the scenario. |
| `inputs` | `object` | **yes** | Mapping of `param_name` (snake_case) to concrete value. |
| `outputs` | `object` | **yes** | Mapping of `output_name` (snake_case) to concrete value. |

```json
"worked_examples": [
  {
    "description": "200m buried 3-phase cable at 100A",
    "inputs": {
      "cable_length": 200,
      "load_current": 100,
      "supply_voltage": 415,
      "installation_method": "buried",
      "grouping_factor": 3
    },
    "outputs": {
      "conductor_cross_section": 95,
      "voltage_drop": 3.2
    }
  }
]
```

---

## Feasibility Object

The feasibility block records whether a task can be turned into a parameterised
template. It is optional but strongly recommended for expert seeds.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `parameterisable` | `bool` | **yes** | `true` if all 5 criteria pass. |
| `criteria` | `object` | **yes** | The 5 boolean criteria. See `feasibility-criteria.md`. |
| `notes` | `string` | **yes** | Free-text explanation. Empty string if nothing to add. |

### `criteria` Sub-Object

| Field | Type | Description |
|-------|------|-------------|
| `closed_form` | `bool` | Computation uses a closed-form formula (no iteration/FEM). |
| `deterministic` | `bool` | Same inputs always produce the same outputs. |
| `parameterisable_inputs` | `bool` | All inputs are numeric or categorical. |
| `numeric_outputs` | `bool` | All outputs are numbers comparable with tolerances. |
| `single_compute` | `bool` | Entire calculation fits in one pure function call. |

---

## Complete Expert Seed Example

```json
{
  "status": "proposed",
  "seed_origin": "expert",
  "created_by": "theo",
  "source": {
    "discipline": "electrical",
    "task_id": "cable-sizing-long-runs",
    "task_name": "Cable Sizing for Long Runs",
    "description": "Calculate minimum conductor cross-section and voltage drop for cable runs exceeding 100m per AS3008",
    "inputs": [
      {"name": "Cable length", "type": "float", "unit": "m"},
      {"name": "Load current", "type": "float", "unit": "A"},
      {"name": "Supply voltage", "type": "float", "unit": "V"},
      {"name": "Installation method", "type": "categorical", "values": ["buried", "in-tray", "in-conduit"]},
      {"name": "Grouping factor", "type": "int", "unit": "cables"}
    ],
    "outputs": [
      {"name": "Conductor cross-section", "type": "float", "unit": "mm2"},
      {"name": "Voltage drop", "type": "float", "unit": "%"}
    ],
    "standards": ["AS/NZS 3008.1.1"],
    "reference_details": ["AS3008.1.1 Table 3 Column 4 -- current-carrying capacity for buried cables"],
    "complexity": "medium",
    "worked_examples": [
      {
        "description": "200m buried 3-phase cable at 100A",
        "inputs": {
          "cable_length": 200,
          "load_current": 100,
          "supply_voltage": 415,
          "installation_method": "buried",
          "grouping_factor": 3
        },
        "outputs": {
          "conductor_cross_section": 95,
          "voltage_drop": 3.2
        }
      }
    ],
    "edge_cases": ["Derating factors apply when more than 3 cables are grouped"]
  },
  "feasibility": {
    "parameterisable": true,
    "criteria": {
      "closed_form": true,
      "deterministic": true,
      "parameterisable_inputs": true,
      "numeric_outputs": true,
      "single_compute": true
    },
    "notes": ""
  }
}
```

## Complete ngnbench Seed Example

```json
{
  "status": "proposed",
  "seed_origin": "ngnbench",
  "source": {
    "discipline": "civil",
    "community": "civil_energy",
    "category_id": "access-roads",
    "category_name": "Access Road Design",
    "task_id": "gravel-road-thickness",
    "task_name": "Gravel Road Pavement Thickness",
    "description": "Calculate required pavement thickness for light-duty gravel access road",
    "complexity": "low",
    "standards": ["Austroads Guides"],
    "inputs": ["Subgrade CBR (%)", "Design traffic (ESAs)", "Gravel material properties"],
    "outputs": ["Required base course thickness (mm)", "Compaction standard", "Crossfall (%)"],
    "keyword_hits": ["calculate"],
    "source_file": "data/tasks/civil/civil_energy.json",
    "suggested_relative_path": "civil/access-roads/gravel-road-thickness"
  }
}
```
