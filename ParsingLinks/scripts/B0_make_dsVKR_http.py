# -*- coding: utf-8 -*-
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import tldextract

from scraping_utils import sha1_text


MEDIUM_HASH_SUFFIX = re.compile(r"-[0-9a-f]{10,14}$", re.I)


def normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*://", u):
        u = "https://" + u
    return u


def base_domain(url: str) -> str:
    u = normalize_url(url)
    ext = tldextract.extract(u)
    if ext.suffix:
        return f"{ext.domain}.{ext.suffix}".lower()
    return ext.domain.lower()


def is_medium_backed(url: str) -> bool:
    u = normalize_url(url)
    d = (urlparse(u).netloc or "").lower()
    if d.startswith("www."):
        d = d[4:]
    if d == "medium.com":
        return True
    p = urlparse(u).path.rstrip("/")
    if not p:
        return False
    last = p.split("/")[-1]
    return bool(MEDIUM_HASH_SUFFIX.search(last))


def load_bucket_jsonl(path: str) -> pd.DataFrame:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # normalize
    df["url_norm"] = df["url"].astype(str).map(normalize_url)
    for col in ["status_code", "text_len", "word_count"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        else:
            df[col] = 0

    if "text" not in df.columns:
        df["text"] = ""
    df["text"] = df["text"].fillna("").astype(str)

    # best per URL = max word_count, then max text_len
    df = df.sort_values(["url_norm", "word_count", "text_len"], ascending=[True, False, False])
    df = df.drop_duplicates(subset=["url_norm"], keep="first").copy()

    df["base_domain"] = df["url_norm"].map(base_domain)
    df["is_medium_candidate"] = df["url_norm"].map(is_medium_backed)

    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_xlsx", required=True)
    ap.add_argument("--url_col", default="Link")
    ap.add_argument("--bucket_jsonl", required=True)
    ap.add_argument("--out_dir", default="./out/99_final")
    ap.add_argument("--min_words_ok", type=int, default=300)
    ap.add_argument("--min_chars_ok", type=int, default=1000)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    text_store = out_dir / "text_store" / "http"
    text_store.mkdir(parents=True, exist_ok=True)

    # Load main dataset
    ds = pd.read_excel(args.input_xlsx)
    if args.url_col not in ds.columns:
        raise ValueError(f"Column '{args.url_col}' not found. Found: {list(ds.columns)}")

    ds["url_norm"] = ds[args.url_col].astype(str).map(normalize_url)
    ds["base_domain"] = ds["url_norm"].map(base_domain)

    # Load bucket jsonl
    b = load_bucket_jsonl(args.bucket_jsonl)
    if b.empty:
        raise ValueError("bucket_jsonl is empty or not parsed")

    # Quality rule for "http good text"
    b["http_good"] = (
        (b["status_code"] == 200)
        & (b["word_count"] >= args.min_words_ok)
        & (b["text_len"] >= args.min_chars_ok)
    )

    good = b[b["http_good"]].copy()

    # Write text files & paths
    def write_text(row):
        u = row["url_norm"]
        txt = row["text"]
        fn = sha1_text(u) + ".txt"
        p = text_store / fn
        if not p.exists():
            p.write_text(txt, encoding="utf-8", errors="ignore")
        return str(p)

    good["http_text_path"] = good.apply(write_text, axis=1)

    # Merge back into dsVKR
    merged = ds.merge(
        good[["url_norm", "http_text_path", "word_count", "text_len", "title", "final_url", "base_domain"]],
        on="url_norm",
        how="left",
        suffixes=("", "_http"),
    )

    merged = merged.rename(columns={
        "word_count": "http_word_count",
        "text_len": "http_text_len",
        "title": "http_title",
        "final_url": "http_final_url",
    })

    ds_http = merged[merged["http_text_path"].notna()].copy()
    ds_todo = merged[merged["http_text_path"].isna()].copy()

    # todo lists
    todo_medium = ds_todo[ds_todo["url_norm"].map(is_medium_backed)].copy()
    todo_a2 = ds_todo[~ds_todo["url_norm"].map(is_medium_backed)].copy()

    # Save outputs
    ds_http_path = out_dir / "dsVKR_http.xlsx"
    ds_http.to_excel(ds_http_path, index=False)

    todo_medium_path = out_dir / "todo_medium.csv"
    todo_a2_path = out_dir / "todo_a2.csv"

    todo_medium[["url_norm", "base_domain"]].rename(columns={"url_norm": "url"}).to_csv(todo_medium_path, index=False, encoding="utf-8-sig")
    todo_a2[["url_norm", "base_domain"]].rename(columns={"url_norm": "url"}).to_csv(todo_a2_path, index=False, encoding="utf-8-sig")

    report = {
        "total_rows_in_dsVKR": int(len(ds)),
        "bucket_rows_unique_urls": int(len(b)),
        "http_good_urls": int(good["url_norm"].nunique()),
        "dsVKR_http_rows": int(len(ds_http)),
        "todo_rows": int(len(ds_todo)),
        "todo_medium_rows": int(len(todo_medium)),
        "todo_a2_rows": int(len(todo_a2)),
        "quality_rule": {"min_words_ok": args.min_words_ok, "min_chars_ok": args.min_chars_ok},
    }
    (out_dir / "report_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK")
    print(f"- {ds_http_path}")
    print(f"- {todo_medium_path}")
    print(f"- {todo_a2_path}")
    print(f"- {out_dir / 'report_summary.json'}")


if __name__ == "__main__":
    main()
