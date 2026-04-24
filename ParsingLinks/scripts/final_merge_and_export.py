# final_merge_and_export.py
# Merge dsVKR_http.xlsx + medium.jsonl + a2_playwright.jsonl into a single master table,
# pick best text per URL, export texts to files, and create unresolved list.
#
# Install:
#   pip install -U pandas openpyxl
#
# Run (example):
#   python .\scripts\final_merge_and_export.py `
#     --http_xlsx .\out\99_final\dsVKR_http.xlsx `
#     --medium_jsonl .\out\02_medium\medium.jsonl `
#     --a2_jsonl .\out\03_a2\a2_playwright.jsonl `
#     --out_dir .\out\final

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import pandas as pd

from scraping_utils import canonicalize_url, sha1_text, safe_slug, read_jsonl


def domain_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""

def normalize_source_http(df_http: pd.DataFrame) -> pd.DataFrame:
    """
    Expected dsVKR_http.xlsx columns (as in your file):
    Link, url_norm, base_domain, http_word_count, http_text_len, http_title, http_final_url, http_text_path, ...
    """
    df = df_http.copy()

    # URL fields
    df["url_original"] = df.get("Link")
    df["url_canonical"] = df.get("url_norm", df.get("Link")).apply(canonicalize_url)
    df["url_final"] = df.get("http_final_url", df.get("Link"))
    df["domain"] = df.get("base_domain_http", df.get("base_domain", df["url_final"].apply(domain_of)))

    # Text fields: if http_text_path exists, we won't load big text into memory by default.
    df["title"] = df.get("http_title", df.get("Title"))
    df["word_count"] = pd.to_numeric(df.get("http_word_count", 0), errors="coerce").fillna(0).astype(int)
    df["text_len"] = pd.to_numeric(df.get("http_text_len", 0), errors="coerce").fillna(0).astype(int)

    # We don't have raw text in the xlsx (only path) => keep text empty, but keep path.
    df["text"] = None
    df["text_path"] = df.get("http_text_path")

    df["source"] = "http"
    df["extraction_method"] = "http"
    df["error"] = None
    df["flags_json"] = "{}"

    keep_cols = [
        "url_original","url_canonical","url_final","domain","source","extraction_method",
        "title","text","text_path","word_count","text_len","error","flags_json"
    ]

    # Also preserve your original metadata if present (company, industry, etc.)
    extra_cols = [c for c in df.columns if c not in keep_cols]
    return df[keep_cols + extra_cols]

