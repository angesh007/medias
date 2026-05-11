"""
pipeline/step1_scraper.py

Refactored from cs3.py.
Key change: run(config) -> list[dict] returns scraped article dicts
instead of only writing files to disk.
All hardcoded constants are now accepted as config parameters.
"""

import logging
import os
import random
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
#  SCRAPE RESULT
# ══════════════════════════════════════════════════════════════

class ScrapeResult:
    def __init__(self, content: str, success: bool, tier: int, tier_name: str, reason: str = ""):
        self.content   = content
        self.success   = success
        self.tier      = tier
        self.tier_name = tier_name
        self.reason    = reason


# ══════════════════════════════════════════════════════════════
#  SEARCH — Serper.dev
# ══════════════════════════════════════════════════════════════

def _build_tbs(date_from: str, date_to: str) -> str:
    return f"cdr:1,cd_min:{date_from},cd_max:{date_to}"


def _search_site(
    term: str,
    site: str,
    date_from: str,
    date_to: str,
    max_results: int,
    serper_key: str,
    country: str = "in",
    retry_attempts: int = 3,
) -> list[dict]:
    """Search via Serper.dev for one term + site + date window."""
    all_results = []
    per_page    = 10
    max_pages   = min(4, -(-max_results // per_page))
    tbs         = _build_tbs(date_from, date_to)
    url         = "https://google.serper.dev/search"
    headers     = {"X-API-KEY": serper_key, "Content-Type": "application/json"}

    for page_num in range(1, max_pages + 1):
        payload = {
            "q": f"site:{site} {term}",
            "gl": country,
            "hl": "en",
            "num": per_page,
            "page": page_num,
            "tbs": tbs,
        }
        for attempt in range(retry_attempts):
            try:
                r = requests.post(url, headers=headers, json=payload, timeout=20)
                r.raise_for_status()
                organic = r.json().get("organic", [])
                if not organic:
                    return all_results
                for item in organic:
                    all_results.append({
                        "title":    item.get("title", ""),
                        "link":     item.get("link", ""),
                        "snippet":  item.get("snippet", ""),
                        "date":     item.get("date", ""),
                        "position": item.get("position", 0),
                        "site":     site,
                    })
                    if len(all_results) >= max_results:
                        return all_results
                if len(organic) < per_page:
                    return all_results
                time.sleep(0.8)
                break
            except requests.exceptions.HTTPError as exc:
                if exc.response.status_code == 401:
                    raise RuntimeError("Invalid Serper API key") from exc
                if attempt < retry_attempts - 1:
                    time.sleep(2 ** attempt)
            except Exception as exc:
                log.warning("Serper request failed (attempt %d): %s", attempt + 1, exc)
                if attempt < retry_attempts - 1:
                    time.sleep(2 ** attempt)
    return all_results


# ══════════════════════════════════════════════════════════════
#  SCRAPING TIERS
# ══════════════════════════════════════════════════════════════

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) Gecko/20100101 Firefox/124.0",
]


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    paras = soup.find_all(["p", "article", "section"])
    text = " ".join(p.get_text(" ", strip=True) for p in paras)
    return re.sub(r"\s+", " ", text).strip()


def _tier1_requests(url: str, min_length: int) -> ScrapeResult:
    try:
        headers = {"User-Agent": random.choice(_USER_AGENTS)}
        r = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        r.raise_for_status()
        text = _extract_text(r.text)
        if len(text) >= min_length:
            return ScrapeResult(text, True, 1, "requests")
        return ScrapeResult(text, False, 1, "requests", "content too short")
    except Exception as exc:
        return ScrapeResult("", False, 1, "requests", str(exc))


def _tier2_cloudscraper(url: str, min_length: int) -> ScrapeResult:
    try:
        import cloudscraper
        scraper = cloudscraper.create_scraper()
        r = scraper.get(url, timeout=20)
        r.raise_for_status()
        text = _extract_text(r.text)
        if len(text) >= min_length:
            return ScrapeResult(text, True, 2, "cloudscraper")
        return ScrapeResult(text, False, 2, "cloudscraper", "content too short")
    except ImportError:
        return ScrapeResult("", False, 2, "cloudscraper", "cloudscraper not installed")
    except Exception as exc:
        return ScrapeResult("", False, 2, "cloudscraper", str(exc))


def _tier3_playwright(url: str, min_length: int) -> ScrapeResult:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(user_agent=random.choice(_USER_AGENTS))
            page.goto(url, timeout=30_000, wait_until="networkidle")
            html = page.content()
            browser.close()
        text = _extract_text(html)
        if len(text) >= min_length:
            return ScrapeResult(text, True, 3, "playwright")
        return ScrapeResult(text, False, 3, "playwright", "content too short")
    except ImportError:
        return ScrapeResult("", False, 3, "playwright", "playwright not installed")
    except Exception as exc:
        return ScrapeResult("", False, 3, "playwright", str(exc))


