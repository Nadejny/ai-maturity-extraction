# Opus 4.7 Annotator Agent — Task Specification

You are Claude Opus 4.7 acting as an inference model in the AI maturity extraction
pipeline. The project already has inference outputs from 6 local LLMs (qwen3_8b,
qwen3_14b, qwen3_32b, llama3.1_8b, gemma4_e4b, mistral_7b) on 769 articles. Your
job is to produce a comparable set of predictions using the **same prompt contract,
same output schema**, so your results can sit next to theirs in the leaderboard and
be compared directly.

## What you are processing

**Batch 1:** 80 articles, pre-selected and listed in
`ParsingLinks/src/artifacts/inference_runs/opus47_160/doc_ids_batch1.txt`
(one doc_id per line, e.g. `DOC000492`).

**(Later run)** Batch 2 is in `doc_ids_batch2.txt` — do not touch it now.

For each doc_id in batch1 you:
1. Look up the article text.
2. Extract AI-maturity signals per schema below.
3. Append a JSON row to `predictions.jsonl` in exactly the schema the 6 local LLMs use.

## Article lookup

The dataset manifest is
`ParsingLinks/src/artifacts/data/dataset_base.csv`
with columns including `doc_id`, `url_canonical`, `company`, `industry`, `year`,
`title`, `text_path`, `word_count`, `text_len`.

`text_path` is a relative path from project root (e.g.
`merged/texts/17c4cd14570d9f6c2f55f2c4931d45b1d0baa8db.txt`). Resolve against
`<project_root>/ParsingLinks/out/final/` if the relative path doesn't exist at
project root (legacy path convention used by the scraping pipeline).

Alternatively: read `dataset_base.jsonl` — same rows, but includes the full `text`
field inline. Easiest way is to load rows from that file and filter by doc_id.

## Output file

Append each prediction as one JSON object per line to:
`ParsingLinks/src/artifacts/inference_runs/opus47_160/opus_4_7/predictions.jsonl`

The file already exists and is empty. Append; never rewrite what's already there.

## Resume logic

Before processing doc_id X:
1. Read existing `predictions.jsonl`, collect all doc_ids already present.
2. Skip doc_ids that are already in the file.

If the run gets interrupted and restarted, this lets you resume without duplicates.

## Prompt contract (the same one used for local LLMs)

Produce exactly one JSON object per article with this structure:

```json
{
  "ai_use_cases":        {"status": "present|absent|uncertain", "items": [...]},
  "adoption_patterns":   {"status": "...", "items": [...]},
  "ai_stack":            {"status": "...", "items": [...]},
  "kpi_signals":         {"status": "...", "items": [...]},
  "budget_signals":      {"status": "...", "items": [...]},
  "org_change_signals":  {"status": "...", "items": [...]},
  "risk_signals":        {"status": "...", "items": [...]},
  "roadmap_signals":     {"status": "...", "items": [...]},
  "deployment_scope":    {"status": "...", "value": "..."},
  "maturity_level":      0|1|2|3|4,
  "maturity_rationale":  "1-2 sentences explaining WHY this level, grounded in article facts",
  "confidence":          0.0..1.0,
  "evidence_spans":      [{"field": "...", "quote": "...", "start_char": null, "end_char": null}]
}
```

### Field rules (copied from the local-LLM prompt verbatim)

1. `status` must be one of: `present`, `absent`, `uncertain`.
   - `present`: article explicitly describes this signal.
   - `absent`: article clearly has NO evidence.
   - `uncertain`: ambiguous or only implied.
2. `items` must be a FLAT LIST OF SHORT STRINGS (2–6 words each), **max 5 items per field**.
   CORRECT: `["code review automation", "fraud detection"]`
   WRONG:   `[{"name": "code review", "description": "..."}]`
   No dicts/objects inside items.
3. `deployment_scope.value`: describe the ACTUAL scope from the article in your own words
   (e.g., `"one product team"`, `"Gboard on Pixel 6"`, `"company-wide across 3 BUs"`).
   Do NOT copy from rubric.
4. If `status` is `absent`, `items` must be `[]` and `value` must be `""`.

### Maturity rubric

- **0** — No AI evidence. No explicit mention of AI/ML in a business process or product.
- **1** — Experiment / pilot. Isolated pilots, PoCs, experimentation without stable production adoption.
- **2** — Operational use. At least one AI use case in production with recurring usage in one function.
- **3** — Integrated multi-function use. AI across multiple business functions with governance and KPI tracking.
- **4** — Transformational enterprise-scale. AI embedded in core operations/products at scale with measurable business impact.

Rules:
- Level 2 requires EXPLICIT production deployment (not just research/experiment).
- Level 3 requires AI in MULTIPLE distinct business functions.
- Level 4 requires enterprise-wide scale with MEASURABLE business impact (revenue, cost, KPIs).
- When in doubt between two levels, choose the LOWER one.

### Confidence calibration

- 0.2–0.4: weak hints, mostly inferred
- 0.5–0.6: some evidence but incomplete
- 0.7–0.8: clear evidence for most fields
- 0.9–1.0: strong, explicit evidence throughout

