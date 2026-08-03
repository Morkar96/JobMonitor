"""
Job monitor entry point.

First run per site: everything currently listed becomes the "baseline"
(marked as seen so it won't be reported again as new), and baseline jobs
that score >= 75% compatible are still printed/saved so you see today's
relevant postings right away.

Every later run: only NEW postings (not in the stored baseline) are
compatibility-checked and reported. New postings are added to the seen
set either way, so nothing gets reprocessed on the next run.

Usage:
    python main.py                # run against all configured sites
    python main.py --site "HiBob" # run against a single site (for testing)
"""

import argparse
import csv
import os
import sys
import traceback
from datetime import datetime

from config import SITES, REPORTS_DIR
import storage
from scraper import fetch_job_candidates
from matcher import score_job


def process_site(site: dict, data: dict) -> list[dict]:
    """Scrape one site, diff against storage, score candidates.
    Returns a list of report rows for jobs worth telling the user about."""
    name = site["name"]
    print(f"\n[{name}] fetching {site['url']} ...")

    try:
        candidates = fetch_job_candidates(site)
    except Exception as e:
        print(f"[{name}] ERROR while scraping: {e}")
        traceback.print_exc()
        return []

    print(f"[{name}] found {len(candidates)} candidate link(s) on the page")

    first_run = storage.is_first_run(data, name)
    seen_urls = storage.get_seen_urls(data, name)
    current_urls = {c["url"] for c in candidates}

    if first_run:
        to_evaluate = candidates
        run_type = "BASELINE"
    else:
        to_evaluate = [c for c in candidates if c["url"] not in seen_urls]
        run_type = "NEW"

    print(f"[{name}] {len(to_evaluate)} job(s) to evaluate ({run_type})")

    rows = []
    for job in to_evaluate:
        result = score_job(job["title"])
        rows.append({
            "site": name,
            "run_type": run_type,
            "title": job["title"],
            "url": job["url"],
            "score": result["score"],
            "compatible": result["compatible"],
            "matched_categories": ", ".join(result["matched"]),
            "checked_at": datetime.now().isoformat(timespec="seconds"),
        })

    # persist: mark everything currently on the page as seen
    storage.update_site(data, name, current_urls)

    return rows


def write_report(rows: list[dict]) -> str:
    os.makedirs(REPORTS_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(REPORTS_DIR, f"jobs_{ts}.csv")
    fieldnames = ["site", "run_type", "title", "url", "score", "compatible",
                  "matched_categories", "checked_at"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", help="Only run a single site by name (for testing)")
    args = parser.parse_args()

    sites = SITES
    if args.site:
        sites = [s for s in SITES if s["name"].lower() == args.site.lower()]
        if not sites:
            print(f"No configured site named '{args.site}'. Available: "
                  f"{', '.join(s['name'] for s in SITES)}")
            sys.exit(1)

    data = storage.load()
    all_rows = []

    for site in sites:
        all_rows.extend(process_site(site, data))

    storage.save(data)

    if not all_rows:
        print("\nNo new/baseline jobs found this run.")
        return

    compatible_rows = [r for r in all_rows if r["compatible"]]

    print(f"\n{'=' * 60}")
    print(f"TOTAL evaluated: {len(all_rows)} | COMPATIBLE (>=75%): {len(compatible_rows)}")
    print(f"{'=' * 60}")
    for r in compatible_rows:
        print(f"[{r['site']}] ({r['score']}%) {r['title']}\n    {r['url']}")

    report_path = write_report(all_rows)
    print(f"\nFull report (including non-matches) saved to: {report_path}")


if __name__ == "__main__":
    main()
