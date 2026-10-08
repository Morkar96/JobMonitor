"""
Consistency audit for reports/relevant_jobs.md.

Every entry in that file was marked "compatible" by the matcher rules in
effect on the day it was scraped. Those rules change over time (bug fixes,
new keywords), so an older entry can be sitting there violating a rule that
didn't exist yet when it was logged -- that's exactly how two real bugs
were caught in this project (a "manager" title and a "Remote, US, CA"
posting that should never have passed). This test re-checks every logged
entry's title against the *current* keyword rules so that kind of bug gets
caught automatically going forward instead of by someone eyeballing the
file.

Deliberately checks only for hard conflicts (senior/foreign/periphery/
non-software), not the overall compatibility score: stage 2 (see main.py)
scores against the full posting page, which isn't available here -- only
the title text that got stored. A title-only re-score would lose location/
level bonuses that came from page body text and falsely "fail" perfectly
good entries. Conflicts, by contrast, are hard disqualifiers that mostly
show up in the title itself in practice (every real bug caught so far did),
so they're a signal reliable enough to assert on without the full page text.

Run with: pytest test_relevant_jobs_audit.py -v
"""

import re

from matcher_keywords import score_job_keywords

TRACKER_PATH = "reports/relevant_jobs.md"

_BULLET_RE = re.compile(
    r"^- \[([ x])\] \*\*(.+?)\*\* — (.+?) \((\d+)%\) — \[link\]\((.+?)\)$"
)


def _load_entries():
    with open(TRACKER_PATH, encoding="utf-8") as f:
        lines = f.readlines()
    entries = []
    for line in lines:
        m = _BULLET_RE.match(line.strip())
        if not m:
            continue
        checked, company, title, score, url = m.groups()
        entries.append({
            "checked": checked == "x", "company": company, "title": title,
            "score": int(score), "url": url,
        })
    return entries


_ENTRIES = _load_entries()


def test_tracker_has_entries():
    """Sanity check the parser itself isn't silently matching nothing --
    a tracker format change should fail loudly here, not show up as every
    other test in this file trivially passing on zero entries."""
    assert len(_ENTRIES) > 10, (
        f"only parsed {len(_ENTRIES)} entries from {TRACKER_PATH} -- "
        "the bullet format may have changed; check _BULLET_RE"
    )


def test_no_conflicting_entries():
    """Every still-actionable (unchecked) entry's title should be free of
    hard conflicts under the current keyword rules. A failure here means
    either a real matcher bug (an old rule gap let something through that
    a newer rule would now catch) or a stale entry that should be cleaned
    out of the tracker -- see reports/relevant_jobs.md's history for prior
    examples of both.

    Checked-off entries are skipped on purpose: those represent an
    application already submitted, which a rule added afterward shouldn't
    retroactively flag -- it's a historical record at that point, not an
    actionable job the matcher needs to keep agreeing with."""
    violations = []
    for e in _ENTRIES:
        if e["checked"]:
            continue
        result = score_job_keywords(e["title"])
        conflicts = [
            name for name in
            ("senior_conflict", "foreign_conflict", "periphery_conflict", "non_software_conflict")
            if result.get(name)
        ]
        if conflicts:
            violations.append(f"{e['company']} — {e['title']!r}: {', '.join(conflicts)}")
    assert not violations, (
        f"{len(violations)} tracker entries violate current matcher rules:\n"
        + "\n".join(violations)
    )
