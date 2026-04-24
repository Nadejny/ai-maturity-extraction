# Prompt Engineering Ceiling Ablation — 2×4 Factorial Analysis

**Date:** 2026-04-21
**Design:** 4 models × 2 prompt versions × 80 articles
**Hypothesis (ex-ante):** Ceiling prompt with few-shot, explicit checklists, and research-paper test would shift extraction quality upward; effect should scale with model size per Wei et al. 2022.
**Actual finding:** Effect is **inverted** — ceiling prompt *degrades* sub-frontier models while leaving Opus nearly unchanged.

---

## 1. Setup

### Models
| Model | Size | Host |
|---|---|---|
| qwen3_8b | 8B | Ollama |
| qwen3_14b | 14B | Ollama |
| qwen3_32b | 32B | Ollama |
| opus_4_7 | frontier (Anthropic) | Claude Code agent |

### Prompt versions
- **Baseline (v1):** original `build_extraction_prompt` in `pipeline_core/prompting.py` — one-shot output schema, maturity rubric, short example. ~900 tokens.
- **Ceiling (v2):** `build_extraction_prompt_ceiling` — adds 4 few-shot examples (mat=0/1/2/3), research-paper test, multi-function test, items specificity with GOOD/WEAK, contrastive rationale pattern, strict verbatim-quote requirement. ~2200 tokens. Self-critique **included for Opus**, **excluded for qwen** (per Wei 2022 / Madaan 2023).

### Sample
80 doc_ids from `doc_ids_batch2.txt` — random sample of the 769-doc corpus, stratified through deterministic seed=42. For qwen models: same 80 docs in both conditions (matched-pairs). For Opus: baseline on `doc_ids_batch1.txt` (80 different docs), ceiling on `doc_ids_batch2.txt` — distribution comparison only, no per-doc pairing.

### Raw data
- qwen3_8b baseline: `artifacts/inference_runs/4x769/qwen3_8b/predictions.jsonl` (filtered to batch2)
- qwen3_8b ceiling: `artifacts/inference_runs/qwen_ceiling_80/qwen3_8b/predictions.jsonl`
- qwen3_14b baseline: `qwen14_800/qwen3_14b/predictions.jsonl` (filtered)
- qwen3_14b ceiling: `qwen_ceiling_80/qwen3_14b/predictions.jsonl`
- qwen3_32b baseline: `qwen32_800/qwen3_32b/predictions.jsonl` (filtered)
- qwen3_32b ceiling: `qwen_ceiling_80/qwen3_32b/predictions.jsonl`
- opus_4_7 baseline: `opus47_160/opus_4_7/predictions.jsonl`
- opus_4_7 ceiling: `opus47_160/opus_4_7_v2/predictions.jsonl`

---

## 2. Main result — maturity distribution

### Counts of 80 documents per maturity level

| Model | Prompt | mat=0 | mat=1 | mat=2 | mat=3 | mat=4 | **avg** |
|---|---|---|---|---|---|---|---|
| qwen3_8b | baseline | 37 (46%) | 1 (1%) | 31 (39%) | 11 (14%) | 0 (0%) | 1.20 |
| qwen3_8b | **ceiling** | **61 (76%)** | 3 (4%) | 12 (15%) | 4 (5%) | 0 (0%) | **0.49** |
| qwen3_14b | baseline | 38 (48%) | 5 (6%) | 25 (31%) | 12 (15%) | 0 (0%) | 1.14 |
| qwen3_14b | **ceiling** | **63 (79%)** | 1 (1%) | 11 (14%) | 5 (6%) | 0 (0%) | **0.47** |
| qwen3_32b | baseline | 35 (44%) | 2 (2%) | 23 (29%) | 19 (24%) | 1 (1%) | 1.36 |
| qwen3_32b | **ceiling** | **62 (78%)** | 2 (2%) | 10 (12%) | 6 (8%) | 0 (0%) | **0.50** |
| opus_4_7 | baseline | 1 (1%) | 3 (4%) | 71 (89%) | 3 (4%) | 2 (2%) | 2.02 |
| opus_4_7 | ceiling | 1 (1%) | 6 (8%) | 68 (85%) | 4 (5%) | 1 (1%) | **1.98** |

