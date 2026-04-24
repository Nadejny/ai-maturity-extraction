"""Inference runner for extraction models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs):
        return iterable

from ..io_utils import ensure_dir, read_jsonl, utc_run_id, write_jsonl
from ..prompting import build_extraction_prompt, build_extraction_prompt_ceiling
from ..providers import build_provider, load_model_registry
from ..schema import extract_error_flags, normalize_extraction_payload, payload_status_snapshot


_PROMPT_BUILDERS = {
    "v1": build_extraction_prompt,
    "baseline": build_extraction_prompt,
    "ceiling": build_extraction_prompt_ceiling,
    "v2": build_extraction_prompt_ceiling,
}


DEFAULT_INFERENCE_SETTINGS = {
    "temperature": 0.0,
    "top_p": 0.95,
    "max_output_tokens": 2048,
    "json_mode": True,
    "max_text_chars": 16000,
}


def extract_first_json_object(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None

    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for idx, ch in enumerate(text):
        if ch != "{":
            continue
        fragment = text[idx:]
        try:
            value, _ = decoder.raw_decode(fragment)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    return None


def _load_settings(path: str | Path | None) -> dict[str, Any]:
    settings = dict(DEFAULT_INFERENCE_SETTINGS)
    if path is None:
        return settings
    p = Path(path)
    if not p.exists():
        return settings
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return settings
    if isinstance(raw, dict):
        settings.update(raw)
    return settings


def _prepare_dataset_rows(
    dataset_base_csv: str | Path,
    max_docs: int | None = None,
    doc_ids_filter: list[str] | None = None,
) -> list[dict[str, Any]]:
    df = pd.read_csv(dataset_base_csv)
    required = {"doc_id", "text"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"dataset_base is missing columns: {sorted(missing)}")

    if doc_ids_filter:
        wanted = {str(d).strip() for d in doc_ids_filter if str(d).strip()}
        df = df[df["doc_id"].astype(str).isin(wanted)].copy()
        df["_order"] = df["doc_id"].astype(str).map({d: i for i, d in enumerate(doc_ids_filter)})
        df = df.sort_values("_order").drop(columns=["_order"])

    rows = df.to_dict(orient="records")
    if max_docs is not None and max_docs > 0:
        rows = rows[:max_docs]
    return rows


def run_inference(
    dataset_base_csv: str | Path,
    model_registry_path: str | Path,
    output_dir: str | Path,
    model_aliases: list[str] | None = None,
    run_id: str | None = None,
    settings_path: str | Path | None = None,
    max_docs: int | None = None,
    skip_existing: bool = False,
    prompt_version: str = "v1",
    doc_ids_filter: list[str] | None = None,
) -> dict[str, Any]:
    settings = _load_settings(settings_path)
    run_id = run_id or utc_run_id("inference")

    model_registry = load_model_registry(model_registry_path)

    if model_aliases:
        selected_aliases = [alias for alias in model_aliases if alias in model_registry]
    else:
        selected_aliases = sorted(model_registry.keys())

    if not selected_aliases:
        raise ValueError("No model aliases selected for inference")

    prompt_builder = _PROMPT_BUILDERS.get(prompt_version)
    if prompt_builder is None:
        raise ValueError(f"Unknown prompt_version: {prompt_version!r}. Options: {sorted(_PROMPT_BUILDERS)}")

    rows = _prepare_dataset_rows(dataset_base_csv, max_docs=max_docs, doc_ids_filter=doc_ids_filter)

    out_root = ensure_dir(Path(output_dir) / run_id)
    log_path = out_root / "inference.log"

    run_summary: dict[str, Any] = {
        "run_id": run_id,
        "dataset_base_csv": str(Path(dataset_base_csv).resolve()),
        "model_registry_path": str(Path(model_registry_path).resolve()),
        "prompt_version": prompt_version,
        "total_docs": len(rows),
        "models": {},
    }

    for alias in selected_aliases:
        cfg = model_registry[alias]
        provider = build_provider(cfg)

        model_dir = ensure_dir(out_root / alias)
        jsonl_path = model_dir / "predictions.jsonl"

        existing_predictions: list[dict[str, Any]] = []
        done_doc_ids: set[str] = set()
        if skip_existing and jsonl_path.exists():
            existing_predictions = read_jsonl(str(jsonl_path))
            done_doc_ids = {str(p.get("doc_id", "")) for p in existing_predictions}
            if done_doc_ids:
                print(f"[{alias}] resuming: {len(done_doc_ids)} existing predictions loaded, skipping them")
        elif not skip_existing and jsonl_path.exists():
            # Fresh run: truncate leftover file from a previous interrupted run.
            jsonl_path.write_text("", encoding="utf-8")

        todo_rows = [r for r in rows if str(r.get("doc_id", "")) not in done_doc_ids] if done_doc_ids else rows
        new_predictions: list[dict[str, Any]] = []

        provider_errors = 0
        parse_errors = 0
        schema_error_rows = 0

        for row in tqdm(todo_rows, desc=f"[{alias}]", unit="doc", dynamic_ncols=True):
            doc_id = str(row.get("doc_id") or "")
            system_prompt, user_prompt = prompt_builder(
                row,
                max_text_chars=int(settings.get("max_text_chars", 16000)),
            )

            raw_text = ""
            latency_ms = 0
            token_usage: dict[str, Any] = {}
            error_tags: list[str] = []
            error_message = ""

            try:
                response = provider.generate(system_prompt, user_prompt, settings=settings)
                raw_text = response.content
                latency_ms = int(response.latency_ms)
                token_usage = response.token_usage
            except Exception as exc:  # pylint: disable=broad-except
                provider_errors += 1
                error_tags.append("provider_error")
                error_message = str(exc)

            parsed = extract_first_json_object(raw_text)
            if parsed is None:
                parse_errors += 1
                error_tags.append("parse_error")
                normalized_payload, schema_errors = normalize_extraction_payload({})
            else:
                normalized_payload, schema_errors = normalize_extraction_payload(parsed)

            if schema_errors:
                schema_error_rows += 1
                error_tags.append("schema_error")

            error_tags.extend(extract_error_flags(raw_text, normalized_payload))

            structured_valid = ("provider_error" not in error_tags) and ("parse_error" not in error_tags) and not schema_errors

            prediction = {
                "doc_id": doc_id,
                "model_alias": alias,
                "run_id": run_id,
                "fields_payload": normalized_payload,
                "confidence": float(normalized_payload.get("confidence", 0.0)),
                "evidence_spans": normalized_payload.get("evidence_spans", []),
                "raw_response": raw_text,
                "latency_ms": latency_ms,
                "token_usage": token_usage,
                "status_snapshot": payload_status_snapshot(normalized_payload),
                "structured_valid": structured_valid,
                "error_tags": error_tags,
                "error_message": error_message,
                "schema_errors": schema_errors,
                "maturity_level": int(normalized_payload.get("maturity_level", 0)),
                "deployment_scope_status": str(
                    (normalized_payload.get("deployment_scope") or {}).get("status") or "uncertain"
                ),
                "deployment_scope_value": str(
                    (normalized_payload.get("deployment_scope") or {}).get("value") or ""
                ),
            }
            new_predictions.append(prediction)

            with jsonl_path.open("a", encoding="utf-8") as pred_f:
                pred_f.write(json.dumps(prediction, ensure_ascii=False) + "\n")

            with log_path.open("a", encoding="utf-8") as log_f:
                log_f.write(json.dumps({
                    "doc_id": doc_id,
                    "model_alias": alias,
                    "latency_ms": latency_ms,
                    "structured_valid": structured_valid,
                    "error_tags": error_tags,
                    "maturity_level": int(normalized_payload.get("maturity_level", 0)),
                }) + "\n")

        predictions = existing_predictions + new_predictions

        csv_rows = []
        for pred in predictions:
            csv_rows.append(
                {
                    "doc_id": pred["doc_id"],
                    "model_alias": pred["model_alias"],
                    "run_id": pred["run_id"],
                    "confidence": pred["confidence"],
                    "maturity_level": pred["maturity_level"],
                    "deployment_scope_status": pred["deployment_scope_status"],
                    "deployment_scope_value": pred["deployment_scope_value"],
                    "structured_valid": pred["structured_valid"],
                    "latency_ms": pred["latency_ms"],
                    "token_usage": json.dumps(pred["token_usage"], ensure_ascii=False),
                    "error_tags": ";".join(pred["error_tags"]),
                    "error_message": pred["error_message"],
                    "schema_errors": ";".join(pred["schema_errors"]),
                    "status_snapshot": json.dumps(pred["status_snapshot"], ensure_ascii=False),
                    "fields_payload": json.dumps(pred["fields_payload"], ensure_ascii=False),
                    "evidence_spans": json.dumps(pred["evidence_spans"], ensure_ascii=False),
                    "raw_response": pred["raw_response"],
                }
            )
        pd.DataFrame(csv_rows).to_csv(model_dir / "predictions.csv", index=False, encoding="utf-8")

        # Compute summary over ALL predictions (existing + new).
        n_rows = len(predictions)
        n_existing = len(existing_predictions)
        valid_count = sum(1 for pred in predictions if pred["structured_valid"])
        avg_latency = round(sum(int(pred["latency_ms"]) for pred in predictions) / max(1, n_rows), 2)

        total_prompt_tokens = sum(int(pred["token_usage"].get("prompt_tokens", 0)) for pred in predictions)
        total_completion_tokens = sum(int(pred["token_usage"].get("completion_tokens", 0)) for pred in predictions)
        total_tokens = sum(int(pred["token_usage"].get("total_tokens", 0)) for pred in predictions)
        total_latency_sec = sum(int(pred["latency_ms"]) for pred in predictions) / 1000

        # Recount errors from combined list so totals are accurate after resume.
        provider_errors = sum(1 for p in predictions if "provider_error" in p.get("error_tags", []))
        parse_errors = sum(1 for p in predictions if "parse_error" in p.get("error_tags", []))
        schema_error_rows = sum(1 for p in predictions if "schema_error" in p.get("error_tags", []))

        error_tag_counts: dict[str, int] = {}
        for pred in predictions:
            for tag in pred.get("error_tags", []):
                error_tag_counts[tag] = error_tag_counts.get(tag, 0) + 1

        print(f"\n[{alias}] done: {valid_count}/{n_rows} valid, "
              f"avg latency {avg_latency}ms, "
              f"errors: provider={provider_errors} parse={parse_errors} schema={schema_error_rows}"
              + (f" (resumed from {n_existing} existing)" if n_existing else ""))

        model_summary = {
            "model_alias": alias,
            "rows": n_rows,
            "structured_valid_rows": valid_count,
            "structured_valid_rate": round(valid_count / max(1, n_rows), 4),
            "provider_error_rows": provider_errors,
            "parse_error_rows": parse_errors,
            "schema_error_rows": schema_error_rows,
            "avg_latency_ms": avg_latency,
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "avg_prompt_tokens": round(total_prompt_tokens / max(1, n_rows), 2),
            "avg_completion_tokens": round(total_completion_tokens / max(1, n_rows), 2),
            "tokens_per_second": round(total_completion_tokens / max(0.001, total_latency_sec), 2),
            "error_tag_counts": error_tag_counts,
            "resumed_from_existing_rows": n_existing,
            "predictions_jsonl": str(jsonl_path.resolve()),
            "predictions_csv": str((model_dir / "predictions.csv").resolve()),
        }

        (model_dir / "run_summary.json").write_text(
            json.dumps(model_summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        run_summary["models"][alias] = model_summary

    run_summary["inference_log"] = str(log_path.resolve())

    run_summary_path = out_root / "run_summary.json"
    run_summary_path.write_text(json.dumps(run_summary, indent=2, ensure_ascii=False), encoding="utf-8")

    return run_summary
