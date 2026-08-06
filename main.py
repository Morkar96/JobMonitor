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

from playwright.sync_api import sync_playwright

from config import SITES, REPORTS_DIR
import storage
import tracker
from scraper import fetch_job_candidates, fetch_job_detail_text
from matcher import score_job
from matcher_keywords import score_job_keywords

# Stage 1 scores a job on its title alone (cheap, from the listing page we
# already scraped). Stage 2 only kicks in for jobs stage 1 marked
# compatible: it fetches the actual posting page and re-scores against the
# real body text, which often states an experience/location requirement
# the title never mentioned. Capped independently of the LLM's own
# per-run cap since it's bounded by page-load time, not API quota -- with
# a shared browser (see main()) each fetch is a few seconds, so this caps
# worst-case stage-2 time at roughly MAX_STAGE2_FETCHES_PER_RUN * ~10s.
MAX_STAGE2_FETCHES_PER_RUN = 60
_stage2_fetch_count = 0


def evaluate_job(job: dict, browser) -> dict:
    """Score a job, refining with stage 2 if stage 1 says it's compatible.

    Stage 1 always uses keyword matching, not the LLM. The Gemini free
    tier's actual daily quota turned out to be as low as 20 requests/day
    (project- and model-dependent, far below what the "~1,500/day" comment
    in matcher_llm.py assumed) -- spending that on stage 1, which runs
    across every single candidate on every site, exhausts it almost
    immediately and leaves nothing for stage 2. Reserving the LLM for
    stage 2 instead means its scarce quota goes to the jobs that already
    cleared the cheap screen, which is both a much smaller set and a much
    higher-value place to spend a semantic check (catching a blog post or
    an implicit seniority requirement the keyword list can't)."""
    global _stage2_fetch_count

    result = score_job_keywords(job["title"])
    result["engine"] = "keywords"
    result.setdefault("stage2_checked", False)
    if not result["compatible"]:
        return result

    if _stage2_fetch_count >= MAX_STAGE2_FETCHES_PER_RUN:
        return result

    try:
        detail_text = fetch_job_detail_text(job["url"], browser)
    except Exception as e:
        print(f"    [stage2] couldn't fetch job page, keeping title-only result: {e}")
        return result

    _stage2_fetch_count += 1
    refined = score_job(job["title"], extra_text=detail_text)
    refined["stage2_checked"] = True
    if result["compatible"] and not refined["compatible"]:
        reason = "non-job content" if refined.get("non_job_content") else (
            "senior/experience" if refined.get("senior_conflict") else (
            "foreign location" if refined.get("foreign_conflict") else "score"))
        print(f"    [stage2/{refined['engine']}] demoted ({reason}) after reading full posting: {job['title'][:60]}")
    return refined


def process_site(site: dict, data: dict, browser) -> list[dict]:
    """Scrape one site, diff against storage, score candidates.
    Returns a list of report rows for jobs worth telling the user about."""
    name = site["name"]
    print(f"\n[{name}] fetching {site['url']} ...")

    try:
        candidates = fetch_job_candidates(site, browser)
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
        result = evaluate_job(job, browser)
        rows.append({
            "site": name,
            "run_type": run_type,
            "title": job["title"],
            "url": job["url"],
            "score": result["score"],
            "compatible": result["compatible"],
            "matched_categories": ", ".join(result["matched"]),
            "stage2_checked": result["stage2_checked"],
            "engine": result["engine"],
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
                  "matched_categories", "stage2_checked", "engine", "checked_at"]
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            for site in sites:
                all_rows.extend(process_site(site, data, browser))
        finally:
            browser.close()

    storage.save(data)

    compatible_rows = [r for r in all_rows if r["compatible"]]
    tracker.append_relevant_jobs(compatible_rows)
    _write_github_actions_output(len(compatible_rows))

    if not all_rows:
        print("\nNo new/baseline jobs found this run.")
        return

    stage2_checked = sum(1 for r in all_rows if r["stage2_checked"])
    llm_used = sum(1 for r in all_rows if r["engine"] == "llm")
    print(f"\n{'=' * 60}")
    print(f"TOTAL evaluated: {len(all_rows)} | COMPATIBLE (>=75%): {len(compatible_rows)} "
          f"| stage-2 refined: {stage2_checked}/{MAX_STAGE2_FETCHES_PER_RUN} cap")
    print(f"Stage-2 LLM calls that actually succeeded: {llm_used}/{stage2_checked} "
          f"(rest fell back to keyword matching -- usually the Gemini free-tier "
          f"daily quota, which can be as low as 20 req/day)")
    print(f"{'=' * 60}")
    for r in compatible_rows:
        print(f"[{r['site']}] ({r['score']}%) {r['title']}\n    {r['url']}")

    report_path = write_report(all_rows)
    print(f"\nFull report (including non-matches) saved to: {report_path}")


def _write_github_actions_output(compatible_count: int):
    """When running inside GitHub Actions, expose the compatible-job count
    as a step output so the workflow can use it (e.g. to title an alert
    issue) without having to re-parse our report files."""
    output_path = os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    with open(output_path, "a", encoding="utf-8") as f:
        f.write(f"compatible_count={compatible_count}\n")


if __name__ == "__main__":
    main()
