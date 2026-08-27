"""
Fetches career pages and extracts candidate job postings (title + url).

Most of the target sites are JS-rendered SPAs (React, Workday, etc.), so we
use Playwright (headless Chromium) to render the page before parsing.
"""

from __future__ import annotations

import csv
import json
import re
import ssl
import time
import urllib.request
from urllib.parse import urljoin, urlparse

import certifi
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PWTimeout

# Some Python installs (notably python.org builds on macOS) don't wire up a
# system CA trust store, so urllib can't verify HTTPS certs out of the box.
# Point it at certifi's bundle explicitly rather than relying on the OS.
_SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

_API_HEADERS = {
    "User-Agent": _UA,
    "Accept": "application/json",
}

# Words that show up in nav/footer/legal links -- used to drop obvious noise
# from the generic extractor. Not exhaustive, just a first-pass filter.
NOISE_WORDS = {
    "privacy", "terms", "cookie", "contact us", "about us", "home",
    "login", "sign in", "sign up", "facebook", "twitter", "linkedin",
    "instagram", "youtube", "accessibility", "site map", "פרטיות",
    "תנאי שימוש", "צור קשר", "אודות", "בית", "התחברות", "נגישות",
    # These describe company content, not a specific role -- a page titled
    # "Engineering Blog" or "Global Engineering Days" will happily pass
    # role/level/location matching despite never being a job posting.
    "blog", "webinar", "read more", "watch now", "watch video",
    "talent community", "קראו עוד", "צפו", "וובינר",
    # Developer *portals* (API docs, SDKs) are an especially sneaky case --
    # the word "developer" in the title is exactly our strongest positive
    # role-match keyword, so these otherwise sail through as compatible
    # (found via real entries: "Developer Hub", "Kaltura developer suite",
    # "Media Services for Developers").
    "developer hub", "developer center", "developer portal",
    "developer suite", "for developers", "api docs", "api documentation",
    # A OneTrust/Cookiebot-style consent banner's ad-tech vendor list repeats
    # this exact phrase once per partner -- seen dominating extraction on
    # several sites (12/29 candidates on one page) purely because it's
    # short, descriptive-looking link text with nothing else to filter it.
    "learn more about this provider",
}

# Link text/URLs pointing at these domains are never job postings (blog
# videos, social embeds, etc.), regardless of how job-ish the link text
# sounds.
NOISE_DOMAINS = {"youtube.com", "youtu.be", "vimeo.com"}

# URL path segments that indicate company content rather than a specific
# job requisition (team overview, marketing/product pages, resource
# libraries). A page can still pass if it ALSO has a clear job_url_hint
# below -- e.g. some ATSes nest job listings under "/careers/blog/" -- but
# on its own this disqualifies what would otherwise pass on link-text length
# alone.
NEGATIVE_URL_WORDS = ["/blog", "/resources", "/solutions", "/products",
                       "/teams/", "/news", "/press", "/webinar", "/developer"]


def _render_page(url: str, browser, wait_selector: str | None = None, timeout_ms: int = 25000) -> str:
    """Load a URL in headless Chromium and return the fully rendered HTML.
    Takes an already-open Playwright `browser` rather than launching its
    own -- callers share one browser for the whole run (see main.py) so we
    don't pay Chromium's ~1-2s launch cost on every single site/page."""
    page = browser.new_page(user_agent=_UA)
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
    page.close()
    return html


def _dedupe_repeated_text(text: str, min_chunk_len: int = 20) -> str:
    """Some sites re-render the same block of text many times on one page --
    LinkedIn's logged-out view repeats its "sign in to apply" prompt (with
    the full user agreement/cookie policy sentence) roughly once per
    interactive element, which can be 1500-2000+ characters of pure noise
    before the real posting text even starts. Left in, that eats into our
    truncation budget and can push the actual requirements past max_chars
    entirely. Split on sentence boundaries and drop exact repeats (keeping
    the first occurrence), independent of language."""
    seen = set()
    kept = []
    for chunk in re.split(r"(?<=[.!?])\s+", text):
        key = chunk.strip()
        if len(key) >= min_chunk_len:
            if key in seen:
                continue
            seen.add(key)
        kept.append(chunk)
    return " ".join(kept)


