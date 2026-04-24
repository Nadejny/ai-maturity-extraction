# B1_medium_playwright.py
# Python 3.10+
#
# Install:
#   pip install -U playwright requests beautifulsoup4 lxml pandas
#   python -m playwright install chromium
#
# Run example:
#   python B1_medium_playwright.py --input_csv .\out\99_final\todo_medium.csv --out_dir .\out\02_medium \
#     --chrome_user_data "C:\Users\<YOU>\AppData\Local\Google\Chrome\User Data" --chrome_profile "Default" \
#     --workers 2 --headful

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import asdict
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

from scraping_utils import (
    canonicalize_url, count_words, ExtractResult, append_jsonl,
    append_error_csv, load_urls_from_csv, try_close_overlays,
    scroll_page, extract_dom_text,
)


# -----------------------------
# Medium: non-browser attempts
# -----------------------------
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

def http_get(url: str, timeout: int = 25) -> Tuple[int, str, str]:
    r = requests.get(url, headers={"User-Agent": UA}, timeout=timeout, allow_redirects=True)
    return r.status_code, r.text or "", r.url

def is_medium_like(url: str) -> bool:
    d = (urlparse(url).netloc or "").lower()
    return ("medium.com" in d) or d.endswith("towardsdatascience.com") or d.endswith("betterprogramming.pub") or d.endswith("levelup.gitconnected.com")

def detect_paywall_or_block(text: str, html: str) -> Dict[str, bool]:
    t = (text or "")[:2000].lower()
    h = (html or "")[:12000].lower()

    paywalled = any(s in (t + " " + h) for s in [
        "member-only", "members-only", "this story is for members",
        "become a member", "to continue reading", "get unlimited access"
    ])

    # ВАЖНО: "blocked" как одиночное слово не используем
    blocked = any(s in h for s in [
        "unusual traffic", "verify you are a human", "cf-chl", "cloudflare",
        "captcha", "access denied", "temporarily unavailable"
    ])

    return {"paywalled": paywalled, "blocked": blocked}

def extract_from_amp_html(html: str) -> Tuple[Optional[str], Optional[str]]:
    soup = BeautifulSoup(html, "lxml")
    # title
    title = None
    if soup.title and soup.title.get_text(strip=True):
        title = soup.title.get_text(strip=True)
    # try amp article/main
    node = soup.find("article") or soup.find("main")
    if not node:
        return title, None
    text = node.get_text("\n", strip=True)
    return title, text if text and len(text) >= 200 else None

def try_medium_amp(url: str) -> Optional[ExtractResult]:
    amp_url = url
    if "?" in amp_url:
        amp_url += "&format=amp"
    else:
        amp_url += "?format=amp"

    status, html, final_url = http_get(amp_url)
    if status != 200 or not html:
        return None

    title, text = extract_from_amp_html(html)
    flags = detect_paywall_or_block(text or "", html)

    if flags["blocked"] or flags["paywalled"]:
        return ExtractResult(
            url_original=url,
            url_canonical=canonicalize_url(url),
            url_final=final_url,
            domain=urlparse(final_url).netloc if final_url else urlparse(url).netloc,
            extraction_method="medium_amp",
            title=title,
            text=text,
            word_count=count_words(text or ""),
            text_len=len(text or ""),
            html_len=len(html),
            error="paywalled_or_blocked",
            flags=flags,
            ts=time.time(),
        )

    if text and count_words(text) >= 250 and len(text) >= 1000:
        return ExtractResult(
            url_original=url,
            url_canonical=canonicalize_url(url),
            url_final=final_url,
            domain=urlparse(final_url).netloc if final_url else urlparse(url).netloc,
            extraction_method="medium_amp",
            title=title,
            text=text,
            word_count=count_words(text),
            text_len=len(text),
            html_len=len(html),
            error=None,
            flags=flags,
            ts=time.time(),
        )
    return None

MEDIUM_JSON_PREFIX = r"^\)\]\}',?\s*"