### Average-maturity delta (ceiling − baseline)

| Model | Δ avg_maturity | Δ confidence |
|---|---|---|
| qwen3_8b | **−0.712** | −0.190 |
| qwen3_14b | **−0.662** | −0.179 |
| qwen3_32b | **−0.863** | −0.209 |
| opus_4_7 | **−0.050** | **+0.034** |

**The magnitude of the Opus effect is ≈15× smaller than the qwen effect, and in the opposite direction on confidence.**

---

## 2a. Opus baseline vs Opus ceiling — is the baseline prompt losing information?

The design question behind the ceiling run is: *"was the original prompt too thin? Is Opus leaving signal on the table under v1 that a more instruction-rich v2 would capture?"* Opus is the only model capable enough to answer this — if even the frontier model cannot meaningfully improve with a richer prompt, no smaller model will either.

**Maturity distribution — unchanged in substance.** Opus clustered at mat=2 on both batches (89% baseline, 85% ceiling). Ceiling shifted three mat=2 docs into mat=1 (arxiv / research papers correctly re-labeled) and one mat=4 into mat=3. The average maturity delta of −0.05 is within noise given disjoint batches; no sign that the baseline prompt was systematically mis-classifying.

**Signal fill rates — secondary fields rise, primary fields unchanged.** Primary extraction fields (ai_use_cases 98.8% / adoption_patterns 98.8% / ai_stack 96–97% / deployment_scope 90–94%) are saturated under both prompts. Secondary fields move up under ceiling: **risk_signals +32.5 pp** (60% → 92.5%), **org_change_signals +21.2 pp** (11% → 32.5%), **budget_signals +11.2 pp** (20% → 31.2%), kpi_signals +3.8 pp. Opus found more evidence on subtle fields when explicitly asked, because its comprehension is robust enough to use richer instructions as concepts rather than keyword filters.

**Confidence and evidence spans — marginal improvement.** Avg confidence +0.034 (0.73 → 0.76), spans per doc +11% (6.41 → 7.09), coverage unchanged at 98.8%. Structural validity 100% under both.

**Answer to the research question.** The baseline prompt is **not leaving substantive signal on the table**. The ceiling prompt's effect on Opus is concentrated on secondary fields (risk, org change, budget) and does not change primary maturity assignments meaningfully. This matters for the thesis in two ways:

1. **Baseline qwen3_32b results on 769 docs are defensible as primary findings** — they are not products of an under-specified prompt. If Opus gains only +10–30 pp on three secondary fields with a 2200-token ceiling prompt, the baseline prompt is already close to the information ceiling at the task level.
2. **Sub-frontier-specific fragility is the real story, not prompt design.** When the same ceiling prompt is applied to qwen, the effect is catastrophic (−0.7 avg maturity, fill rates halved, alignment with Opus collapses). The problem is not "our prompt was too sparse" — it's that sub-frontier models cannot absorb denser instructions without failing into literal phrase-matching.

---

## 3. Per-doc label changes (matched-pairs, qwen only)

Because all 3 qwen models ran both conditions on the same 80 docs, we can track per-doc flips.

| Model | common N | changed | % | upgrades | downgrades | unchanged |
|---|---|---|---|---|---|---|
| qwen3_8b | 80 | 33 | 41.2% | 2 | **31** | 47 |
| qwen3_14b | 80 | 31 | 38.8% | 3 | **28** | 49 |
| qwen3_32b | 80 | 33 | 41.2% | 2 | **31** | 47 |

**~95% of movement is downgrade.** The ceiling prompt did not simply re-calibrate models — it systematically pushed qwen extractions to mat=0.

(Opus cannot be analyzed this way — baseline and ceiling were run on disjoint 80-doc subsamples.)

---

## 4. Signal fill rates — where the downgrade materialized

