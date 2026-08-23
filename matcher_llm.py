"""
LLM-based relevancy scorer using the Google Gemini free tier
(https://aistudio.google.com/apikey).

WHY THIS CAN'T CHARGE YOU, AND WHAT YOU STILL NEED TO CHECK YOURSELF:
- A Google AI Studio API key on its own free tier has no payment method
  attached. If you exceed the free quota, Google returns an HTTP 429
  error -- it does not silently start billing you.
- The ONLY way this project could ever cost money is if the Google
  account behind your API key has been manually upgraded to a paid tier
  (linking a billing account) in Google Cloud / AI Studio. This script
  cannot see or control that setting -- go to
  https://aistudio.google.com/apikey and confirm you're on "Free tier",
  not "Pay-as-you-go", before using this.
- On top of that account-level fact, this module adds its own hard caps
  (MAX_LLM_CALLS_PER_RUN and rate limiting below) so it will never even
  approach the free quota ceiling regardless of how many jobs are found.

If the API key is missing, disabled, rate-limited, or errors for any
reason, callers should catch the exception and fall back to
matcher_keywords.py -- see matcher.py.
"""

from __future__ import annotations

import json
import os
import time

import requests

from config import WEIGHTS, COMPATIBILITY_THRESHOLD

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
# "-latest" is a Google-maintained alias that always points at their current
# recommended flash model, so this doesn't need to be re-pinned every time
# a specific dated model version gets deprecated (as gemini-2.5-flash was).
GEMINI_MODEL = "gemini-flash-latest"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)

# --- Hard safety caps -------------------------------------------------
# NOTE: measured against this project's actual free-tier key, the daily
# quota was as low as 20 requests/day for the current flash model --
# nowhere near the ~1,500/day some free-tier docs describe (it appears to
# vary by project/model and Google changes it without much notice). Don't
# assume MAX_LLM_CALLS_PER_RUN below will actually be reached; in practice
# you'll usually hit Google's own 429 first, which is handled gracefully
# (falls back to keyword matching -- see LLMMatcherUnavailable). Check
# https://ai.dev/rate-limit for the current number on your own key.
MAX_LLM_CALLS_PER_RUN = 150          # hard stop, regardless of how many jobs are found
MIN_SECONDS_BETWEEN_CALLS = 4.0      # keeps us well under free RPM limits
REQUEST_TIMEOUT_SECONDS = 20

_call_count = 0
_last_call_time = 0.0

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "is_job_posting": {"type": "boolean"},
        "role_match": {"type": "boolean"},
        "level_match": {"type": "boolean"},
        "level_explicitly_senior": {"type": "boolean"},
        "location_match": {"type": "boolean"},
        "location_explicitly_foreign": {"type": "boolean"},
        "reasoning": {"type": "string"},
    },
    "required": [
        "is_job_posting", "role_match", "level_match",
        "level_explicitly_senior", "location_match",
        "location_explicitly_foreign", "reasoning",
    ],
}

PROMPT_TEMPLATE = """You are screening ONE job posting for a candidate with
this profile: a junior backend Python developer (~1 year of professional
experience as a "Junior Software Developer", so 0-2 years overall) based in
central Israel (Gush Dan area: Tel Aviv, Ramat Gan, Herzliya, Petah Tikva,
Bnei Brak, Givatayim, Rishon LeZion, etc). Hands-on experience: AWS (Lambda,
S3, ECS, CloudWatch, Secrets Manager), Docker, RabbitMQ, microservices
architecture, and building/maintaining backend APIs. Also has full-stack
training (JavaScript/TypeScript, React, Node.js) but is specifically
targeting Backend or Automation Developer roles, not frontend-focused ones.
Postings may be in English or Hebrew.

Job posting title/text:
\"\"\"{title}\"\"\"

Additional context (may be empty):
\"\"\"{extra_text}\"\"\"

Decide these yes/no questions. Missing information should default to false
for the *_match fields (treat "unknown" as "no bonus", not as a conflict),
but the *_explicitly_* fields must only be true when the text actually says
so -- never guess a conflict from silence.

- is_job_posting: Does this text describe a SPECIFIC open role someone can
  apply for right now? Answer false for a blog post, employee spotlight/
  interview, video, news article, product or marketing page, developer/API
  portal, a "join our talent community" signup, or a team/department
  overview page that isn't a single requisition -- even if it's full of
  role-sounding words like "engineer" or "developer". If false, none of
  the other answers matter (there's no role to evaluate).
- role_match: Is this a software development / programming role this
  candidate would actually want to apply to? Backend, Python, automation,
  DevOps-adjacent, or cloud/infrastructure developer roles are the strongest
  fit given their background -- treat those as a clear yes. General/full
  stack software developer roles are also a yes (their training covers
  that). A role that's purely frontend-focused (no backend component at
  all) is a weaker fit but still counts as role_match, since it's still
  hands-on coding -- just note that in reasoning. Answer false for
  non-coding roles (pure QA/support/sales/hardware/ops) unless clearly
  hands-on coding.
- level_match: Is this appropriate for someone with 0-2 years of experience
  (junior, entry-level, new grad, no explicit senior requirement)?
- level_explicitly_senior: Does the text explicitly require a senior/mid-level
  candidate, OR is this a people-management/management-track role rather
  than an individual-contributor one? This includes the obvious titles
  ("senior", "staff", "principal", "team/tech lead", "manager"/"מנהל" in any
  form -- e.g. "Engineering Manager", "R&D Manager") AND any explicit
  experience requirement above 2 years in any phrasing -- "3+ years",
  "3 years", "3-5 years", a Hebrew phrase like "ניסיון של 3 שנים", or
  describing the candidate as "experienced"/"מנוסה" rather than
  junior/entry-level. This should be true even if level_match above is
  false for the same reason -- it's a stronger, outright-disqualifying
  signal, not just an absence of a junior signal.
- location_match: Is the role based in or near central Israel / Gush Dan /
  Tel Aviv area, or remote-within-Israel?
- location_explicitly_foreign: Does the text explicitly name a location
  outside Israel (a specific non-Israel country or city)? Answer false if
  location simply isn't mentioned at all -- only true when a foreign
  location is actually stated.

Respond with ONLY a JSON object, no other text, matching this exact shape:
{{"is_job_posting": true or false, "role_match": true or false, "level_match": true or false, "level_explicitly_senior": true or false, "location_match": true or false, "location_explicitly_foreign": true or false, "reasoning": "one short sentence explaining the decision"}}
"""


