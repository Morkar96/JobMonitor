# Job Monitor

Watches a fixed list of career pages, detects newly posted jobs, and scores
each one for "junior developer, center of Israel" compatibility (English +
Hebrew keywords: מתכנת/ת, מפתח/ת, ג'וניור, ללא ניסיון, etc.).

## Setup

```bash
cd job_monitor
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

## First run (creates the baseline)

```bash
python main.py
```

Every job currently listed on each site becomes the "already seen" baseline
(so it won't be re-reported next time), but this first run still evaluates
and prints all of today's jobs that score >=75% compatible, so you don't
lose today's postings.

## Every later run (only reports new postings)

```bash
python main.py
```

Same command — the script checks `data/seen_jobs.json` automatically and
only evaluates/report jobs it hasn't seen on that site before.

## Test a single site

```bash
python main.py --site "HiBob"
```

(name must match an entry in `config.py`)

## Automate it

Run on a schedule with cron (macOS/Linux) or Task Scheduler (Windows), e.g.
every morning at 9am:

```
0 9 * * * cd /path/to/job_monitor && ./venv/bin/python main.py >> run.log 2>&1
```

## How compatibility scoring works

Each job title is checked against three keyword categories:

| Category | Weight | Examples |
|---|---|---|
| role     | 40% | developer, engineer, מתכנת, מפתח |
| level    | 40% | junior, entry level, ג'וניור, ללא ניסיון |
| location | 20% | tel aviv, gush dan, תל אביב, רמת גן |

A job needs **role + level** matched (80%) to clear the 75% bar; location is
a bonus. Tune categories/weights/threshold in `config.py`.

## Notes / limitations

- Most target sites are JS-rendered (React SPAs, Workday), so this uses
  headless Chromium via Playwright — it's slower than plain `requests` but
  works on dynamic pages.
- The extractor is **generic** (grabs job-like links off any page) plus a
  **Workday-specific** extractor (used automatically for
  `*.myworkdayjobs.com` sites, e.g. Cadence). Some heavily custom sites
  (e.g. bank/insurer portals, municipality boards) may need their own
  CSS selector added to `config.py` if the generic extractor picks up too
  much noise or misses postings — flag which ones need tuning after a
  first run and I can add site-specific selectors.
- Be a considerate scraper: don't run this more than a few times a day per
  site, and check each site's `robots.txt` / terms if you plan to automate
  this long-term.
