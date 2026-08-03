"""
Fetches career pages and extracts candidate job postings (title + url).

Most of the target sites are JS-rendered SPAs (React, Workday, etc.), so we
use Playwright (headless Chromium) to render the page before parsing.
"""

from __future__ import annotations

import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Words that show up in nav/footer/legal links -- used to drop obvious noise
# from the generic extractor. Not exhaustive, just a first-pass filter.
NOISE_WORDS = {
    "privacy", "terms", "cookie", "contact us", "about us", "home",
    "login", "sign in", "sign up", "facebook", "twitter", "linkedin",
    "instagram", "youtube", "accessibility", "site map", "פרטיות",
    "תנאי שימוש", "צור קשר", "אודות", "בית", "התחברות", "נגישות",
}


def _render_page(url: str, wait_selector: str | None = None, timeout_ms: int = 25000) -> str:
    """Load a URL in headless Chromium and return the fully rendered HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            )
        )
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except PWTimeout:
            # Some sites never go fully idle (polling/analytics). Fall back
            # to whatever loaded so far.
            pass

        if wait_selector:
            try:
                page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except PWTimeout:
                pass

        # small extra pause for lazy-loaded lists
        time.sleep(1.5)
        html = page.content()
        browser.close()
        return html


def _extract_generic(html: str, base_url: str) -> list[dict]:
    """Grab every link on the page that looks like it could be a job posting."""
    soup = BeautifulSoup(html, "lxml")
    seen_urls = set()
    candidates = []

    for a in soup.find_all("a", href=True):
        text = a.get_text(" ", strip=True)
        href = a["href"].strip()
        if not text or len(text) < 3:
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue

        lower_text = text.lower()
        if any(noise in lower_text for noise in NOISE_WORDS):
            continue

        # Heuristic: real job-posting links tend to have "job", "career",
        # "position", "req", "vacancy", or a Hebrew equivalent in the URL,
        # OR reasonably descriptive link text (title-like, not a 1-2 word nav item).
        path = urlparse(full_url).path.lower()
        job_url_hint = any(
            kw in path
            for kw in ["job", "career", "position", "req", "vacan", "role",
                       "משרה", "משרות", "דרוש"]
        )
        descriptive_text = len(text.split()) >= 2

        if job_url_hint or descriptive_text:
            seen_urls.add(full_url)
            candidates.append({"title": text, "url": full_url})

    return candidates


def _extract_workday(html: str, base_url: str) -> list[dict]:
    """Workday job boards render postings as <a data-automation-id="jobTitle">."""
    soup = BeautifulSoup(html, "lxml")
    candidates = []
    seen_urls = set()

    links = soup.select('a[data-automation-id="jobTitle"]')
    if not links:
        # fall back to generic if Workday changed their markup
        return _extract_generic(html, base_url)

    for a in links:
        text = a.get_text(" ", strip=True)
        href = a.get("href", "").strip()
        if not text or not href:
            continue
        full_url = urljoin(base_url, href)
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        candidates.append({"title": text, "url": full_url})

    return candidates


def fetch_job_candidates(site: dict) -> list[dict]:
    """Render a site's career page and return a de-duplicated list of
    {"title": ..., "url": ...} candidate job postings."""
    html = _render_page(site["url"], wait_selector=site.get("wait_selector"))

    if site.get("engine") == "workday":
        return _extract_workday(html, site["url"])
    return _extract_generic(html, site["url"])