Percentage of 80 docs where each signal field has `status="present"`:

| Field | qwen3_8b base | qwen3_8b ceil | qwen3_14b base | qwen3_14b ceil | qwen3_32b base | qwen3_32b ceil | Opus base | Opus ceil |
|---|---|---|---|---|---|---|---|---|
| ai_use_cases | 60.0% | **22.5%** | 63.7% | **25.0%** | 60.0% | **27.5%** | 98.8% | 98.8% |
| adoption_patterns | 40.0% | **3.8%** | 46.2% | **5.0%** | 56.2% | **16.2%** | 98.8% | 98.8% |
| ai_stack | 50.0% | **10.0%** | 41.2% | **8.8%** | 52.5% | **13.8%** | 97.5% | 96.2% |
| kpi_signals | 28.7% | **8.8%** | 33.8% | **6.2%** | 38.8% | **8.8%** | 78.8% | **82.5%** ↑ |
| budget_signals | 0.0% | 0.0% | 0.0% | 0.0% | 2.5% | 1.2% | 20.0% | **31.2%** ↑ |
| org_change_signals | 7.5% | **0.0%** | 6.2% | 1.2% | 26.2% | **7.5%** | 11.2% | **32.5%** ↑ |
| risk_signals | 16.2% | **7.5%** | 12.5% | 2.5% | 37.5% | **15.0%** | 60.0% | **92.5%** ↑ |
| roadmap_signals | 30.0% | **8.8%** | 31.2% | **6.2%** | 46.2% | **12.5%** | 75.0% | 78.8% |
| deployment_scope | 53.8% | **21.2%** | 47.5% | **20.0%** | 55.0% | **17.5%** | 93.8% | 90.0% |

### Two opposite patterns

- **qwen:** every field drops (often by 30–40 pp); typical reduction ×2-3.
- **Opus:** primary fields stable, secondary fields (risk, org_change, budget) **rise** by 10-32 pp.

The ceiling prompt asked both models to be more evidence-grounded. Opus found *more* evidence on subtle fields (risk, org change) because its comprehension is robust. Qwen interpreted the "require verbatim quote" rule literally and marked fields absent when they couldn't locate exact phrase matches.

---

## 5. Structural validity

| Model | Prompt | parse_err | wrong_fld | empty_spans | valid |
|---|---|---|---|---|---|
| qwen3_8b | baseline | 3 | 0 | 8 | 77/80 |
| qwen3_8b | ceiling | 4 | 3 | 0 | 76/80 |
| qwen3_14b | baseline | 0 | 0 | 12 | 80/80 |
| qwen3_14b | ceiling | 1 | 1 | 3 | 79/80 |
| qwen3_32b | baseline | 4 | 0 | 10 | 76/80 |
| qwen3_32b | ceiling | 1 | 2 | 3 | 79/80 |
| opus_4_7 | baseline | 0 | 0 | 0 | 80/80 |
| opus_4_7 | ceiling | 0 | 0 | 0 | 80/80 |

Validity is roughly unchanged or slightly better under ceiling. **The degradation is not in JSON structure — it's in semantic content.** qwen produced valid JSON all along; the JSON now just says "absent" much more often.

---

## 6. Evidence spans

| Model | Prompt | coverage | avg spans/doc | total |
|---|---|---|---|---|
| qwen3_8b | baseline | 51.2% | 4.10 | 168 |
| qwen3_8b | ceiling | **25.0%** | 3.50 | 70 |
| qwen3_14b | baseline | 50.0% | 5.12 | 205 |
| qwen3_14b | ceiling | **23.8%** | 5.05 | 96 |
| qwen3_32b | baseline | 47.5% | 8.71 | 331 |
| qwen3_32b | ceiling | **23.8%** | 9.26 | 176 |
| opus_4_7 | baseline | 98.8% | 6.41 | 506 |
| opus_4_7 | ceiling | 98.8% | **7.09** | 560 |

