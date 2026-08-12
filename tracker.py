"""Append-only log of compatible jobs, grouped by day, as a GitHub-flavored
Markdown checklist. Viewed on GitHub, each "- [ ]" renders as a clickable
checkbox you can tick off (as a repo collaborator) once you've applied --
GitHub commits the tick directly back to the file, no extra tooling needed.
"""

import os
import re
from datetime import date

TRACKER_PATH = "reports/relevant_jobs.md"

_LOGGED_URL_RE = re.compile(r"\]\(([^)]+)\)")


def _flatten(text: str) -> str:
    """Some scraped titles contain raw embedded newlines (a site's HTML had
    literal line breaks within one text node). Left as-is, that splits a
    single bullet across multiple physical lines, which breaks Markdown
    list rendering and defeats simple line-based tooling (dedup scripts,
    grep, etc.). Collapse all whitespace runs to a single space."""
    return " ".join(text.split())


def append_relevant_jobs(rows: list[dict], path: str = TRACKER_PATH):
    """rows: compatible job rows (as built in main.process_site).

    In the common case, each row's URL has already passed through
    storage's seen-URL dedup, so it's a job not logged before. But that
    dedup state (data/seen_jobs.json) can lose continuity -- a manual
    reset, a lost write from a race with another run, etc. -- in which
    case the same job would be scored as "new" again and land here. Since
    this file is what gets actually read/checked off, it needs to stay
    duplicate-free on its own regardless of what upstream state did, so
    we re-check every row's URL against everything already logged in the
    file (not just today's section) before appending."""
    if not rows:
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)

    exists = os.path.exists(path)
    existing = ""
    if exists:
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()

    already_logged = set(_LOGGED_URL_RE.findall(existing))
    rows = [r for r in rows if r["url"] not in already_logged]
    if not rows:
        return

    header = f"## {date.today().isoformat()}"
    bullets = "\n".join(
        # For aggregator sources (e.g. techmap), the site name is just the
        # feed, not the employer -- prefer the actual company when we have
        # one so the entry reads as "Check Point" instead of "TechMap".
        f"- [ ] **{r.get('company') or r['site']}** — {_flatten(r['title'])} ({r['score']}%) — [link]({r['url']})"
        for r in rows
    )

    if not exists:
        block = (
            "# Relevant Job Tracker\n\n"
            "Check a box on GitHub once you've submitted your application for that job.\n\n"
            f"{header}\n{bullets}\n"
        )
    elif header in existing:
        # today's section already exists and, since entries are appended
        # chronologically, is always the last one in the file
        block = f"\n{bullets}\n"
    else:
        block = f"\n{header}\n{bullets}\n"

    with open(path, "a" if exists else "w", encoding="utf-8") as f:
        f.write(block)
