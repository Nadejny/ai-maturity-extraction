# B2_a2_playwright.py
# Based on your B1_medium_playwright.py structure, but adapted for todo_a2.csv (browser-only A2).
#
# Goal:
#   - Read URLs from out/99_final/todo_a2.csv (or any csv with a URL column)
#   - Skip YouTube links (for now)
#   - Use Playwright persistent profile in out_dir/pw_profile (safe even if Chrome is open)
#   - Extract article/main text (+ optional trafilatura fallback if installed)
#   - Save:
#       out_dir/a2_playwright.jsonl
#       out_dir/a2_errors.csv
#       out_dir/debug/*.html + *.png on failures
#
# Install:
#   pip install -U playwright beautifulsoup4 lxml
#   python -m playwright install chromium
# Optional (recommended):
#   pip install -U trafilatura
#
# Run example:
#   python .\scripts\B2_a2_playwright.py --input_csv .\out\99_final\todo_a2.csv --url_col url --out_dir .\out\03_a2 --headful --workers 2

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from scraping_utils import (
    canonicalize_url, count_words, ExtractResult, append_jsonl,
    append_error_csv, load_urls_from_csv, try_close_overlays,
    scroll_page, extract_dom_text,
)

try:
    import trafilatura  # type: ignore
except Exception:
    trafilatura = None


# -----------------------------
# Helpers
# -----------------------------
YOUTUBE_DOMAINS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}

def is_youtube(url: str) -> bool:
    u = (url or "").strip()
    if not u:
        return False
    d = (urlparse(u).netloc or "").lower()
    return (d in YOUTUBE_DOMAINS) or ("youtube.com" in u.lower()) or ("youtu.be" in u.lower())


def detect_blocked_or_login(html: str) -> Dict[str, bool]:
    """
    Heuristic flags (no magic, just categorization):
    - blocked: cloudflare/captcha/access denied
    - login_required: sign in / log in / join / auth walls
    """
    h = (html or "")[:20000].lower()
    blocked = any(s in h for s in ["cf-chl", "cloudflare", "captcha", "access denied", "unusual traffic", "verify you are a human"])
    login_required = any(s in h for s in ["sign in", "log in", "login", "join linkedin", "authwall", "create an account"])
    return {"blocked": blocked, "login_required": login_required}


def playwright_fetch_one(
    context,
    url: str,
    out_dir: Path,
    timeout_ms: int = 60000,
    min_words: int = 300,
    min_chars: int = 1000,
) -> ExtractResult:
    page = context.new_page()
    flags: Dict[str, Any] = {}
    html = ""
    final_url = None
    title = None
    text = None
    method = None
    err = None

    try:
        page.set_default_timeout(timeout_ms)

        # Navigate
        page.goto(url, wait_until="domcontentloaded")
        final_url = page.url

        try_close_overlays(page)

        # ensure content loaded
        scroll_page(page, steps=8)
        try_close_overlays(page)
        time.sleep(0.8)

        title, text, method = extract_dom_text(page)

        # Get HTML for flags/debug
        try:
            html = page.content()
        except Exception:
            html = ""

        flags.update(detect_blocked_or_login(html))

        # If DOM text is weak, try trafilatura on HTML (if available)
        if (not text or count_words(text) < min_words or len(text) < min_chars) and trafilatura is not None and html:
            try:
                extracted = trafilatura.extract(html, include_comments=False, include_tables=False)
                if extracted and len(extracted) >= 400:
                    text = extracted.strip()
                    method = "playwright_trafilatura"
            except Exception:
                pass

        # Final quality decision
        if not text:
            err = "no_text_found"
        else:
            wc = count_words(text)
            if wc < min_words or len(text) < min_chars:
                err = "too_short"

        # Save debug artifacts on error/too_short
        if err is not None:
            safe_name = re.sub(r"[^a-zA-Z0-9]+", "_", (urlparse(final_url or url).path or "root"))[:80].strip("_")
            ts = int(time.time())
            dbg_dir = out_dir / "debug"
            dbg_dir.mkdir(parents=True, exist_ok=True)

            try:
                (dbg_dir / f"{ts}_{safe_name}.html").write_text(html or "", encoding="utf-8")
            except Exception:
                pass
            try:
                page.screenshot(path=str(dbg_dir / f"{ts}_{safe_name}.png"), full_page=True)
            except Exception:
                pass

    except PWTimeoutError:
        err = "timeout"
        try:
            html = page.content()
        except Exception:
            html = ""
        flags.update(detect_blocked_or_login(html))
    except Exception as e:
        err = f"exception:{type(e).__name__}"
        try:
            html = page.content()
        except Exception:
            html = ""
        flags.update(detect_blocked_or_login(html))
    finally:
        try:
            page.close()
        except Exception:
            pass

    wc = count_words(text or "")
    return ExtractResult(
        url_original=url,
        url_canonical=canonicalize_url(url),
        url_final=final_url,
        domain=urlparse(final_url or url).netloc,
        extraction_method=method or "playwright",
        title=title,
        text=text,
        word_count=wc,
        text_len=len(text or ""),
        html_len=len(html or ""),
        error=err,
        flags=flags,
        ts=time.time(),
    )