class LLMMatcherUnavailable(Exception):
    """Raised whenever the LLM matcher can't or shouldn't be used for this
    call -- callers should catch this and fall back to keyword matching."""


def _enforce_rate_limit():
    global _last_call_time
    elapsed = time.time() - _last_call_time
    if elapsed < MIN_SECONDS_BETWEEN_CALLS:
        time.sleep(MIN_SECONDS_BETWEEN_CALLS - elapsed)


def _call_gemini(title: str, extra_text: str) -> dict:
    if not GEMINI_API_KEY:
        raise LLMMatcherUnavailable(
            "GEMINI_API_KEY environment variable is not set. "
            "Get a free key at https://aistudio.google.com/apikey"
        )

    global _call_count
    if _call_count >= MAX_LLM_CALLS_PER_RUN:
        raise LLMMatcherUnavailable(
            f"Hit MAX_LLM_CALLS_PER_RUN ({MAX_LLM_CALLS_PER_RUN}) for this run -- "
            "remaining jobs will use keyword matching instead."
        )

    _enforce_rate_limit()

    body = {
        "contents": [
            {"parts": [{"text": PROMPT_TEMPLATE.format(title=title, extra_text=extra_text)}]}
        ],
        "generationConfig": {
            "temperature": 0,
            "response_mime_type": "application/json",
            "response_schema": RESPONSE_SCHEMA,
        },
    }

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json=body,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException as e:
        raise LLMMatcherUnavailable(f"Network error calling Gemini: {e}") from e

    global _last_call_time
    _last_call_time = time.time()

    if resp.status_code == 429:
        raise LLMMatcherUnavailable("Gemini free-tier rate limit hit (HTTP 429).")
    if not resp.ok:
        raise LLMMatcherUnavailable(f"Gemini API error {resp.status_code}: {resp.text[:200]}")

    _call_count += 1

    try:
        data = resp.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise LLMMatcherUnavailable(f"Unexpected Gemini response shape: {e}") from e


def score_job_llm(title: str, extra_text: str = "") -> dict:
    """
    Same return shape as matcher_keywords.score_job_keywords(), plus
    non_job_content (the keyword matcher has no equivalent -- it can't
    tell a blog post from a posting, only the LLM path can):
    {"score": int, "compatible": bool, "matched": [categories],
     "senior_conflict": bool, "foreign_conflict": bool,
     "non_job_content": bool, "reasoning": str}

    Raises LLMMatcherUnavailable if the LLM can't be used right now --
    callers must catch this and fall back to keyword matching.
    """
    result = _call_gemini(title, extra_text)

    non_job_content = not result.get("is_job_posting", True)

    matched = []
    score = 0
    if result.get("role_match"):
        matched.append("role")
        score += WEIGHTS["role"]
    if result.get("level_match"):
        matched.append("level")
        score += WEIGHTS["level"]
    if result.get("location_match"):
        matched.append("location")
        score += WEIGHTS["location"]

    # Explicit senior/foreign signals are hard disqualifiers, same as
    # matcher_keywords.py -- a role+location score alone must not be enough
    # to mark a clearly senior or clearly non-Israel posting as compatible.
    senior_conflict = bool(result.get("level_explicitly_senior"))
    foreign_conflict = bool(result.get("location_explicitly_foreign"))

    compatible = (
        score >= COMPATIBILITY_THRESHOLD
        and not senior_conflict
        and not foreign_conflict
        and not non_job_content
    )

    return {
        "score": score,
        "compatible": compatible,
        "matched": matched,
        "senior_conflict": senior_conflict,
        "foreign_conflict": foreign_conflict,
        "non_job_content": non_job_content,
        # the LLM already scores role_match=false (semantically) for
        # hardware/mechanical/etc titles, so there's no separate signal to
        # extract here -- this key only exists for shape parity with
        # matcher_keywords.py, whose bare "engineer" keyword needs one.
        "non_software_conflict": False,
        "reasoning": result.get("reasoning", ""),
    }
