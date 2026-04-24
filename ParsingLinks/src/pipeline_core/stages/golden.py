"""Create stratified golden dataset and annotation scaffold."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from ..constants import DEFAULT_GUIDELINE_VERSION
from ..io_utils import ensure_dir, write_jsonl
from ..schema import empty_payload


def _build_strata(df: pd.DataFrame) -> pd.Series:
    len_bins = pd.qcut(df["text_len"], q=4, labels=False, duplicates="drop")
    len_bins = len_bins.fillna(0).astype(int)
    industry = df["industry"].fillna("").astype(str)
    year = df["year"].fillna("").astype(str)
    return industry + "__" + year + "__len" + len_bins.astype(str)


def _allocate_counts(group_sizes: pd.Series, target: int) -> dict[str, int]:
    if target <= 0:
        return {str(k): 0 for k in group_sizes.index}

    total = int(group_sizes.sum())
    if total == 0:
        return {str(k): 0 for k in group_sizes.index}

    proportions = group_sizes / total * target
    base = proportions.apply(int)

    allocation = {str(k): int(v) for k, v in base.items()}
    assigned = sum(allocation.values())

    remainders = (proportions - base).sort_values(ascending=False)
    for key in remainders.index:
        if assigned >= target:
            break
        k = str(key)
        if allocation[k] < int(group_sizes.loc[key]):
            allocation[k] += 1
            assigned += 1

    # Fill any still missing from largest available groups.
    if assigned < target:
        for key in group_sizes.sort_values(ascending=False).index:
            if assigned >= target:
                break
            k = str(key)
            capacity = int(group_sizes.loc[key]) - allocation[k]
            if capacity <= 0:
                continue
            take = min(capacity, target - assigned)
            allocation[k] += take
            assigned += take

    return allocation


def _sample_by_allocation(df: pd.DataFrame, strata_col: str, allocation: dict[str, int], seed: int) -> pd.DataFrame:
    parts: list[pd.DataFrame] = []
    for stratum, count in allocation.items():
        if count <= 0:
            continue
        chunk = df[df[strata_col] == stratum]
        if chunk.empty:
            continue
        take = min(count, chunk.shape[0])
        parts.append(chunk.sample(n=take, random_state=seed))
    if not parts:
        return df.iloc[0:0].copy()
    sampled = pd.concat(parts, ignore_index=True)
    sampled = sampled.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return sampled


def _assign_split(df: pd.DataFrame, train_n: int, dev_n: int, test_n: int, seed: int) -> pd.DataFrame:
    target_total = train_n + dev_n + test_n
    if df.shape[0] != target_total:
        raise ValueError(f"Split target {target_total} does not match sampled rows {df.shape[0]}")

    strata_col = "_strata"
    group_sizes = df.groupby(strata_col).size()

    train_alloc = _allocate_counts(group_sizes, train_n)

    remaining_df = df.copy()
    remaining_df["split"] = ""

    train_parts: list[pd.DataFrame] = []
    for stratum, count in train_alloc.items():
        if count <= 0:
            continue
        chunk = remaining_df[(remaining_df[strata_col] == stratum) & (remaining_df["split"] == "")]
        if chunk.empty:
            continue
        picked = chunk.sample(n=min(count, chunk.shape[0]), random_state=seed)
        remaining_df.loc[picked.index, "split"] = "train"
        train_parts.append(picked)

    dev_target = dev_n
    remaining_for_dev = remaining_df[remaining_df["split"] == ""]
    dev_group_sizes = remaining_for_dev.groupby(strata_col).size()
    dev_alloc = _allocate_counts(dev_group_sizes, dev_target)

    for stratum, count in dev_alloc.items():
        if count <= 0:
            continue
        chunk = remaining_df[(remaining_df[strata_col] == stratum) & (remaining_df["split"] == "")]
        if chunk.empty:
            continue
        picked = chunk.sample(n=min(count, chunk.shape[0]), random_state=seed)
        remaining_df.loc[picked.index, "split"] = "dev"

    remaining_df.loc[remaining_df["split"] == "", "split"] = "test"

    # deterministic ordering in outputs
    split_order = {"train": 0, "dev": 1, "test": 2}
    remaining_df["_split_order"] = remaining_df["split"].map(split_order)
    remaining_df = remaining_df.sort_values(["_split_order", "doc_id"], kind="mergesort").drop(columns=["_split_order"])

    return remaining_df


def build_golden_dataset(
    dataset_base_csv: str | Path,
    output_dir: str | Path,
    sample_size: int = 180,
    train_n: int = 120,
    dev_n: int = 30,
    test_n: int = 30,
    qa_fraction: float = 0.2,
    seed: int = 42,
    guideline_version: str = DEFAULT_GUIDELINE_VERSION,
) -> dict[str, Any]:
    if train_n + dev_n + test_n != sample_size:
        raise ValueError("train_n + dev_n + test_n must equal sample_size")

    df = pd.read_csv(dataset_base_csv)
    if df.shape[0] < sample_size:
        raise ValueError(f"Not enough rows in dataset_base: {df.shape[0]} < {sample_size}")

    for col in ("doc_id", "industry", "year", "text_len"):
        if col not in df.columns:
            raise ValueError(f"Missing required column in dataset_base: {col}")

    df = df.copy()
    df["_strata"] = _build_strata(df)

    strata_sizes = df.groupby("_strata").size()
    sample_alloc = _allocate_counts(strata_sizes, sample_size)
    sampled = _sample_by_allocation(df, "_strata", sample_alloc, seed)

    if sampled.shape[0] != sample_size:
        # Top-up if allocation had capacity limits.
        missing = sample_size - sampled.shape[0]
        if missing > 0:
            leftover = df[~df["doc_id"].isin(sampled["doc_id"])].copy()
            if leftover.shape[0] < missing:
                raise ValueError("Unable to fill sampled set to target size")
            sampled = pd.concat(
                [sampled, leftover.sample(n=missing, random_state=seed)],
                ignore_index=True,
            )

    sampled = _assign_split(sampled, train_n=train_n, dev_n=dev_n, test_n=test_n, seed=seed)

    payload_template = empty_payload()
    sampled["annotator_id"] = ""
    sampled["qa_status"] = "pending"
    sampled["guideline_version"] = guideline_version
    sampled["gold_fields_payload"] = json.dumps(payload_template, ensure_ascii=False)

    qa_n = max(1, int(round(sample_size * qa_fraction)))
    qa_sample = sampled.sample(n=min(qa_n, sampled.shape[0]), random_state=seed).copy()

    out_dir = ensure_dir(output_dir)
    golden_csv = out_dir / "golden.csv"
    golden_jsonl = out_dir / "golden.jsonl"
    qa_csv = out_dir / "golden_qa_sample.csv"

    columns = [
        "doc_id",
        "split",
        "annotator_id",
        "qa_status",
        "guideline_version",
        "gold_fields_payload",
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

    sampled[columns].to_csv(golden_csv, index=False, encoding="utf-8")
    qa_sample[columns].to_csv(qa_csv, index=False, encoding="utf-8")

    jsonl_rows: list[dict[str, Any]] = []
    for _, row in sampled[columns].iterrows():
        payload_raw = row["gold_fields_payload"]
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) and payload_raw else payload_template
        jsonl_rows.append(
            {
                "doc_id": row["doc_id"],
                "split": row["split"],
                "annotator_id": row["annotator_id"],
                "qa_status": row["qa_status"],
                "guideline_version": row["guideline_version"],
                "gold_fields_payload": payload,
                "url_canonical": row["url_canonical"],
                "company": row["company"],
                "industry": row["industry"],
                "year": row["year"],
                "title": row["title"],
                "text": row["text"],
                "text_path": row["text_path"],
                "word_count": int(row["word_count"]),
                "text_len": int(row["text_len"]),
            }
        )

    write_jsonl(golden_jsonl, jsonl_rows)

    for split_name in ("train", "dev", "test"):
        split_path = out_dir / f"golden_{split_name}.csv"
        sampled[sampled["split"] == split_name][columns].to_csv(split_path, index=False, encoding="utf-8")

    locked_test_ids = out_dir / "golden_test_locked_ids.txt"
    test_ids = sampled[sampled["split"] == "test"]["doc_id"].astype(str).tolist()
    locked_test_ids.write_text("\n".join(test_ids) + "\n", encoding="utf-8")

    report = {
        "dataset_base_rows": int(df.shape[0]),
        "sample_size": int(sampled.shape[0]),
        "train_rows": int((sampled["split"] == "train").sum()),
        "dev_rows": int((sampled["split"] == "dev").sum()),
        "test_rows": int((sampled["split"] == "test").sum()),
        "qa_sample_rows": int(qa_sample.shape[0]),
        "guideline_version": guideline_version,
        "golden_csv": str(golden_csv.resolve()),
        "golden_jsonl": str(golden_jsonl.resolve()),
        "qa_sample_csv": str(qa_csv.resolve()),
    }

    report_path = out_dir / "golden_build_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report
