"""
Fetches career pages and extracts candidate job postings (title + url).

Most of the target sites are JS-rendered SPAs (React, Workday, etc.), so we
use Playwright (headless Chromium) to render the page before parsing.
"""

from __future__ import annotations

import json
import re
import ssl
import time
import urllib.request
from urllib.parse import urljoin, urlparse

import certifi
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# Some Python installs (notably python.org builds on macOS) don't wire up a
# system CA trust store, so urllib can't verify HTTPS certs out of the box.
# Point it at certifi's bundle explicitly rather than relying on the OS.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_API_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

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


_WORKDAY_LOCATION_RE = re.compile(r"/job/([^/]+)/")


def _extract_workday(html: str, base_url: str) -> list[dict]:
    """Workday job boards render postings as <a data-automation-id="jobTitle">.
    The link text itself never includes location (Workday renders that in a
    separate sibling element), but the job URL always does, e.g.
    /job/EMEA---Poland---Krakw---Lubomirskiego/Job-Title_ID -- pull it from
    there so downstream matching can actually see location info."""
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

        loc_match = _WORKDAY_LOCATION_RE.search(href)
        if loc_match:
            location = loc_match.group(1).replace("---", ", ").replace("-", " ")
            text = f"{text} - {location}"
        candidates.append({"title": text, "url": full_url})

    return candidates


def _fetch_json(url: str, method: str = "GET", body: dict | None = None, timeout: int = 20):
    """Call a JSON API directly -- no browser needed. Used for sites whose
    career page is backed by a plain, unauthenticated JSON endpoint that we
    found by inspecting the page's network traffic."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = dict(_API_HEADERS)
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CONTEXT) as resp:
        return json.load(resp)


def _extract_varonis_api(site: dict) -> list[dict]:
    """Varonis' career page is a JobVite board that loads listings from a
    plain JSON endpoint (no auth, no iframe) rather than rendering <a> tags
    the generic extractor can see."""
    api_url = urljoin(site["url"], "/api/getRequisitions")
    payload = _fetch_json(api_url)
    candidates = []
    for job in payload.get("data", []):
        title = (job.get("title") or "").strip()
        locations = job.get("jobLocations") or []
        job_url = locations[0].get("jobDetailsUrl") if locations else None
        if not title or not job_url:
            continue
        loc_name = locations[0].get("name")
        display_title = f"{title} - {loc_name}" if loc_name else title
        candidates.append({"title": display_title, "url": job_url})
    return candidates


def _extract_hunter_hrms_api(site: dict) -> list[dict]:
    """Niloo/HunterHRMS-based boards (e.g. Tel Aviv-Yafo Municipality) return
    ALL jobs across ALL categories from one JSON endpoint; the site itself
    filters by category client-side. We replicate that filter using
    `category_id` from site config (matches the page's own ?cid= param).
    Note: a job's category membership lives in the plural `categoryIds`
    list, not the singular `categoryId` field -- a job's primary category
    can differ from a secondary category it's also tagged under."""
    api_url = site.get("api_url", "https://niloo-server.herokuapp.com/actions-ta")
    jobs = _fetch_json(api_url, method="POST", body={"cmd": "get-jobs-ext"})
    category_id = site.get("category_id")
    base = site["url"].split("?")[0]
    candidates = []
    for job in jobs:
        if category_id is not None and category_id not in (job.get("categoryIds") or []):
            continue
        title = (job.get("jobTitle") or "").strip()
        job_id = job.get("jobId")
        if not title or job_id is None:
            continue
        job_url = f"{base}?cid={category_id}&jobId={job_id}"
        candidates.append({"title": title, "url": job_url})
    return candidates


def _extract_greenhouse_api(site: dict) -> list[dict]:
    """Greenhouse job boards expose a public, unauthenticated JSON API. This
    also works around cases where the company's own marketing site (which
    would normally embed/link to the board) is blocked by its WAF -- the
    Greenhouse-hosted board itself is a separate, unblocked domain."""
    board_token = site["board_token"]
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
    payload = _fetch_json(api_url)
    candidates = []
    for job in payload.get("jobs", []):
        title = (job.get("title") or "").strip()
        job_url = job.get("absolute_url")
        if not title or not job_url:
            continue
        loc = (job.get("location") or {}).get("name")
        display_title = f"{title} - {loc}" if loc else title
        candidates.append({"title": display_title, "url": job_url})
    return candidates


def _extract_oracle_hcm_api(site: dict) -> list[dict]:
    """Oracle Fusion HCM 'Candidate Experience' job boards (e.g. Verint)
    expose requisitions via an unauthenticated REST API; the DOM only
    populates after that call, which our fixed render window can miss."""
    site_number = site.get("site_number", "CX")
    base = site.get("api_host", "https://fa-epcb-saasfaprod1.fa.ocs.oraclecloud.com")
    api_url = (
        f"{base}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        f"?onlyData=true&expand=requisitionList.workLocation,requisitionList.otherWorkLocations"
        f"&finder=findReqs;siteNumber={site_number},limit=200"
    )
    payload = _fetch_json(api_url)
    items = payload.get("items") or []
    reqs = items[0].get("requisitionList", []) if items else []
    candidates = []
    for job in reqs:
        title = (job.get("Title") or "").strip()
        job_id = job.get("Id")
        if not title or job_id is None:
            continue
        loc = job.get("PrimaryLocation")
        display_title = f"{title} - {loc}" if loc else title
        job_url = f"{base}/hcmUI/CandidateExperience/en/sites/{site_number}/job/{job_id}"
        candidates.append({"title": display_title, "url": job_url})
    return candidates


def fetch_job_candidates(site: dict) -> list[dict]:
    """Return a de-duplicated list of {"title": ..., "url": ...} candidate
    job postings for a site. Sites backed by a known JSON API are queried
    directly; everything else falls back to rendering + link extraction."""
    engine = site.get("engine", "generic")

    if engine == "varonis_api":
        return _extract_varonis_api(site)
    if engine == "hunter_hrms_api":
        return _extract_hunter_hrms_api(site)
    if engine == "oracle_hcm_api":
        return _extract_oracle_hcm_api(site)
    if engine == "greenhouse_api":
        return _extract_greenhouse_api(site)

    html = _render_page(site["url"], wait_selector=site.get("wait_selector"))

    if engine == "workday":
        return _extract_workday(html, site["url"])
    return _extract_generic(html, site["url"])