def try_medium_json(url: str) -> Optional[ExtractResult]:
    json_url = url
    if "?" in json_url:
        json_url += "&format=json"
    else:
        json_url += "?format=json"

    status, body, final_url = http_get(json_url)
    if status != 200 or not body:
        return None

    # Medium JSON responses sometimes start with )]}'
    body2 = re.sub(MEDIUM_JSON_PREFIX, "", body.strip())
    try:
        data = json.loads(body2)
    except Exception:
        return None

    # Medium JSON often stores HTML in payload.value.content.bodyModel.paragraphs, etc.
    # We'll do a simple robust attempt: search for large HTML-ish strings.
    html_candidates: List[str] = []
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and ("<p" in v or "<article" in v or "<h" in v) and len(v) > 2000:
                    html_candidates.append(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for it in obj:
                walk(it)

    walk(data)
    if not html_candidates:
        return None

    # Take biggest candidate
    html = max(html_candidates, key=len)
    title, text = extract_from_amp_html(html)  # reuse: article/main parsing if present
    if not text:
        # fallback: strip all text
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)

    flags = detect_paywall_or_block(text or "", html)
    if flags["blocked"] or flags["paywalled"]:
        err = "paywalled_or_blocked"
    else:
        err = None

    if text and (count_words(text) >= 250 and len(text) >= 1000) and err is None:
        return ExtractResult(
            url_original=url,
            url_canonical=canonicalize_url(url),
            url_final=final_url,
            domain=urlparse(final_url).netloc if final_url else urlparse(url).netloc,
            extraction_method="medium_json",
            title=title,
            text=text,
            word_count=count_words(text),
            text_len=len(text),
            html_len=len(html),
            error=None,
            flags=flags,
            ts=time.time(),
        )

    # Return even if paywalled/blocked so you can count them
    if err is not None:
        return ExtractResult(
            url_original=url,
            url_canonical=canonicalize_url(url),
            url_final=final_url,
            domain=urlparse(final_url).netloc if final_url else urlparse(url).netloc,
            extraction_method="medium_json",
            title=title,
            text=text,
            word_count=count_words(text or ""),
            text_len=len(text or ""),
            html_len=len(html),
            error=err,
            flags=flags,
            ts=time.time(),
        )
    return None


def playwright_fetch_one(
    context,
    url: str,
    out_dir: Path,
    timeout_ms: int = 45000,
    min_words: int = 250,
    min_chars: int = 1000,
) -> ExtractResult:
    page = context.new_page()
    flags = {"paywalled": False, "blocked": False}
    html = ""
    final_url = None
    title = None
    text = None
    err = None

    try:
        page.set_default_timeout(timeout_ms)

        # Navigate
        resp = page.goto(url, wait_until="domcontentloaded")
        final_url = page.url

        # quick overlay handling
        try_close_overlays(page)

        # ensure content loaded
        scroll_page(page, steps=6, delta=1400)
        try_close_overlays(page)
        time.sleep(0.6)

        title, text, _method = extract_dom_text(page)

        # Get HTML for flags/debug
        try:
            html = page.content()
        except Exception:
            html = ""

        # detect paywall / block
        det = detect_paywall_or_block(text or "", html or "")
        flags.update(det)

        if flags["blocked"]:
            err = "blocked_or_captcha"
        elif flags["paywalled"]:
            err = "paywalled"
        elif not text:
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
    except Exception as e:
        err = f"exception:{type(e).__name__}"
        try:
            html = page.content()
        except Exception:
            html = ""
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
        extraction_method="playwright",
        title=title,
        text=text,
        word_count=wc,
        text_len=len(text or ""),
        html_len=len(html or ""),
        error=err,
        flags=flags,
        ts=time.time(),
    )


