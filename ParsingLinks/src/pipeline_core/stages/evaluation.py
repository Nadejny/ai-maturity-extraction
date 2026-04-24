"""Evaluation pipeline for comparing extraction model quality."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..constants import DEFAULT_SEMANTIC_WEIGHT, DEFAULT_STRICT_WEIGHT
from ..io_utils import ensure_dir, read_jsonl, write_jsonl
from ..metrics import (
    compute_accuracy,
    compute_deployment_exact,
    compute_multilabel_macro_micro_f1,
    compute_status_accuracy,
    evidence_span_overlap,
    semantic_score_from_judge,
    top_error_tags,
    weighted_kappa,
)
from ..prompting import build_semantic_judge_prompt
from ..providers import build_provider, load_model_registry
from ..schema import empty_payload, normalize_extraction_payload
from .inference import extract_first_json_object


def _load_json_or_default(path: str | Path | None, default: dict[str, Any]) -> dict[str, Any]:
    if path is None:
        return dict(default)
    p = Path(path)
    if not p.exists():
        return dict(default)
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(default)
    if not isinstance(parsed, dict):
        return dict(default)
    out = dict(default)
    out.update(parsed)
    return out


def _load_golden_rows(golden_jsonl: str | Path, split: str) -> list[dict[str, Any]]:
    rows = read_jsonl(golden_jsonl)
    filtered: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("split") or "").strip().lower() != split.lower():
            continue
        payload_raw = row.get("gold_fields_payload")
        payload, _ = normalize_extraction_payload(payload_raw)
        copied = dict(row)
        copied["gold_fields_payload"] = payload
        filtered.append(copied)
    return filtered


def _load_predictions(predictions_jsonl: str | Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(predictions_jsonl)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        doc_id = str(row.get("doc_id") or "").strip()
        if not doc_id:
            continue
        payload_raw = row.get("fields_payload")
        payload, _ = normalize_extraction_payload(payload_raw)
        copied = dict(row)
        copied["fields_payload"] = payload
        out[doc_id] = copied
    return out


def _judge_semantic_score(
    judge_provider,
    source_text: str,
    gold_payload: dict[str, Any],
    pred_payload: dict[str, Any],
    judge_settings: dict[str, Any],
) -> tuple[float, dict[str, Any], str]:
    system_prompt, user_prompt = build_semantic_judge_prompt(
        source_text=source_text,
        gold_payload=gold_payload,
        pred_payload=pred_payload,
        max_text_chars=int(judge_settings.get("max_text_chars", 6000)),
    )
    response = judge_provider.generate(system_prompt, user_prompt, settings=judge_settings)
    parsed = extract_first_json_object(response.content)
    if parsed is None:
        return 0.0, {}, "judge_parse_error"

    score = semantic_score_from_judge(parsed)
    return score, parsed, ""


def _strict_score_from_components(components: dict[str, float]) -> float:
    # Fixed weighted blend for strict score.
    return (
        0.15 * components.get("status_accuracy", 0.0)
        + 0.10 * components.get("deployment_exact", 0.0)
        + 0.30 * components.get("multilabel_macro_f1", 0.0)
        + 0.20 * components.get("maturity_accuracy", 0.0)
        + 0.15 * components.get("maturity_kappa_norm", 0.0)
        + 0.10 * components.get("evidence_span_overlap", 0.0)
    )


def evaluate_run(
    golden_jsonl: str | Path,
    inference_run_dir: str | Path,
    output_dir: str | Path,
    split: str = "test",
    strict_weight: float = DEFAULT_STRICT_WEIGHT,
    semantic_weight: float = DEFAULT_SEMANTIC_WEIGHT,
    judge_model_registry_path: str | Path | None = None,
    judge_model_alias: str | None = None,
    judge_settings_path: str | Path | None = None,
) -> dict[str, Any]:
    if abs((strict_weight + semantic_weight) - 1.0) > 1e-6:
        raise ValueError("strict_weight + semantic_weight must equal 1.0")

    golden_rows = _load_golden_rows(golden_jsonl, split=split)
    if not golden_rows:
        raise ValueError(f"No golden rows found for split={split}")

    run_dir = Path(inference_run_dir)
    if not run_dir.exists():
        raise FileNotFoundError(f"Inference run dir not found: {run_dir}")

    model_dirs = [p for p in run_dir.iterdir() if p.is_dir() and (p / "predictions.jsonl").exists()]
    if not model_dirs:
        raise ValueError(f"No model prediction folders found in {run_dir}")

    judge_provider = None
    judge_settings = _load_json_or_default(
        judge_settings_path,
        {
            "temperature": 0.0,
            "top_p": 0.95,
            "max_output_tokens": 1024,
            "json_mode": True,
            "max_text_chars": 6000,
        },
    )

    if judge_model_alias and judge_model_registry_path:
        registry = load_model_registry(judge_model_registry_path)
        if judge_model_alias not in registry:
            raise ValueError(f"Judge model alias not found: {judge_model_alias}")
        judge_provider = build_provider(registry[judge_model_alias])

    out_dir = ensure_dir(output_dir)
    leaderboard_rows: list[dict[str, Any]] = []

    for model_dir in sorted(model_dirs):
        model_alias = model_dir.name
        pred_map = _load_predictions(model_dir / "predictions.jsonl")

        paired_payloads: list[tuple[dict[str, Any], dict[str, Any]]] = []
        maturity_gold: list[int] = []
        maturity_pred: list[int] = []

        status_scores: list[float] = []
        deployment_scores: list[float] = []
        span_scores: list[float] = []
        semantic_scores: list[float] = []

        error_rows: list[list[str]] = []
        per_doc_rows: list[dict[str, Any]] = []

        for row in golden_rows:
            doc_id = str(row.get("doc_id") or "")
            gold_payload = row["gold_fields_payload"]

            pred_row = pred_map.get(doc_id)
            if pred_row is None:
                pred_payload = empty_payload()
                pred_structured_valid = False
                pred_error_tags = ["missing_prediction"]
            else:
                pred_payload = pred_row.get("fields_payload") or empty_payload()
                pred_structured_valid = bool(pred_row.get("structured_valid"))
                pred_error_tags = list(pred_row.get("error_tags") or [])

            paired_payloads.append((gold_payload, pred_payload))

            status_acc = compute_status_accuracy(gold_payload, pred_payload)
            deployment_exact = compute_deployment_exact(gold_payload, pred_payload)
            span_overlap = evidence_span_overlap(
                gold_payload.get("evidence_spans"),
                pred_payload.get("evidence_spans"),
            )

            mg = int(gold_payload.get("maturity_level", 0) or 0)
            mp = int(pred_payload.get("maturity_level", 0) or 0)
            maturity_gold.append(mg)
            maturity_pred.append(mp)

            status_scores.append(status_acc)
            deployment_scores.append(deployment_exact)
            span_scores.append(span_overlap)

            semantic_score = 0.0
            judge_payload: dict[str, Any] = {}
            judge_error = ""
            if judge_provider is not None:
                try:
                    semantic_score, judge_payload, judge_error = _judge_semantic_score(
                        judge_provider=judge_provider,
                        source_text=str(row.get("text") or ""),
                        gold_payload=gold_payload,
                        pred_payload=pred_payload,
                        judge_settings=judge_settings,
                    )
                except Exception as exc:  # pylint: disable=broad-except
                    judge_error = f"judge_error:{exc}"
                    semantic_score = 0.0

            semantic_scores.append(semantic_score)

            error_tags = list(pred_error_tags)
            if status_acc < 1.0:
                error_tags.append("status_mismatch")
            if deployment_exact < 1.0:
                error_tags.append("deployment_scope_mismatch")
            if mg != mp:
                error_tags.append("maturity_mismatch")
            if span_overlap < 0.5:
                error_tags.append("weak_evidence")
            if judge_error:
                error_tags.append(judge_error)

            error_rows.append(error_tags)

            per_doc_rows.append(
                {
                    "doc_id": doc_id,
                    "model_alias": model_alias,
                    "status_accuracy": round(status_acc, 4),
                    "deployment_exact": round(deployment_exact, 4),
                    "span_overlap": round(span_overlap, 4),
                    "maturity_gold": mg,
                    "maturity_pred": mp,
                    "semantic_score": round(semantic_score, 4),
                    "pred_structured_valid": pred_structured_valid,
                    "error_tags": error_tags,
                    "judge_payload": judge_payload,
                }
            )

        multilabel = compute_multilabel_macro_micro_f1(paired_payloads)

        maturity_accuracy = compute_accuracy(maturity_gold, maturity_pred)
        maturity_kappa = weighted_kappa(maturity_gold, maturity_pred, min_label=0, max_label=4)
        maturity_kappa_norm = max(0.0, min(1.0, (maturity_kappa + 1.0) / 2.0))

        strict_components = {
            "status_accuracy": sum(status_scores) / max(1, len(status_scores)),
            "deployment_exact": sum(deployment_scores) / max(1, len(deployment_scores)),
            "multilabel_macro_f1": float(multilabel["macro_f1"]),
            "maturity_accuracy": maturity_accuracy,
            "maturity_kappa_norm": maturity_kappa_norm,
            "evidence_span_overlap": sum(span_scores) / max(1, len(span_scores)),
        }
        strict_score = _strict_score_from_components(strict_components)

        semantic_score = sum(semantic_scores) / max(1, len(semantic_scores))
        final_score = strict_weight * strict_score + semantic_weight * semantic_score

        structured_valid_count = 0
        for row in per_doc_rows:
            if row["pred_structured_valid"]:
                structured_valid_count += 1

        model_eval = {
            "model_alias": model_alias,
            "split": split,
            "docs": len(per_doc_rows),
            "structured_valid_rate": round(structured_valid_count / max(1, len(per_doc_rows)), 4),
            "status_accuracy": round(strict_components["status_accuracy"], 4),
            "deployment_exact": round(strict_components["deployment_exact"], 4),
            "multilabel_micro_f1": float(multilabel["micro_f1"]),
            "multilabel_macro_f1": float(multilabel["macro_f1"]),
            "maturity_accuracy": round(maturity_accuracy, 4),
            "maturity_kappa": round(maturity_kappa, 4),
            "evidence_span_overlap": round(strict_components["evidence_span_overlap"], 4),
            "strict_score": round(strict_score, 4),
            "semantic_score": round(semantic_score, 4),
            "final_score": round(final_score, 4),
            "top_error_tags": top_error_tags(error_rows),
        }

        model_out_dir = ensure_dir(out_dir / model_alias)
        write_jsonl(model_out_dir / "eval_per_doc.jsonl", per_doc_rows)
        pd.DataFrame(
            [
                {
                    **row,
                    "error_tags": ";".join(row["error_tags"]),
                    "judge_payload": json.dumps(row["judge_payload"], ensure_ascii=False),
                }
                for row in per_doc_rows
            ]
        ).to_csv(model_out_dir / "eval_per_doc.csv", index=False, encoding="utf-8")

        (model_out_dir / "eval_summary.json").write_text(
            json.dumps(model_eval, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        leaderboard_rows.append(model_eval)

    leaderboard_df = pd.DataFrame(leaderboard_rows).sort_values(
        by=["final_score", "strict_score"],
        ascending=[False, False],
        kind="mergesort",
    )

    leaderboard_csv = out_dir / "leaderboard.csv"
    leaderboard_json = out_dir / "leaderboard.json"
    leaderboard_df.to_csv(leaderboard_csv, index=False, encoding="utf-8")
    leaderboard_json.write_text(
        json.dumps(leaderboard_df.to_dict(orient="records"), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    md_lines = [
        "# Benchmark Report",
        "",
        f"- Golden split: `{split}`",
        f"- Models evaluated: {leaderboard_df.shape[0]}",
        "",
        "| model_alias | final_score | strict_score | semantic_score | structured_valid_rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for _, row in leaderboard_df.iterrows():
        md_lines.append(
            f"| {row['model_alias']} | {row['final_score']:.4f} | {row['strict_score']:.4f} | "
            f"{row['semantic_score']:.4f} | {row['structured_valid_rate']:.4f} |"
        )

    (out_dir / "benchmark_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    summary = {
        "golden_jsonl": str(Path(golden_jsonl).resolve()),
        "inference_run_dir": str(run_dir.resolve()),
        "split": split,
        "strict_weight": strict_weight,
        "semantic_weight": semantic_weight,
        "judge_enabled": judge_provider is not None,
        "leaderboard_csv": str(leaderboard_csv.resolve()),
        "leaderboard_json": str(leaderboard_json.resolve()),
    }

    (out_dir / "evaluation_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return summary
