# export_text_store.py
# Export texts from medium.jsonl and a2_playwright.jsonl into text_store folders + index.csv

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlparse

from scraping_utils import canonicalize_url, safe_slug, read_jsonl

def get_flag_json(flags_val: Any) -> str:
    try:
        if isinstance(flags_val, dict):
            return json.dumps(flags_val, ensure_ascii=False)
        if isinstance(flags_val, str) and flags_val.strip():
            return flags_val
    except Exception:
        pass
    return "{}"

def export_text_store(
    jsonl_path: Path,
    out_dir: Path,
    source_name: str,
    min_words: int = 300,
    min_chars: int = 1000,
    export_all: bool = False,   # если True — сохраняем даже too_short; если False — только good
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    store_dir = out_dir / "text_store"
    store_dir.mkdir(parents=True, exist_ok=True)

    rows = read_jsonl(jsonl_path)
    index_path = store_dir / "index.csv"

    with index_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "doc_id",
                "source",
                "url_original",
                "url_canonical",
                "url_final",
                "domain",
                "title",
                "word_count",
                "text_len",
                "error",
                "flags_json",
                "text_file",
            ],
        )
        w.writeheader()

        doc_id = 0
        saved = 0

        for r in rows:
            url_original = (r.get("url_original") or r.get("url") or "").strip()
            url_final = (r.get("url_final") or r.get("final_url") or url_original).strip()
            url_canonical = canonicalize_url(r.get("url_canonical") or url_final or url_original)
            domain = (r.get("domain") or urlparse(url_final or url_original).netloc or "").lower()
            title = r.get("title") or ""
            text = r.get("text")
            wc = int(r.get("word_count") or 0)
            tlen = int(r.get("text_len") or (len(text) if isinstance(text, str) else 0))
            error = r.get("error")
            flags_json = get_flag_json(r.get("flags"))

            # good по длине/словам (НЕ учитываем error, потому что он часто ложный/технический)
            is_good = isinstance(text, str) and (wc >= min_words) and (tlen >= min_chars)

            # если export_all=False, сохраняем только good
            if not export_all and not is_good:
                continue

            if not isinstance(text, str) or not text.strip():
                continue

            doc_id += 1
            fname = f"{doc_id:04d}_{safe_slug(domain, 40)}_{safe_slug(title, 60)}.txt"
            fpath = store_dir / fname
            fpath.write_text(text, encoding="utf-8")

            w.writerow({
                "doc_id": f"{doc_id:04d}",
                "source": source_name,
                "url_original": url_original,
                "url_canonical": url_canonical,
                "url_final": url_final,
                "domain": domain,
                "title": title,
                "word_count": wc,
                "text_len": tlen,
                "error": error if error is not None else "",
                "flags_json": flags_json,
                "text_file": str(fpath),
            })
            saved += 1

    print(f"[{source_name}] saved texts: {saved} -> {store_dir}")
    return store_dir

def copy_store_to_final(store_dir: Path, final_dir: Path) -> None:
    final_dir.mkdir(parents=True, exist_ok=True)
    # copy all txt + index.csv
    for p in store_dir.glob("*"):
        if p.is_file() and (p.suffix.lower() in {".txt", ".csv"}):
            (final_dir / p.name).write_bytes(p.read_bytes())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--medium_jsonl", default=r".\out\02_medium\medium.jsonl")
    ap.add_argument("--a2_jsonl", default=r".\out\03_a2\a2_playwright.jsonl")
    ap.add_argument("--out_medium", default=r".\out\02_medium")
    ap.add_argument("--out_a2", default=r".\out\03_a2")
    ap.add_argument("--final_text_store", default=r".\out\99_final\text_store")
    ap.add_argument("--min_words", type=int, default=300)
    ap.add_argument("--min_chars", type=int, default=1000)
    ap.add_argument("--export_all", action="store_true", help="Export even too_short/errored if text exists")
    ap.add_argument("--copy_to_final", action="store_true", help="Also copy stores into out/99_final/text_store/{medium,a2}")
    args = ap.parse_args()

    store_medium = export_text_store(
        jsonl_path=Path(args.medium_jsonl),
        out_dir=Path(args.out_medium),
        source_name="medium",
        min_words=args.min_words,
        min_chars=args.min_chars,
        export_all=args.export_all,
    )

    store_a2 = export_text_store(
        jsonl_path=Path(args.a2_jsonl),
        out_dir=Path(args.out_a2),
        source_name="a2",
        min_words=args.min_words,
        min_chars=args.min_chars,
        export_all=args.export_all,
    )

    if args.copy_to_final:
        base = Path(args.final_text_store)
        copy_store_to_final(store_medium, base / "medium")
        copy_store_to_final(store_a2, base / "a2")
        print(f"[final] copied into: {base / 'medium'} and {base / 'a2'}")

if __name__ == "__main__":
    main()