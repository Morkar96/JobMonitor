"""Append-only log of compatible jobs, grouped by day, as a GitHub-flavored
Markdown checklist. Viewed on GitHub, each "- [ ]" renders as a clickable
checkbox you can tick off (as a repo collaborator) once you've applied --
GitHub commits the tick directly back to the file, no extra tooling needed.
"""

import os
from datetime import date

TRACKER_PATH = "reports/relevant_jobs.md"


def append_relevant_jobs(rows: list[dict], path: str = TRACKER_PATH):
    """rows: compatible job rows (as built in main.process_site). Each row's
    URL has already passed through storage's seen-URL dedup, so every call
    here is guaranteed to be jobs not logged before -- safe to just append."""
    if not rows:
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    header = f"## {date.today().isoformat()}"
    bullets = "\n".join(
        f"- [ ] **{r['site']}** — {r['title']} ({r['score']}%) — [link]({r['url']})"
        for r in rows
    )

    exists = os.path.exists(path)
    existing = ""
    if exists:
        with open(path, "r", encoding="utf-8") as f:
            existing = f.read()

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
