"""Build final analytics dataset from best model predictions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..constants import LIST_SIGNAL_FIELDS
from ..io_utils import ensure_dir, read_jsonl, write_jsonl
from ..schema import normalize_extraction_payload


def _select_model_alias(
    inference_run_dir: Path,
    leaderboard_csv: str | Path | None,
    explicit_model_alias: str | None,
) -> str:
    if explicit_model_alias:
        return explicit_model_alias

    if leaderboard_csv:
        p = Path(leaderboard_csv)
        if p.exists():
            df = pd.read_csv(p)
            if not df.empty and "model_alias" in df.columns:
                return str(df.iloc[0]["model_alias"])

    model_dirs = [d.name for d in inference_run_dir.iterdir() if d.is_dir() and (d / "predictions.jsonl").exists()]
    if not model_dirs:
        raise ValueError(f"No model dirs found in inference_run_dir: {inference_run_dir}")
    return sorted(model_dirs)[0]


def _flatten_payload(payload: dict[str, Any]) -> dict[str, Any]:
    row: dict[str, Any] = {}

    deployment = payload.get("deployment_scope") or {}
    row["deployment_scope_status"] = deployment.get("status", "uncertain")
    row["deployment_scope_value"] = deployment.get("value", "")

    for field in LIST_SIGNAL_FIELDS:
        value = payload.get(field) or {}
        row[f"{field}_status"] = value.get("status", "uncertain")
        items = value.get("items") if isinstance(value.get("items"), list) else []
        row[f"{field}_items"] = "; ".join(str(x) for x in items)

    row["maturity_level"] = payload.get("maturity_level", 0)
    row["maturity_rationale"] = payload.get("maturity_rationale", "")
    row["confidence"] = payload.get("confidence", 0.0)
    row["evidence_spans"] = json.dumps(payload.get("evidence_spans", []), ensure_ascii=False)
    row["fields_payload"] = json.dumps(payload, ensure_ascii=False)

    return row


def build_final_dataset(
    dataset_base_csv: str | Path,
    inference_run_dir: str | Path,
    output_csv: str | Path,
    output_jsonl: str | Path,
    model_alias: str | None = None,
    leaderboard_csv: str | Path | None = None,
) -> dict[str, Any]:
    dataset_df = pd.read_csv(dataset_base_csv)
    run_dir = Path(inference_run_dir)

    selected_alias = _select_model_alias(run_dir, leaderboard_csv, model_alias)

    pred_path = run_dir / selected_alias / "predictions.jsonl"
    if not pred_path.exists():
        raise FileNotFoundError(f"Prediction file not found: {pred_path}")

    pred_rows = read_jsonl(pred_path)
    pred_map: dict[str, dict[str, Any]] = {}
    for row in pred_rows:
        doc_id = str(row.get("doc_id") or "")
        payload, _ = normalize_extraction_payload(row.get("fields_payload"))
        pred_map[doc_id] = {
            "model_alias": selected_alias,
            "run_id": row.get("run_id", ""),
            "structured_valid": bool(row.get("structured_valid", False)),
            "raw_response": row.get("raw_response", ""),
            **_flatten_payload(payload),
        }

    merged_rows: list[dict[str, Any]] = []
    for _, base in dataset_df.iterrows():
        doc_id = str(base.get("doc_id") or "")
        pred = pred_map.get(doc_id)
        if pred is None:
            continue

        row = {k: base[k] for k in dataset_df.columns}
        row.update(pred)
        merged_rows.append(row)

    output_csv_path = Path(output_csv)
    output_jsonl_path = Path(output_jsonl)
    ensure_dir(output_csv_path.parent)
    ensure_dir(output_jsonl_path.parent)

    final_df = pd.DataFrame(merged_rows)
    final_df.to_csv(output_csv_path, index=False, encoding="utf-8")
    write_jsonl(output_jsonl_path, merged_rows)

    summary = {
        "model_alias": selected_alias,
        "rows": int(final_df.shape[0]),
        "output_csv": str(output_csv_path.resolve()),
        "output_jsonl": str(output_jsonl_path.resolve()),
    }

    (output_csv_path.parent / "final_dataset_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return summary
