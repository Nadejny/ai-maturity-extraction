# Prompt Contract v1

Extraction must return exactly one JSON object with this structure:

- list fields: `status` + `items`
  - `ai_use_cases`
  - `adoption_patterns`
  - `ai_stack`
  - `kpi_signals`
  - `budget_signals`
  - `org_change_signals`
  - `risk_signals`
  - `roadmap_signals`
- scalar field: `status` + `value`
  - `deployment_scope`
- scalar values:
  - `maturity_level` (integer 0..4)
  - `maturity_rationale` (string)
  - `confidence` (float 0..1)
  - `evidence_spans` (array of objects)

Each field status must be one of:
- `present`
- `absent`
- `uncertain`

If status is `absent`, the corresponding `items`/`value` should be empty.

`evidence_spans` item shape:
- `field`: one of signal fields or `maturity_rationale`
- `quote`: short supporting text span
- `start_char`: integer or null
- `end_char`: integer or null
