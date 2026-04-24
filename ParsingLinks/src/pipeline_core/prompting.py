"""Prompt builders for extraction and semantic judging."""

from __future__ import annotations

import json
from typing import Any

from .constants import MATURITY_RUBRIC
from .schema import empty_payload


def _rubric_text() -> str:
    lines = []
    for level, desc in MATURITY_RUBRIC.items():
        lines.append(f"{level}: {desc}")
    return "\n".join(lines)


def build_extraction_prompt(record: dict[str, Any], max_text_chars: int = 16000) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    system_prompt = (
        "You are a precise information-extraction system. "
        "You read an article and output exactly one JSON object. "
        "Output raw JSON only — no markdown fences, no commentary, no text before or after the JSON."
    )

    schema_template = json.dumps(empty_payload(), ensure_ascii=False, indent=2)
    text = str(record.get("text") or "")
    text = text[:max_text_chars]

    user_prompt = f"""Extract enterprise AI-adoption signals from the article below.

=== OUTPUT FORMAT ===
Return exactly one JSON object matching this schema:
{schema_template}

=== FIELD RULES ===
1. "status" must be one of: "present", "absent", "uncertain".
   - "present": the article explicitly describes this signal.
   - "absent": the article clearly has NO evidence of this signal.
   - "uncertain": ambiguous or only implied.
2. "items" must be a FLAT LIST OF SHORT STRINGS (2-6 words each), max 5 items per field.
   CORRECT: ["code review automation", "fraud detection"]
   WRONG:   [{{"name": "code review", "description": "..."}}]
   Do NOT put objects, dicts, or nested structures inside items.
3. "deployment_scope.value": describe the ACTUAL scope from the article in your own words
   (e.g., "one product team", "Gboard on Pixel 6", "company-wide across 3 BUs").
   Do NOT copy text from the maturity rubric.
4. If status is "absent", items must be [] and value must be "".

=== MATURITY RUBRIC ===
{_rubric_text()}

Assign maturity based on the STRONGEST evidence in the text:
- Level 2 requires EXPLICIT production deployment (not just a research paper or experiment).
- Level 3 requires evidence of AI in MULTIPLE distinct business functions.
- Level 4 requires enterprise-wide scale with MEASURABLE business impact (revenue, cost, KPIs).
When in doubt between two levels, choose the LOWER one.

=== CONFIDENCE CALIBRATION ===
- 0.2-0.4: weak hints, mostly inferred
- 0.5-0.6: some evidence but incomplete
- 0.7-0.8: clear evidence for most fields
- 0.9-1.0: strong, explicit evidence throughout
Do NOT default to 0.95. Calibrate to actual evidence strength.

=== EVIDENCE SPANS ===
For EVERY field where status="present", you MUST include at least one entry in evidence_spans:
{{"field": "<field_name>", "quote": "<short verbatim quote from text, max 100 chars>", "start_char": null, "end_char": null}}

=== MATURITY RATIONALE ===
Write 1-2 sentences explaining WHY you chose this maturity level, referencing concrete facts from the article. Do NOT copy the rubric definition.

=== EXAMPLE OUTPUT (for reference only, do not copy values) ===
{{"ai_use_cases": {{"status": "present", "items": ["on-device grammar correction"]}}, "adoption_patterns": {{"status": "present", "items": ["on-device inference", "model distillation"]}}, "ai_stack": {{"status": "present", "items": ["transformer encoder", "LSTM decoder"]}}, "kpi_signals": {{"status": "absent", "items": []}}, "budget_signals": {{"status": "absent", "items": []}}, "org_change_signals": {{"status": "absent", "items": []}}, "risk_signals": {{"status": "absent", "items": []}}, "roadmap_signals": {{"status": "present", "items": ["expand to more languages"]}}, "deployment_scope": {{"status": "present", "value": "Gboard on Pixel 6"}}, "maturity_level": 2, "maturity_rationale": "One production AI feature (grammar correction) deployed on a single product line (Pixel 6), no evidence of multi-function use.", "confidence": 0.75, "evidence_spans": [{{"field": "ai_use_cases", "quote": "grammar correction feature built into Gboard on Pixel 6", "start_char": null, "end_char": null}}, {{"field": "deployment_scope", "quote": "available on almost any app with Gboard", "start_char": null, "end_char": null}}]}}

=== ARTICLE METADATA ===
doc_id: {record.get('doc_id', '')}
company: {record.get('company', '')}
industry: {record.get('industry', '')}
year: {record.get('year', '')}
title: {record.get('title', '')}

=== ARTICLE TEXT ===
{text}""".strip()

    return system_prompt, user_prompt


