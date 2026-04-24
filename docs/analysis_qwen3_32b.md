# Qwen3 32B Analysis — 250 Documents

Run: `qwen32_800` | Model: `qwen3:32b` | Date: 2026-04-18
Compared against: `qwen3:8b` from `4x769` run (same prompt, same 250 docs)

---

## 1. Overview

| Metric | qwen3_32b | qwen3_8b (same 250 docs) |
|--------|-----------|--------------------------|
| Documents | 250 | 250 (subset of 769) |
| Structured valid | 246 (98.4%) | ~245 (98%) |
| Parse errors | 4 (1.6%) | ~3-4 (est.) |
| Avg latency/doc | **79.1s** | 16.8s |
| Total time | **5.49 hrs** | ~1.17 hrs (est.) |
| Tokens/second | 10.3 | 36.4 |
| Prompt tokens | 906,163 | ~894K (est.) |
| Completion tokens | 202,805 | ~153K (est.) |

**32b is 4.7x slower** but produces higher quality output (see below).

---

## 2. Maturity distribution

| Maturity | qwen3_32b | qwen3_8b (same 250) | Delta |
|----------|-----------|----------------------|-------|
| 0 (no AI) | 133 (53%) | 138 (55%) | -5 |
| 1 (pilot) | 6 (2%) | 3 (1%) | +3 |
| 2 (production) | 61 (24%) | 86 (34%) | **-25** |
| 3 (multi-function) | 50 (20%) | 22 (9%) | **+28** |
| 4 (enterprise) | 0 (0%) | 1 (0.4%) | -1 |

**Key shift:** 32b moves 28 documents from maturity=2 to maturity=3.
It is better at identifying multi-function AI integration where 8b
only sees single-function production use.

Overall agreement: **199/250 (79.6%)** exact match.
Mean difference: +0.13 (32b slightly higher on average).
Disagreements >= 2 levels: only **6 documents**.

---

## 3. Confidence calibration

| Bucket | qwen3_32b | qwen3_8b (full 769) |
|--------|-----------|----------------------|
| 0.0 | 138 (55%) | 377 (49%) |
| 0.01-0.30 | 0 | 5 |
| 0.31-0.50 | 0 | 3 |
| 0.51-0.70 | 9 (4%) | 9 (1%) |
| 0.71-0.90 | 103 (41%) | 373 (49%) |
| 0.91-1.00 | 0 | 2 |
| **Average** | **0.36** | **0.39** |
| **Max** | 0.85 | 0.95 |

32b is more conservative: max confidence is 0.85 (never 0.95),
and the distribution is cleaner bimodal (0.0 for no-AI, 0.75-0.85
for detected AI, nothing in between).

---

## 4. Signal field extraction rates

| Field | qwen3_32b | qwen3_8b (769) | Difference |
|-------|-----------|----------------|------------|
| ai_use_cases | 127 (50.8%) | 437 (56.8%) | -6pp |
| adoption_patterns | **124 (49.6%)** | 304 (39.5%) | **+10pp** |
| ai_stack | 112 (44.8%) | 379 (49.3%) | -4pp |
| kpi_signals | **93 (37.2%)** | 211 (27.4%) | **+10pp** |
| budget_signals | **17 (6.8%)** | 23 (3.0%) | **+4pp** |
| org_change_signals | **59 (23.6%)** | 49 (6.4%) | **+17pp** |
| risk_signals | **88 (35.2%)** | 90 (11.7%) | **+24pp** |
| roadmap_signals | **109 (43.6%)** | 248 (32.2%) | **+11pp** |
| deployment_scope | 119 (47.6%) | 407 (52.9%) | -5pp |

**32b extracts substantially more signals** in secondary fields:
- `risk_signals`: 35.2% vs 11.7% (+24pp)
- `org_change_signals`: 23.6% vs 6.4% (+17pp)
- `kpi_signals`: 37.2% vs 27.4% (+10pp)
- `roadmap_signals`: 43.6% vs 32.2% (+11pp)

This means the 32b model reads deeper into articles and identifies
signals that the 8b model misses.

---

## 5. Evidence spans quality

| Metric | qwen3_32b | qwen3_8b (769) |
|--------|-----------|----------------|
| Docs with spans | 111 (44%) | 384 (50%) |
| Avg spans/doc (when present) | **8.0** | 4.7 |
| Median spans/doc | **7** | 4 |
| Max spans/doc | **27** | 26 |
| Empty despite present signals | 17 (6.8%) | 53 (6.9%) |

32b produces **70% more evidence spans per document** when it does
produce them (8.0 vs 4.7). The empty-despite-signals rate is
identical (~7%), meaning both models skip spans at the same rate,
but when 32b provides them it is much more thorough.

---

## 6. Items quality

| Metric | qwen3_32b | qwen3_8b (769) |
|--------|-----------|----------------|
| Total present fields | 729 | 1,738 |
| Avg items/present field | 2.8 | 3.1 |

32b is slightly more concise in items (2.8 vs 3.1 avg), consistent
with the "2-6 words, max 5 items" instruction being followed well.

---

## 7. Error analysis

### Parse errors (4/250 = 1.6%)

