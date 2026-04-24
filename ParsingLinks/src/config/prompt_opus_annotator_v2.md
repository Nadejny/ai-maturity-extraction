# Opus 4.7 Annotator Agent — Task Specification v2 (ceiling / prompt-engineered)

You are Claude Opus 4.7 acting as an inference model in the AI maturity extraction
pipeline, **batch 2 ceiling run**. This version is intentionally more prescriptive
than v1 — it adds few-shot discrimination, self-critique, and strict evidence
requirements so we can measure how much prompt engineering moves the needle beyond
the baseline (batch 1 was run with the same contract the 6 local LLMs used).

The schema, output format, and save protocol are **identical to v1**. Only the
extraction reasoning is tightened.

## What you are processing

**Batch 2:** 80 articles listed in
`ParsingLinks/src/artifacts/inference_runs/opus47_160/doc_ids_batch2.txt`
(non-overlapping with batch 1).

## Article lookup

Same as v1 — read `ParsingLinks/src/artifacts/data/dataset_base.jsonl`
(each line has `doc_id`, `text`, `company`, `industry`, `year`, `title`).

## Output file

Append each prediction as one JSON object per line to:
`ParsingLinks/src/artifacts/inference_runs/opus47_160/opus_4_7_v2/predictions.jsonl`

Create the `opus_4_7_v2/` subdirectory if it doesn't exist. **Do not overwrite
batch 1 results** in `opus_4_7/predictions.jsonl`.

## Resume logic

Before processing doc_id X: check existing `predictions.jsonl` in `opus_4_7_v2/`;
skip doc_ids already there.

## Output schema (identical to v1)

Each line in `predictions.jsonl` is ONE JSON object with these top-level keys,
matching the 6 local LLMs:

```json
{
  "doc_id": "...",
  "model_alias": "opus_4_7_v2",
  "run_id": "opus47_160_v2",
  "fields_payload": { ... 13 payload keys ... },
  "confidence": <float>,
  "evidence_spans": [...],
  "raw_response": "<your JSON verbatim>",
  "latency_ms": 0,
  "token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
  "status_snapshot": { ... 9 field statuses ... },
  "structured_valid": true,
  "error_tags": [],
  "error_message": "",
  "schema_errors": [],
  "maturity_level": <int 0-4>,
  "deployment_scope_status": "...",
  "deployment_scope_value": "..."
}
```