def fetch_job_detail_text(url: str, browser, max_chars: int = 8000, timeout_ms: int = 15000) -> str:
    """Render a single job posting page and return its visible body text,
    truncated. Used for stage-2 refinement in main.py: a job that looked
    compatible from its title alone gets re-checked against the real
    posting body, which often states experience/location requirements the
    title/link text never mentioned.

    max_chars was originally 4000, tuned against our own (mostly compact)
    per-company career pages. LinkedIn's logged-out view -- now a common
    source via techmap -- front-loads ~2000-3000 characters of repeated
    "sign in to apply" boilerplate before the real posting text, which was
    pushing genuine requirements (e.g. "3+ years") right up against or past
    that cutoff. Raised to 8000, which comfortably covers full LinkedIn
    pages (measured 7-9k chars) while barely affecting shorter ATS pages
    (Comeet pages run 2.5-3.5k chars total, well under either cap)."""
    page = browser.new_page(user_agent=_UA)
    try:
        try:
            page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        except PWTimeout:
            pass
        html = page.content()
    finally:
        page.close()

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    text = _dedupe_repeated_text(text)
    return text[:max_chars]


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

        parsed = urlparse(full_url)
        if any(parsed.netloc.endswith(d) for d in NOISE_DOMAINS):
            continue
        # A "developer." subdomain (developer.walkme.com, developer.kaltura.com)
        # is an API/SDK portal, not a career site -- NEGATIVE_URL_WORDS below
        # only ever sees the path, so this needs its own check.
        if parsed.netloc.lower().startswith("developer."):
            continue

        # Heuristic: real job-posting links tend to have "job", "career",
        # "position", "req", "vacancy", or a Hebrew equivalent in the URL,
        # OR reasonably descriptive link text (title-like, not a 1-2 word nav item).
        path = parsed.path.lower()
        job_url_hint = any(
            kw in path
            for kw in ["job", "career", "position", "req", "vacan", "role",
                       "משרה", "משרות", "דרוש"]
        )
        descriptive_text = len(text.split()) >= 2
        negative_url_hint = any(kw in path for kw in NEGATIVE_URL_WORDS)

        if job_url_hint or (descriptive_text and not negative_url_hint):
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


def _extract_deep_instinct(html: str, base_url: str) -> list[dict]:
    """Deep Instinct's job cards render the link text as just "SEE DETAILS"
    -- the actual title (and department) live in a sibling text node within
    the same container, not the <a> tag itself, so the generic scraper only
    ever sees identical "SEE DETAILS" links (all collapsing to one
    boilerplate title, not real per-job text). Pull the whole container's
    text instead."""
    soup = BeautifulSoup(html, "lxml")
    candidates = []
    seen_urls = set()

    for a in soup.find_all("a", href=True):
        if a.get_text(strip=True).lower() != "see details":
            continue
        full_url = urljoin(base_url, a["href"].strip())
        if full_url in seen_urls:
            continue
        title = a.parent.get_text(" ", strip=True)
        title = re.sub(r"\s*SEE DETAILS\s*$", "", title, flags=re.IGNORECASE).strip()
        if not title:
            continue
        seen_urls.add(full_url)
        candidates.append({"title": title, "url": full_url})

    return candidates


def _extract_drivenets(html: str, base_url: str) -> list[dict]:
    """DriveNets' job rows link out via a bare arrow-icon <a> with no text
    of its own -- the actual title/department/location live two levels up
    in the row's shared container, not on the link or its immediate parent
    (which only holds the location)."""
    soup = BeautifulSoup(html, "lxml")
    candidates = []
    seen_urls = set()

    for a in soup.find_all("a", href=lambda h: h and h.startswith("/job/?id=")):
        full_url = urljoin(base_url, a["href"].strip())
        if full_url in seen_urls:
            continue
        container = a.parent.parent if a.parent and a.parent.parent else a.parent
        title = container.get_text(" ", strip=True) if container else ""
        if not title:
            continue
        seen_urls.add(full_url)
        candidates.append({"title": title, "url": full_url})

    return candidates