def build_extraction_prompt_ceiling(record: dict[str, Any], max_text_chars: int = 16000) -> tuple[str, str]:
    """Ceiling-version prompt: adds few-shot, research-paper test, multi-function test,
    items-specificity examples, contrastive rationale requirement.

    No self-critique / multi-pass step (literature: self-refine can amplify self-bias
    on sub-frontier models). Single-pass, richer instructions only.
    """
    system_prompt = (
        "You are a precise information-extraction system. "
        "You read an article and output exactly one JSON object. "
        "Output raw JSON only — no markdown fences, no commentary, no text before or after the JSON."
    )

    schema_template = json.dumps(empty_payload(), ensure_ascii=False, indent=2)
    text = str(record.get("text") or "")
    text = text[:max_text_chars]

    user_prompt = f"""Extract enterprise AI-adoption signals from the article below.

=== OUTPUT FORMAT ===
Return exactly one JSON object matching this schema:
{schema_template}

=== FIELD RULES ===
1. "status" must be one of: "present", "absent", "uncertain".
   - "present": the article EXPLICITLY describes this signal with a quotable phrase.
   - "absent": the article clearly has NO evidence of this signal.
   - "uncertain": ambiguous or only implied — DEFAULT to uncertain when in doubt.
2. "items" must be a FLAT LIST OF SHORT STRINGS (2-6 words each), max 5 items per field.
   CORRECT: ["code review automation", "fraud detection"]
   WRONG:   [{{"name": "code review", "description": "..."}}]
   Do NOT put objects, dicts, or nested structures inside items.
3. "deployment_scope.value": describe the ACTUAL scope from the article in your own words
   (e.g., "one product team", "Gboard on Pixel 6", "company-wide across 3 BUs").
   Do NOT copy text from the maturity rubric.
4. If status is "absent", items must be [] and value must be "".

=== ITEMS SPECIFICITY ===
Items must be SPECIFIC facts from the article, not generic categories.

ai_use_cases:
  GOOD: ["real-time ETA prediction", "order-volume forecasting"]
  WEAK: ["prediction", "forecasting"]  ← generic, avoid

ai_stack:
  GOOD: ["GPT-4", "LangChain", "Pinecone", "BERT base"]
  WEAK: ["LLMs", "vector database", "embeddings"]  ← generic

kpi_signals:
  GOOD: ["CTR +12%", "conversion rate 8.3%", "latency p99 450ms"]
  WEAK: ["engagement", "performance"]  ← no concrete value

If the text only provides a generic mention, prefer status="uncertain" over a weak item.

=== MATURITY RUBRIC (apply STRICTLY using flowchart below) ===

Level 0 — No AI evidence:
  The article does NOT describe any AI/ML system being used. Example: generic
  product announcement, company values post, pure infrastructure/DevOps without ML.

Level 1 — Experiment / pilot / research (NOT YET PRODUCTION):
  Use when:
  - arxiv abstract, research paper, conference talk proposing or benchmark-evaluating a method.
  - Pilot, PoC, hackathon, prototype described WITHOUT "deployed to production".
  - Phrases like "we propose", "we evaluated on benchmark X", "pilot program",
    "PoC", "prototype" — without "in production for N months / serving N users".

Level 2 — Production in ONE function:
  Use ONLY if BOTH:
  - EXPLICIT production-deployment phrase present: "deployed in production",
    "serving N requests/day", "launched to users", "currently handles X", "live since".
  - AI is scoped to a SINGLE business function (search only, fraud only, recs only).

Level 3 — Multi-function with governance OR KPI tracking:
  Use ONLY if BOTH conditions met:
  - Condition A: TWO OR MORE DISTINCT business functions use AI, named separately
    (e.g., "search AND ads ranking AND recommendations", "fraud detection AND
    customer support AND code review"). NOT just two features of the same function.
  - Condition B: EITHER governance structure (model review, ML platform, central team)
    OR KPI tracking with named business metrics (CTR, conversion, cost, revenue).
  If A is met but B is NOT — choose Level 2.

Level 4 — Enterprise-scale transformation:
  Use ONLY if:
  - AI embedded across entire company operations (not just multiple functions).
  - AND measurable company-level impact: "revenue +N%", "cost -$M", ">50%
    employees use AI daily", ">80% adoption across organization".

When between two levels: choose the LOWER one.

=== RESEARCH PAPER TEST ===
Before choosing Level 2, check: is this article about a DEPLOYED product, or about a RESEARCH METHODOLOGY?

Signals of research (→ Level 1, not Level 2):
- Title contains "we propose", "toward", "a survey of", "evaluating", "analysis of"
- arxiv/preprint source, conference paper
- Benchmark-only results without production traffic
- No explicit phrase like "deployed", "in production", "serving users"

If article is research-style → Level 1 unless production claim is explicit.

=== MULTI-FUNCTION TEST (for Level 3) ===
List the business functions with AI from the article. If you can name TWO OR MORE distinct functions (not just "search" twice, but e.g. search + fraud + recs), proceed to check governance/KPI. If only ONE function → Level 2.

=== CONFIDENCE CALIBRATION ===
- 0.2-0.4: weak hints, mostly inferred
- 0.5-0.6: some evidence but incomplete
- 0.7-0.8: clear evidence for most fields
- 0.9-1.0: strong, explicit evidence throughout
Do NOT default to 0.95. Calibrate to actual evidence strength.

=== EVIDENCE SPANS (STRICT) ===
For EVERY field where status="present", you MUST include at least one entry in evidence_spans:
{{"field": "<field_name>", "quote": "<VERBATIM quote from text, max 100 chars>", "start_char": null, "end_char": null}}

The quote MUST appear verbatim in the article text. If you cannot find a verbatim supporting quote, downgrade status to "uncertain".

=== MATURITY RATIONALE (CONTRASTIVE, REQUIRED) ===
Follow this pattern exactly:
"Level N because [specific fact X from article]. Considered level N±1 but rejected because [specific reason Y from article]."

Example for Level 2:
"Level 2 because article states 'deployed to Gboard on Pixel 6, serving all users in supported locales'. Considered Level 3 but rejected because no evidence of AI in a second distinct business function beyond keyboard suggestions."

Example for Level 3:
"Level 3 because AI is deployed across search, ads ranking, AND recommendations (three distinct functions), with central ML platform mentioned. Considered Level 4 but rejected because no company-level adoption or revenue figures reported."

=== FEW-SHOT EXAMPLES ===

Example A (Level 1, research paper):
Text: "We propose a novel transformer architecture for code generation and evaluate it on HumanEval benchmark, achieving 85% pass rate."
Decision: Level 1. Research proposal, no production claim. ai_use_cases="uncertain" or "absent" depending on whether code-generation is even implemented.

Example B (Level 2, single-function production):
Text: "Our spam filter is deployed on all incoming emails, processing 100M messages per day with 98% precision."
Decision: Level 2. Explicit production + single function (spam filtering). Not Level 3 because only one function.

Example C (Level 3, multi-function + KPI):
Text: "AI powers our search ranking, personalized ads, and product recommendations. A/B tests showed +5% CTR across all three surfaces."
Decision: Level 3. Three distinct functions + KPI tracking (A/B + CTR). Not Level 4 because no company-wide adoption or revenue figures.

Example D (Level 0, no AI):
Text: "Our engineering culture emphasizes code reviews and pair programming."
Decision: Level 0. No AI described.

=== EXAMPLE OUTPUT (schema reference — do NOT copy values) ===
{{"ai_use_cases": {{"status": "present", "items": ["on-device grammar correction"]}}, "adoption_patterns": {{"status": "present", "items": ["on-device inference", "model distillation"]}}, "ai_stack": {{"status": "present", "items": ["transformer encoder", "LSTM decoder"]}}, "kpi_signals": {{"status": "absent", "items": []}}, "budget_signals": {{"status": "absent", "items": []}}, "org_change_signals": {{"status": "absent", "items": []}}, "risk_signals": {{"status": "absent", "items": []}}, "roadmap_signals": {{"status": "present", "items": ["expand to more languages"]}}, "deployment_scope": {{"status": "present", "value": "Gboard on Pixel 6"}}, "maturity_level": 2, "maturity_rationale": "Level 2 because article states 'deployed to Gboard on Pixel 6'. Considered Level 3 but rejected because no evidence of AI in a second distinct business function beyond keyboard suggestions.", "confidence": 0.75, "evidence_spans": [{{"field": "ai_use_cases", "quote": "grammar correction feature built into Gboard on Pixel 6", "start_char": null, "end_char": null}}, {{"field": "deployment_scope", "quote": "available on almost any app with Gboard", "start_char": null, "end_char": null}}]}}

=== ARTICLE METADATA ===
doc_id: {record.get('doc_id', '')}
company: {record.get('company', '')}
industry: {record.get('industry', '')}
year: {record.get('year', '')}
title: {record.get('title', '')}

=== ARTICLE TEXT ===
{text}""".strip()

    return system_prompt, user_prompt


def build_semantic_judge_prompt(
    source_text: str,
    gold_payload: dict[str, Any],
    pred_payload: dict[str, Any],
    max_text_chars: int = 6000,
) -> tuple[str, str]:
    system_prompt = (
        "You are a strict evaluator of information extraction quality. "
        "Return JSON only."
    )

    user_prompt = f"""
Evaluate prediction quality versus gold annotation and source text.
Return JSON:
{{
  "groundedness": <float 0..1>,
  "completeness": <float 0..1>,
  "hallucination_risk": <float 0..1>,
  "reason": "short rationale"
}}

Source text:
{source_text[:max_text_chars]}

Gold payload:
{json.dumps(gold_payload, ensure_ascii=False)}

Predicted payload:
{json.dumps(pred_payload, ensure_ascii=False)}
""".strip()

    return system_prompt, user_prompt