Do NOT default to 0.95. Calibrate to actual evidence strength.

### Evidence spans

For EVERY field where `status="present"`, include at least one entry in `evidence_spans`:

```json
{"field": "<field_name>", "quote": "<short verbatim quote from text, max 100 chars>",
 "start_char": null, "end_char": null}
```

### Maturity rationale

Write 1–2 sentences explaining WHY you chose this maturity level, referencing
concrete facts from the article. Do NOT copy the rubric definition.
Prefer contrastive phrasing: "Level 2 because … however, no evidence of … so not 3".

## Output row schema (full JSON line per article)

Each line in `predictions.jsonl` is ONE JSON object with these top-level keys:

```json
{
  "doc_id":        "DOC000XYZ",
  "model_alias":   "opus_4_7",
  "run_id":        "opus47_160",
  "fields_payload": { ... all 13 payload keys shown above ... },
  "confidence":    <same as payload.confidence>,
  "evidence_spans": [ ... same as payload.evidence_spans ... ],
  "raw_response":  "<your verbatim JSON string output>",
  "latency_ms":    0,
  "token_usage":   {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "status_snapshot": {
    "ai_use_cases":       "present|absent|uncertain",
    "adoption_patterns":  "...",
    "ai_stack":           "...",
    "kpi_signals":        "...",
    "budget_signals":     "...",
    "org_change_signals": "...",
    "risk_signals":       "...",
    "roadmap_signals":    "...",
    "deployment_scope":   "..."
  },
  "structured_valid": true,
  "error_tags":       [],
  "error_message":    "",
  "schema_errors":    [],
  "maturity_level":             <copy from payload.maturity_level>,
  "deployment_scope_status":    <copy from payload.deployment_scope.status>,
  "deployment_scope_value":     <copy from payload.deployment_scope.value>
}
```

Notes:
- `latency_ms` = 0 and `token_usage` = zeros are intentional — we're not timing you.
- `raw_response` should contain your full JSON payload (not including the outer wrapper).
- `structured_valid` = true if JSON parsed fine and all required keys are present.
- Append with `\n` at end of each line (standard JSONL).

## Per-doc workflow

For each doc_id in `doc_ids_batch1.txt`:

1. Check if doc_id already in `predictions.jsonl`. If yes, log "skip DOC_ID" and continue.
2. Look up article via `dataset_base.csv` or `dataset_base.jsonl` — get `text`, `company`, `industry`, `year`, `title`.
3. Think carefully: apply rubric strictly. Conservative over-generous.
4. Produce the JSON payload per schema.
5. Self-verify: all 9 signal fields present, `deployment_scope` has both status and value, `maturity_level` is 0–4 integer, `confidence` is 0–1 float, at least one evidence span for every "present" field.
6. Wrap into the full row schema (above) and append one line to `predictions.jsonl`.
7. Print one-line progress: `[N/80] DOC000XYZ -> mat=X, confidence=Y.YZ`.
8. Move to next.

## Working in batches

Work in sub-batches of 10. After every 10 docs:
- Print a progress line: `Completed N/80, M parse errors, avg latency N/A`.
- Commit-save the file (no special action needed — just ensure writes are flushed).

## At the end

After all 80 done, write `run_summary.json` at
`ParsingLinks/src/artifacts/inference_runs/opus47_160/opus_4_7/run_summary.json`:

```json
{
  "run_id": "opus47_160",
  "batch": 1,
  "batch_size": 80,
  "model_alias": "opus_4_7",
  "rows": 80,
  "structured_valid_rows": <count>,
  "structured_valid_rate": <fraction>,
  "parse_error_rows": <count>,
  "error_tag_counts": { ... },
  "maturity_distribution": {"0": N, "1": N, "2": N, "3": N, "4": N},
  "avg_confidence": <float>,
  "signals_present_rates": {
    "ai_use_cases": <fraction>, ...
  },
  "predictions_jsonl": "<absolute path>"
}
```

## Conventions and reminders

- **No preamble, no markdown fences in the extracted JSON.** The local LLMs were
  told "raw JSON only" and that's what got scored. Match that exactly.
- **Max 5 items per list field.** Don't over-extract.
- **Evidence quotes must be verbatim from the article text** (max ~100 chars each).
- **Apply the rubric conservatively.** If between 2 and 3, choose 2. If between 0 and 1, choose 0 unless there's an explicit pilot mention.
- **Do not invent fields or restructure.** The schema must match the local LLM output exactly so evaluation metrics work.
- **One line per doc, one pass, no retries** unless structured JSON parsing fails (then retry once; if it fails twice, log a parse_error row: same structure with empty payload, error_tags=["parse_error"], structured_valid=false).

## Expected runtime

~80 articles × 30–60s per article ≈ 40–90 minutes for batch 1. Work patiently; don't
parallelize; keep the log chatty so progress is observable.

When batch 1 is done, report:
- total time
- maturity distribution
- 3 most uncertain docs (by your confidence) with a sentence on why you struggled
- any parse errors with doc_ids

Then stop. Batch 2 is a separate run; do not start it.