def _extract_jsonld_jobs(html: str, base_url: str) -> list[dict]:
    """Some career pages embed schema.org JobPosting structured data
    (<script type="application/ld+json">, either standalone or nested in an
    @graph list) purely for Google Jobs SEO indexing. Found via Axonius,
    where the visible job rows are React <button> elements with no href and
    no attribute JS binds to (no XHR call visible either) -- but this
    structured data is a clean, complete alternative: title, per-job url
    (with a real gh_jid / equivalent query param), and location all
    included, regardless of how the visible DOM renders them."""
    soup = BeautifulSoup(html, "lxml")
    candidates = []
    seen_urls = set()

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except json.JSONDecodeError:
            continue
        items = data.get("@graph", []) if isinstance(data, dict) else data
        if isinstance(data, dict) and "@graph" not in data:
            items = [data]
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or item.get("@type") != "JobPosting":
                continue
            title = (item.get("title") or "").strip()
            job_url = item.get("url")
            if not title or not job_url:
                continue
            full_url = urljoin(base_url, job_url)
            if full_url in seen_urls:
                continue
            location = (item.get("jobLocation") or {}).get("name") or ""
            display_title = f"{title} ({location})" if location else title
            seen_urls.add(full_url)
            candidates.append({"title": display_title, "url": full_url})

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
    can differ from a secondary category it's also tagged under.

    There is no real per-job URL: the site is a client-side app that never
    updates the browser URL for any click (category, job, or otherwise) --
    confirmed no query string or hash it reads either. A "#job-<id>" suffix
    on the plain listing URL is the honest choice: it navigates to the
    general jobs page (not a fabricated-looking specific-job link) while
    still giving each job a unique URL, which storage.py/tracker.py rely on
    for dedup -- without that they'd collapse every job here into one."""
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
        job_url = f"{base}#job-{job_id}"
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


def _extract_comeet_careers_api(site: dict) -> list[dict]:
    """Comeet's newer public Careers API (careers-api/2.0) -- distinct from
    the older comeet.com/jobs/<company> board pages already handled by the
    generic scraper. Unlike Shufersal/HiBob's session-gated endpoints, this
    one is genuinely stateless: company_uid + token are both visible in the
    page's own network calls, and a plain call works with neither. Schema
    per Comeet's own API docs (developers.comeet.com) describes a
    {"positions": [...]} wrapper, but a live call (Hunters' board) returned
    a bare list instead -- handle both shapes."""
    payload = _fetch_json(site["api_url"])
    positions = payload.get("positions", []) if isinstance(payload, dict) else payload
    candidates = []
    for pos in positions:
        title = (pos.get("name") or "").strip()
        job_url = pos.get("url_active_page") or pos.get("url_comeet_hosted_page")
        if not title or not job_url:
            continue
        loc = pos.get("location") or {}
        location = ", ".join(b for b in (loc.get("name"), loc.get("country")) if b)
        display_title = f"{title} ({location})" if location else title
        candidates.append({"title": display_title, "url": job_url})
    return candidates


def _extract_shufersal(site: dict, browser) -> list[dict]:
    """Shufersal's career page (a Wix site) loads all positions via a POST
    to a Velo backend method (Position.jsw/searchPosition.ajax) rather than
    rendering real links -- the generic scraper only ever sees Wix chrome
    (nav links, footer), never an actual job. The endpoint also 401s when
    called directly (needs session context from the page load), so capture
    its response through an already-open page instead of hitting it as a
    standalone API."""
    page = browser.new_page(user_agent=_UA)
    try:
        with page.expect_response(
            lambda r: "searchPosition" in r.url, timeout=25000
        ) as resp_info:
            page.goto(site["url"], wait_until="load", timeout=25000)
        payload = resp_info.value.json()
    finally:
        page.close()

    candidates = []
    for job in payload.get("result", []):
        title = (job.get("description") or "").strip()
        order_id = job.get("order_id")
        if not title or order_id is None:
            continue
        area = job.get("work_area") or ""
        display_title = f"{title} ({area})" if area else title
        # No real per-job deep link exists (client-side filtered SPA, doesn't
        # read query strings or hashes) -- a "#position-<id>" suffix is the
        # honest choice: it navigates to the general jobs page rather than a
        # fabricated-looking specific-job link, while still giving each job
        # a unique URL, which storage.py/tracker.py rely on for dedup.
        job_url = f"{site['url']}#position-{order_id}"
        candidates.append({"title": display_title, "url": job_url})
    return candidates


def _extract_hibob_careers(site: dict, browser) -> list[dict]:
    """HiBob-hosted career boards (<company>.careers.hibob.com) render each
    job as an "Apply" button with the real title only in page JS state, not
    the link text -- the generic scraper gets a real, unique per-job URL but
    a useless "Apply" title for every single one. The actual data comes from
    /api/job-ad, which -- like Shufersal's endpoint -- 401s without session
    context from the page load, so capture it through an already-open page."""
    page = browser.new_page(user_agent=_UA)
    try:
        with page.expect_response(
            lambda r: "/api/job-ad" in r.url, timeout=25000
        ) as resp_info:
            page.goto(site["url"], wait_until="load", timeout=25000)
        payload = resp_info.value.json()
    finally:
        page.close()

    base = site["url"].rstrip("/")
    candidates = []
    for job in payload.get("jobAdDetails", []):
        title = (job.get("title") or "").strip()
        job_id = job.get("id")
        if not title or not job_id:
            continue
        location = ", ".join(b for b in (job.get("site"), job.get("country")) if b)
        display_title = f"{title} ({location})" if location else title
        job_url = f"{base}/jobs/{job_id}/apply"
        candidates.append({"title": display_title, "url": job_url})
    return candidates


