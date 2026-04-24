"""Build immutable dataset_base from final merged CSV + text files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..io_utils import ensure_dir, normalize_year, read_text, to_bool, write_jsonl


REQUIRED_INPUT_COLUMNS = (
    "url_canonical",
    "title",
    "word_count",
    "text_len",
    "Company",
    "Industry",
    "Year",
    "merged_text_path",
    "good",
)


def _resolve_text_path(raw_path: str, csv_path: Path, project_root: Path) -> Path | None:
    raw = (raw_path or "").strip()
    if not raw:
        return None

    raw_candidate = Path(raw)
    candidates: list[Path] = []

    if raw_candidate.is_absolute():
        candidates.append(raw_candidate)

    # Relative to CSV location (usually ParsingLinks/out/final).
    candidates.append((csv_path.parent / raw_candidate).resolve())
    # Relative to project root (ParsingLinks).
    candidates.append((project_root / raw_candidate).resolve())

    # Current export stores files in out/final/texts, but CSV may contain merged/texts.
    basename = raw_candidate.name
    if basename:
        candidates.append((project_root / "out" / "final" / "texts" / basename).resolve())

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def _normalize_record(row: pd.Series, text_path: Path, doc_id: str) -> dict[str, Any]:
    text = read_text(text_path).strip()
    word_count = int(pd.to_numeric(row.get("word_count"), errors="coerce") or 0)
    text_len = int(pd.to_numeric(row.get("text_len"), errors="coerce") or 0)

    return {
        "doc_id": doc_id,
        "url_canonical": str(row.get("url_canonical") or "").strip(),
        "company": str(row.get("Company") or "").strip(),
        "industry": str(row.get("Industry") or "").strip(),
        "year": normalize_year(row.get("Year")),
        "title": str(row.get("title") or "").strip(),
        "text": text,
        "text_path": str(text_path),
        "word_count": word_count,
        "text_len": text_len,
    }


def build_dataset_base(
    input_csv_path: str | Path,
    output_csv_path: str | Path,
    output_jsonl_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    input_csv = Path(input_csv_path)
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    project_root = Path(__file__).resolve().parents[3]

    df = pd.read_csv(input_csv)
    missing_columns = [c for c in REQUIRED_INPUT_COLUMNS if c not in df.columns]
    if missing_columns:
        raise ValueError(f"Missing required input columns: {missing_columns}")

    total_rows = int(df.shape[0])
    df = df[df["good"].apply(to_bool)].copy()
    good_rows = int(df.shape[0])

    duplicate_url_count = int(df.duplicated(subset=["url_canonical"]).sum())

    df = df.sort_values(by=["url_canonical", "title"], kind="mergesort").reset_index(drop=True)

    records: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []

    for idx, row in df.iterrows():
        doc_id = f"DOC{idx + 1:06d}"
        resolved = _resolve_text_path(str(row.get("merged_text_path") or ""), input_csv, project_root)
        if resolved is None:
            unresolved.append(
                {
                    "doc_id": doc_id,
                    "url_canonical": str(row.get("url_canonical") or "").strip(),
                    "reason": "text_file_not_found",
                    "raw_merged_text_path": str(row.get("merged_text_path") or "").strip(),
                }
            )
            continue

        record = _normalize_record(row, resolved, doc_id)
        if not record["text"]:
            unresolved.append(
                {
                    "doc_id": doc_id,
                    "url_canonical": record["url_canonical"],
                    "reason": "text_is_empty",
                    "raw_merged_text_path": str(row.get("merged_text_path") or "").strip(),
                }
            )
            continue

        # Keep one record per canonical URL.
        if any(r["url_canonical"] == record["url_canonical"] for r in records):
            unresolved.append(
                {
                    "doc_id": doc_id,
                    "url_canonical": record["url_canonical"],
                    "reason": "duplicate_url_canonical",
                    "raw_merged_text_path": str(row.get("merged_text_path") or "").strip(),
                }
            )
            continue

        records.append(record)

    records_df = pd.DataFrame(records)

    output_csv = Path(output_csv_path)
    output_jsonl = Path(output_jsonl_path)
    output_report = Path(report_path)

    ensure_dir(output_csv.parent)
    ensure_dir(output_jsonl.parent)
    ensure_dir(output_report.parent)

    if not records_df.empty:
        records_df.to_csv(output_csv, index=False, encoding="utf-8")
    else:
        pd.DataFrame(
            columns=[
                "doc_id",
                "url_canonical",
                "company",
                "industry",
                "year",
                "title",
                "text",
                "text_path",
                "word_count",
                "text_len",
            ]
        ).to_csv(output_csv, index=False, encoding="utf-8")

    write_jsonl(output_jsonl, records)

    unresolved_path = output_report.parent / "dataset_base_unresolved.csv"
    pd.DataFrame(unresolved).to_csv(unresolved_path, index=False, encoding="utf-8")

    report = {
        "input_csv": str(input_csv.resolve()),
        "total_input_rows": total_rows,
        "good_rows": good_rows,
        "dataset_base_rows": len(records),
        "duplicate_url_rows_in_input": duplicate_url_count,
        "unresolved_rows": len(unresolved),
        "output_csv": str(output_csv.resolve()),
        "output_jsonl": str(output_jsonl.resolve()),
        "unresolved_csv": str(unresolved_path.resolve()),
    }

    output_report.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