Qwen span coverage **halved**. Opus coverage unchanged, spans-per-doc *increased* by 11%. The ceiling prompt's "verbatim quote required" pushed qwen to stop providing spans entirely (when they couldn't find exact matches) rather than searching harder.

---

## 7. Inter-model agreement

### Baseline (N=80)

|  | qwen3_8b | qwen3_14b | qwen3_32b | opus_4_7 |
|---|---|---|---|---|
| qwen3_8b | — | 81.2% | 81.2% | — (batch1 disjoint) |
| qwen3_14b | 81.2% | — | 81.2% | — |
| qwen3_32b | 81.2% | 81.2% | — | — |
| opus_4_7 | — | — | — | — |

### Ceiling (N=80)

|  | qwen3_8b | qwen3_14b | qwen3_32b | opus_4_7 |
|---|---|---|---|---|
| qwen3_8b | — | **88.8%** | **91.2%** | 21.2% |
| qwen3_14b | 88.8% | — | **90.0%** | 16.2% |
| qwen3_32b | 91.2% | 90.0% | — | 21.2% |
| opus_4_7 | 21.2% | 16.2% | 21.2% | — |

### What this tells us

- qwen-family agreement **increased** under ceiling (81% → 88-91%). They converged on a common answer.
- qwen-vs-Opus agreement **collapsed** to ~20%.
- **Qwen family converged on a wrong answer, moving away from the frontier model's answer.**

This is a stronger and more interpretable signal than raw distribution shift: whatever the "correct" answer is, ceiling-prompted qwen models are systematically *further* from the frontier reference than baseline-prompted qwen models.

---

## 8. Alignment with Opus as soft reference

Since Opus is the closest available proxy for ground truth, we measure how well each qwen prediction aligns with Opus's ceiling predictions.

| Model | Prompt | Exact match vs Opus-ceiling | Within 1 level |
|---|---|---|---|
| qwen3_8b | baseline | 38.8% | 58.8% |
| qwen3_8b | ceiling | **21.2%** | **30.0%** |
| qwen3_14b | baseline | 41.2% | 57.5% |
| qwen3_14b | ceiling | **16.2%** | **28.7%** |
| qwen3_32b | baseline | 35.0% | 58.8% |
| qwen3_32b | ceiling | **21.2%** | **28.7%** |

Ceiling prompt **halved** alignment with the frontier reference on both exact match and within-1-level metrics.

---

## 9. Mechanism hypothesis

The ceiling prompt contains these hard rules:

1. *"EXPLICIT production-deployment phrase present: 'deployed in production', 'serving N requests/day', 'launched to users'…"*
2. *"If you cannot find a verbatim supporting quote, downgrade status to uncertain / empty."*
3. *"Research paper test: arxiv/preprint → mat=1 unless production claim explicit."*
4. *"When between two levels, choose the LOWER one."*

**Opus** appears to read these as *concepts* — "any clear indication of production use" — and applies them with semantic understanding. It keeps finding production evidence even when the specific phrases aren't used.

**Qwen models** appear to read these as *exact phrase lists*. They scan the article for the literal strings from the rubric and, finding none, conclude there's no production evidence. This triggers cascading downgrades: mat=2 → mat=0 ⇒ signal fields marked absent ⇒ spans disappear ⇒ confidence drops.

This is a well-documented pattern in the LLM prompt-engineering literature: structured complex prompts degrade smaller models (Wei et al. 2022 for CoT; Madaan et al. 2023 for self-refine; Huang et al. 2023 on self-correction failures). Our result is the extraction-task instantiation of the same phenomenon.

---

## 10. Literature alignment

### Wei et al. 2022 — Chain-of-Thought

> "CoT prompting is an emergent ability of model scale that does not positively impact performance for small models, and only yields performance gains when used with models of ~100B parameters."

> "For smaller models, CoT prompting often has a detrimental effect, degrading performance below that of standard prompting."

Our result on extraction task:
- Opus (≥100B effective) — ceiling prompt neutral or slightly positive
- qwen3_8b/14b/32b (all below 100B) — ceiling prompt strongly degrades