Payload structure (same as v1):

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
  "maturity_rationale":  "contrastive, 2-3 sentences",
  "confidence":          0.0..1.0,
  "evidence_spans":      [{"field": "...", "quote": "...", "start_char": null, "end_char": null}]
}
```

## v2 additions — read carefully

### 1. Maturity discrimination checklist (the main fix)

v1 was too permissive on mat=0 vs mat=2 boundary. Apply this flowchart strictly:

**mat=0 — No AI evidence:**
The article does not describe any AI/ML system being used. Example: an article
about company values, a generic product announcement with no ML content, a pure
infrastructure/DevOps post without ML.

**mat=1 — Experiment / pilot / research (NOT YET PRODUCTION):**
Use this when:
- The article is an arxiv abstract, research paper, or conference talk describing
  a proposed or benchmark-evaluated method, with no explicit production claim.
- The article describes a pilot, PoC, hackathon, or internal experiment.
- Phrases like "we propose", "we evaluated on benchmark X", "in a controlled study",
  "pilot program", "prototype", "PoC" — without "deployed to production", "serving
  X customers", "in production for N months".

**mat=2 — Production in ONE function:**
Use ONLY if the article has EXPLICIT production-deployment evidence:
- "deployed in production", "serving N requests/day", "launched to users",
  "currently handling X transactions", "live since date Y"
- AND evidence the AI is scoped to a **single** business function (e.g., search
  only, or fraud detection only, or recommendations only).

**mat=3 — Multi-function with governance:**
Use ONLY if BOTH conditions are met:
- **Condition A:** Two or more DISTINCT business functions use AI, named
  separately (e.g., "search AND ads ranking AND recommendations", or "fraud
  detection AND customer support AND code review"). NOT just two features of
  the same function.
- **Condition B:** EITHER governance structure (model review process, ML platform,
  central team) OR KPI tracking (named business metrics like CTR, conversion,
  cost saved) is mentioned.

If Condition B is missing but Condition A is met, use mat=2.

**mat=4 — Enterprise-scale transformation:**
Use ONLY if:
- AI is described as embedded across entire company operations (not just multiple
  functions),
- AND measurable company-level business impact is reported (e.g., "revenue grew
  N%", "cost reduced by $X million", ">50% of employees use AI daily", "90%
  adoption across organization").

### 2. Research paper test (v1 missed these)

Before labeling anything mat=2, ask: **is this article about a deployed product,
or about a research methodology?**

- Title contains "we propose", "toward", "a survey of", "evaluating", "analysis of"
  → likely research → mat=1 unless production claim is explicit
- arxiv/preprint → mat=1 unless article explicitly says "deployed in production"
- Benchmark-only results without production traffic → mat=1

This is the SAME standard the 6 local LLMs used but with explicit checklist.

### 3. Self-critique pass (do this for every doc)

After you've drafted the JSON:

1. For every field where `status="present"`, find the verbatim quote in the article.
   - If you cannot locate exact text supporting this field, **downgrade to `uncertain`
     with empty items/value**.
2. For `maturity_level`, re-read your rationale:
   - Does it cite SPECIFIC facts (not paraphrase)? If not, rewrite.
   - Does it name the ADJACENT level you considered and why you rejected it? If not, add it.
3. For `items` in each list field:
   - Are all items SPECIFIC (e.g., "fraud detection for credit card transactions"
     vs generic "fraud detection")? Prefer specific where text supports it.
   - Are any items just generic categories like "AI", "ML", "recommendations",
     "analytics"? Remove them — too vague.

### 4. Items specificity rules

- `ai_use_cases` items: name the actual use case with context, not category.
  GOOD: `["real-time ETA prediction", "order-volume forecasting"]`
  WEAK: `["prediction", "forecasting"]`
- `ai_stack` items: specific tools/models/frameworks named in article.
  GOOD: `["GPT-4", "LangChain", "Pinecone"]`
  WEAK: `["LLMs", "vector database"]` (only if no specific name given)
- `kpi_signals` items: concrete metrics with values when stated.
  GOOD: `["CTR +12%", "conversion rate 8.3%", "latency p99 450ms"]`
  WEAK: `["engagement"]`

### 5. Evidence spans — stricter

For every field where `status="present"`:
- Must have at least ONE evidence_span.
- Quote must be ≤100 chars.
- Quote must appear VERBATIM in the article text (copy-paste, don't paraphrase).

If you can't find a verbatim quote, **status should be `uncertain`**, not `present`.

### 6. Contrastive rationale (required)

`maturity_rationale` must follow this pattern:

> "[Level N because specific fact X from article.] [Considered level N±1 but rejected because specific reason Y.]"

Example for mat=2:

> "Level 2 because article explicitly states 'deployed to Gboard on Pixel 6, serving all users'. Considered level 3 but rejected because no evidence of AI in a second distinct business function beyond keyboard suggestions."

Example for mat=3:

> "Level 3 because AI explicitly deployed across search, ads ranking, and recommendations (three distinct functions), with central ML platform and documented A/B testing framework. Considered level 4 but rejected because article doesn't report enterprise-wide adoption metrics or company-level financial impact."

## Per-doc workflow

For each doc_id in `doc_ids_batch2.txt`:

1. Check skip: is it already in `opus_4_7_v2/predictions.jsonl`?
2. Load article from `dataset_base.jsonl` (text + metadata).
3. **First pass** — draft the JSON payload applying all rules.
4. **Self-critique pass** — verify each present field has verbatim quote; check maturity rationale is contrastive; check items are specific.
5. **Refinement pass** — downgrade fields without verbatim support; rewrite rationale if not contrastive.
6. Produce final JSON.
7. Wrap in full row schema and append to `predictions.jsonl`.
8. Print progress: `[N/80] DOC000XYZ -> mat=X, confidence=Y.YZ`.
9. Move to next.

## Batching

After every 10 docs, print summary line with running maturity distribution.

## Final summary

After all 80 done, write `opus_4_7_v2/run_summary.json`:

```json
{
  "run_id": "opus47_160_v2",
  "batch": 2,
  "prompt_version": "ceiling_v2",
  "batch_size": 80,
  "model_alias": "opus_4_7_v2",
  "rows": 80,
  "structured_valid_rows": <count>,
  "parse_error_rows": <count>,
  "maturity_distribution": {"0": N, "1": N, "2": N, "3": N, "4": N},
  "avg_confidence": <float>,
  "signals_present_rates": { ... per field ... },
  "comparison_vs_batch1": {
    "mat3_count_delta": "<N in v2 minus N in v1 on same corpus structure>",
    "avg_confidence_delta": "<v2 avg minus v1 avg>"
  }
}
```

Compute `comparison_vs_batch1` by reading
`ParsingLinks/src/artifacts/inference_runs/opus47_160/opus_4_7/run_summary.json`.

## Conventions

- **Raw JSON only** in the extracted payload. No markdown fences.
- **One line per doc**, append mode only.
- **Prompt caching**: the static prefix (this file + rules) is cacheable; the
  dynamic part (article text) changes each call.
- **No preamble in output JSON** — just `{`.

## Expected outcome vs batch 1

Batch 1 clustered at mat=2 (89%). If v2's ceiling prompt works, expect:
- More mat=0 detections (articles that don't describe AI at all)
- More mat=1 detections (research papers, arxiv abstracts)
- Slightly more mat=3 (stronger multi-function discrimination)
- Fewer false mat=2 from research articles
- More specific `items` lists
- Higher fraction of `uncertain` where v1 said `present`

Delta between batches = **measurable prompt-engineering effect on Opus**. Report
those differences at the end.

## When done

Stop after 80. Report:
- maturity distribution (vs batch 1)
- 3 docs where you downgraded present → uncertain during self-critique (with why)
- 3 docs where the ceiling prompt changed your label from what v1 would likely have produced
- avg confidence (vs batch 1's 0.73)

That's the ceiling-prompt payoff data.
