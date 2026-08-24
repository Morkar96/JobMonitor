"""
Smoke-tests for newly added SITES entries in config.py.

Verifies each new site is reachable and that the scraper extracts
candidates that look like real job postings -- not just an empty result,
or a page's repeated nav/cookie-consent boilerplate (a real failure mode
found while auditing this batch: several marketing sites return dozens of
identical "Learn more about this provider" cookie-consent links before
any real job content).

This does NOT run main.py's pipeline -- no data/seen_jobs.json or
reports/ files are touched. It only calls scraper.fetch_job_candidates
directly against the live sites, so results depend on those sites being
reachable and unchanged at test time.

Run with: pytest test_new_sites.py -v
"""

from collections import Counter

import pytest
from playwright.sync_api import sync_playwright

from config import SITES
from scraper import fetch_job_candidates

# Sites added in the 2026-08-24 upload -- see config.py history. Update this
# list (or replace with a different lookup) for the next batch of new sites.
NEW_SITE_NAMES = [
    "Zafran", "Wix", "monday.com", "Fiverr", "Wiz", "Snyk", "Payoneer",
    "Yotpo", "JFrog", "WalkMe", "Armis", "Claroty", "SentinelOne",
    "Similarweb", "Kaltura", "Global-e", "Bringg", "Deep Instinct",
    "AI21 Labs", "Axonius", "Hunters", "Torq", "Pentera", "Explorium",
    "DoubleVerify", "Papaya Global", "Rapyd", "Bizzabo", "Trigo",
    "HoneyBook", "Verbit", "Personetics", "Redis", "Gett", "Playtika",
    "Moon Active", "Outbrain", "VAST Data", "XM Cyber", "Cyolo",
    "Salt Security", "Lightricks", "DriveNets", "Fundbox",
]

# If a single title accounts for more than this share of all candidates,
# it's almost certainly boilerplate (e.g. a cookie-consent "Learn more
# about this provider" link repeated once per ad partner) rather than
# distinct job postings.
MAX_REPEATED_TITLE_RATIO = 0.3


def _new_sites():
    by_name = {s["name"]: s for s in SITES}
    missing = [n for n in NEW_SITE_NAMES if n not in by_name]
    assert not missing, f"NEW_SITE_NAMES entries missing from config.SITES: {missing}"
    return [by_name[n] for n in NEW_SITE_NAMES]


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.mark.parametrize("site", _new_sites(), ids=lambda s: s["name"])
def test_new_site_scraping(site, browser):
    """A new site should return real-looking job candidates, not an empty
    result or a page's repeated nav/cookie-consent boilerplate. A failure
    here means the site likely needs a custom engine (see scraper.py's
    _extract_* functions) or a wait_selector, the same way TechMap/Shufersal
    needed dedicated handling."""
    candidates = fetch_job_candidates(site, browser)
    assert candidates, f"scraper found 0 candidates at {site['url']}"

    titles = [c["title"] for c in candidates]
    most_common_title, count = Counter(titles).most_common(1)[0]
    ratio = count / len(titles)
    assert ratio <= MAX_REPEATED_TITLE_RATIO, (
        f"{count}/{len(titles)} candidates ({ratio:.0%}) share the identical "
        f"title {most_common_title!r} -- likely repeated nav/consent "
        f"boilerplate rather than real job postings"
    )
