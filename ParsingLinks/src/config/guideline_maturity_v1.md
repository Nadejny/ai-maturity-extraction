# Maturity Guideline v1.0

## Scale 0..4

0. No AI evidence
- No explicit mention of AI/ML use in business process or product.

1. Experiment / pilot
- Isolated pilots, PoCs, or experimentation without stable production adoption.

2. Operational use
- At least one AI use case in production with recurring usage in one function.

3. Integrated multi-function use
- AI used across multiple business functions with governance and KPI tracking.

4. Transformational enterprise-scale use
- AI embedded in core operations/products at scale with measurable business impact.

## Annotation rules

- Use only evidence grounded in text.
- Mark `uncertain` when the text implies but does not clearly confirm.
- Prefer conservative labeling over over-interpretation.
- Always provide evidence spans for `present` fields whenever possible.
- Keep `confidence` calibrated to evidence quality.

## QA protocol

- Primary annotator labels 100% of golden documents.
- QA reviewer checks 20% sample.
- If disagreement rate > 10% on maturity_level or deployment_scope,
  update this guideline version and re-review flagged cases.