def normalize_source_jsonl(rows: List[Dict[str, Any]], source_name: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # standardize url fields
    df["url_original"] = df.get("url_original", df.get("url", ""))
    df["url_final"] = df.get("url_final", df.get("final_url", df.get("url_original", "")))
    df["url_canonical"] = df.get("url_canonical", df["url_original"]).fillna(df["url_final"]).apply(canonicalize_url)
    df["domain"] = df.get("domain", df["url_final"].apply(domain_of))

    df["source"] = source_name
    df["title"] = df.get("title")
    df["text"] = df.get("text")
    df["word_count"] = pd.to_numeric(df.get("word_count", 0), errors="coerce").fillna(0).astype(int)
    df["text_len"] = pd.to_numeric(df.get("text_len", 0), errors="coerce").fillna(0).astype(int)
    df["error"] = df.get("error")
    df["extraction_method"] = df.get("extraction_method", source_name)

    # flags could be dict -> json string
    def flags_to_json(x):
        try:
            if isinstance(x, dict):
                return json.dumps(x, ensure_ascii=False)
            if isinstance(x, str) and x.strip():
                return x
        except Exception:
            pass
        return "{}"

    df["flags_json"] = df.get("flags", "{}").apply(flags_to_json)

    df["text_path"] = None

    keep_cols = [
        "url_original","url_canonical","url_final","domain","source","extraction_method",
        "title","text","text_path","word_count","text_len","error","flags_json"
    ]
    extra_cols = [c for c in df.columns if c not in keep_cols]
    return df[keep_cols + extra_cols]

def quality_score(row: pd.Series) -> float:
    """
    Simple & robust: favor longer texts, penalize likely junk.
    Safe against NaN/float in text/title.
    """
    wc = int(row.get("word_count", 0) or 0)
    tl = int(row.get("text_len", 0) or 0)

    title_raw = row.get("title")
    title = "" if title_raw is None or (isinstance(title_raw, float) and pd.isna(title_raw)) else str(title_raw)

    text_raw = row.get("text")
    if text_raw is None or (isinstance(text_raw, float) and pd.isna(text_raw)):
        text = ""
    else:
        text = str(text_raw)

    # if no inline text (HTTP-only path), score based on wc/tl
    if not text and wc == 0 and tl == 0:
        return -1e9

    head = text[:1200].lower()

    junk_penalty = 0
    for bad in ["cookie", "subscribe", "sign in", "log in", "enable javascript", "access denied", "captcha"]:
        if bad in head:
            junk_penalty += 200

    title_bonus = 50 if (title and len(title) >= 8) else 0
    return (wc * 1.0) + (tl / 200.0) + title_bonus - junk_penalty

def source_rank(source: str, method: str) -> int:
    # lower is better
    if source == "http":
        return 0
    if source == "medium":
        # prefer amp/json over playwright if method contains it
        if "amp" in (method or ""):
            return 1
        if "json" in (method or ""):
            return 2
        return 3
    if source == "a2":
        return 4
    return 9

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--http_xlsx", required=True, type=str)
    ap.add_argument("--medium_jsonl", required=True, type=str)
    ap.add_argument("--a2_jsonl", required=True, type=str)
    ap.add_argument("--out_dir", required=True, type=str)
    ap.add_argument("--min_words", default=300, type=int)
    ap.add_argument("--min_chars", default=1000, type=int)
    ap.add_argument("--export_xlsx", action="store_true", help="Also export best_per_url.xlsx (heavier)")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    texts_dir = out_dir / "texts"
    texts_dir.mkdir(parents=True, exist_ok=True)

    # Load sources
    df_http_raw = pd.read_excel(Path(args.http_xlsx))
    df_http = normalize_source_http(df_http_raw)

    df_med = normalize_source_jsonl(read_jsonl(Path(args.medium_jsonl)), "medium")
    df_a2  = normalize_source_jsonl(read_jsonl(Path(args.a2_jsonl)), "a2")

    frames = [df for df in [df_http, df_med, df_a2] if df is not None and not df.empty]
    df_all = pd.concat(frames, ignore_index=True, sort=False)

    # Normalize metrics for any row with inline text but missing counts
    df_all["text"] = df_all["text"].where(df_all["text"].notna(), None)
    df_all["word_count"] = pd.to_numeric(df_all["word_count"], errors="coerce").fillna(0).astype(int)
    df_all["text_len"] = pd.to_numeric(df_all["text_len"], errors="coerce").fillna(0).astype(int)

    # If text exists, ensure counts at least computed
    def recompute_counts(row):
        txt = row.get("text")
        if isinstance(txt, str) and txt.strip():
            if row.get("text_len", 0) == 0:
                row["text_len"] = len(txt)
            if row.get("word_count", 0) == 0:
                row["word_count"] = len(re.findall(r"\S+", txt))
        return row

    df_all = df_all.apply(recompute_counts, axis=1)

    # Determine "good"
    df_all["good"] = (
        df_all["word_count"].astype(int) >= int(args.min_words)
    ) & (
        df_all["text_len"].astype(int) >= int(args.min_chars)
    )

    # Quality + rank
    # Normalize NaN -> None for text/title
    df_all["text"] = df_all["text"].where(df_all["text"].notna(), None)
    df_all["title"] = df_all["title"].where(df_all["title"].notna(), None)
    df_all["qscore"] = df_all.apply(quality_score, axis=1)
    df_all["srank"] = df_all.apply(lambda r: source_rank(str(r.get("source","")), str(r.get("extraction_method",""))), axis=1)

    # Pick best per canonical URL:
    # 1) prefer good
    # 2) higher qscore
    # 3) lower source rank
    # 4) higher word_count
    df_all_sorted = df_all.sort_values(
        by=["url_canonical", "good", "qscore", "srank", "word_count", "text_len"],
        ascending=[True, False, False, True, False, False],
        kind="mergesort"
    )
    best = df_all_sorted.groupby("url_canonical", as_index=False).head(1).copy()
    # -----------------------------
    # Export texts ONLY for GOOD records
    # -----------------------------
    best_export = best[best["good"] == True].copy()

    text_paths: list[str] = []
    text_hashes: list[str] = []

    for i, row in best_export.iterrows():
        src = str(row.get("source", ""))
        txt_raw = row.get("text")
        existing_path = row.get("text_path")  # for HTTP this is usually http_text_path

        # Build output filename
        dom = safe_slug(row.get("domain", ""), 50)
        title_slug = safe_slug(row.get("title", ""), 60)
        doc_id = f"{i:04d}"
        out_fpath = texts_dir / f"{doc_id}_{dom}_{title_slug}.txt"

        # 1) HTTP: read from existing_path and copy into texts/
        if isinstance(existing_path, str) and existing_path.strip():
            p = Path(existing_path)

            # If your http_text_path is RELATIVE and not found, uncomment and set base:
            # p = (Path(__file__).resolve().parents[1] / existing_path).resolve()
            # or:
            # p = (Path.cwd() / existing_path).resolve()

            if p.exists():
                txt = p.read_text(encoding="utf-8", errors="ignore").strip()
                if txt:
                    out_fpath.write_text(txt, encoding="utf-8")
                    text_paths.append(str(out_fpath))
                    text_hashes.append(sha1_text(txt))
                    continue

            # file missing or empty
            text_paths.append("")
            text_hashes.append("")
            continue

        # 2) Medium / A2: use inline text
        if txt_raw is None or (isinstance(txt_raw, float) and pd.isna(txt_raw)):
            text_paths.append("")
            text_hashes.append("")
            continue

        txt = str(txt_raw).strip()
        if not txt:
            text_paths.append("")
            text_hashes.append("")
            continue

        out_fpath.write_text(txt, encoding="utf-8")
        text_paths.append(str(out_fpath))
        text_hashes.append(sha1_text(txt))

    # Add columns to best_export (IMPORTANT: before merge)
    best_export["final_text_path"] = text_paths
    best_export["text_sha1"] = text_hashes

    # Merge back into full best
    best = best.merge(
        best_export[["url_canonical", "final_text_path", "text_sha1"]],
        on="url_canonical",
        how="left"
    )
    best["final_text_path"] = best["final_text_path"].fillna("")
    best["text_sha1"] = best["text_sha1"].fillna("")


    # Unresolved: not good or missing path
    unresolved = best[(best["good"] == False) | (best["final_text_path"].astype(str).str.len() == 0)].copy()

    # Save outputs
    union_csv = out_dir / "records_union.csv"
    best_csv = out_dir / "best_per_url.csv"
    unresolved_csv = out_dir / "unresolved.csv"

    df_all.to_csv(union_csv, index=False, encoding="utf-8")
    best.to_csv(best_csv, index=False, encoding="utf-8")
    unresolved.to_csv(unresolved_csv, index=False, encoding="utf-8")

    if args.export_xlsx:
        best_xlsx = out_dir / "best_per_url.xlsx"
        with pd.ExcelWriter(best_xlsx, engine="openpyxl") as w:
            best.to_excel(w, index=False, sheet_name="best_per_url")
            unresolved.to_excel(w, index=False, sheet_name="unresolved")

    print("Wrote:")
    print(" ", union_csv)
    print(" ", best_csv)
    print(" ", unresolved_csv)
    if args.export_xlsx:
        print(" ", out_dir / "best_per_url.xlsx")
    print("Texts dir:", texts_dir)

if __name__ == "__main__":
    main()