def process_urls(
    urls: List[str],
    out_dir: Path,
    chrome_user_data: Optional[str],
    chrome_profile: Optional[str],
    headful: bool,
    workers: int,
    per_domain_interval: float,
    min_words: int,
    min_chars: int,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_jsonl = out_dir / "medium.jsonl"
    out_err = out_dir / "medium_errors.csv"

    # error csv header
    err_header = ["url", "url_final", "domain", "error", "paywalled", "blocked", "word_count", "text_len", "method"]

    # (optional) domain pacing
    last_domain_ts: Dict[str, float] = {}

    # Deduplicate on canonical
    seen = set()
    filtered = []
    for u in urls:
        cu = canonicalize_url(u)
        if cu not in seen:
            seen.add(cu)
            filtered.append(u)

    urls = filtered

    # 1) cheap attempts first (amp/json)
    remaining: List[str] = []
    for u in urls:
        cu = canonicalize_url(u)
        dom = urlparse(cu).netloc
        now = time.time()
        if per_domain_interval > 0:
            t0 = last_domain_ts.get(dom, 0)
            dt = now - t0
            if dt < per_domain_interval:
                time.sleep(per_domain_interval - dt)
        last_domain_ts[dom] = time.time()

        res = None
        if is_medium_like(u):
            res = try_medium_amp(u)
            if res is None:
                res = try_medium_json(u)

        if res is None:
            remaining.append(u)
            continue

        append_jsonl(out_jsonl, asdict(res))
        if res.error:
            append_error_csv(out_err, {
                "url": res.url_original,
                "url_final": res.url_final,
                "domain": res.domain,
                "error": res.error,
                "paywalled": res.flags.get("paywalled"),
                "blocked": res.flags.get("blocked"),
                "word_count": res.word_count,
                "text_len": res.text_len,
                "method": res.extraction_method,
            }, err_header)

    # 2) Playwright fallback for remaining
    if not remaining:
        print("Done: no remaining URLs for Playwright.")
        return

    # We keep concurrency low for stability (Medium hates high parallelism)
    workers = max(1, min(workers, 4))

    with sync_playwright() as p:
        chromium = p.chromium

        # Всегда отдельный профиль для Playwright (не конфликтует с открытым Chrome)
        user_data_dir = str(out_dir / "pw_profile")

        launch_args = {
            "headless": not headful,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        }

        # НЕ добавляем --profile-directory, потому что не используем Chrome User Data
        context = chromium.launch_persistent_context(user_data_dir=user_data_dir, **launch_args)
        try:
            # optional: reduce bandwidth (keep JS, drop images/fonts)
            def route_handler(route, request):
                rtype = request.resource_type
                if rtype in {"image", "media", "font"}:
                    return route.abort()
                return route.continue_()

            try:
                context.route("**/*", route_handler)
            except Exception:
                pass

            # Very simple "pool": we iterate sequentially but you can expand later.
            # Keeping it single-threaded is often most stable under VPN.
            for i, u in enumerate(remaining, 1):
                cu = canonicalize_url(u)
                dom = urlparse(cu).netloc
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
                    timeout_ms=45000,
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
                        "paywalled": res.flags.get("paywalled"),
                        "blocked": res.flags.get("blocked"),
                        "word_count": res.word_count,
                        "text_len": res.text_len,
                        "method": res.extraction_method,
                    }, err_header)

                if i % 20 == 0:
                    print(f"Playwright progress: {i}/{len(remaining)}")

        finally:
            try:
                context.close()
            except Exception:
                pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input_csv", required=True, type=str, help="CSV with Medium URLs (e.g., todo_medium.csv)")
    ap.add_argument("--url_col", default="url", type=str, help="Column name in CSV (default: url)")
    ap.add_argument("--out_dir", required=True, type=str, help="Output directory (e.g., out/02_medium)")
    ap.add_argument("--chrome_user_data", default=None, type=str, help="Chrome user data dir to reuse cookies/consents")
    ap.add_argument("--chrome_profile", default=None, type=str, help='Chrome profile directory name (e.g., "Default")')
    ap.add_argument("--headful", action="store_true", help="Run browser in headful mode")
    ap.add_argument("--workers", default=1, type=int, help="Concurrency (kept low; max 4)")
    ap.add_argument("--per_domain_interval", default=0.8, type=float, help="Delay between requests per domain")
    ap.add_argument("--min_words", default=250, type=int)
    ap.add_argument("--min_chars", default=1000, type=int)
    args = ap.parse_args()

    urls = load_urls_from_csv(Path(args.input_csv), col=args.url_col)
    process_urls(
        urls=urls,
        out_dir=Path(args.out_dir),
        chrome_user_data=args.chrome_user_data,
        chrome_profile=args.chrome_profile,
        headful=args.headful,
        workers=args.workers,
        per_domain_interval=args.per_domain_interval,
        min_words=args.min_words,
        min_chars=args.min_chars,
    )
    print("Done.")

if __name__ == "__main__":
    main()