_TECHMAP_SKIP_LEVELS = {"Manager", "Tech Lead", "Architect", "Executive"}


def _extract_techmap_csv(site: dict) -> list[dict]:
    """techmap (https://github.com/mluggy/techmap) publishes a daily CSV of
    open software roles aggregated across ~1000 Israeli tech companies' ATS
    boards -- one more candidate source alongside our own per-site scrapers,
    without having to scrape each of those companies ourselves. Its `level`
    column is only a coarse IC-vs-management split (not IC seniority), so we
    just use it to drop obvious non-IC tracks early; title-based junior/
    senior scoring still happens downstream like any other candidate."""
    req = urllib.request.Request(site["url"], headers=_API_HEADERS)
    with urllib.request.urlopen(req, timeout=20, context=_SSL_CONTEXT) as resp:
        text = resp.read().decode("utf-8-sig")

    candidates = []
    for row in csv.DictReader(text.splitlines()):
        if row.get("level") in _TECHMAP_SKIP_LEVELS:
            continue
        title = (row.get("title") or "").strip()
        job_url = (row.get("url") or "").strip()
        if not title or not job_url:
            continue
        company = row.get("company") or ""
        city = row.get("city") or ""
        # city stays folded into the scored title (location keyword matching
        # needs it); company is kept separate so main.py/tracker.py can show
        # it as the actual employer instead of the generic "TechMap" source
        # name -- these postings live on LinkedIn/Comeet, not on techmap.
        display_title = f"{title} ({city})" if city else title
        candidate = {"title": display_title, "url": job_url}
        if company:
            candidate["company"] = company
        candidates.append(candidate)
    return candidates


def fetch_job_candidates(site: dict, browser) -> list[dict]:
    """Return a de-duplicated list of {"title": ..., "url": ...} candidate
    job postings for a site. Sites backed by a known JSON API are queried
    directly; everything else falls back to rendering + link extraction.
    `browser` is an already-open Playwright browser, shared across the
    whole run -- see main.py."""
    engine = site.get("engine", "generic")

    if engine == "varonis_api":
        return _extract_varonis_api(site)
    if engine == "hunter_hrms_api":
        return _extract_hunter_hrms_api(site)
    if engine == "oracle_hcm_api":
        return _extract_oracle_hcm_api(site)
    if engine == "greenhouse_api":
        return _extract_greenhouse_api(site)
    if engine == "comeet_careers_api":
        return _extract_comeet_careers_api(site)
    if engine == "techmap_csv":
        return _extract_techmap_csv(site)
    if engine == "shufersal":
        return _extract_shufersal(site, browser)
    if engine == "hibob_careers":
        return _extract_hibob_careers(site, browser)

    if engine == "workday":
        extract = lambda h: _extract_workday(h, site["url"])
    elif engine == "deep_instinct":
        extract = lambda h: _extract_deep_instinct(h, site["url"])
    elif engine == "drivenets":
        extract = lambda h: _extract_drivenets(h, site["url"])
    elif engine == "jsonld_jobs":
        extract = lambda h: _extract_jsonld_jobs(h, site["url"])
    else:
        extract = lambda h: _extract_generic(h, site["url"])

    html = _render_page(site["url"], browser, wait_selector=site.get("wait_selector"))
    candidates = extract(html)
    if candidates:
        return candidates

    # A real page that's still loading (slow/analytics-heavy sites can keep
    # "networkidle" from ever firing, e.g. a continuous chat-widget poll)
    # can render with zero real content on the first attempt -- found via
    # sites (Nanox, Strauss Group) that returned real jobs on a manual
    # re-check but had recorded 0 candidates on every scheduled run for
    # days straight. Retry once with more time before concluding the site
    # genuinely has nothing, rather than silently locking in an empty
    # baseline that then looks like "0 open positions" indefinitely.
    html = _render_page(
        site["url"], browser, wait_selector=site.get("wait_selector"), timeout_ms=40000
    )
    return extract(html)
