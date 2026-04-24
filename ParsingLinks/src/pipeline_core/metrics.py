"""Metric utilities for strict and semantic evaluation."""

from __future__ import annotations

from collections import Counter
from typing import Any

from .constants import ALL_SIGNAL_FIELDS, LIST_SIGNAL_FIELDS


def _safe_set(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    out: set[str] = set()
    for item in items:
        s = str(item).strip().lower()
        if s:
            out.add(s)
    return out


def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return precision, recall, f1


def compute_status_accuracy(gold_payload: dict[str, Any], pred_payload: dict[str, Any]) -> float:
    hits = 0
    total = 0
    for field in ALL_SIGNAL_FIELDS:
        g = ((gold_payload.get(field) or {}).get("status") or "uncertain").strip().lower()
        p = ((pred_payload.get(field) or {}).get("status") or "uncertain").strip().lower()
        total += 1
        if g == p:
            hits += 1
    return hits / total if total else 0.0


def compute_deployment_exact(gold_payload: dict[str, Any], pred_payload: dict[str, Any]) -> float:
    g = gold_payload.get("deployment_scope") or {}
    p = pred_payload.get("deployment_scope") or {}

    g_status = str(g.get("status") or "uncertain").strip().lower()
    p_status = str(p.get("status") or "uncertain").strip().lower()

    if g_status != p_status:
        return 0.0
    if g_status != "present":
        return 1.0

    g_val = str(g.get("value") or "").strip().lower()
    p_val = str(p.get("value") or "").strip().lower()
    return 1.0 if g_val == p_val else 0.0


def compute_multilabel_macro_micro_f1(
    paired_payloads: list[tuple[dict[str, Any], dict[str, Any]]],
) -> dict[str, Any]:
    per_field: dict[str, dict[str, float]] = {}

    micro_tp = 0
    micro_fp = 0
    micro_fn = 0

    macro_f1_values: list[float] = []

    for field in LIST_SIGNAL_FIELDS:
        tp = 0
        fp = 0
        fn = 0

        for gold_payload, pred_payload in paired_payloads:
            g_items = _safe_set((gold_payload.get(field) or {}).get("items"))
            p_items = _safe_set((pred_payload.get(field) or {}).get("items"))

            tp += len(g_items.intersection(p_items))
            fp += len(p_items - g_items)
            fn += len(g_items - p_items)

        prec, rec, f1 = precision_recall_f1(tp, fp, fn)
        per_field[field] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1": round(f1, 4),
        }

        micro_tp += tp
        micro_fp += fp
        micro_fn += fn
        macro_f1_values.append(f1)

    micro_prec, micro_rec, micro_f1 = precision_recall_f1(micro_tp, micro_fp, micro_fn)
    macro_f1 = sum(macro_f1_values) / len(macro_f1_values) if macro_f1_values else 0.0

    return {
        "per_field": per_field,
        "micro_precision": round(micro_prec, 4),
        "micro_recall": round(micro_rec, 4),
        "micro_f1": round(micro_f1, 4),
        "macro_f1": round(macro_f1, 4),
    }


def compute_accuracy(labels_gold: list[int], labels_pred: list[int]) -> float:
    if not labels_gold:
        return 0.0
    hits = sum(1 for g, p in zip(labels_gold, labels_pred) if g == p)
    return hits / len(labels_gold)


def weighted_kappa(labels_gold: list[int], labels_pred: list[int], min_label: int = 0, max_label: int = 4) -> float:
    if not labels_gold or len(labels_gold) != len(labels_pred):
        return 0.0

    k = max_label - min_label + 1
    if k <= 1:
        return 1.0

    # Confusion matrix
    matrix = [[0 for _ in range(k)] for _ in range(k)]
    for g, p in zip(labels_gold, labels_pred):
        gi = min(max_label, max(min_label, int(g))) - min_label
        pi = min(max_label, max(min_label, int(p))) - min_label
        matrix[gi][pi] += 1

    n = float(len(labels_gold))
    observed = [[cell / n for cell in row] for row in matrix]

    hist_gold = [sum(row) / n for row in matrix]
    hist_pred = [sum(matrix[r][c] for r in range(k)) / n for c in range(k)]

    expected = [[hist_gold[i] * hist_pred[j] for j in range(k)] for i in range(k)]

    denom = float((k - 1) ** 2)

    def weight(i: int, j: int) -> float:
        return ((i - j) ** 2) / denom

    obs_w = 0.0
    exp_w = 0.0
    for i in range(k):
        for j in range(k):
            w = weight(i, j)
            obs_w += w * observed[i][j]
            exp_w += w * expected[i][j]

    if exp_w == 0.0:
        return 1.0
    return 1.0 - (obs_w / exp_w)


def _interval_iou(a_start: int, a_end: int, b_start: int, b_end: int) -> float:
    left = max(a_start, b_start)
    right = min(a_end, b_end)
    inter = max(0, right - left)
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def _quote_similarity(a: str, b: str) -> float:
    aa = str(a or "").strip().lower()
    bb = str(b or "").strip().lower()
    if not aa and not bb:
        return 1.0
    if not aa or not bb:
        return 0.0
    if aa == bb:
        return 1.0
    if aa in bb or bb in aa:
        return 0.75

    a_tokens = set(aa.split())
    b_tokens = set(bb.split())
    if not a_tokens or not b_tokens:
        return 0.0
    inter = len(a_tokens.intersection(b_tokens))
    union = len(a_tokens.union(b_tokens))
    return inter / union if union else 0.0


def evidence_span_overlap(gold_spans: Any, pred_spans: Any) -> float:
    gold = gold_spans if isinstance(gold_spans, list) else []
    pred = pred_spans if isinstance(pred_spans, list) else []

    if not gold and not pred:
        return 1.0
    if not gold and pred:
        return 0.0

    scores: list[float] = []

    for g in gold:
        if not isinstance(g, dict):
            continue
        g_field = str(g.get("field") or "").strip()
        g_start = g.get("start_char")
        g_end = g.get("end_char")
        g_quote = str(g.get("quote") or "")

        best = 0.0
        for p in pred:
            if not isinstance(p, dict):
                continue
            p_field = str(p.get("field") or "").strip()
            if g_field and p_field and g_field != p_field:
                continue

            p_start = p.get("start_char")
            p_end = p.get("end_char")
            p_quote = str(p.get("quote") or "")

            if all(isinstance(x, int) for x in [g_start, g_end, p_start, p_end]):
                score = _interval_iou(int(g_start), int(g_end), int(p_start), int(p_end))
            else:
                score = _quote_similarity(g_quote, p_quote)

            if score > best:
                best = score

        scores.append(best)

    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def semantic_score_from_judge(judge_payload: dict[str, Any]) -> float:
    groundedness = float(judge_payload.get("groundedness", 0.0) or 0.0)
    completeness = float(judge_payload.get("completeness", 0.0) or 0.0)
    hallucination_risk = float(judge_payload.get("hallucination_risk", 1.0) or 1.0)

    groundedness = min(1.0, max(0.0, groundedness))
    completeness = min(1.0, max(0.0, completeness))
    hallucination_risk = min(1.0, max(0.0, hallucination_risk))

    return (groundedness + completeness + (1.0 - hallucination_risk)) / 3.0


def top_error_tags(error_rows: list[list[str]], top_k: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for tags in error_rows:
        for tag in tags:
            if tag:
                counter[tag] += 1
    return counter.most_common(top_k)