def process_a2(
    urls: List[str],
    out_dir: Path,
    headful: bool,
    workers: int,
    per_domain_interval: float,
    min_words: int,
    min_chars: int,
    skip_youtube: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = out_dir / "a2_playwright.jsonl"
    out_err = out_dir / "a2_errors.csv"

    err_header = [
        "url", "url_final", "domain", "error", "blocked", "login_required",
        "word_count", "text_len", "method"
    ]

    # Deduplicate on canonical
    seen = set()
    filtered = []
    for u in urls:
        if skip_youtube and is_youtube(u):
            continue
        cu = canonicalize_url(u)
        if cu and cu not in seen:
            seen.add(cu)
            filtered.append(u)

    urls = filtered

    # domain pacing
    last_domain_ts: Dict[str, float] = {}

    with sync_playwright() as p:
        chromium = p.chromium

        # Always use a dedicated PW profile (safe when Chrome is open)
        user_data_dir = str(out_dir / "pw_profile")

        launch_args = {
            "headless": not headful,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        context = chromium.launch_persistent_context(user_data_dir=user_data_dir, **launch_args)

        try:
            # Reduce bandwidth: block images/media/fonts (keep JS)
            def route_handler(route, request):
                rtype = request.resource_type
                if rtype in {"image", "media", "font"}:
                    return route.abort()
                return route.continue_()

            try:
                context.route("**/*", route_handler)
            except Exception:
                pass

            # Simple sequential loop (stable). If you want parallel workers later, we can add a queue.
            for i, u in enumerate(urls, 1):
                cu = canonicalize_url(u)
                dom = urlparse(cu).netloc if cu else urlparse(u).netloc
                now = time.time()
                if per_domain_interval > 0:
                    t0 = last_domain_ts.get(dom, 0)
                    dt = now - t0
                    if dt < per_domain_interval:
                        time.sleep(per_domain_interval - dt)
                last_domain_ts[dom] = time.time()

                res = playwright_fetch_one(
                    context=context,
                    url=u,
                    out_dir=out_dir,
                    timeout_ms=60000,
                    min_words=min_words,
                    min_chars=min_chars,
                )
                append_jsonl(out_jsonl, asdict(res))

                if res.error:
                    append_error_csv(out_err, {
                        "url": res.url_original,
                        "url_final": res.url_final,
                        "domain": res.domain,
                        "error": res.error,
                        "blocked": res.flags.get("blocked"),
                        "login_required": res.flags.get("login_required"),
                        "word_count": res.word_count,
                        "text_len": res.text_len,
                        "method": res.extraction_method,
                    }, err_header)

                if i % 20 == 0:
                    print(f"A2 progress: {i}/{len(urls)}")

        finally:
            try:
                context.close()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_csv", required=True, type=str, help="CSV with A2 URLs (e.g., todo_a2.csv)")
    ap.add_argument("--url_col", default="url", type=str, help="URL column name (default: url)")
    ap.add_argument("--out_dir", required=True, type=str, help="Output directory (e.g., out/03_a2)")
    ap.add_argument("--headful", action="store_true", help="Run browser in headful mode")
    ap.add_argument("--workers", default=1, type=int, help="Reserved for future parallelism (keep 1-2 for stability)")
    ap.add_argument("--per_domain_interval", default=1.0, type=float, help="Delay between requests per domain")
    ap.add_argument("--min_words", default=300, type=int)
    ap.add_argument("--min_chars", default=1000, type=int)
    ap.add_argument("--skip_youtube", action="store_true", help="Skip YouTube links")
    args = ap.parse_args()

    urls = load_urls_from_csv(Path(args.input_csv), col=args.url_col)
    process_a2(
        urls=urls,
        out_dir=Path(args.out_dir),
        headful=args.headful,
        workers=args.workers,
        per_domain_interval=args.per_domain_interval,
        min_words=args.min_words,
        min_chars=args.min_chars,
        skip_youtube=args.skip_youtube,
    )
    print("Done.")

if __name__ == "__main__":
    main()