def _tier4_brightdata(url: str, wss_url: str, min_length: int) -> ScrapeResult:
    if not wss_url:
        return ScrapeResult("", False, 4, "brightdata", "BRIGHTDATA_WSS not set")
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(wss_url)
            page = browser.new_page()
            page.goto(url, timeout=60_000, wait_until="networkidle")
            html = page.content()
            browser.close()
        text = _extract_text(html)
        if len(text) >= min_length:
            return ScrapeResult(text, True, 4, "brightdata")
        return ScrapeResult(text, False, 4, "brightdata", "content too short")
    except Exception as exc:
        return ScrapeResult("", False, 4, "brightdata", str(exc))


def _scrape_with_fallback(url: str, config: dict) -> ScrapeResult:
    min_len      = config.get("min_content_length", 300)
    brightdata   = config.get("brightdata_wss", "")

    for tier_fn, enabled_key in [
        (_tier1_requests,    "use_tier1"),
        (_tier2_cloudscraper,"use_tier2"),
        (_tier3_playwright,  "use_tier3"),
    ]:
        if not config.get(enabled_key, True):
            continue
        result = tier_fn(url, min_len)
        if result.success:
            return result
        log.debug("Tier %d failed for %s: %s", result.tier, url, result.reason)

    if config.get("use_tier4", True):
        result = _tier4_brightdata(url, brightdata, min_len)
        if result.success:
            return result

    return ScrapeResult("All tiers failed", False, 0, "none", "total failure")


# ══════════════════════════════════════════════════════════════
#  PUBLIC INTERFACE
# ══════════════════════════════════════════════════════════════

def run(config: dict) -> list[dict]:
    """
    Step 1 entry point.

    config keys:
        serper_key          str   (required)
        sites               list  of domain strings
        date_ranges         list  of (date_from, date_to) tuples
        search_terms        list  of strings
        country             str   default "in"
        max_results_per_site int  default 50
        delay_between_sites  float default 2.0
        delay_between_articles float default 1.5
        min_content_length  int   default 300
        brightdata_wss      str   optional
        use_tier1 .. use_tier4  bool

    Returns:
        List of article dicts, each shaped like:
        {
            "title": ..., "url": ..., "site": ...,
            "published_date": ..., "snippet": ...,
            "search_term": ..., "date_range": ...,
            "country": ...,
            "body": ...,                  ← scraped content
            "scrape_status": "success"|"partial"|"failed",
            "scrape_method": "requests"|...,
            "scraped_at": ISO timestamp,
        }
    """
    serper_key   = config["serper_key"]
    sites        = config.get("sites", [])
    date_ranges  = config.get("date_ranges", [])
    search_terms = config.get("search_terms", ["RSS"])
    country      = config.get("country", "in")
    max_per_site = config.get("max_results_per_site", 50)
    delay_sites  = config.get("delay_between_sites", 2.0)
    delay_arts   = config.get("delay_between_articles", 1.5)

    if not serper_key:
        raise ValueError("serper_key is required in config")
    if not sites:
        raise ValueError("sites list is empty")
    if not date_ranges:
        raise ValueError("date_ranges list is empty")

    log.info("Step 1 — Searching: %d sites × %d date ranges × %d terms",
             len(sites), len(date_ranges), len(search_terms))

    # ── Phase 1: Search ───────────────────────────────────────
    all_search_results: list[dict] = []
    seen_urls: set[str] = set()

    for date_from, date_to in date_ranges:
        range_label = f"{date_from} – {date_to}"
        for site in sites:
            quota_per_term = max(1, max_per_site // len(search_terms))
            for term in search_terms:
                results = _search_site(term, site, date_from, date_to,
                                       quota_per_term, serper_key, country)
                for r in results:
                    if r["link"] not in seen_urls:
                        r["date_range"] = range_label
                        r["search_term"] = term
                        all_search_results.append(r)
                        seen_urls.add(r["link"])
            time.sleep(delay_sites)

    log.info("Step 1 — Found %d unique URLs", len(all_search_results))

    if not all_search_results:
        log.warning("Step 1 — No search results found")
        return []

    # ── Phase 2: Scrape ───────────────────────────────────────
    log.info("Step 1 — Scraping %d articles…", len(all_search_results))
    articles: list[dict] = []

    for i, meta in enumerate(all_search_results, 1):
        url = meta["link"]
        log.info("[%d/%d] Scraping: %s", i, len(all_search_results), url[:80])

        result = _scrape_with_fallback(url, config)

        if result.success:
            status = "success"
        elif len(result.content) > 200:
            status = "partial"
        else:
            status = "failed"

        article = {
            "title":          meta.get("title", ""),
            "url":            url,
            "site":           meta.get("site", ""),
            "published_date": meta.get("date", ""),
            "snippet":        meta.get("snippet", ""),
            "search_term":    meta.get("search_term", ""),
            "date_range":     meta.get("date_range", ""),
            "country":        country.upper(),
            "body":           result.content,
            "scrape_status":  status,
            "scrape_method":  result.tier_name,
            "failure_reason": result.reason or None,
            "scraped_at":     datetime.utcnow().isoformat(),
        }
        articles.append(article)
        time.sleep(delay_arts)

    success_count = sum(1 for a in articles if a["scrape_status"] == "success")
    log.info("Step 1 — Done. %d success / %d partial / %d failed",
             success_count,
             sum(1 for a in articles if a["scrape_status"] == "partial"),
             sum(1 for a in articles if a["scrape_status"] == "failed"))

    return articles
