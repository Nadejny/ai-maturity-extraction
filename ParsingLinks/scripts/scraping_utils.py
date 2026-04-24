# scraping_utils.py
# Shared utilities for scraping scripts (B0, B1, B2, merge, export).

from __future__ import annotations

import csv
import hashlib
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------

DROP_QUERY_KEYS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "ref", "source", "cmpid", "mkt_tok",
}


def canonicalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        return ""
    p = urlparse(url)
    q = [(k, v) for (k, v) in parse_qsl(p.query, keep_blank_values=True)
         if k not in DROP_QUERY_KEYS]
    query = urlencode(q, doseq=True)
    clean = p._replace(query=query, fragment="")
    return urlunparse(clean)


def count_words(text: str) -> int:
    return len(re.findall(r"\S+", text or ""))


def sha1_text(s: str) -> str:
    return hashlib.sha1((s or "").encode("utf-8", errors="ignore")).hexdigest()


def safe_slug(s: str, max_len: int = 80) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = re.sub(r"[^a-zA-Z0-9\-_. ]+", "", s).strip().replace(" ", "_")
    return s[:max_len].strip("_") or "doc"


# ---------------------------------------------------------------------------
# JSONL / CSV I/O
# ---------------------------------------------------------------------------

def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def append_jsonl(path: Path, obj: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")


def load_urls_from_csv(path: Path, col: str = "url") -> List[str]:
    urls: List[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return urls
        if col not in reader.fieldnames:
            col = reader.fieldnames[0]
        for row in reader:
            u = (row.get(col) or "").strip()
            if u:
                urls.append(u)
    return urls


def append_error_csv(path: Path, row: Dict[str, Any], header: List[str]) -> None:
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header)
        if not exists:
            w.writeheader()
        w.writerow(row)


# ---------------------------------------------------------------------------
# Extraction result schema
# ---------------------------------------------------------------------------

@dataclass
class ExtractResult:
    url_original: str
    url_canonical: str
    url_final: Optional[str]
    domain: str
    extraction_method: str
    title: Optional[str]
    text: Optional[str]
    word_count: int
    text_len: int
    html_len: int
    error: Optional[str]
    flags: Dict[str, Any]
    ts: float


# ---------------------------------------------------------------------------
# Playwright helpers
# ---------------------------------------------------------------------------

CLOSE_SELECTORS = [
    '[aria-label="Close"]',
    '[aria-label*="Close" i]',
    'button:has-text("No thanks")',
    'button:has-text("No Thanks")',
    'button:has-text("Not now")',
    'button:has-text("Maybe later")',
    'button:has-text("Skip")',
    'button:has-text("Continue without")',
    'button:has-text("Accept")',
    'button:has-text("I agree")',
    'button:has-text("Agree")',
    'button:has-text("OK")',
    'button:has-text("Got it")',
]

SVG_CLOSE_XPATHS = [
    "//*[name()='svg']//*[name()='path' and contains(@d,'m20.13')]/ancestor::*[self::button or self::div][1]",
]


def try_close_overlays(page) -> None:
    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    for sel in CLOSE_SELECTORS:
        try:
            loc = page.locator(sel).first
            if loc and loc.is_visible(timeout=300):
                loc.click(timeout=800)
        except Exception:
            pass

    for xp in SVG_CLOSE_XPATHS:
        try:
            loc = page.locator(f"xpath={xp}").first
            if loc and loc.is_visible(timeout=300):
                loc.click(timeout=800)
        except Exception:
            pass

    try:
        page.evaluate(
            """() => {
                document.documentElement.style.overflow = 'auto';
                document.body.style.overflow = 'auto';
            }"""
        )
    except Exception:
        pass


def scroll_page(page, steps: int = 8, delta: int = 1600) -> None:
    for _ in range(steps):
        try:
            page.mouse.wheel(0, delta)
        except Exception:
            try:
                page.evaluate(f"() => window.scrollBy(0, {delta})")
            except Exception:
                pass
        time.sleep(0.35)


def extract_dom_text(page) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Returns (title, text, method). method is one of:
    playwright_article, playwright_main, playwright_role_main,
    playwright_section, playwright_body, or None.
    """
    title = None
    try:
        title = page.title()
    except Exception:
        pass

    for sel, method in [
        ("article", "playwright_article"),
        ("main", "playwright_main"),
    ]:
        try:
            loc = page.locator(sel).first
            if loc and loc.is_visible(timeout=600):
                t = loc.inner_text(timeout=3000).strip()
                if t and len(t) >= 400:
                    return title, t, method
        except Exception:
            pass

    for sel, method in [
        ('[role="main"]', "playwright_role_main"),
        ("section", "playwright_section"),
    ]:
        try:
            loc = page.locator(sel).first
            if loc:
                t = loc.inner_text(timeout=3000).strip()
                if t and len(t) >= 400:
                    return title, t, method
        except Exception:
            pass

    try:
        t = page.locator("body").inner_text(timeout=3000).strip()
        if t and len(t) >= 400:
            return title, t, "playwright_body"
    except Exception:
        pass

    return title, None, None