All 4 are repetition loops (same pattern as 8b):

| Doc | Size | Pattern |
|-----|------|---------|
| DOC000074 | 19KB | `{"ai_model_used": ..., "ai_response": {"ai_model_used": ...}}` |
| DOC000095 | 73KB | `{"ai_profiles": {"ai_profiles": ...}}` |
| DOC000125 | 37KB | `{"ai_model_used": "Not applicable", "analysis": {...}}` |
| DOC000240 | 61KB | `{"ai_insights": {"ai_insights": ...}}` |

Parse error rate is comparable: 32b = 1.6%, 8b = 1.4%.
This is a fundamental limitation of constrained JSON generation
in transformer models, not model-size dependent.

### Error tags

| Tag | qwen3_32b | qwen3_8b (769) |
|-----|-----------|----------------|
| parse_error | 4 | 11 |
| evidence_spans_empty_despite_signals | 17 | 53 |
| wrong_field_names_detected | 2 | 20 |
| evidence_spans_alias_used | 3 | 4 |
| maturity_rationale_empty | 1 | 0 |

32b has fewer `wrong_field_names_detected` (2 vs 20) -- better
adherence to the exact field names in the schema.

---

## 8. Maturity rationale quality

### qwen3_32b examples (selected):

**DOC000004 (maturity=2):**
> "The article describes a production AI use case (document
> summarization) deployed for Google Workspace business customers.
> However, it is limited to a single business function (document
> writing assistance) with no evidence of integration across multiple
> functions or enterprise-wide impact."

**DOC000205 (maturity=2):**
> "The article describes two production AI use cases (fraud
> investigation and report summarization) within the Integrity
> Analytics team, with clear deployment and measurable impact
> (e.g., 3-4 hours saved per report). However, there is no evidence
> of AI integration across multiple business functions or
> enterprise-wide governance."

**DOC000069 (maturity=3):**
> "Hermes is used across multiple business functions (food, instamart)
> with governance (audit logs, rbac), KPI tracking (93% accuracy,
> 20-25% improvement), and iterative improvements based on user
> feedback, indicating integration beyond a single use case."

### Comparison with qwen3_8b rationale style:

| Aspect | 32b | 8b |
|--------|-----|-----|
| References specific facts | yes (KPIs, team names, products) | sometimes |
| Explains why NOT higher level | **yes** ("However, no evidence of...") | rarely |
| Copies rubric text | never | occasionally |
| Length | 1-3 sentences | 1 sentence typically |

The 32b rationale is notably better: it explicitly explains why
a higher maturity level was not assigned, references specific
numbers and team names from the article, and never copies the
rubric definition.

---

## 9. Biggest disagreements with 8b

6 documents with >= 2 maturity levels difference:

| Doc | 32b | 8b | Pattern |
|-----|-----|-----|---------|
| DOC000052 | 0 | 2 | 32b more conservative |
| DOC000174 | 0 | 2 | 32b more conservative |
| DOC000096 | 3 | 0 | 8b missed AI signals |
| DOC000128 | 3 | 0 | 8b missed AI signals |
| DOC000139 | 3 | 0 | 8b missed AI signals |
| DOC000187 | 3 | 0 | 8b missed AI signals |

Note: All 4 cases where 32b=3 and 8b=0 have confidence=0.0 on both
sides, suggesting these are edge-case documents where both models
struggle, but 32b attempts extraction where 8b gives up entirely.

---

## 10. Cost-quality trade-off

| Metric | qwen3_8b | qwen3_32b | Ratio |
|--------|----------|-----------|-------|
| Latency/doc | 16.8s | 79.1s | **4.7x slower** |
| Time for 769 docs | 3.59 hrs | ~16.9 hrs (est.) | 4.7x |
| Tokens/second | 36.4 | 10.3 | 3.5x less |
| Parse errors | 1.4% | 1.6% | comparable |
| Maturity accuracy | good | **better** | qualitative |
| Signal fill rates | baseline | **+10-24pp on secondary fields** | significant |
| Evidence spans/doc | 4.7 avg | **8.0 avg** | 1.7x more |
| Rationale quality | basic | **detailed, contrastive** | significant |

**Verdict:** 32b is the better model for quality-critical extraction.
For a diploma where quality matters more than speed, 32b is the
right choice. The 4.7x slowdown is acceptable for a one-time
research run (~17 hours for 769 docs vs ~3.5 hours).

---

## 11. Key numbers for the diploma

- qwen3_32b processed **250 documents** in **5.49 hours**
- **98.4% structured valid** (246/250)
- Maturity distribution: 53% no-AI, 2% pilot, 24% production, 20% multi-function
- **79.6% exact agreement** with qwen3_8b on maturity level
- 32b detects **+24pp more risk signals**, **+17pp more org change signals**
- Evidence spans: **8.0 per doc** average (vs 4.7 for 8b)
- Confidence calibrated: max 0.85, avg 0.36
- Rationale quality: contrastive, fact-grounded, never copies rubric
- Parse error rate: 1.6% (4 repetition loops)
- Total tokens: 1,108,968 (~1.1M)
- Throughput: 10.3 tokens/second