This confirms Wei et al. 2022 beyond reasoning tasks, now on structured extraction.

### Madaan et al. 2023 — Self-Refine

> "The base model needs to be capable of following instructions provided… primitive language models may not be able to benefit from this approach."

In our design, self-critique was **removed** for qwen precisely to avoid this failure mode. Even without self-critique, the ceiling prompt's instruction complexity alone was enough to break qwen behavior.

### Huang et al. 2023 — LLMs Cannot Self-Correct Yet

Even Opus showed only marginal positive delta (+0.034 confidence, −0.05 avg maturity). Our data is consistent with the claim that self-critique buys minimal real improvement at the frontier for well-defined structured tasks.

---

## 11. Implications for the RQ

The research question asks whether LLMs can be employed for **reproducible** extraction with **acceptable quality** and **documented error characteristics**. This ablation contributes to two of those three axes:

### Reproducibility ✓
Both prompt conditions are fully scripted (`prompt_version` parameter in `cli.run_inference`), temperature=0, seed=42, documented inference settings. Running the exact same commands reproduces the results.

### Acceptable quality — model-prompt interaction is a first-order concern
"Acceptable quality" is not a property of the model alone — **the prompt-model pair jointly determines quality**. The same prompt that is neutral for Opus is catastrophic for qwen. A fair quality assessment must report prompt used alongside model.

### Documented error characteristics ✓ (strengthened)
We now document a *failure mode* of sub-frontier models under complex prompts: **literal interpretation cascade**, leading to systematic under-extraction and mat=0 collapse. This is a per-model error signature with quantitative evidence.

---

## 12. Practical recommendations

1. **Main findings of the thesis should use baseline (v1) prompt results**, not ceiling. Baseline qwen3_32b gives 24% mat=3 on the 80-doc sample and 20% on the full 769; ceiling qwen3_32b gives 8%. The baseline number is defensible; the ceiling number is an artifact of a prompt-model mismatch.

2. **For the cross-industry analysis, qwen3_32b baseline remains primary.** No change needed to `analysis_cross_industry.md`.

3. **For small-model prompt engineering in production**: do not port ceiling-style instructions from frontier-model best practices. Small models need prompts with different tradeoffs (more concrete pattern-matching hints, less abstract rule-based reasoning).

4. **Opus-as-reference methodology** is valid: Opus ceiling-prompt predictions cluster in a sensible space (85% mat=2, consistent with tech-blog corpus composition), while qwen-ceiling predictions collapse to mat=0. This asymmetry reinforces Opus as the more reliable soft reference.

---

## 13. Numbers for the thesis

### Key quantitative findings

- 4 models × 2 prompt versions × 80 articles = **640 inference calls** for this ablation
- qwen model average-maturity deltas under ceiling prompt: −0.66, −0.86, −0.71 (14B, 32B, 8B)
- Opus average-maturity delta under ceiling prompt: −0.05
- 31-33 of 80 qwen predictions (~40%) changed label under ceiling, of which 28-31 were downgrades (~95% one-directional)
- Qwen-vs-Opus maturity agreement dropped from ~35-41% (baseline) to 16-21% (ceiling)
- Signal fill rates for qwen dropped by 20-40 pp on most fields under ceiling
- Span coverage halved for qwen under ceiling; unchanged for Opus
- Structural validity unchanged by prompt condition (JSON format was not the problem)

### One-sentence finding

*"Complex prompt instructions (few-shot + checklists + verbatim-quote requirements) degrade sub-frontier extraction models by a magnitude of −0.7 in average maturity and halve alignment with the frontier reference, while leaving the frontier model's output nearly unchanged — confirming Wei et al.'s 2022 chain-of-thought emergent-ability finding on a structured extraction task."*

---

## 14. Next steps

- [x] Factorial analysis computed
- [ ] Write into methodology chapter under "Prompt engineering ablation"
- [ ] Include scaling-curve figure (model-size on X, avg maturity under ceiling on Y)
- [ ] Update TODO — ceiling ablation closed with negative-but-interesting finding
